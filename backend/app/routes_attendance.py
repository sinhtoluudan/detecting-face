from datetime import date, timedelta
from io import BytesIO
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from . import database as store, config
from .schemas import PunchInput, RequestInput, DecisionInput, ReasonInput
from .security import current_user, roles, require_visible, audit, visible_ids
from .services import get, check_open, serialized, punch, scoped_query, report, dates, month_range
from .calculations import bounds, parse_dt

router=APIRouter(tags=['Chấm công và đơn từ'])
management=roles('admin','hr','manager')
hr=roles('admin','hr')

@router.get('/attendance/today')
def today(user=Depends(current_user)):
    local=store.now().astimezone(config.TZ).date()
    candidates=list(store.db.assignments.find({'user_id':user['_id'],'date':{
        '$gte':(local-timedelta(days=1)).isoformat(),'$lte':(local+timedelta(days=1)).isoformat()}}).sort('date',1))
    result=[]
    for assignment in candidates:
        start,end,_=bounds(assignment['date'],assignment['shift'])
        if assignment['date']==local.isoformat() or start-timedelta(hours=2)<=store.now()<=end+timedelta(hours=8):
            attendance=store.db.attendance.find_one({'assignment_id':assignment['_id']})
            result.append({**store.public(assignment),'attendance':store.public(attendance)})
    profile=store.db.face_profiles.find_one({'_id':user['_id']})
    return {'date':local.isoformat(),'server_time':store.now(),'assignments':result,
            'face_enabled':config.FACE_ENABLED,'face_samples':len((profile or {}).get('vectors',[]))}

@router.post('/attendance/punch')
def manual_punch(data: PunchInput,user=Depends(current_user)):
    return punch(user,data.assignment_id,data.action)

@router.get('/requests')
def requests(month: str,user=Depends(current_user)):
    start,end=month_range(month)
    names={x['_id']:x['name'] for x in store.db.users.find({}, {'name':1})}
    query={**scoped_query(user),'start_date':{'$lte':end},'end_date':{'$gte':start}}
    return [{**store.public(r),'employee_name':names.get(r['user_id'],'')} for r in
            store.db.requests.find(query).sort('created_at',-1)]

@router.post('/requests',status_code=201)
@serialized
def create_request(data: RequestInput,user=Depends(current_user)):
    values=data.model_dump(mode='json')
    assignments=[]
    for day in dates(data.start_date,data.end_date):
        check_open(day)
        assignment=store.db.assignments.find_one({'user_id':user['_id'],'date':day.isoformat()})
        if assignment:
            assignments.append(assignment)
    if not assignments:
        raise HTTPException(409,'Chưa được phân ca trong khoảng ngày này')
    if data.type in ['correction','overtime']:
        assignment=assignments[0]
        start,end,_=bounds(assignment['date'],assignment['shift'])
        if not start-timedelta(hours=2)<=data.check_in<data.check_out<=end+timedelta(hours=8):
            raise HTTPException(422,'Khoảng giờ phải nằm trong cửa sổ ca: trước ca 2 giờ, sau ca 8 giờ')
        if data.type=='correction' and data.check_out>store.now():
            raise HTTPException(422,'Không được bổ sung công trong tương lai')
        if data.type=='overtime' and not (data.check_out<=start or data.check_in>=end):
            raise HTTPException(422,'Giờ tăng ca phải nằm hoàn toàn ngoài giờ làm chính thức')
    existing=store.db.requests.find_one({'user_id':user['_id'],'type':data.type,
        'status':{'$in':['pending'] if data.type=='correction' else ['pending','approved']},'start_date':{'$lte':str(data.end_date)},'end_date':{'$gte':str(data.start_date)}})
    if existing:
        raise HTTPException(409,'Đã có đơn cùng loại trùng ngày đang chờ hoặc đã duyệt')
    doc={'_id':store.uid(),'user_id':user['_id'],**values,'status':'pending','created_at':store.now()}
    store.db.requests.insert_one(doc)
    audit(user,'request.create',doc['_id'],after=store.public(doc))
    return store.public(doc)

