#!/bin/sh
# The publish cycle: turn the committed parameters into the complete, checked
# set of release artifacts.  This is the definition of "release-ready" -- if it
# passes, a reviewer can reproduce every number the README reports.
#
# Order matters and is a dependency order, not a preference:
#   1. rebuild the SVG          -- everything below measures THIS file
#   2. render it
#   3. metrics, diagnostics, validation, previews   -- all measure that render
#   4. regression checks        -- on the rebuilt artefacts, not on stale ones
#   5. README last              -- it publishes 3, so 3 must be settled first
#   6. reproducibility          -- the committed params must rebuild this SVG
#
# README regeneration used to sit outside this cycle entirely, which is how a
# flare MAE of 6.37 came to be published against an actual 7.11: out/diagnostics
# .json was never regenerated and nothing checked that it matched the artwork.
set -e
cd "$(dirname "$0")/.."

echo "== 1. rebuild =="
python3 src/build_svg.py

echo "== 2. render =="
python3 tools/render.py reconstruction.svg out/render_1024.png

echo "== 3. measure =="
# --require-provenance: these two write the JSON the README publishes, so they
# must be able to PROVE the raster they measured came from the SVG rebuilt in
# step 1.  Without it a stale out/render_1024.png with an old sidecar beside it
# is measured and published as if it were the shipped artwork.
# --expect-size/--expect-renderer: hashing proves the raster came from this SVG,
# not that it is the RIGHT raster.  validate.py writes a Chromium render of the
# same SVG into the same directory with its own valid sidecar, so without these
# two the README could publish Chromium's numbers as the acceptance figures.
# --expect-svg: and all of that authenticates the RASTER.  The recorded
# svg_sha256 was still only a claim about a file nobody re-read, so a render
# that is perfectly authentic and four commits stale passed everything above --
# which is exactly how three of this iteration's verifiers came to measure a
# model that no longer existed.  This re-hashes reconstruction.svg and requires
# it to still be the SVG the sidecar names.
python3 tools/compare.py reference.png out/render_1024.png --out-prefix out/diff --json out/metrics.json --require-provenance --expect-size 1024 --expect-renderer resvg --expect-svg reconstruction.svg
python3 tools/diagnose.py out/render_1024.png --json out/diagnostics.json --require-provenance --expect-size 1024 --expect-renderer resvg --expect-svg reconstruction.svg
# The cross-engine check is documented as OPTIONAL, so it must not be able to
# stop a release -- but it must not be able to hide either, which is why
# validate.py grew distinct exit codes in the first place.  Both halves are kept:
# 2 (a found browser failed) and 3 (a configured browser is unusable) are
# reported loudly and do not abort; every other nonzero status is a failure of
# the resvg rows, which are the report, and still stops the cycle.
set +e
python3 tools/validate.py
validate_status=$?
set -e
cross_engine_ran=yes
if [ "$validate_status" = 2 ] || [ "$validate_status" = 3 ]; then
    cross_engine_ran=no
    echo "!! validate.py exited $validate_status: the OPTIONAL cross-engine check did"
    echo "!! not run.  out/validation.{md,json} say why, and the README will omit the"
    echo "!! cross-engine line rather than publish a number nothing measured."
    echo "!! The resvg rows -- which are the report -- are unaffected; continuing,"
    echo "!! and the final line of this run will say the check was not made."
elif [ "$validate_status" != 0 ]; then
    echo "FAIL: validate.py exited $validate_status" >&2
    exit "$validate_status"
fi
python3 tools/make_previews.py out/render_1024.png
# The flare inspection sheet is the instrument the acceptance decision rests on,
# so the documented release command has to produce it: a reviewer who runs this
# should not have to know the tool exists to see what it shows.
python3 tools/flare_view.py out/render_1024.png --out out/flare_view.png
# The before/after sheet is a release artefact too, and a checked-in one: it was
# drawn by hand once and would have gone on showing a "this release" column that
# no longer described the release (D62).  Its "before" is the previous ACCEPTED
# release, kept as its SVG in out/baseline/ with a manifest whose digest ties the
# two together; flare_parts refuses to draw if the manifest, the baseline render
# or this release's render does not match the SVG it is labelled as.
# The baseline's render is made by the same setup step CI runs (D66): only the
# SVG the manifest pins is rendered, and a failure there is a SETUP failure.
python3 tools/setup_baseline.py
python3 tools/flare_parts.py out/render_1024.png --svg reconstruction.svg \
    --baseline out/baseline --labels "this release" --out out/flare_parts.png
# ...and prove it: the sheet's provenance sidecar names every input by digest,
# and this refuses the release if the sheet does not describe the SVG rebuilt
# in step 1 and the documented baseline (D63).  test_pipeline repeats the check
# on the committed tree, so a sheet left stale by a hand-run release fails CI.
python3 tools/flare_parts.py --verify --svg reconstruction.svg --baseline out/baseline \
    --out out/flare_parts.png

echo "== 4. regression checks =="
python3 -u tools/test_pipeline.py

echo "== 5. README =="
python3 tools/update_readme.py

echo "== 6. reproducibility =="
# The committed parameters must rebuild the committed SVG byte for byte.  This
# is the check that catches an optimiser that reported one state and saved
# another, which has happened.
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
python3 src/build_svg.py --params src/params.json --out "$tmp/repro.svg" > /dev/null
if cmp -s "$tmp/repro.svg" reconstruction.svg; then
    echo "src/params.json reproduces reconstruction.svg exactly"
else
    echo "FAIL: src/params.json does not reproduce reconstruction.svg" >&2
    # POSIX sh: no process substitution.  Two plain files, then diff them.
    head -c 4000 "$tmp/repro.svg" > "$tmp/a.txt"
    head -c 4000 reconstruction.svg > "$tmp/b.txt"
    diff "$tmp/a.txt" "$tmp/b.txt" | head -20 >&2 || true
    exit 1
fi
if [ "$cross_engine_ran" = yes ]; then
    echo "PUBLISH OK"
else
    # Not blocking the release and not calling it clean either: a reviewer
    # reading only the last line must not be told a check ran when it did not.
    echo "PUBLISH OK -- EXCEPT the optional cross-engine check, which did not run"
    echo "(validate.py exited $validate_status; see out/validation.md).  Every"
    echo "resvg number published here was measured."
fi
