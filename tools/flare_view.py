#!/usr/bin/env python3
"""The flare inspection sheet: one image a reviewer can answer questions from.

    python3 tools/flare_view.py out/render_1024.png --out out/flare_view.png
    python3 tools/flare_view.py a.png b.png --labels "previous,candidate"

`compare_sheet.py` answers "which region is wrong"; this answers "what is wrong
with the flare", which is a different question and needs a different picture.

The sheet is a grid.  Each ROW is one crop at one scale decomposed one way; each
COLUMN is reference, reconstruction, and the differences between them.  Three
decompositions are shown for every crop, because the three failure modes the
reference actually exhibits are not visible in the same view:

  RGB       what the eye sees.  Also the only view in which clipping is
            visible as clipping.
  LUMINANCE structure without colour.  The high-pass columns are here and not
            in RGB because a sharp thin feature is a luminance feature, and
            chroma subsampling in the source would smear it in colour.
  CHROMA    colour with the brightness divided out: mid grey is neutral, so
            "the render is less saturated here" becomes visible directly
            instead of being inferred from a ratio of two bright numbers.

Deliberate choices, each because the alternative misled a previous iteration:

* Enlargement is NEAREST NEIGHBOUR.  A smooth upscale invents a gradient
  between two pixels, and the question "is the centre a diffuse blob or a
  compact core with detail" is exactly the question a smooth upscale answers
  wrongly.  Blocky is honest.

* Every gain is printed in its panel label.  A difference panel with an
  unstated multiplier is an argument, not evidence.

* The difference columns are computed at native resolution and then enlarged,
  never the reverse -- enlarging first and differencing after would hide a
  one-pixel misalignment, which is the most common real defect here.

* Both images are cropped with the SAME integer box, so a feature that appears
  to move between the two panels really has moved.

The default crops are the flare at three scales: the whole structure including
the rays, the core's surroundings, and the core itself at 10x, which is the
scale at which "is there internal detail" can be answered at all.
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from regions import FLARE_CORE  # noqa: E402

#: Label fonts.  These were two hard-coded Debian paths, which is a host
#: assumption this project does not otherwise make: the documented requirement
#: is Python plus Pillow and numpy, and neither macOS nor a minimal Linux image
#: ships DejaVu at that path.  Each name is tried in turn and Pillow's built-in
#: bitmap font is the floor, so the sheet renders everywhere -- smaller and
#: uglier without a TrueType face, but a diagnostic that refuses to draw is
#: worse than one drawn in the default font.
FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
)
FONT_B_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
)


def _font(size, bold=False):
    """A TrueType face at `size` if the host has one, else Pillow's default."""
    for path in (FONT_B_CANDIDATES if bold else FONT_CANDIDATES):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()

#: (name, half-width in source px, panel size in output px).  The panel size
#: divided by 2*half is the enlargement, so these are 1.4x, 3.4x and 9.1x.
CROPS = (("flare  +-160 px", 160, 450),
         ("core surround  +-66 px", 66, 450),
         ("core  +-25 px", 25, 456))

#: The nine questions from the brief this sheet exists to answer, and where.
QUESTIONS = (
    ("Is the central white region too large?", "row 3 RGB / row 3 LUM"),
    ("Is the centre too blurry?", "row 3 LUM high-pass"),
    ("Is the vertical diffraction present?", "row 2 LUM high-pass"),
    ("Are the left rays correct?", "row 1 LUM, signed diff"),
    ("Is the false triangular region present?", "row 1 signed diff, west of centre"),
    ("Are the lower horizontal features present?", "row 2 LUM high-pass"),
    ("Are the right rays sufficiently detailed?", "row 1 LUM high-pass"),
    ("Is the surrounding flare too faint or too saturated?", "row 1 CHROMA"),
)


def load(p):
    return np.asarray(Image.open(p).convert("RGB")).astype(np.float64)


#: crops that had to be padded, so the sheet can say so once at the end.
_CLAMPED = []


