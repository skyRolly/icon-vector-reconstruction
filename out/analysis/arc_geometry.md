# Arc geometry — centre-lines of the two luminous arcs

Component: **geometry only** (centre-lines, sub-pixel). Glow/photometry is another agent's.
Full numbers: `out/analysis/arc_geometry.json`. Diagnostic: `out/analysis/arc_geometry_residuals.png`.

All coordinates below are **pixel-index** (integer = pixel centre), the same frame as
`docs/stage1_findings.md`.

---

## 0. Read this first: a +0.5 px coordinate offset

I rendered a calibration SVG (`<line x1="500" ... stroke-width="8"/>`, 1024 viewBox at 1024 px,
resvg) and measured it with my estimator: it lands at pixel-index **499.5000 ± 0.0000**, width
8.000. So

> **SVG user-space coordinate = measured pixel-index coordinate + 0.5**

This applies to *every* sub-pixel number in `stage1_findings.md` as well (frame edges, mirror
axis, apexes). Getting it wrong puts the whole reconstruction half a pixel off-centre — a
uniform 0.5 px error is one of the larger error terms in the whole job. The `svg_paths` /
`bezier` entries in my JSON are given in **both** frames (`d_pixelindex`, `d_svg_userspace`).

## 1. Method and demonstrated precision

* Cross-sections are taken **perpendicular** to the curve (bilinear, 0.2 px steps, ±26 px),
  sampled uniformly in the parameter of a preliminary ellipse (≈1.15 px arc-length steps). This
  removes the shallow-slope problem at the tips entirely — no row/column bookkeeping needed.
* The core is not a blob: it is a **plateau ≈6–8 px wide with ≈1 px edges**. So the centre is the
  **midpoint of the two 50 %-of-plateau crossings**, which ignores the plateau shape completely
  (the plateau is not flat — it is slightly U-shaped, possibly JPEG overshoot).
* Channel: **R**. G and B clip at 255 along the cores (1198 / 1979 px); R reaches 254 in exactly
  one pixel. Chroma is heavily subsampled (within-2×2-block variance: Y 16.3, Cb 0.047,
  Cr 0.147), so R = full-resolution luma + a smooth chroma term and its edge positions agree
  with Y/G to 0.01–0.05 px.
* **Flare handling** — calibrated, not guessed. The flare's pedestal near the waist is strongly
  curved (measured wing polynomial ≈ 0.0235u³ − 0.167u² − 7.52u). Injecting exactly that into
  clean cross-sections biases a linear-pedestal estimator by **−0.096 px** and an order ≥3
  pedestal estimator by **+0.011 px**, so a cubic pedestal is used everywhere. Its correction is
  +0.13…+0.18 px (inward) over y ∈ [440, 620] and < 0.01 px elsewhere. **No rows are discarded.**
* Precision, four independent ways:
  1. a second, fully independent estimator (pure row/column scans, no oblique interpolation)
     agrees to **0.050 px RMS**, max 0.155, with no trend in y (all bands within ±0.02 px);
  2. the frame's **top edge** measured the same way is straight to **0.034 px RMS** over
     x ∈ [300, 740];
  3. on a synthetic rendered step-pair the centre is recovered to ±0.0000 px and the width to
     8.000/8;
  4. harmonic decomposition of the residual bottoms out at **0.055 px (L) / 0.063 px (R)**.
* Per-point uncertainty (spread over 10 estimator variants — level 0.4/0.5/0.6, pedestal order
  3/4/5, wings 13/16/20, channels R/Y/G): <0.01 px over most of the arc, ≤0.03 px near the tips,
  ≤0.05 px in the flare band.
* 1244 (L) + 1285 (R) ridge points are in the JSON (`ridge_points`, `q=1` flags the
  high-quality subset), plus a `gap`/`mid` table every 5 px in y.

**I also checked for a global image warp** (it would fake exactly this kind of residual): with
the corner-arc rows properly excluded (y ∈ [215, 812]) the frame's left and right edges are
straight to 0.17 px RMS and imply the *same* m(y) to 0.087e-3 — far too small (by ~40×) to
explain the arc residuals. The "1 px bow" you get on those edges over y ∈ [250, 850] is
contamination from the corner arcs starting early, not a warp.

## 2. Model comparison (orthogonal residuals, high-quality point set)

