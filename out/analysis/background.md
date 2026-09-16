# Background field — direct measurement of `reference.png`

Component: **everything that is not the frame stroke, the arc cores or the central flare** —
the exterior colour outside the rounded rectangle and the interior "pedestal" field.

All coordinates are **pixel-index** (integer = pixel centre, 0..1023). For SVG on a 1024 viewBox add
**+0.5**. Full numbers: `out/analysis/background.json`. Scratch images: `out/analysis/background_*.png`.

Geometry taken from `out/analysis/frame.json` (stroke centre-line L 66.02, R 951.07, T 33.86,
B 991.16 in pixel-index; stroke width 6.135). For masking I use an equivalent circular corner radius
**171.758**, which reproduces the 1200 measured corner outline points to **0.79 px rms, 1.86 px max** —
ample for a 10 px exclusion band. `SD` below = signed distance to the stroke centre-line (negative = inside).
`AD` = distance to the nearest of the 2529 arc ridge points in `arc_geometry.json`. `FD` = distance to the
flare at (543.5, 514.5).

Masks used: **interior** SD < −8; **exterior** SD > +4.6; **glow-free main** SD<−8 ∧ AD>185 ∧ FD>300
(159 178 px = 20.0 % of the interior); **glow-free strict** SD<−8 ∧ AD>240 ∧ FD>350 (80 593 px = 10.1 %).
Justification for the 185 px cut: walking outward from each ridge along a row well away from the flare
(y = 700, left half, G channel) gives 253 (on the core) → 70 at AD 15 → 49 at 40 → 35 at 65 → 26 at 90 →
18 at 115 → 12 at 140 → 9 at 165 → 5 at 190 → 7 at 215 → 6 at 240 — i.e. the glow merges into the local
background (5–7) at AD ≈ 185–200. Independently, a free function of AD fitted on the AD>185 mask is flat
to ±0.5 G over AD 185–450 (§2.1), confirming there is no measurable glow left inside the mask.

---

## 1. The exterior

**Recommended: a single flat `#010207` = rgb(1, 2, 7).** That is simultaneously the median, the mode and
(to rounding) the mean of the far exterior, and it is the MAE-optimal flat colour.

| statistic over SD>4.6 (n = 211 406) | R | G | B |
|---|---|---|---|
| mean | 0.832 | 2.036 | 6.102 |
| median / mode | 1 / 1 | 2 / 2 | 7 / 7 |
| sd | 0.721 | 0.868 | 2.053 |
| 1st–99th pct | 0–2 | 0–4 | 1–9 |

Far exterior only (SD>22, n = 150 192): mean **rgb(0.858, 2.192, 6.666)**, median (1, 2, 7).

**It is not uniform.** There is a real dark halo hugging the frame, almost entirely in B:

| side | SD 6–14 | SD 14–30 | SD 30–60 |
|---|---|---|---|
| top    | (1.17, 2.29, **7.32**) | (1.26, 2.26, 7.29) | (1.28, 2.49, 7.49) |
| bottom | (0.64, 1.14, **2.39**) | (0.65, 1.28, 3.00) | (0.92, 1.92, 5.55) |
| left   | (0.68, 1.77, **4.08**) | (0.49, 1.50, 5.54) | (0.85, 2.01, 6.78) |
| right  | (0.72, 1.44, **3.40**) | (0.62, 1.58, 5.27) | (0.84, 1.95, 6.16) |

So the **top margin is flat at B ≈ 7.3 all the way to the canvas edge**, while the bottom margin sits at
B ≈ 1.1–3.0 for its whole 32 px depth and the left/right margins climb 3.4→6.8 over 60 px. Gradient
amplitude: **ΔB ≈ 6.2, ΔG ≈ 1.2, ΔR ≈ 0.8** (measured max−min of the side×band table). The four canvas
corners (48×48) differ by only ~1 code value and in the *opposite* sense to the halo:
TL (1.25, 2.68, 7.68), TR (1.07, 2.79, 7.79), BR (0.53, 3.52, 8.90), BL (0.49, 3.50, 8.52).