def crop(a, cx, cy, half):
    """The same 2*half box out of every image, PADDED where it leaves the canvas.

    It used to be clamped and returned short.  `enlarge` then resized whatever
    came back to a square, so a centre within `half` of an edge was displayed
    with the wrong aspect ratio and no indication: `--cx 10` with the 160-px crop
    yields 320x170 shown at 450x450, stretching horizontal features 1.88x
    against vertical ones on a sheet whose whole purpose is judging flare shape.

    Padding instead keeps every pixel at its true aspect.  The fill is black,
    which is what the canvas outside the artwork is anyway and which `chroma`
    maps to exactly neutral, so it reads as absent rather than as structure; and
    because both images are the same size and get the same box, they are padded
    identically.  The caller is told, because a padded panel is smaller than it
    looks.
    """
    h, w = a.shape[:2]
    x0, y0 = int(round(cx)) - half, int(round(cy)) - half
    x1, y1 = x0 + 2 * half, y0 + 2 * half
    # BOTH endpoints are clamped into range, not just the near one.  Clamping
    # only the lower bound to 0 and the upper to the image size leaves a box
    # entirely off-canvas with cx0 = 0 and a NEGATIVE cx1, and numpy reads a
    # negative endpoint from the far edge: --cx -1000 sliced 184 real columns
    # out of the right-hand side of the image and then tried to write them at
    # x = 1160 of a 320-wide panel, so the sheet raised ValueError instead of
    # drawing the empty panel the centre asks for.
    cx0, cx1 = min(max(x0, 0), w), min(max(x1, 0), w)
    cy0, cy1 = min(max(y0, 0), h), min(max(y1, 0), h)
    sub = a[cy0:cy1, cx0:cx1]
    if sub.shape[0] == 2 * half and sub.shape[1] == 2 * half:
        return sub
    out = np.zeros((2 * half, 2 * half) + a.shape[2:], dtype=a.dtype)
    # An empty intersection is a legal answer -- a wholly off-canvas box is all
    # padding -- so the copy only happens when there is something to copy.
    if sub.shape[0] and sub.shape[1]:
        out[cy0 - y0:cy0 - y0 + sub.shape[0], cx0 - x0:cx0 - x0 + sub.shape[1]] = sub
    note = "+-%d px box at (%d, %d): %dx%d of %dx%d is off-canvas and padded" % (
        half, int(round(cx)), int(round(cy)), sub.shape[1], sub.shape[0],
        2 * half, 2 * half)
    if note not in _CLAMPED:
        _CLAMPED.append(note)
    return out


def enlarge(a, size):
    """Nearest-neighbour to `size` px.  See the module docstring.

    This is only honest because `crop` now returns a square: resizing a
    rectangle to (size, size) silently changes aspect ratios.
    """
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    return im.resize((size, size), Image.NEAREST)


def luminance(a):
    return a.mean(2)


def chroma(a, gain):
    """Colour with brightness divided out: mid grey is neutral.

    `rgb - mean(rgb)` is zero for any grey at any brightness, so what is left
    is the colour alone.  A hue-preserving normalisation by luminance would
    blow up in the dark background; subtracting does not.
    """
    return 128.0 + gain * (a - a.mean(2)[..., None])


def highpass(g, sigma=2.0):
    """Unsharp residual: the structure a blur of this width cannot represent."""
    from numpy import exp, arange
    n = int(sigma * 4) | 1
    x = arange(n) - n // 2
    k = exp(-(x ** 2) / (2 * sigma ** 2))
    k /= k.sum()
    b = np.apply_along_axis(lambda m: np.convolve(m, k, mode="same"), 0, g)
    b = np.apply_along_axis(lambda m: np.convolve(m, k, mode="same"), 1, b)
    return g - b


def grey(g):
    return np.repeat(np.clip(g, 0, 255)[..., None], 3, axis=2)


def signed(d, gain):
    """Red where the second image is brighter, blue where it is darker."""
    h, w = d.shape[:2]
    out = np.zeros((h, w, 3))
    out[..., 0] = np.clip(d * gain, 0, 255)
    out[..., 2] = np.clip(-d * gain, 0, 255)
    out[..., 1] = np.clip(np.minimum(out[..., 0], out[..., 2]), 0, 255)
    return out


