import random
import string

from checkdigit_vision.application.read import iban_length_candidates, repair_ean, repair_iban
from checkdigit_vision.domain.checksums import is_valid_ean13, is_valid_iban
from checkdigit_vision.domain.extract import extract_ean, extract_iban
from checkdigit_vision.domain.generate import random_ean13, random_iban
from checkdigit_vision.domain.repair import fill_erasures, length_error_candidates, single_error_candidates

RNG = random.Random(7)


def test_one_erasure_in_ean_has_exactly_one_fill():
    for _ in range(200):
        ean = random_ean13(RNG)
        i = RNG.randrange(13)
        holed = ean[:i] + "?" + ean[i + 1:]
        assert fill_erasures(holed, is_valid_ean13) == [ean]


def test_two_erasures_in_ean_are_ambiguous():
    ean = random_ean13(RNG)
    holed = "??" + ean[2:]
    assert len(fill_erasures(holed, is_valid_ean13)) > 1


def test_single_error_candidates_include_truth():
    for _ in range(50):
        ean = random_ean13(RNG)
        i = RNG.randrange(13)
        wrong = ean[:i] + str((int(ean[i]) + 1) % 10) + ean[i + 1:]
        assert ean in single_error_candidates(wrong, is_valid_ean13)


def test_length_error_candidates_recover_dropped_and_extra_digit():
    ean = random_ean13(RNG)
    dropped = ean[:5] + ean[6:]
    assert ean in length_error_candidates(dropped, 13, is_valid_ean13, [string.digits] * 14)
    extra = ean[:5] + "7" + ean[5:]
    assert ean in length_error_candidates(extra, 13, is_valid_ean13, [string.digits] * 14)


def test_iban_length_candidates_mask_letters_and_digits():
    for _ in range(30):
        iban = random_iban(RNG)
        extra = iban[:9] + "0" + iban[9:]
        assert iban in iban_length_candidates(extra)


def test_repair_statuses():
    ean = random_ean13(RNG)
    assert repair_ean(ean)["status"] == "valid"
    assert repair_ean(None)["status"] == "no_read"
    assert repair_ean(ean[:3] + "?" + ean[4:]) == {"status": "erasure", "candidates": [ean]}
    iban = random_iban(RNG)
    assert repair_iban(iban)["status"] == "valid"


def test_extract_prefers_checksum_valid_read():
    ean = random_ean13(RNG)
    bad = ean[:-1] + str((int(ean[-1]) + 1) % 10)
    text = f"{bad[0]} {bad[1:7]} {bad[7:]}\n999999999999\n{ean[0]} {ean[1:7]} {ean[7:]}"
    assert extract_ean(text) == ean


def test_extract_maps_ocr_confusions_by_position():
    iban = "GB82WEST12345698765432"
    assert is_valid_iban(iban)
    ocr = "IBAN GB82 WE5T 1Z34 S698 7654 32"
    assert extract_iban(ocr) == iban
