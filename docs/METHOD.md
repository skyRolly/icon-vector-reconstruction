# Reconstructed visual structure

This document describes what `reference.png` is made of, as far as it can be
determined from the pixels, and how `reconstruction.svg` reproduces it.
Every number quoted here was measured; the measurement code lives in
`tools/` and the per-component analyses in `out/analysis/`.

Two coordinate conventions are used and must not be mixed:

* **pixel-index** — integer coordinate = the centre of that pixel. All
  measurements are in this frame.
* **SVG user space** — what goes in the SVG. Verified by rendering a line at a
  known coordinate and re-measuring it: **SVG = pixel-index + 0.5**.
  `src/params.json` stores SVG user space.

---

## 1. Canvas and background

1024x1024, sRGB, no alpha.

**Exterior.** Over the 211 000 pixels clearly outside the frame the mean is
rgb(0.83, 2.04, 6.10) and both the median and the mode are exactly
**rgb(1, 2, 7)**, which is also the MAE-optimal flat colour (0.868 against 2.99
for black). It is not perfectly uniform -- a dark halo hugs the frame, almost
purely in blue: the bottom margin sits at B 1.1-3.0 through its whole 32 px
depth while the top margin stays at B 7.3, and the sides run B 3.4-4.1 next to
the stroke rising to 6.2-6.8 by 60 px out. Modelling that halo in full only
buys 0.035 of whole-canvas MAE, and the blue there is set by the 2x2-subsampled
chroma DC whose quantisation step is ~2 code values of B, so the
reconstruction carries just the flat colour plus a broad vertical and
corner-ward tendency and leaves the rest.

**Interior.** On a glow-free mask (beyond 185 px from the curves, 300 px from
the flare, inside the frame -- 20% of the interior), a flat fill leaves a G MAE
of 1.49. The best six-parameter model is a single **isotropic radial gradient
centred at (882, 678.5) with r 969.7** -- well outside the canvas, to the
bottom-right -- which drops G MAE to 0.99 (R 0.75, B 1.26). Two negatives are
as informative: a free function of distance-to-the-frame explains only 4% of
the variance, so **there is no vignette**, and a free function of
distance-to-the-curves explains nothing at all, so the field is its own element
and not a tail of the glow. The field is brightest at the inner top-left and
darkest at the bottom-right; measured mirror differences are left-right +5.1 G
at y 150-225 falling to +0.8 G at y 750-825, and top-bottom +1.0 to +3.6 G.
The reconstruction uses that gradient plus a flat base, a centre-weighted
radial and a vertical tilt.

**What is deliberately not reproduced.**

* JPEG artefacts: the file has been through JPEG (XMP `CreatorTool = Picasa`)
  and dark areas show 8x8 DCT blocking. Decomposed by scale, the background
  residual is pixel noise 0.27-0.31, 8x8 DC blocking 0.66-0.69 and a >=32 px
  "smudge" of 0.48-0.96 code values. The implied MAE floor is **0.57/0.60/0.61
  per channel**, so roughly a quarter of the reconstruction's final MAE is the
  reference's own compression noise.
* That smudge -- low-frequency mottling with no constructible geometry, and
  different in the two side lobes. Reproducing it would win only ~0.05 of
  whole-image MAE.

**A known limitation of additive-only compositing.** Between the diverging
curves, above and below the flare, there are two dark axial wedges (5.1% of the
interior) whose floor is below any single interior fill that is correct
elsewhere. A screen/additive stack can only add light, so a fill chosen to be
right over the measurable 20% over-predicts those wedges by 4.2-4.7 code
values, and a fill chosen to match the wedges is 4.2 G too dark elsewhere. The
reconstruction takes the first option; the residual cost is about 0.37 of G MAE
whole-canvas and is visible as the faint dark-red vertical band in
`out/diff_signed.png`.

## 2. The frame

A rounded rectangle drawn as a single stroke. Centre-lines were fitted with an
opaque-bar-over-two-backgrounds cross-section model at 371-461 stations per
edge (a single linear baseline instead of two manufactures a spurious +-4%
"glow outside / dark rim inside", because the interior field is 4-10 code
values brighter than the exterior):

