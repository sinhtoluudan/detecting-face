import numpy as np
from datetime import datetime, timedelta
from unittest.mock import patch
import pytest
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


def test_kiosk_without_personal_assignment(client,login,monkeypatch):
    login('admin')
    day=store.now().astimezone(routes_face.config.TZ).date()
    shift=store.db.shifts.find_one({'_id':'shift-office'})
    start,_,_=bounds(day,shift)
    clock=[start+timedelta(minutes=10)]
    monkeypatch.setattr(store,'now',lambda:clock[0])
    monkeypatch.setattr(routes_face.config,'FACECAM_KIOSK_KEY','test-device')
    assert not store.db.assignments.find_one({'user_id':'user-admin'})
    vector=np.zeros(512,dtype=np.float32);vector[0]=1
    store.db.face_profiles.insert_one({'_id':'user-admin','vectors':[vector.tolist()]*5,'regions':[],'model':'buffalo_l'})
    monkeypatch.setattr(routes_face,'extract',lambda image:(vector,{},image))
    def scan(index):
        return client.post('/api/faces/kiosk/punch',json={'image':str(index)*40},headers={'X-FaceCam-Kiosk':'test-device'})
    for index in (1,1,2,3):
        r=scan(index)
        assert r.status_code==200,r.text
        assert r.json()['confirmed']==(index==3)
        clock[0]+=timedelta(seconds=1)
    assert r.json()['status']=='on_time'
    assert scan(4).status_code==409
    clock[0]=start+timedelta(hours=11)
    for i in (5,6,7):
        r=scan(i)
    assert r.json()['status']=='outside_shift'
    assert scan(8).status_code==409
    rows=client.get('/api/reports',params={'month':str(day)[:7]}).json()['rows']
    mine=[r for r in rows if r['user_id']=='user-admin']
    assert {r['status'] for r in mine}=={'on_time','outside_shift'}
    assert len(mine)==2
    assert all(r['check_in'] for r in mine)
    assert next(r for r in mine if r['status']=='outside_shift')['planned_minutes']==0
    assert client.get('/api/attendance/today').status_code==200
    assert 'vectors' not in client.get('/api/faces/profiles').text

@pytest.mark.parametrize('timestamp,status,day', [
    ('2026-11-19 07:29:59','outside_shift','2026-11-19'),
    ('2026-11-19 07:30:00','on_time','2026-11-19'),
    ('2026-11-19 08:10:00','on_time','2026-11-19'),
    ('2026-11-19 08:10:01','late','2026-11-19'),
    ('2026-11-19 17:00:00','late','2026-11-19'),
    ('2026-11-19 17:00:01','outside_shift','2026-11-19'),
    ('2026-11-20 02:00:00','late','2026-11-19'),
    ('2026-11-21 02:00:00','outside_shift','2026-11-21'),
])
def test_shared_shift_windows(timestamp,status,day):
    shifts=[dict(_id='office',start='08:00',end='17:00',weekdays=[3]),
            dict(_id='night',start='22:00',end='06:00',weekdays=[3])]
    with patch.object(store,'db') as db:
        db.shifts.find.return_value=shifts
        actual_day,_,actual_status=routes_face.kiosk_slot(datetime.fromisoformat(timestamp).replace(tzinfo=routes_face.config.TZ))
        db.shifts.find.assert_called_once_with({'active':True})
    assert (actual_day,actual_status)==(day,status)


def test_face_enrollment_permission_and_consent(client,login):
    login('employee')
    assert client.post('/api/faces/user-employee/enroll',json={'image':'x'*40,'consent':True}).status_code==403
    login('hr')
    assert client.post('/api/faces/user-employee/enroll',json={'image':'x'*40,'consent':False}).status_code==422
