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

## 5. The central light

**There is no bright disc at the centre.** At the flare centre the image reads
lum 224, and nothing within 15 px of it reaches 245; along the waist the
luminance rises monotonically from the left core (250) through the gap (178 at
x=486, 213 at x=514, 245 at x=526) into the right core (254). The "star" is the
two converging cores plus a bloom, a streak, and one separate compact glint.

What is separable, and how each part is measured:

* **Centre (509.2, 512.7)**, from a symmetric-exponential fit of the streak's
  y-integrated flux over \|x-xc\| in [45,140] (187 samples, both wings at once)
  and the per-column peak of the vertical profile. That coincides with the
  *frame* centre (509.05, 513.01) to 0.2/0.3 px -- and is 4.2 px right of the
  curves' mirror axis and 2.6 px above their own symmetry axis.
* **Horizontal streak**: e-folding length 30.3 px out to ~+-250 px, horizontal
  to 0.1 degrees, with a vertical Gaussian of only sigma 2.2 px (FWHM 5.2).
  A radial gradient cannot produce that (its transverse law would equal its
  longitudinal one), so it is a rect with a gradient along x and an
  anisotropic blur across y. A second, shorter, whiter streak (e-folding 24 px,
  half-length 78) is what makes the core read as white.
* **Bloom**: not radial. Vertical Gaussian sigma is 9.0-10.4 px in white and
  21-26 px in cyan against a horizontal scale of ~30 px, an axis ratio of
  3-4:1, so it is two horizontally stretched blurred ellipses.
* **Glint**: a compact, nearly saturated element at **(535.0, 514.8)**, FWHM
  28x35 px, peak 170/255 of R excess, colour ~#96E8EE. It carries *every*
  off-arc pixel above lum 245, sits 9.7 px inside the right curve's apex, and
  the two right-hand rays converge on it. Its vertical centre coincides with
  the curves' own symmetry axis rather than with the streak's.
* **Three one-sided diagonal rays**, at outward angles 33.1, 312.3 and 222.2
  degrees, crossing the streak line at x = 534.8, 537.9 and 494.5. Peak
  amplitudes are only 2.9-4.7 code values above the local background. They are
  neither 4-fold nor 6-fold symmetric and there is no vertical pair, so a
  symmetric starburst primitive would invent three rays that do not exist;
  each is placed individually from its measured angle and crossing point.
* The light the flare dumps on the two curves, which is why their cores peak
  near the waist (R = 239 at y = 511 against 190-210 elsewhere).

## 6. Colour: one light source, two emission components

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
