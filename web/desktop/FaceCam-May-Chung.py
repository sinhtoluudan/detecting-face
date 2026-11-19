"""Windows webcam client for the shared attendance API."""
import base64
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import json
import os
from pathlib import Path
from queue import Empty, Queue
import sys
from threading import Event
import time
import tkinter as tk
from tkinter import ttk
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener
import webbrowser

from PIL import Image, ImageTk

WEB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WEB))
from camera import CaptureLoop


class SharedCamera:
    def __init__(self, root, key):
        self.root = root
        self.key = key
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.pending = None
        self.next_scan = 0
        self.worker = None
        self.config = json.loads((WEB / 'config.json').read_text(encoding='utf-8-sig'))
        self.index = tk.StringVar(value=str(self.config['camera_index']))
        self.kiosk_status = tk.StringVar(value='Bấm Bật camera để bắt đầu chấm công.')
        root.title('FaceCam · Máy chấm công chung')
        root.geometry('1000x620')
        controls = ttk.Frame(root, padding=10)
        controls.pack(fill='x')
        ttk.Label(controls, text='Camera:').pack(side='left')
        ttk.Spinbox(controls, from_=0, to=10, width=4, textvariable=self.index).pack(side='left', padx=5)
        self.start_button = ttk.Button(controls, text='Bật camera', command=self.start)
        self.start_button.pack(side='left', padx=4)
        self.stop_button = ttk.Button(controls, text='Tắt camera', command=self.stop, state='disabled')
        self.stop_button.pack(side='left', padx=4)
        side = ttk.Frame(root, padding=12)
        side.pack(side='right', fill='y')
        ttk.Label(side, text='Chấm công bằng khuôn mặt', font=('Segoe UI', 13, 'bold')).pack(anchor='w')
        ttk.Label(side, text='Đưa một khuôn mặt vào giữa khung.').pack(anchor='w', pady=10)
        ttk.Label(side, textvariable=self.kiosk_status, wraplength=290).pack(anchor='w', pady=10)
        ttk.Button(side, text='Hồ sơ khuôn mặt trên web', command=lambda: webbrowser.open(
            'http://localhost:3000/faces')).pack(anchor='w')
        self.preview = tk.Label(root, bg='#101827', fg='white', text='Camera chưa bật', width=1, height=1)
        self.preview.pack(fill='both', expand=True, padx=10, pady=10)
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.timer = root.after(30, self.poll)

    def start(self):
        if self.worker is not None:
            return
        try:
            index = int(self.index.get())
            if not 0 <= index <= 10:
                raise ValueError
        except ValueError:
            self.kiosk_status.set('Chọn chỉ số camera từ 0 đến 10.')
            return
        self.frames = Queue(maxsize=1)
        self.events = Queue()
        self.worker = CaptureLoop(index, self.config, Event(), self.frames, self.events)
        self.start_button.configure(state='disabled')
        self.stop_button.configure(state='normal')
        self.kiosk_status.set('Đang mở camera…')
        self.next_scan = 0
        self.worker.start()

    def stop(self):
        if self.worker:
            self.worker.stop_event.set()
        self.stop_button.configure(state='disabled')
        self.kiosk_status.set('Đã tắt camera.')

    def poll(self):
        if self.worker:
            try:
                while True:
                    _, message = self.events.get_nowait()
                    self.kiosk_status.set(message)
            except Empty:
                pass
            if self.worker.stop_event.is_set():
                self.preview.configure(image='', text='Camera đã tắt')
                self.preview.image = None
                self.stop_button.configure(state='disabled')
                if not self.worker.is_alive():
                    self.worker = None
                    self.start_button.configure(state='normal')
            else:
                try:
                    frame = self.frames.get_nowait()
                except Empty:
                    pass
                else:
                    self.show_live(frame['rgb'])
        self.timer = self.root.after(30, self.poll)

    def show_live(self, rgb):
        preview = Image.fromarray(rgb)
        preview.thumbnail((max(1, self.preview.winfo_width()), max(1, self.preview.winfo_height())))
        photo = ImageTk.PhotoImage(preview)
        self.preview.configure(image=photo, text='')
        self.preview.image = photo
        if self.pending is not None:
            if not self.pending.done():
                return
            self.kiosk_status.set(self.pending.result())
            self.pending = None
            self.next_scan = time.monotonic() + 1.5
        if time.monotonic() >= self.next_scan:
            self.pending = self.pool.submit(self.scan, rgb.copy())

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
        self.root.after_cancel(self.timer)
        if self.worker:
            self.worker.stop_event.set()
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()


if __name__ == '__main__':
    key = os.environ.get('FACECAM_KIOSK_KEY')
    if not key:
        raise SystemExit('Hãy mở bằng Bat-may-cham-cong.ps1.')
    root = tk.Tk()
    SharedCamera(root, key)
    root.mainloop()
