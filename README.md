# FaceCam Attendance — Next.js + FastAPI + MongoDB

Bản web chấm công được bổ sung vào repo `sinhtoluudan/detecting-face`, dựa trên nhánh **khang**, commit nguồn `2f880801296095393f069867308e894bb2273811`.

Ứng dụng desktop ở thư mục gốc được giữ nguyên. Bản web nằm trong `web/`; database của bản web là **MongoDB**, không dùng SQLite để lưu nhân sự/chấm công. SQLite chỉ còn thuộc app desktop và script đọc để chuyển mẫu cũ khi bạn chủ động chạy.

## 1. Chạy nhanh bằng Docker Desktop (Windows)

Mở Docker Desktop ở chế độ Linux containers. Mở PowerShell tại thư mục `web`:

```powershell
Copy-Item .env.example .env
docker compose up -d --build
```

Hoặc nhấp đúp `web/start-docker.bat` (chỉ tạo `.env` nếu chưa có).

- Web: **http://localhost:3000**
- Swagger API: **http://localhost:8000/docs**
- Kiểm tra API: **http://localhost:8000/api/health**
- MongoDB trên máy: **localhost:27019**, bên trong Docker: `mongo:27017`.
- Database: `facecam_attendance`.
- MongoDB và model nhận diện được lưu trong Docker volumes, vẫn còn sau khi restart container.

Tài khoản mẫu (chỉ dùng với dữ liệu demo):

| Tên đăng nhập | Vai trò | Phạm vi |
|---|---|---|
| `admin` | Admin | Toàn hệ thống |
| `hr` | Nhân sự | Nhân sự, ca, duyệt đơn, chốt công |
| `manager` | Quản lý | Phòng Công nghệ |
| `employee` | Nhân viên | Hồ sơ và công cá nhân |
| `linh` | Nhân viên | Phòng Công nghệ |
| `tuan` | Nhân viên | Phòng Kinh doanh |

Mật khẩu mẫu của tất cả tài khoản: **`Demo@123456`**. Có thể đặt giá trị khác ở `DEMO_PASSWORD` **trước lần khởi động đầu**. Khi database đã có tài khoản, seed không chạy lại, không đổi mật khẩu và không ghi đè dữ liệu. Đổi mật khẩu trong web bằng biểu tượng chìa khóa ở góc trên bên phải; hoặc Admin đặt lại mật khẩu qua chỉnh sửa nhân viên.

Docker mặc định cài phần nhận diện (`INSTALL_FACE=true`) và bật `FACE_ENABLED=true`. Lần đầu xác minh/đăng ký khuôn mặt cần tải model buffalo_l khoảng 300 MB; có thể mất vài phút. Nếu chỉ cần kiểm tra 8 chức năng nghiệp vụ trước, đặt cả `INSTALL_FACE=false` và `FACE_ENABLED=false` rồi build lại. Chấm công thủ công vẫn dùng được.

Nếu cổng bận: đổi `WEB_PORT`, `API_PORT`, `MONGO_PORT` trong `web/.env`. Khi đổi cổng web, sửa `ALLOWED_ORIGINS` theo URL mới. Cổng Mongo được để 27019 nhằm tránh xung đột phổ biến với 27017/27018.

```powershell
docker compose ps
docker compose logs --tail=100 api
docker compose logs --tail=100 frontend
docker compose down
```

`docker compose down` giữ dữ liệu. **Không dùng `down -v` nếu cần giữ database và mẫu khuôn mặt.**

Mật khẩu Mongo trong ví dụ chỉ phục vụ máy local; nếu dùng ký tự đặc biệt trong mật khẩu, phải URL-encode phần mật khẩu của `MONGO_URI` hoặc cung cấp URI hoàn chỉnh phù hợp.

## 2. Chạy riêng FastAPI và Next.js, dùng MongoDB sẵn trên Windows

Cần Python 3.11 64-bit, Node.js 22 LTS, MongoDB đang chạy. Không sử dụng venv desktop cho backend web; hai ứng dụng có môi trường riêng.

### Terminal 1 — backend

