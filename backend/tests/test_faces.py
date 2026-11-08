import json
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

def test_face_settings_reload_from_shared_config(tmp_path,monkeypatch):
    settings=routes_face.config.face_settings()
    path=tmp_path/'config.json'
    values=json.loads(routes_face.config.FACE_CONFIG_PATH.read_text(encoding='utf-8'))
    values['similarity_threshold']=0.64
    values['runner_up_margin']=0.12
    path.write_text(json.dumps(values),encoding='utf-8')
    monkeypatch.setattr(routes_face.config,'FACE_CONFIG_PATH',path)
    assert routes_face.config.face_settings()['threshold']==0.64
    values['similarity_threshold']=0.68
    path.write_text(json.dumps(values),encoding='utf-8')
    current=routes_face.config.face_settings()
    assert current['threshold']==0.68 and current['margin']==0.12
    assert current['confirm_frames']==settings['confirm_frames']


def test_face_requires_three_frames_and_own_account(client,login,monkeypatch):
    login('employee')
    day=store.now().astimezone(routes_face.config.TZ).date().isoformat()
    a=store.db.assignments.find_one({'user_id':'user-employee','date':day})
    start,end,_=bounds(a['date'],a['shift'])
    monkeypatch.setattr(store,'now',lambda:start+timedelta(minutes=5))
    vector=np.zeros(512,dtype=np.float32);vector[0]=1
    store.db.face_profiles.insert_one({'_id':'user-employee','vectors':[vector.tolist()]*5,'regions':[],'model':'buffalo_l'})
    required=routes_face.config.face_settings()['confirm_frames']
    serial=iter(['in0','in0',*[f'in{index}' for index in range(1,required)],
                 *[f'out{index}' for index in range(required)]])
    monkeypatch.setattr(routes_face,'extract',lambda image,settings=None:(vector,{},next(serial)))
    payload={'assignment_id':a['_id'],'action':'in','attempt_id':'12345678-1234-1234-1234-123456789abc','image':'x'*40}
    for index in range(required):
        r=client.post('/api/faces/punch',json=payload)
        assert r.status_code==200,r.text
        assert r.json()['confirmed']==(index==required-1)
        if index==0:
            assert client.post('/api/faces/punch',json=payload).status_code==409
    assert store.db.attendance.find_one({'assignment_id':a['_id']})['source']=='face'
    assert client.post('/api/faces/punch',json=payload).status_code==409
    monkeypatch.setattr(store,'now',lambda:end)
    payload.update(action='out',attempt_id='22345678-1234-1234-1234-123456789abc')
    for index in range(required):
        r=client.post('/api/faces/punch',json=payload)
        assert r.status_code==200,r.text
        assert r.json()['confirmed']==(index==required-1)
    attendance=store.db.attendance.find_one({'assignment_id':a['_id']})
    assert attendance['out_source']=='face' and attendance['check_out']==end
    assert client.post('/api/attendance/punch',json={'assignment_id':a['_id'],'action':'out'}).status_code==403
    assert 'vectors' not in client.get('/api/faces/profiles').text


def test_face_enrollment_permission_and_consent(client,login):
    login('employee')
    assert client.post('/api/faces/user-employee/enroll',json={'image':'x'*40,'consent':True}).status_code==403
    login('manager')
    assert client.post('/api/faces/user-employee/enroll',json={'image':'x'*40,'consent':False}).status_code==422
    login('hr')
    assert client.post('/api/faces/user-employee/enroll',json={'image':'x'*40,'consent':False}).status_code==422
