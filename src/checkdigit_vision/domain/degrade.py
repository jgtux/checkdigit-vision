import random
from typing import Dict, List, Tuple

import cv2
import numpy as np

Box = Tuple[int, int, int, int]

# one factor at a time: level 0 is always the clean image
LEVELS: Dict[str, List[float]] = {
    "blur": [0, 1, 2, 3, 4, 5],                    # gaussian sigma, px
    "rotation": [0, 3, 7, 12, 20, 30],             # degrees
    "perspective": [0, 0.04, 0.08, 0.12, 0.16, 0.20],  # corner jitter, fraction of size
    "noise": [0, 15, 30, 50, 75, 100],             # gaussian sd, gray levels
    "jpeg": [95, 40, 20, 12, 7, 4],                # quality
    "downscale": [1.0, 0.7, 0.5, 0.4, 0.3, 0.22],  # resize factor
    "occlusion": [0, 0.1, 0.2, 0.35, 0.5, 0.7],    # fraction of barcode width covered
}


def _white_border_warp(img: np.ndarray, m: np.ndarray, perspective: bool) -> np.ndarray:
    h, w = img.shape
    warp = cv2.warpPerspective if perspective else cv2.warpAffine
    return warp(img, m, (w, h), flags=cv2.INTER_LINEAR, borderValue=255)


def blur(img, sigma, rng):
    if sigma <= 0:
        return img
    return cv2.GaussianBlur(img, (0, 0), sigma)


def rotation(img, deg, rng):
    if deg == 0:
        return img
    h, w = img.shape
    angle = deg if rng.random() < 0.5 else -deg
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return _white_border_warp(img, m, perspective=False)


def perspective(img, strength, rng):
    if strength == 0:
        return img
    h, w = img.shape
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    jitter = [(rng.uniform(0, strength) * w, rng.uniform(0, strength) * h) for _ in range(4)]
    signs = [(1, 1), (-1, 1), (-1, -1), (1, -1)]
    dst = np.float32([[x + sx * jx, y + sy * jy] for (x, y), (sx, sy), (jx, jy) in zip(src, signs, jitter)])
    m = cv2.getPerspectiveTransform(src, dst)
    return _white_border_warp(img, m, perspective=True)


def noise(img, sd, rng):
    if sd <= 0:
        return img
    nrng = np.random.default_rng(rng.randrange(2**32))
    out = img.astype(np.float32) + nrng.normal(0, sd, img.shape)
    return np.clip(out, 0, 255).astype(np.uint8)


def jpeg(img, quality, rng):
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, int(quality)])
    if not ok:
        raise RuntimeError("jpeg encode failed")
    return cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)


def downscale(img, factor, rng):
    if factor >= 1:
        return img
    h, w = img.shape
    return cv2.resize(img, (max(1, int(w * factor)), max(1, int(h * factor))), interpolation=cv2.INTER_AREA)


def occlusion(img, fraction, rng, barcode_box: Box = None):
    if fraction <= 0 or barcode_box is None:
        return img
    x0, y0, x1, y1 = barcode_box
    width = int((x1 - x0) * fraction)
    start = rng.randint(x0, x1 - width)
    out = img.copy()
    # a vertical band over the bars only, the printed digits stay visible
    out[y0:y1, start:start + width] = 255
    return out


APPLY = {
    "blur": blur,
    "rotation": rotation,
    "perspective": perspective,
    "noise": noise,
    "jpeg": jpeg,
    "downscale": downscale,
    "occlusion": occlusion,
}


def degrade(img: np.ndarray, kind: str, level: float, rng: random.Random, barcode_box: Box = None) -> np.ndarray:
    fn = APPLY[kind]
    if kind == "occlusion":
        return fn(img, level, rng, barcode_box=barcode_box)
    return fn(img, level, rng)
