"""Connect the existing FaceCam Tkinter window to the shared attendance API."""
import base64
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener
import webbrowser

sys.path.insert(0, r'D:\FaceCam-ChamCong')
from app import App, Image, tk, ttk


class SharedCamera(App):
    def __init__(self, root, key):
        self.key = key
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.pending = None
        self.next_scan = 0
        self.kiosk_status = tk.StringVar(value='Đang chờ camera…')
        super().__init__(root)
        self.root.title('FaceCam · Máy chấm công chung')

    def build_ui(self):
        super().build_ui()
        side = self.people_list.master
        for widget in side.winfo_children():
            widget.destroy()
        ttk.Label(side, text='Chấm công bằng khuôn mặt', font=('Segoe UI', 13, 'bold')).pack(anchor='w')
        ttk.Label(side, text='Đưa một khuôn mặt vào giữa khung.', wraplength=290).pack(anchor='w', pady=10)
        ttk.Label(side, textvariable=self.kiosk_status, wraplength=290).pack(anchor='w', pady=10)
        ttk.Button(side, text='Hồ sơ khuôn mặt trên web', command=lambda: webbrowser.open(
            'http://localhost:3000/faces')).pack(anchor='w')

    def refresh_people(self, selected=None):
        self.gallery = {}

    def analyze(self, item):
        self.analysis_fps = item['fps']

    def show_live(self, item):
        super().show_live(item)
        if self.pending is not None:
            if not self.pending.done():
                return
            self.kiosk_status.set(self.pending.result())
            self.pending = None
            self.next_scan = time.monotonic() + 1.5
        if time.monotonic() >= self.next_scan:
            self.pending = self.pool.submit(self.scan, item['rgb'].copy())

    def scan(self, rgb):
        image = Image.fromarray(rgb)
        image.thumbnail((640, 480))
        buffer = BytesIO()
        image.save(buffer, format='JPEG', quality=88)
        data = json.dumps({'image': base64.b64encode(buffer.getvalue()).decode('ascii')}).encode()
        request = Request('http://127.0.0.1:8000/api/faces/kiosk/punch', data=data, headers={
            'Content-Type': 'application/json',
            'X-FaceCam-Kiosk': self.key,
        })
        try:
            with build_opener(ProxyHandler({})).open(request, timeout=95) as response:
                return json.load(response)['message']
        except HTTPError as exc:
            try:
                detail = json.load(exc).get('detail')
                if isinstance(detail, str):
                    return detail
            except (ValueError, OSError):
                pass
            return f'Máy chủ trả lỗi {exc.code}.'
        except (URLError, OSError):
            return 'Chưa kết nối được máy chủ FaceCam ở cổng 8000.'

    def close(self):
        self.pool.shutdown(wait=False, cancel_futures=True)
        super().close()


if __name__ == '__main__':
    key = os.environ.get('FACECAM_KIOSK_KEY')
    if not key:
        raise SystemExit('Hãy mở bằng Bat-may-cham-cong.ps1.')
    root = tk.Tk()
    SharedCamera(root, key)
    root.mainloop()
