from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from . import database as store
from .schemas import UserInput, DepartmentInput, ShiftInput, AssignmentInput, AssignmentShiftInput, HolidayInput
from .security import current_user, roles, visible_ids, require_visible, password_hash, audit
from .services import get, check_open, dates, bounds, serialized, enriched_assignments

router = APIRouter(tags=['Nhân sự và lịch làm'])
hr = roles('admin','hr','manager')
management = roles('admin','hr','manager')

@router.get('/users')
def users(user=Depends(current_user)):
    ids = visible_ids(user)
    query = {} if ids is None else {'_id':{'$in':ids}}
    return [store.public(x) for x in store.db.users.find(query, {'password_hash':0}).sort('code',1)]

def validate_user(data, actor, existing=None):
    if existing and existing['_id']==actor['_id'] and (not data.active or data.role!=actor['role']):
        raise HTTPException(409, 'Không thể tự khóa hoặc tự đổi quyền tài khoản đang sử dụng')
    if existing and existing['role']=='manager' and (data.role!='manager' or not data.active):
        if store.db.departments.count_documents({'manager_id':existing['_id']}):
            raise HTTPException(409, 'Hãy thay quản lý phòng ban trước khi khóa hoặc đổi quyền')
    if data.department_id:
        get('departments',data.department_id)
    values = data.model_dump(mode='json', exclude={'password'})
    values['username'] = data.username.lower()
    if data.password:
        values['password_hash'] = password_hash(data.password)
    return values

@router.post('/users', status_code=201)
@serialized
def create_user(data: UserInput, user=Depends(hr)):
    if not data.password:
        raise HTTPException(422,'Tài khoản mới cần mật khẩu ít nhất 10 ký tự')
    values = validate_user(data,user)
    doc = {'_id':store.uid(), **values, 'created_at':store.now()}
    store.db.users.insert_one(doc)
    audit(user,'user.create',doc['_id'],after=store.public(doc))
    return store.public(doc)

@router.put('/users/{id}')
@serialized
def update_user(id: str, data: UserInput, user=Depends(hr)):
    old = get('users',id)
    values = validate_user(data,user,old)
    store.db.users.update_one({'_id':id},{'$set':values})
    if data.password or not data.active or old['role']!=data.role:
        store.db.sessions.delete_many({'user_id':id})
    after = store.public(get('users',id))
    audit(user,'user.update',id,store.public(old),after)
    return after

@router.get('/departments')
def departments(user=Depends(current_user)):
    people = {x['_id']: x['name'] for x in store.db.users.find({}, {'name': 1})}
    return [{**store.public(x),
             'manager_name': people.get(x.get('manager_id'), ''),
             'employee_count': store.db.users.count_documents({'department_id': x['_id'], 'active': True})}
            for x in store.db.departments.find().sort('name',1)]

def department_values(data):
    if data.manager_id:
        manager = get('users',data.manager_id)
        if manager['role']!='manager' or not manager['active']:
            raise HTTPException(422,'Trưởng phòng phải là tài khoản Quản lý đang hoạt động')
    return data.model_dump()

@router.post('/departments',status_code=201)
@serialized
def create_department(data: DepartmentInput,user=Depends(hr)):
    doc = {'_id':store.uid(),**department_values(data)}
    store.db.departments.insert_one(doc)
    audit(user,'department.create',doc['_id'],after=store.public(doc))
    return store.public(doc)

@router.put('/departments/{id}')
@serialized
def update_department(id: str,data: DepartmentInput,user=Depends(hr)):
    old=get('departments',id)
    store.db.departments.update_one({'_id':id},{'$set':department_values(data)})
    audit(user,'department.update',id,store.public(old),data.model_dump())
    return store.public(get('departments',id))

@router.delete('/departments/{id}')
@serialized
def delete_department(id: str,user=Depends(hr)):
    old=get('departments',id)
    if store.db.users.count_documents({'department_id':id}):
        raise HTTPException(409,'Phòng ban còn nhân viên, hãy chuyển họ sang phòng khác trước')
    store.db.departments.delete_one({'_id':id})
    audit(user,'department.delete',id,before=store.public(old))
    return {'message':'Đã xóa phòng ban'}

@router.get('/shifts')
def shifts(user=Depends(current_user)):
    return [store.public(x) for x in store.db.shifts.find().sort('name',1)]

@router.post('/shifts',status_code=201)
@serialized
def create_shift(data: ShiftInput,user=Depends(hr)):
    doc={'_id':store.uid(),**data.model_dump(mode='json')}
    store.db.shifts.insert_one(doc)
    audit(user,'shift.create',doc['_id'],after=store.public(doc))
    return store.public(doc)

@router.put('/shifts/{id}')
@serialized
def update_shift(id: str,data: ShiftInput,user=Depends(hr)):
    old=get('shifts',id)
    store.db.shifts.update_one({'_id':id},{'$set':data.model_dump(mode='json')})
    audit(user,'shift.update',id,store.public(old),data.model_dump(mode='json'))
    return store.public(get('shifts',id))

@router.get('/assignments')
def assignments(month: str,user=Depends(current_user)):
    return enriched_assignments(user,month)

