import re
import string
from typing import List, Optional

from .checksums import is_valid_ean13, is_valid_iban
from .repair import DIGIT_CONFUSIONS, ERASURE

# per-country IBAN shape: L = letter, D = digit (only the two countries generated)
IBAN_MASKS = {
    "GB": "LLDDLLLLDDDDDDDDDDDDDD",
    "DE": "LLDDDDDDDDDDDDDDDDDDDD",
}

LETTER_CONFUSIONS = str.maketrans({"0": "O", "1": "I", "2": "Z", "5": "S", "8": "B", "6": "G"})


def mask_alphabets(mask: str) -> List[str]:
    return [string.ascii_uppercase if m == "L" else string.digits for m in mask]


def apply_mask(raw: str, mask: str) -> str:
    out = []
    for c, m in zip(raw, mask):
        if m == "D":
            c = c.translate(DIGIT_CONFUSIONS)
            out.append(c if c.isdigit() else ERASURE)
        else:
            c = c.upper().translate(LETTER_CONFUSIONS)
            out.append(c if c.isalpha() and c.isascii() else ERASURE)
    return "".join(out)


def _pick(cands: List[str], expected_len: Optional[int], is_valid) -> Optional[str]:
    # the text holds several attempts at the same field (two page
    # segmentation modes): prefer one that passes the checksum, then one
    # of the right length, then the first seen
    if not cands:
        return None
    for c in cands:
        if ERASURE not in c and is_valid(c):
            return c
    if expected_len is not None:
        for c in cands:
            if len(c) == expected_len:
                return c
    return cands[0]


def ean_candidates(text: str) -> List[str]:
    out = []
    for line in text.splitlines():
        s = re.sub(r"\s+", "", line)
        if not s or "BAN" in s.upper():
            continue
        norm = "".join(c if c.isdigit() else ERASURE for c in s.translate(DIGIT_CONFUSIONS))
        digits = sum(c.isdigit() for c in norm)
        if 12 <= len(norm) <= 14 and digits >= len(norm) - 2 and len(set(norm)) > 2:
            out.append(norm)
    return out


def iban_candidates(text: str) -> List[str]:
    out = []
    for line in text.splitlines():
        m = re.search(r"[I1l|]?BAN\s*(.*)", line, flags=re.IGNORECASE)
        if not m:
            continue
        s = re.sub(r"[^A-Za-z0-9|]", "", m.group(1))
        if len(s) < 4:
            continue
        country = s[:2].upper().translate(LETTER_CONFUSIONS)
        mask = IBAN_MASKS.get(country)
        if mask is not None and len(s) == len(mask):
            out.append(country + apply_mask(s[2:], mask[2:]))
        else:
            out.append(country + s[2:].upper())
    return out


def extract_ean(text: str) -> Optional[str]:
    return _pick(ean_candidates(text), 13, is_valid_ean13)


def extract_iban(text: str) -> Optional[str]:
    cands = iban_candidates(text)
    lens = {c[:2]: len(IBAN_MASKS[c[:2]]) for c in cands if c[:2] in IBAN_MASKS}
    expected = next(iter(lens.values()), None)
    return _pick(cands, expected, is_valid_iban)
