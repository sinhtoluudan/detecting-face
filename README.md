# FaceCam — nhiều khuôn mặt, khung và tên trên camera chính

Ứng dụng Python/Tkinter nhận diện những người đã đăng ký qua webcam laptop hoặc
camera điện thoại được Windows nhận như webcam. Dùng InsightFace `buffalo_l`
trên CPU, OpenCV, ONNX Runtime, NumPy, Pillow và SQLite.

## Bản cập nhật hiện tại

- Một khung camera chính; đã bỏ bảng tên lớn, dòng “đang xác nhận” đổi liên tục
  và ảnh AI phụ. Không hiển thị điểm số thay đổi trên nhãn tên.
- Mỗi khuôn mặt có một khung và tên riêng ngay trên khung.
- Mặc định phân tích tối đa **5 khuôn mặt** mỗi lượt; tăng số người làm AI chậm hơn.
- Theo dõi chuyển động giữa các lần AI bằng optical flow; đối chiếu vị trí và
  đặc trưng mặt để không phụ thuộc thứ tự detector trả về.
- Mỗi người có bộ xác nhận riêng. Tên được xác nhận sau 3 kết quả phù hợp;
  sau đó giữ ngắn hạn nếu AI tạm không nhận ra, để bớt chớp.
- Kết quả mâu thuẫn, liên kết mơ hồ, mất dấu hoặc hết hạn sẽ xóa tên cũ.
  Không giữ một tên vô thời hạn khi người đó rời camera.
- Camera và AI vẫn chạy trên luồng riêng, chỉ giữ khung hình mới nhất.
- Mẫu dữ liệu cũ vẫn dùng được. Không đổi mô hình hoặc hạ ngưỡng để tăng tốc.

Đây là bản thử nghiệm. Không bảo đảm khung/tên luôn chính xác khi người đi
chéo nhau, di chuyển nhanh, mặt quá nhỏ, bị che nhiều hoặc AI quá chậm. Optical
flow theo dõi điểm ảnh, không tự chứng minh danh tính. Tên có độ trễ so với camera
và có thể được giữ tối đa khoảng thời gian cấu hình sau lần khớp gần nhất.

## 1. Cập nhật bản đang chạy

1. Đóng ứng dụng và sao lưu thư mục dự án.
2. Chép **app.py, camera.py, tracking.py, config.json** trong ZIP mới vào `D:\FaceCam`.
   `tracking.py` là file mới, không được bỏ sót.
3. Giữ nguyên `.venv/` và `data/`; không cần cài lại thư viện hoặc đăng ký lại mẫu.
4. Trong PowerShell tại thư mục dự án, chạy:

```powershell
.\run_windows.bat
```

Nếu bạn đã sửa cấu hình riêng, có thể giữ các giá trị cũ và bổ sung các khóa mới
trong bảng cấu hình dưới đây thay vì chép đè `config.json`.

## 2. Cài lần đầu trên Windows

Cần Python 3.11 64-bit và Python Launcher/Install Manager. Nếu máy dùng trình
quản lý Python mới và báo chưa có 3.11, chạy `py install 3.11` rồi kiểm tra:

```powershell
py -3.11 --version
```

Giải nén toàn bộ ZIP, mở PowerShell trong thư mục có `app.py` rồi chạy:

```powershell
.\install_windows.bat
```

Chờ `Installation complete`, sau đó:

```powershell
.\run_windows.bat
```

