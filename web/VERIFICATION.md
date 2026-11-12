# Kiểm chứng bản bàn giao — 29/10/2026

## Đã chạy

- `python -m pytest web/backend/tests -q`: **27 passed**. FastAPI TestClient sử dụng `mongomock`, không kết nối MongoDB thật. Một cảnh báo deprecation từ Starlette/httpx, không ảnh hưởng kết quả bài test.
- `python -m unittest discover -s tests -v` tại repo gốc: **29 tests, OK**. Đây là bài test logic/camera mô phỏng vốn có trong nhánh khang.
- `npm run build` tại `web/frontend`: thành công, gồm biên dịch Next.js và kiểm tra TypeScript.
- Kiểm tra cú pháp Python các module API và script bằng `compileall`: thành công.
- Parse Compose YAML, kiểm tra build context, Dockerfile và file nguồn: hợp lệ.
- So sánh byte với commit gốc: giữ nguyên `app.py`, `camera.py`, `core.py`, `regions.py`, `region_match.py`, `tracking.py`, `config.json`, `requirements.txt`.

Các bài test mới bao gồm phân quyền theo phòng ban, CSRF, giới hạn đăng nhập, chặn HR nâng quyền, khóa tài khoản và thu hồi phiên, kiểm tra ca qua đêm/trùng giờ, giữ snapshot ca, vào/ra trùng, đơn từ và không tự duyệt, sửa công có audit, chốt/mở tháng, chặn chốt khi còn đơn/thiếu công, tính giờ nghỉ/tăng ca, Excel thật và chống công thức từ tên nhân viên, đối chiếu vector gốc và xác nhận 3 ảnh.

## Chưa xác minh end-to-end trong môi trường bàn giao

- Môi trường hiện tại không khởi động được MongoDB thật (`mongod` báo `open: Operation not permitted`), không có Docker daemon để chạy toàn bộ Compose. Các test không chứng minh transaction/network/auth của một MongoDB triển khai thật.
- Bản preview được mở bằng trình duyệt nhưng chỉ quan sát được màn hình tải; chưa hoàn tất kiểm thử thao tác giao diện. Không coi screenshot/loading là xác nhận luồng web đã chạy hết. Cần smoke test trên localhost với FastAPI và MongoDB thực.
- Chưa tải và chạy inference buffalo_l với ảnh người thật; chưa kiểm thử camera laptop/điện thoại hoặc độ chính xác sinh trắc. Luồng Face API được test với vector và ảnh đầu vào mô phỏng.
- Chưa chạy Docker build, file `.bat` trên Windows hoặc script import với database `faces.db` thực của bạn.
- Chưa đẩy thay đổi lên GitHub hoặc triển khai public.

## Smoke test trên máy của bạn

1. Chạy Docker theo README; `/api/health` phải trả `status: ok`, `database: mongodb`.
2. Đăng nhập admin → tạo phòng ban, quản lý và nhân viên → tạo ca → phân ca cho ngày hiện tại.
3. Đăng nhập nhân viên → vào ca, thử bấm lặp (phải bị chặn) → ra ca → xem bảng công cá nhân.
4. Tạo đơn nghỉ/sửa công → quản lý cùng phòng hoặc HR duyệt → xác nhận công và nhật ký.
5. Dùng tháng trước trong dữ liệu demo → xuất Excel → chốt tháng → thử chỉnh lịch/đơn (phải bị chặn) → HR mở lại bằng lý do.
6. Bật Face → HR đăng ký đúng nhân viên với sự đồng ý → đủ ít nhất 5 mẫu → nhân viên chấm bằng mặt. Thử mặt sai tài khoản, nhiều người trong ảnh và mẫu quá mờ để kiểm tra bị từ chối.
7. Khởi động lại containers → xác nhận dữ liệu vẫn tồn tại. Không xóa volumes.

Bản này chạy một process API, chưa có chống video/ảnh giả mạo; các giới hạn nghiệp vụ và vận hành chi tiết nằm trong README.
