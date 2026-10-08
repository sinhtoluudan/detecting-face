# FaceCam — nhận diện tên bằng camera laptop

## Bản cập nhật: đối chiếu mắt, chân mày, mũi và trán

Đã thêm **logic đối chiếu từng vùng** trong quyết định có hiển thị tên hay không:

| Vùng / chi tiết | Cách dùng |
| --- | --- |
| Hai vùng mắt | Lấy cửa sổ quanh điểm mắt; so sánh hướng cạnh và kết cấu quanh mắt |
| Hai vùng chân mày | Ước lượng cửa sổ phía trên mắt; so sánh hình ảnh cục bộ |
| Mũi | Lấy cửa sổ quanh điểm mũi; chỉ dùng khi bạn chọn mũi đang lộ rõ |
| Trán | Ước lượng vị trí dựa trên đường nối hai mắt; so sánh kết cấu, cạnh và đường tối |
| Chi tiết da / nếp gấp | Đặc trưng HOG + LBP mô tả hình ảnh cục bộ; không phân loại từng nét là nếp nhăn thật |

Mắt và mũi dựa trên điểm mốc từ detector. Chân mày/trán là **vùng ước lượng**,
không phải mô hình phân đoạn chính xác biên chân mày, đường tóc hoặc da trán.
Hai bên trái/phải được đặt tên theo ảnh hiển thị đã soi gương.

**Cách dùng phần mới:**

1. Bật camera, giữ mặt đủ gần và ánh sáng tốt.
2. Bật **Đối chiếu thêm từng vùng (thử nghiệm)**.
3. Trong bảng bên phải, chỉ chọn những vùng đang lộ rõ.
   Khi đeo khẩu trang, **bỏ chọn Mũi trước khi lưu mẫu và trước khi nhận diện**.
   Nếu tóc che trán hoặc tay che mắt, bỏ chọn vùng tương ứng.
4. Chọn đúng tên rồi lưu lại nhiều mẫu. Cần ít nhất 5 mẫu toàn mặt; mỗi vùng
   tham gia đối chiếu cần ít nhất 3 mẫu đã lưu có vùng đó.
5. Bấm **Bắt đầu nhận diện**. Bảng bên phải hiển thị điểm của từng vùng được dùng.
   Cuộn thanh cuộn bên phải để xem đầy đủ phần chi tiết.

Vùng màu xanh lam trên camera có đủ chất lượng ảnh để trích xuất đặc trưng;
màu xám là vùng chưa đạt kiểm tra chất lượng. Màu này **không có nghĩa vùng đó
đã được xác minh không bị che hoặc đã khớp danh tính**.

Ảnh nhỏ của trán đánh dấu màu vàng các đường tối ứng viên bằng phép lọc
**morphological black-hat**. Tóc, bóng đổ, cạnh và nhiễu cũng có thể sáng lên.
Đây là ảnh minh họa chi tiết kết cấu; **không đếm nếp nhăn, không suy đoán tuổi,
không phải bộ phát hiện nếp nhăn đã được gán nhãn/kiểm chứng**.

### Quyết định nhận diện mới

1. Đối chiếu vector toàn mặt như bản cũ để tìm ứng viên đã đạt ngưỡng và khoảng cách.
2. Nếu bật đối chiếu vùng: so sánh các vùng được chọn với mẫu vùng của chính ứng viên đó.
3. Phải có ít nhất 3 vùng hợp lệ, trong đó có ít nhất một vùng mắt.
4. Tính trung bình có trọng số điểm các vùng khả dụng; yêu cầu đạt `region_threshold`.
5. Sau đó mới xác nhận qua 3 lần xử lý liên tiếp và hiển thị tên.

Không có ứng viên toàn mặt đạt điều kiện thì **không dùng nếp nhăn/kết cấu da
để tự gán tên**. Bước mới là điều kiện kiểm tra bổ sung, có thể giảm chấp nhận
nhầm nhưng cũng có thể tăng từ chối. Nó **không cứu trường hợp mô hình toàn mặt
không nhận ra người đeo khẩu trang**. Chưa có bằng chứng bản mới chính xác hơn:
cần so sánh bật/tắt kiểm tra vùng trên dữ liệu của bạn.