@router.post('/requests/{id}/cancel')
@serialized
def cancel_request(id: str,user=Depends(current_user)):
    doc=get('requests',id)
    if doc['user_id']!=user['_id']:
        raise HTTPException(403,'Chỉ người gửi được hủy đơn')
    if doc['status']!='pending':
        raise HTTPException(409,'Chỉ được hủy đơn còn chờ duyệt')
    for day in dates(doc['start_date'],doc['end_date']):
        check_open(day)
    store.db.requests.update_one({'_id':id},{'$set':{'status':'cancelled'}})
    audit(user,'request.cancel',id,before=store.public(doc))
    return {'message':'Đã hủy đơn'}

@router.post('/requests/{id}/decision')
@serialized
def decide(id: str,data: DecisionInput,user=Depends(management)):
    doc=get('requests',id)
    require_visible(user,doc['user_id'])
    if doc['user_id']==user['_id']:
        raise HTTPException(403,'Không được tự duyệt đơn của chính mình')
    target=get('users',doc['user_id'])
    if user['role']=='manager' and target['role'] in ['admin','hr','manager']:
        raise HTTPException(403,'Đơn của quản lý cần HR hoặc Admin duyệt')
    if doc['status']!='pending':
        raise HTTPException(409,'Đơn này đã được xử lý')
    for day in dates(doc['start_date'],doc['end_date']):
        check_open(day)
    if data.status=='approved' and doc['type']=='correction':
        a=store.db.assignments.find_one({'user_id':doc['user_id'],'date':doc['start_date']})
        if not a:
            raise HTTPException(409,'Ca làm không còn tồn tại')
        old=store.db.attendance.find_one({'assignment_id':a['_id']})
        updated={'user_id':doc['user_id'],'date':doc['start_date'],
                 'check_in':parse_dt(doc['check_in']),'check_out':parse_dt(doc['check_out']),
                 'source':'correction','request_id':id}
        store.db.attendance.update_one({'assignment_id':a['_id']},
            {'$set':updated,'$setOnInsert':{'_id':store.uid()}},upsert=True)
        audit(user,'attendance.correct',a['_id'],store.public(old),updated,data.note)
    decision={'status':data.status,'reviewer_id':user['_id'],'reviewer_name':user['name'],
              'review_note':data.note,'reviewed_at':store.now()}
    store.db.requests.update_one({'_id':id},{'$set':decision})
    audit(user,'request.'+data.status,id,store.public(doc),decision,data.note)
    return store.public(get('requests',id))

@router.get('/reports')
def reports(month: str,user=Depends(current_user)):
    return report(user,month)

@router.post('/reports/{month}/close')
@serialized
def close_month(month: str,data: ReasonInput,user=Depends(hr)):
    first,last=month_range(month)
    check_open(first)
    if last>=store.now().astimezone(config.TZ).date().isoformat():
        raise HTTPException(409,'Chỉ chốt tháng đã kết thúc')
    if store.db.requests.count_documents({'status':'pending','start_date':{'$lte':last},'end_date':{'$gte':first}}):
        raise HTTPException(409,'Còn đơn chờ duyệt trong tháng, hãy xử lý trước')
    current=report(user,month,live=True)
    if not current['rows']:
        raise HTTPException(409,'Tháng này chưa có bảng công')
    if any(r['status']=='missing_out' for r in current['rows']):
        raise HTTPException(409,'Còn ca thiếu lượt ra, hãy xử lý đơn bổ sung trước')
    store.db.months.update_one({'_id':month},{'$set':{'locked':True,'rows':current['rows'],
        'locked_at':store.now(),'locked_by':user['_id'],'reason':data.reason}},upsert=True)
    audit(user,'month.close',month,after={'rows':len(current['rows'])},reason=data.reason)
    return {'message':'Đã chốt bảng công và lưu bản tổng hợp cố định'}

