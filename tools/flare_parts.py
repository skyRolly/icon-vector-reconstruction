#!/usr/bin/env python3
"""Before/after sheet for every named part of the flare, against the reference.

    python3 tools/flare_parts.py BEFORE.png AFTER.png --out out/flare_parts.png
    python3 tools/flare_parts.py out/render_1024.png --svg reconstruction.svg \
            --baseline out/baseline --labels "this release"      # what publish runs

Up to three images are compared with the reference.  `--baseline DIR` puts the
previous ACCEPTED release first: DIR holds that release's SVG and a manifest
naming it (label, commit, svg_sha256), and publish renders it to
DIR/render_1024.png.  The manifest's digest must match the SVG and the render's
provenance must match both, or the sheet is not drawn -- a before/after sheet
whose "before" is not the release it claims to be is worse than none.  `--svg`
does the same for the positional images: each must be the 1024-px resvg render
of the SVG given for it.  Without `--svg` the images are taken as given (an
ad-hoc comparison of scratch renders), and the sheet says so in its header.

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
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

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
    n = len(images)
    out = Image.new("RGB", (n * W + (n - 1) * g, top + 2 * H + g), (255, 255, 255))
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


CANVAS = 1024


class InputError(Exception):
    pass


def check_input(path, a, svg=None):
    """A compared image must be a 1024 x 1024 render; with `svg`, provably of it."""
    if a.shape[:2] != (CANVAS, CANVAS):
        raise InputError("%s is %dx%d; the parts are boxes on the %d-px canvas -- render "
                         "at --size %d" % (path, a.shape[1], a.shape[0], CANVAS, CANVAS))
    if svg is not None:
        import render as _R
        try:
            _R.read_provenance(path, require=True, expect_size=CANVAS,
                               expect_renderer="resvg", expect_svg=svg)
        except _R.ProvenanceError as exc:
            raise InputError(str(exc))


def baseline_input(d):
    """(render path, svg path, label) of the accepted baseline in directory `d`."""
    import render as _R
    man_p = os.path.join(d, "manifest.json")
    try:
        man = json.load(open(man_p))
    except (OSError, ValueError) as exc:
        raise InputError("baseline manifest %s is unreadable: %s" % (man_p, exc))
    svg = os.path.join(d, man.get("svg", "reconstruction.svg"))
    if not os.path.exists(svg):
        raise InputError("baseline SVG %s does not exist" % svg)
    got = _R.sha256_file(svg)
    if got != man.get("svg_sha256"):
        raise InputError("baseline SVG %s hashes to %s..., but its manifest names %s...: it "
                         "is not the release the manifest describes"
                         % (svg, got[:12], str(man.get("svg_sha256"))[:12]))
    return os.path.join(d, "render_1024.png"), svg, man.get("label", "baseline")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("images", nargs="+", help="1-3 renders to compare, in column order")
    ap.add_argument("--reference", default=os.path.join(ROOT, "reference.png"))
    ap.add_argument("--labels", default=None, help="comma-separated, one per image")
    ap.add_argument("--svg", nargs="+", default=None,
                    help="the SVG each image must be the resvg render of (verified)")
    ap.add_argument("--baseline", default=None,
                    help="directory holding the accepted release's SVG and manifest; its "
                         "render becomes the first compared column")
    ap.add_argument("--out", default=os.path.join(ROOT, "out", "flare_parts.png"))
    ap.add_argument("--split", action="store_true",
                    help="also write one image per part next to --out")
    a = ap.parse_args()
    paths = list(a.images)
    labels = a.labels.split(",") if a.labels else ["image %d" % (i + 1) for i in range(len(paths))]
    svgs = list(a.svg) if a.svg else [None] * len(paths)
    try:
        if len(labels) != len(paths):
            raise InputError("%d labels for %d images" % (len(labels), len(paths)))
        if len(svgs) != len(paths):
            raise InputError("%d --svg for %d images" % (len(svgs), len(paths)))
        if a.baseline:
            bp, bs, bl = baseline_input(a.baseline)
            paths, svgs, labels = [bp] + paths, [bs] + svgs, [bl] + labels
        if len(paths) > 3:
            raise InputError("at most three images are compared with the reference, got %d"
                             % len(paths))
        images = [load(a.reference)]
        check_input(a.reference, images[0])
        for p, sv in zip(paths, svgs):
            if not os.path.exists(p):
                raise InputError("%s does not exist" % p)
            im = load(p)
            check_input(p, im, sv)
            images.append(im)
    except InputError as exc:
        print("flare_parts: %s" % exc, file=sys.stderr)
        return 2
    verified = all(sv is not None for sv in svgs)
    labels = ["reference"] + labels
    sheets = [(n, part_sheet(n, b, images, labels)) for n, b in PARTS.items()]
    width = max(s.width for _n, s in sheets)
    head = 16
    out = Image.new("RGB", (width, head + sum(s.height + 10 for _n, s in sheets)), (255, 255, 255))
    ImageDraw.Draw(out).text((2, 2), "columns: %s -- %s" % (
        " | ".join(labels), "every render verified against the SVG it is labelled as"
        if verified else "UNVERIFIED inputs (no --svg): an ad-hoc comparison"), fill=(0, 0, 0))
    y = head
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
