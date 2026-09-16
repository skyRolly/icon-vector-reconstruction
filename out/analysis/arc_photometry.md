# Arc photometry — core + glow of the two luminous arcs

Everything here is measured from `reference.png`. Full numbers, per-station tables and the raw
cross-sections are in `out/analysis/arc_photometry.json`. Geometry (centre-lines) is taken as given from
`out/analysis/arc_geometry.json`; I re-used its ridge points, smoothed with a local cubic in arc length
(the raw ridge points scatter 0.048 px (L) / 0.052 px (R) about my smoothed line), and sampled the image
bilinearly along the true normal at 0.25 px steps out to ±320 px, at 83 (L) / 86 (R) stations spaced
~14 px of arc length.

**Sign convention** (used everywhere below): `t` is the signed perpendicular distance from the
centre-line. **`t > 0` points toward the icon centre** (the convex side of each arc, the lens between the
two arcs); **`t < 0` points away from the icon centre, toward the nearer frame edge** — that is the
**concave** side, where the centre of curvature lies. Pixel-index coordinates (add 0.5 for SVG).

---

## 1. The one structural fact: the glow is not centred on the core

The glow sits on the **concave** side of each arc. Raw pixels, row y = 301 (no fitting involved):

```
left arc,  core at x = 418..425:   x=408..416 (concave side) G = 78,76,84,83,91,102,97,98,101
                                   x=426..434 (centre side)  G = 74,74,75,67,63,61,55,51,47
right arc, core at x = 584..590:   x=593..623 (concave side) G = 96,100,93,82,74,74,69,62,57,52,49
                                   x=581..575 (centre side)  G = 79,54,40
```

The background-subtracted outer/inner ratio at matched |t| is **3–7×** over y ∈ [215, 815] and falls to
1.2–1.8 near the tips. `docs/stage1_findings.md` describes the lobes as "brighter on the concave/centre
side" — those are opposite sides, and the measurement says **concave (away from the icon centre)**.

Consequence for fitting: any model whose components are *centred* on the core cannot work. Same 32
stations, same masks, amplitudes refitted per family (uniform-in-t rms in code values, all 3 channels):

| family (N terms) | N=1 | N=2 | N=3 |
|---|---|---|---|
| gaussian, centred | 7.06 | 6.13 | **5.91** |
| exponential, centred | 6.48 | 6.04 | **5.92** |
| gaussian, offset | 5.14 | 2.82 | **2.18** |
| exponential, offset | 4.30 | 2.49 | **2.18** |
| power law (1+|t−δ|/r₀)^−n, offset | 4.13 | 2.49 | 2.20 |
| gaussian, per-side σ (centred) | 4.17 | 2.58 | **2.15** |

* Centred families stall at ~5.9 whatever you do; offsetting drops them to 2.2 (JPEG noise floor ≈ 1.3).
* With **one** term the profile is broader-tailed than a gaussian (exp 4.30 / power 4.13 < gauss 5.14).
* With **three** terms every family ties. So use gaussians — that is what `feGaussianBlur` gives you.
* The power-law family *degenerates to the exponential limit* at N=2 (r₀ → 1.4e6 px, n → 2.4e4, i.e.
  r₀/n = 58 px), so there is no evidence for a genuine 1/rⁿ tail.
* Per-side-σ and offset descriptions are equivalent (2.15 vs 2.18). Offsets are drawable with one
  blurred stroke; per-side σ is not.

---

## 2. Core

Fitted per station in **R** (the glow is nearly red-free, so R is almost a pure core channel) over
|t| ≤ 26 with a box⊗gaussian core plus a cubic pedestal:

| quantity | value |
|---|---|
| edge blur σ | **0.45–0.75 px** (median 0.59) → the core is a **hard-edged stroke, not blurred**; that is plain anti-aliasing |
| width w (= FWHM to 0.03 px) | **5.8 px at both tips → 8.5 px at mid-height**, max near y ≈ 600 (the 2 extreme tip stations hit the 3.0 px fit bound at 4 % coverage — ignore them) |
| peak value in R | 172–219 (never clipped); G, B peak 216–252 and clip only inside \|y−515\| < 130 |
| colour | **R/G = 0.877 ± 0.03, B/G = 1.010 ± 0.02 → #E0FFFF** |
| peak coverage | 0.69–0.86 of a #E0FFFF layer over y ∈ [170, 860]; ≈ 0.97 of that layer's G at y ≈ 790–830 |

