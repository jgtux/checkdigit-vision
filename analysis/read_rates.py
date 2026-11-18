# %% [markdown]
# # Read rates under degradation
#
# Every synthetic label carries the same identifiers twice: once as a symbol
# (EAN-13 barcode, QR code with an IBAN) and once as printed text. Each label
# is degraded one factor at a time and read three ways: symbol decoding
# (pyzbar), OCR on the raw image and OCR after preprocessing (Tesseract).
# Failed OCR reads go through checksum repair. Ground truth is exact because
# the labels are generated.

# %%
import hashlib
import json
import platform
import subprocess
import sys
from multiprocessing import Pool
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent if "__file__" in globals() else Path.cwd().parent
sys.path.insert(0, str(ROOT / "src"))

from checkdigit_vision.application.experiment import init_worker, run_one, tasks  # noqa: E402
from checkdigit_vision.infrastructure.render import FONT_PATH  # noqa: E402

SEED = 20261118
N = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 40
WORKERS = 12
OUT = ROOT / "results"
OUT.mkdir(exist_ok=True)

# %%
if __name__ == "__main__":
    work = tasks(SEED, N)
    with Pool(WORKERS, initializer=init_worker) as pool:
        rows = pool.map(run_one, work, chunksize=4)

    df = pd.DataFrame(rows).sort_values(["kind", "level", "idx"]).reset_index(drop=True)
    # wall time is the only non-deterministic column: kept apart so the
    # results file hashes the same on every run with the same seed
    df[["kind", "level", "idx", "seconds"]].to_csv(OUT / "timings.csv", index=False)
    df = df.drop(columns=["seconds"])
    csv_path = OUT / "read_rates.csv"
    df.to_csv(csv_path, index=False)

    rate_cols = [c for c in df.columns if c.endswith("_ok") or c.endswith("_hit")]
    summary = df.groupby(["kind", "level"])[rate_cols].mean()
    for field in ("ean", "iban"):
        for o in ("correct", "wrong", "rejected"):
            summary[f"final_{field}_{o}"] = df.groupby(["kind", "level"])[f"final_{field}_outcome"].apply(
                lambda s, o=o: (s == o).mean())
    summary.round(4).to_csv(OUT / "summary.csv")

    tess = subprocess.run(["tesseract", "--version"], capture_output=True, text=True).stdout.splitlines()[0]
    meta = {
        "seed": SEED,
        "n_per_level": N,
        "images": len(df),
        "python": platform.python_version(),
        "tesseract": tess,
        "font": FONT_PATH,
        "font_sha256": hashlib.sha256(Path(FONT_PATH).read_bytes()).hexdigest(),
        "platform": platform.platform(),
        "read_rates_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
    }
    (OUT / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta, indent=2))
