import string
from typing import Callable, List, Tuple

ERASURE = "?"

# common OCR confusions inside a field that should only hold digits
DIGIT_CONFUSIONS = str.maketrans({"O": "0", "o": "0", "D": "0", "Q": "0", "I": "1", "l": "1",
                                  "|": "1", "i": "1", "Z": "2", "z": "2", "S": "5", "s": "5",
                                  "G": "6", "B": "8", "g": "9", "q": "9"})


def _alphabet(position_char: str) -> str:
    return string.ascii_uppercase if position_char.isalpha() else string.digits


def fill_erasures(code: str, is_valid: Callable[[str], bool], alphabet: str = string.digits,
                  max_erasures: int = 2) -> List[str]:
    holes = [i for i, c in enumerate(code) if c == ERASURE]
    if not holes or len(holes) > max_erasures:
        return []
    out = [code]
    for i in holes:
        out = [s[:i] + a + s[i + 1:] for s in out for a in alphabet]
    return [s for s in out if is_valid(s)]


def single_error_candidates(code: str, is_valid: Callable[[str], bool]) -> List[str]:
    found = set()
    for i, c in enumerate(code):
        for a in _alphabet(c):
            if a != c:
                s = code[:i] + a + code[i + 1:]
                if is_valid(s):
                    found.add(s)
    for i in range(len(code) - 1):
        if code[i] != code[i + 1]:
            s = code[:i] + code[i + 1] + code[i] + code[i + 2:]
            if is_valid(s):
                found.add(s)
    return sorted(found)


def length_error_candidates(code: str, expected_len: int, is_valid: Callable[[str], bool],
                            alphabets: List[str]) -> List[str]:
    """OCR also inserts and drops characters, which a check digit was never
    designed for. One extra char: try every deletion. One missing char: try
    every insertion, with the alphabet of the position it would land on."""
    found = set()
    if len(code) == expected_len + 1:
        for i in range(len(code)):
            s = code[:i] + code[i + 1:]
            if ERASURE not in s and is_valid(s):
                found.add(s)
    elif len(code) == expected_len - 1 and ERASURE not in code:
        for i in range(len(code) + 1):
            for a in alphabets[i]:
                s = code[:i] + a + code[i:]
                if is_valid(s):
                    found.add(s)
    return sorted(found)
