"""Criptonautas brand filter: exact 5-color palette, 45° halftone, ink lines and paper grain."""
import cv2
import numpy as np

INK = (0x14, 0x11, 0x0F)
PAPER = (0xE8, 0xE6, 0xE1)
GREY = (0x7E, 0x79, 0x73)
VIOLET = (0x46, 0x20, 0x8A)
RED = (0xC5, 0x38, 0x25)
PALETTE = {INK, PAPER, GREY, VIOLET, RED}
ACCENTS = {"violet": VIOLET, "red": RED}


def apply_brand_filter(rgb, accent, cell=9, seed=7, lines=None, grain=0.025):
    """rgb: uint8 HxWx3. lines: optional bool HxW stroke mask. Returns uint8 HxWx3 using only PALETTE."""
    h, w = rgb.shape[:2]
    gray = cv2.equalizeHist(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY))
    lightness = gray.astype(np.float32) / 255.0

    if lines is None:  # no line model: fall back to an adaptive threshold
        smooth = cv2.bilateralFilter(cv2.medianBlur(gray, 5), 9, 60, 60)
        lines = cv2.adaptiveThreshold(smooth, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 11, 4) == 0
    lines = cv2.GaussianBlur(lines.astype(np.float32), (3, 3), 0.8) > 0.45  # slight ink bleed

    # 45° halftone: dot radius grows with darkness
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    du = ((xx + yy) / np.sqrt(2)) % cell - cell / 2
    dv = ((xx - yy) / np.sqrt(2)) % cell - cell / 2
    darkness = np.clip((0.88 - lightness) / 0.63, 0, 1)
    dots = np.sqrt(du * du + dv * dv) < cell * 0.62 * np.sqrt(darkness)

    out = np.empty((h, w, 3), np.uint8)
    out[:] = PAPER
    out[dots] = ACCENTS[accent]
    out[lightness < 0.16] = INK  # deep shadows become solid ink
    out[lines] = INK

    # paper grain uses a palette color, so no new tones appear
    rng = np.random.default_rng(seed)
    is_paper = np.all(out == PAPER, axis=-1)
    out[is_paper & (rng.random((h, w)) < grain)] = GREY
    return out