| edge | centre-line (SVG) | sd over the straight run |
|---|---|---|
| left | x = 66.5225 | 0.041 |
| right | x = 951.5700 | 0.031 |
| top | y = 34.3555 | 0.017 |
| bottom | y = 991.6551 | 0.023 |

=> frame box **885.05 x 957.30**, centred at **(509.05, 513.01)**: 8% taller
than wide and ~3 px left of the canvas centre. Residual tilt is <= 2e-4 rad and
has opposite signs on the left and right edges, so it is not a rotation. The
asymmetry is reproduced, not tidied up.

Stroke width per edge 6.046-6.250, i.e. **6.135 +- 0.10**, constant through the
corners to 0.05 px. The fitted edge blur is only sigma 0.06-0.16 px, so the rim
is a crisp vector edge: **no blur, no soft edge**.

**The corners are not circular, and they are not squircles either.** Three
independent signatures:

* sliding 12-degree circle fits give a local radius of curvature of 250-400 px
  near the straight edges and 145-175 px through the 45-degree region;
* the centre-line is still 0.66 px inward 195 px from the box corner, where a
  circular corner that fits the 45-degree region would be exactly on the line;
* a circle fitted to the corner points alone sits 1.9-2.7 px *inside* both
  measured straight edges, i.e. it cannot be tangent to them.

Model residuals to the measured corner outlines (199-200 points per corner,
method floor 0.06 px):

| corner model | residual per corner |
|---|---|
| superellipse (n free -> 6.4) | 2.52 / 2.53 / 2.70 / 2.61 px |
| circular rounded rect tangent to the lines (r 171-172) | 0.84 / 0.84 / 0.66 / 0.75 px |
| single cubic Bezier corner (R 185, k 0.63) | 0.44 / 0.43 / 0.35 / 0.37 px |
| **3-arc corner: blend, main, blend** | **0.23 / 0.27 / 0.13 / 0.13 px** |

So each corner is a **continuous-curvature ("corner-smoothed") corner**: a long
shallow blend arc of r 639.06 turning 5.242 degrees, the main arc of
r **163.561 +- 0.21** turning 79.517 degrees, then the mirror blend arc. All
four corners share that radius (diagonal depth 70.35-70.70 px) and the
curvature starts 208.99 px from each box corner, so the genuinely straight runs
are only x in [275.5, 742.6] and y in [243.3, 782.7]. What is actually
constrained in the blend is its lateral offset, 3.0 px over a 58 px run: any
(r2, turn) pair with r2*turn ~ 58 px and r2*turn^2/2 ~ 3.0 px is equivalent.

**The rim's brightness is not one gradient, and its hue changes.** 418 stations
at 8 px of arc length:

| location | stroke sRGB | lum |
|---|---|---|
| top edge, middle | rgb(112, 121, 128) | 119 |
| right edge, middle | rgb(65, 75, 83) | 74 |
| left edge, middle | rgb(65, 73, 78) | 72 |
| bottom edge, middle | rgb(50, 65, 67) | 62 |
| darkest corner (BL) | rgb(16, 26, 31) | 24 |

Every edge is brightest at its own midpoint and the corners are the darkest
points, which rules out every linear gradient (vertical rms 19.5, best
direction 18.9); the top edge being 1.9x the bottom rules out the symmetric
radial ones (centre-radial rms 17.3). The winner, rms **5.72**, is an
**anisotropic radial gradient centred at (508.34, 476.40)** -- 30 px above the
frame centre -- with r 575 and a 1.130 vertical stretch. B/G stays at 0.98-1.05
around the whole perimeter while R/G climbs from 0.71 at the dim corners to
0.95 at the bright top middle, so the paint really does change colour rather
than just alpha; the reconstruction gets that from two stroked copies (a cyan
floor plus the measured radial highlight) whose fitted mix interpolates the hue.

A stacked residual with a standard error of ~0.001 of the stroke value shows
**no second ring, bevel or outer glow**: beyond 6 px from the centre-line the
residual is under 1.2% of the stroke, and the +-5% oscillation inside that is a
symmetric double overshoot at both boundaries, i.e. JPEG ringing.

## 3. The two luminous curves

Sub-pixel ridge centre-lines were extracted from perpendicular cross-sections
of the R channel (G and B clip at 255 along the cores; R peaks at 254 in exactly
one pixel), taking the midpoint of the 50%-of-plateau crossings so the clipped,
slightly U-shaped plateau cannot bias the centre.

