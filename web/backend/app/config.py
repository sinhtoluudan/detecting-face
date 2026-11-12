import os
from pathlib import Path
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / '.env')
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017')
MONGO_DB = os.getenv('MONGO_DB', 'facecam_attendance')
TZ = ZoneInfo('Asia/Ho_Chi_Minh')
ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',')
COOKIE_SECURE = os.getenv('COOKIE_SECURE', 'false').lower() == 'true'
SEED_DEMO = os.getenv('SEED_DEMO', 'false').lower() == 'true'
DEMO_PASSWORD = os.getenv('DEMO_PASSWORD', '')
FACECAM_KIOSK_KEY = os.getenv('FACECAM_KIOSK_KEY', '')
FACE_ENABLED = os.getenv('FACE_ENABLED', 'false').lower() == 'true'
FACE_THRESHOLD = float(os.getenv('FACE_THRESHOLD', '0.50'))
FACE_MARGIN = float(os.getenv('FACE_MARGIN', '0.08'))
if not 0 < FACE_THRESHOLD <= 1 or not 0 <= FACE_MARGIN <= 1:
    raise ValueError('FACE_THRESHOLD/FACE_MARGIN không hợp lệ')
