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


def test_employee_scope_and_admin_guards(client,login):
    login('employee')
    assert len(client.get('/api/users').json())==1
    assert client.get('/api/audit').status_code==403
    assert client.post('/api/departments',json={'name':'Illegal'}).status_code==403
    rows=client.get('/api/reports',params={'month':today()[:7]}).json()['rows']
    assert all(x['user_id']=='user-employee' for x in rows)
    other=own_assignment('hr')
    assert client.post('/api/attendance/punch',json={'assignment_id':other['_id'],'action':'in'}).status_code==403


def test_manager_scope(client,login):
    login('manager')
    ids=[x['id'] for x in client.get('/api/users').json()]
    assert 'user-employee' in ids and 'user-tuan' not in ids
    assert client.post('/api/assignments',json={'user_ids':['user-tuan'],'shift_id':'shift-office','start_date':today(),'end_date':today(),'weekdays':list(range(7))}).status_code==403


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


def test_hr_cannot_escalate(client,login):
    login('hr')
    b={'code':'NV100','name':'Admin clone','username':'clone','password':'NewPassword@123','role':'admin','joined_date':today()}
    assert client.post('/api/users',json=b).status_code==403


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


def test_punch_duplicate_checkout(client,login,monkeypatch):
    login('employee');a=own_assignment();start,end=at_work(monkeypatch,a)
    payload={'assignment_id':a['_id'],'action':'out'}
    assert client.post('/api/attendance/punch',json=payload).status_code==409
    payload['action']='in';post(client,'/attendance/punch',payload)
    assert client.post('/api/attendance/punch',json=payload).status_code==409
    monkeypatch.setattr(store,'now',lambda:end)
    # Test login sessions may expire during overnight tests; this is a daytime shift.
    payload['action']='out';post(client,'/attendance/punch',payload)
    assert client.post('/api/attendance/punch',json=payload).status_code==409
    r=client.get('/api/reports',params={'month':today()[:7]}).json()
    row=next(r for r in r['rows'] if r['date']==today())
    assert row['worked_minutes']==470 and row['late_minutes']==10


def test_request_review_no_self(client,login):
    login('employee');r=post(client,'/requests',request_payload())
    assert client.post('/api/requests/'+r['id']+'/decision',json={'status':'approved','note':'Đồng ý'}).status_code==403
    login('manager');post(client,'/requests/'+r['id']+'/decision',{'status':'approved','note':'Đồng ý nghỉ phép'})
    assert client.post('/api/requests/'+r['id']+'/decision',json={'status':'approved','note':'Duyệt lại'}).status_code==409
    login('employee')
    report=client.get('/api/reports',params={'month':today()[:7]}).json()
    assert next(x for x in report['rows'] if x['date']==today())['paid_leave_minutes']==480


def test_own_manager_request_requires_other_reviewer(client,login):
    login('manager');r=post(client,'/requests',request_payload())
    assert client.post('/api/requests/'+r['id']+'/decision',json={'status':'approved','note':'Đồng ý'}).status_code==403


def test_cancel_pending(client,login):
    login('employee');r=post(client,'/requests',request_payload())
    post(client,'/requests/'+r['id']+'/cancel',{})
    assert client.post('/api/requests/'+r['id']+'/cancel').status_code==409


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


def test_request_outside_manager_department_denied(client,login):
    login('tuan');r=post(client,'/requests',request_payload())
    login('manager')
    assert client.post('/api/requests/'+r['id']+'/decision',json={'status':'approved','note':'Không được duyệt'}).status_code==403