The colour comes two independent ways: (a) the ratio of screen-un-mixed coverages covR/covG/covB per
station (0.86–0.90 / 1.00–1.02 over y ∈ [140, 880]); (b) a scan of the fixed core colour inside the full
3-channel screen fit — median rms 2.72 / **2.68** / 2.74 / 2.84 for R/G = 0.84 / 0.877 / 0.91 / 0.94.
So the core is *not* white: R is 12 % below G. B/G = 1.00 and 1.013 are indistinguishable (2.69 vs 2.68).
G and B **do not** clip over most of the arc, so this is a real measurement, not an extrapolation.

---

## 3. Glow decomposition

Model, exactly as the reference behaves — **screen compositing over black in sRGB code space**:

```
V_ch = 255 · [ 1 − (1−bg_ch/255) · (1 − a_core·coreCol_ch/255 · box⊗gauss(t; w, 0.59))
                                 · Π_i (1 − A_i,ch/255 · exp(−½((t−δ_i)/σ_i)²)) ]
```

with **one global set of σ and δ for both arcs and all stations** (only the amplitudes taper):

| term | σ (px) | δ (px, negative = offset to the concave side) | G amplitude range | R/G | B/G |
|---|---|---|---|---|---|
| 1 | **7.22** | **−3.28** | 0 → 45–55 at y≈200/810 → 95–125 mid-arc | 0.02–0.18 (0.23–0.57 for \|y−515\|<180) | 1.006 |
| 2 | **26.92** | **−16.20** | 0 → 28–34 at y≈200/810 → 65–100 mid-arc | 0.00–0.04 | 0.988 |
| 3 | **56.59** | **−62.07** | 0 for \|y−515\|>310 → 28–34 mid-arc | 0.00–0.07 | 1.003 |

Median cross-section rms: **2.68 (L) / 2.48 (R)** code values over the whole ±320 px cut, all three
channels, against a JPEG noise floor of 1.3; **2.3** for stations away from the flare. A 4-term variant
(σ = 6.13, 10.74, 35.76, 56.18; δ = −1.45, −15.08, −20.59, −81.92) reaches 1.91 — not worth a 4th layer.

**Glow colour.** Background-free per-station regressions of R on G and B on G over |t| ∈ [10, 150]
(185 station-sides): **dR/dG = 0.041 ± 0.051, dB/dG = 1.008 ± 0.090**. Per-term medians agree
(B/G = 1.006 / 0.988 / 1.003). So the glow is **pure cyan, #0AFFFF**, with B = G to 1–2 %. The apparent
blue excess in raw ratios (B/G = 1.3–1.6 where G < 25) is the dark-blue background field rgb(2,7,14),
not the glow. The σ = 7.2 term is *not* pure cyan: R/G climbs to 0.23–0.57 for |y−515| < 180 — there is a
faint **white halo** on the core (directly visible: at y = 301 the R channel is 12–29 for 4–8 px either
side of the core while the background R is 2–3). Part of that mid-height R is the central flare's bloom,
so 0.25 is an upper bound for a white-halo component and 0.03 the pure-cyan floor.

---

## 4. Along-arc taper

*Core* — a **plateau with short end ramps**, not a peaked taper: coverage 0.69–0.86 flat over
y ∈ [170, 860] (±6 % station-to-station wobble, with shallow local maxima at y ≈ 210 and y ≈ 800 and a
shallow dip at y ≈ 350–650), then a near-linear fade. Zero points (linear extrapolation of the
12–55 % range): **L y = 88.3 and 943.5; R y = 85.7 and 938.8** — symmetric about y = 515.9 (L) /
512.3 (R), half-span 427 px. Direct probing past the last ridge point confirms the core is still
detectable at y = 80 (13 code above the local field), marginal at y = 74 and gone by y = 68.

*Glow* — strongly centrally peaked, and **each term tapers differently**:
`A_G = A_apex·cos^p(θ)`, θ = the ellipse parameter angle (sin θ = (y−cy)/ry, θ = 0 at the apex):

