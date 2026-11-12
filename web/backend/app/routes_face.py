from datetime import timedelta
from secrets import compare_digest
from fastapi import APIRouter, Depends, Header, HTTPException
from . import database as store, config
from .schemas import FaceEnroll, FaceFrame, FacePunch, ReasonInput
from .security import current_user, roles, audit, throttle, visible_ids
from .services import get, serialized, punch, check_face_shift, bounds
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

@router.post('/kiosk/punch')
@serialized
def kiosk_punch(data: FaceFrame, kiosk_key: str = Header(default='', alias='X-FaceCam-Kiosk')):
    secret = config.FACECAM_KIOSK_KEY
    if not secret or not compare_digest(kiosk_key.encode(), secret.encode()):
        raise HTTPException(403, 'Máy này chưa được cấp quyền chấm công')
    throttle('face:kiosk', 60, 60)
    key = 'kiosk'
    try:
        vector, _, frame_hash = extract(data.image)
    except HTTPException:
        store.db.face_attempts.delete_one({'_id': key})
        raise

    candidate, _, _ = match(vector, gallery(), threshold=config.FACE_THRESHOLD,
                            margin=config.FACE_MARGIN, min_samples=5)
    person = store.db.users.find_one({'_id': candidate, 'active': True, 'role': {'$ne': 'admin'}}) if candidate else None
    if not person:
        store.db.face_attempts.delete_one({'_id': key})
        raise HTTPException(422, 'Chưa nhận ra nhân viên đã đăng ký')

    current = store.now()
    today = current.astimezone(config.TZ).date()
    assignments = store.db.assignments.find({'user_id': candidate, 'date': {
        '$in': [today.isoformat(), (today - timedelta(days=1)).isoformat()]}})
    for assignment in assignments:
        start, end, _ = bounds(assignment['date'], assignment['shift'])
        if start <= current < end:
            break
    else:
        store.db.face_attempts.delete_one({'_id': key})
        raise HTTPException(409, f"{person['name']} chưa có ca đang diễn ra")

    check_face_shift(assignment, current)
    state = store.db.face_attempts.find_one({'_id': key})
    if (not state or state['expires_at'] <= current or state['user_id'] != candidate
            or state['assignment_id'] != assignment['_id']):
        state = {'_id': key, 'user_id': candidate, 'assignment_id': assignment['_id'], 'hashes': []}
    if frame_hash not in state['hashes']:
        state['hashes'].append(frame_hash)
    count = len(state['hashes'])
    if count >= 3:
        punch(person, assignment['_id'], 'in', source='face')
        store.db.face_attempts.delete_one({'_id': key})
        return {'confirmed': True, 'message': f"{person['name']} · Chấm công thành công"}
    state['expires_at'] = current + timedelta(seconds=15)
    store.db.face_attempts.replace_one({'_id': key}, state, upsert=True)
    return {'confirmed': False, 'message': f"Đang xác nhận {person['name']} · {count}/3"}


@router.post('/punch')
def face_punch(data: FacePunch, user=Depends(current_user)):
    raise HTTPException(403, 'Vui lòng chấm công tại máy FaceCam chung')