```powershell
cd web\backend
Copy-Item .env.example .env
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Trong `backend/.env`, sửa `MONGO_URI` nếu MongoDB có tài khoản hoặc cổng khác:

```dotenv
MONGO_URI=mongodb://localhost:27017
MONGO_DB=facecam_attendance
```

Nếu chạy Mongo bằng Compose nhưng chạy API bằng Python: dùng cổng host 27019 và thông tin đăng nhập khớp `.env` của Compose, thêm `?authSource=admin`.

### Terminal 2 — frontend

```powershell
cd web\frontend
Copy-Item .env.example .env.local
npm ci
npm run dev
```

Mở http://localhost:3000. Frontend gọi `/api/*`, Next.js proxy đến FastAPI qua `API_PROXY_URL`; trình duyệt không kết nối trực tiếp MongoDB. Có thể dùng hai file `start-windows.bat` tương ứng để tự tạo môi trường và chạy.

### Bật nhận diện trên backend Python

Dừng FastAPI, chạy:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-face.txt
```

Sửa `FACE_ENABLED=true` trong `backend/.env`, rồi khởi động lại API. Nếu build InsightFace trên Windows yêu cầu compiler, cài Visual Studio Build Tools với **Desktop development with C++**, hoặc dùng Docker.

Model lưu tại `%USERPROFILE%\.insightface\models\buffalo_l` khi chạy Python trực tiếp. Có thể tái sử dụng model sẵn có ở đó. Bộ mã nguồn không kèm trọng số.

## 3. Đủ 8 nhóm chức năng

| Nhóm | Đã thực hiện | Màn hình |
|---|---|---|
| 1. Đăng nhập & phân quyền | Session cookie HttpOnly, scrypt password hash, CSRF, giới hạn đăng nhập, 4 vai trò, đổi mật khẩu, thu hồi phiên khi khóa/đổi mật khẩu/đổi vai trò | Đăng nhập, hồ sơ góc trên |
| 2. Nhân viên | Tạo/sửa hồ sơ và tài khoản, mã NV, phòng ban, chức danh, ngày vào làm, khóa/mở, đặt lại mật khẩu; không trả hash ra giao diện | Nhân viên |
| 3. Phòng ban | Tạo/sửa/xóa phòng trống, gán quản lý, giới hạn quản lý theo phòng | Phòng ban |
| 4. Ca làm | Tạo/sửa/ngưng ca, giờ nghỉ chính xác, ngưỡng đi trễ, ca qua đêm, ngày lễ | Ca làm việc |
| 5. Phân ca | Phân nhiều nhân viên theo khoảng ngày và thứ trong tuần, một ca/ngày, kiểm tra trùng giờ giữa hai ngày, hủy ca chưa có công/đơn | Lịch phân ca |
| 6. Chấm công | Vào/ra bằng giờ máy chủ, chặn trùng và ra khi chưa vào, lịch sử, xác minh khuôn mặt tùy chọn | Chấm công |
| 7. Đơn từ | Nghỉ phép, sửa công, tăng ca, từ xa, công tác, trễ/sớm; gửi/hủy đơn chờ; duyệt/từ chối có ghi chú; không tự duyệt | Đơn từ |
| 8. Bảng công | Tính giờ/ngày công, trễ/sớm, nghỉ có lương, tăng ca đã duyệt, lọc theo tháng, XLSX, chốt/mở tháng có lý do và nhật ký | Bảng công |

Có thêm dashboard, hồ sơ khuôn mặt và nhật ký thay đổi. Không có đăng ký công khai; Admin/HR cấp tài khoản nhân viên. HR không tạo/sửa tài khoản Admin hoặc HR. Quản lý chỉ phân ca/xem/duyệt cho nhân viên thuộc phòng mình quản lý. Đơn của quản lý cần HR/Admin duyệt.

## 4. Quy tắc tính công và phạm vi bản đầu

- Tất cả ngày/ca theo `Asia/Ho_Chi_Minh`; thời điểm chấm lấy từ server, lưu datetime trong MongoDB.
- Một nhân viên được phân **một ca/ngày**. Ca 22:00–06:00 thuộc ngày bắt đầu. Chặn ca trùng giờ với ngày liền kề.
- Ca đã phân giữ bản sao giờ làm/giờ nghỉ, nên sửa định nghĩa ca không đổi dữ liệu cũ.
- Ca 08:00–17:00, nghỉ 12:00–13:00 có 480 phút chuẩn. Giờ làm là giao giữa thời gian có mặt và khung ca, trừ đúng khoảng nghỉ giao nhau.
- Nếu cho trễ 5 phút: vào 08:04 ghi 0 phút trễ, vào 08:10 ghi 10 phút trễ. Thời gian cho phép chỉ áp dụng cờ đi trễ, không tự cộng phút chưa làm vào giờ thực tế.
- Công quy đổi = `(phút làm thực tế + phút nghỉ hưởng lương) / phút chuẩn của ca`, tối đa 1 công mỗi ca.
- Nghỉ một phần ngày được nhập theo số giờ; tổng phút được tính không vượt giờ chuẩn. Nếu vừa có đơn nghỉ vừa trễ/sớm, đánh dấu HR cần rà soát; không tự suy ra người đó được nghỉ vào đầu hay cuối ca.
- Tăng ca phải có đơn đã duyệt **và** giờ ra/vào thực tế bao phủ. Chỉ lấy phần ngoài ca; không tự tính người ra muộn thành tăng ca. Bản đầu cho một đơn tăng ca trong ngày.
- Đơn từ xa/công tác/trễ-sớm là phê duyệt nghiệp vụ; không tự tạo lượt chấm công hoặc miễn trừ số phút. Muốn sửa giờ công cần đơn bổ sung.
- Chấm công trong cửa sổ: trước giờ bắt đầu tối đa 2 giờ, sau giờ kết thúc tối đa 8 giờ. Ngoài cửa sổ dùng đơn bổ sung có người duyệt.
- Chỉ ngày đã được phân ca mới được đưa vào bảng công. Ngày không phân ca không tự tính là vắng. Ngày lễ là ghi chú; không tự áp dụng hệ số lương hoặc tự xóa ca đã phân.
- Chỉ chốt tháng đã kết thúc, không còn đơn chờ và ca thiếu lượt ra. Khi chốt lưu snapshot bảng công và chặn thay đổi; HR/Admin mở lại bằng lý do có nhật ký.
- Sửa công ghi lại dữ liệu trước/sau và người duyệt. Có thể gửi đơn sửa tiếp khi đơn cũ đã xử lý.
- Chưa gồm tính lương, quỹ phép tích lũy, nhiều ca trong một ngày, email/SMS, GPS/IP/QR hoặc máy chấm công phần cứng.

## 5. Phần nhận diện kế thừa nhánh khang

Không viết lại bộ nhận diện bằng cách giả tên hay lấy ID nhân viên do trình duyệt gửi:

| File nguồn giữ nguyên | Cách dùng trong web |
|---|---|
| `core.py` — `normalize`, `match` | Import trực tiếp chuẩn hóa 512 chiều, trung bình 2 mẫu khớp nhất, ngưỡng cosine, chênh lệch với người thứ hai, ít nhất 5 mẫu |
| `camera.py` — `create_engine` | Import trực tiếp để tạo InsightFace buffalo_l CPU và giới hạn luồng ONNX |
| `regions.py` — `extract_regions` | Lưu thêm đặc trưng vùng cùng mẫu; web V1 chưa dùng vùng làm điều kiện phê duyệt công |
| `region_match.py` | Đọc/kiểm tra định dạng vùng khi chuyển dữ liệu cũ |
| `tracking.py`, `app.py` | Giữ nguyên cho desktop; web chấm từng người nên không dùng optical-flow nhiều mặt |

`face_service.py` tiếp nhận ảnh camera, kiểm tra đúng một khuôn mặt, kích thước, độ nét, sau đó **server tự trích xuất vector**. MongoDB lưu vector và mã nhân viên; không lưu ảnh/video gốc.

1. Đăng nhập `hr` hoặc `admin` → Hồ sơ khuôn mặt → chọn đúng nhân viên → Đăng ký.
2. Xác nhận nhân viên đồng ý → mở camera. Nhìn thẳng và đổi góc nhẹ; hệ thống tự lấy mẫu khác nhau, bỏ mẫu gần trùng, dừng ở 20 mẫu. Tối thiểu 5, tối đa 60 mẫu.
3. Đăng nhập tài khoản của nhân viên → Chấm công → Vào/Ra ca bằng khuôn mặt.
4. Ba ảnh mới liên tiếp phải khớp **chính tài khoản đang đăng nhập**; API mới ghi công. Không cho dùng tài khoản A để chấm bằng mặt B.
5. HR có thể xóa mẫu bằng lý do; có nhật ký xóa.

Ngưỡng kế thừa nhánh hiện tại: `FACE_THRESHOLD=0.50`, `FACE_MARGIN=0.08`. Cosine **không phải xác suất chính xác**. Nếu muốn thử 0.90, thay biến môi trường và khởi động lại, nhưng cần đánh giá tỷ lệ từ chối người đúng trên camera thực tế. Không tự áp dụng ngưỡng từ lịch sử trò chuyện thay cho cấu hình hiện có của nhánh.

Chưa có liveness/anti-spoofing; 3 ảnh khác nhau không chứng minh người thật và không chống được video phát lại. Chưa kiểm định camera thật, khuôn mặt che một phần hoặc sinh trắc của nhân viên. Không coi bản này là hệ thống chống gian lận hoàn chỉnh. Quyền dùng trọng số buffalo_l cần kiểm tra trước khi dùng thương mại; README nguồn nêu trọng số có sẵn giới hạn nghiên cứu phi thương mại.

Trình duyệt chỉ cho camera ở **localhost hoặc HTTPS**. Mở bằng IP LAN qua HTTP có thể không truy cập camera.

## 6. Chuyển mẫu SQLite cũ sang MongoDB (tùy chọn)

Không tự đoán ghép người chỉ qua họ tên. Tạo nhân viên trên web trước, sau đó tạo CSV theo `scripts/face-mapping.example.csv`:

```csv
person_id,employee_code
ID_NGUOI_TRONG_BANG_people,NV004
```

Từ thư mục `web/backend`, chạy kiểm tra không ghi dữ liệu:

```powershell
.\.venv\Scripts\python.exe ..\scripts\import_faces.py --sqlite D:\FaceCam\data\faces.db --mapping D:\FaceCam\mapping.csv
```

Sau khi kiểm tra đúng mã và có sự đồng ý của nhân viên:

```powershell
.\.venv\Scripts\python.exe ..\scripts\import_faces.py --sqlite D:\FaceCam\data\faces.db --mapping D:\FaceCam\mapping.csv --apply --consent-confirmed
```

Chỉ nhận mẫu `buffalo_l` 512 chiều, bỏ gần trùng, giới hạn 60. Không sửa SQLite, không ghi đè hồ sơ đã có trên web. Sao lưu trước và dừng thao tác đăng ký trong lúc import. Nếu import bị gián đoạn, kiểm tra hồ sơ đã tạo trước khi chạy lại; script cố tình dừng khi gặp hồ sơ trùng.

## 7. Cấu trúc mã nguồn

```text
repo/
  app.py, camera.py, core.py, regions.py, region_match.py, tracking.py
  web/
    compose.yaml
    .env.example
    start-docker.bat
    backend/
      app/
        main.py                 FastAPI, CORS, xử lý lỗi
        config.py               Biến môi trường
        database.py             MongoDB, indexes, UUID
        security.py             Session, CSRF, scrypt, phân quyền
        schemas.py              Kiểm tra dữ liệu đầu vào
        calculations.py         Tính giờ ca và công (hàm thuần)
        services.py             Phạm vi dữ liệu, bảng công, vào/ra
        routes_auth.py          Đăng nhập, đổi mật khẩu, đăng xuất
        routes_catalog.py       Nhân viên, phòng, ca, lịch, ngày lễ
        routes_attendance.py    Đơn từ, phê duyệt, báo cáo, Excel
        face_service.py         Adapter model/thuật toán từ repo gốc
        routes_face.py          Đăng ký, xóa mẫu, xác minh và ghi công
        seed.py                 Dữ liệu demo
      tests/                    Kiểm thử API và nghiệp vụ
    frontend/
      app/                      Next.js App Router, layout, CSS
      components/               Giao diện, biểu mẫu, camera
      lib/api.ts                Gọi API và định dạng dữ liệu
    scripts/
      create_admin.py           Tạo Admin cho database trống
      import_faces.py           Chuyển mẫu cũ có mapping rõ ràng
```

Collections: `users`, `departments`, `shifts`, `assignments`, `attendance`, `requests`, `holidays`, `months`, `sessions`, `rate_limits`, `face_profiles`, `face_attempts`, `audit`.

Luồng: **trình duyệt → Next.js `/api` proxy → FastAPI kiểm tra session/quyền/CSRF → nghiệp vụ → MongoDB → trả JSON → giao diện cập nhật**.

## 8. API và kiểm thử

Swagger: http://localhost:8000/docs. API gốc `/api`. Đăng nhập `POST /api/auth/login`; cookie được trình duyệt giữ. Các thao tác ghi tiếp theo cần header `X-CSRF-Token` lấy từ JSON login hoặc `/auth/me`. Giao diện web tự xử lý. Có thể dùng tab Network để xem request/response.

```powershell
# Backend, tại web/backend
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest tests -q

# Frontend, tại web/frontend
npm run typecheck
npm run build
npm start
```

Kiểm thử backend dùng **mongomock** (MongoDB giả lập), có kiểm tra đăng nhập/CSRF, phạm vi phòng, ngăn leo quyền, khóa tài khoản, snapshot ca, phân ca trùng, chấm công, duyệt đơn, bổ sung công, chốt/mở tháng, file Excel và luồng xác nhận khuôn mặt bằng vector mô phỏng. Không dùng mock trong mã chạy ứng dụng. `app/database.py` luôn dùng PyMongo thật.

Kết quả kiểm thử và giới hạn cụ thể khi bàn giao được ghi trong `VERIFICATION.md`.

## 9. Trước khi vận hành nhiều người thật

Đây là bản V1 để chạy thử và mở rộng, chưa phải một dịch vụ đã triển khai sản xuất:

- Chạy **một process API / một Uvicorn worker**. Các thao tác nhiều collection dùng khóa trong process để tránh ghi đồng thời với chốt tháng. Chưa có MongoDB transaction/khôi phục đa-document khi tiến trình chết giữa thao tác; không scale nhiều worker/replica API nếu chưa thay bằng transaction trên replica set và cơ chế đồng bộ thích hợp.
- Dùng database riêng, tắt `SEED_DEMO`, cấp tài khoản thực, đổi mật khẩu mẫu; không đưa `.env`, `data/`, mẫu mặt lên Git.
- Cấp MongoDB user riêng với quyền trên database ứng dụng khi triển khai thật; tài khoản root trong Compose chỉ nhằm đơn giản hóa local demo.
- Đặt HTTPS, `COOKIE_SECURE=true`, cấu hình đúng `ALLOWED_ORIGINS`, sao lưu MongoDB và giới hạn quyền truy cập vector khuôn mặt.
- Dữ liệu không có mã hóa ở tầng ứng dụng. Áp dụng mã hóa ổ đĩa/backup và chính sách lưu/xóa phù hợp trước khi lưu sinh trắc thật.
- Bộ lọc và báo cáo V1 tải dữ liệu tháng trong phạm vi của người dùng; chưa tối ưu/phân trang cho doanh nghiệp rất lớn.
- HR cần thống nhất quy định nghỉ phép, tăng ca, cách tính công trước khi dùng để trả lương. Chưa tính lương hoặc hệ số tăng ca/ngày lễ.

Tạo Admin khi `SEED_DEMO=false`, database trống: chạy `python ../scripts/create_admin.py` từ `backend` trong venv. Script hỏi mật khẩu không hiển thị; không ghi đè tài khoản Admin đã có.

Tài liệu chính thức tham khảo: https://nextjs.org/docs/app/getting-started/installation ; https://fastapi.tiangolo.com/advanced/response-cookies/ ; https://www.mongodb.com/docs/languages/python/pymongo-driver/current/ .