**Cost of ignoring the halo** (MAE over SD>4.6): flat (1,2,7) → R 0.515 / G 0.597 / B 1.492, overall
**0.868**, RMSE 1.452. A 5-band `f(SD)` concentric-stroke halo → 0.808 (no real gain). A full
4-side × 5-band model → **0.699**, all of the gain in B (1.492 → 1.041). So modelling the halo buys
0.17 code values of MAE over 20 % of the canvas = **0.035 of whole-canvas MAE**. Not worth an extra
element. (Also: at these levels B is carried almost entirely by the JPEG Cb DC coefficient, whose
quantisation step is ~2 code values of B, so the "gradient" is only 3 quantisation steps deep.)

For reference, `#000000` would cost MAE 2.99 — so the exterior is definitely *not* black
(consistent with stage 1).

---

## 2. The interior field

### 2.1 Model comparison, glow-free main mask (159 178 px), per-pixel MAE / sd

| model | k | R | G | B |
|---|---|---|---|---|
| flat | 1 | 0.917 / 1.165 | 1.493 / 2.124 | 2.081 / 2.660 |
| vertical linearGradient, 2 stops | 2 | 0.725 / 0.942 | 1.260 / 1.721 | 1.726 / 2.170 |
| vertical linearGradient, 5 stops | 5 | 0.715 / 0.932 | 1.238 / 1.686 | 1.717 / 2.152 |
| linearGradient tilted 17.5°, 2 stops | 2 | 0.718 / 0.926 | 1.110 / 1.526 | 1.418 / 1.795 |
| linearGradient tilted 17.5°, 5 stops | 5 | 0.702 / 0.904 | 1.026 / 1.403 | 1.347 / 1.707 |
| free `f(SD)`, 10 knots — *pure vignette* | 10 | 0.911 / 1.145 | 1.436 / 1.940 | 1.903 / 2.461 |
| free `f(AD)`, 7 knots — *pure arc-glow tail* | 7 | 0.917 / 1.159 | 1.536 / 2.092 | 2.063 / 2.630 |
| **radialGradient, isotropic, c = (881, 678), 6 stops** | 6 | **0.750 / 0.963** | **0.994 / 1.307** | **1.261 / 1.621** |
| radialGradient + free `f(SD)` | 15 | 0.744 / 0.947 | 0.931 / 1.209 | 1.202 / 1.523 |
| separable `f(y) + f(x)`, 8+7 knots | 15 | 0.677 / 0.875 | 0.926 / 1.222 | 1.207 / 1.507 |
| anisotropic radial (q = 1.06), 6 stops | 7 | 0.752 / 0.967 | 0.990 / 1.303 | 1.251 / 1.609 |

On the strict mask the same ranking holds; refitted there the radial 6-stop reaches **R 0.715 / G 0.825 /
B 1.072** MAE (sd 0.895 / 1.025 / 1.332, max 6.8 / 6.5 / 6.2).

Two negative results worth recording:

* **A vignette does not exist.** A completely free function of distance-to-frame explains 4 % of the G
  variance (sd 2.124 → 1.940). The field is *not* organised around the frame.
* **The field is not the arcs' glow tail.** A completely free function of distance-to-the-arcs explains
  *nothing* (sd 2.124 → 2.092, MAE actually worse). The large-scale field is an independent element.
* **Anisotropy is not needed** — the best q is 1.06, i.e. a plain circular `radialGradient`.

### 2.2 RECOMMENDED interior gradient (verified by an actual render)

