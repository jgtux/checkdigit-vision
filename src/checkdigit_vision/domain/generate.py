import random
import string

from .checksums import gtin_check_digit, iban_check_digits


def random_ean13(rng: random.Random) -> str:
    body = "".join(str(rng.randint(0, 9)) for _ in range(12))
    return body + str(gtin_check_digit(body))


def random_iban(rng: random.Random) -> str:
    # synthetic only: GB has a 4-letter bank code (mixed letters/digits),
    # DE is all digits, so both alphabets show up in the experiment
    if rng.random() < 0.5:
        bban = "".join(rng.choice(string.ascii_uppercase) for _ in range(4))
        bban += "".join(str(rng.randint(0, 9)) for _ in range(14))
        country = "GB"
    else:
        bban = "".join(str(rng.randint(0, 9)) for _ in range(18))
        country = "DE"
    return country + iban_check_digits(country, bban) + bban


def group(s: str, size: int = 4) -> str:
    return " ".join(s[i:i + size] for i in range(0, len(s), size))


def ean13_human(ean: str) -> str:
    return f"{ean[0]} {ean[1:7]} {ean[7:]}"