def tone(a, gamma=2.5):
    """A display boost that shows the faint bloom without clipping the core."""
    return 255.0 * np.clip(a / 255.0, 0, 1) ** (1.0 / gamma)


def build_row(ref, rec, view, size, gains):
    """Six panels: reference, reconstruction, |diff|, signed diff, and two
    view-specific enhancements.  Returns [(image, label), ...]."""
    ga, gs, ge = gains
    if view == "RGB":
        panels = [(ref, "reference"),
                  (rec, "reconstruction"),
                  (np.abs(rec - ref) * ga, "|difference| x%g" % ga),
                  (signed((rec - ref).mean(2), gs), "signed x%g  red=too bright" % gs),
                  (tone(ref), "reference  gamma 1/2.5"),
                  (tone(rec), "reconstruction  gamma 1/2.5")]
    elif view == "LUM":
        lr, lc = luminance(ref), luminance(rec)
        panels = [(grey(lr), "reference luminance"),
                  (grey(lc), "reconstruction luminance"),
                  (grey(np.abs(lc - lr) * ga), "|difference| x%g" % ga),
                  (signed(lc - lr, gs), "signed x%g" % gs),
                  (grey(128 + highpass(lr) * ge), "reference high-pass x%g" % ge),
                  (grey(128 + highpass(lc) * ge), "reconstruction high-pass x%g" % ge)]
    else:
        cr, cc = chroma(ref, 3.0), chroma(rec, 3.0)
        # NOT (cc - cr).mean(2), which this used to be and which is identically
        # zero: `chroma` subtracts each pixel's own channel mean, so the three
        # deviations it returns sum to zero by construction, and so does their
        # difference.  Averaging that over channels gave float noise and a black
        # panel for every pair, however differently coloured -- a cyan pixel
        # against a grey one produced 0.000e+00.  What the label promises is
        # "more colour", which is a MAGNITUDE question: how far each pixel's
        # chroma sits from neutral.
        d = (np.linalg.norm(cc - 128.0, axis=2)
             - np.linalg.norm(cr - 128.0, axis=2))
        panels = [(cr, "reference chroma x3"),
                  (cc, "reconstruction chroma x3"),
                  (np.abs(cc - cr) * ga, "|difference| x%g" % ga),
                  (signed(d, gs), "signed x%g  red=more colour" % gs),
                  (chroma(ref, 9.0), "reference chroma x9"),
                  (chroma(rec, 9.0), "reconstruction chroma x9")]
    return [(enlarge(p, size), lab) for p, lab in panels]


#: Per crop scale, the (abs, signed, enhance) gains for each view.  Wider crops
#: contain the bright core, so their differences are larger and need less gain.
GAINS = {
    ("RGB", 0): (4, 6, 1), ("RGB", 1): (4, 6, 1), ("RGB", 2): (3, 4, 1),
    ("LUM", 0): (4, 6, 6), ("LUM", 1): (4, 6, 6), ("LUM", 2): (3, 4, 4),
    ("CHR", 0): (4, 6, 1), ("CHR", 1): (4, 6, 1), ("CHR", 2): (4, 6, 1),
}
VIEWS = ("RGB", "LUM", "CHR")
VIEW_TITLE = {"RGB": "RGB -- what the eye sees",
              "LUM": "LUMINANCE -- structure without colour",
              "CHR": "CHROMA -- colour with brightness divided out"}


