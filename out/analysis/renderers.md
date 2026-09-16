# Renderer behaviour: resvg 0.5.0 (resvg_py) vs Chromium 141 headless

All numbers are measured from renders of the test SVGs in
`out/analysis/renderers_tests/` (216 SVGs kept). Profiles are averaged over
200-264 identical rows to beat 8-bit quantisation; model fits are least
squares. Full numeric detail is in `out/analysis/renderers.json`.

## TL;DR for the glow stack

1. **Stack with `style="mix-blend-mode:screen"`.** Byte-identical in both
   engines at every depth 1..16 (max diff **0 LSB**), and equal to sRGB-space
   `1-(1-a)(1-b)`. The same stack done with plain translucent alpha diverges
   (see below).
2. **`mix-blend-mode` must be in `style=""` or a `<style>` rule.** As a
   presentation attribute (`mix-blend-mode="screen"`) it is **ignored by both
   engines** - silently no blending.
3. **Never `plus-lighter`**: chromium implements it exactly, resvg ignores it
   (10-layer stack: core pixel 194 vs 255, rms 3.73 LSB).
4. **Every filter gets `filterUnits="userSpaceOnUse" x/y/width/height`** with a
   margin of **3 sigma**, and **`color-interpolation-filters="sRGB"`**.
5. **Prefer gradients to blurs for the broad bloom**: radialGradient agrees to
   <=1 LSB between engines and costs resvg 195 ms for the whole canvas versus
   ~105 ms *per* blurred layer.

## 1. feGaussianBlur

Both engines use a **three-pass box blur** (profiles are exactly 0 beyond
~2.8 sigma, where a true Gaussian is still 2.4e-3 of peak; the 3-box step
response fits chromium with rms 0.22-0.27 LSB vs 0.62-0.65 LSB for an erf).

Fitted box size `d` (3 passes), and the resulting kernel sigma
`sigma_eff = sqrt(3(d^2-1)/12)`:

| stdDeviation | resvg d | chromium d (=spec) | sigma_eff/nominal resvg | chromium | ratio r/c | profile max diff |
|---|---|---|---|---|---|---|
| 5   | 11  | 9   | 1.095 | 0.894 | 1.225 | 7 LSB |
| 10  | 19  | 19  | 0.949 | 0.949 | 1.000 | 2 LSB |
| 20  | 39  | 39  | 0.975 | 0.975 | 1.000 | 2 LSB |
| 40  | 79  | 75  | 0.987 | 0.937 | 1.053 | 4 LSB |
| 60  | 119 | 113 | 0.992 | 0.942 | 1.053 | 4 LSB |
| 100 | 197 | 189 | 0.985 | 0.945 | 1.042 | 4 LSB |

* chromium uses the spec box size `floor(1.88*sigma+0.5)`, which has ~6% less
  variance than the nominal Gaussian -> **chromium's glow is ~4-6% tighter**.
  resvg uses `d ~= 1.97*sigma`, landing within ~1-2% of a true Gaussian.
* Independent erf fits of a 255-amplitude edge: sigma 40 -> **40.7 (resvg) /
  38.8 (chromium)**; sigma 10 -> 10.10 / 9.78.
* Peak of a blurred line (row-averaged, 8-bit):

| stdDev | 1px line r/c | 6px line r/c |
|---|---|---|
| 2  | **51 / 43** | **227 / 210** |
| 5  | 19 / 21 | 111 / 121 |
| 10 | 10 / 10 | 59 / 60 |
| 20 | 5 / 5 | 29 / 30 |
| 40 | 2 / 3 | 15 / 15 |
| 80 | 1 / 1 | 7 / 8 |

  **sigma <= ~5 is not portable** (19% peak difference at sigma 2, opposite
  sign at sigma 5). sigma >= 20 agrees to <=1 LSB on a blurred dot.
* Relative profile (sRGB, fraction of peak): sigma 10 -> 0.890/0.636/0.364/
  0.153/0.042/0.009 at 0.5/1/1.5/2/2.5/3 sigma; sigma 40 -> 0.867/0.600/0.333/
  0.133/0.067/0.000. A true Gaussian would be 0.882/0.607/0.325/0.135/0.044/
  0.011 - so the **only real deviation from a Gaussian is the hard cut-off at
  2.8-3.0 sigma**.
