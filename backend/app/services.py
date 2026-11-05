import calendar
from datetime import date, timedelta
from functools import wraps
from threading import RLock
from fastapi import HTTPException
from . import database as store
from .calculations import bounds, calculate
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

def report(user, month, live=False):
    start, end = month_range(month)
    closed = store.db.months.find_one({'_id': month, 'locked': True})
    if closed and not live:
        ids = visible_ids(user)
        rows = [r for r in closed['rows'] if ids is None or r['user_id'] in ids]
    else:
        rows = []
        assignments = enriched_assignments(user, month)
        ids = [a['id'] for a in assignments]
        punches = {x['assignment_id']: x for x in store.db.attendance.find({'assignment_id': {'$in': ids}})}
        approved = list(store.db.requests.find({**scoped_query(user), 'status':'approved',
                          'start_date':{'$lte':end}, 'end_date':{'$gte':start}}))
        for a in assignments:
            requests = [r for r in approved if r['user_id']==a['user_id'] and r['start_date']<=a['date']<=r['end_date']]
            rows.append({**a, **calculate(a, punches.get(a['id']), requests, store.now()),
                         'source': punches.get(a['id'],{}).get('source',''),
                         'holiday': a.get('holiday','')})
    return {'month': month, 'locked': bool(closed), 'locked_at': (closed or {}).get('locked_at'), 'rows': rows,
            'totals': {key: sum(r.get(key,0) for r in rows) for key in
                ['planned_minutes','worked_minutes','credited_minutes','paid_leave_minutes','late_minutes','early_minutes','overtime_minutes']}}

@serialized
def punch(user, assignment_id, action, source='manual'):
    assignment = get('assignments', assignment_id)
    if assignment['user_id'] != user['_id']:
        raise HTTPException(403, 'Bạn chỉ được chấm công cho chính mình')
    check_open(assignment['date'])
    start, end, _ = bounds(assignment['date'], assignment['shift'])
    current = store.now()
    if not start-timedelta(hours=2) <= current <= end+timedelta(hours=8):
        raise HTTPException(409, 'Ngoài khung chấm công của ca (trước ca 2 giờ, sau ca 8 giờ). Hãy gửi đơn bổ sung công')
    existing = store.db.attendance.find_one({'assignment_id': assignment_id})
    if action == 'in':
        if existing:
            raise HTTPException(409, 'Ca này đã có lượt vào')
        record = {'_id': store.uid(), 'assignment_id': assignment_id, 'user_id': user['_id'],
                  'date': assignment['date'], 'check_in': current, 'check_out': None, 'source': source}
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
