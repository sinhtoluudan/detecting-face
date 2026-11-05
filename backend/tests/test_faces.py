import numpy as np
from datetime import timedelta
from app import database as store
from app import routes_face
from app.calculations import bounds
from app.face_service import normalize, match


def test_original_match_threshold_and_ambiguity():
    v=np.zeros(512);v[0]=1
    assert np.linalg.norm(normalize(v))==1
    gallery={'a':{'vectors':[v]*5},'b':{'vectors':[v]*5}}
    assert match(v,gallery)[0] is None
    del gallery['b']
    assert match(v,gallery)[0]=='a'


def test_face_requires_three_frames_and_own_account(client,login,monkeypatch):
    login('employee')
    day=store.now().astimezone(routes_face.config.TZ).date().isoformat()
    a=store.db.assignments.find_one({'user_id':'user-employee','date':day})
    start,end,_=bounds(a['date'],a['shift'])
    monkeypatch.setattr(store,'now',lambda:start+timedelta(minutes=5))
    vector=np.zeros(512,dtype=np.float32);vector[0]=1
    store.db.face_profiles.insert_one({'_id':'user-employee','vectors':[vector.tolist()]*5,'regions':[],'model':'buffalo_l'})
    serial=iter(['frame1','frame2','frame3','frame4'])
    monkeypatch.setattr(routes_face,'extract',lambda image:(vector,{},next(serial)))
    payload={'assignment_id':a['_id'],'action':'in','attempt_id':'12345678-1234-1234-1234-123456789abc','image':'x'*40}
    for index in range(3):
        r=client.post('/api/faces/punch',json=payload)
        assert r.status_code==200,r.text
        assert r.json()['confirmed']==(index==2)
    assert store.db.attendance.find_one({'assignment_id':a['_id']})['source']=='face'
    assert client.post('/api/faces/punch',json=payload).status_code==409
    assert 'vectors' not in client.get('/api/faces/profiles').text


def test_face_enrollment_permission_and_consent(client,login):
    login('employee')
    assert client.post('/api/faces/user-employee/enroll',json={'image':'x'*40,'consent':True}).status_code==403
    login('hr')
    assert client.post('/api/faces/user-employee/enroll',json={'image':'x'*40,'consent':False}).status_code==422