| term | A_apex (G) L / R | p (L / R) | rms |
|---|---|---|---|
| σ 7.2 | 108 / 114 | 2.58 / 2.50 | 8 % of peak |
| σ 26.9 | 63.9 / 58.0 | 2.99 / 2.46 | **5 % of peak** |
| σ 56.6 | 37.8 / 37.0 | 5.48 / 4.69 | 8 % of peak |

cos³θ = ((x−cx)/rx)³ = (1−((y−cy)/ry)²)^1.5. This single closed form beats a gaussian in y (6.8 %), an
exponential in flare distance (8.2 %) and a power of flare distance (11.8 %).

**Which variable drives the taper?** The reference does **not** discriminate. A trapezoid fit of the core
taper is equally good in y (5.2 / 5.6 %), arc length (5.1 / 5.6 %), ellipse parameter angle (5.1 / 5.5 %)
and distance from the flare (5.1 / 5.6 %); likewise the glow (3.1–3.6 % in all four). Over a single arc
these are monotone reparametrisations of one another. **Use y** — it is the one SVG expresses directly as
a `linearGradient`, and it fits as well as any other choice. `gradient_stops` in the JSON gives
normalised stops every 20 px for the core and for all three glow terms, both arcs.

**Symmetry about the ellipse centre y.** The glow is 0–20 % brighter in the bottom half at matched
|y−514.85| (bottom/top = 1.04, 1.04, 1.10, 1.20, 1.19 for L at d = 150…350 px; 1.09, 1.02, 1.04, 1.10,
1.01 for R). The core is inconsistent: L is 0–9 % brighter at the bottom, R is 5–16 % *dimmer*. So the
taper is symmetric to ±10–20 %; a symmetric taper costs ≤ 6 code values of glow and is defensible.

**Caution — the flare band.** For |y−515| ≲ 80 the arcs' glow cannot be separated from the central
flare's bloom: term-1 amplitudes run into the 255 bound and the fit rms doubles (5–6.7). The measured
amplitudes near y = 440–600 are ~15–20 % above the arc-only cos^p model (e.g. A2_G 75 measured vs 62.6
predicted at y = 442). Use the cos^p extrapolation, or the interpolated stops, and let whoever owns the
flare supply the rest.

---

## 5. How far out the lead must paint

Largest |t| where the 13-px-smoothed G channel still exceeds the **local** far-field background
(bg_local is 4–13 in G; the darkest interior floor is G = 3):

| side | > bg+2 | > bg+5 | > bg+10 |
|---|---|---|---|
| concave / outer | **205 px** | 173 px | 141 px |
| convex / inner | **73 px** (model); ~80 px measured at the tips | — | 50 px |

The inner side cannot be measured at mid-height at all — the gap between the arcs is only 79–170 px, so
the two glows and the flare overlap completely. The 73 px figure is the fitted model at mid-arc
amplitudes. Beyond ~210 px the arc glow is under 2 code values and is indistinguishable from the diffuse
interior field (which is itself structured: G ≈ 16–20 in the top corners vs 4–6 near the bottom).

---

## 6. Recommended layer stack (and the arithmetic check)

Five strokes, screen-composited over a dark-blue base, per arc. A stroke of width W blurred by σ_b has
the perpendicular coverage profile `α·½[erf((t+W/2)/(σ_b√2)) − erf((t−W/2)/(σ_b√2))]`; picking
**W = 2σ** gives **σ_b = 0.8165 σ** and a peak factor erf(0.866) = 0.7793, so
**α = peak_amplitude / 255 / 0.7793**. Any (W, σ_b) with σ_b² + W²/12 = σ² works.

```
base            fill rgb(2,7,14)  (local far-field background; 4-13 in G, see glow.rows[].bg)
glow3  stroke #0AFFFF  W 113.2  blur σ 46.2  path offset 62.1 px inward  α gradient, max 0.19
glow2  stroke #0AFFFF  W  53.8  blur σ 22.0  path offset 16.2 px inward  α gradient, max 0.32
glow1  stroke #19F0FF  W  14.4  blur σ  5.9  path offset  3.3 px inward  α gradient, max 0.54
core   stroke #E0FFFF  W 5.8→8.5  no blur     on the centre-line          α gradient, max 0.99
```

