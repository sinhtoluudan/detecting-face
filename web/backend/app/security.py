import hashlib
import hmac
import secrets
from datetime import timedelta
from fastapi import Depends, HTTPException, Request
from . import database as store, config

COOKIE = 'facecam_session'

def password_hash(value):
    salt = secrets.token_hex(16)
    result = hashlib.scrypt(value.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
    return f'{salt}:{result.hex()}'

def verify_password(value, encoded):
    try:
        salt, expected = encoded.split(':')
        actual = hashlib.scrypt(value.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False

def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()

def current_user(request: Request):
    token = request.cookies.get(COOKIE, '')
    session = store.db.sessions.find_one({'_id': digest(token), 'expires_at': {'$gt': store.now()}})
    if not session:
        raise HTTPException(401, 'Vui lòng đăng nhập lại')
    user = store.db.users.find_one({'_id': session['user_id'], 'active': True})
    if not user:
        raise HTTPException(401, 'Tài khoản đã bị khóa')
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        if not hmac.compare_digest(request.headers.get('X-CSRF-Token', ''), session['csrf']):
            raise HTTPException(403, 'Phiên thao tác không hợp lệ, vui lòng tải lại trang')
    request.state.session = session
    return user

def roles(*allowed):
    def dependency(user=Depends(current_user)):
        if user['role'] not in allowed:
            raise HTTPException(403, 'Bạn không có quyền thực hiện thao tác này')
        return user
    return dependency

def visible_ids(user):
    if user['role'] in ['admin', 'hr']:
        return None
    if user['role'] == 'manager':
        departments = [x['_id'] for x in store.db.departments.find({'manager_id': user['_id']})]
        return list({user['_id'], *[x['_id'] for x in store.db.users.find({'department_id': {'$in': departments}})]})
    return [user['_id']]

def require_visible(user, target):
    ids = visible_ids(user)
    if ids is not None and target not in ids:
        raise HTTPException(403, 'Nhân viên không thuộc phạm vi quản lý của bạn')

def audit(actor, action, target, before=None, after=None, reason=''):
    store.db.audit.insert_one({'_id': store.uid(), 'actor_id': actor['_id'], 'actor_name': actor['name'],
        'action': action, 'target': target, 'before': before, 'after': after, 'reason': reason,
        'created_at': store.now()})

def throttle(key, limit=10, seconds=60):
    bucket = int(store.now().timestamp()) // seconds
    record = store.db.rate_limits.find_one_and_update({'_id': f'{key}:{bucket}'},
        {'$inc': {'count': 1}, '$setOnInsert': {'expires_at': store.now()+timedelta(seconds=seconds*2)}},
        upsert=True, return_document=True)
    if record['count'] > limit:
        raise HTTPException(429, 'Bạn thao tác quá nhanh, vui lòng thử lại sau ít phút')
