#!/usr/bin/env python3
"""Set up the accepted baseline's render: the one setup step the regression gate needs.

    python3 tools/setup_baseline.py            # CI's "Baseline setup" step; publish.sh runs it too

The before/after sheet (`out/flare_parts.png`, tools/flare_parts.py) compares
this release with the previous ACCEPTED release.  That release is committed as
its SVG, `out/baseline/reconstruction.svg`, pinned by `out/baseline/manifest.json`
(label, commit, svg_sha256).  Its 1024-px render is NOT committed -- it is a
derived artefact, and `.gitignore` keeps it out -- so a clean checkout has to
make it before anything can check the sheet.  Until D66 only `tools/publish.sh`
did, and CI ran the regression gate without it: the published-sheet check then
failed on a file that had simply never been generated, which read as a broken
release rather than a missing setup step (the D66 review finding).

What this does, in order, and why each step is here:

1. The baseline SVG must hash to the manifest's `svg_sha256`.  The digest is
   the pin: the render is made from THAT file and from nothing else in the
   working tree.
2. If git can see the manifest's `commit` (a full clone), that commit's
   `reconstruction.svg` must hash to the same digest.  A shallow clone (CI's
   default) cannot see it; the digest alone is then the pin, and it says so.
3. The SVG is rendered at 1024 px by resvg -- the acceptance renderer -- and a
   provenance sidecar is written beside it (tools/render.py).
4. The sidecar is read back with every expectation (size, renderer, SVG).
5. If the published sheet says it was drawn from THIS baseline (same SVG
   digest), the new render must be byte-for-byte the image the sheet recorded.
   resvg's PNG output is deterministic for a given resvg-py version, which
   `requirements.txt` pins; a mismatch means this environment does not
   reproduce the baseline (a different renderer version), and it is reported
   as a SETUP failure, not left for the regression gate to misreport as a
   stale sheet.  A sheet drawn from an older baseline is skipped with a note:
   `publish.sh` is about to redraw it.

Exit status: 0 set up and verified; 3 SETUP FAILURE (nothing about the artwork
was tested).  tools/test_pipeline.py uses the same 3 for its own pre-flight
check of these artefacts, so "setup failed" and "a regression failed" (exit 1)
cannot be confused.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import render as R  # noqa: E402

BASELINE_DIR = os.path.join(ROOT, "out", "baseline")
RENDER_NAME = "render_1024.png"
SIZE = 1024
RENDERER = "resvg"
SETUP_FAILURE = 3


class SetupError(Exception):
    pass


def renderer_version():
    try:
        from importlib.metadata import version
        return "resvg-py " + version("resvg-py")
    except Exception:                                   # noqa: BLE001
        return "resvg-py (version unknown)"


def manifest(baseline_dir=BASELINE_DIR):
    path = os.path.join(baseline_dir, "manifest.json")
    try:
        man = json.load(open(path))
    except (OSError, ValueError) as exc:
        raise SetupError("the baseline manifest %s is unreadable (%s)" % (path, exc))
    if not isinstance(man, dict) or not isinstance(man.get("svg_sha256"), str):
        raise SetupError("the baseline manifest %s names no svg_sha256" % path)
    return man


def check_commit(man, svg_sha, root=ROOT):
    """(ok, note): the pinned commit's reconstruction.svg against the digest, if git can see it."""
    commit = man.get("commit")
    if not commit:
        return True, "the manifest names no commit; pinned by digest"
    try:
        blob = subprocess.run(["git", "-C", root, "show", "%s:%s" % (commit, man.get("svg", "reconstruction.svg"))],
                              capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return True, "commit %s is not in this clone (shallow?); pinned by digest" % commit[:12]
    got = hashlib.sha256(blob).hexdigest()
    if got != svg_sha:
        return False, ("commit %s's %s hashes to %s..., not the manifest's %s...: the manifest "
                       "does not describe the release it names" % (commit[:12], man.get("svg"), got[:12],
                                                                 svg_sha[:12]))
    return True, "commit %s's reconstruction.svg matches the pinned digest" % commit[:12]


def sheet_expectation(baseline_svg_rel, svg_sha, sheet_path):
    """The image digest the published sheet recorded for this baseline, or (None, note)."""
    side = sheet_path + ".prov.json"
    try:
        rec = json.load(open(side))
    except (OSError, ValueError):
        return None, "no published sheet record to compare with"
    for col in rec.get("columns") or []:
        if col.get("svg") == baseline_svg_rel:
            if col.get("svg_sha256") != svg_sha:
                return None, ("the published sheet was drawn from an older baseline (%s...); "
                              "publish.sh redraws it" % str(col.get("svg_sha256"))[:12])
            return col.get("image_sha256"), "the published sheet's baseline column"
    return None, "the published sheet has no column for this baseline"


def setup(baseline_dir=BASELINE_DIR, root=ROOT, sheet_path=None, verbose=True):
    """Render and verify the baseline; returns the render's path.  Raises SetupError."""
    man = manifest(baseline_dir)
    svg = os.path.join(baseline_dir, man.get("svg", "reconstruction.svg"))
    if not os.path.exists(svg):
        raise SetupError("the baseline SVG %s is missing" % svg)
    svg_sha = R.sha256_file(svg)
    if svg_sha != man["svg_sha256"]:
        raise SetupError("%s hashes to %s..., but the manifest pins %s...: the baseline is not "
                         "the release the manifest names" % (svg, svg_sha[:12], man["svg_sha256"][:12]))
    ok, note = check_commit(man, svg_sha, root)
    if not ok:
        raise SetupError(note)
    out = os.path.join(baseline_dir, RENDER_NAME)
    data = R.render(svg, SIZE, RENDERER)
    open(out, "wb").write(data)
    R.write_provenance(out, svg, data, SIZE, RENDERER)
    try:
        R.read_provenance(out, require=True, expect_size=SIZE, expect_renderer=RENDERER, expect_svg=svg)
    except R.ProvenanceError as exc:
        raise SetupError("the baseline render does not verify: %s" % exc)
    png_sha = hashlib.sha256(data).hexdigest()
    rel = os.path.relpath(svg, root)
    want, wnote = sheet_expectation(rel, svg_sha, sheet_path or os.path.join(root, "out", "flare_parts.png"))
    if want is not None and want != png_sha:
        # Leave nothing behind that could pass for a set-up baseline: a render
        # the sheet does not describe would otherwise reach the regression gate
        # and be misreported there as a stale sheet.
        os.remove(out)
        R.clear_provenance(out)
        raise SetupError("the baseline rendered here (%s, %s...) is not the image the published sheet "
                         "was drawn from (%s...): this environment does not reproduce the baseline "
                         "render -- install the pinned versions (requirements.txt)"
                         % (renderer_version(), png_sha[:12], str(want)[:12]))
    if verbose:
        print("baseline: %s (%s)" % (man.get("label", "?"), rel))
        print("  svg %s... = manifest; %s" % (svg_sha[:12], note))
        print("  rendered %s at %d px by %s (%s), png %s..."
              % (os.path.relpath(out, root), SIZE, RENDERER, renderer_version(), png_sha[:12]))
        print("  %s" % ("matches " + wnote if want is not None else wnote))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--baseline", default=BASELINE_DIR, help="baseline directory (manifest + SVG)")
    a = ap.parse_args()
    try:
        setup(a.baseline)
    except SetupError as exc:
        print("SETUP FAILURE: %s" % exc, file=sys.stderr)
        print("(this is a setup failure, not an artwork regression: nothing was tested)", file=sys.stderr)
        return SETUP_FAILURE
    print("baseline setup OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