Các giá trị khởi đầu trong `config.json`:

| Khóa | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `region_threshold` | 0.80 | Điểm vùng tổng hợp tối thiểu; cần hiệu chỉnh thực tế |
| `min_region_samples` | 3 | Số mẫu tham chiếu tối thiểu cho một vùng |
| `min_regions` | 3 | Số vùng cần có điểm; vẫn yêu cầu ít nhất một mắt |

Trọng số mắt: 0.25 mỗi bên; chân mày: 0.10 mỗi bên; trán: 0.15; mũi: 0.15.
Trọng số được chia lại theo tổng trọng số của các vùng thực sự được dùng;
không chia cố định cho sáu vùng khi mũi bị loại. Điểm một vùng là trung bình hai
điểm cao nhất trong các mẫu cùng vùng của ứng viên. Các trọng số/ngưỡng này là
thiết kế thử nghiệm, chưa được tối ưu trên tập đánh giá độc lập.

Các phép kiểm tra độ rõ chỉ phát hiện ảnh nhỏ, mờ, quá tối/sáng hoặc nằm ngoài
khung hình. **Không tự phát hiện khẩu trang, tóc, kính hay tay che mặt.** Bạn chọn
vùng đang lộ rõ; nếu chọn nhầm, vùng bị che vẫn có thể tham gia so sánh và gây sai.

### Nâng cấp từ bản cũ

- Đóng ứng dụng cũ và sao lưu thư mục `data` trước khi nâng cấp.
- Giải nén mã mới sang thư mục mới, chạy cài đặt, rồi sao chép `data/faces.db`
  từ thư mục cũ sang `data/faces.db` trong thư mục mới.
- Khi mở app, cột lưu mẫu vùng được thêm tự động; tên và mẫu toàn mặt cũ vẫn giữ.
- Vector toàn mặt cũ không chứa ảnh để trích xuất lại vùng. Vì vậy cần chụp thêm
  mẫu vùng cho từng người. Tạm bỏ chọn đối chiếu vùng nếu muốn dùng cách cũ.
- Không kèm dữ liệu khuôn mặt của bất kỳ người nào trong ZIP.

File mới: `regions.py` (trích xuất), `region_match.py` (điều kiện đối chiếu),
`tests/test_regions.py` (kiểm tra loại vùng che, chất lượng, dữ liệu cũ và quyết định).

---

Ứng dụng Python có cửa sổ tiếng Việt. Bật webcam, đăng ký tên và mẫu khuôn mặt,
sau đó nhìn vào camera để ứng dụng đối chiếu và hiển thị tên đã đăng ký.

Đây là bản thử nghiệm dùng mô hình có sẵn InsightFace `buffalo_l`, chạy CPU.
Có thể đăng ký thêm mẫu có khẩu trang hoặc che một phần mặt để thử nhận diện
trong các điều kiện này. **Không bảo đảm nhận diện đúng mọi kiểu che mặt**;
mô hình này không phải mô hình được tinh chỉnh riêng cho dữ liệu khẩu trang của bạn.
Khi không đạt điều kiện đối chiếu, ứng dụng hiện **Chưa xác định**.

## 1. Chạy trên Windows

1. Cài **Python 3.11 bản 64-bit** từ https://www.python.org/downloads/windows/.
   Khi cài, chọn **Add python.exe to PATH** và cài **Python Launcher**.
2. Giải nén toàn bộ thư mục, ví dụ `D:\FaceCam`. Không chạy trực tiếp trong ZIP.
3. Nhấp đúp **install_windows.bat** và chờ cài thư viện xong.
4. Nhấp đúp **run_windows.bat** để mở ứng dụng.
5. Chọn camera `0`, bấm **Bật camera**.

Lần đầu bật camera, InsightFace cần Internet để tải gói mô hình buffalo_l
khoảng 300 MB vào `%USERPROFILE%\.insightface\models\buffalo_l`.
Sau khi đã tải và cài đầy đủ, nhận diện chạy cục bộ trên máy, không cần gửi ảnh
lên dịch vụ nhận diện. Bộ ZIP không kèm trọng số mô hình.

