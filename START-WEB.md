# Chạy FaceCam

Thư mục gốc chứa ứng dụng desktop. Thư mục web chứa giao diện Next.js, API FastAPI và cấu hình MongoDB.

1. Chạy install_windows.bat ở thư mục gốc để tạo môi trường Python.
2. Trong thư mục web, sao chép .env.example thành .env và thiết lập mật khẩu.
3. Mở Docker Desktop. Từ PowerShell trong thư mục web, chạy:

    .\desktop\Bat-may-cham-cong.ps1 -CaiDat

4. Mở http://localhost:3000. Đăng ký khuôn mặt cho nhân viên trong Hồ sơ khuôn mặt.
5. Những lần sau, mở máy chấm công chung bằng .\desktop\Bat-may-cham-cong.ps1 trong thư mục web.

Để mở bản desktop độc lập dùng SQLite, chạy run_windows.bat ở thư mục gốc.
