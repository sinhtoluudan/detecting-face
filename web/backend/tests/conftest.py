import sys
from pathlib import Path
from datetime import timezone
import pytest
import mongomock
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import database as store, config
from app.seed import seed
from app.main import app

@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(store,'db',mongomock.MongoClient(tz_aware=True).test_attendance)
    monkeypatch.setattr(config,'SEED_DEMO',True)
    monkeypatch.setattr(config,'DEMO_PASSWORD','TestPassword@123')
    monkeypatch.setattr(mongomock, 'utcnow', lambda: store.now().astimezone(timezone.utc).replace(tzinfo=None))
    monkeypatch.setattr(store.db, 'command', lambda *a, **k: {'ok': 1})
    store.indexes();seed()
    # Lifespan runs against an injected MongoDB-compatible test store; ping is stubbed.
    with TestClient(app,raise_server_exceptions=True) as client:
        yield client

@pytest.fixture()
def login(client):
    def login_as(username='admin'):
        r=client.post('/api/auth/login',json={'username':username,'password':'TestPassword@123'})
        assert r.status_code==200,r.text
        client.headers['X-CSRF-Token']=r.json()['csrf']
        return r.json()['user']
    return login_as
