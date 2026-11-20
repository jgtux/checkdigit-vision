"""Cover image for the article: label 0 under one level of each degradation.

Uses the same seeds as analysis/read_rates.py, so every tile is an image the
experiment actually read.
usage: cover_mosaic.py <out.webp>
"""
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from checkdigit_vision.domain.degrade import LEVELS, degrade  # noqa: E402
from checkdigit_vision.domain.generate import random_ean13, random_iban  # noqa: E402
from checkdigit_vision.infrastructure.render import FONT_PATH, render_label  # noqa: E402

SEED, IDX = 20261118, 0
TILES = [
    ("blur", 0, "clean"),
    ("blur", 3, "blur sigma 3"),
    ("rotation", 12, "rotation 12 deg"),
    ("perspective", 0.12, "perspective 12%"),
    ("noise", 50, "noise sd 50"),
    ("jpeg", 12, "jpeg quality 12"),
    ("downscale", 0.4, "downscale x0.4"),
    ("occlusion", 0.35, "barcode 35% covered"),
]
W, H = 1900, 700
BG = 236
TW, TH = 440, 274          # tile; the 2px border is drawn over its edge
X0, Y0, DX, DY = 28, 28, 468, 336


def tile(label, kind, level):
    # level must be the LEVELS value itself: the seed string is "12", not "12.0"
    assert level in LEVELS[kind], (kind, level)
    rng = random.Random(f"{SEED}:{kind}:{level}:{IDX}")
    img = degrade(np.array(label.image), kind, level, rng, barcode_box=label.barcode_box)
    return Image.fromarray(img).resize((TW, TH), Image.LANCZOS)


def main(out):
    lrng = random.Random(f"{SEED}:label:{IDX}")
    label = render_label(random_ean13(lrng), random_iban(lrng), item_no=IDX)
    canvas = Image.new("L", (W, H), BG)
    d = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(FONT_PATH, 22)
    for i, (kind, level, caption) in enumerate(TILES):
        x, y = X0 + (i % 4) * DX, Y0 + (i // 4) * DY
        canvas.paste(tile(label, kind, level), (x, y))
        d.rectangle([x - 1, y - 1, x + TW, y + TH], outline=0, width=2)
        d.text((x, y + TH + 6), caption, font=font, fill=0)
    canvas.convert("RGB").save(out, quality=90)


if __name__ == "__main__":
    main(sys.argv[1])