* `stdDeviation="40 2"` (anisotropic) works identically in both engines - the
  natural construct for the horizontal streak. `stdDeviation="0"` is a clean
  no-op in both.

## 2. Filter regions

* The default region is `-10%,-10%,120%,120%` of the **geometry** bbox -
  **stroke excluded** (measured with an `feFlood`-only filter: a 200x100 rect
  and a stroke-width-60 line with the same endpoints produce the identical
  region 280..519 x 390..509 in both engines).
* **Wide strokes get cut**: a 60px stroke on the reference-like arc with the
  default region loses **5.8% of its ink** (the outer 6.8 px of each side) -
  identically in both engines. objectBoundingBox padding of 0.2 reduces it to
  <0.12%, 0.3 to zero.
* **A zero-area bbox deletes the element in BOTH engines**: `M 300 500 L 700
  500` with stroke-width 40 and a default-region filter renders *nothing*.
* Default region + stdDeviation 40 on a thin line: **resvg drops the element
  entirely** (total ink 0); chromium renders the region-clipped strip with the
  correct peak. resvg also renders nothing for any explicit region narrower
  than ~26 px at sigma 40 (fails <=22 px, works >=26 px).
* Minimum margin at sigma 40, full 255 amplitude: 2.0 sigma loses 5/3 LSB,
  2.25 sigma 2/1, 2.5 sigma 1/0, **2.75 sigma and beyond 0/0**. Use
  `margin = 3*sigma`; the hard kernel support is 2.82 sigma (chromium) /
  2.96 sigma (resvg).
* Explicit `userSpaceOnUse` and `objectBoundingBox` regions agree between
  engines to within 1 px of outward rounding.

## 3. Additive compositing (probe: opaque grey-64 layers)

| construct | 2 layers | 3 layers | resvg | chromium |
|---|---|---|---|---|
| normal (opaque) | 64 | 64 | yes | yes |
| `style="mix-blend-mode:screen"` | 112 | 148 | yes | yes (identical) |
| `mix-blend-mode="screen"` attribute | 64 | 64 | **ignored** | **ignored** |
| `style="mix-blend-mode:plus-lighter"` | - | - | **ignored (64)** | 128 / 192 |
| `style="mix-blend-mode:lighten"` | 64 | 64 | yes | yes (degenerate probe) |
| white @ fill-opacity 0.251, plain alpha | 112 | 148 | yes | yes |
| `<style>.c{mix-blend-mode:screen}` | 112 | 148 | yes | yes |

Blend-mode sweep with **distinct** values (backdrop 96, top 48), probe at the
overlap: normal 48/48, screen 126/126, lighten 96/96, multiply 18/18,
overlay 36/36, color-dodge 118/118, hard-light 36/36 -- all identical in both
engines. **`plus-lighter` 48 (resvg, i.e. normal) vs 144 (chromium) is the only
blend-mode divergence.**

* 148 == `255*(1-(1-64/255)^3)` = 147.8, **not** the linear-light 106.7:
  element-level blending is in **sRGB** in both engines.
* Inside one filter: `feComposite arithmetic k2=1 k3=1` x3 gives **192** with
  `cif="sRGB"` and **109** with `linearRGB`; `feBlend mode="screen"` x3 gives
  **148 / 106**. Both engines identical in both spaces. With the attribute
  **missing** both give the linearRGB answer (the spec default); with the
  invalid value `auto` **resvg gives 109 and chromium 192** - always write it
  explicitly.
* **Stack depth**, 8%-white layers, N=1..16:
  * screen: `20 38 55 71 85 98 110 121 132 142 151 159 167 174 180 186` -
    **identical in both engines**, ~1.8 LSB under the ideal at N=16.
  * plain alpha: resvg `... 180 186`, chromium `... 176 182` - **up to 4 LSB
    divergence**, chromium truncating.
  * On a 10-layer blurred halo the plain-alpha total ink differs by **28%**
    between engines (mean |diff| 0.77 LSB, 8.2% of pixels >1 LSB) versus
    **2.3%** for the screen version (mean 0.09 LSB, 1.7% of pixels).
* Isolation: a blended child sees the backdrop of its parent stacking context.
  `filter`, `mask`, `clip-path`, `opacity<1` and `isolation:isolate` on an
  ancestor **all** cut that backdrop off (probe 112 -> 64) - identically in
  both engines. A group with `mix-blend-mode:screen` and normal children does
  **not** add its children together; they composite normally inside the group
  and the group screens onto the backdrop.
