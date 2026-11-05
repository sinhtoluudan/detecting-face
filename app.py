from pathlib import Path
import json
import queue
import time
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw, ImageFont
from core import Store, match
from camera import CameraWorker
from region_match import LABELS, support_identity
from tracking import FaceTracker

ROOT = Path(__file__).resolve().parent


class App:
    def __init__(self,root):
        self.root = root
        root.title('FaceCam • Nhiều khuôn mặt')
        root.geometry('1120x720')
        root.minsize(960,650)
        self.config = json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
        self.store = Store(ROOT/'data'/'faces.db')
        self.tracker = FaceTracker(self.config)
        self.worker = None
        self.latest = None
        self.recognizing = False
        self.closing = False
        self.error_seen = False
        self.last_capture = 0.0
        self.last_live = 0.0
        self.last_metrics = 0.0
        self.camera_fps = self.analysis_fps = 0.0
        self.camera_index = tk.StringVar(value=str(self.config['camera_index']))
        self.threshold = tk.StringVar(value=str(self.config['similarity_threshold']))
        self.use_regions = tk.BooleanVar(value=True)
        self.visible_regions = {key:tk.BooleanVar(value=True) for key in LABELS}
        self.status = tk.StringVar(value='Bật camera, đăng ký mẫu cho từng người, rồi bắt đầu nhận diện.')
        self.performance = tk.StringVar(value='Mỗi người có khung và tên riêng trên camera chính.')
        self.font = self.load_font(22)
        self.build_ui()
        self.refresh_people()
        root.protocol('WM_DELETE_WINDOW',self.close)
        root.after(20,self.poll)

    def load_font(self,size):
        for path in ['C:/Windows/Fonts/arialbd.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']:
            if Path(path).exists():
                return ImageFont.truetype(path,size)
        return ImageFont.load_default()

    def build_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TButton',padding=7)
        outer = ttk.Frame(self.root,padding=14)
        outer.pack(fill='both',expand=True)
        outer.columnconfigure(0,weight=1)
        outer.rowconfigure(2,weight=1)
        ttk.Label(outer,text='FaceCam',font=('Segoe UI',23,'bold')).grid(row=0,column=0,sticky='w')
        bar = ttk.Frame(outer)
        bar.grid(row=1,column=0,sticky='ew',pady=10)
        ttk.Label(bar,text='Camera:').pack(side='left')
        ttk.Spinbox(bar,from_=0,to=10,textvariable=self.camera_index,width=4).pack(side='left',padx=5)
        self.start_button = ttk.Button(bar,text='Bật camera',command=self.start)
        self.start_button.pack(side='left',padx=4)
        ttk.Button(bar,text='Tắt camera',command=self.stop).pack(side='left',padx=4)
        self.rec_button = ttk.Button(bar,text='Bắt đầu nhận diện',command=self.toggle_recognition)
        self.rec_button.pack(side='left',padx=4)
        ttk.Label(bar,text='Ngưỡng:').pack(side='left',padx=(12,4))
        ttk.Entry(bar,textvariable=self.threshold,width=6).pack(side='left')
        body = ttk.Frame(outer)
        body.grid(row=2,column=0,sticky='nsew')
        body.columnconfigure(0,weight=1)
        body.rowconfigure(0,weight=1)
        self.preview = tk.Label(body,bg='#101827',fg='white',text='Camera chưa bật',width=1,height=1,
                                font=('Segoe UI',16))
        self.preview.grid(row=0,column=0,sticky='nsew')
        side = ttk.Frame(body,padding=(12,0,0,0))
        side.grid(row=0,column=1,sticky='ns')
        canvas = tk.Canvas(side,width=320,highlightthickness=0)
        scrollbar = ttk.Scrollbar(side,orient='vertical',command=canvas.yview)
        scrollbar.pack(side='right',fill='y')
        canvas.pack(side='left',fill='y',expand=True)
        canvas.configure(yscrollcommand=scrollbar.set)
        right = ttk.Frame(canvas)
        window_id = canvas.create_window((0,0),window=right,anchor='nw',width=320)
        right.bind('<Configure>',lambda _:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda event:canvas.itemconfigure(window_id,width=event.width))
        ttk.Label(right,text='Người đã đăng ký',font=('Segoe UI',13,'bold')).pack(anchor='w')
        self.people_list = tk.Listbox(right,width=33,height=7,exportselection=False,font=('Segoe UI',10))
        self.people_list.pack(fill='x',pady=8)
        ttk.Button(right,text='1. Thêm người / nhập tên',command=self.add_person).pack(fill='x',pady=3)
        ttk.Button(right,text='2. Lưu một mẫu khuôn mặt',command=self.capture).pack(fill='x',pady=3)
        ttk.Button(right,text='Xóa người đang chọn',command=self.delete_person).pack(fill='x',pady=3)
        ttk.Label(right,text='ĐĂNG KÝ: chỉ một người trước camera.\nChọn đúng tên, lưu ít nhất 5 mẫu/người.\n\nNHẬN DIỆN: nhiều người cùng lúc.\nTên xanh: đã xác nhận.\nChưa xác định: chưa đủ điều kiện.',wraplength=295,
                  justify='left').pack(anchor='w',pady=12)
        ttk.Separator(right).pack(fill='x',pady=6)
        ttk.Checkbutton(right,text='Đối chiếu thêm từng vùng (thử nghiệm)',variable=self.use_regions,
                        command=self.reset_names).pack(anchor='w')
        ttk.Label(right,text='Vùng dùng chung cho mọi người:',font=('Segoe UI',10,'bold')).pack(anchor='w',pady=(8,2))
        selection = ttk.Frame(right)
        selection.pack(fill='x')
        for i,(key,title) in enumerate(LABELS.items()):
            ttk.Checkbutton(selection,text=title,variable=self.visible_regions[key],command=self.reset_names).grid(
                row=i//2,column=i%2,sticky='w')
        ttk.Label(right,text='Nếu nhóm có người đeo khẩu trang, bỏ chọn Mũi. Các ô này chưa tự nhận biết vùng bị che ở từng người.',
                  wraplength=295,foreground='#9a3412').pack(anchor='w',pady=10)
        ttk.Label(right,text='Không còn bảng tên lớn hay ảnh AI phụ. Tên được giữ ngắn hạn khi AI tạm mất kết quả; khi mất dấu hoặc kết quả hết hạn, tên bị xóa.',
                  wraplength=295).pack(anchor='w',pady=8)
        ttk.Label(outer,textvariable=self.performance,wraplength=1000).grid(row=3,column=0,sticky='w',pady=(8,0))
        ttk.Label(outer,textvariable=self.status,wraplength=1000,foreground='#334155').grid(row=4,column=0,sticky='w',pady=(5,0))

    def reset_names(self):
        self.tracker.clear()

    def enabled_regions(self):
        return [key for key,value in self.visible_regions.items() if value.get()]

    def refresh_people(self,selected=None):
        self.gallery,self.people = self.store.gallery(),self.store.people()
        self.people_list.delete(0,'end')
        for index,(pid,name,count) in enumerate(self.people):
            regional = len(self.gallery.get(pid,{}).get('regions',[]))
            self.people_list.insert('end',f'{name} [{pid[:4]}] — {count} mặt / {regional} vùng')
            if pid==selected:
                self.people_list.selection_set(index)
        self.reset_names()

    def selected_person(self):
        selected = self.people_list.curselection()
        return self.people[selected[0]] if selected else None

    def add_person(self):
        name = simpledialog.askstring('Đăng ký','Nhập họ tên người sẽ đăng ký:',parent=self.root)
        if name is None:
            return
        try:
            pid = self.store.create_person(name)
            self.refresh_people(pid)
            self.status.set(f'Đã tạo {name.strip()}. Chỉ để người này trong camera và lưu mẫu.')
        except Exception as exc:
            messagebox.showerror('Không lưu được',str(exc))

    def capture(self):
        person,item = self.selected_person(),self.latest
        if not person:
            messagebox.showinfo('Chọn người','Thêm người hoặc chọn tên trước khi lưu.')
            return
        if not self.worker or self.worker.stop_event.is_set() or not item or time.monotonic()-item['time']>self.config.get('max_result_age',3):
            self.status.set('Chưa có ảnh phân tích mới. Giữ mặt trước camera và chờ AI.')
            return
        if len(item['faces'])!=1 or not item['faces'][0]['good']:
            messagebox.showinfo('Chưa thể lưu','Khi đăng ký cần đúng một khuôn mặt đủ rõ. Những người khác hãy ra khỏi khung hình.')
            return
        if time.monotonic()-self.last_capture<0.6:
            return
        vectors = {key:value for key,value in item['faces'][0]['regions']['vectors'].items() if key in self.enabled_regions()}
        if self.use_regions.get() and (len(vectors)<self.config.get('min_regions',3) or not ({'eye_left','eye_right'}&vectors.keys())):
            self.status.set('Cần ít nhất 3 vùng rõ, có một mắt. Tiến gần và tăng ánh sáng.')
            return
        try:
            self.store.add_sample(person[0],item['faces'][0]['embedding'],vectors)
            self.last_capture = time.monotonic()
            self.refresh_people(person[0])
            self.status.set(f'Đã lưu mẫu cho {person[1]}. Đổi góc nhẹ rồi lưu tiếp.')
        except Exception as exc:
            self.status.set(str(exc))

    def delete_person(self):
        person = self.selected_person()
        if person and messagebox.askyesno('Xóa dữ liệu',f'Xóa {person[1]} và các mẫu đã đăng ký?'):
            try:
                self.store.delete_person(person[0])
                self.refresh_people()
            except Exception as exc:
                messagebox.showerror('Không xóa được',str(exc))

    def start(self):
        if self.worker is not None:
            return
        try:
            index = int(self.camera_index.get())
            if not 0<=index<=10:
                raise ValueError()
        except ValueError:
            messagebox.showerror('Camera','Nhập chỉ số camera từ 0 đến 10.')
            return
        self.latest = None
        self.error_seen = False
        self.last_live = 0.0
        self.camera_fps = self.analysis_fps = 0.0
        self.reset_names()
        self.worker = CameraWorker(index,self.config)
        self.start_button.configure(state='disabled')
        self.worker.start()

    def stop(self):
        if self.worker:
            self.worker.stop_event.set()
        self.recognizing = False
        self.latest = None
        self.reset_names()
        self.rec_button.configure(text='Bắt đầu nhận diện')
        self.preview.configure(image='',text='Camera đã dừng')
        self.preview.image = None
        self.status.set('Đã dừng camera và nhận diện.')

    def toggle_recognition(self):
        if not self.recognizing:
            if not self.worker or self.worker.stop_event.is_set():
                messagebox.showinfo('Camera','Bật camera trước.')
                return
            try:
                self.active_threshold = float(self.threshold.get())
                if not 0<self.active_threshold<1:
                    raise ValueError()
            except ValueError:
                messagebox.showerror('Ngưỡng','Nhập số từ 0 đến 1, ví dụ 0.50.')
                return
            if not any(len(p['vectors'])>=self.config['min_samples'] for p in self.gallery.values()):
                messagebox.showinfo('Chưa đủ mẫu','Cần ít nhất một người có 5 mẫu. Lưu thêm mẫu rồi thử lại.')
                return
        self.recognizing = not self.recognizing
        self.reset_names()
        self.rec_button.configure(text='Dừng nhận diện' if self.recognizing else 'Bắt đầu nhận diện')
        self.status.set('Đang nhận diện nhiều khuôn mặt. Mỗi tên nằm trên khung của người tương ứng.' if self.recognizing else 'Nhận diện đã dừng; camera vẫn chạy.')

    def analyze(self,item):
        self.analysis_fps = item['fps']
        if time.monotonic()-item['time']>self.config.get('max_result_age',3):
            self.latest = None
            return
        self.latest = item
        candidates = []
        for face in item['faces']:
            pid = None
            if self.recognizing and face['good']:
                pid,_,_ = match(face['embedding'],self.gallery,self.active_threshold,
                              self.config['runner_up_margin'],self.config['min_samples'])
                if self.use_regions.get():
                    pid,_,_,_ = support_identity(pid,face['regions']['vectors'],self.gallery,self.enabled_regions(),
                        threshold=self.config.get('region_threshold',0.8),min_regions=self.config.get('min_regions',3),
                        min_samples=self.config.get('min_region_samples',3))
            candidates.append(pid)
        self.tracker.ingest(item,candidates)

    def show_live(self,item):
        self.last_live,self.camera_fps = item['time'],item['camera_fps']
        self.tracker.advance(item['rgb'],item['time'])
        image = Image.fromarray(item['rgb'])
        image.thumbnail((max(1,self.preview.winfo_width()),max(1,self.preview.winfo_height())))
        draw = ImageDraw.Draw(image)
        for _,box,pid in self.tracker.visible(time.monotonic()):
            x1,y1,x2,y2 = [int(v) for v in box*[image.width,image.height,image.width,image.height]]
            known = self.recognizing and pid in self.gallery
            name = self.gallery[pid]['name'] if known else ('Chưa xác định' if self.recognizing else 'Khuôn mặt')
            color = '#4ade80' if known else '#fbbf24'
            draw.rectangle((x1,y1,x2,y2),outline=color,width=3)
            # Text is drawn AFTER resize, so names remain readable on large phone frames.
            while draw.textlength(name,font=self.font)>max(50,image.width-16) and len(name)>3:
                name = name[:-2].rstrip('…')+'…'
            text_box = draw.textbbox((0,0),name,font=self.font)
            width,height = text_box[2]-text_box[0]+14,text_box[3]-text_box[1]+12
            tx = max(0,min(x1,image.width-width))
            ty = max(0,y1-height)
            draw.rectangle((tx,ty,tx+width,ty+height),fill='#101827')
            draw.text((tx+7,ty+6-text_box[1]),name,font=self.font,fill=color)
        photo = ImageTk.PhotoImage(image)
        self.preview.configure(image=photo,text='')
        self.preview.image = photo

    def poll(self):
        if self.worker:
            try:
                while True:
                    kind,text = self.worker.events.get_nowait()
                    if kind=='error':
                        self.error_seen = True
                        self.stop()
                        self.status.set(text)
                        if not self.closing:
                            messagebox.showerror('Camera / AI',text)
                    elif kind=='status' and not self.worker.stop_event.is_set():
                        self.status.set(text)
            except queue.Empty:
                pass
            try:
                item = self.worker.preview_frames.get_nowait()
                if not self.worker.stop_event.is_set() and not self.closing:
                    self.show_live(item)
            except queue.Empty:
                pass
            try:
                item = self.worker.frames.get_nowait()
                if not self.worker.stop_event.is_set() and not self.closing:
                    self.analyze(item)
            except queue.Empty:
                pass
            if not self.worker.is_alive():
                self.worker = None
                self.latest = None
                self.recognizing = False
                self.reset_names()
                self.start_button.configure(state='normal')
                self.rec_button.configure(text='Bắt đầu nhận diện')
                self.preview.configure(image='',text='Camera đã tắt')
                self.preview.image = None
            elif self.last_live and time.monotonic()-self.last_live>1:
                self.reset_names()
                self.preview.configure(image='',text='Đang chờ camera…')
                self.preview.image = None
            if time.monotonic()-self.last_metrics>=1:
                self.performance.set(f'Camera: {self.camera_fps:.0f} FPS | AI: {self.analysis_fps:.1f} lượt/s | Tối đa {self.config.get("max_faces",5)} khuôn mặt')
                self.last_metrics = time.monotonic()
        if self.closing and self.worker is None:
            self.root.destroy()
            return
        self.root.after(20,self.poll)

    def close(self):
        self.closing = True
        self.stop()
        if self.worker and self.worker.is_alive():
            self.root.after(2000,self.root.destroy)


if __name__=='__main__':
    root = tk.Tk()
    App(root)
    root.mainloop()
