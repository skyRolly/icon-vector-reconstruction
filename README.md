# icon-vector-reconstruction

A resolution-independent reconstruction of `reference.png` — a 1024x1024 dark
icon showing two luminous cyan curves pinched around a central light inside a
rounded-square frame — as a hand-built, parametric SVG.

| reference | reconstruction | difference (x4) |
|---|---|---|
| ![reference](out/side_reference.png) | ![reconstruction](out/side_reconstruction.png) | ![difference](out/side_diff.png) |

<!-- DELIVERABLE:START -->
**Primary deliverable: [`reconstruction.svg`](reconstruction.svg)** — 35 named
layers, 79 KB, no embedded bitmap and no traced outlines. Every mark is a
primitive driven by a named parameter in
[`src/params.json`](src/params.json): one path for the frame, two cubic-Bézier
paths for the luminous curves (reused, offset and clipped, by every glow
layer), and blurred ellipses, rects, cones and gradients for the optical
effects.
<!-- DELIVERABLE:END -->

<!-- METRICS:START -->
## Fidelity

Reconstruction rendered at 1024 px (resvg) against `reference.png`:

| metric | value | for scale |
|---|---|---|
| mean absolute error | **1.877** / 255 | a flat black canvas scores 17.89 |
| RMSE | 4.049 | |
| MAE on a 1/2.2 display curve | 5.447 | weights the dark background as the eye does; black scores 59.7 |
| SSIM (luminance) | **0.9741** | black scores 0.142 |
| worst single-channel error | 110 | |
| pixels off by more than 2 / 8 / 24 | 34.4% / 4.9% / 0.8% | |
| mean bias | -0.241 | |

Per region (MAE): frame band 2.50, centre 90 px 7.77, bright pixels 9.50, dark background 1.39, everything else 1.65.

About a quarter of that error is the reference's own JPEG noise: decomposed by
scale, the background residual implies an MAE floor of 0.57-0.61 per channel
that no reconstruction of the underlying design can go below.

The two regions a whole-image average cannot police, from
`tools/diagnose.py` (full report in `out/diagnostics.json`):

| targeted measurement | value |
|---|---|
| MAE within 110 px of the central light | 6.41 |
| worst ring of the flare's radial profile | -4.3 code values at r = 30-45 |
| curve glow, rms relative error over 21 signed-distance bins | 4.0% |
| the same, resolved along the curve (71 cells) | 5.7% |
| light in the four interior corners, rms relative error | 5.0% |
| worst single bin of that profile | -11.8% at s = 9..14 px |
| left lobe, MAE more than 25 px from the ridge | 1.36 (bias -0.17) |
| right lobe, MAE more than 25 px from the ridge | 1.31 (bias -0.11) |

