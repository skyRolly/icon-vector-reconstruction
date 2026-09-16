# Outer rounded-rectangle frame — measurements

All numbers are **SVG user units** on the 1024×1024 viewBox: pixel column *i* covers
`[i, i+1]`, so its centre is at `i + 0.5`.

> **Coordinate warning.** `docs/stage1_findings.md` quotes the four centre-lines in
> *pixel-index* space (a coverage-weighted centroid over integer indices). **Add +0.5**
> to convert those to SVG user units. Once that is done, stage1's values and mine agree
> to ≤ 0.04 px. Everything below is already in SVG user units.

## Method and its verification

Every cross-section is fitted with an *opaque bar over two different backgrounds*:

```
v(t) = bg_o·(1−S(t−eo)) + A·(S(t−eo) − S(t−ei)) + bg_i·S(t−ei)
S = unit step ⊗ 1-px box ⊗ Gaussian(σ);  w = ei−eo,  c = (eo+ei)/2
```

The two-background term matters: the interior field is 4–10 code values brighter than
the exterior, and a single linear baseline (the obvious approach) mis-fits that step and
manufactures a fake "glow outside / dark rim inside" of ±4 % of the stroke.

Validation:
* On analytically exact area-sampled bars the estimator recovers `c` and `w` to **<1e-5 px**
  at every width and sub-pixel phase tested.
* On a resvg render of a plain rounded rect (`rx=170`, `stroke-width 6`) it returns
  w = 6.0000–6.0020 and the corner radius to 0.04 px, circle-fit residual 0.055 px rms.

## 1. Straight-edge centre-lines

| edge | centre-line | sd over the straight run | sem | n | straight run used | stage1 + 0.5 |
|---|---|---|---|---|---|---|
| left   | **66.5225**  | 0.0406 | 0.0020 | 421 | y 340–760 | 66.48 |
| right  | **951.5700** | 0.0305 | 0.0014 | 461 | y 320–780 | 951.59 |
| top    | **34.3555**  | 0.0166 | 0.0009 | 371 | x 330–700 | 34.38 |
| bottom | **991.6551** | 0.0226 | 0.0012 | 371 | x 330–700 | 991.68 |

Centre-line box **885.048 × 957.299**, centre **(509.046, 513.006)**, aspect 0.9245.
Margins: left 66.52, right 72.43, top 34.36, bottom 32.34. Residual tilt is ≤ 2e-4 rad
and has *opposite* signs on the left and right edges, so it is not a rotation — treat the
frame as axis-aligned.

The sd figures are the honest uncertainty (JPEG mottling + the real ±0.05 px wobble); the
sem is optimistic. The straight runs really are straight: a quadratic fit over the run
gives |a₂| ≤ 1.7e-6 px⁻¹, i.e. < 0.1 px of bow over 430 px.

## 2. Stroke width

| edge | width | sd | median |
|---|---|---|---|
| left   | 6.250 | 0.077 | 6.269 |
| right  | 6.046 | 0.074 | 6.047 |
| top    | 6.128 | 0.040 | 6.114 |
| bottom | 6.116 | 0.097 | 6.147 |

**Use stroke-width = 6.13 (±0.10).** The left−right difference (0.20 px) is far above the
statistical error but the estimator is provably unbiased, so it is a property of the
reference image (ringing / prior resampling), not something to design in.
Fitted extra blur σ = 0.06–0.16 px: the frame edges are as crisp as a clean vector edge,
so **do not add a blur or a soft edge**.

Width through the corners: measured with interpolated normal scans, the four corners give
6.16–6.39 while the same scan on the straight sections gives 6.14–6.31 — i.e. the width is
constant around the whole perimeter to within 0.05 px.

## 3. Corner geometry — *not* a circular rounded rect

Sub-pixel corner outlines were extracted with axis-aligned row cuts on the half of each
corner nearer the vertical edge and column cuts on the other half (no interpolation),
covering 8°–45° from each tangent plus 34 px of straight beyond. 199–200 points per corner.

Model comparison (residual = perpendicular distance to the model curve; the method's own
floor is 0.06 px):

