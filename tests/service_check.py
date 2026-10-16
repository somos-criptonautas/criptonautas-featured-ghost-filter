"""End-to-end check against a running container: SERVICE_URL=http://127.0.0.1:8000 python tests/service_check.py"""
import io
import json
import os
import sys
import urllib.error
import urllib.request

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from brand_filter import PALETTE  # noqa: E402
from tests.test_unit import sample_image  # noqa: E402

BASE_URL = os.environ.get("SERVICE_URL", "http://127.0.0.1:8000")


def post(path, body):
    request = urllib.request.Request(BASE_URL + path, data=body, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return response.status, response.read(), response.headers
    except urllib.error.HTTPError as error:
        return error.code, error.read(), error.headers


image = sample_image(1920, 1080)
code, png, headers = post("/filter?seed=test-post", image)
assert code == 200, (code, png[:200])
output = Image.open(io.BytesIO(png))
assert output.size == (1600, 896), output.size
assert {tuple(c) for c in np.array(output).reshape(-1, 3)} <= PALETTE, "colors outside the palette"
assert not {"exif", "icc_profile", "XML:com.adobe.xmp"} & set(output.info), output.info
assert headers["Content-Disposition"] == 'inline; filename="test-post.png"', headers["Content-Disposition"]
assert post("/filter?seed=test-post", image)[1] == png, "same seed must give the same image"

forced = json.loads(post("/filter?seed=test-post&accent=red&stroke=thin", image)[2]["X-Variant"])
assert (forced["accent"], forced["stroke"]) == ("red", "thin"), forced
assert post("/filter", image)[0] == 400
assert post("/filter?seed=x", b"not an image")[0] == 422
print("ok", json.loads(headers["X-Variant"]))
