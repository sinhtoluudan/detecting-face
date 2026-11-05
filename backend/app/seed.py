from datetime import date, timedelta, datetime
from . import database as store, config
from .security import password_hash
from .calculations import bounds


def seed():
    if not config.SEED_DEMO:
        return
    if len(config.DEMO_PASSWORD)<10:
        raise RuntimeError('SEED_DEMO=true cần DEMO_PASSWORD ít nhất 10 ký tự trong .env')
    if store.db.users.count_documents({}):
        return
    today=store.now().astimezone(config.TZ).date()
    joined=(today.replace(day=1)-timedelta(days=40)).isoformat()
    departments=[{'_id':'dept-tech','name':'Công nghệ','description':'Phát triển sản phẩm & vận hành','manager_id':'user-manager'},
                 {'_id':'dept-hr','name':'Nhân sự','description':'Nhân sự & hành chính','manager_id':None},
                 {'_id':'dept-sales','name':'Kinh doanh','description':'Khách hàng & đối tác','manager_id':None}]
    store.db.departments.insert_many(departments)
    people=[('admin','Nguyễn Minh Anh','admin','dept-hr','Quản trị hệ thống'),
            ('hr','Trần Thu Hà','hr','dept-hr','Chuyên viên nhân sự'),
            ('manager','Lê Hoàng Nam','manager','dept-tech','Trưởng phòng công nghệ'),
            ('employee','Nguyễn Đăng Khang','employee','dept-tech','Lập trình viên'),
            ('linh','Phạm Ngọc Linh','employee','dept-tech','Thiết kế sản phẩm'),
            ('tuan','Võ Anh Tuấn','employee','dept-sales','Chuyên viên kinh doanh')]
    users=[]
    for i,(username,name,role,department,title) in enumerate(people):
        users.append({'_id':'user-'+username,'code':f'NV{i+1:03}','name':name,'username':username,
            'role':role,'department_id':department,'title':title,'phone':'','joined_date':joined,'active':True,
            'password_hash':password_hash(config.DEMO_PASSWORD),'created_at':store.now()})
    store.db.users.insert_many(users)
    shifts=[{'_id':'shift-office','name':'Hành chính','start':'08:00:00','end':'17:00:00',
             'break_start':'12:00:00','break_end':'13:00:00','grace_minutes':5,'color':'#087f8c','active':True},
            {'_id':'shift-night','name':'Ca đêm','start':'22:00:00','end':'06:00:00',
             'break_start':'02:00:00','break_end':'02:30:00','grace_minutes':5,'color':'#7c5cba','active':True}]
    store.db.shifts.insert_many(shifts)
    first=(today.replace(day=1)-timedelta(days=1)).replace(day=1)
    day=first
    while day<=today+timedelta(days=14):
        if day.weekday()<5 or day==today:
            for i,u in enumerate(users):
                a={'_id':store.uid(),'user_id':u['_id'],'date':day.isoformat(),'shift_id':'shift-office','shift':store.public(shifts[0]),'holiday':''}
                store.db.assignments.insert_one(a)
                if day<today and (day.day+i)%13!=0:
                    start,end,_=bounds(day,shifts[0]); late=17 if (day.day+i)%7==0 else 0
                    store.db.attendance.insert_one({'_id':store.uid(),'assignment_id':a['_id'],'user_id':u['_id'],
                        'date':day.isoformat(),'check_in':start+timedelta(minutes=late), 'check_out':end,'source':'demo'})
        day+=timedelta(days=1)
    nextday=today+timedelta(days=1)
    while nextday.weekday()>4:
        nextday+=timedelta(days=1)
    store.db.requests.insert_one({'_id':store.uid(),'user_id':'user-employee','type':'leave','start_date':str(nextday),
        'end_date':str(nextday),'reason':'Xin nghỉ một ngày để giải quyết việc gia đình.','paid':True,'leave_hours':8,
        'check_in':None,'check_out':None,'status':'pending','created_at':store.now()})