Hoặc mở PowerShell tại thư mục dự án và chạy lần lượt:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Không cần kích hoạt venv nên không cần thay đổi Execution Policy của PowerShell.

## 2. Đăng ký tên lần đầu

1. Bật camera và chờ hình xuất hiện.
2. Bấm **1. Thêm người / nhập tên**, nhập ví dụ **Đăng Khang**.
3. Chọn đúng tên trong danh sách. Chỉ để đúng người đó trước camera.
4. Bấm **2. Lưu một mẫu khuôn mặt**. Mỗi lần bấm lưu một vector đặc trưng.
5. Đổi góc nhẹ, biểu cảm hoặc khoảng cách rồi lưu thêm.
6. Đeo khẩu trang thật, vẫn chọn tên đó và tiếp tục lưu thêm mẫu.
7. Làm tương tự cho người khác nếu cần.

Ứng dụng yêu cầu ít nhất **5 mẫu/người** trước khi đối chiếu. Để thử nghiêm túc,
nên thu **20–40 mẫu đa dạng/người**, bao gồm khoảng 10–20 mẫu không che và
10–20 mẫu có khẩu trang/kiểu che cần thử. Đây là hướng dẫn thu dữ liệu ban đầu,
không phải số lượng bảo đảm độ chính xác. Tối đa 60 mẫu/người.

Ảnh quá nhỏ, quá mờ, không thấy mặt hoặc có nhiều người sẽ không được lưu.
Mẫu gần như giống hệt mẫu cũ cũng được từ chối. Nếu nhiều ảnh khác góc nhưng
vẫn quá giống, thay đổi biểu cảm, ánh sáng hoặc khoảng cách; không cần tạo ảnh mờ.

**Lưu mẫu chỉ bổ sung dữ liệu đối chiếu, không huấn luyện lại mô hình.**
Ứng dụng không tự xác minh bạn đã chọn đúng tên khi đăng ký; việc gắn tên đúng
là trách nhiệm người thao tác. Không trộn mẫu của hai người trong cùng hồ sơ.

## 3. Nhận diện qua webcam

1. Bật camera.
2. Bấm **Bắt đầu nhận diện**.
3. Nhìn vào camera; chỉ để một người trong khung hình.
4. Thử không che, đeo khẩu trang rồi thử che một phần mặt.

Kết quả:

| Hiển thị | Ý nghĩa |
| --- | --- |
| Tên màu xanh | Đạt ngưỡng, đủ khoảng cách với ứng viên thứ hai và ổn định 3 lần xử lý liên tiếp |
| Đang xác nhận | Có ứng viên phù hợp nhưng chưa đủ số lần xác nhận |
| Chưa xác định | Không có ứng viên đạt điều kiện |
| Mặt chưa đủ rõ | Tiến gần camera, giữ yên hoặc tăng ánh sáng |
| Chỉ để một người… | Bản demo cố ý chỉ xử lý tình huống soi mặt một người |

Tên gắn với kết quả đối chiếu hiện tại, không phải bằng chứng danh tính chắc chắn.
Khi bật tính năng vùng, tên màu xanh còn cần vượt qua điều kiện vùng ở phần đầu.
Điểm hiển thị là **cosine similarity**, không phải phần trăm xác suất đúng.
Ba lần xác nhận giúp bớt nhấp nháy, không phải ba bằng chứng độc lập.

Bấm **Dừng nhận diện** để chỉ xem camera, hoặc **Tắt camera** để nhả webcam.
Bạn có thể bổ sung mẫu sau này bằng cách chọn hồ sơ cũ; không cần tạo lại người.

## 4. Ngưỡng và giới hạn khẩu trang

Mặc định dùng ngưỡng `0.50`, chênh lệch với người đứng thứ hai ít nhất `0.08`,
và cần 3 kết quả liên tiếp. Các giá trị này là **giá trị khởi đầu chưa hiệu chỉnh
trên camera/dữ liệu của bạn**, không phải ngưỡng chuẩn được chứng minh.

