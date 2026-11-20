"""The IBAN that OCR misread in 4 places and still passed mod 97."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from checkdigit_vision.domain.checksums import is_valid_iban  # noqa: E402

printed = "GB78AZTR29158378389299"
ocr = "GB78AZIR20158378385290"

print(is_valid_iban(printed), is_valid_iban(ocr))
print(sum(a != b for a, b in zip(printed, ocr)), "characters differ")
