"""Inference lives in a worker; Tk widgets are only touched on the main thread."""
import os
import queue
import threading
import time


class CameraWorker(threading.Thread):
    def __init__(self, index, config):
        super().__init__(daemon=True)
        self.index = index
        self.config = config
        self.stop_event = threading.Event()
        self.frames = queue.Queue(maxsize=1)
        self.events = queue.Queue()

    def run(self):
        cap = None
        try:
            import cv2
            from regions import extract_regions
            self.events.put(("status", "Đang mở camera…"))
            # DirectShow is usually suitable for integrated Windows webcams.
            cap = cv2.VideoCapture(self.index, cv2.CAP_DSHOW) if os.name == "nt" else cv2.VideoCapture(self.index)
            if not cap.isOpened():
                cap.release()
                cap = cv2.VideoCapture(self.index)
            if not cap.isOpened():
                raise RuntimeError("Không mở được camera. Đóng Zoom/Teams/Camera, cấp quyền camera hoặc thử chỉ số 1.")
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.events.put(("status", "Đang nạp mô hình. Lần đầu cần mạng để tải buffalo_l (~300 MB)…"))
            from insightface.app import FaceAnalysis
            engine = FaceAnalysis(name="buffalo_l", allowed_modules=["detection", "recognition"],
                                  providers=["CPUExecutionProvider"])
            engine.prepare(ctx_id=-1, det_size=(640, 640))
            self.events.put(("status", "Camera đã bật. Đưa một khuôn mặt vào khung hình."))
            failures = 0
            while not self.stop_event.is_set():
                ok, frame = cap.read()
                if not ok:
                    failures += 1
                    if failures >= 10:
                        raise RuntimeError("Camera không trả ảnh. Tắt/bật lại camera hoặc chọn chỉ số khác.")
                    self.stop_event.wait(0.1)
                    continue
                failures = 0
                # Mirror BEFORE detection so coordinates and enrollment match.
                frame = cv2.flip(frame, 1)
                started = time.monotonic()
                detected = engine.get(frame)
                faces = []
                for face in detected:
                    x1, y1, x2, y2 = [int(v) for v in face.bbox]
                    h, w = frame.shape[:2]
                    x1, y1, x2, y2 = max(0,x1), max(0,y1), min(w,x2), min(h,y2)
                    crop = frame[y1:y2, x1:x2]
                    blur = float(cv2.Laplacian(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()) if crop.size else 0
                    good = (min(x2-x1, y2-y1) >= self.config["min_face_size"]
                            and blur >= self.config["min_blur_score"] and float(face.det_score) >= 0.65)
                    faces.append({"box": (x1,y1,x2,y2), "embedding": face.normed_embedding,
                                  "good": good, "regions": extract_regions(frame, face.kps) if good else
                                  {"vectors": {}, "polygons": {}, "reason": "Mặt chưa đủ rõ", "detail_preview": None}})
                item = {"rgb": cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), "faces": faces,
                        "time": time.monotonic(), "fps": 1 / max(time.monotonic()-started, 0.001)}
                try:
                    self.frames.get_nowait()
                except queue.Empty:
                    pass
                self.frames.put_nowait(item)
        except Exception as exc:
            self.events.put(("error", f"{type(exc).__name__}: {exc}"))
        finally:
            if cap is not None:
                cap.release()
            self.events.put(("stopped", "Camera đã tắt."))