Điểm mỗi người là trung bình hai điểm tương đồng cao nhất từ các mẫu của họ.
Hồ sơ dưới 5 mẫu không tham gia đối chiếu. Nếu chỉ có một hồ sơ, không có ứng viên
thứ hai để so sánh; kiểm tra với người chưa đăng ký càng quan trọng.

- Ngưỡng cao hơn thường giảm nhận nhầm nhưng dễ từ chối người đã đăng ký.
- Ngưỡng thấp hơn dễ nhận ra hơn nhưng cũng dễ gán nhầm tên cho người lạ.
- Đừng giảm ngưỡng chỉ để khẩu trang luôn hiện tên. Trước hết thu mẫu tốt và
  đánh giá người lạ. Khi mô hình không đủ tốt, cần thay mô hình/tinh chỉnh,
  không thể khắc phục chỉ bằng giao diện.
- Thay ngưỡng trên cửa sổ rồi dừng/bắt đầu nhận diện để áp dụng.
- Cấu hình mặc định cho lần mở sau nằm trong `config.json`; sửa khi đã đóng app.

Không có cơ chế phát hiện giả mạo bằng ảnh/video. Không dùng bản thử nghiệm này
để tự động mở khóa, phê duyệt truy cập hoặc ra quyết định quan trọng.

## 5. Kiểm tra kết quả đúng cách

Thu ảnh/mẫu đăng ký ở buổi A; thử webcam ở buổi B với ánh sáng/góc khác.
Không đánh giá bằng chính các khung hình đã lưu. Thử cả người chưa đăng ký.

Ghi lại mỗi lần thử trong bảng:

| Người thực | Đã đăng ký? | Điều kiện | Tên ứng dụng trả về | Đúng / sai / chưa xác định |
| --- | --- | --- | --- | --- |
| Khang | Có | Không che | | |
| Khang | Có | Khẩu trang | | |
| Khang | Có | Che một phần má | | |
| Người thử khác | Không | Không che | | |
| Người thử khác | Không | Khẩu trang | | |

Báo cáo riêng theo từng điều kiện: tỷ lệ nhận đúng người đã đăng ký, tỷ lệ gán
nhầm tên, tỷ lệ từ chối người đã đăng ký và tỷ lệ người lạ bị gán tên.
Nếu dùng một tập để chọn ngưỡng, hãy giữ một tập thử khác để báo cáo cuối cùng.

## 6. Xử lý lỗi

**Không mở được camera:** đóng ứng dụng Windows Camera, Zoom, Teams hoặc tab web
đang dùng cam. Trong Windows Settings, tìm *Camera privacy settings*, bật quyền
camera cho ứng dụng desktop. Thử chỉ số `1` rồi bấm bật camera.

**Có đèn camera nhưng chưa có hình:** lần đầu đang tải/nạp mô hình; đọc trạng thái
dưới cửa sổ và chờ. Nếu bị lỗi tải, kiểm tra mạng và chạy lại. Tải gián đoạn có thể
để lại gói chưa hoàn chỉnh; đổi tên thư mục `buffalo_l` chưa hoàn chỉnh rồi thử lại.

**`py` không được nhận diện / không có Python 3.11:** cài Python 3.11 64-bit với
Python Launcher. Kiểm tra `py -0p`. Nếu Python 3.11 đã có nhưng không có Launcher,
có thể thay `py -3.11` bằng đường dẫn đầy đủ tới `python.exe` của Python 3.11.

**Không tìm thấy phiên bản InsightFace:** requirements cố định phiên bản 2.1,
đã đối chiếu là có trên PyPI. Nâng cấp pip và kiểm tra kết nối tới kho gói.
Nếu dùng mirror nội bộ, mirror có thể chưa cập nhật. Không tự hạ phiên bản:
bản cũ có yêu cầu biên dịch khác trên Windows.

**`ModuleNotFoundError`:** chạy lại `install_windows.bat` và đọc lỗi đầu tiên;
luôn chạy bằng `run_windows.bat` để dùng đúng môi trường.

