"""Placeholder texture (PNG) painted with each face's layout rectangle."""

import struct
import zlib


FACE_SHADE = {"top": 1.0, "front": 0.9, "right": 0.8, "left": 0.75, "back": 0.7, "bottom": 0.6}


def write_png(path, width, height, paint):
    """Placeholder texture: each face filled with the object's material
    viewport color, shaded per side so faces are easy to tell apart."""
    bg = bytes((0, 0, 0, 0))
    rows = [bytearray(bg * width) for _ in range(height)]
    for x, y, w, h, face, color in paint:
        k = FACE_SHADE.get(face, 1.0)
        px = bytes((int(color[0] * k), int(color[1] * k), int(color[2] * k), 255))
        span = px * w
        for yy in range(y, min(y + h, height)):
            rows[yy][x * 4:(x + w) * 4] = span

    raw = b"".join(b"\x00" + bytes(r) for r in rows)

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(raw, 9)))
        f.write(chunk(b"IEND", b""))
