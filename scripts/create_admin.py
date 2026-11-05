"""Bootstrap an empty production database. Never resets existing accounts."""
import sys
from pathlib import Path
from getpass import getpass
from datetime import date
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app import database as store
from app.security import password_hash


def main():
    store.db.command('ping'); store.indexes()
    if store.db.users.count_documents({'role':'admin'}):
        raise SystemExit('Đã có tài khoản Admin. Đăng nhập để quản lý tài khoản; script không ghi đè.')
    name=input('Họ tên Admin: ').strip()
    username=input('Tên đăng nhập: ').strip().lower()
    password=getpass('Mật khẩu (ít nhất 10 ký tự): ')
    confirm=getpass('Nhập lại mật khẩu: ')
    from app.schemas import UserInput
    values=UserInput(code='ADMIN001',name=name,username=username,password=password,role='admin',joined_date=date.today())
    if password!=confirm:
        raise SystemExit('Hai mật khẩu không khớp')
    record=values.model_dump(mode='json',exclude={'password'})
    store.db.users.insert_one({'_id':store.uid(),**record,'password_hash':password_hash(password),'created_at':store.now()})
    print('Đã tạo Admin. Mật khẩu không được in hoặc lưu vào file.')

if __name__=='__main__': main()