α maxima are computed from the arc-only cos^p apex amplitudes (A_G = 108 / 64 / 37.8 and core coverage
0.86/0.877 = 0.985), i.e. α = A_G/255/0.7793. Multiply by the normalised `gradient_stops` to get α(y).
glow1 is the one layer that is not pure cyan: #19F0FF (R/G = 0.1) is its median, and R/G rises to
0.23-0.57 for |y-515| < 180, so either ramp its red or add a separate faint white halo layer there.

"path offset d inward" = toward that arc's own ellipse centre; for an axis-aligned ellipse, shrinking the
radii to (rx−d, ry−d) about the same centre is exact at the apex and within ~4 px at the tips (0.07 σ for
d = 62 — invisible).

Worked numeric check at **L, y = 294.1**. Layers actually used: core = #E0FFFF at α = 207.4/255 = 0.813,
W = 7.51, edge σ 0.63; glow1 = rgb(23,248,255) at α = 0.284 (peak amplitude [5.0, 54.9, 56.5]);
glow2 = rgb(0,245,255) at α = 0.217 ([0.0, 41.4, 43.0]); glow3 = rgb(0,239,255) at α = 0.098
([0.0, 18.2, 19.4]); base rgb(2.3, 7.0, 13.9). Stack evaluated exactly (erf strokes, screen) against the
measured cross-section:

```
   t    measured R/G/B    stack R/G/B
-250    2.0   7.0  13.0    2.3   7.0  14.0
-160    2.8  12.2  19.4    2.3  11.2  18.3
-120    1.7  14.7  22.7    2.3  17.9  25.3
 -90    1.9  24.9  32.9    2.3  23.6  31.2
 -50    0.6  39.7  46.7    2.3  42.3  50.0
 -25    1.1  60.3  67.8    2.3  58.1  65.8
 -12    3.1  76.9  85.8    4.8  78.9  86.3
  -5   20.3  95.2 102.0   11.4  99.0 106.2
   0  186.5 222.5 224.5  183.9 224.3 226.9
   5   10.7  69.1  76.0    9.3  73.6  80.9
  12    1.1  37.1  45.3    2.8  43.6  51.0
  25    0.0  19.0  26.0    2.3  25.7  33.0
  50    0.1  13.1  19.1    2.3  11.5  18.6
  70    1.0   8.0  14.0    2.3   8.3  15.3
```

rms over the whole cut, all channels: **2.37** code values, max |deviation| 17.5 (at t = ±2–5, the core
edge, where a 0.3 px centre-line error alone is worth 30 code values). Three more stations
(L 697 → rms 3.10, R 199 → 2.26, R 779 → 2.40) with their own layer tables are in
`recommended_stack.numeric_check`.

**Blend space matters, blur space does not.** The composite must be `screen` in **sRGB** space
(`mix-blend-mode:screen` on isolated groups, or `feBlend mode="screen"` with
`color-interpolation-filters="sRGB"`). The linearRGB-vs-sRGB choice for `feGaussianBlur` is irrelevant
*here* because each glow layer is a single colour: the blur acts on premultiplied colour+alpha, so a
monochrome layer keeps its colour and only its alpha is blurred. That stops being true if several
colours are blurred inside one group.

---

## 7. What the reference cannot tell us

* The glow's peak amplitude **under** the core (|t| < 6) is an extrapolation: the core dominates there.
  The σ = 7.2 term and the core's own box profile are partly degenerate, which is why the core amplitude
  is pinned from the R channel (with its own flexible cubic pedestal) rather than fitted jointly.
* Inside |y−515| < 80 the arc glow and the flare bloom are inseparable.
* The widest term (σ = 56.6) trades off against the fitted per-station background beyond |t| ≈ 220; the
  background is genuinely non-flat (G ≈ 16–20 in the top corners, 4–6 at the bottom), so the extreme
  tail of the glow and the diffuse field are not separable.
* Whether the design intent is "offset glow" or "per-side σ" is undecidable (2.18 vs 2.15).
* Whether the taper is driven by y, arc length, ellipse angle or flare distance is undecidable from one
  arc pair (all fit to the same 3–6 %).
