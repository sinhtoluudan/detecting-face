from pathlib import Path
import json
import queue
import time
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw, ImageFont
from core import Store, match, Confirmation
from camera import CameraWorker
from region_match import LABELS, support_identity

ROOT = Path(__file__).resolve().parent


class App:
    def __init__(self, root):
        self.root = root
        root.title("FaceCam • Nhận diện khuôn mặt qua camera laptop")
        root.geometry("1120x720")
        root.minsize(960, 650)
        self.config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
        self.store = Store(ROOT / "data" / "faces.db")
        self.worker = None
        self.latest = None
        self.last_box = None
        self.confirmation = Confirmation(self.config["confirm_frames"])
        self.recognizing = False
        self.closing = False
        self.error_seen = False
        self.last_capture = 0.0
        self.status = tk.StringVar(value="Bước 1: Bật camera. Bước 2: Tạo người và lưu mẫu. Bước 3: Nhận diện.")
        self.result = tk.StringVar(value="Chưa bật camera")
        self.camera_index = tk.StringVar(value=str(self.config["camera_index"]))
        self.threshold = tk.StringVar(value=str(self.config["similarity_threshold"]))
        self.use_regions = tk.BooleanVar(value=True)
        self.show_regions = tk.BooleanVar(value=True)
        self.visible_regions = {key: tk.BooleanVar(value=True) for key in LABELS}
        self.region_details = tk.StringVar(value="Chọn các vùng đang nhìn rõ; bỏ Mũi khi đeo khẩu trang.")
        self.font = self.load_font()
        self.build_ui()
        self.refresh_people()
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(40, self.poll)

    def load_font(self):
        for path in ["C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
            if Path(path).exists():
                return ImageFont.truetype(path, 19)
        return ImageFont.load_default()

    def build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TButton", padding=8)
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="FaceCam", font=("Segoe UI", 24, "bold")).pack(anchor="w")
        ttk.Label(outer, text="Đăng ký khuôn mặt • Bật camera • Hiển thị tên", font=("Segoe UI", 11)).pack(anchor="w", pady=(0,12))
        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=(0,12))
        ttk.Label(controls, text="Camera:").pack(side="left")
        ttk.Spinbox(controls, from_=0, to=5, textvariable=self.camera_index, width=4).pack(side="left", padx=5)
        self.start_button = ttk.Button(controls, text="Bật camera", command=self.start)
        self.start_button.pack(side="left", padx=4)
        ttk.Button(controls, text="Tắt camera", command=self.stop).pack(side="left", padx=4)
        self.rec_button = ttk.Button(controls, text="Bắt đầu nhận diện", command=self.toggle_recognition)
        self.rec_button.pack(side="left", padx=4)
        ttk.Label(controls, text="Ngưỡng:").pack(side="left", padx=(12,4))
        ttk.Entry(controls, textvariable=self.threshold, width=6).pack(side="left")
        body = ttk.Frame(outer)
        body.pack(fill="both", expand=True)
        left = ttk.Frame(body)
        left.pack(side="left", fill="both", expand=True)
        self.preview = tk.Label(left, bg="#101827", fg="white", text="Camera chưa bật", font=("Segoe UI", 16))
        self.preview.pack(fill="both", expand=True)
        ttk.Label(left, textvariable=self.result, font=("Segoe UI",16,"bold"), wraplength=660).pack(anchor="w", pady=10)
        side = ttk.Frame(body, padding=(12,0,0,0))
        side.pack(side="right", fill="y")
        canvas = tk.Canvas(side, width=320, highlightthickness=0)
        scrollbar = ttk.Scrollbar(side, orient="vertical", command=canvas.yview)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="y", expand=True)
        canvas.configure(yscrollcommand=scrollbar.set)
        right = ttk.Frame(canvas)
        window_id = canvas.create_window((0,0), window=right, anchor="nw", width=320)
        right.bind("<Configure>", lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window_id, width=event.width))
        ttk.Label(right, text="Người đã đăng ký", font=("Segoe UI",13,"bold")).pack(anchor="w")
        self.people_list = tk.Listbox(right, width=33, height=5, exportselection=False, font=("Segoe UI",10))
        self.people_list.pack(fill="x", pady=8)
        self.people_list.bind("<<ListboxSelect>>", lambda _: self.clear_confirmation())
        ttk.Button(right, text="1. Thêm người / nhập tên", command=self.add_person).pack(fill="x", pady=3)
        ttk.Button(right, text="2. Lưu một mẫu khuôn mặt", command=self.capture).pack(fill="x", pady=3)
        ttk.Button(right, text="Xóa người đang chọn", command=self.delete_person).pack(fill="x", pady=3)
        ttk.Label(right, text="Chọn đúng tên trước khi lưu mẫu.\nTối thiểu 5 mẫu toàn mặt / người.\nMột người trong khung hình.", wraplength=280, justify="left").pack(anchor="w", pady=8)
        ttk.Separator(right).pack(fill="x", pady=6)
        ttk.Checkbutton(right, text="Đối chiếu thêm từng vùng (thử nghiệm)", variable=self.use_regions,
                        command=self.clear_confirmation).pack(anchor="w")
        ttk.Checkbutton(right, text="Vẽ vùng mặt trên camera", variable=self.show_regions).pack(anchor="w")
        ttk.Label(right, text="Chỉ chọn các vùng đang lộ rõ:", font=("Segoe UI",10,"bold")).pack(anchor="w", pady=(8,2))
        selection = ttk.Frame(right)
        selection.pack(fill="x")
        for i,(key,title) in enumerate(LABELS.items()):
            ttk.Checkbutton(selection, text=title, variable=self.visible_regions[key],
                            command=self.clear_confirmation).grid(row=i//2,column=i%2,sticky="w")
        ttk.Label(right, text="Đeo khẩu trang: bỏ chọn Mũi.\nTóc/tay che vùng nào: bỏ vùng đó.\nÁp dụng cả khi lưu mẫu và nhận diện.", wraplength=280,
                  foreground="#9a3412").pack(anchor="w", pady=6)
        ttk.Label(right, textvariable=self.region_details, wraplength=285, justify="left").pack(anchor="w", pady=6)
        ttk.Label(right, text="Chi tiết tối trên trán (không phải\nkết luận phát hiện nếp nhăn):", wraplength=280).pack(anchor="w")
        self.texture_preview = tk.Label(right, bg="#101827", fg="white", text="Chưa có ảnh vùng trán", width=32)
        self.texture_preview.pack(fill="x", pady=4)
        ttk.Label(outer, textvariable=self.status, wraplength=1000, foreground="#334155").pack(fill="x", pady=(12,0))

    def refresh_people(self, selected=None):
        self.gallery = self.store.gallery()
        self.people = self.store.people()
        self.people_list.delete(0, "end")
        for i, (pid, name, count) in enumerate(self.people):
            regional = len(self.gallery.get(pid,{}).get("regions",[]))
            self.people_list.insert("end", f"{name} [{pid[:4]}] — {count} mặt / {regional} vùng")
            if pid == selected:
                self.people_list.selection_set(i)
        self.clear_confirmation()

    def clear_confirmation(self):
        self.confirmation.reset()
        self.last_box = None

    def enabled_regions(self):
        return [key for key,value in self.visible_regions.items() if value.get()]

    def clear_region_preview(self):
        self.texture_preview.configure(image="", text="Chưa có ảnh vùng trán",width=32)
        self.texture_preview.image = None

    def selected_person(self):
        indices = self.people_list.curselection()
        return self.people[indices[0]] if indices else None

    def add_person(self):
        name = simpledialog.askstring("Đăng ký", "Nhập họ tên người sẽ đưa mặt vào camera:", parent=self.root)
        if name is None:
            return
        try:
            pid = self.store.create_person(name)
            self.refresh_people(pid)
            self.status.set(f"Đã tạo {name.strip()}. Đưa đúng người vào camera và lưu các mẫu.")
        except Exception as exc:
            messagebox.showerror("Không lưu được", str(exc))

    def capture(self):
        person = self.selected_person()
        if not person:
            messagebox.showinfo("Chọn người", "Thêm người hoặc chọn tên trong danh sách trước.")
            return
        item = self.latest
        if not item or time.monotonic()-item["time"] > 1.5 or not self.worker or self.worker.stop_event.is_set():
            self.status.set("Chưa có ảnh camera mới. Hãy bật camera và chờ mô hình nạp xong.")
            return
        if len(item["faces"]) != 1 or not item["faces"][0]["good"]:
            self.status.set("Cần đúng một khuôn mặt đủ rõ. Hãy tiến gần, giữ yên và tăng ánh sáng.")
            return
        if time.monotonic()-self.last_capture < 0.6:
            return
        vectors = {key:value for key,value in item["faces"][0].get("regions",{}).get("vectors",{}).items()
                   if key in self.enabled_regions()}
        if self.use_regions.get() and (len(vectors) < self.config.get("min_regions",3)
                                      or not ({"eye_left","eye_right"} & vectors.keys())):
            self.status.set("Chưa đủ ≥3 vùng rõ, có ít nhất một mắt. Tiến gần và chọn đúng vùng đang lộ.")
            return
        try:
            self.store.add_sample(person[0], item["faces"][0]["embedding"],vectors)
            self.last_capture = time.monotonic()
            self.refresh_people(person[0])
            self.status.set(f"Đã lưu mẫu cho {person[1]} với {len(vectors)} vùng. Đổi góc nhẹ rồi lưu thêm; bỏ chọn Mũi trước khi đeo khẩu trang.")
        except Exception as exc:
            self.status.set(str(exc))

    def delete_person(self):
        person = self.selected_person()
        if person and messagebox.askyesno("Xóa dữ liệu", f"Xóa {person[1]} và toàn bộ mẫu khuôn mặt của người này?"):
            try:
                self.store.delete_person(person[0])
                self.refresh_people()
            except Exception as exc:
                messagebox.showerror("Không xóa được", str(exc))

    def start(self):
        if self.worker is not None:
            return
        try:
            index = int(self.camera_index.get())
            if not 0 <= index <= 10:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Camera", "Chỉ số camera phải là số nguyên từ 0 đến 10.")
            return
        self.latest = None
        self.error_seen = False
        self.clear_confirmation()
        self.start_button.configure(state="disabled")
        self.worker = CameraWorker(index, self.config)
        self.worker.start()

    def stop(self):
        if self.worker:
            self.worker.stop_event.set()
            self.status.set("Đang tắt camera… Nếu đang tải mô hình, chờ tác vụ tải kết thúc.")
        self.latest = None
        self.clear_confirmation()
        self.recognizing = False
        self.rec_button.configure(text="Bắt đầu nhận diện")
        self.result.set("Đã dừng nhận diện")
        self.preview.configure(image="", text="Camera đang tắt")
        self.preview.image = None
        self.clear_region_preview()
        self.region_details.set("Đã dừng phân tích vùng.")

    def toggle_recognition(self):
        if not self.recognizing:
            if not self.worker or self.worker.stop_event.is_set():
                self.status.set("Bật camera trước khi nhận diện.")
                return
            try:
                threshold = float(self.threshold.get())
                if not 0.0 < threshold < 1.0:
                    raise ValueError()
            except ValueError:
                messagebox.showerror("Ngưỡng", "Nhập số từ 0 đến 1, ví dụ 0.50.")
                return
            self.active_threshold = threshold
            if not any(len(p["vectors"]) >= self.config["min_samples"] for p in self.gallery.values()):
                self.status.set("Chưa có ai đủ 5 mẫu. Hãy đăng ký và lưu thêm mẫu trước.")
                return
        self.recognizing = not self.recognizing
        self.clear_confirmation()
        self.rec_button.configure(text="Dừng nhận diện" if self.recognizing else "Bắt đầu nhận diện")
        self.status.set("Nhận diện đang chạy. Người lạ hoặc kết quả chưa chắc chắn sẽ không được gán tên." if self.recognizing else "Đang xem camera; nhận diện đã dừng.")

    def display(self, item):
        self.latest = item
        faces = item["faces"]
        image = Image.fromarray(item["rgb"])
        draw = ImageDraw.Draw(image)
        label, color = "Đang xem camera", "#fbbf24"
        self.region_details.set("Chưa có đủ một khuôn mặt rõ để phân tích.")
        self.clear_region_preview()
        if len(faces) != 1:
            self.clear_confirmation()
            label = "Không thấy khuôn mặt" if not faces else "Chỉ để một người trong khung hình"
        elif not faces[0]["good"]:
            self.clear_confirmation()
            label = "Mặt chưa đủ rõ — tiến gần và giữ yên"
        elif self.recognizing:
            face = faces[0]
            box = face["box"]
            if self.last_box:
                a, b = self.last_box, box
                inter = max(0,min(a[2],b[2])-max(a[0],b[0])) * max(0,min(a[3],b[3])-max(a[1],b[1]))
                union = (a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter
                if inter/max(union,1) < 0.25:
                    self.confirmation.reset()
            self.last_box = box
            pid, score, _ = match(face["embedding"], self.gallery, self.active_threshold,
                                  self.config["runner_up_margin"], self.config["min_samples"])
            if self.use_regions.get():
                pid, region_score, details, reason = support_identity(
                    pid, face.get("regions",{}).get("vectors",{}),self.gallery,self.enabled_regions(),
                    threshold=self.config.get("region_threshold",0.80),
                    min_regions=self.config.get("min_regions",3),
                    min_samples=self.config.get("min_region_samples",3))
                text = "\n".join(f"{LABELS[key]}: {value:.3f}" for key,value in details.items())
                aggregate = f"\nĐiểm vùng: {region_score:.3f}" if region_score is not None else ""
                self.region_details.set(reason + aggregate + ("\n"+text if text else ""))
            else:
                self.region_details.set("Đang dùng đối chiếu toàn mặt; kiểm tra vùng đã tắt.")
            accepted = self.confirmation.update(pid)
            if accepted:
                label = f"{self.gallery[accepted]['name']} • điểm {score:.3f}"
                color = "#4ade80"
            else:
                label = f"{'Đang xác nhận' if pid else 'Chưa xác định'} • điểm {score:.3f}"
        else:
            self.clear_confirmation()
            label = "Mặt rõ — có thể lưu mẫu"
        if len(faces) == 1 and faces[0]["good"]:
            regions = faces[0].get("regions",{})
            enabled = self.enabled_regions()
            if not self.recognizing:
                names = [LABELS[key] for key in regions.get("vectors",{}) if key in enabled]
                self.region_details.set("Vùng có thể lưu: " + (", ".join(names) if names else regions.get("reason", "Chưa rõ")))
            if self.show_regions.get():
                for key, polygon in regions.get("polygons",{}).items():
                    if key not in enabled:
                        continue
                    points = [tuple(point) for point in polygon]
                    available = key in regions.get("vectors",{})
                    draw.line(points+[points[0]], fill="#38bdf8" if available else "#94a3b8", width=2)
            detail = regions.get("detail_preview")
            if detail is not None and "forehead" in enabled and "forehead" in regions.get("vectors",{}):
                photo = ImageTk.PhotoImage(Image.fromarray(detail).resize((260,100)))
                self.texture_preview.configure(image=photo,text="",width=260)
                self.texture_preview.image = photo
        for face in faces:
            draw.rectangle(face["box"], outline=color, width=3)
        draw.rectangle((0,0,image.width,34), fill="#101827")
        draw.text((8,5), label, font=self.font, fill=color)
        image.thumbnail((max(400,self.preview.winfo_width()), max(300,self.preview.winfo_height())))
        photo = ImageTk.PhotoImage(image)
        self.preview.configure(image=photo, text="")
        self.preview.image = photo
        self.result.set(label)

    def poll(self):
        if self.worker:
            try:
                while True:
                    kind, text = self.worker.events.get_nowait()
                    if kind == "error":
                        self.error_seen = True
                        self.status.set(text)
                        if not self.closing:
                            messagebox.showerror("Camera / mô hình", text + "\n\nXem README.md để xử lý.")
                    elif kind == "status" and not self.worker.stop_event.is_set():
                        self.status.set(text)
            except queue.Empty:
                pass
            try:
                item = self.worker.frames.get_nowait()
                if not self.worker.stop_event.is_set() and not self.closing:
                    self.display(item)
            except queue.Empty:
                pass
            if not self.worker.is_alive():
                self.worker = None
                self.latest = None
                self.clear_confirmation()
                self.recognizing = False
                self.rec_button.configure(text="Bắt đầu nhận diện")
                self.start_button.configure(state="normal")
                self.preview.configure(image="", text="Camera đã tắt")
                self.preview.image = None
                self.clear_region_preview()
                self.region_details.set("Camera đã tắt.")
                self.result.set("Camera đã tắt")
                if not self.error_seen:
                    self.status.set("Camera đã tắt.")
            elif self.latest and time.monotonic()-self.latest["time"] > 1.5:
                self.clear_confirmation()
                self.result.set("Đang chờ ảnh mới…")
                self.preview.configure(image="", text="Đang chờ ảnh mới…")
                self.preview.image = None
                self.clear_region_preview()
                self.region_details.set("Đang chờ ảnh mới…")
        if self.closing and self.worker is None:
            self.root.destroy()
            return
        self.root.after(40, self.poll)

    def close(self):
        self.closing = True
        self.stop()
        if self.worker and self.worker.is_alive():
            # A model download may block; daemon shutdown exits safely without DB writes.
            self.root.after(2000, self.root.destroy)


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