| model | params | rms (px) per corner | verdict |
|---|---|---|---|
| superellipse \|x/a\|ⁿ+\|y/b\|ⁿ=1 | n≈6.4 | 2.52 / 2.53 / 2.70 / 2.61 | ruled out |
| SVG rounded rect, circular arc tangent to the measured lines | r = 172.2/172.2/171.1/171.6 | 0.844 / 0.835 / 0.662 / 0.749 | poor, max error 1.4–1.8 px |
| circular arc + free line offsets | r ≈ 167.1 | 0.410 / 0.412 / 0.353 / 0.389 | poor |
| single cubic Bézier corner | R≈185, k≈0.62 | 0.443 / 0.433 / 0.349 / 0.370 | poor |
| **3-arc corner (blend–main–blend), lines fixed** | r₁≈163.6, r₂≈639, turn 5.24° | 0.232 / 0.268 / 0.128 / 0.133 | good |
| **3-arc corner, lines free (≤0.8 px)** | r₁≈163.1, r₂≈376, turn 7.2° | **0.088 / 0.106 / 0.108 / 0.096** | at the measurement floor |

Why: the local radius of curvature, from sliding 12° circle fits, is **250–400 px near the
straights and 145–175 px (mean ≈ 160) through the 45° region** — a continuous-curvature,
"corner-smoothed" (squircle-style) corner, identical on all four corners. Two independent
signatures of the same thing:

* The stroke centre-line leaves the straight line **gradually**: it is still 0.66 px inward
  at 195 px from the box corner and 1.15 px at 175 px, where a circular corner of any radius
  that fits the 45° region would be exactly 0. See `frame_corner_deviation.png`.
* A circle fitted to the arc-only points sits **1.9–2.7 px inside** the straight edges in
  both coordinates, i.e. it is not tangent to them:
  TL (231.99, 199.09) r 162.81 · TR (786.14, 198.97) r 162.72 ·
  BR (786.25, 826.38) r 163.46 · BL (231.67, 826.69) r 162.95 (rms 0.07–0.11 px).

**The four corners share one radius**: r₁ = 163.56 ± 0.25 (3-arc fits) / 163.0 ± 0.35
(arc-only circle fits). Diagonal corner depth 70.35–70.70 px, identical to ±0.35 px.

**Tangent points / corner extent.** The curvature starts **205.5–212.2 px** from the box
corner along each edge (mean 209.0), not at 170. So the genuinely straight part of each
edge is x ∈ [275.5, 742.6] (top/bottom) and y ∈ [243.3, 782.7] (left/right).

**Recommended construction** (rms 0.09–0.27 px), per corner, three `A` commands with the
same sweep flag:
`straight → arc(r=639.1, turn 5.242°) → arc(r=163.561, turn 79.517°) → arc(r=639.1, turn 5.242°) → straight`.
Full `path_d` is in `frame.json → recommended_path`. Note r₂ and the turn are strongly
correlated: what is actually measured is the lateral blend offset r₂(1−cos α) ≈ **3.0 px**
over a **≈ 58 px** run, so any (r₂, α) pair with r₂α ≈ 58 px and r₂α²/2 ≈ 3.0 px works.

**Single-number fallbacks** if the lead wants a plain `rx`: 171.8 (best L2 to the corner
points, rms 0.66–0.84 px) or 170.4 (matches the diagonal corner depth exactly).

## 4. Photometry around the perimeter

418 stations at 8 px of arc length, all three channels, absolute opaque-stroke value.

Peak stroke colour at each edge midpoint, and the darkest point of each corner:

| where | stroke sRGB | lum |
|---|---|---|
| top middle (501, 34.4)    | rgb(112, 121, 128) | 119.2 |
| right middle (951.6, 460) | rgb(65, 75, 83)    | 73.7 |
| left middle (66.5, 412)   | rgb(65, 73, 78)    | 71.5 |
| bottom middle (485, 991.7)| rgb(50, 65, 67)    | 61.6 |
| TL corner min | rgb(23.5, 33.0, 39.4) | 31.4 |
| TR corner min | rgb(21.2, 31.9, 38.2) | 30.0 |
| BR corner min | rgb(17.6, 28.8, 32.7) | 26.7 |
| BL corner min | rgb(16.4, 25.7, 30.9) | 24.0 |

**Corner vs edge-middle:** corners are 26 % (top), 41 % (right), 34 % (left), 43 % (bottom)
of the adjacent edge-middle brightness. The top edge is ~1.9× the bottom and ~1.65× the sides.

