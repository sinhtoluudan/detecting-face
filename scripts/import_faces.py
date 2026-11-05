"""Read-only SQLite -> MongoDB import with explicit person-id/employee-code map.
Dry run by default. Does not modify the desktop database or auto-match names.
"""
import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app import database as store
from app.face_service import normalize, ROOT
from region_match import VERSION, validate_regions


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sqlite',required=True,type=Path)
    parser.add_argument('--mapping',required=True,type=Path,help='CSV columns: person_id,employee_code')
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--consent-confirmed',action='store_true',help='Confirm permission to migrate biometric templates')
    args=parser.parse_args()
    if args.apply and not args.consent_confirmed:
        raise SystemExit('Cần --consent-confirmed khi --apply. Chỉ chuyển mẫu của người đã đồng ý.')
    if not args.sqlite.is_file():
        raise SystemExit('Không tìm thấy SQLite nguồn')
    with args.mapping.open(encoding='utf-8-sig',newline='') as f:
        mapping=list(csv.DictReader(f))
    if not mapping or set(mapping[0])!={'person_id','employee_code'}:
        raise SystemExit('CSV cần đúng hai cột person_id,employee_code')
    if len({m['person_id'] for m in mapping})!=len(mapping) or len({m['employee_code'] for m in mapping})!=len(mapping):
        raise SystemExit('Không cho phép trùng person_id hoặc employee_code trong mapping')
    db=sqlite3.connect(args.sqlite.resolve().as_uri()+'?mode=ro',uri=True)
    columns={r[1] for r in db.execute('PRAGMA table_info(samples)')}
    query='SELECT embedding,model'+(',regions' if 'regions' in columns else '')+' FROM samples WHERE person_id=?'
    pending=[]
    for m in mapping:
        employee=store.db.users.find_one({'code':m['employee_code'],'active':True})
        if not employee:
            raise SystemExit('Không tìm thấy nhân viên đang hoạt động: '+m['employee_code'])
        if not db.execute('SELECT 1 FROM people WHERE id=?',(m['person_id'],)).fetchone():
            raise SystemExit('Không tìm thấy person_id trong SQLite: '+m['person_id'])
        # Import is append-only. Stop on an existing profile to avoid overwriting data during concurrent enrollment.
        if store.db.face_profiles.find_one({'_id':employee['_id']}):
            raise SystemExit('Đã có mẫu trên web cho '+m['employee_code']+'. Không tự ghi đè.')
        vectors=[];regions=[]
        for row in db.execute(query,(m['person_id'],)):
            if row[1]!='buffalo_l':
                continue
            vector=normalize(np.frombuffer(row[0],dtype=np.float32))
            if any(float(normalize(v)@vector)>0.9995 for v in vectors):
                continue
            clean={}
            if len(row)>2 and row[2]:
                region=json.loads(row[2])
                if region.get('version')==VERSION:
                    clean={k:v.tolist() for k,v in validate_regions(region.get('vectors')).items()}
            vectors.append(vector.tolist());regions.append(clean)
        if not vectors or len(vectors)>60:
            raise SystemExit('Số mẫu không hợp lệ (1..60): '+m['employee_code'])
        pending.append({'_id':employee['_id'],'model':'buffalo_l','vectors':vectors,'regions':regions,
                        'updated_at':store.now(),'consent_at':store.now(),'enrolled_by':'sqlite-import'})
        print(f'{m["employee_code"]}: {len(vectors)} mẫu hợp lệ'+(' (chưa đủ 5 mẫu để nhận diện)' if len(vectors)<5 else ''))
    db.close()
    if args.apply:
        for record in pending:
            store.db.face_profiles.insert_one(record)
            store.db.audit.insert_one({'_id':store.uid(),'actor_id':'cli','actor_name':'Quản trị viên CLI',
                'action':'face.import','target':record['_id'],'created_at':store.now(),
                'after':{'samples':len(record['vectors'])},'reason':'Chuyển mẫu có xác nhận đồng ý từ FaceCam desktop'})
        print('Đã chuyển mẫu sang MongoDB. SQLite nguồn giữ nguyên.')
    else:
        print('DRY RUN: chưa ghi dữ liệu. Kiểm tra mapping; thêm --apply --consent-confirmed khi sẵn sàng.')

if __name__=='__main__': main()