Nhấp đúp file trong VS Code chỉ mở nội dung. Không dán nội dung `.bat` vào
PowerShell; hãy chạy tên file với tiền tố `.\` như trên.

Lần đầu bật camera cần mạng để tải `buffalo_l` (~300 MB) vào
`%USERPROFILE%\.insightface\models\buffalo_l`. ZIP không kèm trọng số.
Sau khi tải và cài xong, ảnh được xử lý tại máy, không gửi tới API nhận diện.

## 3. Đăng ký từng người

1. Bật camera, chọn đúng chỉ số thiết bị (thường 0 hoặc 1).
2. Bấm **Thêm người / nhập tên**.
3. Chọn đúng tên. **Chỉ để một người trước camera khi lưu mẫu.**
4. Bấm **Lưu một mẫu khuôn mặt**; thay đổi góc nhẹ rồi lưu tiếp.
5. Cần tối thiểu 5 mẫu toàn mặt/người. Nên thử với 20–40 mẫu đa dạng,
   không che, có khẩu trang, nhiều góc và ánh sáng phù hợp. Đây không phải số
   mẫu bảo đảm độ chính xác.
6. Đưa người tiếp theo vào và đăng ký bằng hồ sơ khác.

Có từ hai khuôn mặt trở lên thì nút lưu mẫu sẽ từ chối, để tránh gắn nhầm tên.
Mẫu lưu là đặc trưng của khung hình AI mới phân tích (không quá 3 giây theo
mặc định); hãy giữ đúng người trước camera và chờ AI cập nhật trước khi lưu.
Lưu mẫu là thêm dữ liệu tham chiếu, **không huấn luyện lại mô hình**.

## 4. Nhận diện nhiều người

Bấm **Bắt đầu nhận diện**, sau đó nhiều người có thể đứng trong hình.

| Hiển thị trên khung | Ý nghĩa |
| --- | --- |
| Tên màu xanh | Danh tính đã đạt điều kiện và đủ lần xác nhận trên luồng theo dõi đó |
| Chưa xác định, màu vàng | Chưa có kết quả đủ chắc chắn hoặc chưa xác nhận đủ lần |
| Khuôn mặt | Chưa bật chế độ nhận diện danh tính |
| Khung biến mất | Mất dấu, chuyển động không đáng tin hoặc kết quả AI đã quá cũ |

Tên không thay bằng “Đang xác nhận” mỗi khung hình. Một lần đối chiếu thất bại
ngắn hạn không lập tức xóa tên vừa xác nhận; nhưng mâu thuẫn rõ với ứng viên
khác sẽ xóa ngay để chờ xác nhận lại.

Không có tự động chống ảnh/video giả mạo. Không dùng bản demo để mở khóa hoặc
phê duyệt truy cập quan trọng. Chưa có benchmark xác nhận độ chính xác trên
camera của bạn.

## 5. Mắt, chân mày, mũi, trán và che khuất

`regions.py` căn chỉnh theo hai mắt và tính HOG/LBP cho các vùng cục bộ.
Mắt/mũi dựa trên điểm mốc detector; chân mày/trán là cửa sổ ước lượng.
HOG mô tả hướng cạnh; LBP mô tả kết cấu ảnh. **Không phải bộ đếm hoặc phân loại
nếp nhăn đã được huấn luyện/kiểm chứng.** Không phân đoạn chính xác biên trán,
đường tóc hoặc chân mày.

Bật **Đối chiếu thêm từng vùng** để kiểm tra bổ sung sau đối chiếu toàn mặt.
Cần tối thiểu 3 vùng hợp lệ, có ít nhất một mắt; mỗi vùng cần ít nhất 3 mẫu tham
chiếu. Điểm vùng là trung bình có trọng số của điểm từng vùng. Những ngưỡng này
chưa được hiệu chỉnh trên dữ liệu của bạn; có thể tăng từ chối người đúng.

Các ô vùng áp dụng **chung cho tất cả người trong camera**. Nếu nhóm có người
đeo khẩu trang, bỏ chọn Mũi cho cả nhóm. Tóc/tay che vùng nào thì bỏ vùng đó.
Chưa tự nhận biết vùng bị che theo từng người. Việc bỏ Mũi chỉ tác động kiểm tra
vùng; mô hình toàn mặt vẫn có thể giảm độ chính xác vì khẩu trang.

Không có ứng viên toàn mặt đạt điều kiện thì không gán tên chỉ dựa trên HOG/LBP.
Ảnh vùng quá mờ/tối/sáng hoặc ra ngoài ảnh bị loại, nhưng kiểm tra chất lượng
không tự phát hiện tóc, tay, kính hay khẩu trang.

## 6. Cấu hình

Sửa `config.json` khi đã đóng app. Các giá trị là điểm khởi đầu thử nghiệm.

| Khóa | Mặc định | Ý nghĩa |
| --- | --- | --- |
| camera_index | 0 | Chỉ số webcam |
| similarity_threshold | 0.50 | Ngưỡng điểm cosine toàn mặt, không phải xác suất |
| runner_up_margin | 0.08 | Chênh lệch tối thiểu với danh tính đứng thứ hai |
| confirm_frames | 3 | Số kết quả AI xác nhận liên tiếp cho từng người |
| min_face_size | 90 | Cạnh khuôn mặt tối thiểu tính theo pixel nguồn |
| min_blur_score | 35 | Ngưỡng độ nét ảnh toàn mặt |
| min_samples | 5 | Mẫu toàn mặt tối thiểu/hồ sơ |
| region_threshold | 0.80 | Ngưỡng kiểm tra vùng |
| min_region_samples | 3 | Số mẫu tham chiếu mỗi vùng |
| min_regions | 3 | Số vùng tối thiểu; vẫn cần có vùng mắt |
| preview_fps | 25 | Giới hạn gửi ảnh xem trực tiếp |
| max_analysis_fps | 5 | Giới hạn trên tần suất AI, không bảo đảm đạt |
| detection_size | 480 | Đầu vào detector, chia hết cho 32 |
| cpu_threads | 2 | Luồng ONNX Runtime cho mỗi mô hình |
| max_result_age | 3.0 | Tuổi tối đa ảnh AI được dùng, giây |
| max_faces | 5 | Số khuôn mặt tối đa detector xử lý; tối thiểu hiệu lực là 2 để chặn đăng ký nhiều người |
| track_timeout | 3.0 | Xóa luồng theo dõi nếu quá lâu không có quan sát AI mới |
| name_hold_seconds | 2.5 | Giữ tên sau lần khớp gần nhất nếu chưa có mâu thuẫn/mất dấu |

Không tăng thời gian giữ tên quá cao chỉ để hết nhấp nháy: có thể giữ tên sai
khi người khác vào vị trí cũ. Không hạ ngưỡng chỉ để mọi người đều hiện tên.

## 7. Nếu chậm hoặc lỗi

- Nếu Camera FPS thấp, đóng app và thử Windows Camera để kiểm tra thiết bị,
  ánh sáng và kết nối điện thoại. Nếu Camera FPS cao nhưng AI thấp, mô hình là
  phần chậm; nhiều người cần nhiều lượt trích xuất đặc trưng hơn.
- Giảm `max_faces` nếu máy yếu. Đưa người gần camera để mặt đủ lớn.
- Nếu không mở camera: đóng Zoom/Teams/Windows Camera, kiểm tra quyền camera
  cho ứng dụng desktop và thử chỉ số khác.
- Nếu chưa có tên: kiểm tra đủ mẫu, đã bấm Bắt đầu nhận diện, vùng đang chọn,
  ánh sáng và khoảng cách. Đăng ký người lạ mới nếu họ chưa có hồ sơ.
- Nếu báo thiếu `tracking`: chưa chép `tracking.py` vào cùng thư mục `app.py`.
- Nếu báo thiếu thư viện: chạy lại `install_windows.bat`, đọc lỗi đầu tiên;
  luôn mở bằng `run_windows.bat` để dùng đúng môi trường.
- Mất dấu trong chuyển động nhanh/che nhiều có thể làm khung biến mất để tránh
  gắn nhầm; giữ mặt rõ và chờ AI xác nhận lại.

## 8. File và dữ liệu

| File | Vai trò |
| --- | --- |
| app.py | Một giao diện camera, quản lý người, đối chiếu từng mặt, vẽ khung và tên |
| camera.py | Luồng đọc webcam và luồng AI độc lập; phân tích nhiều mặt |
| tracking.py | Optical flow, ghép quan sát với luồng theo dõi và ổn định tên riêng |
| core.py | SQLite, chuẩn hóa vector toàn mặt và đối chiếu |
| regions.py | Trích xuất vùng, HOG/LBP và các tiện ích kết cấu da |
| region_match.py | Kiểm tra bổ sung vùng cho từng ứng viên |
| config.json | Các cấu hình |
| requirements.txt | Thư viện; không thêm thư viện cho bản nhiều mặt |
| install_windows.bat | Cài Python environment/thư viện |
| run_windows.bat | Chạy ứng dụng |
| tests/ | Các kiểm tra logic và mô phỏng camera/AI |

Tên và vector được lưu trong `data/faces.db`. Không lưu video/ảnh gốc. Vector
vẫn là dữ liệu sinh trắc học, file chưa mã hóa. Chỉ đăng ký người đồng ý tham gia;
không đưa `data` lên GitHub. Xóa hồ sơ trong app xóa các mẫu trong cơ sở dữ liệu,
không bảo đảm xóa mọi bản sao lưu hoặc dấu vết trên ổ đĩa.

## 9. Kiểm chứng và nguồn

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

29 kiểm tra logic/mô phỏng đã chạy qua khi đóng gói, gồm: hai danh tính độc lập
khi detector đảo thứ tự, theo chuyển động giả lập, giữ/xóa tên theo thời hạn,
không giữ tên bị mâu thuẫn, xử lý dữ liệu cũ và camera không chờ AI.
Không thay thế kiểm thử nhiều người thật trên Windows/camera của bạn.

Đánh giá với buổi đăng ký và buổi kiểm tra khác nhau; thử người chưa đăng ký,
khẩu trang, nhiều người vào/ra hoặc đi ngang nhau. Báo cáo riêng nhận đúng,
nhận nhầm, từ chối người đúng và đổi nhầm danh tính giữa hai người.

- InsightFace API và giấy phép: https://github.com/deepinsight/insightface/blob/master/python-package/README.md
- OpenCV tracking: https://docs.opencv.org/4.7.0/dc/d6b/group__video__track.html
- LBP: https://scikit-image.org/docs/stable/auto_examples/features_detection/plot_local_binary_pattern.html
- ONNX Runtime: https://onnxruntime.ai/docs/performance/tune-performance/threading.html

InsightFace code là MIT; trọng số có sẵn được giới hạn cho nghiên cứu phi thương
mại. ZIP không chứa trọng số và không cấp lại giấy phép của nhà cung cấp.
