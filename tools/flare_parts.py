#!/usr/bin/env python3
"""Before/after sheet for every named part of the flare, against the reference.

    python3 tools/flare_parts.py BEFORE.png AFTER.png --out out/flare_parts.png

`flare_view.py` decomposes one crop several ways; this answers the question a
review of a flare change actually asks -- "for each part of the flare, did the
change move it towards the reference or away?" -- so every named part gets the
same three columns (reference | before | after) at the same scale, in two rows:

  plain   the pixels, contrast-stretched identically for all three (the window
          is printed in the label), nearest-neighbour enlarged.
  LCE     local-contrast enhanced: image + 2.2 * (image - Gaussian(12)), which
          is roughly how the eye picks a ray or a line out of a glow.  A
          structure visible here and not in `plain` is a structure a viewer
          notices without being able to point at it, which is exactly what
          "too soft" and "too sharp" complaints are about.

The parts are fixed boxes in canvas pixels, named after the flare's own
anatomy, so two sheets from different iterations are directly comparable.
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

#: name -> (x0, y0, w, h, scale, lo, hi)
PARTS = {
    "core": (490, 474, 80, 80, 4, 0, 255),
    "upper-left rays": (330, 340, 210, 190, 2, 0, 200),
    "lower-left rays": (420, 505, 130, 120, 3, 30, 150),
    "upper-right ray": (535, 380, 150, 140, 3, 0, 200),
    "lower-right ray": (540, 505, 190, 130, 3, 0, 200),
    "vertical line": (500, 380, 60, 270, 2, 0, 230),
    "horizontal, east": (548, 498, 130, 40, 4, 0, 230),
    "horizontal, west": (340, 498, 125, 40, 4, 0, 230),
}


def load(p):
    return np.asarray(Image.open(p).convert("RGB")).astype(np.float64)


def plain(a, box):
    x0, y0, w, h, sc, lo, hi = box
    c = 255 * np.clip((a[y0:y0 + h, x0:x0 + w] - lo) / (hi - lo), 0, 1)
    return Image.fromarray(c.astype(np.uint8)).resize((w * sc, h * sc), Image.NEAREST)


def gauss(a, sigma):
    """Separable Gaussian blur, edges replicated (numpy only)."""
    r = int(4 * sigma + 0.5)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    p = np.pad(a, r, mode="edge")
    p = np.apply_along_axis(lambda m: np.convolve(m, k, mode="valid"), 0, p)
    return np.apply_along_axis(lambda m: np.convolve(m, k, mode="valid"), 1, p)


def lce(a, box):
    x0, y0, w, h, sc, _lo, _hi = box
    # blur only a margin around the box: the view is local and a whole-image
    # blur per channel per image would dominate the run time
    m = 48
    ya, yb, xa, xb = max(0, y0 - m), min(a.shape[0], y0 + h + m), max(0, x0 - m), min(a.shape[1], x0 + w + m)
    sub = a[ya:yb, xa:xb]
    b = np.stack([gauss(sub[..., k], 12.0) for k in range(3)], 2)
    a = np.zeros_like(a); bb = np.zeros_like(a)
    a[ya:yb, xa:xb] = sub; bb[ya:yb, xa:xb] = b
    b = bb
    e = (a + 2.2 * (a - b))[y0:y0 + h, x0:x0 + w]
    e = 255 * np.clip(e / 230.0, 0, 1) ** 0.85
    return Image.fromarray(e.astype(np.uint8)).resize((w * sc, h * sc), Image.LANCZOS)


def part_sheet(name, box, images, labels):
    x0, y0, w, h, sc, lo, hi = box
    W, H, g, top = w * sc, h * sc, 6, 18
    out = Image.new("RGB", (3 * W + 2 * g, top + 2 * H + g), (255, 255, 255))
    d = ImageDraw.Draw(out)
    d.text((2, 2), "%s   box x %d-%d, y %d-%d, x%d; plain window %g-%g"
           % (name, x0, x0 + w, y0, y0 + h, sc, lo, hi), fill=(0, 0, 0))
    for i, (a, lab) in enumerate(zip(images, labels)):
        for r, im in enumerate((plain(a, box), lce(a, box))):
            X, Y = i * (W + g), top + r * (H + g)
            out.paste(im, (X, Y))
            t = lab + (" LCE" if r else "")
            d.rectangle([X, Y, X + 7 * len(t) + 6, Y + 13], fill=(0, 0, 0))
            d.text((X + 3, Y + 1), t, fill=(255, 255, 0))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--reference", default=os.path.join(ROOT, "reference.png"))
    ap.add_argument("--labels", default="before,after")
    ap.add_argument("--out", default=os.path.join(ROOT, "out", "flare_parts.png"))
    ap.add_argument("--split", action="store_true",
                    help="also write one image per part next to --out")
    a = ap.parse_args()
    images = [load(a.reference), load(a.before), load(a.after)]
    labels = ["reference"] + a.labels.split(",")[:2]
    sheets = [(n, part_sheet(n, b, images, labels)) for n, b in PARTS.items()]
    width = max(s.width for _n, s in sheets)
    out = Image.new("RGB", (width, sum(s.height + 10 for _n, s in sheets)), (255, 255, 255))
    y = 0
    for _n, s in sheets:
        out.paste(s, (0, y))
        y += s.height + 10
    out.save(a.out)
    print("wrote %s (%dx%d)" % (a.out, out.width, out.height))
    if a.split:
        stem, ext = os.path.splitext(a.out)
        for n, s in sheets:
            p = "%s_%s%s" % (stem, n.replace(",", "").replace(" ", "_"), ext)
            s.save(p)
            print("wrote %s" % p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