Cross-engine: the same SVG in resvg and headless Chromium agrees to MAE 2.680 (SSIM 0.9555); see `out/validation.md` for the resolution sweep.
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
tools/isolate.py         recovers one layer group's own contribution from the reference
tools/diagnose.py        targeted reports for the flare, the lobes and the glow profile
tools/ray_report.py      the four diagonal rays: peak, angle and width against the reference
tools/core_report.py     the flare core's radial falloff, in bands, where a blur would show
tools/chroma_report.py   colour by distance from a curve ridge, where the paleness is
tools/measure_flare.py   sets the rays' and flanks' amplitudes from those measurements
tools/wedge_report.py    angular modulation west of the flare, where a regional mean is blind
tools/arm_report.py      the horizontal arms, scored against a matched null along the ridge
tools/vstreak_report.py  the vertical line through the core, north and south reported apart
tools/fan_report.py      whether the westward fan is too bright or too long -- different faults
tools/line_shape.py      the long line's transverse spread and colour, rather than its height
tools/line_report.py     the three horizontal lines' amplitudes, ridges masked
tools/compare_sheet.py   reference | render | signed difference, by region and by scale
tools/flare_view.py      the flare in RGB, luminance and chroma at three scales, side by side
tools/visual_regression.py  the twelve recurring visual failures, as ratios to the reference
tools/publish.sh         the one command that produces a reviewable release
tools/regions.py         the measured anchors and region geometry both of those share
tools/test_pipeline.py   regression checks that keep optimisation results meaningful
tools/validate.py        multi-resolution and cross-engine validation report
tools/update_readme.py   writes the measured metrics back into this file
docs/METHOD.md           what the image is made of, and how it is reproduced
docs/DECISIONS.md        decision record: what was chosen, why, what was rejected
docs/stage1_findings.md  the first-pass measurements the rest was built on
out/analysis/            per-component measurement reports
out/diagnostics.json     the targeted flare / profile / corner measurements
out/prune.log            what each layer is worth, as MAE
out/                     renders, difference images, metrics, validation report
```

## Reproducing

Needs Python 3 with `numpy`, `Pillow` and `resvg-py` (`pip install numpy pillow
resvg-py`) — and nothing else: `tools/test_pipeline.py` checks that every shipped
module imports only those three plus the standard library, because
`tools/diagnose.py` once needed SciPy that this line did not mention. Headless
Chromium is optional and only used for the second opinion in `tools/validate.py`.

**Renderer.** resvg is the acceptance renderer: every number quoted here, and
every objective the optimiser minimises, is measured on its output at 1024 px.
Chromium is a cross-check only. The two disagree by a known, measured amount
(`docs/DECISIONS.md` D12) and the artwork is not adjusted to suit Chromium.

```sh
python3 src/build_svg.py                                    # params -> reconstruction.svg
python3 tools/render.py reconstruction.svg out/r.png --size 1024
python3 tools/compare.py reference.png out/r.png --out-prefix out/diff
python3 tools/validate.py                                   # sizes 256..4096, both engines
python3 tools/validate.py --quick --no-chromium              # resvg only, no browser needed
python3 tools/probe_compare.py out/r.png                     # geometry/alignment probes
python3 tools/diagnose.py out/r.png                          # flare / lobe / profile reports
python3 tools/test_pipeline.py                               # optimiser correctness checks
sh tools/optimize_all.sh                                     # refit everything from scratch
```

`tools/compare.py` writes `out/diff_diff.png` (absolute difference, x4 gain),
`out/diff_signed.png` (red = reconstruction too bright, blue = too dark) and
`out/diff_sbs.png` (side by side).

## How it works, in one page

The reference decomposes into geometry plus smooth optical falloffs, so the SVG
is a stack of primitives composited with `mix-blend-mode: screen` over black:

The counts below are the shipped structure; the parameter values live in
`src/params.json`, which is the single source of truth for them. Prose that
restated those numbers drifted out of date twice, so it no longer does.

1. **Background** — a flat exterior in three pieces (body, top edge, corners),
   then the frame shape filled with a base colour, two broad radial gradients
   and a vertical ramp.
2. **Glow** — six blurred copies of each curve's path at effective cross-curve
   widths from 3.3 to 87 px, four offset inward and two outward. The measured
   facts they reproduce: the glow is 2.8-3.5x brighter on the concave side, and
   each component carries its own measured fade along the curve, emitted as the
   measured stations themselves. A seventh component closing the gap between
   5.8 and 20.6 px was built and measured; it raises what the basis can achieve
   beside the ridge but did not improve the render, and is not shipped
   (docs/DECISIONS.md D19, D22).
3. **Central light** — thirteen layers: two stretched radial blooms, four
   horizontal streak components at the three measured line heights, five
   one-sided rays at their measured angles and widths, and two broad flanks.
   There is no separate glint layer; the brightest pixels come from the streak
   and bloom stack. The four diagonal rays are each measured rather than
   assumed: the right-hand pair is at 45.6 and 327.8 degrees and is 4-5 px
   wide, against the left pair's 8-11 px, so they are not mirror images of each
   other (D26), and it runs out to r = 170-230 px where the left pair fades by
   140 (D32). Two of them are a sharp spike on a broad fan, which is why the
   flanks are their own layers (D29). A different rebuild of this group into
   fourteen layers is recorded in D14/D21 and is not shipped — it measured
   worse (D22).
4. **Curve cores** — a hard-edged bright stroke on each path plus a narrower
   inset one, because the measured core is 5.8 px at the tips, 8.4 px at
   mid-height, and asymmetric about its own centre-line.
5. **Rim** — two frame-ring strokes, a uniform base and a gradient-painted rim,
   because the measured rim brightness peaks at the middle of each edge and the
   top edge is twice as bright as the bottom. Two further layers light the four
   interior corners, which lie past the curve ends and so get no curve glow.

Three measurements did most of the work:

* **The curves are not conics.** Two cubic Beziers joined at the apex with a
  vertical tangent fit the ridge to 0.083/0.093 px; the best ellipse arc manages
  0.331/0.473 px and leaves a systematic 4-5 lobe residual.
* **The frame corners are continuous-curvature corners**, three arcs each
  (blend r 639, main r 163.56, blend r 639): the local radius of curvature runs
  250-400 px near the straight edges and 145-175 px through the 45-degree
  region, and a circle fitted to the corner points cannot even be tangent to
  the measured straight edges.
* **All the light lies in a narrow non-negative colour cone** — white(1, 1, 1),
  cyan(0, 0.94, 1.00) and blue(0, 0, 1) — so each layer carries three
  non-negative amounts rather than three free channels, and the cone's
  `R <= G <= B` is a constraint the fit cannot escape by inventing a green or
  magenta layer. All three are needed: over the 946 964 reference pixels above
  luminance 3, the non-negative fit in this basis is off by 0.010/255, while
  dropping blue and using white+cyan alone is off by 1.84/255. The reason is the
  dark field, which is not cyan: across its 620 317 pixels between luminance 3
  and 14 the mean colour is (1.8, 7.1, 13.4), G/B = 0.53 against cyan's 0.94.

Because everything is screen-composited, the render has the closed form
`out = 1 - prod(1 - A_i k_i)`, so each layer's colour can be fitted analytically
from a single white render of that layer. That is why the fitting loop is fast
enough to search the geometry.

## Known limitations

* **The banding budget is now the binding constraint on the flare.** The profile
  error in the 26 px strip beside each ridge has a ceiling of 5.00%, and this
  iteration's three measured corrections spend it: the horizontal lines +0.09,
  the west fan +0.08, the ridge colour trade +0.08. They do not all fit. The
  combination that is best on structure measures 5.03% and is **not shipped**;
  line A's falloff was given back instead, so its error rises from 2.95 to 4.02
  (still below the 3.41 it had before). Raising the ceiling to fit the result was
  declined, for the same reason it was declined in D31. D37 has the table.
* **The flare region's mean absolute error rose while every structural measure
  in it improved** — 7.138 to 7.202 within 110 px of the core, against a wedge
  modulation of 5.62 to 3.83, three horizontal lines from 12.63 to 6.73, and
  bright pixels at the core from 13 to 10 where the reference has 10. This is
  not incidental: the angular and line diagnostics exist because a regional mean
  cannot see a redistribution, and it will sometimes move against them.
* **The worst single-channel error rose from 104 to 110.** It is a handful of
  pixels on the curve crest beside the flare, where the reference reaches R 254
  and the reconstruction 249.
* **The paleness beside each curve is improved but not closed.** In the 4-8 px
  ring the chroma deficit falls from 15.19 to 10.74 code values and the red
  excess from 6.75 to 3.51, but the ring is also 7% too dark, and a further
  white-for-cyan trade drives red negative before the chroma closes. That
  residual is an amplitude problem, not a colour one.
* **Three of the four rays match the reference's edge hardness; the upper-left is
  the exception, and it is too SOFT, not too hard.** Defining the softness index
  as the 25-75% edge run over FWHM of the mean transverse profile (a Gaussian is
  0.385, a blurred slab under 0.35), measured on the stacked, ridge-masked,
  axis-aligned profile — a pipeline that recovers each rendered ray layer's own
  exact value to ±0.03 — the reference reads 0.306 / 0.359 / 0.320 / 0.442 for the
  upper-left, lower-left, upper-right and lower-right rays against the render's
  0.340 / 0.339 / 0.326 / 0.343. Only the lower-right reference ray is materially
  softer than its rendered counterpart. An earlier version of this list reported
  0.46-0.48 for the reference's left pair and concluded that all four were softer;
  that came from a per-radius peak statistic, which is biased upward on an image
  with the reference's 8×8 blocking — the same numbers can be manufactured by
  adding matched noise to the render, whose true edges are unchanged. See D38.
* The reference's JPEG blocking and its low-frequency "smudge" texture are not
  reproduced, by choice: together they set an MAE floor of ~0.6 per channel.
* The two dark axial wedges between the diverging curves used to be
  over-predicted by ~4 code values, and this list blamed the additive stack for
  it: "a screen stack can only add light". That was the wrong diagnosis. The
  wedges are dark because nothing in the reference puts light there, and the
  over-prediction was two model errors — a broad glow that was not one-sided
  and a central bloom with more than twice its measured reach — both fixed in
  `docs/DECISIONS.md` D13 and D14.

* **The same SVG is about 2.8 code values brighter in Chromium than in resvg.**
  Chromium composites each dim screen layer 0.26-0.33 counts brighter, and over
  a stack this deep that accumulates to a near-uniform lift of the dark
  background;
  removing the mean offset leaves the two engines agreeing to MAE 1.36. It is a
  compositing-precision artefact rather than a structural difference, it cannot
  be merged away (a gradient modulates alpha, and each of these layers carries
  a different colour), and it is the one measure that got worse as the
  reconstruction gained elements, so the reconstruction is not changed to suit
  one engine. `docs/DECISIONS.md` D12 has the per-layer measurements.
* The true peak radiance of the cores and the streak is unrecoverable: G and B
  clip at 255 over those pixels in the reference. Any model that clips in the
  same places matches them.
* **The coherent cross-curve structure beside each curve is still about 1.8x the
  reference's** in the 26 px strip next to the ridge (1.23x on the right curve),
  falling to 0.96x by a 12 px scale. Across the whole open lobe it is 0.68-1.04x
  — at or below the reference — so this is a localised defect at the curve's
  inner edge, not the whole-lobe banding it was first measured as. What makes it
  read more strongly than its amplitude suggests is that the reference carries
  structure of the same size under 0.7-0.9 counts of incoherent grain, and the
  reconstruction carries it naked; that is an observation about visibility, not
  an excuse, and it is not a reason to add grain. Softening the one layer
  responsible (`arc_glow1` carries 74%/60% of it) does reduce the ratio, to 1.20x
  at the widest blur its bounds allow -- and makes the profile error in the same
  strip worse as it does so, 4.00% to 6.55%, along with MAE and SSIM. So the
  layer is left alone: a blurred stroke that matches the reference's level there
  necessarily carries more fine cross-curve structure than the reference does,
  and separating the two needs a primitive that can be flat-topped, not a
  different blur.
* **The lobe interior's coherent profile error is several times its own bound.**
  The best the basis can do there, fitted to the lobe profile and nothing else,
  is 0.89%/0.97% — and it reaches that only by amplitudes that take the global
  MAE from 1.90 to 8.20 and the flare from 7.5 to 35.2. So the bound is not
  reachable, and what remains is the price of one basis serving the lobes, the
  frame, the field and the flare at once. Reducing it needs a different
  decomposition, not a better fit. `docs/DECISIONS.md` D19 has the measurements.
* **Each glow layer's cross-curve profile shape is constant along the curve** —
  only its amplitude tapers. The reference's varies. This is the structural
  reason the reconstruction's contours run further than the reference's, and it
  is the obvious next thing to change.

`docs/METHOD.md` has the measurements; `docs/DECISIONS.md` has the decision
record, including what was rejected and why; `out/analysis/` has the
per-component measurement reports the reconstruction was built from.
