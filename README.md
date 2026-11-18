# checkdigit-vision

Reading check-digit codes (EAN-13 barcodes, IBANs in QR codes) from degraded
images: symbol decoding first, OCR as fallback, checksum validation and
repair last, measured on synthetic labels with exact ground truth.

Companion code for a [fugu.cafe](https://fugu.cafe) article.

---

# Philosophy

## A check digit detects, it doesn't correct

EAN-13's check digit catches every single-digit error and every adjacent swap
except digits that differ by 5. IBAN's mod-97 catches every single
substitution and every swap of adjacent digits (97 is prime and divides
none of the differences those errors make). Neither was designed to *fix* anything:
one equation can't recover an unknown position. This project measures what
happens when you use them to repair OCR anyway.

## Synthetic on purpose

Every label is generated, so ground truth is exact and nothing private is
read. The cost is realism: one font, one layout, no paper texture, no
lighting. The numbers here describe this setup, not every camera in the world.

## Numbers only from code that ran

Every rate in this README and in the article comes from `results/`, written
by `analysis/read_rates.py` with a fixed seed. The results file hashes the
same on every run (wall time is kept in a separate file for that reason).

---

# Pipeline

```
 synthetic label (PIL)               domain/generate.py, infrastructure/render.py
   EAN-13 barcode + printed digits
   QR "IBAN:..." + printed IBAN
        │
        ▼
 one degradation, one level          domain/degrade.py
   blur, rotation, perspective, noise,
   jpeg, downscale, barcode occlusion
        │
        ▼
 read                                application/read.py
   1. pyzbar: EAN-13 and QR
   2. Tesseract on the raw image
   3. Tesseract after preprocessing
      (upscale, projection-profile deskew,
       contrast, adaptive threshold,
       vertical-bar removal)
        │
        ▼
 decide                              application/read.py: decide()
   symbol → OCR read that passes its checksum
   → repair with exactly one candidate → reject
```

Repair (`domain/repair.py`) handles the error types OCR actually makes:
unreadable characters (erasures), substitutions, adjacent swaps, and one
inserted or dropped character.

---

# Results

Seed `20261118`, 7 degradations × 6 levels × 40 labels = 1680 images
(`results/policies.csv`):

| field | policy | correct | wrong | rejected |
|---|---|---:|---:|---:|
| EAN-13 | symbol only | 1040 | 0 | 640 |
| EAN-13 | + OCR (preprocessed) | 1423 | 0 | 257 |
| EAN-13 | + OCR (raw) | 1482 | 0 | 198 |
| EAN-13 | + checksum repair | 1492 | 12 | 176 |
| IBAN | symbol only | 1338 | 0 | 342 |
| IBAN | + OCR (preprocessed) | 1384 | 0 | 296 |
| IBAN | + OCR (raw) | 1397 | 1 | 282 |
| IBAN | + checksum repair | 1400 | 6 | 274 |

Repair added 10 correct EAN-13 reads and 12 wrong ones. The one wrong IBAN
accepted straight from OCR is a mod-97 collision: four characters misread
under the heaviest noise, and the checksum still closed.

Per-level rates are in `results/summary.csv`, and the charts are in `results/figures/`.

---

# Reproducing

System packages: `tesseract` with the `eng` language data, and `zbar`.
The font defaults to Liberation Mono; override it with `CHECKDIGIT_FONT`
(its sha256 is recorded in `results/meta.json`).

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python analysis/read_rates.py 40   # ~6 min on 12 workers
.venv/bin/python analysis/figures.py
```

---

# Testing

```sh
.venv/bin/pytest -q
```

Covers the checksums against published examples and exhaustive properties,
erasure/substitution/length repair, and OCR-text extraction.

---

# License

This project is licensed under the **GNU Affero General Public License v3.0**.

See the `LICENSE` file for full details.
