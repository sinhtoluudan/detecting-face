import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import DuplicateKeyError, PyMongoError
from . import database as store, config
from .seed import seed
from .routes_auth import router as auth_router
from .routes_catalog import router as catalog_router
from .routes_attendance import router as attendance_router
from .routes_face import router as face_router

@asynccontextmanager
async def lifespan(app):
    store.db.command('ping')
    store.indexes()
    seed()
    yield

app=FastAPI(title='FaceCam • Chấm công',version='1.0.0',lifespan=lifespan,
    description='Next.js + FastAPI + MongoDB. Adapter nhận diện từ nhánh khang. Đăng nhập tại /auth/login; lấy csrf trong response để gọi API ghi dữ liệu.')
app.add_middleware(CORSMiddleware,allow_origins=config.ALLOWED_ORIGINS,allow_credentials=True,
    allow_methods=['GET','POST','PUT','DELETE','OPTIONS'],allow_headers=['Content-Type','X-CSRF-Token'])

@app.middleware('http')
async def protect(request: Request, call_next):
    origin=request.headers.get('origin')
    if request.method not in ['GET','HEAD','OPTIONS']:
        if origin and origin not in config.ALLOWED_ORIGINS:
            return JSONResponse({'detail':'Nguồn yêu cầu không được phép'},status_code=403)
        if request.headers.get('sec-fetch-site')=='cross-site' and not origin:
            return JSONResponse({'detail':'Nguồn yêu cầu không được phép'},status_code=403)
        if int(request.headers.get('content-length','0') or '0')>2_000_000:
            return JSONResponse({'detail':'Yêu cầu quá lớn'},status_code=413)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['Cache-Control']='no-store'
    return response

@app.exception_handler(DuplicateKeyError)
async def duplicate(request, exc):
    return JSONResponse({'detail':'Dữ liệu bị trùng (tên đăng nhập, mã nhân viên hoặc ca đã tồn tại)'},status_code=409)

@app.exception_handler(PyMongoError)
async def database_error(request, exc):
    logging.exception('MongoDB operation failed')
    return JSONResponse({'detail':'Không kết nối được MongoDB. Kiểm tra dịch vụ rồi thử lại'},status_code=503)

@app.get('/api/health')
def health():
    store.db.command('ping')
    return {'status':'ok','database':'mongodb'}

for router in [auth_router,catalog_router,attendance_router,face_router]:
    app.include_router(router,prefix='/api')
