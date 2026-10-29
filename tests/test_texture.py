import os
import struct
import tempfile
import unittest
import zlib

from tests import _blender_stubs  # noqa: F401
from modules import texture


def read_png(path):
    """Return (width, height, rows) where rows[y] is a list of (r, g, b, a) tuples."""
    with open(path, "rb") as f:
        data = f.read()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG file"
    pos, idat = 8, b""
    width = height = None
    while pos < len(data):
        length, = struct.unpack(">I", data[pos:pos + 4])
        tag = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        if tag == b"IHDR":
            width, height, depth, color_type, _, _, _ = struct.unpack(">IIBBBBB", body)
            assert (depth, color_type) == (8, 6), "expected 8-bit RGBA"
        elif tag == b"IDAT":
            idat += body
        pos += 12 + length
    raw = zlib.decompress(idat)
    stride = width * 4 + 1
    rows = []
    for y in range(height):
        line = raw[y * stride:(y + 1) * stride]
        assert line[0] == 0, "expected unfiltered rows"
        px = line[1:]
        rows.append([tuple(px[x * 4:x * 4 + 4]) for x in range(width)])
    return width, height, rows


class WritePng(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "tex.png")

    def tearDown(self):
        self.dir.cleanup()

    def test_dimensions_match_request(self):
        texture.write_png(self.path, 64, 32, [])
        width, height, rows = read_png(self.path)
        self.assertEqual((width, height), (64, 32))
        self.assertEqual(len(rows), 32)

    def test_empty_texture_is_fully_transparent(self):
        texture.write_png(self.path, 32, 32, [])
        _, _, rows = read_png(self.path)
        self.assertTrue(all(px == (0, 0, 0, 0) for row in rows for px in row))

    def test_face_is_painted_with_its_color(self):
        texture.write_png(self.path, 32, 32, [(4, 6, 8, 5, "front", (200, 100, 50))])
        _, _, rows = read_png(self.path)
        expected = (200, 100, 50, 255)
        self.assertEqual(rows[6][4], expected)
        self.assertEqual(rows[10][8], expected)
        self.assertEqual(rows[5][4], (0, 0, 0, 0))   # just above the rectangle (y 6..10, x 4..11)
        self.assertEqual(rows[11][4], (0, 0, 0, 0))  # just below it
        self.assertEqual(rows[6][12], (0, 0, 0, 0))  # just right of it

    def test_rectangles_are_clipped_to_the_texture(self):
        texture.write_png(self.path, 8, 8, [(-2, 6, 4, 4, "front", (1, 2, 3))])
        _, _, rows = read_png(self.path)
        self.assertEqual(rows[7][1], (1, 2, 3, 255))
        self.assertEqual(rows[7][2], (0, 0, 0, 0))


class Pastel(unittest.TestCase):
    def test_same_key_same_color(self):
        self.assertEqual(texture.pastel("1:front"), texture.pastel("1:front"))

    def test_different_keys_differ(self):
        colors = {texture.pastel(f"{i}:{f}") for i in range(4)
                  for f in ("front", "back", "left", "right", "top", "bottom")}
        self.assertGreater(len(colors), 20)

    def test_colors_are_light_and_soft(self):
        for i in range(50):
            r, g, b = texture.pastel(str(i))
            self.assertGreaterEqual(max(r, g, b), 230)   # light
            self.assertGreaterEqual(min(r, g, b), 150)   # not saturated


if __name__ == "__main__":
    unittest.main()
