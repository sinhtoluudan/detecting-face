from datetime import datetime,timedelta,timezone
from io import BytesIO
import pytest
from openpyxl import load_workbook
from app import database as store, config
from app.calculations import bounds, calculate


def post(client,url,data):
    r=client.post('/api'+url,json=data)
    assert r.status_code<300,r.text
    return r.json()

def today():
    return store.now().astimezone(config.TZ).date().isoformat()

def shift_payload(**kw):
    return {'name':'Test shift','start':'08:00','end':'17:00','break_start':'12:00','break_end':'13:00',
            'grace_minutes':5,'color':'#123456','active':True,**kw}

def request_payload(**kw):
    return {'type':'leave','start_date':today(),'end_date':today(),'reason':'Lý do kiểm thử hợp lệ','paid':True,'leave_hours':8,**kw}

def own_assignment(username='employee',day=None):
    return store.db.assignments.find_one({'user_id':'user-'+username,'date':day or today()})

def at_work(monkeypatch,assignment):
    start,end,_=bounds(assignment['date'],assignment['shift'])
    monkeypatch.setattr(store,'now',lambda:start+timedelta(minutes=10))
    return start,end


def test_login_cookie_and_csrf(client,login):
    response=client.post('/api/auth/login',json={'username':'employee','password':'wrong'})
    assert response.status_code==401
    login('employee')
    assert 'HttpOnly' in client.post('/api/auth/login',json={'username':'employee','password':'TestPassword@123'}).headers['set-cookie']
    client.headers.pop('X-CSRF-Token')
    assert client.post('/api/auth/logout').status_code==403
    assert 'password_hash' not in client.get('/api/auth/me').text


def test_employee_read_scope_and_write_guards(client,login):
    login('employee')
    assert len(client.get('/api/users').json())==1
    assert client.get('/api/audit').status_code==403
    departments=client.get('/api/departments')
    assert departments.status_code==200 and departments.json()
    assert departments.json()[0]['employee_count']>0
    assert client.get('/api/shifts').status_code==200
    assert client.get('/api/holidays').status_code==200
    assert client.post('/api/departments',json={'name':'Illegal'}).status_code==403
    assert client.put('/api/departments/dept-tech',json={'name':'Illegal'}).status_code==403
    assert client.delete('/api/departments/dept-sales').status_code==403
    assert client.put('/api/shifts/shift-office',json=shift_payload()).status_code==403
    rows=client.get('/api/reports',params={'month':today()[:7]}).json()['rows']
    assert all(x['user_id']=='user-employee' for x in rows)
    schedule=client.get('/api/assignments',params={'month':today()[:7]}).json()
    assert schedule and all(x['user_id']=='user-employee' for x in schedule)
    assert client.delete('/api/assignments/'+schedule[0]['id']).status_code==403
    requests=client.get('/api/requests',params={'month':today()[:7]}).json()
    assert all(x['user_id']=='user-employee' for x in requests)
    dashboard=client.get('/api/dashboard',params={'month':today()[:7]}).json()
    assert dashboard['active_employees']==1
    assert all(x['user_id']=='user-employee' for x in dashboard['rows'])
    assert client.post('/api/shifts',json=shift_payload()).status_code==403
    assert client.post('/api/assignments',json={'user_ids':['user-tuan'],'shift_id':'shift-office','start_date':today(),'end_date':today(),'weekdays':list(range(7))}).status_code==403
    other=own_assignment('hr')
    assert client.post('/api/attendance/punch',json={'assignment_id':other['_id'],'action':'in'}).status_code==403


def test_manager_has_full_management_scope(client,login):
    login('manager')
    ids=[x['id'] for x in client.get('/api/users').json()]
    assert 'user-employee' in ids and 'user-tuan' in ids
    account=client.post('/api/users',json={'code':'NV101','name':'New administrator','username':'new-admin',
        'password':'NewPassword@123','role':'admin','joined_date':today()})
    assert account.status_code==201,account.text
    day=(store.now().astimezone(config.TZ).date()+timedelta(days=20)).isoformat()
    response=client.post('/api/assignments',json={'user_ids':['user-tuan'],'shift_id':'shift-office','start_date':day,'end_date':day,'weekdays':list(range(7))})
    assert response.status_code==201,response.text
    assert client.post('/api/departments',json={'name':'Manager department'}).status_code==201
    assert client.get('/api/audit').status_code==200