| model | k | RMS L | max L | RMS R | max R |
|---|---|---|---|---|---|
| circle | 3 | 1.651 | 5.38 | 1.846 | 6.14 |
| parabola (conic, B²=4AC) | 4 | 4.997 | 15.2 | 5.253 | 16.0 |
| **ellipse, axis-aligned** | 4 | **0.331** | 0.90 | **0.473** | 1.29 |
| ellipse, rotated | 5 | 0.321 | 0.74 | 0.224 | 0.62 |
| general conic (unconstrained) | 5 | 0.307 | 0.70 | 0.213 | 0.60 |
| superellipse (n free) | 5 | 0.188 (n=1.947) | 0.49 | 0.453 (n=1.981) | 1.10 |
| ellipse with split ry (up/down) | 5 | 0.301 | 0.71 | 0.154 | 0.43 |
| single cubic Bézier, free | 8 | 0.397 | 1.30 | 0.245 | 0.97 |
| single cubic Bézier, symmetric | 5 | 0.409 | 1.26 | 0.496 | 1.53 |
| **two cubic Béziers joined at the apex** | 12 | **0.083** | 0.26 | **0.093** | 0.27 |

**Neither arc is a conic.** An axis-aligned ellipse leaves a smooth, nearly even-in-y, 4–5 lobe
residual of ±0.4–0.5 px (see the PNG). The general conic converges to *exactly* the
rotated-ellipse solution, so the 5th conic parameter buys nothing. Rotation, a superellipse
exponent, and a split `ry` each remove a *different* part of the same residual (rotation and
split-ry help the right curve, the superellipse helps only the left) — the signature of a
parameter absorbing model error rather than measuring a real degree of freedom.

**Two cubic Béziers joined at the apex with a vertical tangent reach the noise floor** (0.083 /
0.093 px; the harmonic test says ~10 DOF are needed per curve, which matches a 2-segment cubic
path and rules out any 4–6 parameter primitive). This is almost certainly how the artwork was
drawn: three anchors — top tip, apex, bottom tip — with a vertical handle at the apex.

### Conditioning / what is *not* justified

Block bootstrap (300 resamples of 60-point contiguous blocks — blocks, because the residual is
smooth model error, not white noise), axis-aligned fit:

| quantity | L | R |
|---|---|---|
| apex x = cx+rx | 464.46 ± 0.18 | 544.48 ± 0.20 |
| cy | 514.82 ± 0.15 | 514.79 ± 0.31 |
| R_osc at apex = ry²/rx | 565.4 ± 2.9 | 566.5 ± 2.4 |
| rx | 388.9 ± 9.6 | 382.9 ± 7.3 |
| ry | 468.9 ± 4.5 | 465.7 ± 3.6 |

`corr(cx, rx) = −1.000` — cx and rx are a single degenerate direction, so **never quote cx or rx
on their own**; quote the apex and the apex curvature. `corr(rx, ry) = 0.996` as well.
Not justified: any rotation, the conic's 5th parameter, a superellipse exponent, a parabola or
a circle.

## 3. Numbers the lead needs

| quantity | value (pixel-index) | σ | SVG user-space |
|---|---|---|---|
| apex of left arc (rightmost point) | **x = 464.94**, y = 516.8 | 0.06 / 1.5 | 465.44, 517.3 |
| apex of right arc (leftmost point) | **x = 544.19**, y = 517.8 | 0.06 / 1.5 | 544.69, 518.3 |
| waist gap (min x_R − x_L) | **79.25 px** | 0.09 | — |
| y of the waist | **517.3** | 0.25 | 517.8 |
| mirror axis x | **504.53** | 0.05 | 505.03 |
| each arc's own up/down symmetry axis y | **514.85** | 0.2 | 515.35 |

The apex **x** values are model-free (local polynomial of x(y); stable to 0.04 px across windows
±50…180 px and degrees 2–4). The apex **y** is nearly unmeasurable — x changes by less than
0.01 px within ±3 px of the apex — so ±1.5 px there is harmless. `d²gap/dy² = 1.90e−3`: the gap
is only 0.3 px wider 20 px away from the waist. The two curves never touch.

The mirror axis 504.53 is **not** the canvas centre (512) and **not** the frame centre (508.54);
the arcs' symmetry axis y = 514.85 is 2.3 px **below** the frame centre y = 512.53.

### Mirror symmetry: real but imperfect

Fitting the reflected left ridge onto the right ridge (orthogonal distance):

| hypothesis | RMS | max | |
|---|---|---|---|
| pure mirror about x = 504.498 | 0.450 | 1.195 | best single-parameter answer |
| 180° rotation about (504.50, 514.77) | 0.630 | 1.705 | worse → it is a mirror pair, not a rotational copy |
| mirror + free rotation | 0.449 | 1.157 | best angle **−0.005°** → **no net relative rotation** |
| mirror + rotation + y-shift | 0.342 | 0.99 | +1.25°, −12.1 px (degenerate pair) |
| + scale | 0.295 | 0.79 | k = 0.9977 |

