"""Placeholder texture (PNG) painted with each face's layout rectangle."""

import colorsys
import struct
import zlib


def pastel(key):
    """A pastel RGB color picked at random from key: the same key always gets the same color."""
    hue = (zlib.crc32(key.encode("utf-8")) % 3600) / 3600
    return tuple(int(c * 255) for c in colorsys.hsv_to_rgb(hue, 0.35, 0.95))


def paint_rows(width, height, paint):
    """Placeholder texture as RGBA rows, top row first: each face's rectangle filled
    with its color."""
    bg = bytes((0, 0, 0, 0))
    rows = [bytearray(bg * width) for _ in range(height)]
    for x, y, w, h, _face, color in paint:
        px = bytes((color[0], color[1], color[2], 255))
        x0, x1 = max(x, 0), min(x + w, width)
        if x1 <= x0:
            continue
        span = px * (x1 - x0)
        for yy in range(max(y, 0), min(y + h, height)):
            rows[yy][x0 * 4:x1 * 4] = span
    return rows


def write_png(path, width, height, paint):
    """Write the placeholder texture (see paint_rows) as an RGBA PNG."""
    rows = paint_rows(width, height, paint)
    raw = b"".join(b"\x00" + bytes(r) for r in rows)

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(raw, 9)))
        f.write(chunk(b"IEND", b""))
