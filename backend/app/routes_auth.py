import secrets
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from . import database as store, config
from .schemas import Login, PasswordChange
from .security import current_user, verify_password, password_hash, digest, throttle, audit, COOKIE
from .services import serialized

router = APIRouter(prefix='/auth', tags=['Đăng nhập'])
DUMMY_HASH = password_hash('constant-dummy-password-never-used')

@router.post('/login')
def login(data: Login, request: Request, response: Response):
    throttle('login:'+str(request.client.host), 30, 60)
    throttle('account:'+data.username.lower(), 10, 60)
    user = store.db.users.find_one({'username': data.username.lower()})
    valid = verify_password(data.password, user['password_hash'] if user else DUMMY_HASH)
    if not user or not valid or not user['active']:
        raise HTTPException(401, 'Tên đăng nhập hoặc mật khẩu không đúng, hoặc tài khoản đã khóa')
    token, csrf = secrets.token_urlsafe(40), secrets.token_urlsafe(32)
    store.db.sessions.insert_one({'_id':digest(token), 'user_id':user['_id'], 'csrf':csrf,
                                 'expires_at':store.now()+timedelta(hours=12)})
    response.set_cookie(COOKIE, token, max_age=43200, httponly=True, samesite='lax', secure=config.COOKIE_SECURE, path='/')
    return {'user':store.public(user), 'csrf':csrf}

@router.get('/me')
def me(request: Request, user=Depends(current_user)):
    return {'user':store.public(user), 'csrf':request.state.session['csrf']}

@router.post('/logout')
def logout(request: Request, response: Response, user=Depends(current_user)):
    store.db.sessions.delete_one({'_id':request.state.session['_id']})
    response.delete_cookie(COOKIE, path='/')
    return {'message':'Đã đăng xuất'}

@router.post('/password')
@serialized
def change_password(data: PasswordChange, response: Response, user=Depends(current_user)):
    if not verify_password(data.current_password, user['password_hash']):
        raise HTTPException(400, 'Mật khẩu hiện tại không đúng')
    store.db.users.update_one({'_id':user['_id']}, {'$set':{'password_hash':password_hash(data.new_password)}})
    store.db.sessions.delete_many({'user_id':user['_id']})
    response.delete_cookie(COOKIE, path='/')
    audit(user,'account.password',user['_id'])
    return {'message':'Đã đổi mật khẩu. Vui lòng đăng nhập lại'}