@router.post('/reports/{month}/reopen')
@serialized
def reopen_month(month: str,data: ReasonInput,user=Depends(hr)):
    month_range(month)
    old=get('months',month)
    if not old.get('locked'):
        raise HTTPException(409,'Tháng này đang mở')
    store.db.months.update_one({'_id':month},{'$set':{'locked':False,'reopened_at':store.now(),'reopen_reason':data.reason}})
    audit(user,'month.reopen',month,reason=data.reason)
    return {'message':'Đã mở lại bảng công'}

@router.get('/reports/export')
def export(month: str,user=Depends(current_user)):
    data=report(user,month)
    wb=Workbook(); ws=wb.active; ws.title='Bang cong'
    ws.append(['Mã NV','Họ tên','Ngày','Ca','Vào','Ra','Trạng thái','Giờ làm','Công quy đổi','Nghỉ hưởng lương (giờ)','Trễ (phút)','Sớm (phút)','Tăng ca (giờ)','Cần rà soát','Ngày lễ'])
    labels={'present':'Đủ công','late':'Đi trễ','early':'Về sớm','absent':'Vắng','leave':'Nghỉ phép',
            'scheduled':'Chưa đến ca','working':'Đang làm','missing_out':'Thiếu lượt ra'}
    def clock(v):
        return parse_dt(v).astimezone(config.TZ).strftime('%d/%m %H:%M') if v else ''
    for r in data['rows']:
        ws.append([r['employee_code'],r['employee_name'],r['date'],r['shift']['name'],clock(r['check_in']),clock(r['check_out']),
            labels[r['status']],round(r['worked_minutes']/60,2),round(r['credited_minutes']/r['planned_minutes'],2) if r['planned_minutes'] else 0,
            round(r['paid_leave_minutes']/60,2),r['late_minutes'],r['early_minutes'],round(r['overtime_minutes']/60,2),
            'Có' if r['needs_review'] else '',r.get('holiday','')])
    # Explicit string cells prevent formula injection from employee-controlled names.
    for row in ws:
        for cell in row:
            if isinstance(cell.value,str): cell.data_type='s'
    for cell in ws[1]:
        cell.fill=PatternFill('solid',fgColor='183D3D'); cell.font=Font(color='FFFFFF',bold=True)
        cell.alignment=Alignment(vertical='center')
    ws.row_dimensions[1].height=30
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width=min(32,max(14,max(len(str(c.value or '')) for c in col)+2))
    ws.freeze_panes='C2'; ws.auto_filter.ref=ws.dimensions
    buf=BytesIO(); wb.save(buf); buf.seek(0)
    return StreamingResponse(buf,media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition':f'attachment; filename="bang-cong-{month}.xlsx"'})

@router.get('/dashboard')
def dashboard(month: str,user=Depends(current_user)):
    data=report(user,month)
    today=store.now().astimezone(config.TZ).date().isoformat()
    today_rows=[r for r in data['rows'] if r['date']==today]
    ids=visible_ids(user)
    users=store.db.users.count_documents({'active':True,**({} if ids is None else {'_id':{'$in':ids}})})
    pending=store.db.requests.count_documents({**scoped_query(user),'status':'pending'})
    return {'active_employees':users,'pending_requests':pending,'scheduled_today':len(today_rows),
        'working_today':sum(r['status']=='working' for r in today_rows),
        'checked_today':sum(bool(r['check_in']) for r in today_rows),
        'late_today':sum(r['late_minutes']>0 for r in today_rows),'today_rows':today_rows,
        'totals':data['totals'],'locked':data['locked'],'rows':data['rows']}

@router.get('/audit')
def audit_log(limit: int=Query(default=100,ge=1,le=500),user=Depends(hr)):
    return [store.public(x) for x in store.db.audit.find().sort('created_at',-1).limit(limit)]
