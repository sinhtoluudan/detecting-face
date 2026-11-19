import calendar
from datetime import date, timedelta
from functools import wraps
from threading import RLock
from fastapi import HTTPException
from . import database as store, config
from .calculations import bounds, calculate, parse_dt
from .security import visible_ids, require_visible, audit

# Single-process deployment: serializes compound business operations and month closing.
# Run ONE Uvicorn worker; use MongoDB transactions before scaling to multiple API processes.
MUTATION_LOCK = RLock()

def serialized(fn):
    @wraps(fn)
    def inner(*args, **kwargs):
        with MUTATION_LOCK:
            return fn(*args, **kwargs)
    return inner

def get(collection, id):
    doc = store.db[collection].find_one({'_id': id})
    if not doc:
        raise HTTPException(404, 'Không tìm thấy dữ liệu')
    return doc

def check_open(day):
    if store.db.months.find_one({'_id': str(day)[:7], 'locked': True}):
        raise HTTPException(409, 'Tháng này đã chốt công. HR phải mở lại trước khi thay đổi')

def month_range(month):
    try:
        first = date.fromisoformat(month+'-01')
        last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
        if len(month)!=7:
            raise ValueError()
        return first.isoformat(), last.isoformat()
    except ValueError:
        raise HTTPException(422, 'Tháng phải có dạng YYYY-MM')

def dates(start, end):
    day = date.fromisoformat(str(start))
    final = date.fromisoformat(str(end))
    while day <= final:
        yield day
        day += timedelta(days=1)

def scoped_query(user, field='user_id'):
    ids = visible_ids(user)
    return {} if ids is None else {field: {'$in': ids}}

def enriched_assignments(user, month):
    start, end = month_range(month)
    query = {**scoped_query(user), 'date': {'$gte': start, '$lte': end}}
    users = {x['_id']: x for x in store.db.users.find({}, {'password_hash': 0})}
    return [{**store.public(a), 'employee_name': users.get(a['user_id'],{}).get('name','Đã nghỉ việc'),
             'employee_code': users.get(a['user_id'],{}).get('code','')}
            for a in store.db.assignments.find(query).sort([('date',1),('user_id',1)])]

def kiosk_slot(current):
    local_day = current.astimezone(config.TZ).date()
    choices = []
    for shift in store.db.shifts.find({'active': True}):
        for offset in (-1, 0, 1):
            day = local_day + timedelta(days=offset)
            if day.weekday() not in shift.get('weekdays', range(7)):
                continue
            start, end, _ = bounds(day, shift)
            if start - timedelta(minutes=30) <= current <= end:
                choices.append((abs(current - start), start, shift['_id'], day, shift))
    if not choices:
        return local_day.isoformat(), None, 'outside_shift'
    _, start, _, day, shift = min(choices)
    status = 'on_time' if current <= start + timedelta(minutes=10) else 'late'
    return day.isoformat(), store.public(shift), status

def attendance_entries(query):
    # Personal schedules are optional. A shared punch carries its historical shift snapshot.
    schedules = list(store.db.assignments.find(query))
    punches = list(store.db.attendance.find({'$or': [
        {'assignment_id': {'$in': [a['_id'] for a in schedules]}},
        {**query, 'kiosk_status': {'$exists': True}},
    ]}))
    by_id = {p['assignment_id']: p for p in punches}
    by_slot = {(p['user_id'], p['date'], p['shift_id']): p
               for p in punches if 'kiosk_status' in p}
    used = set()
    entries = []
    for a in schedules:
        shared = by_slot.get((a['user_id'], a['date'], a['shift_id']))
        if shared:
            used.add(shared['_id'])
        punch = by_id.get(a['_id']) or shared
        if punch:
            used.add(punch['_id'])
        entries.append((store.public(a), punch))
    for p in punches:
        if 'kiosk_status' in p and p['_id'] not in used:
            entries.append(({'id': p['assignment_id'], 'user_id': p['user_id'], 'date': p['date'],
                             'shift_id': p['shift_id'], 'holiday': p.get('holiday', '')}, p))
    for a, p in entries:
        if p and 'kiosk_status' in p:
            a['shift'] = p['shift']
    return sorted(entries, key=lambda entry: (entry[0]['date'], entry[0]['user_id'], entry[0]['shift']['start']))

