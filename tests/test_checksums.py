import random

import pytest

from checkdigit_vision.domain.checksums import (
    gtin_check_digit,
    iban_check_digits,
    is_valid_ean13,
    is_valid_gtin,
    is_valid_iban,
    is_valid_isbn10,
    is_valid_isbn13,
    is_valid_upca,
    isbn10_check_char,
)

RNG = random.Random(20261118)


def random_ean13() -> str:
    body = "".join(str(RNG.randint(0, 9)) for _ in range(12))
    return body + str(gtin_check_digit(body))


def single_substitutions(code: str, positions):
    for i in positions:
        for d in "0123456789":
            if d != code[i]:
                yield code[:i] + d + code[i + 1:]


def adjacent_swaps(code: str, positions):
    for i in positions:
        a, b = code[i], code[i + 1]
        if a != b:
            yield (a, b), code[:i] + b + a + code[i + 2:]


@pytest.mark.parametrize("code", ["4006381333931", "9780306406157", "5901234123457"])
def test_known_ean13(code):
    assert is_valid_ean13(code)


def test_known_upca():
    assert is_valid_upca("036000291452")
    assert not is_valid_upca("036000291453")


def test_known_isbn():
    assert is_valid_isbn13("9780306406157")
    assert not is_valid_isbn13("4006381333931")
    assert is_valid_isbn10("0306406152")
    assert isbn10_check_char("030640615") == "2"


def test_isbn10_x_check():
    body = next(
        b for b in (f"{n:09d}" for n in range(1000, 100000)) if isbn10_check_char(b) == "X"
    )
    assert is_valid_isbn10(body + "X")
    assert is_valid_isbn10(body + "x")


@pytest.mark.parametrize(
    "iban",
    ["GB82 WEST 1234 5698 7654 32", "DE89 3704 0044 0532 0130 00", "GB82WEST12345698765432"],
)
def test_known_iban(iban):
    assert is_valid_iban(iban)


def test_iban_check_digits_roundtrip():
    assert iban_check_digits("GB", "WEST12345698765432") == "82"
    assert iban_check_digits("DE", "370400440532013000") == "89"


def test_iban_rejects_bad_length_and_chars():
    assert not is_valid_iban("GB82WEST1234569876543")
    assert not is_valid_iban("GB82WEST1234569876543!")
    assert not is_valid_iban("")


@pytest.mark.parametrize("bad", ["", "abc", "123", "40063813339310"[:11]])
def test_gtin_rejects_garbage(bad):
    assert not is_valid_gtin(bad)


def test_gtin_detects_every_single_digit_error():
    for _ in range(200):
        code = random_ean13()
        for wrong in single_substitutions(code, range(13)):
            assert not is_valid_ean13(wrong), (code, wrong)


def test_gtin_adjacent_swaps_escape_only_when_digits_differ_by_5():
    escaped = set()
    for _ in range(500):
        code = random_ean13()
        for pair, swapped in adjacent_swaps(code, range(12)):
            if is_valid_ean13(swapped):
                escaped.add(pair)
    assert escaped
    assert all(abs(int(a) - int(b)) == 5 for a, b in escaped)


def test_isbn10_detects_single_errors_and_adjacent_swaps():
    for n in range(0, 10**9, 7_919_993):
        body = f"{n:09d}"
        code = body + isbn10_check_char(body)
        for wrong in single_substitutions(code, range(9)):
            assert not is_valid_isbn10(wrong)
        for _, swapped in adjacent_swaps(code, range(9)):
            assert not is_valid_isbn10(swapped)


def test_iban_detects_digit_substitutions_and_adjacent_swaps():
    code = "GB82WEST12345698765432"
    digit_pos = [i for i, c in enumerate(code) if c.isdigit()]
    for wrong in single_substitutions(code, digit_pos):
        assert not is_valid_iban(wrong)
    swap_pos = [i for i in digit_pos if i + 1 in digit_pos]
    for _, swapped in adjacent_swaps(code, swap_pos):
        assert not is_valid_iban(swapped)