```svg
<radialGradient id="bgField" gradientUnits="userSpaceOnUse" cx="881.5" cy="678.5" r="969.7">
  <stop offset="0"   stop-color="rgb(0.32,3.75,9.13)"/>   <!-- #000409 -->
  <stop offset="0.2" stop-color="rgb(1.73,6.61,13.41)"/>  <!-- #02070D -->
  <stop offset="0.4" stop-color="rgb(2.40,7.38,13.23)"/>  <!-- #02070D -->
  <stop offset="0.6" stop-color="rgb(2.13,9.53,17.56)"/>  <!-- #020A12 -->
  <stop offset="0.8" stop-color="rgb(1.64,6.04,12.72)"/>  <!-- #02060D -->
  <stop offset="1"   stop-color="rgb(5.30,17.51,25.77)"/> <!-- #05121A -->
</radialGradient>
```

(`cx`,`cy` are SVG user units = pixel-index (881, 678) + 0.5. Keep the fractional stop colours —
resvg and Chromium both accept them and both dither/round identically to within 0.4 code values.)

The centre sits at the **bottom-right of the icon**: the field is darkest there and brightest at the
top-left frame corner. Centre uncertainty ±25 px (the χ² surface is shallow; ±25 px changes the G sd by
<0.02). The 5-stop variant costs +0.12 G MAE; the 7-stop variant gains nothing.

The profile is **not monotone** (13.41 → 13.23 → 17.56 → 12.72 → 25.77 in B): the wobble at offsets
0.4–0.8 is ~±3 code values and the sharp rise at offset 1.0 is the bright rim inside the top frame
corners. A monotone design would not be the best fit; I report the best fit.

### 2.3 The one place this model fails, and its price

The radial gradient is fitted only where the field is measurable (the two side pockets plus the
near-frame ring). It **over-predicts the two axial wedges** — the dark regions between the two diverging
arcs above and below the flare. Over the whole interior: G exceeds the reference by >3 on
**41 056 px = 5.1 % of the interior** (12 866 px at y<400, mean overshoot 4.71; 27 612 px at y>640, mean
4.23; max 11.7). Because a glow layer can only *add* light, nothing downstream can correct this.

Integrated over the whole canvas the unremovable over-brightness is **R 0.301, G 0.372, B 0.519 code
values of MAE**. That is the honest price of the single-element background, and in my judgement it is
worth paying — every alternative that avoids it is much worse everywhere else (below).

### 2.4 Alternatives if the lead wants an additive-only pedestal

* **Flat lower-envelope base `#00030A` = rgb(0.5, 2.8, 9.8)** — the darkest coherent interior colour,
  measured in the two axial wedges (upper wedge x 496–536, y 185–235: mean rgb(0.79, 2.80, 9.77),
  median (1,3,10); lower wedge x 480–545, y 830–885: mean rgb(0.34, 2.84, 9.92), median (0,3,10)).
  It over-predicts only **0.29 %** of interior pixels, so everything else can be purely additive — but it
  under-predicts the glow-free field by a mean of **1.3 R / 4.2 G / 3.8 B**, i.e. the arc-glow layer would
  have to supply a very broad pedestal reaching 300–390 px from the ridges. (Per-channel over-prediction
  fractions: R 9.3 %, G 0.31 %, B 3.2 % — the R channel of this base is slightly too high; rgb(0, 2.8, 9.8)
  removes that.)
  Note this base is **3.1 code values bluer in B than the exterior** (interior B−G = 7.0, exterior
  B−G = 4.5; the difference is glow-independent, so it is real, though only ~1 chroma quantisation step).
* **Radial lower envelope** (same centre, profile fitted to the 2nd percentile of each 20 px annulus) —
  still over-predicts 5.5 % of pixels, and under-predicts the glow-free field by 2.0 G. Worse than both.
  Stops in the JSON.
* **A per-row lower envelope** (the 1st percentile of each row of the 9×9-smoothed interior) is tabulated
  in the JSON; the curve is G 12.6 (y 41) → 7.5 (y 89) → 3.9 (y 137) → **1.46 (y 209)** → 6.2 (y 305) →
  5.5 (y 497) → 3.6 (y 617) → 3.5 (y 737) → **1.83 (y 857)** → 5.1 (y 977).