Candidate models, rms of the stroke luminance (which spans 24–119):

| model | rms |
|---|---|
| vertical linear gradient | 19.5 |
| best linear gradient, any direction (θ=89°) | 18.9 |
| radial from the frame centre | 17.3 |
| f(distance to the nearest edge midpoint) | 14.8 |
| f(arc length from the nearest edge midpoint) | 14.1 |
| per-edge Gaussian bumps + floor (6 params) | 6.28 |
| **anisotropic radial, free centre** | **5.72** |

So it is **not** a vertical gradient and **not** a centre-radial falloff; the winner is a
radial gradient centred slightly **above** the frame centre and stretched ~13 % vertically.
Every edge is brightest at its own midpoint and the corners are the darkest points, which
kills all the linear models; the top/bottom asymmetry kills the symmetric radial ones.

```svg
<radialGradient id="frameGrad" gradientUnits="userSpaceOnUse"
   cx="508.34" cy="476.40" r="575"
   gradientTransform="translate(508.34 476.40) scale(1 1.13006) translate(-508.34 -476.40)">
  <stop offset="0.6957" stop-color="#6B737B"/>   <!-- rgb(107.1,115.5,123.1) -->
  <stop offset="0.7391" stop-color="#464D55"/>   <!-- rgb( 70.1, 77.4, 84.8) -->
  <stop offset="0.7826" stop-color="#374247"/>   <!-- rgb( 55.2, 65.7, 70.7) -->
  <stop offset="0.8261" stop-color="#242F33"/>   <!-- rgb( 35.5, 46.7, 51.4) -->
  <stop offset="0.8696" stop-color="#20292E"/>   <!-- rgb( 32.0, 41.3, 46.3) -->
  <stop offset="0.9130" stop-color="#202A2F"/>   <!-- rgb( 32.3, 42.0, 46.9) -->
  <stop offset="0.9565" stop-color="#111C21"/>   <!-- rgb( 17.3, 28.1, 33.3) -->
  <stop offset="1.0000" stop-color="#152025"/>   <!-- rgb( 21.0, 32.1, 36.6) -->
</radialGradient>
```

Stop colours are the **absolute** measured opaque-stroke sRGB values, so paint with
`stop-opacity 1`. `offset = hypot(x−508.34, (y−476.40)/1.13006) / 575`. Only offsets
0.68–1.0 are constrained by the frame; the inner part of the gradient is free.
The two stops at 0.870/0.913 are a real plateau, not noise (the corner regions bottom out).

Residual per edge for this gradient: top +0.8±3.2, right +0.7±4.8, bottom +2.5±5.2,
left +2.2±3.8, BR −0.7±2.9, BL +1.2±2.9, **TR −4.5±9.3, TL −9.5±12.4** — the two *top*
corners are the model's weak spot (measured brighter than predicted). If the lead wants
those right, the alternative is 4 per-edge linear gradients (floor 23.5, σ 158.6 px in
arc length, amplitudes top 90.2 / right 42.2 / left 39.6 / bottom 29.0; rms 6.28).

End-to-end check: a resvg render of the recommended path + this gradient, compared with the
reference inside the ±4 px band around the frame, gives rms 7.1/7.3/7.5 code values in
R/G/B with a mean bias of −0.3/−1.3/−1.4, on a stroke that peaks at 128.

## 5. Single stroke or layered?

**Single stroke.** After the correct two-background bar model, the stacked residual
(421–461 rows per edge, in units of the stroke value, sem ≈ 0.001) is an oscillation
confined to |t| < 5 px: ≈ −0.02 at t = −2, +0.03…+0.06 at t = −1…0, −0.05…−0.08 at t = +2,
+0.01…+0.04 at t = +4, and **|residual| < 0.012 for |t| > 6 px** on all four edges.

* Absolute terms: the exterior rises only 0.5–1.3 code values above its far-field level over
  the 4–6 px just outside the stroke (1–2 % of the stroke), and the interior dips 2.4–2.5
  code values 1 px inside the stroke then overshoots +2 at 2 px.
