import json
import os
from pathlib import Path
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / '.env')
load_dotenv(Path(__file__).resolve().parents[2] / '.env', override=False)
MONGO_URI = os.getenv('MONGO_URI')
if not MONGO_URI or (MONGO_URI == 'mongodb://localhost:27017' and os.getenv('MONGO_PASSWORD')):
    mongo_port = os.getenv('MONGO_PORT', '27017')
    mongo_user = os.getenv('MONGO_USER')
    mongo_password = os.getenv('MONGO_PASSWORD')
    credentials = f'{quote_plus(mongo_user)}:{quote_plus(mongo_password)}@' if mongo_user and mongo_password else ''
    auth_source = '?authSource=admin' if credentials else ''
    MONGO_URI = f'mongodb://{credentials}localhost:{mongo_port}/{auth_source}'
MONGO_DB = os.getenv('MONGO_DB', 'facecam_attendance')
TZ = ZoneInfo('Asia/Ho_Chi_Minh')
ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',')
COOKIE_SECURE = os.getenv('COOKIE_SECURE', 'false').lower() == 'true'
SEED_DEMO = os.getenv('SEED_DEMO', 'false').lower() == 'true'
DEMO_PASSWORD = os.getenv('DEMO_PASSWORD', '')
FACE_ENABLED = os.getenv('FACE_ENABLED', 'false').lower() == 'true'
FACE_CONFIG_PATH = Path(os.getenv('FACECAM_CONFIG_PATH',
    str(Path(__file__).resolve().parents[2] / 'config.json')))

def face_settings():
    try:
        values = json.loads(FACE_CONFIG_PATH.read_text(encoding='utf-8'))
        settings = {
            'threshold': float(values['similarity_threshold']),
            'margin': float(values['runner_up_margin']),
            'min_samples': int(values['min_samples']),
            'confirm_frames': int(values['confirm_frames']),
            'detection_size': int(values['detection_size']),
            'cpu_threads': int(values['cpu_threads']),
            'min_face_size': int(values['min_face_size']),
            'min_blur_score': float(values['min_blur_score']),
        }
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(f'Không đọc được cấu hình nhận diện từ {FACE_CONFIG_PATH}') from exc
    if not 0 < settings['threshold'] <= 1 or not 0 <= settings['margin'] <= 1:
        raise RuntimeError('Ngưỡng nhận diện và biên trong config.json phải nằm trong khoảng 0 đến 1')
    if not 5 <= settings['min_samples'] <= 60 or not 1 <= settings['confirm_frames'] <= 10:
        raise RuntimeError('Số mẫu hoặc số ảnh xác nhận trong config.json không hợp lệ')
    if not 160 <= settings['detection_size'] <= 1024 or settings['detection_size'] % 32:
        raise RuntimeError('detection_size trong config.json phải chia hết cho 32, từ 160 đến 1024')
    if not 1 <= settings['cpu_threads'] <= 16 or not 40 <= settings['min_face_size'] <= 500:
        raise RuntimeError('Số luồng hoặc kích thước khuôn mặt trong config.json không hợp lệ')
    if not 0 <= settings['min_blur_score'] <= 10000:
        raise RuntimeError('min_blur_score trong config.json không hợp lệ')
    return settings
