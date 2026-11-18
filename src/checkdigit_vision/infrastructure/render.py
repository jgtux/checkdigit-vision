import os
from dataclasses import dataclass
from typing import Tuple

import qrcode
from barcode import EAN13
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFont

from ..domain.generate import ean13_human, group

DEFAULT_FONT = "/usr/share/fonts/liberation/LiberationMono-Regular.ttf"
FONT_PATH = os.environ.get("CHECKDIGIT_FONT", DEFAULT_FONT)

WIDTH, HEIGHT = 900, 560

Box = Tuple[int, int, int, int]


@dataclass
class Label:
    image: Image.Image
    ean: str
    iban: str
    barcode_box: Box
    qr_box: Box


def _font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_PATH, size)


def _barcode(ean: str) -> Image.Image:
    code = EAN13(ean[:12], writer=ImageWriter())
    if code.get_fullcode() != ean:
        raise ValueError(f"python-barcode disagrees on check digit: {ean}")
    img = code.render(
        writer_options={
            "module_width": 0.33,
            "module_height": 18.0,
            "quiet_zone": 4.0,
            "write_text": False,
            "dpi": 200,
        }
    )
    return img.convert("L")


def _qr(payload: str) -> Image.Image:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=6, border=4)
    qr.add_data(payload)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").get_image().convert("L")


def render_label(ean: str, iban: str, item_no: int = 1) -> Label:
    img = Image.new("L", (WIDTH, HEIGHT), 255)
    draw = ImageDraw.Draw(img)

    draw.text((40, 30), f"ITEM {item_no:04d}  /  SYNTHETIC LABEL", font=_font(28), fill=0)

    bc = _barcode(ean)
    bx, by = 40, 100
    img.paste(bc, (bx, by))
    barcode_box = (bx, by, bx + bc.width, by + bc.height)
    draw.text((bx + 20, by + bc.height + 8), ean13_human(ean), font=_font(36), fill=0)

    qr = _qr(f"IBAN:{iban}")
    qx, qy = WIDTH - qr.width - 30, 90
    img.paste(qr, (qx, qy))
    qr_box = (qx, qy, qx + qr.width, qy + qr.height)

    draw.text((40, HEIGHT - 90), "IBAN " + group(iban), font=_font(30), fill=0)

    return Label(image=img, ean=ean, iban=iban, barcode_box=barcode_box, qr_box=qr_box)