* The stroke plateau is flat to ±5 %. The brightest pixel of every cross-section is the one
  just inside the **inner** boundary (+5…+7 % over the plateau mean); the pixel just inside
  the **outer** boundary is +3…+5 %. A *symmetric double* overshoot straddling a flat middle
  is edge-sharpening / JPEG ringing, not a designed inner hairline.

So: **no second ring, no bevel, no outer glow above ~1.5 % of the stroke**. Model the frame
as one flat-filled 6.13 px stroke and nothing else.

## 6. Hue around the perimeter

B ≈ G at every station (B/G = 0.98–1.05, no trend). The **R deficit is brightness-dependent**:

| stroke lum | 22 | 26 | 31 | 39 | 48 | 54 | 62 | 92 |
|---|---|---|---|---|---|---|---|---|
| R/G | 0.711 | 0.767 | 0.789 | 0.864 | 0.896 | 0.874 | 0.897 | 0.951 |

Per edge (R/G, B/G): top 0.953/1.016 · right 0.837/1.055 · left 0.887/1.014 ·
bottom 0.791/1.008 · TL 0.929/0.982 · TR 0.955/0.991 · BR 0.728/0.979 · BL 0.685/0.977.

So the dim corners are a desaturated **cyan** and the bright top-edge middle is nearly
**neutral**. This is *not* one colour at varying alpha, and it is not an sRGB-vs-linear
compositing artefact (in linear light B/G stays at 1.12 but R/G still moves 0.53 → 0.85).
The gradient therefore needs genuine colour stops — which the stops in §4 already carry.

## Background immediately inside vs outside the stroke

Extrapolated to the stroke boundary by the cross-section model (so free of stroke spill),
mean ± sd over each edge, sRGB:

| edge | outside | inside |
|---|---|---|
| top    | rgb(0.62, 1.99, 6.95) ±(0.8,0.6,0.6) | rgb(3.92, 11.95, 18.61) ±(1.7,2.6,2.4) |
| right  | rgb(0.70, 1.11, 1.91) ±(0.4,0.6,0.8) | rgb(2.05, 6.13, 12.16) ±(0.9,1.4,1.6) |
| bottom | rgb(0.55, 1.30, 3.14) ±(0.6,0.7,1.1) | rgb(1.47, 6.29, 12.22) ±(0.7,0.9,1.1) |
| left   | rgb(0.67, 2.08, 3.62) ±(0.6,0.7,1.5) | rgb(2.09, 7.99, 13.93) ±(1.2,2.8,2.9) |
| TL / TR corners | rgb(1.2,2.4,7.1) / rgb(0.9,2.6,7.0) | rgb(5.7,16.5,22.3) / rgb(4.8,15.0,20.3) |
| BR / BL corners | rgb(0.7,1.7,3.9) / rgb(0.8,2.0,5.4) | rgb(2.0,7.9,15.0) / rgb(1.8,7.3,14.5) |

The exterior far field (10–20 px out) is rgb(≈0.4, ≈1.4, 2–7) — i.e. the outside is
essentially the flat page colour and the interior field is a distinctly bluer teal that
keeps brightening inward. The interior level at the frame is *not* uniform: 18.6 (B) under
the top edge vs 12.2 under the bottom/right.

## Renderer caveat (affects any geometry tuning loop)

**resvg snaps stroke-outline edges to multiples of 0.25 px.** A flat-stroke resvg render of
the recommended frame at `stroke-width 6.130` measures 6.002 / 6.255 / 6.248 / 6.253 on
L/R/T/B — and all eight edge positions land exactly on 0.25 multiples. Chromium got the two
vertical edges right (6.122 / 6.126) but snapped the horizontal ones the same way (6.246).
So up to 0.13 px of measured-vs-rendered disagreement in edge position and width is renderer
quantisation; don't chase geometry below that against resvg.

## Files

* `out/analysis/frame.json` — all of the above plus the raw tables:
  `raw_straight_edge_scans` (per-scan-line centre/width/stroke value/backgrounds, 1 px steps),
  `corner_outline_points` (≈200 sub-pixel points per corner),
  `perimeter_photometry` (418 stations × RGB), `raw_stacked_cross_section_residual`,
  and `recommended_path.path_d`.
* `out/analysis/frame_corner_deviation.png` — measured corner departure vs the circular and
  3-arc models.
* `out/analysis/frame_corner_compare.png` — reference (top row) vs model render (bottom row)
  corner crops.
