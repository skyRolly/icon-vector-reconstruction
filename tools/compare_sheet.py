#!/usr/bin/env python3
"""Contact sheet: reference, render and signed difference, region by region.

    python3 tools/compare_sheet.py out/render_1024.png --out out/sheet.png
    python3 tools/compare_sheet.py a.png b.png --labels now,candidate

A single mean absolute error cannot tell you whether a ray is missing, whether
the core is too large, or whether a broad wedge has appeared where the reference
has none.  This puts the reference and the render side by side at the places
those questions live, with the signed difference beside them, so the answer is
visible rather than inferred.

Two deliberate choices:

* the difference is SIGNED and symmetric -- red where the render is too bright,
  blue where it is too dark, at a stated scale -- because "too bright here and
  too dark there" is the signature of a redistribution, and an absolute
  difference hides exactly that;

* each region is also shown contrast-STRETCHED over a band chosen for that
  region, because the structures at issue are a few code values on a background
  of 80-200 and are invisible at native contrast.  The stretch is stated in the
  label so nothing is silently exaggerated.

`--scales` adds a multi-scale row: the same crop at 1x, and box-averaged 2x and
4x.  The reference carries real 8x8 JPEG blocking, so a feature that survives
averaging is structure and one that does not is probably compression.
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from regions import FLARE_CORE  # noqa: E402

CX, CY = int(round(FLARE_CORE[0])), int(round(FLARE_CORE[1]))

#: name -> (centre x, centre y, half-size, zoom, stretch low, stretch high)
#: The offsets are the measured ray directions, so each crop is centred on the
#: structure it is named for rather than on a guess.
REGIONS = (
    ("full image",          512,      512,      512, 1, 0,   200),
    ("centre",              CX,       CY,       130, 3, 60,  190),
    ("brightest core",      CX,       CY,        36, 9, 150, 255),
    ("lower line stack",    CX,       CY + 14,   90, 5, 90,  200),
    ("upper-left ray",      CX - 62,  CY - 63,   70, 5, 70,  150),
    ("lower-left ray",      CX - 54,  CY + 65,   70, 5, 70,  150),
    ("upper-right ray",     CX + 72,  CY - 60,   70, 5, 60,  140),
    ("lower-right ray",     CX + 72,  CY + 45,   70, 5, 60,  140),
    ("west field",          CX - 150, CY,       120, 3, 55,  130),
)
PAD = 8
BG = (26, 26, 28)


def load(p):
    return np.asarray(Image.open(p).convert("RGB")).astype(np.float64)


def crop(a, cx, cy, half):
    h, w = a.shape[:2]
    x0, y0 = max(0, cx - half), max(0, cy - half)
    x1, y1 = min(w, cx + half), min(h, cy + half)
    return a[y0:y1, x0:x1]


def stretch(a, lo, hi, gamma=0.65):
    return (np.clip((a - lo) / float(hi - lo), 0, 1) ** gamma * 255).astype(np.uint8)


def signed(d, scale):
    """Red where the render is too bright, blue where too dark."""
    t = np.clip(d.mean(2) / float(scale), -1, 1)
    out = np.zeros(d.shape[:2] + (3,), np.float64)
    out[..., 0] = np.where(t > 0, t, 0) * 255
    out[..., 2] = np.where(t < 0, -t, 0) * 255
    out[..., 1] = (1 - np.abs(t)) * 60
    return out.astype(np.uint8)


def zoom(a, z):
    return np.asarray(Image.fromarray(a).resize((a.shape[1] * z, a.shape[0] * z), Image.NEAREST))


def box(a, k):
    h, w = a.shape[:2]
    h, w = h - h % k, w - w % k
    return a[:h, :w].reshape(h // k, k, w // k, k, -1).mean((1, 3))


def label(img, text):
    im = Image.fromarray(img)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, im.width, 15], fill=BG)
    d.text((4, 3), text, fill=(210, 210, 215))
    return np.asarray(im)


def row(tiles):
    h = max(t.shape[0] for t in tiles)
    out = []
    for t in tiles:
        if t.shape[0] < h:
            t = np.vstack([t, np.full((h - t.shape[0],) + t.shape[1:], BG, np.uint8)])
        out.append(t)
        out.append(np.full((h, PAD, 3), BG, np.uint8))
    return np.hstack(out[:-1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("renders", nargs="+")
    ap.add_argument("--reference", default=os.path.join(ROOT, "reference.png"))
    ap.add_argument("--out", default=os.path.join(ROOT, "out", "compare_sheet.png"))
    ap.add_argument("--labels", default=None)
    ap.add_argument("--diff-scale", type=float, default=12.0)
    ap.add_argument("--scales", action="store_true", help="add a multi-scale row per region")
    ap.add_argument("--only", default=None, help="comma-separated region names")
    a = ap.parse_args()

    ref = load(a.reference)
    imgs = [load(p) for p in a.renders]
    names = (a.labels.split(",") if a.labels
             else [os.path.basename(p).replace(".png", "") for p in a.renders])

    wanted = set(x.strip() for x in a.only.split(",")) if a.only else None
    rows = []
    for name, cx, cy, half, z, lo, hi in REGIONS:
        if wanted and name not in wanted:
            continue
        rc = crop(ref, cx, cy, half)
        tiles = [label(zoom(stretch(rc, lo, hi), z), "%s  reference  [%d-%d]" % (name, lo, hi))]
        for img, nm in zip(imgs, names):
            ic = crop(img, cx, cy, half)
            tiles.append(label(zoom(stretch(ic, lo, hi), z), "%s" % nm))
            tiles.append(label(zoom(signed(ic - rc, a.diff-scale if False else a.diff_scale), z),
                               "%s - reference  [+-%g cv]" % (nm, a.diff_scale)))
        rows.append(row(tiles))
        if a.scales:
            multi = []
            for k in (1, 2, 4):
                r2 = box(rc, k) if k > 1 else rc
                multi.append(label(zoom(stretch(r2, lo, hi), z * k), "ref /%d" % k))
                for img, nm in zip(imgs, names):
                    i2 = box(crop(img, cx, cy, half), k) if k > 1 else crop(img, cx, cy, half)
                    multi.append(label(zoom(signed(i2 - r2, a.diff_scale), z * k),
                                       "%s diff /%d" % (nm, k)))
            rows.append(row(multi))

    w = max(r.shape[1] for r in rows)
    padded = [np.hstack([r, np.full((r.shape[0], w - r.shape[1], 3), BG, np.uint8)])
              for r in rows]
    gap = np.full((PAD * 2, w, 3), BG, np.uint8)
    sheet = padded[0]
    for r in padded[1:]:
        sheet = np.vstack([sheet, gap, r])
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    Image.fromarray(sheet).save(a.out)
    print("wrote %s  (%d regions, %dx%d)" % (a.out, len(rows), sheet.shape[1], sheet.shape[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