I also publish a **260-station grid of the glow-free field** (`glowfree_station_grid`, AD>150, FD>260,
9×9-smoothed RGB) so whoever owns the arc glow can fit their profile against whatever pedestal the lead
chooses, rather than re-deriving it.

---

## 3. The structures visible at 6× gain

### 3.1 Dark band on the vertical centre line — REAL, but it is the gap between the two glows
G-channel cut (±6 rows averaged), floor vs shoulders in the window x 440–580:

| y | min at x | floor G | shoulder G | depth | FWHM |
|---|---|---|---|---|---|
| 150 | 519 | 3.31 | 7.12 | 3.8 | 53 px |
| 200 | 517 | 1.00 | 10.04 | 9.0 | 86 px |
| 250 | 511 | 2.85 | 16.31 | 13.5 | 94 px |
| 300 | 510 | 9.08 | 42.38 | 33.3 | 131 px |
| 800 | 511 | 2.85 | 13.15 | 10.3 | 76 px |
| 840 | 520 | 2.00 | 7.23 | 5.2 | 83 px |
| 880 | 486 | 2.54 | 4.38 | 1.9 | 64 px |

The minimum tracks **x ≈ 508 ± 6** (closer to the frame centre 508.5 than to the arcs' mirror axis
504.5; the scatter is larger than the difference, so this does not discriminate). Verdict: **this is not
a separate background element** — it is where the two arcs' convex-side glows are both weakest, and the
floor there (rgb ≈ 0.5, 2.8, 9.8) is the true base colour. The glow owner should check that their profile
reproduces a floor this low: the convex (gap-side) glow is **much weaker than the concave side** —
at 74 px from the left ridge at y = 250 the gap side reads G 8.3 while the inside reads G ≈ 21.

### 3.2 "Darker patches in the four quadrant corners" — fully absorbed by the recommended gradient
Relative to a *flat* background the four pockets are the dark patches (down to G 3.5–4.4 at x 832–896,
y 576–736 and G 5.5–6.4 at its mirror x 128–192). Relative to the **recommended radial gradient** no
64 px block in the glow-free region deviates by more than **−1.58 / +1.49 G** (most negative:
x 192–255 y 640–703 = −1.58; most positive: x 192–255 y 448–511 = +1.49). So they need no extra element.

### 3.3 A bright rim inside the frame — real, top-weighted, and NOT distance-to-frame
Walking inward from each arc on the left half, G falls to a floor and then **rises again** toward the frame:

| y | floor G (at AD) | rim G (at AD) | rise |
|---|---|---|---|
| 200 | 5.7 (110) | 15.3 (170) | **+9.6** |
| 260 | 7.8 (170) | 14.5 (230) | +6.7 |
| 340 | 6.4 (250) | 11.6 (290) | +5.2 |
| 420 | 7.4 (310) | 8.9 (350) | +1.5 |
| 515 | 6.1 (290) | 8.4 (370) | +2.3 |
| 600 | 5.9 (270) | 7.7 (370) | +1.8 |
| 680 | 5.6 (290) | 6.2 (310) | +0.6 |
| 840 | 4.4 (110) | 7.0 (190) | +2.6 |

Just inside the stroke the field is G 11.3–11.4 (top mid), 8.3–9.2 (left mid), 6.3–6.7 (right mid),
5.8–6.8 (bottom mid). Because the rise is 9.6 at the top and 0.6 at mid-bottom, this is *not* a function
of distance-to-frame (§2.1) — it is the outer part of the same top-left-bright gradient, and the
recommended radial gradient reproduces it (that is what the offset-1.0 stop is doing).

Caution for whoever owns the arcs: the two upper arc tips sit only **49–52 px inside the frame
centre-line** at (230, 86) and (786, 83), so the very bright inner top-left/top-right corner readings in
`frame.json` (tl inner G 16.5, tr 15.0) are **arc-tip glow, not background**.