def test_create_edit_lock_user(client,login):
    login()
    department=post(client,'/departments',{'name':'Phòng kiểm thử','description':'QA'})
    body={'code':'NV099','name':'Test Person','username':'tester','password':'NewPassword@123','role':'employee',
          'department_id':department['id'],'joined_date':today(),'active':True}
    u=post(client,'/users',body)
    assert 'password_hash' not in u and 'password' not in u
    assert client.delete('/api/departments/'+department['id']).status_code==409
    body['active']=False;body.pop('password')
    assert client.put('/api/users/'+u['id'],json=body).status_code==200
    assert client.post('/api/auth/login',json={'username':'tester','password':'NewPassword@123'}).status_code==401


def test_hr_and_manager_can_manage_all_account_roles(client,login):
    login('hr')
    b={'code':'NV100','name':'Admin clone','username':'clone','password':'NewPassword@123','role':'admin','joined_date':today()}
    assert client.post('/api/users',json=b).status_code==201


def test_shift_validation_and_snapshot(client,login):
    login()
    assert client.post('/api/shifts',json=shift_payload(end='08:00')).status_code==422
    assert client.post('/api/shifts',json=shift_payload(break_end='20:00')).status_code==422
    old=own_assignment()['shift']['start']
    assert client.put('/api/shifts/shift-office',json=shift_payload(name='Hành chính',start='09:00')).status_code==200
    assert own_assignment()['shift']['start']==old


def test_duplicate_schedule_no_partial_insert(client,login):
    login()
    before=store.db.assignments.count_documents({})
    assert client.post('/api/assignments',json={'user_ids':['user-employee','user-linh'],'shift_id':'shift-office','start_date':today(),'end_date':today(),'weekdays':list(range(7))}).status_code==409
    assert store.db.assignments.count_documents({})==before


def test_assign_and_delete(client,login):
    login()
    day=(store.now().astimezone(config.TZ).date()+timedelta(days=20)).isoformat()
    post(client,'/assignments',{'user_ids':['user-employee'],'shift_id':'shift-night','start_date':day,'end_date':day,'weekdays':list(range(7))})
    a=own_assignment(day=day)
    assert a['shift']['end']=='06:00:00'
    assert client.delete('/api/assignments/'+a['_id']).status_code==200


def test_manual_punch_cannot_bypass_face_verification(client,login,monkeypatch):
    login('employee');a=own_assignment();start,end=at_work(monkeypatch,a)
    for action in ('in','out'):
        response=client.post('/api/attendance/punch',json={'assignment_id':a['_id'],'action':action})
        assert response.status_code==403
    assert store.db.attendance.find_one({'assignment_id':a['_id']}) is None


def test_request_review_no_self(client,login):
    login('employee');r=post(client,'/requests',request_payload())
    assert client.post('/api/requests/'+r['id']+'/decision',json={'status':'approved','note':'Đồng ý'}).status_code==403
    login('manager');post(client,'/requests/'+r['id']+'/decision',{'status':'approved','note':'Đồng ý nghỉ phép'})
    assert client.post('/api/requests/'+r['id']+'/decision',json={'status':'approved','note':'Duyệt lại'}).status_code==409
    login('employee')
    report=client.get('/api/reports',params={'month':today()[:7]}).json()
    assert next(x for x in report['rows'] if x['date']==today())['paid_leave_minutes']==480


def test_employee_cannot_review_another_employee_request(client,login):
    login('tuan')
    request=post(client,'/requests',request_payload())
    login('employee')
    assert client.post('/api/requests/'+request['id']+'/decision',
        json={'status':'approved','note':'Test approval'}).status_code==403


def test_own_manager_request_requires_other_reviewer(client,login):
    login('manager');r=post(client,'/requests',request_payload())
    assert client.post('/api/requests/'+r['id']+'/decision',json={'status':'approved','note':'Đồng ý'}).status_code==403