def sheet(ref_path, rec_path, out_path, cx, cy, labels=("reference", "reconstruction")):
    ref_full, rec_full = load(ref_path), load(rec_path)
    if ref_full.shape != rec_full.shape:
        raise SystemExit("images differ in size: %s vs %s -- alignment would be a lie"
                         % (ref_full.shape, rec_full.shape))
    f_head = _font(21, bold=True)
    f_row = _font(16, bold=True)
    f_lab = _font(13)
    pad, gap = 16, 8
    head_h, row_h, lab_h = 34, 26, 19

    rows = []                                   # (title, [(img, label)...])
    for ci, (cname, half, size) in enumerate(CROPS):
        r = crop(ref_full, cx, cy, half)
        c = crop(rec_full, cx, cy, half)
        for view in VIEWS:
            rows.append(("%s   %s   (%.1fx)" % (cname, view, size / (2.0 * half)),
                         build_row(r, c, view, size, GAINS[(view, ci)])))

    pw = rows[0][1][0][0].size[0]
    ncol = 6
    W = pad * 2 + ncol * pw + (ncol - 1) * gap
    # a head band per view group, a title per row, then the panels and labels
    H = pad
    for i, (title, panels) in enumerate(rows):
        if i % len(VIEWS) == 0:
            H += head_h
        H += row_h + panels[0][0].size[1] + lab_h + gap * 2
    H += 26 * (len(QUESTIONS) + 2) + pad

    sheet_im = Image.new("RGB", (W, H), (17, 17, 20))
    dr = ImageDraw.Draw(sheet_im)
    y = pad
    for i, (title, panels) in enumerate(rows):
        if i % len(VIEWS) == 0:
            cname = CROPS[i // len(VIEWS)][0]
            dr.rectangle([pad - 6, y - 4, W - pad + 6, y + head_h - 10], fill=(38, 38, 46))
            dr.text((pad, y), "CROP %d   %s   centred on the flare at (%.1f, %.1f)"
                    % (i // len(VIEWS) + 1, cname, cx, cy), font=f_head, fill=(235, 235, 240))
            y += head_h
        view = VIEWS[i % len(VIEWS)]
        dr.text((pad, y), VIEW_TITLE[view], font=f_row, fill=(150, 200, 255))
        y += row_h
        x = pad
        for j, (im, lab) in enumerate(panels):
            sheet_im.paste(im, (x, y))
            dr.rectangle([x, y, x + im.size[0] - 1, y + im.size[1] - 1], outline=(70, 70, 80))
            name = labels[0] if j == 0 else (labels[1] if j == 1 else None)
            text = lab if name is None else lab.replace("reference", labels[0]).replace(
                "reconstruction", labels[1])
            dr.text((x + 2, y + im.size[1] + 3), text, font=f_lab, fill=(190, 190, 200))
            x += im.size[0] + gap
        y += panels[0][0].size[1] + lab_h + gap * 2

    dr.text((pad, y), "What this sheet is for -- the questions it exists to answer:",
            font=f_row, fill=(150, 200, 255))
    y += 28
    for q, where in QUESTIONS:
        dr.text((pad + 8, y), "- %-52s %s" % (q, where), font=f_lab, fill=(200, 200, 210))
        y += 24

    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    sheet_im.save(out_path)
    print("wrote %s (%dx%d)" % (out_path, W, H))
    return out_path


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("images", nargs="+",
                    help="one render (compared against reference.png), or two images")
    ap.add_argument("--reference", default=os.path.join(ROOT, "reference.png"))
    ap.add_argument("--out", default=os.path.join(ROOT, "out", "flare_view.png"))
    ap.add_argument("--labels", default=None, help="comma-separated pair")
    ap.add_argument("--cx", type=float, default=FLARE_CORE[0])
    ap.add_argument("--cy", type=float, default=FLARE_CORE[1])
    a = ap.parse_args()
    if len(a.images) == 1:
        ref, rec = a.reference, a.images[0]
        labels = ("reference", "reconstruction")
    else:
        ref, rec = a.images[0], a.images[1]
        labels = ("A", "B")
    if a.labels:
        # [:2] silently produced a ONE-element tuple for a one-item value, and
        # sheet() indexes labels[1]: the option aborted with IndexError deep in
        # drawing instead of being rejected here.
        parts = tuple(s.strip() for s in a.labels.split(","))
        if len(parts) != 2 or not all(parts):
            ap.error("--labels needs exactly two non-empty comma-separated "
                     "names, e.g. --labels \"previous,candidate\"")
        labels = parts
    sheet(ref, rec, a.out, a.cx, a.cy, labels)
    for note in _CLAMPED:
        print("NOTE: %s.  The panel keeps its aspect ratio; the padding is not "
              "image data." % note, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
