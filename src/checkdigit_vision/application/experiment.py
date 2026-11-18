import os
import random
import time
from typing import List

import numpy as np

from ..domain.degrade import LEVELS, degrade
from ..domain.generate import random_ean13, random_iban
from ..infrastructure.render import render_label
from .read import read_label


def outcome(value, truth) -> str:
    if value is None:
        return "rejected"
    return "correct" if value == truth else "wrong"


def run_one(task) -> dict:
    seed, kind, level, idx = task
    # same label for a given idx across every kind/level: paired design, so
    # differences between levels are not differences between labels
    lrng = random.Random(f"{seed}:label:{idx}")
    label = render_label(random_ean13(lrng), random_iban(lrng), item_no=idx)
    img = degrade(np.array(label.image), kind, level, random.Random(f"{seed}:{kind}:{level}:{idx}"),
                  barcode_box=label.barcode_box)

    t0 = time.perf_counter()
    r = read_label(img)
    seconds = time.perf_counter() - t0

    row = {"kind": kind, "level": level, "idx": idx, "ean": label.ean, "iban": label.iban,
           "seconds": round(seconds, 3)}
    for field, truth in (("ean", label.ean), ("iban", label.iban)):
        row[f"sym_{field}_read"] = r[f"sym_{field}"]
        row[f"sym_{field}_ok"] = r[f"sym_{field}"] == truth
        for name in ("raw", "pre"):
            read = r[f"ocr_{name}_{field}"]
            rep = r[f"rep_{name}_{field}"]
            row.update({
                f"{name}_{field}_read": read,
                f"{name}_{field}_ok": read == truth,
                f"{name}_{field}_status": rep["status"],
                f"{name}_{field}_n": len(rep["candidates"]),
                f"{name}_{field}_hit": truth in rep["candidates"],
            })
        row[f"final_{field}_source"] = r[f"final_{field}"]["source"]
        row[f"final_{field}_outcome"] = outcome(r[f"final_{field}"]["value"], truth)
    return row


def tasks(seed: int, n: int) -> List[tuple]:
    return [(seed, kind, level, idx) for kind, levels in LEVELS.items() for level in levels for idx in range(n)]


def init_worker():
    # tesseract is deterministic per call; one thread per process keeps it
    # from oversubscribing the cores the pool already uses
    os.environ["OMP_THREAD_LIMIT"] = "1"
