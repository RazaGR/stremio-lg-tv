#!/usr/bin/env python3
"""Generate the app's PNG assets at the sizes webOS TV requires.

webOS TV wants icon 80x80, largeIcon 130x130 and a 1920x1080 splash. Rather
than check binaries into the repo we draw them here, so the artwork is
reproducible and `make icons` can regenerate everything after a tweak.

Everything is drawn by supersampling a signed-distance description of the mark
(rounded square + play triangle) and downsampling, which gives clean edges
without pulling in an image library.
"""

import math
import os
import struct
import sys
import zlib

# Brand-ish purple. BG_* is the tile/splash backdrop, MARK_* the gradient.
BG = (0x0F, 0x02, 0x26)
MARK_TOP = (0x8B, 0x5C, 0xF6)
MARK_BOTTOM = (0x5B, 0x21, 0xB6)
GLYPH = (0xFF, 0xFF, 0xFF)

SS = 4  # supersampling factor per axis (16 samples per output pixel)


def write_png(path, width, height, pixels):
    """Write RGBA8 `pixels` (bytes, row-major) as a PNG."""

    def chunk(tag, data):
        body = tag + data
        return (
            struct.pack(">I", len(data))
            + body
            + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        )

    stride = width * 4
    raw = b"".join(
        b"\x00" + pixels[y * stride : (y + 1) * stride] for y in range(height)
    )

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")

    with open(path, "wb") as fh:
        fh.write(png)


def rounded_rect_sdf(px, py, half_w, half_h, radius):
    """Signed distance from (px, py) to a rounded rect centred on the origin."""
    qx = abs(px) - (half_w - radius)
    qy = abs(py) - (half_h - radius)
    outside = math.hypot(max(qx, 0.0), max(qy, 0.0))
    inside = min(max(qx, qy), 0.0)
    return outside + inside - radius


def in_triangle(px, py, tri):
    """Point-in-triangle via consistent winding of the three edge cross products."""
    sign = None
    for i in range(3):
        ax, ay = tri[i]
        bx, by = tri[(i + 1) % 3]
        cross = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
        if cross == 0:
            continue
        current = cross > 0
        if sign is None:
            sign = current
        elif sign != current:
            return False
    return True


def render_mark(size):
    """Draw the rounded-square + play mark at `size`x`size`, returns RGBA bytes.

    Alpha is 0 outside the rounded square so the mark can be composited onto
    the splash without a visible bounding box.
    """
    hi = size * SS
    half = hi / 2.0
    # Slightly inset so antialiased edges are not clipped by the bitmap border.
    box_half = half * 0.94
    radius = box_half * 0.32

    # Play triangle, sized relative to the box and nudged right so it reads as
    # optically centred rather than mathematically centred.
    t = box_half * 0.46
    cx = half + box_half * 0.07
    cy = half
    triangle = (
        (cx - t * 0.72, cy - t),
        (cx - t * 0.72, cy + t),
        (cx + t * 0.88, cy),
    )

    samples = [[0] * 4 for _ in range(size * size)]

    for sy in range(hi):
        py = sy + 0.5
        row_base = (sy // SS) * size
        for sx in range(hi):
            px = sx + 0.5
            if rounded_rect_sdf(px - half, py - half, box_half, box_half, radius) > 0:
                continue

            if in_triangle(px, py, triangle):
                r, g, b = GLYPH
            else:
                # Vertical gradient across the tile.
                t_grad = py / hi
                r = int(MARK_TOP[0] + (MARK_BOTTOM[0] - MARK_TOP[0]) * t_grad)
                g = int(MARK_TOP[1] + (MARK_BOTTOM[1] - MARK_TOP[1]) * t_grad)
                b = int(MARK_TOP[2] + (MARK_BOTTOM[2] - MARK_TOP[2]) * t_grad)

            acc = samples[row_base + (sx // SS)]
            acc[0] += r
            acc[1] += g
            acc[2] += b
            acc[3] += 255

    per_pixel = SS * SS
    out = bytearray(size * size * 4)
    for i, (r, g, b, a) in enumerate(samples):
        covered = a // 255
        if covered:
            # Average only over covered samples so edge pixels keep full
            # colour and vary in alpha (rather than darkening toward black).
            out[i * 4 + 0] = r // covered
            out[i * 4 + 1] = g // covered
            out[i * 4 + 2] = b // covered
        out[i * 4 + 3] = a // per_pixel
    return bytes(out)


def composite(dst, dst_w, src, src_w, src_h, at_x, at_y):
    """Alpha-composite `src` over `dst` (both RGBA bytes) at the given offset."""
    for y in range(src_h):
        for x in range(src_w):
            si = (y * src_w + x) * 4
            alpha = src[si + 3]
            if not alpha:
                continue
            di = ((at_y + y) * dst_w + (at_x + x)) * 4
            inv = 255 - alpha
            for c in range(3):
                dst[di + c] = (src[si + c] * alpha + dst[di + c] * inv) // 255
            dst[di + 3] = 255


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "src"
    asset_dir = sys.argv[2] if len(sys.argv) > 2 else "assets"
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(asset_dir, exist_ok=True)

    # webOS TV mandates these two sizes exactly.
    for name, size in (("icon.png", 80), ("largeIcon.png", 130)):
        path = os.path.join(out_dir, name)
        write_png(path, size, size, render_mark(size))
        print("wrote %s (%dx%d)" % (path, size, size))

    # Listing icon for the Homebrew Channel. Kept outside the packaged app so
    # it does not bloat the .ipk with an asset the TV never renders.
    path = os.path.join(asset_dir, "icon160.png")
    write_png(path, 160, 160, render_mark(160))
    print("wrote %s (160x160)" % path)

    # Splash: solid backdrop with the mark centred. Drawn small then composited
    # so we never supersample a 1920x1080 canvas.
    sw, sh, mark_size = 1920, 1080, 320
    canvas = bytearray()
    for _ in range(sw * sh):
        canvas += bytes((BG[0], BG[1], BG[2], 255))
    mark = render_mark(mark_size)
    composite(canvas, sw, mark, mark_size, mark_size, (sw - mark_size) // 2,
              (sh - mark_size) // 2)
    path = os.path.join(out_dir, "splash.png")
    write_png(path, sw, sh, bytes(canvas))
    print("wrote %s (%dx%d)" % (path, sw, sh))


if __name__ == "__main__":
    main()
