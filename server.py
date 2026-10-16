"""HTTP service for the internal Docker network. n8n calls it; it is never published to the internet.

POST /filter?seed=<slug>[&accent=violet|red][&stroke=thin|thick]   body = image bytes
  -> 200 image/png (exact palette, no metadata), X-Variant header with the chosen variant
GET  /health -> 200 ok
"""
import hashlib
import io
import json
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import cv2
import numpy as np
from PIL import Image

from brand_filter import apply_brand_filter
from line_art import line_map

MAX_BODY_BYTES = 20 * 1024 * 1024
MAX_WIDTH = 1600
LINE_MODEL_MAX_SIDE = 768  # the line model uses ~1 GB per megapixel; run it small and upscale the map
MODELS_DIR = os.environ.get("MODELS_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "models"))
STROKES = ("thin", "thick")
ACCENTS = ("violet", "red")

nets = {}
line_model_lock = threading.Lock()  # an OpenCV net handles one image at a time; also caps memory


def load_nets():
    for stroke in STROKES:
        nets[stroke] = cv2.dnn.readNetFromONNX(f"{MODELS_DIR}/stroke_{stroke}.onnx")


def choose_variant(seed, query):
    """The seed picks the variant; the query may force accent or stroke."""
    digest = hashlib.sha256(seed.encode()).digest()
    variant = {"accent": ACCENTS[digest[0] % 2], "stroke": STROKES[digest[1] % 2],
               "cell": (8, 9, 11)[digest[2] % 3], "grain": (0.015, 0.025, 0.035)[digest[3] % 3]}
    for key, allowed in (("accent", ACCENTS), ("stroke", STROKES)):
        value = query.get(key, [None])[0]
        if value in allowed:
            variant[key] = value
    return variant


def crop_to_multiple_of_8(rgb):
    return np.ascontiguousarray(rgb[: rgb.shape[0] // 8 * 8, : rgb.shape[1] // 8 * 8])


def process(image_bytes, seed, query):
    rgb = np.array(Image.open(io.BytesIO(image_bytes)).convert("RGB"))
    if rgb.shape[1] > MAX_WIDTH:
        scale = MAX_WIDTH / rgb.shape[1]
        rgb = cv2.resize(rgb, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    rgb = crop_to_multiple_of_8(rgb)
    if min(rgb.shape[:2]) < 8:
        raise ValueError("image is smaller than 8 px")
    variant = choose_variant(seed, query)

    scale = min(1, LINE_MODEL_MAX_SIDE / max(rgb.shape[:2]))
    small = crop_to_multiple_of_8(cv2.resize(rgb, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA))
    with line_model_lock:
        lines = line_map(nets[variant["stroke"]], small)
    lines = cv2.resize(lines, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_LINEAR)
    strokes = cv2.dilate((lines < 0.75).astype(np.uint8), np.ones((2, 2), np.uint8)) > 0

    seed_int = int.from_bytes(hashlib.sha256(seed.encode()).digest()[:4], "big")
    out = apply_brand_filter(rgb, variant["accent"], cell=variant["cell"], seed=seed_int,
                             lines=strokes, grain=variant["grain"])
    buffer = io.BytesIO()
    Image.fromarray(out).save(buffer, format="PNG", optimize=True)  # PIL writes no EXIF or text chunks here
    return buffer.getvalue(), variant


class Handler(BaseHTTPRequestHandler):
    def send(self, code, body, content_type="text/plain", headers=None):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if urlparse(self.path).path == "/health":
            return self.send(200, b"ok")
        self.send(404, b"not found")

    def do_POST(self):
        url = urlparse(self.path)
        if url.path != "/filter":
            return self.send(404, b"not found")
        query = parse_qs(url.query)
        seed = query.get("seed", [""])[0]
        length = int(self.headers.get("Content-Length") or 0)
        if not seed or not 0 < length <= MAX_BODY_BYTES:
            return self.send(400, b"missing seed, or body is empty or over 20 MB")
        try:
            png, variant = process(self.rfile.read(length), seed, query)
        except (OSError, ValueError) as error:  # unreadable image or impossible size
            return self.send(422, f"cannot process image: {error}".encode())
        file_name = re.sub(r"[^a-z0-9-]", "", seed.lower())[:80] or "image"  # Ghost needs an image extension
        self.send(200, png, "image/png", {"X-Variant": json.dumps(variant),
                                          "Content-Disposition": f'inline; filename="{file_name}.png"'})


if __name__ == "__main__":
    load_nets()
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", 8000))), Handler).serve_forever()