@router.post('/assignments',status_code=201)
@serialized
def assign(data: AssignmentInput,user=Depends(management)):
    shift=get('shifts',data.shift_id)
    if not shift['active']:
        raise HTTPException(409,'Ca làm đã ngưng sử dụng')
    days=[d for d in dates(data.start_date,data.end_date) if d.weekday() in data.weekdays]
    if not days:
        raise HTTPException(422,'Không có ngày nào khớp thứ đã chọn')
    planned=[]
    for employee in set(data.user_ids):
        require_visible(user,employee)
        target=get('users',employee)
        if not target['active']:
            raise HTTPException(409,'Không thể phân ca cho nhân viên đã nghỉ')
        for day in days:
            check_open(day)
            if day.isoformat()<target['joined_date']:
                raise HTTPException(409,'Không thể phân ca trước ngày vào làm')
            if store.db.assignments.find_one({'user_id':employee,'date':day.isoformat()}):
                raise HTTPException(409,f'{target["name"]} đã có ca ngày {day}. Hủy ca cũ trước khi đổi')
            start,end,_=bounds(day,shift)
            neighbors=store.db.assignments.find({'user_id':employee,'date':{
                '$gte':(day-timedelta(days=1)).isoformat(),'$lte':(day+timedelta(days=1)).isoformat()}})
            for other in neighbors:
                os,oe,_=bounds(other['date'],other['shift'])
                if start<oe and end>os:
                    raise HTTPException(409,'Ca làm bị trùng giờ với ca ngày liền kề')
            holiday=store.db.holidays.find_one({'_id':day.isoformat()})
            planned.append({'_id':store.uid(),'user_id':employee,'date':day.isoformat(),
                'shift_id':shift['_id'],'shift':store.public(shift),'holiday':(holiday or {}).get('name','')})
    store.db.assignments.insert_many(planned)
    audit(user,'assignment.create','batch',after={'count':len(planned),'user_ids':data.user_ids,'start':str(data.start_date),'end':str(data.end_date)})
    return {'message':f'Đã phân {len(planned)} ca','count':len(planned)}

@router.delete('/assignments/{id}')
@serialized
def delete_assignment(id: str,user=Depends(management)):
    doc=get('assignments',id)
    require_visible(user,doc['user_id'])
    check_open(doc['date'])
    if store.db.attendance.count_documents({'assignment_id':id}):
        raise HTTPException(409,'Ca đã có chấm công. Hãy dùng đơn bổ sung để điều chỉnh')
    if store.db.requests.count_documents({'user_id':doc['user_id'],'start_date':{'$lte':doc['date']},'end_date':{'$gte':doc['date']},'status':{'$in':['pending','approved']}}):
        raise HTTPException(409,'Ca đang có đơn liên quan. Hủy/xử lý đơn trước khi đổi ca')
    store.db.assignments.delete_one({'_id':id})
    audit(user,'assignment.delete',id,before=store.public(doc))
    return {'message':'Đã hủy ca'}

@router.put('/assignments/{id}')
@serialized
def update_assignment(id: str,data: AssignmentShiftInput,user=Depends(management)):
    doc=get('assignments',id)
    require_visible(user,doc['user_id'])
    check_open(doc['date'])
    shift=get('shifts',data.shift_id)
    if not shift['active']:
        raise HTTPException(409,'Ca làm đã ngưng sử dụng')
    if data.shift_id==doc['shift_id']:
        return store.public(doc)
    if store.db.attendance.count_documents({'assignment_id':id}):
        raise HTTPException(409,'Ca đã có chấm công, không thể đổi lịch')
    if store.db.requests.count_documents({'user_id':doc['user_id'],'start_date':{'$lte':doc['date']},
        'end_date':{'$gte':doc['date']},'status':{'$in':['pending','approved']}}):
        raise HTTPException(409,'Ca đang có đơn liên quan. Hủy hoặc xử lý đơn trước khi đổi ca')
    employee=get('users',doc['user_id'])
    if doc['date']<employee['joined_date']:
        raise HTTPException(409,'Không thể phân ca trước ngày vào làm')
    start,end,_=bounds(doc['date'],shift)
    neighbors=store.db.assignments.find({'user_id':doc['user_id'],'_id':{'$ne':id},
        'date':{'$gte':(date.fromisoformat(doc['date'])-timedelta(days=1)).isoformat(),
                '$lte':(date.fromisoformat(doc['date'])+timedelta(days=1)).isoformat()}})
    for other in neighbors:
        other_start,other_end,_=bounds(other['date'],other['shift'])
        if start<other_end and end>other_start:
            raise HTTPException(409,'Ca làm bị trùng giờ với ca ngày liền kề')
    before=store.public(doc)
    store.db.assignments.update_one({'_id':id},{'$set':{'shift_id':shift['_id'],'shift':store.public(shift)}})
    updated=store.public(get('assignments',id))
    audit(user,'assignment.update',id,before=before,after=updated)
    return updated

@router.get('/holidays')
def holidays(user=Depends(current_user)):
    return [store.public(x) for x in store.db.holidays.find().sort('_id',1)]

@router.post('/holidays')
@serialized
def set_holiday(data: HolidayInput,user=Depends(hr)):
    day=data.date.isoformat()
    check_open(day)
    old=store.db.holidays.find_one({'_id':day})
    store.db.holidays.update_one({'_id':day},{'$set':{'name':data.name}},upsert=True)
    store.db.assignments.update_many({'date':day},{'$set':{'holiday':data.name}})
    audit(user,'holiday.set',day,store.public(old),data.model_dump(mode='json'))
    return {'message':'Đã lưu ngày nghỉ lễ'}

@router.delete('/holidays/{day}')
@serialized
def delete_holiday(day: str,user=Depends(hr)):
    check_open(day)
    old=get('holidays',day)
    store.db.holidays.delete_one({'_id':day})
    store.db.assignments.update_many({'date':day},{'$set':{'holiday':''}})
    audit(user,'holiday.delete',day,before=store.public(old))
    return {'message':'Đã xóa ngày lễ'}