**Neither curve is a conic.** Model comparison on the high-quality ridge points
(orthogonal residuals):

| model | free params | RMS left | RMS right |
|---|---|---|---|
| circle | 3 | 1.65 | 1.85 |
| parabola | 4 | 5.00 | 5.25 |
| ellipse, axis-aligned | 4 | 0.331 | 0.473 |
| ellipse, rotated | 5 | 0.321 | 0.224 |
| general conic | 5 | 0.307 | 0.213 |
| superellipse | 5 | 0.188 | 0.453 |
| single cubic Bezier | 8 | 0.397 | 0.245 |
| **two cubic Beziers joined at the apex** | 12 | **0.083** | **0.093** |

An axis-aligned ellipse leaves a smooth, nearly even-in-y, 4-5 lobe residual of
+-0.4 px. Rotation, a superellipse exponent and a split vertical radius each
remove a *different* part of that residual, which is the signature of a
parameter absorbing model error rather than measuring a real degree of freedom;
the fitted "tilt" of the right curve swings from -24 to +11 degrees depending on
the y-range used. Two cubic Beziers joined at the apex with a vertical tangent
reach the 0.055-0.063 px measurement noise floor, so each curve is **three
anchors — top tip, apex, bottom tip — with a vertical handle at the apex**, and
that is what the SVG contains.

Well-conditioned quantities (the individual `cx`/`rx` of an ellipse fit are
not: they are 100% anti-correlated with sigma ~9.5 px each):

* left apex x = 464.94 +- 0.06, right apex x = 544.19 +- 0.06
* waist gap = **79.25 +- 0.09 px** at y = 517.3 — the curves never touch
* mirror axis x = **504.53 +- 0.05** — not the canvas centre (512) and not the
  frame centre (508.5)
* each curve's own up/down symmetry axis: y = 514.85, i.e. 2.3 px above the
  apex/waist

The pair is mirror-symmetric to +-0.25 px for y in [90,620], with real
departures of up to ~1 px in the bottom third; there is no relative rotation
(0.00 +- 0.05 degrees). Both curves are kept at their own fitted control points
so that asymmetry survives; the measured mirror axis is recorded in
`src/params.json` for anyone who prefers to mirror one side.

**The tips are an opacity fade, not a geometric taper**: the core's width stays
5.9-6.2 px out to the last detectable signal, and the amplitude falls to zero at
y ~ 85 and y ~ 945 — symmetric about the curves' own centre y (514.85 +- 430).
So the paths are drawn to their full extent and the fade is done with alpha.

## 4. The glow around the curves

Perpendicular cross-sections out to +-320 px at 45 stations per arc, fitted
with a screen-compositing model in sRGB code space, decompose the glow into
**three Gaussian terms whose widths and offsets are global** -- one set for both
arcs and every station -- with only the amplitudes varying along the arc:

| term | sigma | centre offset, inward | amplitude along the arc |
|---|---|---|---|
| glow1 | 7.22 px | 3.28 px | 0 at the tips, 45-55 at y=200/810, 95-125 mid-arc |
| glow2 | 26.92 px | 16.20 px | 0 at the tips, 28-34 at y=200/810, ~65 mid-arc |
| glow3 | 56.59 px | 62.07 px | 0 beyond \|y-515\| > 310, 28-34 mid-arc |

That model reproduces the whole cross-section, core included, to **2.4-2.7 code
values rms** against a JPEG noise floor of 1.3. The negative offsets are what
makes the glow decisively brighter on the concave side: the measured
outer/inner ratio at 15-25 px from the core is 2.8-3.5.

A stroke of width W blurred by sigma_b has the same profile as a Gaussian of
sigma when sigma_b^2 + W^2/12 = sigma^2, so each term becomes one stroked copy
of the arc path, offset inward by its measured delta and blurred. The core
itself is a **hard-edged stroke**: the fitted edge sigma is 0.45-0.75 px, i.e.
plain anti-aliasing and no blur at all.

### 4a. How one-sided the glow is, measured directly