* Inside a `<mask>` the content is an isolated group in both engines, and
  `mix-blend-mode:screen` between mask shapes works (64 / 112).
* **Warning**: N *identical* stacked layers quantise to N-LSB steps (ten
  identical layers produced only the G values 2, 12, 22, 32). Vary sigma and
  opacity per layer.

**Recommendation**: `style="mix-blend-mode:screen"` on each glow layer, over a
flat dark background (`rgb(1,2,7)` reads back exactly in both engines). It is
the only additive-looking construct that is bit-exact across both engines at
arbitrary depth, and near-black backdrops make screen and plain alpha
numerically equivalent anyway - screen just removes the per-layer rounding
divergence.

## 4. Masks and gradients

* **Mask luminance is computed in sRGB by default in both engines** (grey 128
  -> 128, grey 64 -> 64). Adding `color-interpolation="linearRGB"` to the mask
  makes **chromium** switch to linear luminance (128 -> 55, 64 -> 13) while
  **resvg ignores it** - avoid.
* A `linearGradient` white->black in a mask tapering a bar: row-averaged
  samples 255/212/170/127/85/42/0 in both engines (max diff 1.5 LSB).
  `maskUnits="userSpaceOnUse"` and `maskContentUnits="objectBoundingBox"` both
  work; obb content agrees within 1 LSB. `mask-type:alpha` works in both.
* `stroke-opacity` x mask is multiplicative and identical (0.5 x 0.5 -> 64).
* `stroke="url(#lg)"` works in both; `gradientUnits="userSpaceOnUse"` and
  `objectBoundingBox` give the same values (obb maps to the **geometry** bbox,
  stroke excluded): peaks along the arc 18/73/128/182/237 (resvg) vs
  19/74/128/183/237 (chromium).
* `color-interpolation="linearRGB"` **on a gradient** diverges: chromium
  honours it (64/128/191 -> 137/187/224), resvg ignores it. Never set it.
* `radialGradient` - including `gradientTransform`, `fx/fy` and the SVG2 `fr`
  attribute - agrees to **max 1 LSB, rms 0.33-0.38** over the whole canvas,
  and is ~15x cheaper in resvg than a blur layer. Best fidelity-per-cost tool
  for the broad bloom.

## 5. Colour / gamma

* **For a monochrome shape on transparency, `color-interpolation-filters` has
  no measurable effect in either engine.** sRGB, linearRGB and the default gave
  byte-identical blurred profiles (peak 59/15, FWHM 24/98 at sigma 10/40). Only
  alpha is convolved, and alpha is linear in both spaces. Do not expect the
  glow *falloff shape* to change with `cif`.
* `cif` matters where values of different colours combine: a white bar abutting
  grey-64, sigma 10, junction pixel = **156 (sRGB) vs 189 (linearRGB)** in both
  engines; additive chains give 192 vs 109.
* Both engines default to **linearRGB** inside filters (spec) and composite
  elements in **sRGB**.
* Recommendation: put `color-interpolation-filters="sRGB"` on every filter, so
  in-filter arithmetic matches the sRGB screen math of the element-level stack
  and the `auto`/invalid divergence cannot bite.

## 6. Anti-aliasing and hairlines

* Coverage is linear in stroke width; **no hairline clamping** in either
  engine. Coverage integral across a near-vertical cut (resvg/chromium):
  0.25 -> 0.25/0.24, 0.5 -> 0.49/0.48, 1 -> 0.93-1.00, 2 -> 2.00/1.99,
  3.2 -> 3.25/3.19, 6 -> 6.00/5.99.
* Peak of a thin bright stroke is sub-pixel-phase dependent and **not**
  portable: 1px stroke at y=400 gives **249 (resvg) vs 227 (chromium)**;
  0.5px gives 124 vs 113.
* Stroke centre-lines agree to **0.08-0.19 px** between engines.
* Both engines lose **7.5% of the coverage on the single scanline through an
  arc's x-extremum** (row sum 236 vs 255 on neighbouring rows; peak 162 vs
  175). It vanishes at 4x supersampling - it is a rasteriser artifact, not
  something to model.
* A direct 1024 render differs from a 4096 render box-downsampled 4:1 by
  rms 0.7 LSB (resvg) / 0.7-1.3 LSB (chromium), max 55-108 LSB on single edge
  pixels.