**Ảnh giật/chậm:** bản mặc định dùng CPU, tốc độ phụ thuộc máy. Tắt ứng dụng nặng,
giữ một người trong hình, dùng nguồn điện ổn định. Không cam kết FPS.

**Không nhận ra khi che nhiều:** có thể detector không tìm thấy mặt, mẫu không đủ
đa dạng hoặc mô hình không phân biệt được. Giữ vùng mắt rõ, tăng ánh sáng,
thu thêm mẫu cùng điều kiện và thử lại; chấp nhận “Chưa xác định” khi thiếu dữ liệu.

## 7. Dữ liệu và cấu trúc

Chỉ đăng ký người đồng ý tham gia. Ảnh camera được xử lý trong bộ nhớ;
ứng dụng không ghi video và không lưu ảnh gốc. Tên và vector khuôn mặt được lưu
cục bộ trong `data/faces.db`. Vector vẫn là dữ liệu sinh trắc học, không phải
dữ liệu vô danh; file hiện không được mã hóa. Không chia sẻ file này tùy tiện.
Nút **Xóa người đang chọn** xóa hồ sơ cùng các mẫu của người đó trong cơ sở dữ liệu;
đây không phải thao tác xóa an toàn mọi dấu vết trên ổ đĩa hoặc các bản sao lưu.

| File | Nội dung |
| --- | --- |
| `app.py` | Giao diện Tkinter, đăng ký, quản lý, điều phối kết quả |
| `camera.py` | Worker mở webcam, chạy detector và trích xuất đặc trưng |
| `core.py` | SQLite, chuẩn hóa vector, đối chiếu, xác nhận nhiều khung hình |
| `regions.py` | Căn chỉnh theo mắt, vùng ước lượng, HOG/LBP và ảnh chi tiết trán |
| `region_match.py` | Đối chiếu từng vùng, loại vùng không được chọn và kiểm tra bổ sung |
| `config.json` | Các ngưỡng và camera mặc định |
| `requirements.txt` | Thư viện cần cài |
| `install_windows.bat` | Cài môi trường Windows |
| `run_windows.bat` | Mở ứng dụng |
| `tests/test_core.py` | Kiểm tra logic đối chiếu và lưu/xóa dữ liệu |
| `tests/test_regions.py` | Kiểm tra đặc trưng vùng, xử lý che khuất giả lập và nâng cấp dữ liệu |

## 8. Kiểm chứng và nguồn

Chạy kiểm tra logic:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Các kiểm tra bằng vector tổng hợp chỉ xác minh logic; **không đo độ chính xác
nhận diện người thật hoặc khẩu trang**. Môi trường tạo bộ mã không kết nối được
camera laptop của bạn; cần cài và thử trực tiếp trên máy. Không có báo cáo benchmark
hoặc tuyên bố đã kiểm thử camera thực tế kèm theo bộ mã này.

- InsightFace Python / API / giấy phép:
  https://github.com/deepinsight/insightface/blob/master/python-package/README.md
- Model zoo:
  https://github.com/deepinsight/insightface/blob/master/python-package/docs/model_zoo.md
- NIST Face Mask Effects:
  https://pages.nist.gov/frvt/html/frvt_facemask.html
- LBP cho phân loại kết cấu — tài liệu scikit-image:
  https://scikit-image.org/docs/stable/auto_examples/features_detection/plot_local_binary_pattern.html
- Tham khảo căn chỉnh khuôn mặt trong InsightFace:
  https://github.com/deepinsight/insightface/blob/master/python-package/insightface/utils/face_align.py

Các nguồn trên giải thích công cụ/phương pháp, không chứng minh hiệu quả của
phép kết hợp HOG/LBP với nhận diện toàn mặt trong ứng dụng này.

Mã thư viện InsightFace có giấy phép MIT; trọng số có sẵn được nhà cung cấp giới
hạn cho nghiên cứu phi thương mại. Bộ ZIP này không kèm hay cấp lại giấy phép
trọng số. Kiểm tra giấy phép trước khi dùng ngoài phạm vi đồ án/nghiên cứu.