Three inward-offset strokes get the *sign* of the asymmetry right and its
*extent* wrong, and no whole-image metric says so. Pooling both curves over
\|t\| < 62 degrees and excluding everything within 200 px of the central light
(so the flare cannot be read as curve glow), mean luminance against signed
distance `s` from the curve — negative into the lobe, positive between the
curves — is:

| \|s\| px | 11 | 17 | 24 | 33 | 45 | 61 | 80 | 100 | 130 | 170 | 215 | 270 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| concave | 41.6 | 33.9 | 30.1 | 26.3 | 23.2 | 19.8 | 16.5 | 14.0 | 12.4 | 10.9 | 9.3 | 7.5 |
| convex | 26.4 | 19.4 | 16.4 | 13.4 | 11.7 | 9.5 | 7.6 | 6.3 | 6.4 | — | — | — |

Above the far-field floor of ~6.3 the concave excess is 1.7x the convex one at
11 px and **5.9x at 100 px**, and the convex side is indistinguishable from the
background by 100-130 px while the concave side still carries 6 code values at
170 px. The single most direct statement of it: on the inter-curve midline at
y=200, where both curves are 140 px away, the reference sits at **3.9 code
values**, while a lobe point 140 px from one curve sits at **13.5**.

Two components follow from that, and the difference is visible rather than
numerical:

* **arc_haze**, a wide low stroke deep in the lobe, `clip-path`-ed to that
  arc's own ellipse so it contributes nothing on the convex side. Clipping
  (rather than relying on the offset) is what lets the concave tail run to
  270 px without filling the space between the curves; the hard edge it leaves
  at the curve is hidden under the core stroke, which is two orders of
  magnitude brighter.
* **arc_glow2b**, the one component offset *outward*, towards the convex side.
  Every other stroke is inset into the lobe, which left the band 28-70 px
  between the curves 13-19% too dark while the lobe 14-38 px out was 6-11% too
  bright. Adding it cut the profile's rms relative error from 8.6% to 7.0% and
  left the global MAE unchanged.

### 4b. The asymmetry is not the same all along the curve

Splitting the same profile by along-curve angle \|t\| separates two errors that
the pooled table hides. Relative error of the reconstruction, before the fades
of the two new components were fitted:

| s px | \|t\| 0-20 | \|t\| 20-40 | \|t\| 40-62 |
|---|---|---|---|
| -11 (concave, near) | — | +8.5% | **+26.6%** |
| -24 | — | +1.0% | +19.2% |
| -61 | — | -11.3% | -12.6% |
| -170 (concave, far) | -9.0% | -0.8% | **+22.5%** |
| +11 (convex, near) | — | -5.3% | -11.9% |
| +33 | — | +5.5% | **-15.2%** |
| +80 | — | -0.6% | -9.3% |

Near the waist the balance is close; towards the tips the reconstruction was
far too one-sided — too much light in the lobe, too little between the curves.
The three measured glow fades come from the station-by-station cross-section
fit and are data; the two components added above postdate that fit, so reusing
`glow3`'s table for them would have been an assumption dressed as a
measurement. They carry their own fades (`tapers.haze`, `tapers.glow2b`) as
tunable ramps instead.

The core's width is not constant -- 5.8 px at both tips, 8.4 px at mid-height --
and it is **not symmetric about its own centre-line**: its 50% edges reach
4.8 px on the concave side but only 3.3 px on the convex side. A single stroke
cannot do either, so the core is two strokes: a full-length one on the fitted
centre-line, and a narrower inset one tapered towards mid-height that supplies
exactly that extra concave-side width.

The fades along the arcs are not guessed: the core coverage and each glow term's
amplitude were measured station by station on both arcs and are carried in
`src/params.json` as explicit stop tables (`tapers.core`, `tapers.glow1..3`),
with a tunable gamma and scale on top.

### 4c. Light past the ends of the curves: the interior corners

The drawn curves end at \|t\| = 66-69 degrees (the four Bezier endpoints are at
66.1, 66.8, 67.6 and 68.9). Past those ends there is no curve, but the
reference is not dark there. Measured over interior pixels more than 40 px from
either curve and more than 250 px from the central light:

| distance inside the frame | corner quadrants | edge midpoints |
|---|---|---|
| 12-45 px | ref 11.00, rec 8.29 (**-25%**) | ref 7.67, rec 7.00 |
| 45-100 px | ref 9.46, rec 6.96 (**-26%**) | ref 6.96, rec 6.87 |
| 100-200 px | ref 8.38, rec 8.18 | ref 8.46, rec 8.48 |

