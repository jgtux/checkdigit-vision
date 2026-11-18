import string
from dataclasses import dataclass, asdict
from typing import List, Optional

import cv2
import numpy as np
import pytesseract
from pyzbar import pyzbar

from ..domain.checksums import is_valid_ean13, is_valid_iban
from ..domain.extract import IBAN_MASKS, apply_mask, extract_ean, extract_iban, mask_alphabets
from ..domain.repair import ERASURE, fill_erasures, length_error_candidates, single_error_candidates


def decode_symbols(img: np.ndarray) -> dict:
    out = {"ean": None, "iban": None}
    for sym in pyzbar.decode(img):
        data = sym.data.decode("ascii", errors="replace")
        if sym.type == "EAN13":
            out["ean"] = data
        elif sym.type == "QRCODE" and data.startswith("IBAN:"):
            out["iban"] = data[5:]
    return out


def _rotate(img: np.ndarray, angle: float, border: int = 255) -> np.ndarray:
    h, w = img.shape
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_CUBIC, borderValue=border)


def skew_angle(img: np.ndarray, max_angle: float = 40.0) -> float:
    # projection profile: text lines are sharpest (highest row-sum variance)
    # when they are horizontal. minAreaRect over all dark pixels was fooled
    # by the barcode and the QR code dominating the ink.
    small = cv2.resize(img, (img.shape[1] // 3, img.shape[0] // 3), interpolation=cv2.INTER_AREA)
    _, bw = cv2.threshold(small, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    def score(a):
        return float(np.var(_rotate(bw, a, border=0).sum(axis=1)))

    coarse = max(np.arange(-max_angle, max_angle + 0.1, 1.0), key=score)
    fine = max(np.arange(coarse - 1, coarse + 1.01, 0.1), key=score)
    return float(fine)


def deskew(img: np.ndarray) -> np.ndarray:
    angle = skew_angle(img)
    return img if abs(angle) < 0.3 else _rotate(img, angle)


def preprocess(img: np.ndarray) -> np.ndarray:
    # grayscale -> contrast -> adaptive threshold, the chain from my old
    # imgnpdf_preprocessor snippet, plus upscaling and deskew in front of it
    h, w = img.shape
    if w < 1800:
        scale = 1800 / w
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)
    img = deskew(img)
    img = cv2.convertScaleAbs(img, alpha=1.5, beta=0)
    img = cv2.medianBlur(img, 3)
    bw = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15)
    return remove_bars(bw)


def remove_bars(bw: np.ndarray) -> np.ndarray:
    # barcode bars read as "999999..." and confuse page segmentation; a
    # vertical opening keeps only strokes much taller than any glyph
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, bw.shape[0] // 8))
    bars = cv2.morphologyEx(255 - bw, cv2.MORPH_OPEN, kernel)
    return cv2.bitwise_or(bw, bars)


def ocr(img: np.ndarray) -> str:
    # psm 6 (one block) returns nothing on some clean labels, psm 11 (sparse
    # text) misses others; both texts go to the extractor, which prefers
    # reads that pass their checksum
    return "\n".join(pytesseract.image_to_string(img, lang="eng", config=f"--psm {p}") for p in (6, 11))


def iban_alphabets(code: str) -> Optional[List[str]]:
    mask = IBAN_MASKS.get(code[:2])
    if mask is None or len(code) != len(mask):
        return None
    return mask_alphabets(mask)


def iban_length_candidates(raw: str) -> List[str]:
    # raw is unmasked here (extract_iban only masks full-length reads), so
    # every deletion/insertion is masked before the checksum is tried
    mask = IBAN_MASKS.get(raw[:2])
    if mask is None or abs(len(raw) - len(mask)) != 1:
        return []
    found = set()
    tries = []
    if len(raw) == len(mask) + 1:
        tries = [raw[:i] + raw[i + 1:] for i in range(2, len(raw))]
    else:
        alphabets = mask_alphabets(mask)
        tries = [raw[:i] + a + raw[i:] for i in range(2, len(raw) + 1) for a in alphabets[i]]
    for s in tries:
        masked = s[:2] + apply_mask(s[2:], mask[2:])
        if ERASURE not in masked and is_valid_iban(masked):
            found.add(masked)
    return sorted(found)


def repair_ean(read: Optional[str]) -> dict:
    if read is None:
        return {"status": "no_read", "candidates": []}
    if len(read) != 13:
        cands = length_error_candidates(read, 13, is_valid_ean13, [string.digits] * 14)
        return {"status": "length", "candidates": cands}
    if ERASURE in read:
        return {"status": "erasure", "candidates": fill_erasures(read, is_valid_ean13)}
    if is_valid_ean13(read):
        return {"status": "valid", "candidates": [read]}
    return {"status": "error", "candidates": single_error_candidates(read, is_valid_ean13)}


def repair_iban(read: Optional[str]) -> dict:
    if read is None:
        return {"status": "no_read", "candidates": []}
    alphabets = iban_alphabets(read)
    if alphabets is None:
        return {"status": "length", "candidates": iban_length_candidates(read)}
    if ERASURE in read:
        holes = [i for i, c in enumerate(read) if c == ERASURE]
        if len(holes) > 2:
            return {"status": "erasure", "candidates": []}
        out = [read]
        for i in holes:
            out = [s[:i] + a + s[i + 1:] for s in out for a in alphabets[i]]
        return {"status": "erasure", "candidates": [s for s in out if is_valid_iban(s)]}
    if is_valid_iban(read):
        return {"status": "valid", "candidates": [read]}
    return {"status": "error", "candidates": single_error_candidates(read, is_valid_iban)}


@dataclass
class Decision:
    value: Optional[str]
    source: str  # symbol | ocr | repair | rejected


def decide(symbol: Optional[str], reps: List[dict], is_valid) -> Decision:
    """Cheapest trustworthy evidence first: a decoded symbol, then any OCR
    read (raw or preprocessed) that passes its checksum, and only then a
    repair that left exactly one candidate."""
    if symbol is not None and is_valid(symbol):
        return Decision(symbol, "symbol")
    for rep in reps:
        if rep["status"] == "valid":
            return Decision(rep["candidates"][0], "ocr")
    for rep in reps:
        if len(rep["candidates"]) == 1:
            return Decision(rep["candidates"][0], "repair")
    return Decision(None, "rejected")


def read_label(img: np.ndarray) -> dict:
    sym = decode_symbols(img)
    texts = {"pre": ocr(preprocess(img)), "raw": ocr(img)}

    out = {"sym_ean": sym["ean"], "sym_iban": sym["iban"]}
    for field, extract, repair, is_valid in (
        ("ean", extract_ean, repair_ean, is_valid_ean13),
        ("iban", extract_iban, repair_iban, is_valid_iban),
    ):
        reps = []
        for name in ("pre", "raw"):
            read = extract(texts[name])
            rep = repair(read)
            out[f"ocr_{name}_{field}"] = read
            out[f"rep_{name}_{field}"] = rep
            reps.append(rep)
        out[f"final_{field}"] = asdict(decide(sym[field], reps, is_valid))
    return out