def report(user, month, live=False):
    start, end = month_range(month)
    closed = store.db.months.find_one({'_id': month, 'locked': True})
    if closed and not live:
        ids = visible_ids(user)
        rows = [r for r in closed['rows'] if ids is None or r['user_id'] in ids]
    else:
        rows = []
        query = {**scoped_query(user), 'date': {'$gte': start, '$lte': end}}
        users = {u['_id']: u for u in store.db.users.find({}, {'name': 1, 'code': 1})}
        approved = list(store.db.requests.find({**scoped_query(user), 'status':'approved',
                          'start_date':{'$lte':end}, 'end_date':{'$gte':start}}))
        for a, record in attendance_entries(query):
            requests = [r for r in approved if r['user_id']==a['user_id'] and r['start_date']<=a['date']<=r['end_date']]
            employee = users.get(a['user_id'], {})
            rows.append({**a, **calculate(a, record, requests, store.now()),
                         'employee_name': employee.get('name', 'Đã nghỉ việc'), 'employee_code': employee.get('code', ''),
                         'source': (record or {}).get('source',''),
                         'holiday': a.get('holiday','')})
    return {'month': month, 'locked': bool(closed), 'locked_at': (closed or {}).get('locked_at'), 'rows': rows,
            'totals': {key: sum(r.get(key,0) for r in rows) for key in
                ['planned_minutes','worked_minutes','credited_minutes','paid_leave_minutes','late_minutes','early_minutes','overtime_minutes']}}

def check_face_shift(assignment, current):
    start, end, _ = bounds(assignment['date'], assignment['shift'])
    if not start <= current < end:
        raise HTTPException(409, 'Chỉ được chấm công trong giờ của ca làm việc')
    existing = store.db.attendance.find_one({'assignment_id': assignment['_id']})
    if existing:
        checked_at = parse_dt(existing.get('check_in') or existing.get('check_out'))
        if checked_at:
            timestamp = checked_at.astimezone(config.TZ).strftime('%H:%M:%S %d/%m/%Y')
            raise HTTPException(409, f'Bạn đã chấm công rồi lúc {timestamp}')
        raise HTTPException(409, 'Ca này đã có bản ghi chấm công')

@serialized
def punch(user, assignment_id, action, source='manual'):
    if user['role'] == 'admin':
        raise HTTPException(403, 'Tài khoản quản trị không chấm công')
    assignment = get('assignments', assignment_id)
    if assignment['user_id'] != user['_id']:
        raise HTTPException(403, 'Bạn chỉ được chấm công cho chính mình')
    check_open(assignment['date'])
    start, end, _ = bounds(assignment['date'], assignment['shift'])
    current = store.now()
    if source == 'face':
        check_face_shift(assignment, current)
    elif not start-timedelta(hours=2) <= current <= end+timedelta(hours=8):
        raise HTTPException(409, 'Ngoài khung chấm công của ca (trước ca 2 giờ, sau ca 8 giờ). Hãy gửi đơn bổ sung công')
    existing = store.db.attendance.find_one({'assignment_id': assignment_id})
    if action == 'in':
        if existing:
            raise HTTPException(409, 'Ca này đã có lượt vào')
        record = {'_id': store.uid(), 'assignment_id': assignment_id, 'user_id': user['_id'],
                  'date': assignment['date'], 'check_in': current, 'check_out': None, 'source': source}
        if source == 'face':
            record['single_scan'] = True
        store.db.attendance.insert_one(record)
    else:
        if not existing or not existing.get('check_in'):
            raise HTTPException(409, 'Chưa có lượt vào. Hãy gửi đơn bổ sung công')
        result = store.db.attendance.update_one({'_id':existing['_id'], 'check_out':None},
                     {'$set':{'check_out':current, 'out_source':source}})
        if not result.modified_count:
            raise HTTPException(409, 'Ca này đã có lượt ra')
        record = store.db.attendance.find_one({'_id':existing['_id']})
    audit(user, 'attendance.'+action, assignment_id, store.public(existing), store.public(record))
    return store.public(record)