So the light is corner-weighted and reaches about 100 px inside the frame:
67 000 pixels roughly 30% too dark, in four patches, invisible to every other
measurement here. The reconstruction adds one layer for it (`corner_in`): a
wide stroked copy of the frame path, clipped to the interior, blurred, painted
with a radial gradient centred in the icon. That gradient is what makes it a
*corner* glow rather than a rim glow — the frame path is 651 px from the icon
centre at the corners against 442-478 px at the edge midpoints, so a gradient
rising over that range lights the corners and leaves the edges alone.

## 5. The central light

### 5a. How it was separated from everything else

Screen compositing is commutative and has a closed form, so the flare's own
contribution can be recovered from the reference rather than guessed at.
Drop every `flare_*` layer, composite the rest into a base `M`, and

    ref = M + f (1 - M)    =>    f = (ref - M) / (1 - M)

is exactly what the dropped group must supply, in the units its own layers use.
Two cautions, both learned the hard way and both implemented in
`tools/isolate.py`:

* the surviving layers were fitted *with* the flare present, so they have
  already absorbed some of its light. Isolating against that base attributes
  the absorbed part to the wrong source — which is how a broad deficit left of
  the flare first read as a bright leftward "ray". The base is therefore
  re-fitted on a mask that excludes a 200 px disc around the centre first.
* `f` is unstable wherever `M` approaches 1, i.e. on the arc cores, so those
  pixels are masked out of every profile below.

Working in additive luminance `u = -ln(1 - f)`, where screen layers simply add,
then makes the structure readable.

### 5b. What the isolated flare actually is

**Centre (530.95, 513.33).** The peak of the isolated flare is at (531, 513)
and the centroid of every off-arc pixel above luminance 245 is (531.3, 512.8);
the two agree to within a pixel. (The brightest pixel *within* 45 px of it is
at (543, 514) — that is the right curve's apex, 14 px away, not the flare.)

**A clipped plateau, not a peak.** 198 reference pixels sit above luminance
248, spread over a plateau roughly 20 px across; along y=513 the red channel
holds 233-247 from x=528 to x=538. The previous reconstruction rendered 67 such
pixels, and was 20 code values too dark at the very centre while being too
bright 15 px out. This one renders 184 (170 against the reference's 170 within
60 px of the centre) with no dedicated flat-topped element: the plateau comes
out of the sum of the halo -- once its radius came down from 122 to its
measured 92 px -- and the two thin streaks, all of which saturate together over
those pixels. See `docs/DECISIONS.md` D14 for the flat-topped disc that was
tried and is no longer needed.

**The off-axis halo, and where it stops.** Mean `u` along rays clear of the
horizontal streak and of the arcs:

| r px | 6 | 10 | 15 | 22 | 30 | 40 | 55 | 72 | 92 | 115 | 145 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| u | 2.30 | 1.65 | 1.15 | 0.75 | 0.48 | 0.30 | 0.16 | 0.06 | 0.02 | 0.005 | ~0 |

The local e-folding length grows from ~12 px at the core to ~24 px by r=45,
which is why the halo is two exponential terms and not one. The important part
is the end of the table: **the flare contributes nothing measurable beyond
r ~ 130-160 px.** The previous reconstruction's widest bloom had a radius of
378 px, and that surplus is exactly what filled the space between the curves —
which is the darkest part of the reference's interior (3.9 code values on the
midline at y=200). The widest bloom's radius is now bounded by the
measurement.

**Horizontal anisotropy, and its left/right asymmetry.** Along the same rays:

| r px | 22 | 30 | 40 | 92 | 115 | 145 | 185 |
|---|---|---|---|---|---|---|---|
| due west (180 deg) | 1.77 | 1.60 | 1.29 | 0.41 | 0.145 | 0.065 | 0.028 |
| due east (0 deg) | — | 0.87 | 0.51 | 0.083 | 0.042 | 0.028 | 0.021 |
| off-axis | 0.75 | 0.48 | 0.30 | 0.02 | 0.005 | ~0 | ~0 |

