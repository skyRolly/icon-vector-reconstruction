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
python3 tools/compare.py reference.png out/render_1024.png --out-prefix out/diff --json out/metrics.json --require-provenance --expect-size 1024 --expect-renderer resvg
python3 tools/diagnose.py out/render_1024.png --json out/diagnostics.json --require-provenance --expect-size 1024 --expect-renderer resvg
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
if [ "$validate_status" = 2 ] || [ "$validate_status" = 3 ]; then
    echo "!! validate.py exited $validate_status: the OPTIONAL cross-engine check did"
    echo "!! not run.  out/validation.{md,json} say why, and the README will omit the"
    echo "!! cross-engine line rather than publish a number nothing measured."
    echo "!! The resvg rows -- which are the report -- are unaffected; continuing."
elif [ "$validate_status" != 0 ]; then
    echo "FAIL: validate.py exited $validate_status" >&2
    exit "$validate_status"
fi
python3 tools/make_previews.py out/render_1024.png

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
echo "PUBLISH OK"
