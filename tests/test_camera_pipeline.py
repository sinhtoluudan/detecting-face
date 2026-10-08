"""Tests use a synthetic camera and a blocked engine, not a real webcam/model."""
import queue
import threading
import time
import unittest
import numpy as np
from camera import CameraWorker


class FakeCapture:
    def __init__(self,opened=True):
        self.opened = opened
        self.released = threading.Event()
        self.counter = 0

    def isOpened(self):
        return self.opened

    def set(self,*args):
        return True

    def read(self):
        self.released.wait(0.02)
        self.counter += 1
        return True,np.full((48,64,3),self.counter%255,dtype=np.uint8)

    def release(self):
        self.released.set()


CONFIG = {"preview_fps":50,"max_analysis_fps":10,"min_face_size":90,"min_blur_score":35}


class PipelineTests(unittest.TestCase):
    def test_preview_continues_during_model_load_and_slow_inference(self):
        camera = FakeCapture()
        loading,allow_load = threading.Event(),threading.Event()
        analyzing,allow_analysis = threading.Event(),threading.Event()

        class SlowEngine:
            def get(self,frame,max_num=2):
                analyzing.set()
                if not allow_analysis.wait(3):
                    raise RuntimeError("test timeout")
                return []

        def load(config):
            loading.set()
            if not allow_load.wait(3):
                raise RuntimeError("test timeout")
            return SlowEngine()

        worker = CameraWorker(0,CONFIG,load,lambda _:camera)
        worker.start()
        try:
            self.assertTrue(loading.wait(2))
            first = worker.preview_frames.get(timeout=1)
            next_frame = worker.preview_frames.get(timeout=1)
            self.assertGreater(next_frame["sequence"],first["sequence"])
            self.assertTrue(worker.frames.empty())
            allow_load.set()
            self.assertTrue(analyzing.wait(2))
            previews = [worker.preview_frames.get(timeout=1) for _ in range(8)]
            self.assertEqual(len({p["sequence"] for p in previews}),8)
            self.assertTrue(worker.frames.empty())
            allow_analysis.set()
            result = worker.frames.get(timeout=2)
            self.assertGreater(result["finished_at"]-result["time"],0.1)
            self.assertGreater(previews[-1]["sequence"],result["sequence"])
            self.assertLessEqual(worker.preview_frames.qsize(),1)
        finally:
            worker.stop_event.set()
            allow_load.set()
            allow_analysis.set()
            worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertTrue(camera.released.is_set())

    def test_stop_releases_camera_even_while_ai_is_blocked(self):
        camera = FakeCapture()
        entered,unblock = threading.Event(),threading.Event()

        class Engine:
            def get(self,frame,max_num=2):
                entered.set()
                unblock.wait(3)
                return []

        worker = CameraWorker(0,CONFIG,lambda _:Engine(),lambda _:camera)
        worker.start()
        try:
            self.assertTrue(entered.wait(2))
            worker.stop_event.set()
            self.assertTrue(camera.released.wait(1))
        finally:
            unblock.set()
            worker.stop_event.set()
            worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertTrue(worker.frames.empty())

    def test_unavailable_camera_reports_error_without_loading_ai(self):
        camera = FakeCapture(opened=False)
        called = threading.Event()
        worker = CameraWorker(0,CONFIG,lambda _:called.set(),lambda _:camera)
        worker.start()
        worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertFalse(called.is_set())
        self.assertTrue(camera.released.is_set())
        events = []
        while not worker.events.empty():
            events.append(worker.events.get_nowait()[0])
        self.assertIn("error",events)

    def test_ai_failure_releases_camera(self):
        camera = FakeCapture()
        def fail(config):
            raise RuntimeError("model unavailable")
        worker = CameraWorker(0,CONFIG,fail,lambda _:camera)
        worker.start()
        worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertTrue(camera.released.is_set())
        self.assertTrue(worker.stop_event.is_set())


if __name__ == "__main__":
    unittest.main()