### 3.4 Left/right and top/bottom asymmetry — both real
Mirror difference about x = 504.53, glow-free mask, left − right:

| y band | ΔR | ΔG | ΔB |
|---|---|---|---|
| 150–225 | +1.52 | **+5.09** | +3.70 |
| 225–300 | +0.94 | +3.30 | +4.50 |
| 300–375 | +0.75 | +1.70 | +3.22 |
| 450–525 | +0.15 | +1.15 | +1.47 |
| 600–675 | +0.72 | +1.65 | +2.73 |
| 750–825 | +0.07 | +0.78 | +0.60 |

The **left half is brighter than the right everywhere**, by up to 5 G in the upper third, fading to
+0.8 G at the bottom. Top − bottom about y = 514.85: +3.29 G at x 64–160, +0.98 at 160–256, +3.64 at
448–544, +1.84 at 736–832, +2.32 at 832–928, +2.10 at 928–1024 — the **top is 1–3.6 G brighter**.
Both asymmetries are produced automatically by the single off-centre radialGradient; the lead does not
need separate elements, but should not "symmetrise" the background.

### 3.5 Bright lobes between the arcs — not mine
Integrated over the interior, the excess above the recommended background is
**4.43e6 / 1.47e7 / 1.47e7** code-value·px in R/G/B (mean 5.4 / 17.8 / 17.9 per interior pixel);
395 208 px exceed the background by >3 G. That is the budget the arc-glow + flare layers must supply.

---

## 4. Texture and the noise floor

Residual after the recommended radial gradient (fitted on the main mask), evaluated on the glow-free
**strict** mask:

| | R | G | B |
|---|---|---|---|
| per-pixel sd | 0.901 | 1.079 | 1.396 |
| MAE | 0.716 | 0.856 | 1.126 |
| within-2×2 sd (= pixel noise) | 0.270 | 0.285 | 0.309 |
| 8×8 DC sd (blocking) | 0.656 | 0.687 | 0.690 |
| 32 px block-mean sd (= smudge) | 0.484 | 0.664 | 0.962 |

**JPEG blocking amplitude** (per-pixel step across 8-aligned block edges minus a mid-block control, /√2):
interior dark region **0.66 / 0.69 / 0.69** code values of DC offset per 8×8 block; exterior
**0.41 / 0.41 / 0.47**. Pixel noise: interior 0.29–0.33, exterior 0.14–0.17.

Residual autocorrelation along rows: 0.85 at lag 1, 0.72 at 2, 0.55 at 4, **0.39 at 8**, 0.17 at 16,
−0.05 at 32 (G). So the dominant correlated scale is the 8 px JPEG block; the remaining power is a
smooth ≥32 px "smudge" with 32 px block means ranging **−2.10 … +3.49** (sd 0.664 in G).

**Implied noise floor**: quadrature of pixel noise and 8×8 DC gives sd 0.718 / 0.752 / 0.764 in the dark
interior, i.e. an **MAE floor of ≈ 0.57 / 0.60 / 0.61** — no vector model can beat that. The recommended
model already sits at 0.72 / 0.86 / 1.13, within 0.15–0.5 MAE of the floor.

**Verdict on the smudge: do not reproduce it.** Perfect reproduction would move the interior-background
G MAE from 0.856 to about 0.60 — 0.26 code values over 20 % of the canvas, ≈ **0.05 code values of
whole-image MAE**. It has no symmetry, no relation to any construction line, and is exactly the
signature of a resampled/recompressed source.

---

## 5. Concrete SVG construction

