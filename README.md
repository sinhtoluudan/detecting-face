# 🔍 Tìm kiếm và nhận diện khuôn mặt có che/đeo khẩu trang

## 📌 Giới thiệu

Đây là hệ thống **tìm kiếm và nhận diện khuôn mặt** từ hình ảnh hoặc camera.

Hệ thống có khả năng:

* 📷 Phát hiện khuôn mặt trong hình ảnh/video.
* 🧑 Nhận diện người dựa trên khuôn mặt đã đăng ký.
* 😷 Phát hiện khuôn mặt có **đeo khẩu trang** hay không.
* 🕶️ Phát hiện khuôn mặt bị **che một phần**.
* 🔎 Tìm kiếm người tương ứng trong cơ sở dữ liệu khuôn mặt.
* 📊 Hiển thị kết quả nhận diện và trạng thái khuôn mặt.

---

## 🎯 Mục tiêu

Xây dựng một hệ thống có thể:

```text
Ảnh / Camera
     │
     ▼
Phát hiện khuôn mặt
     │
     ▼
Kiểm tra khuôn mặt có bị che không
     │
     ├── Không bị che ──► Nhận diện khuôn mặt
     │
     └── Bị che / khẩu trang
                 │
                 ▼
          Xử lý nhận diện
                 │
                 ▼
          Tìm kiếm trong Database
                 │
                 ▼
             Hiển thị kết quả
```

---

## ⚙️ Chức năng chính

### 1. Phát hiện khuôn mặt

Hệ thống xác định vị trí khuôn mặt trong ảnh hoặc video.

Kết quả có thể được hiển thị bằng bounding box:

```text
┌─────────────────────────────┐
│                             │
│       ┌───────────┐         │
│       │   FACE    │         │
│       │           │         │
│       └───────────┘         │
│                             │
└─────────────────────────────┘
```

---

### 2. Nhận diện khuôn mặt

Sau khi phát hiện khuôn mặt, hệ thống trích xuất đặc trưng khuôn mặt và so sánh với dữ liệu đã đăng ký.

Ví dụ:

```text
Input
  ↓
Face Detection
  ↓
Face Embedding
  ↓
So sánh với Database
  ↓
Người phù hợp
```

Kết quả:

```text
Name: Nguyen Van A
Confidence: 92%
Status: Recognized
```

---

### 3. Phát hiện đeo khẩu trang

Hệ thống kiểm tra khuôn mặt có bị khẩu trang che phần mũi và miệng hay không.

Ví dụ:

```text
┌─────────────────┐
│      FACE       │
│                 │
│      👀 👀      │
│                 │
│    😷 MASK      │
└─────────────────┘
```

Kết quả:

```text
Mask: YES
```

hoặc:

```text
Mask: NO
```

---

### 4. Phát hiện khuôn mặt bị che

Ngoài khẩu trang, hệ thống có thể xác định khuôn mặt bị che một phần bởi:

* Khẩu trang
* Tay
* Điện thoại
* Kính
* Vật thể khác
* Góc quay làm mất một phần khuôn mặt

Ví dụ:

```text
Face
 ├── Full Face
 ├── Masked Face
 └── Occluded Face
```

---

## 🏗️ Kiến trúc hệ thống

```text
                 ┌─────────────────┐
                 │   Image/Camera  │
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │ Face Detection  │
                 └────────┬────────┘
                          │
                          ▼
                ┌───────────────────┐
                │ Occlusion / Mask  │
                │     Detection     │
                └─────────┬─────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │ Face Recognition│
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │ Face Embedding  │
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │ Face Database   │
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │ Search / Result │
                 └─────────────────┘
```

---

## 🧰 Công nghệ sử dụng

Tùy theo implementation, project có thể sử dụng:

| Thành phần       | Công nghệ                       |
| ---------------- | ------------------------------- |
| Ngôn ngữ         | Python                          |
| Computer Vision  | OpenCV                          |
| Face Detection   | YOLO / MTCNN / RetinaFace       |
| Face Recognition | FaceNet / ArcFace / InsightFace |
| Mask Detection   | YOLO / CNN                      |
| Backend          | FastAPI / Flask                 |
| Database         | MongoDB / PostgreSQL            |
| Frontend         | React / Next.js                 |
| Vector Search    | FAISS / ChromaDB                |

---

## 📂 Cấu trúc thư mục

