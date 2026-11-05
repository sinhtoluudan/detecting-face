from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from . import database as store, config
from .schemas import FaceEnroll, FacePunch, ReasonInput
from .security import current_user, roles, audit, throttle, visible_ids
from .services import get, serialized, punch
from .face_service import extract, normalize, match, gallery

router=APIRouter(prefix='/faces',tags=['Khuôn mặt — kế thừa nhánh khang'])
hr=roles('admin','hr')

@router.get('/profiles')
def profiles(user=Depends(current_user)):
    ids=visible_ids(user)
    query={} if ids is None else {'_id':{'$in':ids}}
    profiles={x['_id']:x for x in store.db.face_profiles.find(query)}
    return {'enabled':config.FACE_ENABLED,'threshold':config.FACE_THRESHOLD,'minimum_samples':5,
        'items':[{'user_id':x['_id'],'name':x['name'],'code':x['code'],
          'samples':len(profiles.get(x['_id'],{}).get('vectors',[])),
          'updated_at':profiles.get(x['_id'],{}).get('updated_at')}
         for x in store.db.users.find({**query,'active':True})]}

@router.post('/{user_id}/enroll')
@serialized
def enroll(user_id: str,data: FaceEnroll,user=Depends(hr)):
    target=get('users',user_id)
    if not target['active']:
        raise HTTPException(409,'Nhân viên đã ngừng hoạt động')
    if not data.consent:
        raise HTTPException(422,'Cần sự đồng ý của nhân viên trước khi lưu mẫu')
    throttle('enroll:'+user['_id'],120,60)
    vector,regions,_=extract(data.image)
    profile=store.db.face_profiles.find_one({'_id':user_id}) or {'vectors':[]}
    if len(profile['vectors'])>=60:
        raise HTTPException(409,'Đã đủ 60 mẫu. Xóa và đăng ký lại nếu cần')
    if any(float(normalize(v)@vector)>0.9995 for v in profile['vectors']):
        raise HTTPException(409,'Mẫu gần như trùng. Hãy đổi góc nhẹ rồi thử lại')
    # Keep same buffalo_l 512-D embeddings and region descriptors as desktop.
    store.db.face_profiles.update_one({'_id':user_id},{'$push':{'vectors':vector.tolist(),
        'regions':{k:v.tolist() for k,v in regions.items()}},'$set':{'model':'buffalo_l','updated_at':store.now(),
        'consent_at':store.now(),'enrolled_by':user['_id']}},upsert=True)
    audit(user,'face.enroll',user_id,after={'samples':len(profile['vectors'])+1})
    return {'samples':len(profile['vectors'])+1,'message':'Đã lưu mẫu khuôn mặt'}

@router.post('/{user_id}/delete')
@serialized
def delete_face(user_id: str,data: ReasonInput,user=Depends(hr)):
    get('users',user_id)
    store.db.face_profiles.delete_one({'_id':user_id})
    store.db.face_attempts.delete_many({'user_id':user_id})
    audit(user,'face.delete',user_id,reason=data.reason)
    return {'message':'Đã xóa mẫu khuôn mặt đang lưu'}

@router.post('/punch')
@serialized
def face_punch(data: FacePunch,user=Depends(current_user)):
    throttle('face:'+user['_id'],60,60)
    assignment=get('assignments',data.assignment_id)
    if assignment['user_id']!=user['_id']:
        raise HTTPException(403,'Không được chấm công cho người khác')
    key=user['_id']+':'+data.attempt_id
    state=store.db.face_attempts.find_one({'_id':key})
    if state and state.get('completed'):
        raise HTTPException(409,'Lượt xác nhận đã dùng. Bắt đầu lượt mới')
    try:
        vector,_,frame_hash=extract(data.image)
    except HTTPException:
        store.db.face_attempts.delete_one({'_id':key,'completed':{'$ne':True}})
        raise
    candidate,score,gap=match(vector,gallery(),threshold=config.FACE_THRESHOLD,margin=config.FACE_MARGIN,min_samples=5)
    if candidate!=user['_id']:
        store.db.face_attempts.delete_one({'_id':key,'completed':{'$ne':True}})
        raise HTTPException(422,'Khuôn mặt chưa khớp tài khoản đang đăng nhập. Thử lại với mặt rõ hoặc liên hệ HR')
    if (not state or state['expires_at']<store.now() or state.get('assignment_id')!=data.assignment_id
            or state.get('action')!=data.action):
        state={'_id':key,'count':0,'hashes':[],'user_id':user['_id'],'assignment_id':data.assignment_id,'action':data.action}
    if frame_hash in state['hashes']:
        raise HTTPException(409,'Cần ảnh mới từ camera để xác nhận tiếp')
    state['count']+=1; state['hashes'].append(frame_hash)
    state['expires_at']=store.now()+timedelta(seconds=15)
    completed=state['count']>=3
    if completed:
        result=punch(user,data.assignment_id,data.action,source='face')
        state['completed']=True
        store.db.face_attempts.replace_one({'_id':key},state,upsert=True)
        return {'confirmed':True,'count':3,'attendance':result,'message':'Đã xác nhận khuôn mặt và ghi nhận công'}
    store.db.face_attempts.replace_one({'_id':key},state,upsert=True)
    return {'confirmed':False,'count':state['count'],'message':f'Đang xác nhận {state["count"]}/3'}