So the streak is 3-5x stronger westward than eastward and reaches past 185 px,
while the halo it sits on has already died by 130. That is the largest single
feature of the flare, and it is carried by three components with different
widths: a thin spike (sigma_y ~2.6 px), a longer thin streak whose own centre
is 59 px west of the core — which is where the far-wing symmetry centre of the
reference's streak actually is — and a broader fan (sigma_y ~11 px), plus a
westward cone.

**The streak's cross-section is genuinely a few pixels.** Row by row, 26-61 px
west of the core, the additive excess over the local baseline peaks at 0.76
across two pixel rows and is down to a quarter of that 4 px away. Reproducing
that needs the layer's on-axis coverage to be able to approach 1: a 2 px source
rect blurred by 2.7 px caps it at `h / (sigma_b sqrt(2 pi))` = 0.29, which
forced the layer's fitted colour against white and still rendered the streak
three times too faint. The markup now derives both the rect height and the blur
from the requested `sigma_y` at a fixed ratio `h / sigma_b = 3.92`, which puts
on-axis coverage at 0.95 while keeping `sigma_eff = sigma_y` exactly.

**Rays.** After dividing out the halo, the isolated flare has local angular
maxima at roughly 45-60, 110-120, 175-195, 225-255, 300 and 330-345 degrees.
They are faint — 0.45 in `u` at r=40 for the 45-degree ray against 0.32
off-axis, 0.09 at r=72 — and they are not 4- or 6-fold symmetric, so a
symmetric starburst primitive would invent rays that are not there; each is
placed from its own measured angle. The westward fan is not a constant-width
streak either: its half width grows from ~10 px at r=30 to ~28 px at r=92, so
each ray carries a `spread` (its far end's width as a multiple of its near
end's) and is built as a cone.

**What is not separable.** The peak radiance of the core, the arc cores and the
streak is unrecoverable: G and B clip at 255 over those pixels. Any model that
clips in the same places matches them.

## 6. Colour: a three-component non-negative cone

A PCA of the colour *directions* of 300 000 interior pixels (after subtracting
the exterior background) gives eigenvalues **0.981 / 0.012 / 0.007**: the light
is essentially two-dimensional, white plus one cyan emission. Fitting every
pixel as a non-negative combination of

    white(1, 1, 1)   cyan(0, 0.94, 1.00)   blue(0, 0, 1)

is then exact -- mean absolute error **0.012 / 255** -- against 1.85 for
white+cyan alone and 9.96 for white alone. The third, pure-blue term is needed
only by the very dark background (the dim interior sits at G/B ~ 0.66 and the
exterior at ~0.3, both bluer than the cyan); it carries no visible weight
anywhere bright.

So every layer in the reconstruction carries three numbers -- how much white,
cyan and blue -- rather than three free channels. The cone spanned by those
three with non-negative amounts is exactly **R <= G <= B**, which is the family
the reference uses everywhere. That is the point of the basis rather than free
RGB: it is a modelling safeguard. When layer colours were fitted as free RGB,
the optimiser used hue to compensate for shape error and produced a magenta
core and a green bloom that fit slightly better and meant nothing.

## 7. Compositing

Everything luminous is composited with `mix-blend-mode: screen` over an opaque
black base, so the whole image is

    out = 1 - product_i (1 - A_i * k_i)

where `A_i` is layer i's coverage (anti-aliasing x blur x gradient alpha) and
`k_i` its premultiplied colour. Screen was chosen because light in the
reference adds and then rolls off into a clipped white core; `plus-lighter`
(true addition) would be the physical model but resvg does not implement it,
while both engines implement `screen` bit-identically.

That closed form is also what makes the fitting cheap: render each layer once in
white and every layer's colour can be fitted analytically, with no further
rendering (`tools/fit_photometry.py`). The analytic composite agrees with the
actual render to well under one code value, the residual being 8-bit
quantisation of the per-layer basis renders.

One correction this model needed, found by comparing the closed form against
the real render: a `normal`-blended layer composites as
`out*(1 - alpha*opacity) + alpha*opacity*C`, so its opacity also weakens the
backdrop. Emitting such a layer as a bright colour times a small opacity --
which is right for `screen`, where only the product matters -- let the backdrop
bleed through and rendered the frame rim at B 148 where the measurement says
128. Normal-blended layers are therefore emitted at opacity 1.