The signed residual is **≤ 0.25 px for y ∈ [90, 620]** and then +0.90 px at y ≈ 700 and −1.04 px
at y ≈ 880: **the asymmetry is real and confined to the bottom third**. It is not measurement
bias — mid(y) is reproduced to <0.03 px by every estimator variant (level 0.3–0.7, pedestal order
1–5, wings 12–22, channels R/Y/G) and by both independent estimators. Model-free, the **left**
curve is up/down symmetric to 0.37 px RMS while the **right** is not (0.95 px RMS, up to 1.8 px).

A strictly mirrored construction is still defensible: it costs ~1 px, at the two bottom tips only.

### Is either arc tilted? No.

The right curve's ~+1.6° preference is a real *fit result* but not a tilt of the artwork, and it
is **not** an artefact of excluding the flare rows:

* excluding the flare changes it by < 0.11° (all points +1.593°, excl. 468–562 +1.516°,
  excl. 440–600 +1.483°, excl. 400–640 +1.427°);
* but truncating the y-range swings the fitted rotation over **−24° … +11°** while the RMS
  *improves* (y 100–640: L −8.25°, R +7.47°; y 390–930: L +10.91°, R −3.60°; y 250–780:
  L −24.1°, R +9.6°). A rotation simply soaks up the much larger non-elliptical shape error. At
  matched truncated ranges the two sides prefer nearly equal-and-opposite angles — exactly what a
  mirror pair must do;
* measured directly, the best rigid rotation taking the reflected left ridge onto the right
  ridge is **−0.005°**.

So: use rot = 0 for both (RMS 0.33 / 0.47), or use −0.335° / +1.593° purely as best-fit numbers
(RMS 0.32 / 0.22) knowing what they are, or use the 2-cubic Bézier and the question evaporates.

## 4. Ready-to-use path data

Endpoints are at the **amp → 0** extrapolation of each tip's fade ramp (§5). Implied-centre
check: re-deriving the centre from each `A` command via the W3C endpoint→centre conversion
returns the fitted centre to **0.0000 px** in all four cases.

**Elliptical-arc form (SVG user space — already includes +0.5):**

```
left  : M 238.70 89.74  A 386.05 467.47 0    0 1 236.10 942.25   (centre 78.91 515.29, span 131.52°)
right : M 776.53 87.94  A 378.12 463.35 0    0 0 772.66 940.13   (centre 923.12 515.05, span 133.74°)
```

Best-fit-rotated variant (better on the right, RMS 0.224 vs 0.473):

```
left  : M 238.80 89.56  A 385.80 467.36 -0.34 0 1 235.98 942.02  (centre 79.16 514.59)
right : M 776.02 86.98  A 376.68 462.79  1.59 0 0 773.29 938.95  (centre 921.76 511.60)
```

**Recommended (2 cubic Béziers, RMS 0.083/0.093 px; SVG user space):**

```
left  : M 230.93 86.30  C 381.16 161.39 465.43 342.28 465.43 519.79
                        C 465.43 699.36 365.85 890.09 216.90 948.84
right : M 778.84 86.39  C 621.26 165.57 544.79 353.78 544.79 517.66
                        C 544.79 715.69 648.36 875.70 770.24 937.08
```

(apex handles are vertical by construction: |handle| = 177.5 up / 179.6 down on the left,
163.9 / 198.0 on the right. The right curve's unequal handles *are* its asymmetry. These two
paths span the **full detectable extent**, y ≈ 86 → 948, not the amp→0 point — pair them with an
opacity fade over the last ~60 px of each end. Do not extrapolate a cubic beyond its endpoint.)

**Ellipse arc expressed as cubics** (if per-segment control is wanted while keeping the ellipse):
splitting the arc at the apex, **2 segments deviate from the true ellipse by at most 0.018 px**
(L) / 0.020 px (R); 3 segments → 0.0017 px; 4 → 0.0003 px. A *single* cubic over the whole
131–134° arc is off by 1.10–1.22 px, so don't. Control points for all of these are in the JSON
(`bezier.*_arc_as_n2_cubics`).

**Waist warning.** Both ellipse options render the waist **0.79 px too wide** and ~2.5 px too
high (ellipse apexes 464.46 / 544.50 → gap 80.04; measured 464.94 / 544.19 → gap 79.25). The
2-cubic gets the gap to 79.36. The waist is the part of the image sitting right against the
central flare, so if ellipse arcs are used it is worth nudging each apex ~0.4 px inward
(e.g. rx → rx + 0.4 with cx fixed) at a cost of ~0.1 px elsewhere.

**End-to-end validation** — each candidate rendered with `tools/render.py` (resvg, sw=7) and the
ridge re-extracted, then compared with the reference ridge:

| model | L RMS / max | R RMS / max |
|---|---|---|
| 2 cubic Béziers | 0.110 / 0.30 | 0.127 / 0.40 |
| ellipse arc, axis-aligned | 0.331 / 0.78 | 0.469 / 1.09 |
| ellipse arc, rotated | 0.321 / 0.78 | 0.228 / 0.69 |

These reproduce the fit statistics, which validates the whole chain (estimator, fit, the +0.5
convention, the renderer).

## 5. Tips: where the stroke actually ends

The core width stays 5.9–6.2 px right out to the last detectable signal, so **the tips are an
opacity fade, not a geometric taper** — the path may be drawn to its full extent and faded
photometrically. R-channel plateau amplitude is 171 (L) / 166 (R); the fade ramp is close to
linear in arc angle.

| tip | amp = 25 | amp = 10 | amp = 5 | amp → 0 (extrapolated) | last credible core |
|---|---|---|---|---|---|
| L top | 244.9, 93.6 | 237.9, 89.7 | 227.4, 84.6 | **237.95, 89.70** (t=−1.144) | 215.1, 79.3 (t=−1.207) |
| L bottom | 250.2, 932.4 | 237.2, 939.1 | 226.3, 944.3 | **234.87, 940.39** (t=+1.151) | 216.7, 948.5 (t=+1.202) |
| R top | 765.0, 93.0 | 777.9, 86.4 | 790.1, 78.8 | **775.98, 87.35** (t=−1.194) | 793.5, 79.3 (t=−1.244) |
| R bottom | 758.1, 930.5 | 769.6, 936.7 | 781.3, 942.5 | **772.82, 938.38** (t=+1.182) | 808.7, 953.7 (t=+1.285)* |

\* the last R-bottom point may be contaminated by the frame's bottom-right corner; treat
|t| ≤ 1.21 as the trustworthy extent. If the glow model fades the stroke smoothly it is better to
extend the path to |t| ≈ 1.21 and let opacity reach zero there, otherwise a hard line-end shows.

## 6. Relationship to the frame — no coincidences

Frame taken as measured in stage 1: left 65.98, right 951.09, top 33.88, bottom 991.18, centre
(508.54, 512.53), 885.11 × 957.30, corner radius 170.

* **Ellipse centres vs frame edge mid-points: NO.** Fitted centres (78.41, 514.79) and
  (922.62, 514.55) vs edge mid-points (65.98, 512.53) and (951.09, 512.53). `cx` is individually
  meaningless (σ ≈ 7–9 px, corr(cx,rx) = −1.000), so "cx = frame side edge" cannot be excluded on
  cx alone for the left curve (1.18× worse RMS) — but the vertical half of the claim fails hard:
  forcing cy = 512.53 makes the fit **2.4–3.7× worse** (RMS 1.16–1.21 px). The arcs' own symmetry
  axis is y = 514.85, **2.3 px below** the frame centre, and that 2.3 px is 15σ.
* **Ellipse vertical extremes vs frame top/bottom: NO.** cy ± ry = 47.3 / 982.3 (L) and
  51.2 / 977.9 (R) vs frame 33.88 / 991.18 — 13–17 px inside the top, 9–13 px inside the bottom,
  i.e. 2–4σ, and pinning them costs 2.8–3.9× in RMS. `ry = frame half-height (478.65)` is also
  rejected (1.59× both sides).
* **Do the fading tips land on the frame corner arcs? NO — they stop well short.** The left top
  tip (fade-zero at 237.95, 89.70) is 114.2 px from the top-left corner-arc centre (235.98,
  203.88), i.e. **55.8 px clear** of the frame stroke; even the last detectable point (227.4,
  84.6) is 43.7 px clear. Extended, the ellipse *would* cross the corner arcs at (152.2, 55.9) /
  (158.0, 972.2) on the left and (865.8, 56.5) / (860.4, 971.6) on the right — at |t| = 1.36–1.42,
  some 12–16° of arc beyond where the stroke has already faded to nothing.

## 7. Bonus (not my component, but measured here)

The core is **not constant width**: the 50 %-level perpendicular width runs 5.96 px at the tips →
8.19 px near y ≈ 580–620 → 6.03 px at the other tip, essentially the same on both sides. The same
taper with the same relative amplitude (+38 % vs +34 %) appears at the 80 % level, so it is real
width variation, not a glow artefact. Note the maximum is near y ≈ 600, **not** at the waist
(y = 517). Full table in the JSON (`stroke_width_profile`).

The residual plot also shows a small ±0.05 px ripple with a ~8 px period in y — the JPEG 8×8
block grid. That is noise; do not model it.