def test_cancel_pending(client,login):
    login('employee');r=post(client,'/requests',request_payload())
    assert client.post('/api/requests/'+r['id']+'/cancel').status_code==403
    assert store.db.requests.find_one({'_id':r['id']})['status']=='pending'
    login('manager');own=post(client,'/requests',request_payload())
    post(client,'/requests/'+own['id']+'/cancel',{})
    assert client.post('/api/requests/'+own['id']+'/cancel').status_code==409


def test_correction_with_audit(client,login):
    a=store.db.assignments.find_one({'user_id':'user-employee','date':{'$lt':today()}})
    start,end,_=bounds(a['date'],a['shift'])
    login('employee')
    r=post(client,'/requests',request_payload(type='correction',start_date=a['date'],end_date=a['date'],check_in=start.isoformat(),check_out=end.isoformat()))
    login('hr');post(client,'/requests/'+r['id']+'/decision',{'status':'approved','note':'Đã xác minh quên chấm công'})
    punch=store.db.attendance.find_one({'assignment_id':a['_id']})
    assert punch['source']=='correction'
    assert store.db.audit.count_documents({'action':'attendance.correct'})==1


def test_close_reopen_and_snapshot(client,login):
    login('hr')
    month=(store.now().astimezone(config.TZ).date().replace(day=1)-timedelta(days=1)).isoformat()[:7]
    post(client,'/reports/'+month+'/close',{'reason':'Đã kiểm tra bảng công tháng'})
    r=client.get('/api/reports',params={'month':month}).json();assert r['locked']
    a=store.db.assignments.find_one({'date':{'$regex':'^'+month}})
    assert client.delete('/api/assignments/'+a['_id']).status_code==409
    login('employee')
    assert client.post('/api/requests',json=request_payload(start_date=month+'-02',end_date=month+'-02')).status_code==409
    login('hr');post(client,'/reports/'+month+'/reopen',{'reason':'Cần kiểm tra lại dữ liệu công'})
    assert not client.get('/api/reports',params={'month':month}).json()['locked']


def test_cannot_close_current_month(client,login):
    login('hr')
    assert client.post('/api/reports/'+today()[:7]+'/close',json={'reason':'Kiểm tra chốt công'}).status_code==409


def test_export_is_real_xlsx_and_formula_safe(client,login):
    login()
    store.db.users.update_one({'_id':'user-employee'},{'$set':{'name':'=1+1'}})
    r=client.get('/api/reports/export',params={'month':today()[:7]})
    assert r.status_code==200 and r.content[:2]==b'PK'
    ws=load_workbook(BytesIO(r.content)).active
    matches=[cell for row in ws for cell in row if cell.value=='=1+1']
    assert matches and all(cell.data_type=='s' for cell in matches)


def test_untrusted_origin_and_password_change(client,login):
    login('employee')
    assert client.post('/api/auth/logout',headers={'Origin':'https://evil.example'}).status_code==403
    post(client,'/auth/password',{'current_password':'TestPassword@123','new_password':'AnotherPassword@123'})
    assert client.get('/api/auth/me').status_code==401
    assert client.post('/api/auth/login',json={'username':'employee','password':'AnotherPassword@123'}).status_code==200


def test_calculation_night_break_overlap_and_approved_ot():
    a={'date':'2026-10-01','shift':{'start':'22:00','end':'06:00','break_start':'02:00','break_end':'02:30','grace_minutes':5}}
    start,end,_=bounds(a['date'],a['shift'])
    p={'check_in':start,'check_out':end+timedelta(hours=2)}
    r=calculate(a,p,[],end+timedelta(hours=3))
    assert r['worked_minutes']==450 and r['overtime_minutes']==0
    approval={'type':'overtime','check_in':end,'check_out':end+timedelta(hours=1)}
    assert calculate(a,p,[approval],end+timedelta(hours=3))['overtime_minutes']==60
    p={'check_in':start,'check_out':start+timedelta(hours=3)}
    assert calculate(a,p,[],end)['worked_minutes']==180


def test_five_minute_lateness_and_absence_status():
    a={'date':'2026-10-01','shift':{'start':'12:00','end':'20:00','grace_minutes':5}}
    start,end,_=bounds(a['date'],a['shift'])
    late=calculate(a,{'check_in':start+timedelta(minutes=5),'check_out':end},[],end)
    assert late['late_minutes']==5 and late['status']=='late'
    absent=calculate(a,None,[],end)
    assert absent['status']=='absent'
    scheduled=calculate(a,None,[],end-timedelta(seconds=1))
    assert scheduled['status']=='scheduled'


