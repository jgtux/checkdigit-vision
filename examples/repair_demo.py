"""Checksum repair: one erasure has one answer, one unknown error has many."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from checkdigit_vision.domain.checksums import is_valid_ean13  # noqa: E402
from checkdigit_vision.domain.repair import fill_erasures, single_error_candidates  # noqa: E402

truth = "4006381333931"

# OCR could not read the 5th digit at all
print(fill_erasures("4006?81333931", is_valid_ean13))

# OCR read the 8th digit as 8 instead of 3
candidates = single_error_candidates("4006381833931", is_valid_ean13)
print(len(candidates), truth in candidates)
print(candidates[:4])
