# icon-vector-reconstruction

A resolution-independent reconstruction of `reference.png` — a 1024x1024 dark
icon showing two luminous cyan curves pinched around a central light inside a
rounded-square frame — as a hand-built, parametric SVG.

| reference | reconstruction | difference (x4) |
|---|---|---|
| ![reference](out/side_reference.png) | ![reconstruction](out/side_reconstruction.png) | ![difference](out/side_diff.png) |

**Primary deliverable: [`reconstruction.svg`](reconstruction.svg)** — 22 named
layers, ~53 KB, no embedded bitmap and no traced outlines. Every mark is a
primitive driven by a named parameter in
[`src/params.json`](src/params.json): one path for the frame, two cubic-Bézier
paths for the luminous curves (reused by every glow layer), and blurred
ellipses, rects and gradients for the optical effects.

<!-- METRICS:START -->
## Fidelity

Reconstruction rendered at 1024 px (resvg) against `reference.png`:

| metric | value | for scale |
|---|---|---|
| mean absolute error | **2.262** / 255 | a flat black canvas scores 17.89 |
| RMSE | 4.454 | |
| MAE on a 1/2.2 display curve | 6.361 | weights the dark background as the eye does; black scores 59.7 |
| SSIM (luminance) | **0.9664** | black scores 0.142 |
| worst single-channel error | 112 | |
| pixels off by more than 2 / 8 / 24 | 44.0% / 6.6% / 0.9% | |
| mean bias | -0.565 | |

Per region (MAE): frame band 2.64, centre 90 px 9.84, bright pixels 10.13, dark background 1.75, everything else 2.02.

About a quarter of that error is the reference's own JPEG noise: decomposed by
scale, the background residual implies an MAE floor of 0.57-0.61 per channel
that no reconstruction of the underlying design can go below.

Cross-engine: the same SVG in resvg and headless Chromium agrees to MAE 2.177 (SSIM 0.9653); see `out/validation.md` for the resolution sweep.
<!-- METRICS:END -->

## What is in here

```
reference.png            the ground truth (unmodified)
reconstruction.svg       the deliverable, generated from src/
src/params.json          every number that defines the artwork
src/build_svg.py         params -> SVG (geometry, gradients, filters, layer stack)
tools/render.py          SVG -> PNG at any size, via resvg or headless Chromium
tools/compare.py         metrics + difference images against the reference
tools/probe_compare.py   geometric probes: measure reference and render the same way
tools/fit_photometry.py  closed-form fit of every layer's light amount
tools/optimize.py        bounded coordinate descent over shapes/tapers/geometry
tools/optimize_all.sh    the full fitting cycle
tools/prune_layers.py    re-fits without each layer to see which ones earn their place
tools/validate.py        multi-resolution and cross-engine validation report
tools/update_readme.py   writes the measured metrics back into this file
docs/METHOD.md           what the image is made of, and how it is reproduced
docs/DECISIONS.md        decision record: what was chosen, why, what was rejected
docs/stage1_findings.md  the first-pass measurements the rest was built on
out/analysis/            per-component measurement reports
out/                     renders, difference images, metrics, validation report
```

## Reproducing

Needs Python 3 with `numpy`, `Pillow` and `resvg-py` (`pip install numpy pillow
resvg-py`). Headless Chromium is optional and only used for the second opinion
in `tools/validate.py`.

```sh
python3 src/build_svg.py                                    # params -> reconstruction.svg
python3 tools/render.py reconstruction.svg out/r.png --size 1024
python3 tools/compare.py reference.png out/r.png --out-prefix out/diff
python3 tools/validate.py                                   # sizes 256..4096, both engines
python3 tools/probe_compare.py out/r.png                     # geometry/alignment probes
sh tools/optimize_all.sh                                     # refit everything from scratch
```

`tools/compare.py` writes `out/diff_diff.png` (absolute difference, x4 gain),
`out/diff_signed.png` (red = reconstruction too bright, blue = too dark) and
`out/diff_sbs.png` (side by side).

## How it works, in one page

The reference decomposes into geometry plus smooth optical falloffs, so the SVG
is a stack of primitives composited with `mix-blend-mode: screen` over black:

1. **Background** — flat exterior, then the frame shape filled with a base
   colour plus two broad radial gradients.
2. **Glow** — three blurred copies of each curve's path, offset inward by the
   measured 3.3 / 16.2 / 62.1 px so their profiles are Gaussians of sigma
   7.2 / 26.9 / 56.6 px; the offsets are what make the glow 2.8-3.5x brighter
   on the concave side. Each carries its own measured fade along the curve.
3. **Central light** — two horizontally stretched blooms, a thin horizontal
   streak (sigma 2.2 px across, e-folding 30 px along), three one-sided
   diagonal rays, and a separate compact glint just inside the right curve's
   apex, which is where the icon's actual brightest pixels are.
4. **Curve cores** — a hard-edged bright stroke on each path plus a narrower
   inset one, because the measured core is 5.8 px at the tips, 8.4 px at
   mid-height, and asymmetric about its own centre-line.
5. **Rim** — one uniform stroke plus four edge-highlight strokes, because the
   measured rim brightness peaks at the middle of each edge and the top edge is
   twice as bright as the bottom.

Three measurements did most of the work:

* **The curves are not conics.** Two cubic Beziers joined at the apex with a
  vertical tangent fit the ridge to 0.083/0.093 px; the best ellipse arc manages
  0.331/0.473 px and leaves a systematic 4-5 lobe residual.
* **The frame corners are continuous-curvature corners**, three arcs each
  (blend r 639, main r 163.56, blend r 639): the local radius of curvature runs
  250-400 px near the straight edges and 145-175 px through the 45-degree
  region, and a circle fitted to the corner points cannot even be tangent to
  the measured straight edges.
* **All the light lies in a two-dimensional colour space** — white plus
  cyan(0, 0.94, 1.00), mean error 0.63/255 over 300 000 pixels — so each layer
  carries just two numbers instead of three free channels.

Because everything is screen-composited, the render has the closed form
`out = 1 - prod(1 - A_i k_i)`, so each layer's colour can be fitted analytically
from a single white render of that layer. That is why the fitting loop is fast
enough to search the geometry.

## Known limitations

* The reference's JPEG blocking and its low-frequency "smudge" texture are not
  reproduced, by choice: together they set an MAE floor of ~0.6 per channel.
* A screen/additive stack can only add light, so the two dark axial wedges
  between the diverging curves (5.1% of the interior) are over-predicted by
  ~4 code values — visible as the faint dark-red vertical band in
  `out/diff_signed.png`.
* The true peak radiance of the cores, the glint and the streak is
  unrecoverable: G and B clip at 255 over those pixels in the reference. Any
  model that clips in the same places matches them.
* Chromium's dim-layer rounding, above.

`docs/METHOD.md` has the measurements; `docs/DECISIONS.md` has the decision
record, including what was rejected and why; `out/analysis/` has the
per-component measurement reports the reconstruction was built from.
