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

Every sheet is written with a provenance sidecar, `<out>.prov.json`: the
digest of the sheet itself and, per column, the label, the SVG digest and the
render digest it was drawn from, plus the reference's digest and the baseline
manifest.  `sheet_problems()` reads it back and says why a sheet no longer
describes the artefacts beside it -- including a source render replaced after
the sheet was drawn (D65) -- and tools/test_pipeline.py fails the release if
the published sheet is stale (D63).

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


SHEET_FORMAT = "flare_parts/1"


def write_sheet_provenance(out_path, columns, verified, baseline=None):
    """Record what a sheet was drawn from, by content, beside the sheet.

    `columns` is [(label, image path, svg path or None)], reference first.  The
    sheet's own digest goes in too, for the same reason a render sidecar holds
    the PNG's: without it the record describes a filename, and a filename can be
    overwritten by anything.
    """
    import render as _R
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rel = lambda q: os.path.relpath(os.path.abspath(q), root) if q else None  # noqa: E731
    rec = {
        "format": SHEET_FORMAT,
        "sheet_sha256": _R.sha256_file(out_path),
        "verified": bool(verified),
        "columns": [{"label": lab, "image": rel(img), "image_sha256": _R.sha256_file(img),
                     "svg": rel(svg), "svg_sha256": _R.sha256_file(svg) if svg else None}
                    for lab, img, svg in columns],
        "baseline": baseline,
    }
    with open(out_path + ".prov.json", "w") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True)
        fh.write("\n")
    return rec