def test_edit_assignment_shift_and_reject_attended_shift(client,login):
    login()
    a=own_assignment()
    store.db.attendance.insert_one({'_id':'test-attendance','assignment_id':a['_id']})
    assert client.put('/api/assignments/'+a['_id'],json={'shift_id':'shift-night'}).status_code==409
    day=(store.now().astimezone(config.TZ).date()+timedelta(days=20)).isoformat()
    post(client,'/assignments',{'user_ids':['user-employee'],'shift_id':'shift-office','start_date':day,
        'end_date':day,'weekdays':list(range(7))})
    scheduled=own_assignment(day=day)
    result=client.put('/api/assignments/'+scheduled['_id'],json={'shift_id':'shift-night'})
    assert result.status_code==200,result.text
    assert result.json()['shift']['name']=='Ca đêm'


def test_fractional_leave_does_not_double_count_work():
    a={'date':'2026-10-01','shift':{'start':'08:00','end':'17:00','break_start':'12:00','break_end':'13:00','grace_minutes':5}}
    start,end,_=bounds(a['date'],a['shift'])
    r=calculate(a,{'check_in':start,'check_out':end},[{'type':'leave','paid':True,'leave_hours':8}],end)
    assert r['credited_minutes']==480 and r['paid_leave_minutes']==0


def test_overnight_conflict_with_next_day(client,login):
    login()
    day=store.now().astimezone(config.TZ).date()+timedelta(days=21)
    post(client,'/assignments',{'user_ids':['user-employee'],'shift_id':'shift-night','start_date':str(day),'end_date':str(day),'weekdays':list(range(7))})
    early=post(client,'/shifts',shift_payload(name='Sáng sớm',start='05:00',end='12:00',break_start=None,break_end=None))
    nextday=str(day+timedelta(days=1))
    assert client.post('/api/assignments',json={'user_ids':['user-employee'],'shift_id':early['id'],'start_date':nextday,'end_date':nextday,'weekdays':list(range(7))}).status_code==409


def test_locking_employee_revokes_existing_session(client,login):
    login('employee')
    cookie=client.cookies.get('facecam_session')
    login('admin')
    old=store.public(store.db.users.find_one({'_id':'user-employee'}))
    allowed={'code','name','username','role','department_id','title','phone','joined_date','active'}
    body={k:v for k,v in old.items() if k in allowed};body['active']=False
    assert client.put('/api/users/user-employee',json=body).status_code==200
    client.cookies.clear();client.cookies.set('facecam_session',cookie)
    assert client.get('/api/auth/me').status_code==401


def test_month_close_refuses_pending_requests_and_missing_out(client,login):
    login('admin')
    a=store.db.assignments.find_one({'date':{'$lt':today()[:7]+'-01'}})
    month=a['date'][:7]
    store.db.requests.insert_one({'_id':'pending-old','user_id':a['user_id'],'type':'leave','start_date':a['date'],'end_date':a['date'],'status':'pending'})
    assert client.post('/api/reports/'+month+'/close',json={'reason':'Kiểm tra dữ liệu'}).status_code==409
    store.db.requests.delete_one({'_id':'pending-old'})
    start,_,_=bounds(a['date'],a['shift'])
    store.db.attendance.update_one({'assignment_id':a['_id']},{'$set':{'check_in':start,'check_out':None}},upsert=True)
    assert client.post('/api/reports/'+month+'/close',json={'reason':'Kiểm tra dữ liệu'}).status_code==409


def test_login_rate_limit(client):
    for _ in range(10):
        assert client.post('/api/auth/login',json={'username':'missing','password':'bad'}).status_code==401
    assert client.post('/api/auth/login',json={'username':'missing','password':'bad'}).status_code==429


def test_manager_can_review_requests_outside_own_department(client,login):
    login('tuan');r=post(client,'/requests',request_payload())
    login('manager')
    assert client.post('/api/requests/'+r['id']+'/decision',json={'status':'approved','note':'Đã kiểm tra đơn'}).status_code==200
