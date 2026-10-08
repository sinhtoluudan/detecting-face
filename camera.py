"""Independent webcam capture and AI inference; bounded latest-only queues."""
import os
import queue
import threading
import time


def publish_latest(target, item):
    """Single producer: discard old data, never block the webcam."""
    try:
        target.get_nowait()
    except queue.Empty:
        pass
    target.put_nowait(item)


class CaptureLoop(threading.Thread):
    def __init__(self, index, config, stop_event, previews, events, capture_factory=None):
        super().__init__(daemon=True)
        self.index, self.config = index, config
        self.stop_event, self.previews, self.events = stop_event, previews, events
        self.capture_factory = capture_factory
        self.lock = threading.Lock()
        self.latest = None
        self.ready = threading.Event()

    def snapshot(self):
        with self.lock:
            return self.latest

    def run(self):
        cap = None
        try:
            import cv2
            self.events.put(("status", "Đang mở camera…"))
            if self.capture_factory is not None:
                cap = self.capture_factory(self.index)
            else:
                cap = cv2.VideoCapture(self.index, cv2.CAP_DSHOW) if os.name == "nt" else cv2.VideoCapture(self.index)
                if not cap.isOpened():
                    cap.release()
                    cap = cv2.VideoCapture(self.index)
            if not cap.isOpened():
                raise RuntimeError("Không mở được camera. Đóng Zoom/Teams/Camera, cấp quyền camera hoặc thử chỉ số 1.")
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_FPS, 30)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            failures, sequence, count = 0, 0, 0
            fps, window_start = 0.0, time.monotonic()
            last_preview = 0.0
            preview_period = 1.0 / max(1, float(self.config.get("preview_fps",25)))
            while not self.stop_event.is_set():
                ok, frame = cap.read()
                if self.stop_event.is_set():
                    break
                if not ok:
                    failures += 1
                    if failures >= 10:
                        raise RuntimeError("Camera không trả ảnh. Thử chỉ số camera khác hoặc tắt/bật lại.")
                    self.stop_event.wait(0.1)
                    continue
                failures = 0
                now = time.monotonic()
                sequence += 1
                count += 1
                if now-window_start >= 0.5:
                    fps = count/(now-window_start)
                    count, window_start = 0, now
                frame = cv2.flip(frame,1)
                snapshot = {"bgr":frame,"time":now,"sequence":sequence,"camera_fps":fps}
                with self.lock:
                    self.latest = snapshot
                self.ready.set()
                if now-last_preview >= preview_period:
                    publish_latest(self.previews,{"rgb":cv2.cvtColor(frame,cv2.COLOR_BGR2RGB),
                                   "time":now,"sequence":sequence,"camera_fps":fps})
                    last_preview = now
        except Exception as exc:
            self.events.put(("error", f"{type(exc).__name__}: {exc}"))
            self.stop_event.set()
            self.ready.set()
        finally:
            if cap is not None:
                cap.release()


def create_engine(config):
    import cv2
    import onnxruntime as ort
    from insightface.app import FaceAnalysis
    cv2.setNumThreads(1)
    options = ort.SessionOptions()
    options.intra_op_num_threads = max(1,int(config.get("cpu_threads",2)))
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.add_session_config_entry("session.intra_op.allow_spinning","0")
    options.add_session_config_entry("session.inter_op.allow_spinning","0")
    engine = FaceAnalysis(name="buffalo_l", allowed_modules=["detection","recognition"],
                          providers=["CPUExecutionProvider"], sess_options=options)
    size = int(config.get("detection_size",480))
    if size < 160 or size > 1024 or size % 32:
        raise ValueError("detection_size cần chia hết cho 32, từ 160 đến 1024.")
    engine.prepare(ctx_id=-1,det_size=(size,size))
    return engine


class CameraWorker(threading.Thread):
    def __init__(self, index, config, engine_factory=None, capture_factory=None):
        super().__init__(daemon=True)
        self.index, self.config = index, config
        self.stop_event = threading.Event()
        self.frames = queue.Queue(maxsize=1)
        self.preview_frames = queue.Queue(maxsize=1)
        self.events = queue.Queue()
        self.engine_factory = engine_factory or create_engine
        self.capture = CaptureLoop(index,config,self.stop_event,self.preview_frames,
                                   self.events,capture_factory)

    def run(self):
        try:
            import cv2
            from regions import extract_regions
            self.capture.start()
            while not self.capture.ready.wait(0.05):
                if self.stop_event.is_set():
                    return
            if self.stop_event.is_set():
                return
            self.events.put(("status", "Camera đã chạy. Đang nạp AI; lần đầu cần mạng để tải buffalo_l (~300 MB)…"))
            engine = self.engine_factory(self.config)
            self.events.put(("status", "Camera trực tiếp và AI đã sẵn sàng. AI có thể cập nhật chậm hơn hình camera."))
            last_sequence, last_start, previous_done = -1, 0.0, None
            minimum_period = 1.0/max(0.1,float(self.config.get("max_analysis_fps",5)))
            while not self.stop_event.is_set():
                wait = minimum_period-(time.monotonic()-last_start)
                if wait > 0 and self.stop_event.wait(wait):
                    break
                snapshot = self.capture.snapshot()
                if snapshot is None or snapshot["sequence"] == last_sequence:
                    self.stop_event.wait(0.01)
                    continue
                if time.monotonic()-snapshot["time"] > 1.0:
                    self.stop_event.wait(0.02)
                    continue
                last_sequence, last_start = snapshot["sequence"], time.monotonic()
                frame = snapshot["bgr"].copy()
                detected = engine.get(frame, max_num=max(2,int(self.config.get("max_faces",5))))
                faces = []
                for face in detected:
                    x1,y1,x2,y2 = [int(v) for v in face.bbox]
                    h,w = frame.shape[:2]
                    x1,y1,x2,y2 = max(0,x1),max(0,y1),min(w,x2),min(h,y2)
                    crop = frame[y1:y2,x1:x2]
                    blur = float(cv2.Laplacian(cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY),cv2.CV_64F).var()) if crop.size else 0
                    good = (min(x2-x1,y2-y1) >= self.config["min_face_size"]
                            and blur >= self.config["min_blur_score"] and float(face.det_score) >= 0.65)
                    faces.append({"box":(x1,y1,x2,y2),"embedding":face.normed_embedding,
                                  "good":good,"regions":extract_regions(frame,face.kps) if good else
                                  {"vectors":{},"polygons":{},"reason":"Cần một mặt đủ rõ","detail_preview":None}})
                done = time.monotonic()
                interval = done-previous_done if previous_done is not None else done-last_start
                previous_done = done
                item = {"rgb":cv2.cvtColor(frame,cv2.COLOR_BGR2RGB),"faces":faces,
                        "time":snapshot["time"],"finished_at":done,"sequence":last_sequence,
                        "fps":1/max(interval,0.001),"latency_ms":(done-snapshot["time"])*1000}
                if not self.stop_event.is_set():
                    publish_latest(self.frames,item)
        except Exception as exc:
            self.events.put(("error",f"{type(exc).__name__}: {exc}"))
        finally:
            self.stop_event.set()
            if self.capture.ident is not None:
                while self.capture.is_alive():
                    self.capture.join(0.1)
            self.events.put(("stopped","Camera đã tắt."))