* `shape-rendering="geometricPrecision"` = default. **`crispEdges` and
  `optimizeSpeed` turn AA off in both engines** and snap geometry (a 3.2px
  stroke becomes exactly 3px, centre snapped to 464.0) - per-pixel differences
  up to 255 LSB. Never set `shape-rendering`.
* Whole-image engine difference for one plain stroked arc: rms 0.8-1.0 LSB,
  99.9th percentile 10-13 LSB, max 64-80 LSB (AA edge pixels only).

## 7. Avoid list

1. `mix-blend-mode:plus-lighter` - resvg ignores it.
2. `mix-blend-mode` as a presentation attribute - both ignore it.
3. Default filter region with a large blur - resvg drops the element,
   chromium clips.
4. A filter on a straight horizontal/vertical segment without an explicit
   region - the element vanishes in both.
5. `color-interpolation-filters="auto"` or any invalid value - 109 vs 192.
6. `color-interpolation="linearRGB"` on a mask - 128 vs 55.
7. `color-interpolation="linearRGB"` on a gradient - 64/128/191 vs 137/187/224.
8. `shape-rendering="crispEdges"/"optimizeSpeed"`.
9. Deep plain-alpha stacks (10+ translucent layers) - 4 LSB / 28% ink drift.
10. Many identical stacked layers - N-LSB banding.
11. A typo'd `filter="url(#missing)"` - resvg drops the element, chromium
    renders it unfiltered (useful to know while iterating).
12. Negative `stdDeviation` - both render the element unfiltered instead of
    dropping it (not spec; don't rely on it).

## 8. Performance (1024x1024, this machine)

| scene | resvg | chromium |
|---|---|---|
| trivial background | 42 ms | 231 ms (process startup) |
| 100 plain stroke layers | 316 ms | 313 ms |
| 100 screen-blended stroke layers | 999 ms | 418 ms |
| 5 blurred+screened layers, tight regions | 610 ms | 265 ms |
| 10 blurred+screened layers | 1130 ms | 357 ms |
| 20 blurred+screened layers | 2150 ms | 400 ms |
| 40 blurred+screened layers | 4119 ms | 532 ms |
| full-canvas radialGradient | 195 ms | 268 ms |

* resvg's filter cost is proportional to **filter-region area**: the same 10
  sigma-24 layers took 2963 ms over 1184x1184, 2331 ms over 1024x1024 and
  **757 ms over 320x910**. Tight per-layer regions are a 4x speed-up.
* Marginal cost per layer: resvg ~105 ms per blurred layer (tight region) vs
  chromium ~7 ms; ~7 ms vs ~1 ms for a screen-blended plain stroke.
* Engine agreement degrades slowly with stack depth (the ~4% sigma difference
  accumulates): 5 layers rms 0.31 LSB, 10 -> 0.48, 20 -> 0.70, 40 -> 1.11
  (max 18 LSB).
* **A 100-layer all-blur stack would cost resvg ~10 s per render.** Keep the
  blur count to ~10-20 and build the rest from gradients.

## 9. Recommended skeleton

```svg
<rect width="1024" height="1024" fill="rgb(1,2,7)"/>          <!-- flat bg -->
<!-- broad bloom: gradients, no filters -->
<ellipse ... fill="url(#bloom)" style="mix-blend-mode:screen"/>
<!-- glow layers: 10-20 blurs, distinct sigma/opacity, tight regions -->
<filter id="g24" filterUnits="userSpaceOnUse" x="158" y="-12" width="464" height="1034"
        color-interpolation-filters="sRGB">          <!-- margin >= 3*sigma -->
  <feGaussianBlur stdDeviation="24"/>
</filter>
<g filter="url(#g24)" style="mix-blend-mode:screen">
  <path d="M ..." fill="none" stroke="#ccffff" stroke-width="9" stroke-opacity="0.18"/>
</g>
<!-- core strokes last, unfiltered -->
<path d="M ..." fill="none" stroke="#ddffff" stroke-width="3.2" style="mix-blend-mode:screen"/>
```

Tune `stdDeviation` against the renderer of record and remember the other
engine's glow will be ~4% tighter (chromium) or wider (resvg); do not rely on
sub-pixel stroke *peaks* (up to 22 LSB apart) or on blurs with sigma <= 5.
