"""Web adapter for the ORIGINAL khang camera/core modules; MongoDB replaces Store.

No browser-provided employee identity or embedding is trusted for a face punch.
The API extracts embeddings itself and binds the result to the logged-in account.
"""
import base64
import hashlib
import logging
import sys
from pathlib import Path
from threading import Lock
from datetime import timedelta
from fastapi import HTTPException
from . import config, database as store

ROOT=Path(__file__).resolve().parents[2]
if not (ROOT/'core.py').is_file() and (ROOT.parent/'core.py').is_file():
    ROOT=ROOT.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from core import normalize, match  # Original branch algorithm, not a replacement.

_engine=None
_engine_settings=None
_engine_lock=Lock()


def extract(image,settings=None):
    global _engine,_engine_settings
    settings=settings or config.face_settings()
    if not config.FACE_ENABLED:
        raise HTTPException(503,'Chưa bật nhận diện. Cài requirements-face.txt và đặt FACE_ENABLED=true')
    try:
        from PIL import Image
        from io import BytesIO
        import cv2
        import numpy as np
        from camera import create_engine
        from regions import extract_regions
    except ImportError:
        raise HTTPException(503,'Máy chủ thiếu thư viện nhận diện. Xem hướng dẫn cài phần Face trong README')
    try:
        raw=base64.b64decode(image.split(',')[-1],validate=True)
        if len(raw)>1_200_000:
            raise ValueError()
        with Image.open(BytesIO(raw)) as probe:
            if probe.width>1920 or probe.height>1080 or probe.width<160 or probe.height<160:
                raise ValueError()
        frame=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError()
    except Exception:
        raise HTTPException(422,'Ảnh không hợp lệ. Dùng ảnh camera tối đa 1920×1080 và 1.2 MB')
    with _engine_lock:
        engine_settings=(settings['cpu_threads'],settings['detection_size'])
        if _engine is None or _engine_settings!=engine_settings:
            _engine=None
            _engine_settings=None
            try:
                _engine=create_engine(settings)
                _engine_settings=engine_settings
            except Exception as exc:
                logging.exception('Could not initialize the face recognition model')
                raise HTTPException(503,'Không nạp được buffalo_l. Kiểm tra model, thư viện và kết nối tải model trên máy chủ') from exc
        try:
            faces=_engine.get(frame,max_num=2)
        except Exception as exc:
            logging.exception('Face recognition failed while processing a frame')
            raise HTTPException(503,'Không xử lý được ảnh khuôn mặt. Hãy thử lại hoặc liên hệ quản trị viên') from exc
    if len(faces)!=1:
        raise HTTPException(422,'Cần đúng một khuôn mặt trong khung hình')
    face=faces[0]
    x1,y1,x2,y2=[int(v) for v in face.bbox]
    h,w=frame.shape[:2]
    x1,y1,x2,y2=max(0,x1),max(0,y1),min(w,x2),min(h,y2)
    crop=frame[y1:y2,x1:x2]
    blur=float(cv2.Laplacian(cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY),cv2.CV_64F).var()) if crop.size else 0
    if min(x2-x1,y2-y1)<settings['min_face_size'] or blur<settings['min_blur_score'] or float(face.det_score)<0.65:
        raise HTTPException(422,'Mặt quá nhỏ hoặc mờ. Tiến gần camera và giữ mặt rõ')
    region_data=extract_regions(frame,face.kps)['vectors']
    return normalize(face.normed_embedding),region_data,hashlib.sha256(raw).hexdigest()


def gallery():
    active={x['_id']:x['name'] for x in store.db.users.find({'active':True},{'name':1})}
    return {p['_id']:{'name':active[p['_id']],'vectors':[normalize(v) for v in p.get('vectors',[])],
                         'regions':p.get('regions',[])}
            for p in store.db.face_profiles.find({'model':'buffalo_l'}) if p['_id'] in active}