def sheet_problems(sheet_path, current_svg, baseline_dir=None, reference=None):
    """Why the sheet at `sheet_path` does not describe these artefacts ([] if it does).

    It must exist with its sidecar; the sheet's bytes must be the ones the
    sidecar describes; it must have been drawn from verified inputs; every
    column's source image must still exist and hash to what the sheet was drawn
    from, and every rendered column's render must still carry provenance naming
    its recorded SVG (1024 px, resvg); its last column must be `current_svg` as
    it is NOW; with `baseline_dir`, its first rendered column must be that
    baseline's SVG and match its manifest; and the reference column must be the
    reference as it is now.
    """
    import render as _R
    out = []
    side = sheet_path + ".prov.json"
    if not os.path.exists(sheet_path):
        return ["%s does not exist" % sheet_path]
    try:
        rec = json.load(open(side))
    except (OSError, ValueError) as exc:
        return ["%s has no readable provenance (%s)" % (sheet_path, exc)]
    if not isinstance(rec, dict) or rec.get("format") != SHEET_FORMAT:
        return ["%s's provenance is not a %s record" % (sheet_path, SHEET_FORMAT)]
    if rec.get("sheet_sha256") != _R.sha256_file(sheet_path):
        out.append("%s is not the sheet its provenance describes" % sheet_path)
    if not rec.get("verified"):
        out.append("%s was drawn from unverified inputs" % sheet_path)
    cols = rec.get("columns") or []
    if len(cols) < 2:
        return out + ["%s records %d columns" % (sheet_path, len(cols))]
    # Every column's SOURCE, re-read now (D65).  The sidecar used to be checked
    # only for the SVG digests, so a sheet drawn from one render kept passing
    # after that render was replaced -- the sheet showed pixels that no longer
    # existed.  Each recorded image must still exist and still hash to the
    # digest the sheet was drawn from; a rendered column's SVG must still be
    # the recorded one, and the render's own provenance must say it is that
    # SVG's 1024-px resvg render.
    for i, col in enumerate(cols):
        lab = col.get("label", "column %d" % i)
        img = col.get("image")
        if not img:
            out.append("%s's %r column records no source image" % (sheet_path, lab))
            continue
        ip = img if os.path.isabs(img) else os.path.normpath(os.path.join(ROOT, img))
        if not os.path.exists(ip):
            out.append("%s's %r column was drawn from %s, which no longer exists"
                       % (sheet_path, lab, img))
            continue
        got = _R.sha256_file(ip)
        if got != col.get("image_sha256"):
            out.append("%s's %r column was drawn from %s as it hashed then (%s...), but it now "
                       "hashes to %s...: the sheet shows an image that is no longer there"
                       % (sheet_path, lab, img, str(col.get("image_sha256"))[:12], got[:12]))
        svg = col.get("svg")
        if not svg:
            if i > 0 and rec.get("verified"):
                out.append("%s is marked verified but its %r column records no SVG"
                           % (sheet_path, lab))
            continue
        sp = svg if os.path.isabs(svg) else os.path.normpath(os.path.join(ROOT, svg))
        if not os.path.exists(sp) or _R.sha256_file(sp) != col.get("svg_sha256"):
            out.append("%s's %r column records SVG %s at %s..., which it no longer is"
                       % (sheet_path, lab, svg, str(col.get("svg_sha256"))[:12]))
            continue
        try:
            _R.read_provenance(ip, require=True, expect_size=CANVAS,
                               expect_renderer="resvg", expect_svg=sp)
        except _R.ProvenanceError as exc:
            out.append("%s's %r column: %s" % (sheet_path, lab, exc))
    cur = _R.sha256_file(current_svg)
    if cols[-1].get("svg_sha256") != cur:
        out.append("%s's last column was drawn from SVG %s..., but %s is now %s...: the sheet "
                   "is stale" % (sheet_path, str(cols[-1].get("svg_sha256"))[:12], current_svg, cur[:12]))
    if reference is not None and cols[0].get("image_sha256") != _R.sha256_file(reference):
        out.append("%s's reference column is not %s" % (sheet_path, reference))
    if baseline_dir is not None:
        try:
            man = json.load(open(os.path.join(baseline_dir, "manifest.json")))
        except (OSError, ValueError) as exc:
            return out + ["baseline manifest unreadable: %s" % exc]
        bsvg = os.path.join(baseline_dir, man.get("svg", "reconstruction.svg"))
        want = man.get("svg_sha256")
        if not os.path.exists(bsvg) or _R.sha256_file(bsvg) != want:
            out.append("the baseline SVG no longer matches its manifest")
        if cols[1].get("svg_sha256") != want:
            out.append("%s's first compared column is not the documented baseline (%s...)"
                       % (sheet_path, str(want)[:12]))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("images", nargs="*", help="1-3 renders to compare, in column order")
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
    ap.add_argument("--verify", action="store_true",
                    help="draw nothing: check that the sheet at --out (and its provenance) "
                         "describes --svg as it is now and the --baseline; exit 1 if not")
    a = ap.parse_args()
    if a.verify:
        if not a.svg or len(a.svg) != 1:
            print("flare_parts: --verify needs exactly one --svg (the current release)", file=sys.stderr)
            return 2
        problems = sheet_problems(a.out, a.svg[0], a.baseline, a.reference)
        for msg in problems:
            print("flare_parts: %s" % msg, file=sys.stderr)
        if not problems:
            print("%s describes %s and %s" % (a.out, a.svg[0], a.baseline or "no baseline"))
        return 1 if problems else 0
    if not a.images:
        print("flare_parts: give 1-3 renders to compare (or --verify)", file=sys.stderr)
        return 2
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
    base_rec = None
    if a.baseline:
        base_rec = json.load(open(os.path.join(a.baseline, "manifest.json")))
    write_sheet_provenance(a.out, [("reference", a.reference, None)]
                           + list(zip(labels[1:], paths, svgs)), verified, base_rec)
    print("wrote %s (%dx%d) and its provenance" % (a.out, out.width, out.height))
    if a.split:
        stem, ext = os.path.splitext(a.out)
        for n, s in sheets:
            p = "%s_%s%s" % (stem, n.replace(",", "").replace(" ", "_"), ext)
            s.save(p)
            print("wrote %s" % p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
