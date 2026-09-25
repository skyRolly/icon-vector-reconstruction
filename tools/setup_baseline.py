#!/usr/bin/env python3
"""Set up the accepted baseline's render: the one setup step the regression gate needs.

    python3 tools/setup_baseline.py                 # CI's "Baseline setup" step
    python3 tools/setup_baseline.py --for-publish   # publish.sh, which redraws the sheet next

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
2. If git can see the manifest's `commit`, that commit's `reconstruction.svg`
   must hash to the same digest.  A shallow clone (CI's default) cannot see
   it and says so -- the digest alone is then the pin -- but a full clone
   that cannot find the commit, or finds it without that file, is a failure.
3. The SVG is rendered at 1024 px by resvg -- the acceptance renderer.
4. If the published sheet has a column drawn from THIS baseline (a column
   whose SVG digest is the manifest's -- matched by content, not by how its
   path is spelled), the render must be byte-for-byte the image that column
   recorded.  resvg's PNG output is deterministic for a given resvg-py, which
   `requirements.txt` pins; a mismatch means this environment does not
   reproduce the baseline, and it is reported as a SETUP failure rather than
   left for the regression gate to misreport as a stale sheet.  A sheet
   drawn from an older baseline is not compared (publish.sh redraws it), and
   `--for-publish` skips the comparison altogether: publish.sh redraws the
   sheet from this render and then verifies the new sheet, so a renderer
   upgrade can be published at all.
5. Only then is the render written, with its provenance sidecar, and read
   back with every expectation (size, renderer, SVG).  On any failure nothing
   verified-looking is left behind.

`verify()` repeats every check except the rendering; tools/test_pipeline.py
runs it before any regression check.  Exit status: 0 set up and verified;
3 SETUP FAILURE (nothing about the artwork was tested) -- for every failure,
including an unexpected error.  The gate uses the same 3 for its own
pre-flight, so "setup failed" and "a regression failed" (exit 1) cannot be
confused.
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
SHEET = os.path.join(ROOT, "out", "flare_parts.png")
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


def pinned_svg(baseline_dir=BASELINE_DIR):
    """(manifest, svg path) after checking the SVG against the manifest's digest."""
    man = manifest(baseline_dir)
    svg = os.path.join(baseline_dir, man.get("svg", "reconstruction.svg"))
    if not os.path.exists(svg):
        raise SetupError("the baseline SVG %s is missing" % svg)
    got = R.sha256_file(svg)
    if got != man["svg_sha256"]:
        raise SetupError("%s hashes to %s..., but the manifest pins %s...: the baseline is not "
                         "the release the manifest names" % (svg, got[:12], man["svg_sha256"][:12]))
    return man, svg


def _git(root, *args):
    return subprocess.run(["git", "-C", root] + list(args), capture_output=True)


def check_commit(man, svg_sha, root=ROOT):
    """(ok, note): the pinned commit's reconstruction.svg against the digest, as far as git can tell."""
    commit = man.get("commit")
    if not commit:
        return True, "the manifest names no commit; pinned by digest"
    try:
        inside = _git(root, "rev-parse", "--is-inside-work-tree")
    except OSError:
        return True, "git is not available; pinned by digest"
    if inside.returncode != 0:
        return True, "not a git checkout; pinned by digest"
    shallow = _git(root, "rev-parse", "--is-shallow-repository").stdout.strip() == b"true"
    if _git(root, "cat-file", "-e", commit + "^{commit}").returncode != 0:
        if shallow:
            return True, "commit %s is not in this shallow clone; pinned by digest" % commit[:12]
        return False, ("the manifest names commit %s, which this (full) clone does not have: "
                       "the pin cannot be checked against the release it claims" % commit[:12])
    path = man.get("svg", "reconstruction.svg")
    blob = _git(root, "show", "%s:%s" % (commit, path))
    if blob.returncode != 0:
        return False, "commit %s has no %s: the manifest does not describe that release" % (commit[:12], path)
    got = hashlib.sha256(blob.stdout).hexdigest()
    if got != svg_sha:
        return False, ("commit %s's %s hashes to %s..., not the manifest's %s...: the manifest "
                       "does not describe the release it names" % (commit[:12], path, got[:12], svg_sha[:12]))
    return True, "commit %s's %s matches the pinned digest" % (commit[:12], path)


def sheet_expectation(svg_sha, sheet_path=SHEET):
    """(image digest the published sheet recorded for this baseline, or None; note).

    The column is found by CONTENT -- its recorded SVG digest is the
    manifest's -- so the comparison cannot be skipped by a path spelled
    differently (a --baseline elsewhere, a symlinked root).  A sheet whose
    only rendered columns name other SVGs was drawn from an older baseline.
    """
    side = sheet_path + ".prov.json"
    try:
        rec = json.load(open(side))
    except (OSError, ValueError):
        return None, "no published sheet record to compare with"
    cols = rec.get("columns") if isinstance(rec, dict) else None
    if not isinstance(cols, list):
        return None, "the published sheet record has no columns"
    for col in cols:
        if isinstance(col, dict) and col.get("svg_sha256") == svg_sha:
            want = col.get("image_sha256")
            if not isinstance(want, str):
                return None, "the published sheet's baseline column records no image digest"
            return want, "the published sheet's baseline column"
    return None, "the published sheet was drawn from another baseline; publish.sh redraws it"


