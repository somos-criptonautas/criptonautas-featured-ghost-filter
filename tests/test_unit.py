"""Fast checks without the line models: python -m unittest discover tests"""
import io
import unittest

import numpy as np
from PIL import Image

import server
from brand_filter import PALETTE, apply_brand_filter


class FakeNet:
    """Stands in for the OpenCV net: returns a blank line map of the input size."""

    def setInput(self, x):
        self.shape = x.shape[2:]

    def forward(self):
        return np.ones((1, 1, *self.shape), np.float32)


def sample_image(width=640, height=480):
    rng = np.random.default_rng(1)
    gradient = np.linspace(0, 255, width, dtype=np.uint8)[None, :, None].repeat(height, 0).repeat(3, 2)
    noise = rng.integers(0, 40, (height, width, 3), dtype=np.uint8)
    buffer = io.BytesIO()
    Image.fromarray(gradient // 2 + noise).save(buffer, format="JPEG")
    return buffer.getvalue()


class BrandFilterTest(unittest.TestCase):
    def test_output_uses_only_the_palette(self):
        rgb = np.array(Image.open(io.BytesIO(sample_image())))
        for accent in ("violet", "red"):
            out = apply_brand_filter(rgb, accent)
            self.assertLessEqual({tuple(c) for c in out.reshape(-1, 3)}, PALETTE)


class VariantTest(unittest.TestCase):
    def test_same_seed_same_variant(self):
        self.assertEqual(server.choose_variant("a-post", {}), server.choose_variant("a-post", {}))

    def test_query_forces_accent_and_stroke(self):
        variant = server.choose_variant("a-post", {"accent": ["red"], "stroke": ["thin"]})
        self.assertEqual((variant["accent"], variant["stroke"]), ("red", "thin"))

    def test_unknown_values_are_ignored(self):
        self.assertEqual(server.choose_variant("a-post", {"accent": ["green"]}), server.choose_variant("a-post", {}))


class ProcessTest(unittest.TestCase):
    def setUp(self):
        server.nets.update(thin=FakeNet(), thick=FakeNet())

    def test_png_is_deterministic_and_clean(self):
        png, _ = server.process(sample_image(), "a-post", {})
        self.assertEqual(png, server.process(sample_image(), "a-post", {})[0])
        image = Image.open(io.BytesIO(png))
        self.assertEqual(image.format, "PNG")
        self.assertFalse({"exif", "icc_profile", "XML:com.adobe.xmp"} & set(image.info))

    def test_large_image_is_resized(self):
        png, _ = server.process(sample_image(2000, 1000), "a-post", {})
        self.assertEqual(Image.open(io.BytesIO(png)).size, (1600, 800))

    def test_unreadable_image_raises(self):
        with self.assertRaises(OSError):
            server.process(b"not an image", "a-post", {})


if __name__ == "__main__":
    unittest.main()
