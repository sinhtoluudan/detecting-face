from datetime import datetime, timezone
from uuid import uuid4
from pymongo import MongoClient
from . import config

client = MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=5000, tz_aware=True)
db = client[config.MONGO_DB]

def now():
    return datetime.now(timezone.utc)

def uid():
    return uuid4().hex

def public(doc):
    if doc is None:
        return None
    return {('id' if k == '_id' else k): v for k, v in doc.items()
            if k not in {'password_hash', 'token_hash', 'csrf', 'vectors', 'regions'}}

def indexes():
    db.users.create_index('username', unique=True)
    db.users.create_index('code', unique=True)
    db.departments.create_index('name', unique=True)
    db.shifts.create_index('name', unique=True)
    db.assignments.create_index([('user_id', 1), ('date', 1)], unique=True)
    db.attendance.create_index('assignment_id', unique=True)
    db.sessions.create_index('expires_at', expireAfterSeconds=0)
    db.rate_limits.create_index('expires_at', expireAfterSeconds=0)
    db.face_attempts.create_index('expires_at', expireAfterSeconds=0)
    db.requests.create_index([('user_id', 1), ('start_date', 1)])
    db.audit.create_index('created_at')
