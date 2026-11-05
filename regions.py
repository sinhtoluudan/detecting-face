"""Eye-anchored region estimates + HOG/LBP appearance, not a wrinkle classifier.

    Coordinates are in a 256px canonical image. Brows/forehead are approximate
    windows inferred from the eye line, NOT anatomical segmentation.
"""
import cv2
import numpy as np

BOXES = {
    "eye_left": (58, 107, 113, 137),
    "eye_right": (143, 107, 198, 137),
    "brow_left": (53, 82, 116, 107),
    "brow_right": (140, 82, 203, 107),
    "forehead": (76, 39, 180, 79),
}


def eye_transform(keypoints):
    points = np.asarray(keypoints, dtype=np.float32)
    if points.shape != (5, 2) or not np.isfinite(points).all():
        raise ValueError("Thiếu các điểm mốc khuôn mặt.")
    eyes = points[:2][np.argsort(points[:2, 0])]
    dx, dy = eyes[1] - eyes[0]
    distance = float(np.hypot(dx, dy))
    if distance < 45:
        raise ValueError("Cần tiến gần camera để vùng mắt đủ chi tiết.")
    # Similarity transform from TWO eyes, avoiding inferred masked nose/mouth.
    a, b = 80.0 * dx / distance**2, 80.0 * dy / distance**2
    x, y = eyes[0]
    return np.array([[a, b, 88-a*x-b*y], [-b, a, 120+b*x-a*y]], dtype=np.float32)


def descriptor(gray):
    """4x4 HOG cells (9 bins) + 4x4 uniform LBP cells (10 bins) = 304 values."""
    if gray.ndim != 2 or min(gray.shape) < 12:
        raise ValueError("Ảnh vùng quá nhỏ.")
    patch = cv2.resize(gray, (64,64), interpolation=cv2.INTER_AREA)
    patch = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4,4)).apply(patch)
    gx = cv2.Sobel(patch, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(patch, cv2.CV_32F, 0, 1, ksize=3)
    magnitude, angle = cv2.cartToPolar(gx, gy, angleInDegrees=True)
    bins = ((angle % 180) / 20).astype(np.int32).clip(0,8)
    hog = []
    for row in range(4):
        for col in range(4):
            cell = np.s_[row*16:(row+1)*16, col*16:(col+1)*16]
            hist = np.bincount(bins[cell].ravel(), weights=magnitude[cell].ravel(), minlength=9)
            hist /= np.linalg.norm(hist) + 1e-8
            hog.extend(hist)
    center = patch[1:-1,1:-1]
    neighbors = [patch[:-2,:-2], patch[:-2,1:-1], patch[:-2,2:], patch[1:-1,2:],
                 patch[2:,2:], patch[2:,1:-1], patch[2:,:-2], patch[1:-1,:-2]]
    bits = np.stack([p >= center for p in neighbors])
    transitions = np.count_nonzero(bits != np.roll(bits,1,axis=0),axis=0)
    uniform = np.where(transitions <= 2, bits.sum(axis=0), 9)
    lbp = []
    for rows in np.array_split(uniform,4,axis=0):
        for cell in np.array_split(rows,4,axis=1):
            hist = np.bincount(cell.ravel(), minlength=10).astype(np.float32)
            hist /= hist.sum() + 1e-8
            lbp.extend(np.sqrt(hist))
    hog, lbp = np.asarray(hog), np.asarray(lbp)
    hog /= np.linalg.norm(hog) + 1e-8
    lbp /= np.linalg.norm(lbp) + 1e-8
    vector = np.concatenate([np.sqrt(0.7)*hog, np.sqrt(0.3)*lbp]).astype(np.float32)
    return vector / max(float(np.linalg.norm(vector)), 1e-8)


def extract_regions(frame_bgr, keypoints):
    result = {"vectors": {}, "polygons": {}, "reason": "", "detail_preview": None}
    try:
        transform = eye_transform(keypoints)
    except (ValueError, TypeError):
        result["reason"] = "Điểm mốc chưa rõ / mặt quá xa để phân tích vùng"
        return result
    canonical = cv2.warpAffine(frame_bgr, transform, (256,256), flags=cv2.INTER_LINEAR)
    valid = cv2.warpAffine(np.full(frame_bgr.shape[:2],255,np.uint8), transform, (256,256))
    gray = cv2.cvtColor(canonical, cv2.COLOR_BGR2GRAY)
    inverse = cv2.invertAffineTransform(transform)
    boxes = dict(BOXES)
    nose = transform @ np.r_[np.asarray(keypoints)[2], 1]
    nx, ny = np.rint(nose).astype(int)
    # Bound estimated nose location to reduce large pose / invalid landmarks.
    if 103 <= nx <= 153 and 138 <= ny <= 192:
        boxes["nose"] = (nx-24,ny-24,nx+24,ny+22)
    for key, (x1,y1,x2,y2) in boxes.items():
        corners = np.array([[x1,y1,1],[x2,y1,1],[x2,y2,1],[x1,y2,1]],np.float32)
        result["polygons"][key] = (corners @ inverse.T).tolist()
        patch = gray[y1:y2,x1:x2]
        # Quality checks don't detect hands, glasses, hair or masks. User excludes them.
        if np.mean(valid[y1:y2,x1:x2] > 250) < 0.98 or patch.std() < 5:
            continue
        if np.mean((patch < 6) | (patch > 249)) > 0.35:
            continue
        if cv2.Laplacian(patch,cv2.CV_32F).var() < 15:
            continue
        result["vectors"][key] = descriptor(patch)
    # Show candidate dark lines on the forehead; NOT validated wrinkle detection.
    x1,y1,x2,y2 = BOXES["forehead"]
    forehead = gray[y1:y2,x1:x2]
    response = cv2.morphologyEx(forehead, cv2.MORPH_BLACKHAT,
                              cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(7,7)))
    preview = cv2.cvtColor(forehead,cv2.COLOR_GRAY2RGB)
    cutoff = max(12.0, float(np.percentile(response,90)))
    preview[response > cutoff] = (255,180,30)
    result["detail_preview"] = preview
    if not result["vectors"]:
        result["reason"] = "Các vùng mờ, tối hoặc nằm ngoài khung hình"
    return result
