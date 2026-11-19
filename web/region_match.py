"""Experimental regional support. Never identifies someone on texture alone."""
import numpy as np

VERSION = "eye-aligned-hog-lbp-v1"
DIMENSION = 304
LABELS = {
    "eye_left": "Mắt trái ảnh", "eye_right": "Mắt phải ảnh",
    "brow_left": "Mày trái ảnh", "brow_right": "Mày phải ảnh",
    "forehead": "Trán (ước lượng)", "nose": "Mũi",
}
WEIGHTS = {"eye_left": 0.25, "eye_right": 0.25, "brow_left": 0.10,
           "brow_right": 0.10, "forehead": 0.15, "nose": 0.15}


def validate_regions(regions):
    cleaned = {}
    for key, value in (regions or {}).items():
        if key not in LABELS:
            raise ValueError("Vùng mặt không hợp lệ.")
        vector = np.asarray(value, dtype=np.float32).reshape(-1)
        length = np.linalg.norm(vector)
        if vector.size != DIMENSION or not np.isfinite(vector).all() or length < 1e-8:
            raise ValueError("Đặc trưng vùng mặt không hợp lệ.")
        cleaned[key] = vector / length
    return cleaned


def check_regions(query, templates, enabled, threshold=0.80, min_regions=3, min_samples=3):
    """Compare only manually enabled, quality-passing, version-compatible regions.

    Returns (passed, aggregate_score or None, scores_by_region, explanation).
    No texture score can override a rejected global face identity.
    """
    query = validate_regions(query)
    scores = {}
    for key in enabled:
        if key not in query:
            continue
        vectors = [sample[key] for sample in templates if key in sample]
        if len(vectors) < min_samples:
            continue
        values = np.sort(np.stack(vectors) @ query[key])
        scores[key] = float(np.clip(values[-2:].mean(), 0, 1))
    # Need actual eye information; forehead/eyebrows alone cannot pass the gate.
    if len(scores) < min_regions or not ({"eye_left", "eye_right"} & scores.keys()):
        return False, None, scores, "Thiếu mẫu/vùng rõ: cần ≥3 vùng, có ít nhất một mắt"
    weight = sum(WEIGHTS[key] for key in scores)
    score = sum(WEIGHTS[key] * value for key, value in scores.items()) / weight
    passed = score >= threshold
    return passed, score, scores, "Vùng mặt khớp" if passed else "Đặc trưng vùng mặt chưa khớp"


def support_identity(candidate, query, gallery, enabled, **options):
    if candidate is None:
        return None, None, {}, "Toàn mặt chưa đạt: không gán tên bằng kết cấu da"
    passed, score, scores, reason = check_regions(
        query, gallery[candidate].get("regions", []), enabled, **options)
    return candidate if passed else None, score, scores, reason
