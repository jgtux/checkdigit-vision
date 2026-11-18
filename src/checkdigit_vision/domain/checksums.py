import string
from typing import Optional

IBAN_LENGTHS = {
    "BE": 16, "BR": 29, "CH": 21, "DE": 22, "ES": 24, "FR": 27,
    "GB": 22, "IT": 27, "NL": 18, "NO": 15, "PT": 25,
}


def _digits(s: str) -> Optional[list]:
    if not s or not s.isdigit():
        return None
    return [int(c) for c in s]


def gtin_check_digit(body: str) -> int:
    ds = _digits(body)
    if ds is None:
        raise ValueError(f"not a digit string: {body!r}")
    # weights start at 3 from the rightmost body digit, so the same function
    # covers EAN-8, UPC-A (12) and EAN-13
    total = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(ds)))
    return (10 - total % 10) % 10


def is_valid_gtin(code: str) -> bool:
    if len(code) not in (8, 12, 13, 14) or not code.isdigit():
        return False
    return gtin_check_digit(code[:-1]) == int(code[-1])


def is_valid_ean13(code: str) -> bool:
    return len(code) == 13 and is_valid_gtin(code)


def is_valid_upca(code: str) -> bool:
    return len(code) == 12 and is_valid_gtin(code)


def is_valid_isbn13(code: str) -> bool:
    return code[:3] in ("978", "979") and is_valid_ean13(code)


def isbn10_check_char(body: str) -> str:
    ds = _digits(body)
    if ds is None or len(ds) != 9:
        raise ValueError(f"isbn-10 body must be 9 digits: {body!r}")
    total = sum(d * w for d, w in zip(ds, range(10, 1, -1)))
    check = (11 - total % 11) % 11
    return "X" if check == 10 else str(check)


def is_valid_isbn10(code: str) -> bool:
    if len(code) != 10 or not code[:9].isdigit():
        return False
    return isbn10_check_char(code[:9]) == code[9].upper()


def _iban_to_int(rearranged: str) -> int:
    out = []
    for c in rearranged:
        if c.isdigit():
            out.append(c)
        elif c in string.ascii_uppercase:
            out.append(str(ord(c) - ord("A") + 10))
        else:
            raise ValueError(f"invalid iban char: {c!r}")
    return int("".join(out))


def normalize_iban(iban: str) -> str:
    return iban.replace(" ", "").upper()


def iban_check_digits(country: str, bban: str) -> str:
    n = _iban_to_int(normalize_iban(bban) + country.upper() + "00")
    return f"{98 - n % 97:02d}"


def is_valid_iban(iban: str) -> bool:
    s = normalize_iban(iban)
    if len(s) < 5 or not s[:2].isalpha() or not s[2:4].isdigit():
        return False
    expected = IBAN_LENGTHS.get(s[:2])
    if expected is not None and len(s) != expected:
        return False
    try:
        return _iban_to_int(s[4:] + s[:4]) % 97 == 1
    except ValueError:
        return False