```text
face-recognition/
│
├── dataset/
│   ├── person_01/
│   ├── person_02/
│   └── person_03/
│
├── models/
│   ├── face_detection/
│   ├── face_recognition/
│   └── mask_detection/
│
├── src/
│   ├── detection/
│   │   └── face_detector.py
│   │
│   ├── recognition/
│   │   └── face_recognizer.py
│   │
│   ├── mask/
│   │   └── mask_detector.py
│   │
│   ├── search/
│   │   └── face_search.py
│   │
│   └── main.py
│
├── database/
│   └── database.py
│
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🚀 Cài đặt

### 1. Clone project

```bash
git clone <repository-url>
```

Di chuyển vào thư mục project:

```bash
cd face-recognition
```

### 2. Tạo môi trường Python

```bash
python -m venv venv
```

Windows:

```bash
venv\Scripts\activate
```

Linux/macOS:

```bash
source venv/bin/activate
```

### 3. Cài đặt thư viện

```bash
pip install -r requirements.txt
```

---

## ▶️ Chạy chương trình

Chạy chương trình:

```bash
python src/main.py
```

Nếu sử dụng camera:

```text
Camera
   ↓
Detect Face
   ↓
Detect Mask/Occlusion
   ↓
Recognize Face
   ↓
Display Result
```

---

## 🔎 Ví dụ kết quả

### Không đeo khẩu trang

```text
Person: Nguyen Van A
Face: Detected
Mask: No
Occlusion: No
Confidence: 96.5%
```

### Đeo khẩu trang

```text
Person: Nguyen Van A
Face: Detected
Mask: Yes
Occlusion: Partial
Confidence: 78.2%
```

### Không nhận diện được

```text
Person: Unknown
Face: Detected
Mask: Yes
Occlusion: Partial
Confidence: 42.1%
```

---

## 🧠 Quy trình xử lý

### Bước 1 — Input

Nhận hình ảnh từ:

* Camera
* File ảnh
* Video

### Bước 2 — Face Detection

Tìm tất cả khuôn mặt:

```text
Image
  ↓
Face Detector
  ↓
Face Bounding Box
```

### Bước 3 — Mask/Occlusion Detection

Kiểm tra phần khuôn mặt có bị che hay không.

```text
Face
 │
 ├── Mask = No
 │
 ├── Mask = Yes
 │
 └── Occluded = Yes
```

### Bước 4 — Face Recognition

Nếu có thể nhận diện, hệ thống tạo **face embedding** và tìm khuôn mặt gần nhất trong database.

```text
Face
 ↓
Embedding
 ↓
Vector Search
 ↓
Similarity
 ↓
Identity
```

### Bước 5 — Trả kết quả

Hệ thống trả về:

```json
{
    "name": "Nguyen Van A",
    "mask": true,
    "occluded": true,
    "confidence": 0.82
}
```

---

## 📊 Tiêu chí đánh giá

Hệ thống có thể được đánh giá dựa trên:

### Face Detection

* Accuracy
* Precision
* Recall
* F1-score

### Face Recognition

* Recognition Accuracy
* False Acceptance Rate (FAR)
* False Rejection Rate (FRR)

### Mask Detection

* Accuracy
* Precision
* Recall
* F1-score

---

## ⚠️ Lưu ý

Kết quả nhận diện khuôn mặt có thể bị ảnh hưởng bởi:

* Ánh sáng yếu.
* Góc nghiêng khuôn mặt.
* Khuôn mặt quá nhỏ.
* Khẩu trang che nhiều vùng khuôn mặt.
* Kính hoặc vật thể che mặt.
* Chất lượng camera.
* Dữ liệu huấn luyện không đủ đa dạng.

Vì vậy, hệ thống nên được sử dụng như một công cụ hỗ trợ và cần có ngưỡng confidence phù hợp trước khi đưa ra kết quả nhận diện.

---

## 🔐 Quyền riêng tư

Dữ liệu khuôn mặt là dữ liệu nhạy cảm. Project cần:

* Chỉ lưu dữ liệu khi có quyền sử dụng.
* Bảo vệ ảnh và face embedding.
* Không chia sẻ dữ liệu khuôn mặt trái phép.
* Có cơ chế xóa dữ liệu khi không còn cần thiết.
* Hạn chế quyền truy cập vào database.

---

## 📌 Hướng phát triển

* [ ] Nhận diện khuôn mặt realtime.
* [ ] Nhận diện nhiều người cùng lúc.
* [ ] Phát hiện khẩu trang realtime.
* [ ] Phát hiện nhiều loại che khuất.
* [ ] Tìm kiếm khuôn mặt bằng vector database.
* [ ] Xây dựng REST API.
* [ ] Xây dựng giao diện web.
* [ ] Lưu lịch sử nhận diện.
* [ ] Thống kê kết quả nhận diện.
* [ ] Tối ưu tốc độ xử lý.

---

## 👨‍💻 Author

**Face Recognition & Mask/Occlusion Detection Project**

> Hệ thống được xây dựng nhằm nghiên cứu và ứng dụng Computer Vision trong bài toán phát hiện, tìm kiếm và nhận diện khuôn mặt trong điều kiện khuôn mặt có thể bị che khuất hoặc đeo khẩu trang.
# detecting-face
