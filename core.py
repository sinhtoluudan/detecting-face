"""Local template storage and open-set matching; independent of camera/model."""
from pathlib import Path
from contextlib import contextmanager
import sqlite3
import uuid
import json
import numpy as np
from region_match import VERSION, validate_regions


def normalize(vector):
    value = np.asarray(vector, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(value))
    if value.size != 512 or not np.isfinite(value).all() or norm < 1e-8:
        raise ValueError("Vector khuôn mặt không hợp lệ (cần 512 phần tử).")
    return value / norm


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS people (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS samples (
                    id INTEGER PRIMARY KEY, person_id TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    model TEXT NOT NULL DEFAULT 'buffalo_l',
                    FOREIGN KEY(person_id) REFERENCES people(id) ON DELETE CASCADE);
            ''')
            columns = {row[1] for row in db.execute("PRAGMA table_info(samples)")}
            if "regions" not in columns:
                db.execute("ALTER TABLE samples ADD COLUMN regions TEXT")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path)
        try:
            db.execute("PRAGMA foreign_keys=ON")
            with db:
                yield db
        finally:
            db.close()

    def create_person(self, name):
        name = name.strip()
        if not 1 <= len(name) <= 80:
            raise ValueError("Tên cần từ 1 đến 80 ký tự.")
        person_id = uuid.uuid4().hex
        with self.connect() as db:
            db.execute("INSERT INTO people VALUES (?, ?)", (person_id, name))
        return person_id

    def people(self):
        with self.connect() as db:
            return db.execute('''SELECT p.id, p.name, COUNT(s.id) FROM people p
                LEFT JOIN samples s ON p.id=s.person_id GROUP BY p.id ORDER BY p.name''').fetchall()

    def add_sample(self, person_id, embedding, regions=None):
        embedding = normalize(embedding)
        cleaned = validate_regions(regions)
        payload = json.dumps({"version": VERSION, "vectors": {
            key: value.round(6).tolist() for key,value in cleaned.items()}}, separators=(",", ":")) if cleaned else None
        with self.connect() as db:
            old = db.execute("SELECT id,embedding,regions FROM samples WHERE person_id=?", (person_id,)).fetchall()
            for sample_id, blob, previous_regions in old:
                if float(np.frombuffer(blob, dtype=np.float32) @ embedding) > 0.9995:
                    if payload and not previous_regions:
                        db.execute("UPDATE samples SET regions=? WHERE id=?", (payload,sample_id))
                        return "updated"
                    raise ValueError("Mẫu gần như trùng. Hãy đổi góc hoặc biểu cảm nhẹ rồi chụp lại.")
            if len(old) >= 60:
                raise ValueError("Đã đủ 60 mẫu. Xóa hồ sơ và đăng ký lại nếu cần.")
            db.execute("INSERT INTO samples(person_id,embedding,regions) VALUES (?,?,?)",
                       (person_id, embedding.tobytes(),payload))
        return "added"

    def delete_person(self, person_id):
        with self.connect() as db:
            db.execute("DELETE FROM people WHERE id=?", (person_id,))

    def gallery(self):
        result = {}
        with self.connect() as db:
            rows = db.execute('''SELECT p.id,p.name,s.embedding,s.regions FROM people p
                JOIN samples s ON p.id=s.person_id WHERE s.model='buffalo_l' ''').fetchall()
        for person_id, name, blob, regions in rows:
            result.setdefault(person_id, {"name": name, "vectors": [], "regions": []})["vectors"].append(
                normalize(np.frombuffer(blob, dtype=np.float32)))
            if regions:
                payload = json.loads(regions)
                if payload.get("version") == VERSION:
                    result[person_id]["regions"].append(validate_regions(payload["vectors"]))
        return result


def match(embedding, gallery, threshold=0.50, margin=0.08, min_samples=5):
    """Average best two templates per identity; thresholds need local calibration.

    Return accepted id or None, best similarity and gap to runner-up.
    Similarity is NOT probability. Unready identities never receive a name.
    """
    query = normalize(embedding)
    scores = []
    for person_id, person in gallery.items():
        vectors = person["vectors"]
        if len(vectors) < min_samples:
            continue
        values = np.sort(np.stack(vectors) @ query)
        scores.append((float(values[-2:].mean()), person_id))
    if not scores:
        return None, 0.0, 0.0
    scores.sort(reverse=True)
    best, person_id = scores[0]
    gap = best - scores[1][0] if len(scores) > 1 else 2.0
    accepted = best >= threshold and gap >= margin
    return person_id if accepted else None, best, gap


class Confirmation:
    def __init__(self, required=3):
        self.required = required
        self.reset()

    def reset(self):
        self.candidate = None
        self.count = 0

    def update(self, candidate):
        if candidate is None:
            self.reset()
            return None
        self.count = self.count + 1 if candidate == self.candidate else 1
        self.candidate = candidate
        return candidate if self.count >= self.required else None