def verify(baseline_dir=BASELINE_DIR, root=ROOT, sheet_path=SHEET, compare_sheet=True):
    """Every setup check except rendering, on what is on disk now ([] if set up)."""
    try:
        man, svg = pinned_svg(baseline_dir)
    except SetupError as exc:
        return [str(exc)]
    png = os.path.join(baseline_dir, RENDER_NAME)
    rel = os.path.relpath(png, root)
    if not os.path.exists(png):
        return ["%s is absent (a clean checkout does not carry it)" % rel]
    try:
        R.read_provenance(png, require=True, expect_size=SIZE, expect_renderer=RENDERER, expect_svg=svg)
    except R.ProvenanceError as exc:
        return ["%s does not verify as the resvg render of the pinned baseline: %s" % (rel, exc)]
    if compare_sheet:
        want, _note = sheet_expectation(man["svg_sha256"], sheet_path)
        got = R.sha256_file(png)
        if want is not None and want != got:
            return ["%s (%s...) is not the image the published sheet was drawn from (%s...): it was "
                    "made by another renderer version, or not by tools/setup_baseline.py"
                    % (rel, got[:12], want[:12])]
    return []


def _remove(png):
    for p in (png, R.provenance_path(png)):
        try:
            os.remove(p)
        except FileNotFoundError:
            pass


def setup(baseline_dir=BASELINE_DIR, root=ROOT, sheet_path=SHEET, compare_sheet=True, verbose=True):
    """Render and verify the baseline; returns the render's path.  Raises SetupError.

    Whatever render was there before is removed first, on every path: a setup
    that fails -- on the pin, the commit, the renderer or the sheet -- leaves no
    render at all, never an earlier one that the gate's pre-flight could take
    for a set-up baseline."""
    out = os.path.join(baseline_dir, RENDER_NAME)
    _remove(out)
    man, svg = pinned_svg(baseline_dir)
    ok, note = check_commit(man, man["svg_sha256"], root)
    if not ok:
        raise SetupError(note)
    data = R.render(svg, SIZE, RENDERER)
    png_sha = hashlib.sha256(data).hexdigest()
    want, wnote = (sheet_expectation(man["svg_sha256"], sheet_path) if compare_sheet
                   else (None, "sheet comparison skipped (--for-publish: publish.sh redraws and "
                               "verifies the sheet)"))
    if want is not None and want != png_sha:
        raise SetupError("the baseline rendered here (%s, %s...) is not the image the published sheet "
                         "was drawn from (%s...): this environment does not reproduce the baseline "
                         "render -- install the pinned versions (requirements.txt)"
                         % (renderer_version(), png_sha[:12], want[:12]))
    try:
        open(out, "wb").write(data)
        R.write_provenance(out, svg, data, SIZE, RENDERER)
        R.read_provenance(out, require=True, expect_size=SIZE, expect_renderer=RENDERER, expect_svg=svg)
    except Exception as exc:                            # noqa: BLE001
        _remove(out)
        raise SetupError("the baseline render could not be written and verified: %s" % exc)
    if verbose:
        print("baseline: %s (%s)" % (man.get("label", "?"), os.path.relpath(svg, root)))
        print("  svg %s... = manifest; %s" % (man["svg_sha256"][:12], note))
        print("  rendered %s at %d px by %s (%s), png %s..."
              % (os.path.relpath(out, root), SIZE, RENDERER, renderer_version(), png_sha[:12]))
        print("  %s" % ("matches " + wnote if want is not None else wnote))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--baseline", default=BASELINE_DIR, help="baseline directory (manifest + SVG)")
    ap.add_argument("--sheet", default=SHEET, help="the published sheet whose record the render must match")
    ap.add_argument("--for-publish", action="store_true",
                    help="skip the comparison with the published sheet (publish.sh redraws and verifies it)")
    a = ap.parse_args()
    try:
        setup(a.baseline, sheet_path=a.sheet, compare_sheet=not a.for_publish)
    except SetupError as exc:
        print("SETUP FAILURE: %s" % exc, file=sys.stderr)
        print("(this is a setup failure, not an artwork regression: nothing was tested)", file=sys.stderr)
        return SETUP_FAILURE
    except Exception as exc:                            # noqa: BLE001
        print("SETUP FAILURE: unexpected %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        print("(this is a setup failure, not an artwork regression: nothing was tested)", file=sys.stderr)
        return SETUP_FAILURE
    print("baseline setup OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