```svg
<!-- 1. exterior -->
<rect x="0" y="0" width="1024" height="1024" fill="#010207"/>

<!-- 2. interior field: SAME path the frame stroke uses -->
<path d="<frame.json recommended_path.path_d>" fill="url(#bgField)"/>

<!-- 3. arc glows / arc cores / flare  (other agents) -->

<!-- 4. the frame stroke LAST, so it covers the fill edge -->
<path d="<same d>" fill="none" stroke="url(#frameGrad)" stroke-width="6.135"/>
```

No `<clipPath>` is needed: fill the **stroke centre-line path** and paint the stroke afterwards — the
6.135 px stroke straddles the path by ±3.07 px, so the fill edge and its antialiasing are completely
hidden. A `clipPath` using the same path is equivalent.

**Where does the interior field actually stop?** Measured, not assumed:

* Immediately **outside** the stroke the field reads R 0.7–1.1 / G 1.0–3.6 / B 1.4–5.7 — at or slightly
  *below* the far-field exterior (0.86 / 2.19 / 6.67), never at the interior level (2–3 / 6–11 / 12–19).
  A fill edge overhanging the stroke's outer edge by even 0.5 px would lift the adjacent exterior pixel by
  ≈ +2 G / +4 B; the observed sign is negative (JPEG undershoot). **No outset.**
* Immediately **inside** the stroke (SD −8…−5) the field reads rgb(3.10, 9.12, 15.48) on the left,
  (4.11, 12.02, 19.01) on top, (2.39, 6.47, 12.50) on the right and (1.46, 6.19, 12.11) on the bottom,
  dipping only 2.4–2.8 code values in the last 1.5 px — which `frame.json` independently identifies as
  ringing. **No inset gap.**
* **Conclusion:** the fill boundary lies within **SD ∈ [−4.5, +3.1] px** of the stroke centre-line and
  cannot be localised better than that from this reference. Painting it exactly on the centre-line is
  safe and indistinguishable from any other choice inside the stroke.

**Renderer verification** (I actually rendered this): against my continuous model, resvg reproduces it to
MAE 0.21 / 0.31 / 0.34 (max 0.92) and Chromium to 0.23 / 0.36 / 0.39 (max 1.42) — both interpolate
gradient stops **linearly in sRGB code space**, so the stop colours above need no gamma correction.
Against the reference, the rendered two-element background gives MAE **R 0.728 / G 0.978 / B 1.250**
over the glow-free main mask (Chromium 0.747 / 1.002 / 1.267) and **R 0.515 / G 0.597 / B 1.492**
over the exterior.

---

## Where the reference does not determine the construction

1. **The background under the arcs and the flare is unobservable.** 80 % of the interior is within 185 px
   of an arc ridge or 300 px of the flare. Any background/glow split there is a convention, not a
   measurement. I recommend the convention "background = the recommended radial gradient; glow = max(0,
   reference − background)", and I publish the 260-station glow-free grid so the split can be revisited.
2. **Best fit vs additive-only are in genuine conflict.** The best-fitting single gradient is 4–5 G too
   bright in the two axial wedges (5 % of the interior); the additive-safe flat base is 4 G too dark over
   the 20 % that is measurable. Both numbers are given; the choice depends on how the glow layers are fitted.
3. **The exterior's B channel is only determined to ±2–3 code values** because at these levels B is set
   almost entirely by the heavily quantised, 2×2-subsampled Cb DC coefficient. rgb(1,2,7) is the best
   single answer but rgb(1,2,5)…rgb(1,2,8) are all within ~0.2 MAE.
4. **Interior base vs exterior base**: the interior floor is 3.1 code values bluer in B. This survives the
   glow-independent B−G test but is only ~1 chroma quantisation step, so a lead who wants one colour for
   both is not contradicting the data.
5. **I could not verify** whether the dark axial band is a designed element or purely the two-glow gap —
   that needs the arc-glow radial profile, which is another agent's component. The band's FWHM (33 px at
   y = 250 measured on the raw profile, 86–94 px by the shoulder definition in §3.1) is narrower than a
   naive two-glow sum would give, so it is worth the glow owner's attention.
