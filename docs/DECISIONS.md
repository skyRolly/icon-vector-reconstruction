# Decision record

Why the reconstruction looks the way it does inside. Each entry states the
decision, the evidence, and what was rejected.

---

## D1. Representation: hand-built parametric SVG, no raster component

**Decision.** A single parametric SVG: one path for the frame (straight runs
plus three arcs per corner), two cubic-Bezier paths for the luminous curves
(reused, offset, by every glow layer), and blurred ellipses, rects, cones and
gradients for the central light and the background. Every mark is driven by a
named number in `src/params.json`. No embedded bitmap, no traced outlines.
(The layer count and the file size are not restated here: they are generated
into the README from `src/params.json` and the built file, because this entry
and the README both carried stale counts for a whole iteration -- 22 and 28
named layers, ~52 and ~68 KB, against the real 29 and 74 KB.)

**Evidence.** Everything visible decomposes into geometry plus smooth optical
falloffs: the curves are sub-pixel-accurate Beziers (section 3 of
`docs/METHOD.md`), the glow separates into a product of an inward profile and an
along-curve modulation (i.e. a blurred stroke with a taper), the colour space is
a narrow non-negative cone (D6: a PCA of the interior gives eigenvalues 0.981 /
0.012 / 0.007, so the light is *nearly* two-dimensional, but the third dimension
is where the whole dark background lives, and each layer carries three
non-negative amounts, not two), and the background is two radial gradients plus
a ramp. Nothing needed a per-pixel description.

**Alternatives evaluated.**

* *Automatic bitmap tracing.* Rejected on principle for this image and not used
  even as an aid: the subject is 95% smooth gradient. A tracer would emit
  thousands of iso-luminance contours of JPEG noise, would not scale (the
  contours are rasterisation artefacts, not design), and would not be editable.
* *Hybrid SVG + one raster layer* for the background texture. Rejected: the
  only thing a raster layer would add is the reference's own JPEG blocking and
  generator smudge (D7). It would have improved the metrics slightly while
  making the artwork non-scalable and non-editable.
* *A single mega-filter* doing the whole composite with `feComposite
  arithmetic`. Rejected: portable but unreadable, and it would have made the
  analytic fitting impossible.

## D2. Curves: two cubic Beziers per curve, not an ellipse arc

**Decision.** Each curve is two cubic segments joined at the apex with a
vertical tangent.

**Evidence.** Ridge RMS 0.083/0.093 px against 0.331/0.473 px for the best
axis-aligned ellipse arc; verified end-to-end (render the candidate, re-extract
the ridge, compare with the reference ridge) at 0.11/0.13 px versus 0.33/0.47 px.
The ellipse's residual is a smooth 4-5 lobe +-0.4 px shape that no fifth conic
parameter removes.

**Rejected.** Circle (RMS 1.7-1.8 px). Parabola (5 px). Rotated ellipse and
general conic: the general conic converges to the rotated ellipse, and the
fitted rotation swings from -24 to +11 degrees with the y-range used, so the
parameter is absorbing model error, not measuring a tilt. A superellipse
exponent helps the left curve and not the right. The elliptical-arc form is
kept in `src/params.json` (as `measured_ellipse_fits_pixelindex`) because the
glow clip still uses it, and it documents what the shape is close to.

## D3. Frame corners: a 3-arc continuous-curvature corner

**Decision.** Each corner is blend arc (r 639.06, 5.0916 deg), main arc
(r 163.561, 79.8168 deg), blend arc -- the corner design tools draw with "corner
smoothing" on.

**Evidence.** Residual to the measured corner outlines: 0.13-0.27 px, against
0.35-0.44 px for a single cubic Bezier corner, 0.66-0.84 px for a circular
rounded rect tangent to the measured straight edges, and 2.5-2.7 px for a
superellipse. Independently: the local radius of curvature runs 250-400 px near
the straights and 145-175 px through the 45-degree region; a circle fitted to
the corner points alone sits 1.9-2.7 px inside both straight edges, so it
cannot join them; and the centre-line is still 0.66 px inward 195 px from the
box corner, where any circular corner fitting the 45-degree region would be
exactly on the line. All four corners share one radius to +-0.21 px.

**Rejected.** `<rect rx>` / circular arcs (a visible 1.4-1.8 px corner
mismatch). A per-corner superellipse, which was this reconstruction's own
earlier answer: fitting |dx/r|^n + |dy/r|^n = 1 with the centre pinned so the
curve is tangent to the measured edges gives n = 2.45, r = 203 and ~0.7 px --
better than a circle, and still five times the 3-arc residual. It is left in
`src/build_svg.py` (`squircle_rect_path`, selectable via
`frame.corner_model`) because it documents what the shape is close to.
Per-corner radii were not used: the four agree within noise.

## D4. Glow: three offset blurred strokes per curve

**Decision.** Each curve's glow is three stroked copies of its own path, offset
inward by 3.28 / 16.20 / 62.07 px and blurred so their perpendicular profiles
are Gaussians of sigma 7.22 / 26.92 / 56.59 px, each with its own measured fade
along the curve.

**Evidence.** Cross-sections out to +-320 px at 45 stations per arc are
reproduced, core included, to 2.4-2.7 code values rms (JPEG noise floor 1.3) by
exactly that decomposition, with the sigmas and offsets *global* -- one set for
both curves and every station -- and only the amplitudes varying. The inward
offsets are what produce the measured 2.8-3.5x concave/convex asymmetry.

**Rejected.**

* *Symmetric blurred strokes only*: cannot produce the asymmetry at all. The
  first version of this reconstruction did that and left the region between the
  curves several counts too bright and the concave side too dark.
* *An ellipse filled with a light-centred radial gradient*: reproduces the
  asymmetry but not the along-the-curve modulation. Along a normal at
  mid-latitude the distance to the central light barely changes while the
  brightness drops 4x, which rules out any light-centred radial field.
* *Wide blurred strokes clipped to each curve's own ellipse*: this was the
  second version, and it works (it was the single biggest fidelity jump of the
  whole job, MAE 9.19 -> 6.80). The measured three-Gaussian decomposition
  replaced it because it needs no clip, no extra `clipPath` defs, and reaches a
  lower peak error (max channel error 147 -> 100). **Partly reinstated in
  D13**: three inward-offset strokes get the sign of the asymmetry right and
  its extent wrong, and the clip is the only thing that stops the broad
  concave tail from also filling the space between the curves.

## D5. Colour: a three-component non-negative cone

**Decision.** Every layer carries three non-negative numbers: how much
white(1, 1, 1), cyan(0, 0.94, 1) and blue(0, 0, 1).

**Evidence.** PCA of the interior colour *directions* gives eigenvalues 0.981 /
0.012 / 0.007, so the light is nearly two-dimensional — but "nearly" is not
"is", and the third dimension is where the whole background lives. Over the
946 964 reference pixels above luminance 3, the non-negative fit in this basis
is off by **0.010/255**; dropping blue and keeping white+cyan alone is off by
**1.84/255**, and white alone by 9.96/255. The same ordering holds at every
brightness threshold (1.5-1.8/255 for white+cyan at thresholds 10, 25 and 60).
The reason is the dark field: across its 620 317 pixels between luminance 3 and
14 the mean colour is (1.8, 7.1, 13.4), G/B = **0.53**, against cyan's 0.94.

The point of the basis is not compression, it is a modelling safeguard: the
non-negative cone spanned by these three vectors is exactly `R <= G <= B`, the
family the reference uses everywhere, so a shape error can no longer be hidden
by inventing a colour.

**Rejected.**

* *White + cyan only.* This was the previous decision, and it was wrong by a
  factor of 180 in the colour residual. An earlier version of this record and
  of the README said each layer "carries just two numbers"; the code had three
  components all along. Corrected here and in `README.md`.
* *Free RGB per layer.* Fits marginally better in the raw metric but produced
  physically absurd layers (a magenta core, a green bloom) as the optimiser
  used hue to compensate for shape error, and made the SVG much harder to
  reason about.

## D6. Compositing: `mix-blend-mode: screen`

**Decision.** Screen over an opaque black base, clip on every element.

**Evidence, measured in both engines.** `screen` gives identical results in
resvg and Chromium (64 over 96 -> 136 in both). `plus-lighter` — the physically
correct operator — is **not** implemented by resvg (it falls back to 96 where
Chromium gives the correct 160), so it is unusable here. A group carrying
`clip-path` becomes an isolated group and silently kills `mix-blend-mode` for
its children (96 instead of 136, in *both* engines), so clips are set on each
element instead of on a wrapper. `clip-path` and `filter` on the element itself
compose correctly with the blend mode.

Screen is also a good model for the reference: light adds while dim, and rolls
off into a clipped white core.

## D7. Not reproduced: JPEG blocking and generator texture

**Decision.** The reference's +-1..3 count 8x8 DCT blocking, and the
low-frequency smudge texture in the side lobes, are not reproduced.

**Evidence.** XMP says `CreatorTool = Picasa` and the blocking is on an 8x8
grid — it is a compression artefact of the delivered file, not of the artwork.
The smudge has no constructible geometry and differs between the two lobes.

**Cost.** These set the noise floor on every metric: a perfect reconstruction of
the underlying design would still show ~1-2 counts of MAE from them.
The brief explicitly forbids introducing texture not supported by the reference,
and reproducing an artefact of the file format is not fidelity to the design.

## D8. Filter regions and colour interpolation are pinned

**Decision.** Every blur filter has an explicit user-space region clamped to
the frame's bounding box, and `color-interpolation-filters="sRGB"`.

**Evidence.** The SVG default region (-10%/120% of the object bounding box)
visibly clips a sigma-165 blur of a thin path. The SVG *default* colour
interpolation is linearRGB, which changes every glow falloff; pinning sRGB
matches the reference's own compositing space and removes an engine-dependent
variable. Clamping the region to the frame bbox is lossless (filtering happens
before clipping) and cut the render time by a third.

## D9. Fitting: analytic photometry, searched geometry

**Decision.** Layer colours are fitted in closed form; layer shapes and the
geometry are searched by bounded coordinate descent with the colours re-fitted
inside the loop.

**Evidence.** The closed-form composite (D6) makes the colour problem a smooth
52-parameter least-squares that needs no rendering, so it converges in seconds
and cannot be the bottleneck. Shapes have to be searched because they change the
coverage fields. Per-layer bounds are part of the artwork, not just the search:
without them the optimiser swaps a "near" glow for a "wide" one or collapses the
core stroke into the halo — numerically free, but it destroys the layer stack's
meaning.

## D11. The central light: no bright disc, plus a separate glint

> **Superseded by D14.** Kept because its evidence still stands and because one
> of its conclusions was wrong in a way worth recording. "No bright disc" was
> read off the *composite*, where the flare centre reads luminance 224; the
> exact isolation in D14 shows the flare's own contribution peaking exactly
> there, at additive luminance 4.9, and 198 pixels above luminance 248 in a
> plateau ~20 px across. What the reference does not have is a bright disc with
> a *peak*; it has one with a flat, clipped top. The reconstruction now carries
> a plateau-topped core, and the "glint" of this entry is that core.

**Decision.** The centre is built from a two-part horizontal streak, two
horizontally stretched blooms, three individually placed one-sided rays, and a
separate compact glint at (535.0, 514.8) -- and *no* bright disc at the flare
centre.

**Evidence.** At the flare centre the image reads lum 224 and nothing within
15 px of it reaches 245; along the waist the luminance rises monotonically from
one core to the other with no local maximum in between. Meanwhile every
off-arc pixel above lum 245 lies in one small patch centred (531.3, 512.8),
whose excess over the mirrored image is a clean bump of FWHM 35.5 px centred at
(534.5, 514.3) with a peak of 170/255 -- and the two right-hand rays converge
on it. So the visually brightest thing in the icon is not the flare centre.

**Rejected.** A radial "core" disc at the flare centre -- which is what this
reconstruction had for several iterations. It produced a local maximum the
reference does not have (+11 code values at r < 12 and -6 at r = 12-25 in the
ring profile) and cost 2.4 MAE in the central region. A symmetric starburst
primitive was also rejected: the three measured rays are one-sided and are
neither 4- nor 6-fold symmetric, so a symmetric primitive invents three rays
that are not there -- at 3-5 code values each, they would be as strong as the
real ones.

**Ambiguity kept in the record.** The glint's vertical centre (514.8)
coincides with the curves' own symmetry axis (514.85) rather than with the
streak (512.2), so it can be read either as a second glint element of the flare
placed on the right curve's apex (which is what the ray convergence says) or as
an extra inner glow lobe belonging to the right curve. Both readings produce
the same pixels; the reconstruction draws it as one radial layer and does not
claim which it is.

## D12. Renderer choices, measured in both engines

224 purpose-built test SVGs were rendered in both resvg and headless Chromium.
What that settled:

* **`mix-blend-mode` must be written in `style=""`.** As a presentation
  attribute it is ignored by *both* engines.
* **`screen` is byte-identical** in both at every stack depth 1..16, and it is
  sRGB-space screen (three grey-64 layers give 148, not the linear 106.7).
  Plain-alpha stacks diverge instead (resvg rounds, Chromium truncates: 4 code
  values at depth 16, and a 28% total-ink difference in a 10-layer blurred halo
  against 2.3% for the screen version).
* **`plus-lighter` is unusable**: resvg silently falls back to normal (48 where
  Chromium gives the correct 144).
* **Filter regions must be explicit and in user space.** With the default
  region a sigma-40 blur loses the element entirely in resvg (ink 0) and is
  clipped in Chromium; the default region is also the geometry bbox with the
  *stroke excluded*, so a 60 px stroke loses 5.8% of its ink in both. A margin
  of 3 sigma clips exactly nothing.
* **`color-interpolation-filters` must be written explicitly.** The absent
  default is linearRGB in both, but `auto` diverges (109 vs 192 on the same
  additive chain). It has no effect on a monochrome blurred shape -- only alpha
  is convolved -- so it does not change any glow's falloff here; it matters
  only where different colours combine.
* **Known residual disagreement.** Both engines use a three-pass box blur, but
  with different box sizes: resvg's effective sigma is 0.98-0.99 of nominal and
  Chromium's 0.94, so resvg's wide glows are 3.5-5.3% wider. Small blurs are
  worse: a 1 px line at sigma 2 peaks at 51 in resvg and 43 in Chromium. This
  is the main reason the two engines disagree at all on this artwork
  (`out/validation.md` quantifies it end to end), and it is not fixable from
  the SVG side.
* resvg also quantises stroke-outline edges to multiples of 0.25 px, so there
  is no point tuning frame geometry below ~0.13 px.
* **Chromium renders each *dim* screen layer slightly brighter, and it
  accumulates.** Measured on this artwork by rendering subsets: one dim layer
  alone is +0.26 to +0.33 code values brighter in Chromium than in resvg, four
  of the field layers together +1.32, two corner layers +0.50 -- roughly
  additive, and roughly absent on bright layers (three arc glows: +0.22 in
  total). Across the whole 29-layer stack it is a **+2.77** mean offset.
  That offset is nearly all of the cross-engine difference: the MAE between the
  two engines is 2.907, and 1.355 once the mean is removed, so the two engines
  agree on the artwork's *structure* and disagree on a near-uniform lift of the
  dark background. It is a compositing-precision artefact, not something the
  SVG can express its way out of: the layers cannot be merged, because a
  gradient modulates alpha only and each of these layers carries a different
  colour. It is the cost of the extra elements iteration 2 added -- the same
  figure was about +2.0 with 22 layers -- and it is the one number that got
  worse while every fidelity measure improved.

## D13. The broad glow is clipped to the lobe, and one stroke leans the other way

**Decision.** Two components were added to each curve. `arc_haze` is a wide,
low-amplitude stroke deep in the lobe, `clip-path`-ed to that curve's own
ellipse so it puts *nothing* on the convex side. Two components are offset
**outward**, towards the space between the curves: `arc_glow2b` (the wider of
the pair) and `arc_glow1b`. Every other glow component is offset inward.

**Evidence.** Signed-distance profiles pooled over both curves, with everything
within 200 px of the central light excluded (section 4a of `METHOD.md`). Above
the far-field floor the concave excess is 1.7x the convex one 11 px out and
5.9x 100 px out; the convex side is indistinguishable from the background by
100-130 px while the concave side still carries 6 code values at 170 px. On the
inter-curve midline at y=200, 140 px from *both* curves, the reference sits at
3.9 code values against 13.5 at a lobe point 140 px from one curve.

Against that measurement the previous stack was 13-19% too dark in the band
28-70 px between the curves and 6-11% too bright in the lobe 14-38 px out —
because every one of its strokes was inset into the lobe, so the convex side
only ever saw their tails. `arc_glow2b` cut the profile's rms relative error
from 8.6% to 7.0% with no change in global MAE (2.2753 -> 2.2745).

**Rejected.**

* *Retuning the three existing strokes.* A scan of `arc_haze` over
  width x inset x blur = 4 x 3 x 3 found nothing better than the starting
  point: the concave side was already within 11% everywhere, so no amount of
  broad-concave shape fixed a convex-side deficit. That is what identified the
  missing component rather than a missing parameter value.
* *Removing `field_mid`, the broad central wash, instead.* Tried: the profile
  error got worse (7.0% -> 8.0%) and the global MAE much worse (2.275 ->
  2.478). It earns its place; what it needed was a searchable vertical squash,
  since a round blob of its size over-fills the top and bottom of the lens.
* *Reusing `glow3`'s measured fade for both new components.* Splitting the
  profile error by along-curve angle showed why that is wrong: near the waist
  the two sides balanced, but towards the tips (\|t\| 40-62 degrees) the
  reconstruction was +27% on the concave side and -15% on the convex one, i.e.
  far too one-sided exactly where `glow3`'s fade has died. The three original
  fades are measured station by station and stay tables; the two new components
  carry their own tunable ramps (`tapers.haze`, `tapers.glow2b`), which is
  honest about the fact that no station-by-station measurement exists for them.
* *A softer, unclipped version of `arc_haze`.* The hard edge a clip leaves at
  the curve is a real artefact, but it falls under a core stroke two orders of
  magnitude brighter and is invisible at every resolution tested; an unclipped
  stroke wide enough to reach 270 px into the lobe puts 20-40% of that light
  between the curves, where the reference is at its darkest.

## D14. The central light's extent is bounded by measurement, not by the metric

**Decision.** The flare is rebuilt from an exact isolation of its own
contribution (`tools/isolate.py`, method in section 5a of `METHOD.md`): a
plateau-topped compact core, two halo terms whose widest is bounded at 210 px,
a thin 59-px-west-centred streak, a broad fan, and five cones. (D21 rebuilds
it again, to the measured streak comb and the thin spokes; the shipped layer
list is in `src/params.json` and is not restated here.)

**Evidence.** In additive luminance the isolated flare falls from 2.30 at r=6
to 0.02 at r=92 and **0.005 at r=115**, i.e. nothing measurable past
~130-160 px. The previous widest bloom had r=378 px and its surplus filled the
space between the curves — the darkest part of the interior. Three further
measurements each forced a specific change:

* 198 reference pixels sit above luminance 248 in a plateau ~20 px across; the
  previous reconstruction rendered 67 of them and was 20 code values too dark
  at the centre. This one renders 184, and 170 against the reference's 170
  within 60 px of the centre.
* the streak's additive excess peaks at 0.76 across two pixel rows, and the old
  markup (a 2 px rect blurred by 2.7 px) caps on-axis coverage at 0.29 — so the
  layer's colour was pinned at white and the streak still rendered three times
  too faint. The rect height and the blur are now both derived from `sigma_y`
  at `h / sigma_b = 3.92`, giving 0.95 on-axis with `sigma_eff = sigma_y`.
* the westward fan's half width grows from ~10 px at r=30 to ~28 px at r=92, so
  a parallel-sided quad can match its near part or its far part but not both.
  Rays now carry a `spread`.

**Effect, as measured at the time of this change.** Flare radial profile
agreement went from -20/-13/-11 code values at r<45 to within +-4.3 at every
radius; MAE within 110 px of the core 10.01 -> 7.9; peak channel error over the
whole image 112 -> 96. These are the figures for *this* decision and not the
current state of the reconstruction: D21 rebuilt the streak afterwards, and the
current numbers are in the README's generated fidelity table and in
`out/diagnostics.json`.

**Rejected.**

* *Raising the bloom's amplitude to close the r<12 deficit.* That deficit was a
  plateau-versus-peak error, and the amplitudes were already clipped against
  white — three separate layers were sitting exactly at the colour bound, which
  is the signature of a shape that cannot deliver what the fit wants.
* *A dedicated flat-topped disc at the centre.* This was tried and it worked: a
  `plateau` fraction on the falloff law, holding it at its peak over the first
  part of the radius, took the centre from 20 code values too dark to within 3.
  It is not in the final reconstruction, because it was the right fix for a
  model that was wrong elsewhere. Once the halo's radius came down to its
  measured 92 px and the streak markup stopped capping its own on-axis
  coverage, the sum of halo and streaks saturates over the measured plateau by
  itself: re-fitting left the flat-topped disc at 0.006 of full amplitude, and
  removing it changed the whole-image MAE by -0.0001 — it heads the
  `tools/prune_layers.py` report. The parameter went with it rather than
  staying as an unused knob; the SVG is byte-identical without it.
* *A symmetric starburst primitive.* The angular maxima are at 45-60, 110-120,
  175-195, 225-255, 300 and 330-345 degrees, with the westward one 3-5x the
  eastward one. Neither 4- nor 6-fold symmetry, so the primitive would invent
  rays that are not in the image.

## D15. The fitting objective scores the glow's shape cell by cell

**Decision.** The per-pixel fitting weight has a third emphasis term. The
glow's cross-section is divided into cells -- (signed distance from the curve) x
(along-curve band), plus the four interior corners past the curve ends, and
since the flare rebuild also the flare's radius x sector cells and its streak
comb, 222 in all -- and each cell receives the same influence, shaped as
`1 / (L + floor)^(2p)` inside the cell, *replacing* the display-curve weight
there rather than multiplying it. The cells are disjoint by construction. The
floor and the exponent are `EMPHASIS["profile"]`'s, and D20 measures them: the
shipped values are 0.006 and 1.0. `tools/test_pipeline.py` prints the cell count
and the cost spread on every run, so neither figure has to be remembered here.

**Evidence, in three steps, each one a thing that went wrong first.**

1. *Scale.* The objective is a weighted sum of squares, so what a cell costs
   for a given *relative* error is `(total weight) x (r L)^2`. Equalising that
   needs `1/L^2`, not `1/L`, and needs the base weight out of the way. All the
   figures here are now measured with the *production* formula, because the
   earlier ones were not and two different numbers ended up standing for two
   different things under the same name. With the shaping in place a uniform 1%
   relative error costs 4.57x more in the worst cell than the best; with the
   display curve alone and no cell shaping, 51.23x. And while the weight was
   being applied in the wrong convention (see below) the production spread was
   183.27x -- the mechanism by which "a numerically strong global score"
   coexisted with an obvious local error: a 19% deficit 45 px inside the curves
   cost the fit less than a 2% error on the frame.
2. *Where the floor sits.* `1/L^2` with no floor equalises relative error
   exactly -- Weber's law -- and Weber's law fails near black: 15% of the
   7.5-count outermost cell is one code value and invisible, 15% of the
   42-count innermost cell is six and not. The floor is therefore a visibility
   threshold. It was 0.012 (3 code values) here; D20 re-measures it and ships
   0.006, about the quantisation scale.
3. *Cells, not distance-only bins.* Pooling along the curve hid the tips
   completely. Every pooled bin read within 5%, while the lobe within 80 px of
   a curve end was 20-30% too dark -- and because the objective could not see
   it, the taper search had drained it further (iteration 1 was 15-20% too dark
   there, not 30%). Splitting by along-curve band is what surfaced it.

`tools/test_pipeline.py` checks all three: the cost of a 1% relative error
across the cells, that the outermost along-curve band is covered, and that the
interior corners are covered.

**Rejected.**

* *A fully relative weight, `1/(L + f)` over the whole image.* It did improve
  global MAE (2.2955 -> 2.2501) but degraded the flare (bias -4.0 -> -5.6 code
  values inside r=40) and still left every structural error in place, because
  those are shape errors and no reweighting fixes a shape.
* *Overlapping cells.* Cells that share pixels are each weighted as if they
  owned them, and the shared pixels take whichever value was written last; the
  cost spread went from 2.3x to 6.2x. They are made disjoint in
  `regions.weight_cells`.
* *Cells past the curve ends.* Tempting, since that is where the worst deficit
  was, but there is no curve there -- it would have been asking the glow layers
  to light a region with no source. The deficit belongs to a separate element;
  see D18.

## D16. Optimiser correctness, and the checks that keep it

**Decision.** Five defects that could invalidate an optimisation result were
fixed and are now covered by `tools/test_pipeline.py`, which
`tools/optimize_all.sh` runs first.

* **Stale layer caching.** The basis cache was keyed on layer id with a
  hand-maintained list of which parameters invalidate which layers; the list
  and the builder had drifted, so trials were scored against streak artwork
  that the parameters no longer described. The cache key is now a SHA-1 of the
  SVG the layer would actually render, which makes a stale entry impossible by
  construction, and the builder itself answers which layers read the global
  flare centre (`build_svg.flare_dependent_layers`).
* **Search intervals that excluded the current value.** `field_grad.cx` sat at
  890.33 while the generated interval ended at 820, which silently froze it:
  every proposal landed outside and was rejected unevaluated. Field intervals
  are now generated around the current value, and any interval that still fails
  to contain it is widened with a log line. A check asserts that every
  generated interval contains its parameter's value.
* **Parameters nested under `paint/`.** `exterior_corner`'s gradient centre is
  `paint.cx` / `paint.cy`, which the field spec builder never looked at, so
  that layer was skipped entirely. Both spellings are discovered now.
* **List-valued parameters.** An anisotropic `[x, y]` blur produced no specs at
  all. Each component is now searched separately, with per-component intervals;
  the check exercises this against a probe layer so it cannot pass vacuously if
  the shipped artwork happens to use only scalars.
* **A degenerate parameter under search.** `corner_r_blend` was searched with a
  +-300 px span although the corner fit only measures the blend's lateral
  offset `r (1 - cos a)`; it had drifted 639.06 -> 619.06 for a 0.08 px change
  in that offset, leaving the documented value wrong. It is now held at its
  fitted value and only the turn angle — which spans the identifiable
  direction — is searched.

**Rejected.** *Clamping `field_grad.cx` into the old interval.* The value was
not the error; the interval generator was. Clamping would have moved a measured
gradient centre 70 px to satisfy a bound that had no evidence behind it.

## D17. Headless Chromium is optional in fact as well as in the README

**Decision.** `tools/validate.py` takes `--no-chromium`, checks that the binary
exists before invoking it, catches a failed launch, and says plainly in its
report that the cross-engine rows were not measured while the resvg rows are
unaffected.

**Evidence.** The README said Chromium was optional; `validate.py` invoked it
unconditionally, so the documented validation command failed on a clean
checkout with only the documented dependencies installed. Behaviour and
documentation now agree; `python3 tools/validate.py --quick --no-chromium`
completes with numpy, Pillow and resvg-py alone.

## D18. The light in the four interior corners is its own element

**Decision.** Two layers, `corner_in` and `corner_in_top`: each a wide stroked
copy of the frame path, clipped to the interior, blurred, painted with a radial
gradient centred in the icon so that it lights the corners and not the edge
midpoints. Two rather than one because the top pair of corners is brighter and
reaches further into the interior than the bottom pair, and a single layer
splits the difference and is wrong at both ends.

**Evidence.** Over interior pixels more than 40 px from either curve and more
than 250 px from the central light, within 100 px of the frame, the corner
quadrants read 9.5-11.0 code values in the reference against 7.0-8.3 rendered
(30% too dark over 67 000 px) while the edge midpoints agreed to 0.1-0.7. The
deficit does not decay with distance from the *curve*, it decays with distance
from the *frame*, and only near the corners. Nothing else in the model is
corner-weighted on the inside: `exterior_corner` is clipped to the outside, and
the interior field gradient is a single monotone ramp, which cannot be bright
at all four corners at once.

The primitive works because of the frame's own geometry: its path is 651 px
from the icon centre at the corners against 442-478 px at the edge midpoints,
so a radial gradient rising across that range separates the two.

**Rejected.**

* *Extending the curve glow past the curve ends.* The Bezier endpoints are at
  \|t\| = 66-69 degrees; the deficit runs from there to 90. Filling it with
  curve glow would put light where the reference has no curve, and would need
  the glow layers to stop obeying their own measured cross-section.
* *Making the interior field gradient corner-weighted.* It is one radial ramp
  centred well outside the canvas -- measured, and it beats flat by 33% in G
  MAE on a glow-free mask. A single ramp cannot be bright at four corners, and
  replacing it with something that can would discard a measured element to fix
  an unrelated one.

## D10. Asymmetries are preserved, not tidied

The frame is 885 x 957 (not square) and sits 3.5 px left of the canvas centre;
the curves' mirror axis is x = 504.5, which is neither the canvas centre nor the
frame centre; the curves' own vertical centre is y = 514.85 while their apexes
are at y = 517-519; the pair departs from mirror symmetry by up to 1 px in the
bottom third. All of these are measured, repeatable, and reproduced. The brief
asks for the observable result, not for a tidier design.

## D19. The banding inside the curves: what it is, and what it is not

The reported defect was "vertical banding / layered stripes" in the lobes, and
five hypotheses were tested before anything was changed. Four are refuted and
recorded here so they are not tried again.

**The metric had to be built first, because the obvious one is backwards.**
A high-pass "smoothness" score says the render is *smoother* than the reference:
in the lobes its total cross-curve band-pass amplitude is 0.51 counts rms at
sigma 3 against the reference's 0.68, and across the open interior 0.10-0.28
against 0.49-0.65 -- a third of it. Blurring would score better still. What
differs is coherence along the curve. The reference's band-pass content is grain
and JPEG texture, uncorrelated from one height to the next, so averaging along
the curve cancels it as 1/sqrt(N) -- to 0.029 counts at N ~ 450. A layered field
produces the same cross-curve profile at every height and survives that average
untouched, and what survives is exactly what the eye reads as a stripe. So the
measurement is the along-curve-*averaged* cross-curve profile, the reference
supplies its own value for every part of it, and the target is two-sided: less
coherent structure than the reference fails as well, because that is what
blurring the region until the stripes stop showing would produce.
`band_report` in `tools/diagnose.py` is that measurement.

**Refuted: gradient stop interpolation.** SVG gradients interpolate linearly, so
every stop is a slope discontinuity. Replacing the sampling with a monotone
cubic (PCHIP) through the measured knots plus error-driven adaptive sampling to
1.0 code values changed the far-lobe contour residual from 0.3271 to 0.3284 --
i.e. not at all. The smooth interpolation was kept anyway, because it is a more
faithful rendering of the profile the parameters describe, but it is not a
banding fix and must not be described as one.

**Refuted: 8-bit output and dithering.** A float render averaged over 4096
samples and a dithered render show identical patches.

**Refuted: filter-region truncation.** The old comment's claim that clamping the
region inside the frame bbox was lossless *was* wrong and is fixed, but the
measured effect was at most 1.33 counts, mean -0.102.

**Refuted: the renderer.** The analytic float composite (no 8-bit step
anywhere), the shipped 1024 px resvg render, and a 4096 px render box-downsampled
to 1024 score 0.3920, 0.3901 and 0.3863 -- all 1.67-1.69x the reference. The
excess is in the model, not in any rasteriser.

**Refuted for the lobe as a whole, confirmed for the ridge strip: one bad
layer.** Removing each layer in turn and scoring the *whole* lobe moves the
coherent amplitude by at most 1.6%, and removing the field layers makes it
slightly worse -- the fit has arranged partial cancellation between them. That
is the answer to the wrong question, because the whole-lobe figure dilutes the
strip where the excess actually is. Scored on the ridge strip alone the answer is
unambiguous: removing `arc_glow1` takes it from 0.9215 to 0.2370 counts on the
left curve and 0.7507 to 0.3017 on the right -- **74% and 60%** of the total,
against the reference's own 0.4950 and 0.5791. `arc_glow1c` accounts for 4% and
8%, and every other layer for under 1%. Removing `arc_glow1` overshoots to 0.48x
and 0.52x of the reference, so the layer is not spurious: its cross-curve
profile is too sharp, and the amount by which is measurable against the
reference's own coherent amplitude rather than against a preference for
smoothness.

**And softening it is not the fix.** `arc_glow1`'s blur is the one parameter
that sets how much 3-px-scale cross-curve content it puts in that strip, so it
was swept with the cost reported beside the gain:

| blur | sigma_eff | ridge coh L | ridge coh R | MAE | SSIM | ridge profile err | interior |
|---|---|---|---|---|---|---|---|
| 5.108 | 5.8 | 1.85x | 1.30x | **1.9723** | **0.9726** | **4.00%** | **4.13%** |
| 7.0 | 7.6 | 1.99x | 1.52x | 1.9968 | 0.9720 | 3.39% | 5.36% |
| 9.0 | 9.4 | 1.68x | 1.36x | 2.0406 | 0.9712 | 4.52% | 5.17% |
| 11.0 | 11.4 | 1.34x | 1.16x | 2.0946 | 0.9705 | 5.96% | 5.07% |
| 12.0 | 12.3 | 1.20x | 1.06x | 2.1181 | 0.9700 | 6.55% | 5.10% |

Blurring the layer does bring the coherence ratio down, from 1.85x to 1.20x, and
makes the *profile error in the same strip worse* as it does so -- 4.00% to
6.55% -- along with the global MAE (+0.146) and SSIM. This is the blur-to-satisfy-
the-metric outcome that the two-sided target exists to catch, caught here by the
measurements beside it. The layer is left as it is.

What that leaves is a real limitation of the blurred-stroke family rather than a
parameter error: a blurred stroke that matches the reference's *level* in the
14-40 px strip necessarily carries more 3-px-scale cross-curve structure there
than the reference does, and the two cannot be separated by choosing a blur.
Separating them needs a primitive whose profile can be flat-topped where a
Gaussian is peaked -- a change of kind, on the evidence above, and not one to
make blind at the end of an iteration.

**What it actually is: two defects, in different places, with different causes.**
Localising the error in cross-curve distance separates them, and pooling them
was what made the earlier readings contradictory.

*Inside 40 px of the ridge* the glow basis cannot reach the reference's shape.
The effective cross-curve widths of the glow strokes step 5.8 px (`arc_glow1`)
to 20.6 px (`arc_glow2`), a factor of 3.5, and the best achievable residual
peaks inside that step and changes sign across it. Adding one stroke in the gap
raises the best achievable accuracy there -- the profile-only non-negative fit,
scored on the same grid as everything else -- from 1.08%/0.49% to 0.32%/0.19%
(left/right), and its oscillatory part from 0.711%/0.253% to 0.196%/0.165%.
Three candidate widths between sigma_eff 10 and 12.5 px all do it; the shipped
one is width 20, blur 8, inset 10. Position matters as much as width: the same
effective width at inset 14 instead of 6-10 is markedly worse. That is the
evidence for `arc_glow1c` -- one blurred stroke on the existing Bezier path, six
numbers, no new geometry.

It is **not in the shipped model.** The capacity it buys is real and so is the
measurement, but capacity is what the basis *could* reach and the fit never
reached it: adding the layer and re-fitting moved the achieved ridge excess from
1.82x to 1.81x on the left curve and 1.21x to 1.23x on the right, while the
reconstruction as a whole measured worse (D22). The layer waits for a search
that can exploit it against the corrected objective and the corrected builder
(D23), and this entry is the record of what it would buy if one does.

*Beyond 40 px* the basis can reach the reference's profile to 0.89%/0.97%, but
not while the rest of the image is fitted. The profile-only optimum gets there
by using 13 of 29 layers and wrecking everything else: global MAE 1.90 -> 8.20,
frame 1.30 -> 7.48, centre 90 px 7.53 -> 35.16, between the curves 4.34 ->
24.86. So that bound is not a target. The lobe's pedestal comes from field,
exterior and flare layers that are pinned by their duties elsewhere, and what
remains in the interior is the price of a shared basis, not a fitting failure.
It is stated here rather than hidden because it is the honest limit of this
model: driving the interior to its bound would take a different decomposition,
not a better fit.

**Rejected on measurement: a lobe-localised field component.** The obvious way
to give the interior its own freedom is a soft radial gradient centred in each
lobe. It improves the global metrics -- MAE 1.9849 -> 1.9619, SSIM 0.9720 ->
0.9730 -- and makes the region it was added for *worse*: the right lobe's
coherent profile error goes 4.32% -> 4.86% and its ridge 4.16% -> 5.06%
(measured on the grid in use at the time; the ordering is what matters and it is
unambiguous). It is not in the model. This is the clearest case in the project of
a change that a global metric endorses and the measurement of the actual defect
rejects.

**Also rejected on measurement: replacing `field_grad`'s profile table.** Its
table has a pronounced non-monotonic dip, and the lobes sit at u = 0.47-0.82 of
its radius -- right across it -- so it was a plausible source of contour
structure. Replacing it with a monotone power law or a monotone table leaves the
coherent structure identical (0.763/0.531 counts against 0.763/0.533 shipped)
and costs real accuracy: MAE 2.0280 and 2.0552 against 1.9908. The dip had
already survived an evidence test on fit quality alone (residual 1.246 against
1.297 for the best power law and 1.780 for flat); it now survives one on
structure too.

**Rejected on measurement: the glow as gradients instead of blurred strokes.**
A filter's Gaussian is a three-pass box blur in both engines, departing from a
true Gaussian by 1.5-2.1 code values in coherent bands that follow the blurred
object -- which is exactly the shape a banding complaint would take. And the
replacement is in principle *exact* rather than approximate: the curves are lens
ellipses, so the iso-distance contours on the concave side are that ellipse
scaled, which is precisely what a radial gradient with the ellipse's own aspect
ratio paints, with the along-curve fade applied as a mask on the element (a mask
on a wrapping group isolates it and kills `mix-blend-mode`, exactly like
`clip-path`; verified in both engines). It was built and measured, and it
reconstructs the lobes *worse* than the blurred strokes do: 0.352 against 0.326.
The code has been removed rather than left in place unexercised, because this
project has already had one builder kind rot that way -- `arc_lens` referenced a
schema that no longer existed and would have crashed had anything used it. The
measurements are kept here instead, which is the part worth keeping.

**The gradient stop tolerance, and the wrong measure I first chose it with.**
The adaptive stop sampling was added while testing the interpolation hypothesis
above. With the hypothesis refuted it had to justify its bytes, and the first
attempt measured it against MAE: between 1 and 2 code values of tolerance the
file gives back 10.2 KB for 0.002 of MAE, so 2 looked free.

It is not free, because MAE is not sensitive to the thing a stop tolerance
controls. A piecewise-linear stop leaves a *contour ring*, coherent over
hundreds of pixels, and 0.15 counts of coherent ring is visible where 0.15
counts of grain is not. Measured properly -- each render differenced against one
at 0.15 counts, which has no rings, over the two lobes:

| tolerance | 0.35 | 0.70 | 1.00 | 2.00 | 4.00 |
|---|---|---|---|---|---|
| ring rms | 0.077 | 0.098 | 0.141 | 0.150 | 0.230 |
| worst ring | 1.33 | 1.33 | 1.67 | 3.00 | 4.33 |
| file (KB) | 130 | 104 | 94 | 83 | 77 |

Between 1 and 2 the rms barely moves and the *worst* ring doubles, 1.7 counts to
3.0, in lobes that sit at 8-35 counts. The shipped value is 1. Below it the file
grows much faster than the artifact shrinks.

**And the rings are mostly not the stops.** The same measurement bounds how much
of the visible contour structure stop density can account for at all: 0.14
counts rms. The rest is the genuine curvature of the overlapping smooth
gradients. Rendered in arc-aligned coordinates and stretched to +-1.5 counts,
the render shows several overlapping families of smooth contours -- one per
radial gradient centre -- where the reference at the same stretch shows
incoherent JPEG blocking. That is a real difference in *kind*, and it is why a
modest excess reads as strongly as it does: structure of the same amplitude is
buried under 0.7-0.9 counts of grain in the reference and is naked in the
render. It is not a reason to accept the excess, and not a reason to add grain.

**Where the excess actually is, and three ways of mismeasuring it.** Localised
in cross-curve distance on a grid where every along-curve average is taken over
the same 481 stations, the render's excess coherent structure sits entirely in
the 26 px strip beside the ridge: at sigma 3 it is 1.81x the reference's on the
left curve and 1.23x on the right, falling to 0.96x and 0.93x by sigma 12. From
40 px outwards -- the whole open lobe, which is what the complaint describes --
the render runs 0.68x to 1.04x, at or below the reference, and its *total*
cross-curve amplitude there is a third of the reference's. Cell by cell in
(distance x along-curve angle) the same thing: 0.9-2.7x in the ridge strip, and
0.03-0.7x everywhere beyond it, on both curves in every band.

Getting that localisation wrong is easy, and it was got wrong three times before
it was got right, each time in a way that inverted a conclusion:

* *Partial along-curve averages.* Accepting any sampling row with 60 of 481
  stations inside the region let rows averaged over short unrepresentative arc
  segments dominate: they put the reference's coherent amplitude at 0.508 counts
  and the render's at 0.764, an apparent 1.5x excess over the whole lobe, where
  on fully populated rows the same statistic gives 0.116 and 0.082 -- the render
  *below* the reference. Six rows out of 287 were carrying the conclusion. The
  region is now the frame interior split at the mirror axis, where all 481
  stations are fully inside.
* *Edge-biased smoothing.* A `mode="same"` convolution pads with zeros, so the
  nine rows nearest each end of the cross-curve run are meaningless. Trimming
  them removes the ridge strip, which is exactly where the excess is; that is
  how a per-band measurement came to read 0.32-0.87x and suggest the defect was
  one of *persistence* along the curve rather than amplitude. It is not: with
  edge-normalised smoothing the per-band and whole-arc figures agree to 6%.
* *Pooling the two regions.* One number for the lobe is dominated by the ridge
  strip, because that is where the amplitudes are, and reads as though the whole
  lobe were over-structured. `band_report` reports them separately.

## D20. The profile weighting's strength is now a parameter, chosen by measurement

Fixing the squared-weight bug in D15 changed the objective's *strength*, not
only its correctness, and that had to be re-decided rather than inherited.

The bug made the profile term's objective coefficient `1/(n^2 (L+floor)^4)`
where the comments described `1/(n (L+floor)^2)` -- a fourth-power law in
brightness instead of a square, which leaned far harder on the dim far-lobe
cells than the design said it did. Correcting it to the documented form, with
the floor it had inherited, made the lobe interior measurably *worse*. So the
strength of the shaping had been doing real work by accident.

Two parameters were therefore separated and both settled by measurement, on a
colour-only fit from a fixed set of shapes:

* **The visibility floor**, 0.012 (3 code values) as inherited. Lowering it to
  0.006 (1.53 counts, about the quantisation scale) improves the coherent
  profile error from 0.781 to 0.665 counts and the cell error from 6.3% to
  5.6%; 0.003, 0.0015 and 0.0 are all within noise of 0.006 (0.665-0.690). So
  0.006, and the guard against chasing sub-quantisation error is kept.
* **The brightness exponent** `p`, now explicit in
  `EMPHASIS["profile"]["exponent"]`: the coefficient is
  `1/(n (L+floor)^(2p))`, so p = 1 equalises relative error across cells and
  larger p pushes past it. p = 1 is best on every measure -- MAE 1.967 against
  1.998 (p 1.5) and 2.050 (p 2.0), ridge error 2.53%/3.70% against 3.23%/7.75%
  and 4.81%/10.45%, interior 3.41%/4.26% against 3.95%/4.44% and
  4.83%/5.20%. The correct objective is also the best one; the bug was not
  compensating for anything, and the earlier reading that it was came from
  comparing a re-fit against a baseline whose *shapes* had been tuned to the
  old objective.

It is a parameter rather than a constant because nothing in principle fixes it
at 1 -- it is a claim about visibility, and this artwork answers it.

## D21. The central streak is centred on the core, with a falloff per side

**Decision.** `flare_streak` sits on the flare centre and carries a separate
falloff and gain for its east half (`profile_e`, `east_gain`), both searched.
`flare_ray_e` goes back to being a broad wedge rather than a thin spoke.

**Evidence.** The streak row cannot be measured naively: the two curve ridges
cross it at dx -65.5 and +14.5 from the flare core, so a window at dx -75..-40
or +15..+40 is entirely inside a curve's core and reads the core, not the
streak. Every earlier reading of this streak's asymmetry was taken that way. With
the ridges masked (ridge distance > 30 px) the reference's thin-line residual
above a 21-px median envelope is

| dx | -210..-160 | -160..-110 | -110..-75 | -40..-15 | +40..+75 | +75..+110 | +110..+160 | +160..+210 |
|---|---|---|---|---|---|---|---|---|
| reference | 5.15 | 11.75 | 19.44 | 31.57 | 15.85 | 7.14 | 3.07 | 1.62 |
| before | 5.65 | 17.14 | 38.63 | 15.70 | 2.28 | 1.39 | 0.29 | 0.01 |

Both sides fall off from the core, the west more slowly than the east. The
shipped layer instead displaced a *symmetric* streak 58 px west of the core with
a 37 px e-folding, and that one substitution produced three separate errors: its
peak sat 58 px off the core (15.70 at dx -40..-15 where the reference has 31.57,
38.63 at -110..-75 where it has 19.44), its east end truncated at core+158, and
the east side ran 7x too faint inside the span and to nothing outside it, where
the reference still carries 1.6-3.1 counts out to +210. The bounds could not have
recovered it either: `profile` was capped at 0.3 of a 215 px half-length, so the
reachable e-folding stopped at 65 px against a measured 77-90.

The thin-component angular scan says the same thing from the other direction:
at 0 degrees (due east) the reference reads 5.99 counts and the render 0.83.

**Effect.** Thin-line rms error along the streak 9.42 -> 6.14 code values at the
starting parameters, before any search, for +0.005 of whole-image MAE.

**`flare_ray_e`.** The same scan finds no thin spoke at 48 degrees: -0.58 counts
in the reference against +2.02 in the render. What D14 measured at 45-60 degrees
was a maximum in the *total* angular profile, which a broad wedge produces and a
thin spoke does not. Iteration 3 made every ray thin while chasing the six
spokes that are real, and then the fit drove this one hard to cover broad energy
with a thin primitive -- which is what turned the flare into a visible starburst.
The broad angular profile confirms the mechanism: at 165-180 degrees the render
is 3.5-9.0 counts too *dark* broadly while its thin line there is 7.2 counts too
*bright*. The westward energy was in the wrong shape, not the wrong amount.

**Not changed.** The six thin spokes at 91, 111, 225, 248, 265 and 328 degrees
stay: they are in the reference's thin-component scan at 1.2-3.5 counts and are
not an invention. Their amplitudes are over-driven (111 degrees reads 7.13
against 1.71, 249 reads 4.32 against 1.60) and that is left to the fit, because
the over-drive is a consequence of the two errors above and not a separate one.

## D22. Iteration 3's model changes did not improve the reconstruction

**The measurement.** Rendered at 1024 px against `reference.png`, every state
iteration 3 produced is worse than the iteration-2 baseline:

| state | layers | MAE | SSIM | flare r<110 | worst channel |
|---|---|---|---|---|---|
| iteration 2 (committed) | 29 | **1.9411** | **0.9731** | **7.602** | **105** |
| iteration 3, flare rebuild | 33 | 1.9818 | 0.9723 | 8.600 | 108 |
| + `arc_glow1c` | 34 | 1.9899 | 0.9728 | 8.498 | 110 |
| + one shapes sweep | 34 | 1.9661 | 0.9726 | 8.239 | 112 |
| + the streak primitive and a flare sweep | 34 | 1.9794 | 0.9724 | 8.310 | 112 |

The regional and targeted numbers agree: the glow profile's rms relative error
goes 4.08% -> 4.59%, the cell figure 5.19% -> 6.02%, both lobes' MAE up, and on
the arc-masked streak measurement the thin-line error goes 4.98 -> 5.72 counts.
Only the frame band, the bright pixels and the interior corners improved.

This is recorded as a decision rather than left in a commit message because the
conclusion has to survive the iteration: a change is not an improvement because
it is newer or better argued, and the artwork that ships is the one that
measures best.

**The flare rebuild was already a regression before this iteration's work
started.** At 33 layers it rendered 1.9818 against 1.9411, with the flare's own
region 8.600 against 7.602 -- the region it was rebuilt to fix. Its individual
measurements were sound (the streak comb's satellites, the six thin spokes at
their measured angles); what went wrong was downstream of them.

**One cause is identified and fixed.** `flare_cells` masked the curve ridges by
13 px. The ridges cross the streak row 14.5 px east and 65.5 px west of the
flare centre and the curve's glow reaches far past that, so a third of the comb
cells were scoring curve glow and calling it the comb -- and the flare search
optimised toward it. The signature is unambiguous: with the margin at 13 the
search drove the streak's west side to 9.6/20.1/26.7 counts where the reference
has 5.2/11.8/19.4, and its east side down to 6.2 where the reference has 15.9,
which is the *opposite* of what the same lines measured with the ridges properly
masked ask for. The margin is now 30 px, which is what the measurement needs to
come out clean, and it drops 9 comb and 17 sector cells.

**The other cause is search, not model.** The baseline's parameters accumulated
many sweeps of every spec across iteration 2. Iteration 3 changed the objective
twice over (the squared-weight correction, then the floor and exponent of D20)
and the shapes have had one sweep against the result. A colour-only re-fit of
the *baseline* under the corrected objective already costs it 0.03 of MAE, which
is the size of the whole regression: the parameters are not converged for the
objective they are now being scored against.

**What is not claimed.** That the model changes are wrong. `arc_glow1c` raises
the ridge strip's achievable accuracy 3.4x/2.6x (D19) and the streak's per-side
falloff is measured with the ridges masked (D21); both are better-founded than
what they replace. What is claimed is only that the reconstruction they produce
has not yet been optimised well enough to beat the one they replace, and until
it is, it does not ship.

## D23. The stop rewrite was the regression; the filter region was the fix

**How the iteration-3 regression decomposed.** D22 recorded that every
iteration-3 state rendered worse than the iteration-2 baseline and named two
suspected causes, both in the parameters. Both were wrong about where most of it
was. Rendering the *same* iteration-2 parameters through each builder separates
the code from the fit, and the answer is a 2x2:

| gradient stops | filter region | MAE | SSIM | flare r<110 | file |
|---|---|---|---|---|---|
| measured stations, verbatim | frame bbox +-4 px | 1.9411 | 0.9731 | 7.602 | 72.3 KB |
| **measured stations, verbatim** | **scaled to the blur** | **1.9352** | **0.9734** | **7.602** | **72.2 KB** |
| PCHIP, adaptively resampled | frame bbox +-4 px | 1.9763 | 0.9721 | 7.693 | 79.7 KB |
| PCHIP, adaptively resampled | scaled to the blur | 1.9594 | 0.9725 | 7.693 | 79.6 KB |

So of the changes made to the builder during iteration 3, one was a genuine
improvement and the other a genuine regression, and pooling them hid both:

* **The filter region was wrong and its correction helps.** It had been clamped
  to the frame's bounding box plus 4 px *regardless of the blur width*, with a
  comment asserting that was lossless because filtering precedes clipping. A
  filter region clips the filter's SOURCE, so a sigma-76 haze was being built
  from a truncated source. Scaling the region to the blur's own padding is
  worth -0.0059 of MAE and +0.0003 of SSIM on identical parameters.
* **The adaptive PCHIP stops were a regression: +0.0242 of MAE, -0.0009 of
  SSIM and 7.4 KB.** They were added while testing whether stop interpolation
  caused the lobe banding, which it does not (D19), and then kept on the
  argument that a smooth interpolant represents the intended profile more
  faithfully than straight segments between knots.

**Why the smooth interpolant is the wrong choice here, not merely a costly one.**
The knots are not control points for a curve someone designed; for the tapers
and the field table they are a MEASUREMENT, station by station along each arc.
Linear interpolation between measured stations is the minimal assumption. A
monotone cubic through them asserts curvature in between that nothing measured
-- and the change shipped a smoothing pass with it, a 7-point window over the
measured alphas, which discards measured detail outright. The amplitudes were
then fitted against the linear reading and are correct for it. Both are
reverted; the machinery is removed rather than left unexercised, and this entry
is the record of what it cost.

**The consequence for the baseline.** Iteration 2's parameters, built with the
corrected filter region and the measured stations emitted verbatim, render at
**MAE 1.9352, SSIM 0.9734, flare 7.602, worst channel 105, 72.2 KB** -- better
than the iteration-2 commit on the global metrics, identical in the flare, and
slightly smaller, with no parameter changed. That is the baseline this iteration
proceeds from, and it is a *code* improvement: the previous numbers were held
back by a truncated filter source.

**What this says about the rest of the iteration-3 regression.** With 0.0183 of
the 0.0438 attributable to the builder, the remainder is the parameters -- and
they were searched against an objective that changed twice underneath them. It
does not establish that the model additions are wrong, and it does not establish
that they are right. They stay out until a search against the corrected
objective and the corrected builder puts them ahead of this baseline.

## D24. The central light's horizontal lines are three features, not one

**Evidence.** The reference carries three distinct horizontal lines through and
below the flare core. Their centres, from a shared-centre three-Gaussian fit and
cross-checked model-free against `L(y) - 0.5*[L(y-k) + L(y+k)]`, with every
window masked to more than 30 px from either curve ridge:

| line | dy from the core row | reach | shape |
|---|---|---|---|
| A | **-0.283 +- 0.037** | 300 px W, 240 px E | FWHM 4.64 +- 0.10 px |
| B | **+6.740 +- 0.055** | dies past abs(dx) 130 | short |
| C | **+19.329 +- 0.065** | 300 px W, 240 px E | faint, and NOT decaying from the core |

The masking is not a detail. The ridges cross the streak row 65.5 px west and
14.5 px east of the core, so the windows at dx +15..+40 and -75..-40 lie
entirely inside a curve's core: an unmasked measurement there reads the curve,
which is how earlier work came to describe this family as a west-displaced
symmetric streak (D21).

**Line A passes THROUGH the core, not below it.** Its centre is 0.28 px above
the stated core row, so the "prominent line below the bright point" of the
report is this streak; only B and C are below.

**Line C cannot be emitted from the core at all.** It rises from an inner
cut-off near abs(dx) 80, peaks at 5.6 counts around abs(dx) 110-170, then falls
-- reaching 240 px east and 300 px west. Neither an exponential (log-rms
0.27-0.36) nor a power law (0.30-0.40) fits it. Any primitive whose amplitude
decays monotonically outward is the wrong shape, whatever its parameters, so it
gets an explicit non-monotone knot table, which `profile_stops` emits verbatim.

**Refuted and therefore not built:** a line at dy +12 (an inverse-variance stack
of ten far bins reads 0.000 at +11.2 and 0.105 at +12.2, below 1 sigma -- the
earlier suggestion came from the 21-px median envelope overshooting in the
trough between B and C); slab-shaped cross-sections (a generalised Gaussian of
exponent 4 fits worse than Gaussian or Lorentzian in every bin); and the earlier
satellite positions +6.5 and +18.5 (+19.329 is 12 sigma from +18.5, which
matters for a 5-px feature).

**What the baseline had.** Three streak layers all at dy ~ 0, stacked on the
core row with sigma_y 3.56, 2.45 and 10.85 -- which is why the rendered line A
measures 9.6 px FWHM against 4.64, and why B and C were absent outright: line C
read -0.11 to +0.15 counts across 390 masked columns where the reference reads
3.0-4.8.

**A mapping error worth recording.** The measurement says the main streak's east
side follows a power law of index 2.10 -- meaning amplitude proportional to
abs(dx)^-2.1. The builder's `pow` profile emits `(1 - u)^k`, which is a
different function entirely, and substituting one for the other put 2-3x too
much light along the east side from abs(dx) 70 outward (12.4 counts at +70
against a reference 6.97). Both sides are now explicit tables of the measured
amplitudes, which is also the minimal assumption between measured points (D23).
The innermost east knot is held flat rather than extrapolated to a spike,
because the right curve's ridge masks abs(dx) < 40 there and a spike inward of
it would be invented, not measured.

**Four representations were built and measured.** The line amplitudes below are
the model-free row difference of `tools/line_report.py`, rms over the 14 masked
`dx` bins, against the reference:

| representation of line A | line A | line B | line C | total | MAE |
|---|---|---|---|---|---|
| baseline (no B, no C, one wide streak) | 6.38 | 10.53 | 3.08 | 20.00 | 1.9352 |
| east `(1-u)^2.10` | 8.93 | 7.18 | 1.44 | 17.55 | 1.9496 |
| both sides sparse measured tables | 4.84 | 7.40 | 1.40 | 13.64 | 1.9386 |
| **west exponential, east measured table** | **3.30** | 8.05 | 1.42 | **12.77** | 1.9367 |
| west dense log-interpolated table | 5.49 | 7.18 | 1.41 | 14.08 | 1.9401 |

Two of those are my own errors, and both were caught by measurement rather than
by argument:

* The measurement says the east side follows a power law of index 2.10, meaning
  amplitude proportional to `abs(dx)^-2.1`. The builder's `pow` profile emits
  `(1 - u)^k`. Substituting one for the other put 2-3x too much light along the
  east side from `abs(dx)` 70 outward -- 12.4 counts at +70 against a reference
  6.97 -- and made line A *worse* than the baseline that lacked two of the three
  lines entirely.
* A dense table log-interpolated between the measured points flattens the
  near-core profile, and then the fit cannot reach the peak: 18.11 counts at
  `dx` -36 against a reference 34.95. The reason is that 34.95 is a BIN MEAN over
  `abs(dx)` 17-36, a range across which the profile falls steeply, so it
  under-represents the peak and a table anchored on it is too flat. The
  exponential law's own curvature is the better reading of the same data.

**Shipped:** line A's west as the exponential law (e-folding 64.7 px), its east
as the measured table, line B as an exponential of e-folding 37.4 px at
dy +6.740, and line C as the non-monotone table at dy +19.329.

**What it costs and what it buys.** The line-structure error falls 36%, from
20.00 to 12.77, and line C goes from absent -- `-0.11` to `+0.15` counts across
390 masked columns where the reference reads 3.0-4.8 -- to within about a count
on both sides. Against that: whole-image MAE rises 0.0015 (0.08%), SSIM is
unchanged at 0.9734, the worst single-channel error *improves* from 105 to 104
and the fraction of pixels off by more than 2 improves from 35.80% to 35.66%,
while the flare region's own MAE rises 0.42 (7.6016 to 8.0178). That regional
cost is the open item: the bloom, halos and rays underneath the lines have not
been re-searched since the lines changed, and the flare geometry search is the
next step, not a reason to reject the decomposition.

## D25. Fitting a new flare component without discarding the validated colours

**The problem.** Introducing a layer needs a photometric fit, and a full re-fit
of every layer under the current objective measures *worse* than the colour
solution iteration 2 already has: same geometry, full re-fit, MAE 1.9480 against
1.9352. So a full re-fit would trade a validated solution for the objective's
own optimum and, worse, would hide whether the new layer helped -- the
comparison would confound the layer with the re-fit.

**The decision.** Fit only the layers the change touches, with
`FP.fit(free=...)`, and leave every other layer's colour exactly as it was
(`tools/fit_only.py` in the scratch tooling drives it; the same `free` mechanism
the optimiser uses per family). Every flare result in D24 is measured this way:
the eleven `flare_*` layers are free and the nineteen others are frozen at
iteration 2's values, so the reported change is the change the flare model made.

**Why this is not just convenience.** It is the same requirement as the
geometry-trial fix in this iteration's optimiser work: a comparison is only
about the thing being changed if everything else is held equal. A full re-fit on
each side of the comparison changes nineteen layers that the flare model has
nothing to do with.

**What it does not settle.** That the current objective's optimum is worse on
the unweighted metrics than iteration 2's is itself unexplained, and it is the
open question behind D22. Iteration 2's colours were fitted under the
squared-weight bug, so they minimise a quartic-weighted objective; that they
also give lower MAE and higher SSIM than the corrected objective's optimum is a
fact about this artwork that neither objective was designed to optimise. It is
recorded here as a thing to explain rather than a thing to exploit.

## D26. The diagonal rays: measured widths, and two angles that were wrong

**The brief's premise, tested.** The review asked why the "left-side rays look
blurry" and whether the right-side rays are missing detail, with the caution not
to assume the right side mirrors the left. Both questions are answered by
measurement, and the first one's premise turns out to be the wrong way round in
one respect and right in another.

`tools/ray_report.py` scores each ray by sampling an annulus around the flare
core, masking every sample within 30 px of a curve ridge -- the right ridge is
only 14.5 px east of the core, so an unmasked scan reads the curve, not the
flare -- and taking, at each radius, the peak of the excess over the surviving
angular island's own chord. `peak / FWHM` is then the hardness: the same
integrated light spread wider scores lower.

Against `reference.png` and the accepted baseline render:

| ray | theta | ref peak | ref FWHM | ref pk/FWHM | render peak | render FWHM | render pk/FWHM |
| --- | --- | --- | --- | --- | --- | --- | --- |
| upper-left | 113.6 deg | 8.08 cv | 10.6 px | 0.778 | 5.18 cv | 15.4 px | 0.325 |
| lower-left | 249.7 deg | 6.88 cv | 8.3 px | 0.836 | 0.87 cv | 4.0 px | 0.234 |
| upper-right | 45.6 deg | 2.37 cv | 3.9 px | 0.601 | 0.56 cv | 3.1 px | 0.180 |
| lower-right | 327.8 deg | 4.77 cv | 4.6 px | 1.135 | 2.11 cv | 6.5 px | 0.295 |

Every ray is softer than the reference by a factor of 2.4 to 3.9 on
`peak / FWHM`, and every ray is dimmer at its peak. So "too blurry" is right;
what is wrong is the implied remedy. The reconstruction is not missing
sharpening -- it is missing *concentration*. The upper-left ray carries 82% of
the reference's integrated energy (4045 against 4959 cv*px^2) in a cross-section
1.5x too wide, and the lower-left ray's light is in a broad flank pedestal
measuring 10.5% and 12.3% above the reference rather than in a ray at all.

**Two of the four angles were wrong.** The right-hand pair was first scanned at
32 and 310 degrees, inherited from an earlier pass. Within those windows the
reference's peak does not sit at the window centre: it sits at 45.6 and 327.8
degrees, and it holds those angles at every radius that clears the ridge mask
(the lower-right within +-1.5 deg over r = 60..100). That is what the report's
`ref angle` row is for, and it is why the row exists: a peak whose angle wanders
with radius is a local maximum of something else, and adding a ray element for
it would be fitting a feature that is not there. Re-centred on the measured
angles, both right-hand rays resolve cleanly, and the lower-right turns out to
be the hardest ray in the image.

**The right side is not a mirror of the left.** The left rays are 8-11 px wide
at peaks of 7-8 cv; the right rays are 4-5 px wide at peaks of 2.4-4.8 cv. A
symmetric four-ray construction -- the obvious thing to reach for -- would make
the right pair twice too wide and three times too bright, and the ray primitive
is deliberately one-sided for the same reason (see the comment at
`src/build_svg.py` around the `ray` branch).

**What was changed.** Only geometry, in `scratchpad/apply_rays.py`: each ray's
`rot` set to its measured angle, and its `height` and `blur` chosen together to
hit the measured FWHM through the primitive's own optics -- a slab of height h
blurred by sigma_b has sigma_eff^2 = sigma_b^2 + h^2/12, so the pair is
determined once the FWHM is fixed. The blur bound had to be lowered from 2.0 to
0.6 for these layers: a 3.9 px FWHM is not reachable with sigma_b >= 2, which
alone is already 4.7 px of FWHM. Rendered with the geometry changed and nothing
else, the measured widths land at 9.5, 9.3, 4.7 and 4.9 px against the
reference's 10.6, 8.3, 3.9 and 4.6.

**Amplitudes are not set here.** The same rendering overshoots every peak
(13.6, 14.6, 12.9 and 6.1 cv against 8.1, 6.9, 2.4 and 4.8), because
concentrating an unchanged opacity into a narrower slab raises the peak. That is
a photometric quantity and it belongs to the fitter, fitted after the geometry
is right. Doing it the other way round -- reducing opacity until the too-wide
ray stops being conspicuous -- is what the review warned against, and it would
have left the structure wrong while making the error smaller.

**Why global MAE cannot judge any of this.** The two renders that differ by 0.04
of whole-image MAE are bit-identical within 334 px of the flare core, so that
difference is generated entirely outside this region and says nothing about it.
These changes are a redistribution at nearly constant integrated light, which is
close to invisible to a mean absolute error over any region large enough to
contain the ray. `tools/ray_report.py` is the acceptance instrument for them.

## D27. Which earlier conclusions the isolation bug could have touched

**The bug.** `tools/isolate.py` recovered a dropped group's contribution as
`f = (ref - M) / (1 - M)`. That is exact only when every layer composited
*after* the dropped group is screen-blended. This stack ends with two
normal-blended frame layers, so wherever they have coverage both `ref` and `M`
have already been through an affine map and dividing them as if they had not
distorts the result. The fix composes the trailing layers into one affine map
in `u = 1 - out` and inverts it, and rejects the two orderings the algebra
cannot express rather than approximating them.

**The question the review asked** is which earlier conclusions were reached
through the broken formula and therefore need re-deriving. The answer is
bounded exactly, because the corrected formula reduces to the old one
identically wherever the trailing normal layers have zero coverage: the error's
support is precisely the set of pixels the frame covers, and nothing else.

**Measured support.** Rendering `frame_base` and `frame_rim` as basis layers and
compositing their coverage:

* 23,781 of 1,048,576 pixels, 2.27% of the canvas, have any frame coverage;
* every one of them lies within 106 px of a canvas edge;
* coverage within 340 px of the flare core is **exactly zero** -- not small,
  zero -- at every radius tested (110, 160, 200, 260, 340 px).

**The classification.**

*Unaffected, no re-derivation needed.* Everything derived from isolating the
flare: D11's correction, D14's bound on the flare's extent, D21's streak comb
and spokes, D24's three-line decomposition, D26's rays, and sections 5a and 5b
of `METHOD.md`. The flare and every measurement made from it sit in a region
with zero frame coverage, where the two formulas agree to the last bit. This is
not a judgement that the error was small there; it is that there was no error
there.

*Affected in principle.* Isolations of the arc-glow and field groups, whose
footprints run out to the rim. Within the two banding boxes
`(96,96)-(512,930)` and `(512,96)-(928,930)` the frame covers 232 and 391
pixels, 0.09% of their combined area, and at those pixels it is fully opaque --
so where it bites, it bites hard.

*What that changes in practice.* Nothing that was concluded. The banding
analysis of D19 compares rendered images against the reference directly and
never goes through the isolation at all, and the arc-glow amplitudes come from
the photometric fit, which composites forwards and has no such inverse. No
shipped parameter traces back to an isolation in the affected 2.27%.

**Why it was still worth fixing.** The next measurement that wants the
arc-glow's own contribution near the rim -- the paleness in the 16 px annulus
flanking each curve is exactly that kind of question -- would have been wrong,
and wrong in a way that looks plausible. A tool that silently returns a
distorted answer outside its domain is worse than one that refuses, which is
why the two inexpressible orderings now raise `UnsupportedIsolation` instead of
returning a number.

## D28. The colour saturation: the finding is real, the global reading is not

**What was asked.** The review's secondary objective was overall colour
saturation -- the reconstruction reads paler than the reference.

**The global reading is refuted.** Over the whole canvas the reconstruction's
mean chroma is 1.2% *above* the reference's, not below it. A global saturation
boost would therefore move the majority of the image away from the reference to
fix a minority of it. Three related readings fail the same way and are recorded
so they are not re-proposed: the flare is not washed out (+0.4% chroma); the
dark field is not too pale but too *pure*, missing 21-38% of the white pedestal
the reference has there; and the colour cone is not the limitation, since
matching the reference exactly would violate its R <= G <= B constraint by at
most 1.2 counts of blue.

**Where the paleness actually is.** `tools/chroma_report.py` bins every interior
pixel by its distance from the nearest curve ridge, excluding the flare and the
frame. Against the accepted baseline render:

| ridge distance | dR | dG | dB | d chroma | d hue |
| --- | --- | --- | --- | --- | --- |
| 0-4 px | +1.73 | -5.14 | -4.43 | **-6.15** | +1.5 deg |
| 4-8 px | +6.73 | -10.11 | -8.43 | **-15.16** | +3.3 deg |
| 8-12 px | +5.29 | -5.18 | -4.18 | **-9.47** | +2.4 deg |
| 12-16 px | +2.72 | -0.18 | +0.85 | -1.87 | +1.6 deg |
| 16-24 px | -0.14 | -0.06 | +0.65 | +0.80 | +0.8 deg |
| 24-40 px | -0.61 | +0.67 | +1.17 | +1.78 | +0.2 deg |
| 40-70 px | -0.94 | -0.76 | -0.25 | +0.69 | +0.8 deg |

The effect is confined to the 16 px band hugging each ridge and it peaks at 4-8
px out, where chroma is 15.2 counts short of the reference's 68.85 -- 22% -- and
red is 6.73 counts high against a reference value of 17.08, which is 39% too
much red. Beyond 16 px the sign reverses and the render is very slightly *more*
chromatic than the reference, which is where the +1.2% whole-canvas figure comes
from. Both facts are true at once; only the second one is visible in an average.

**What that means mechanically.** Too much red at unchanged luminance is too
much *white* in the mix, because white is the only cone primary with a red
component. So the band wants its light delivered as cyan where the
reconstruction delivers it as white plus blue.

**Why the fit cannot simply fix it.** A layer has one colour triple for its
whole footprint, and no layer's footprint is this band: the narrowest arc glow
is much wider than 16 px, so any colour change made for the band is also made
30, 50 and 70 px out, where the render is already right or slightly over. This
is a basis limitation, not a fitting failure -- which is consistent with the
cone measurement above, since the colour the band needs is inside the cone and
simply cannot be delivered there alone.

**Decision: measured, located, not fixed in this iteration.** The change it
calls for is a new ridge-hugging glow layer roughly 6 px in effective sigma,
carrying cyan. The nearest thing tried, `arc_glow1c` at sigma_eff ~10 px,
measured worse on the whole-image metrics when it was tried against the
iteration-3 state (MAE 1.9899) and was not shipped. Re-testing it against the
reconciled baseline, with `tools/chroma_report.py` as the acceptance instrument
rather than whole-image MAE, is the next step and is not one this iteration
takes. Recording the measurement without acting on it is deliberate: the
alternative on offer was a global saturation change that the first paragraph
shows to be wrong, and a wrong fix that improves the average is worse than a
located problem that is still open.

## D29. Each strong ray is a sharp spike on a broad fan, and what that cost

**The decision.** Ship the measured flare: the three horizontal lines of D24,
the four diagonal rays at the measured angles, widths and amplitudes of D26, and
two new broad flank layers. This is accepted knowing it raises whole-image MAE
from 1.9352 to 1.9577 and the mean absolute error inside r = 110 px of the flare
core from 6.372 to 7.191.

**How the flanks were found, which is the substance of this entry.** Setting the
rays to their measured widths cost 3.2 code values of error over r = 20..80 px.
Mapping that error by angle showed it was not spread around the flare at all: it
sat at theta 210..260, peaking at 13.5 cv at theta 225, exactly where the old
lower-left ray -- 30 px tall with a 1.6x spread -- had been laying down broad
light that the 8.3 px measured ray does not.

So the reference carries two things in the lower left, not one: a narrow spike
at theta 249.7 and a broad fan across theta 210..260. The obvious alternative,
letting the bloom make up the difference, was tried and fails for a structural
reason: the bloom layers are radially symmetric, so raising them adds light at
every angle while the deficit is at four angles out of twenty-four. Measured --
freeing the whole bloom with the rays frozen recovers r 0..20 (8.83 against the
baseline's 9.21, better than before the change) and leaves r 20..45 at 11.61
against 8.36.

With the lower-left flank in place the same analysis found the same thing again
on the upper left, at theta 105..135, and it was given the same treatment. That
the pattern appeared twice, independently, from the same measurement, is what
makes it a decomposition rather than a patch.

**Amplitudes are measured, not fitted, for rays and flanks alike.** After
fitting the corrected geometry the photometric fit left the lower-left and
upper-right rays 2.3 and 2.4 times too bright and the lower-right 3.9 times too
dim, which is not a defect in the fit: a ray is a few code values over a few
hundred pixels and a weighted whole-image objective has almost no reason to
place it. So each ray's amplitude is driven to its measured peak and each
flank's to the mean signed error over its own sector, and both are then held
fixed while the bloom is fitted around them.

**What it bought, measured.**

The right-hand column is this change alone; D31 then widens the bloom, which
improves the whole-image and flare-region figures further, to 1.9538 and 7.114.

| | baseline | this change |
| --- | --- | --- |
| ray hardness, mean err in `peak/FWHM` | 0.579 | **0.076** |
| horizontal line error (D24) | 20.00 | **12.77** |
| broad angular structure, r 45-80 | 3.02 cv | **2.48 cv** |
| pixels off by more than 2 | 35.80% | **35.72%** |
| worst single channel | 105 | **104** |
| SSIM | 0.97340 | 0.97334 |
| whole-image MAE | **1.9352** | 1.9577 |
| flare r<110 MAE | **6.372** | 7.191 |

**What it cost, located.** The flare-region cost is not evenly spread. Splitting
r < 110 by distance from a curve ridge: within 30 px of a ridge the error rises
by 1.167 (on 22,495 px, where the baseline already stands at 8.307 because of
the colour-basis error of D28); further than 30 px from a ridge -- the flare's
own territory -- it rises by 0.315. Broad angular structure at r 45..80 improves
and at r 20..45 worsens.

**Why this is the right trade, and the honest case against it.** The case for is
that the reference's flare is a spoked starburst and the previous
reconstruction's was a featureless blob: rendered crops at 3x, stretched and
unstretched, show four diagonal rays present in the reference and in the new
render and absent in the old one. The review asked for the reconstruction to be
visibly closer to the reference in the central flare, and explicitly asked that
success not be defined as a metric improving. The case against is that 0.022 of
MAE and 0.82 of flare-region MAE are real error, not measurement artefacts, and
that a reader who cares only about the aggregate is worse off. Both are true.
The structure is what a reader looking at the image sees, so the structure wins;
the cost is stated in `README.md` rather than left in the numbers for someone
else to find.

**What is still open.** The remaining deficit over r 20..45 is concentrated at
theta 165 (-11.5 cv, against the baseline's -6.2) and at theta 105..135 (-3.5),
and it is a radial-distribution error rather than an amplitude one: sweeping the
flanks' `peak_at` and `len` improves it to a point and then stops, because the
mean signed error over each flank's sector is already within 0.35 cv of zero.
Inside r = 50 the reference's lower-left structure sits at theta 228, not at the
ray's 249.7, which suggests the fan and the spike do not share an axis. That is
the next measurement, not this iteration's.

## D30. Two correctness bugs that made earlier search results untrustworthy

Both were found by review rather than by a failing test, and both had been
silently corrupting comparisons for an iteration. They are recorded together
because they share a shape: each made two things look comparable that were not.

**The geometry trial inherited a colour fit it did not earn.**
`tools/optimize.py`'s sweep evaluated a geometry trial against a baseline whose
inner colour optimisation had been done for a *different* family of free
parameters. So a trial could win because its baseline was handicapped, not
because its geometry was better, and every accepted geometry move in the
previous iteration is suspect for that reason. The fix re-bases whenever the
free-parameter signature changes:

    last_free = object()          # a sentinel no family signature can equal
    for sp in specs:
        free = obj.families(params, sp["affects"])
        sig = "all" if free is None else tuple(free)
        if sig != last_free:
            best_sse, best_mae, Kb = obj.evaluate(params, free=free)
            obj.K = Kb
            last_free = sig

and the trial itself is scored with the same `free`. The regression check
spies on `Objective.evaluate` and asserts the baseline was re-established for
each distinct free-set: with two searched families it sees 7 calls, 3 distinct
free-sets, and both families re-baselined.

**The profile weight cache collided on the luminance sum.**
`tools/fit_photometry.py` keyed `_PROFILE_CACHE` on the target's luminance
*sum*, so two entirely different targets with the same total light shared a
cached weight map. The fix keys on the contents:

    lum_c = np.ascontiguousarray(lum)
    key = (hashlib.blake2b(lum_c.view(np.uint8), digest_size=16).hexdigest(),
           lum_c.shape, lum_c.dtype.str, fl, fl_floor, fl_w, pp, fl_p)

The check moves a bright patch between cells while holding `lum.sum()` fixed and
asserts the weights change, and separately that an identical target still hits
the cache -- a hash that never collides but also never hits would be its own bug.

**What was re-run because of them.** The flare geometry search, against the
corrected objective and with the corrected comb margin. Its result is itself
worth recording: it improved the weighted objective it was minimising (1.8751 to
1.8617) while making unweighted whole-image MAE *worse* (1.9401 to 1.9461) and
leaving the flare region essentially unchanged (6.690 to 6.676). So the search
is now correct and its output was still not shipped -- which is the same open
question as D25's, and the reason the flare's structure in this iteration comes
from measurement rather than from search.

**Why no test caught either.** Both bugs produce plausible numbers. A cache
collision returns a weight map, a mis-baselined trial returns an error, and
neither is out of range. The checks that now exist assert a *relationship*
between two runs rather than a property of one, which is the only kind of check
that could have caught them, and is worth preferring wherever a result is a
comparison.

## D31. The core's falloff: a third of the gap, and where the rest of it goes

**The finding.** `tools/core_report.py` reads the flare core two ways the curve
ridges do not erase -- a vertical cut down the core's own column and an
azimuthal mean over the west sector -- and reports the falloff in three radial
bands rather than one number, because the core is wrong in two directions at
once. Against the reference's 3.81 / 3.80 / 3.12 cv/px over r = 1-8, 8-16 and
16-28, the reconstruction read 2.48 / 3.96 / 4.36: too flat where the reference
is steep, and too steep where the reference is shallow. In signed terms it was
12.7 cv too bright 9 px west of the core and 4.3 too dim at 29 px. The light was
sitting in a ring instead of reaching outward, which is what "the flare centre
is too blurry" turns out to mean here.

**What it is not.** It is not a rasterisation or a filter effect, and sharpening
the rendered image -- which the review explicitly warned against -- would not
touch it. It is the inner bloom's radial profile: `flare_halo` had an
exponential e-folding of 14.7 px where the reference wants a longer one.

**The sweep.** `flare_halo`'s exponential scale, with the bloom refitted each
time and the rays and flanks held at their measured values:

| scale | e-folding | MAE | flare r<110 | flare r<20 | falloff r 1-8 / 8-16 / 16-28 |
| --- | --- | --- | --- | --- | --- |
| 0.159 (was) | 14.7 px | 1.9577 | 7.191 | 9.469 | 2.48 / 3.96 / 4.36 |
| 0.20 | 18.5 px | **1.9538** | **7.114** | 8.732 | 2.61 / 3.91 / 4.20 |
| **0.23 (shipped)** | **21.3 px** | 1.9576 | 7.225 | 8.037 | **2.90 / 3.93 / 4.12** |
| 0.26 | 24.0 px | 1.9624 | 7.347 | **7.935** | 3.09 / 3.96 / 4.00 |
| reference | | | | | 3.81 / 3.80 / 3.12 |

**The choice was made by the banding regression check, not by the table
above.** On the flare's own numbers 0.23 was the better answer: it closes a
third of the falloff gap against 0.20's tenth, takes the innermost 20 px of the
flare from 9.469 to 8.037 (the previous iteration's own figure there was 9.207),
and costs nothing on whole-image MAE, 1.9576 against 1.9577. It was written up
and about to ship. Then the check failed.

The along-curve-averaged profile error in the 26 px strip beside each ridge
climbs monotonically with the bloom's width, because a wider bloom puts light
where the curve glow's own profile is being measured:

| scale | ridge strip profile error | ceiling |
| --- | --- | --- |
| 0.159 (was) | 4.72% | 5.00% |
| **0.20 (shipped)** | **4.87%** | 5.00% |
| 0.23 | 5.00% | 5.00% -- fails |
| 0.26 | 5.06% | 5.00% -- fails |

That ceiling was set in this iteration, just above the then-shipped value, for
exactly this purpose: the banding beside the curves is the regression the review
named as sensitive, and a budget that can be spent by any change that happens to
improve some other number is not a budget. So 0.20 is shipped -- it is also the
Pareto point for the aggregates, beating the previous value on whole-image MAE,
on flare-region MAE, on pixels off by more than 2 and on the core at once -- and
0.23 is recorded here as measured, better on the flare, and blocked.

The honest reading is that the core's sharpness and the ridge strip's profile
are competing for the same light, and this iteration did not find a way to give
the core more without taking it from there. Raising the ceiling to fit the
result would have been the wrong way to resolve that.

**What is still wrong.** Even at 0.26 the inner falloff is 3.09 against 3.81, so
no single e-folding fixes this: the reference's core is very nearly *linear* in
r out to 28 px -- its gradient is 3.81, 3.80, 3.12 across the three bands, which
is a straight line, not an exponential, whose gradient would fall with the
level. Expressing that needs a measured profile table for the bloom, derived
from an isolation the way D24 derived the horizontal lines. That is the next
step and this iteration does not take it.

## D32. An independent measurement disagreed, and what settled it

A parallel measurement pass, run against the reference alone, returned a flat
contradiction of D26's upper-right ray: it reported "no radial spoke anywhere
between theta +6 and +40", and that "earlier reports of broad maxima at 45-60
deg are the right curve's glow truncated by the arc mask".

**The objection is methodologically serious**, which is why it was tested rather
than argued with. `tools/ray_report.py` reads a ray as the peak of the excess
over a straight chord across the surviving angular island. A straight chord
across an island whose background is *curved* leaves a residual that peaks in
the middle -- a ray that is not there. That failure mode is worst exactly where
the objection was raised: on the right, where the ridge mask leaves the island
narrow and the curve's own glow steeply curved.

**The test.** An angular high-pass: subtract from each annulus a moving average
24 px of arc wide, much wider than a ray and much narrower than the island. That
removes a smooth background of *any* curvature and keeps only narrow structure.
A fitted quadratic baseline was tried first and rejected as the wrong
instrument -- extrapolated across the core it is badly conditioned and inflated
every excess, the upper-right by 6.9x.

Under the high-pass, the reference carries, in counts, averaged over r = 50-100:

| ray | reference | iteration 2 | shipped |
| --- | --- | --- | --- |
| upper-left 113.6 | 4.50 | 2.21 | 5.93 |
| lower-left 249.7 | 4.73 | **0.59** | 5.08 |
| upper-right 45.6 | **3.92** | 2.79 | 4.29 |
| lower-right 327.8 | 5.52 | 2.54 | 5.50 |

So the upper-right axis carries 3.92 counts of genuinely narrow structure, and
the objection is refuted on its own terms. It is also not quite a
contradiction: "no spoke between +6 and +40 degrees" and a ray at 45.6 are both
true, and only the sentence extending that to 45-60 was wrong. The same table
settles the lower-left independently -- 0.59 counts in iteration 2 against the
reference's 4.73 is the missing ray, measured by an instrument with no chord in
it at all.

**What the objection was right about.** It reported the lower-right ray
terminating at r ~ 155 where the reference reaches r ~ 205. Checked with the
same filter out to r = 230, both right-hand rays were far too short: the
reference holds 2-3.6 counts at theta 327.8 out to r = 170 and 1-2.8 counts at
theta 45.6 out to r = 230, where the shipped model had died by r = 110. Their
lengths are now 185 and 215 px with the longitudinal peak moved in to match.
Measured, this is free -- MAE 1.9538 to 1.9537, flare region 7.114 to 7.115 --
because it is structure in a region a mean absolute error barely weights, which
is the whole reason the diagnostic exists.

**Widths are now calibrated closed-loop too.** The slab formula sets the width
the *layer* is built to; the width the *composite* then measures is different,
because the excess is read against a background the other layers also shape.
Measured, the rendered FWHM came out 14% narrow on the upper left and 5% wide on
the lower left. Feeding that back -- building to 12.3 and 7.9 px to land on 10.6
and 8.3 -- puts the lower-left and lower-right FWHM exactly on the reference and
takes the mean hardness error from 0.049 to **0.037**, for 0.001 of MAE.

**Still open.** The upper-left's high-pass amplitude is 5.93 against the
reference's 4.50 -- 32% too much narrow light -- while its chord-excess peak
matches to 0.4%. The two measures disagree because the ray and its flank trade
against each other and only their sum is pinned. Balancing them needs the
flank's own amplitude measured against the high-pass rather than against the
sector's mean signed error, which is a change to the instrument, not to the
artwork.

**The general point.** The disagreement was resolved by building a third
instrument whose failure modes do not overlap either of the first two, not by
weighing the two reports against each other. Both original measurements survive
in the record, including the one that was wrong, because which of them was wrong
was not obvious in advance and the reasoning that settled it is more reusable
than the answer.

## D33. The comb was invisible to every shape search, and other infrastructure

Nine review findings, each confirmed against the code before being changed. Two
of them invalidate earlier results and so are recorded in full; the rest are
listed with what they broke.

**The fitting cells did not survive subsampling.** `tools/regions.py` builds its
cells on whatever grid the caller passes, and the optimiser passes a subsampled
one -- at stride 3 a cell covers a ninth of the samples it covers at full
resolution. The minimum population was a fixed 60 pixels. Measured:

| stride | comb cells | where that stride is used |
| --- | --- | --- |
| 1 | 51 | nothing |
| 2 | 29 | `fit_photometry --stride 2` |
| 3 | **0** | `--spec shapes`, twice |
| 4 | **0** | `--spec tapers`, `geometry`, `field` |

So every shape, taper, geometry and field search in the documented cycle was
blind to the horizontal comb -- not weighting it lightly, unable to see it --
and the comb is the sharpest structure in the image and the thing the cell grid
exists to expose. Thresholds are now areas in reference space, converted to a
count for the grid in hand, with a separate statistical floor of four samples.
Comb cells by stride are now 51 / 53 / 49 / 45.

**What that invalidated, classified.** *Unaffected:* everything in this
iteration and the last that came from direct measurement rather than search --
the three lines, the four rays, the flanks, the bloom e-folding sweep. Those
never consulted the objective. *Materially affected:* the flare geometry search
of D30, which is the one search that ran on flare shapes; its result was already
rejected on measurement and is not shipped, so nothing built on it. *Partially
affected:* every photometric fit, which ran at stride 2 and so saw 29 of 51 comb
cells. Re-running the flare fit with the comb fully visible was the first thing
tried in this iteration and it made line B **worse** (rms 8.13 -> 9.34), which is
what established that line B's deficit was a model error and not an amplitude
one -- see D35.

**Coordinate refinement never refined.** `while moved` in `tools/optimize.py`
exited the instant a pass failed, so the `step /= 2.2` below it was dead code: a
parameter whose optimum lay between v0 and v0 + step was left where it started.
The regression check puts the optimum at +0.45 of one step, where +-1.0 are both
worse; before the fix the search stayed at 0, after it lands at 0.4545 having
actually proposed sub-step values. Fine flare geometry is exactly the case that
needed it.

**The rest.** A flare-anchored layer that pinned one coordinate and inherited the
other was dropped from the dependency set (the rule wanted *either* missing, not
both) and so was scored at a stale position. `tools/measure_flare.py` could not
be told from a stale one: the converged path returned before saving and the
exhausted path saved a state it had never rendered; both now end in a
verification pass that re-renders from the file on disk. The documented full
cycle stopped before validation, the regression checks and the README, so no
single command defined a reviewable state -- `tools/publish.sh` is now that
command, and it ends by checking that `src/params.json` rebuilds
`reconstruction.svg` byte for byte. The README published a flare MAE of 6.37
against an actual 7.13 because `out/diagnostics.json` had gone an entire
iteration without regeneration, so the freshness guard now covers every
generated input and refuses. Chromium discovery was a single hard-coded
Playwright path, which silently narrowed cross-engine validation to one
machine's layout. The regression gate imported `resvg_py` itself and aborted
with a bare `ImportError` rather than naming the documented dependency. And an
`all` sweep searched eight paths twice because `layer_specs` and `field_specs`
both emit a radial layer's `cx`/`cy`; they are merged rather than one dropped,
since one relocates and the other refines -- which is only sufficient because
the step schedule now actually refines.

## D34. The ray high-pass was reading the mask edge, not the ray

**What was wrong.** D32 introduced an angular high-pass to decide whether a
narrow ray exists, on the argument that a straight chord across a curved island
manufactures a peak. That argument stands. The implementation did not: it
subtracted a 24 px moving AVERAGE, which is unbiased only where the background
is flat. Against a sloped background it leaves a residual proportional to the
slope, and the steepest slopes in this image are at the edge of the ridge mask,
where the window is also truncated.

**Measured.** At r = 70 on the upper-right axis the boxcar reads 4.67 code
values where a local LINEAR fit over the same samples reads 0.06 -- a factor of
78. The affected radii are r <= 82 at theta 45.6 and r <= 65 at theta 327.8,
four of the eleven radii the report scans.

**What it invalidated.** D32's conclusion that the reference's upper-right ray
"holds 1-2.8 counts out to r = 230", and the lengthening of `flare_ray_e` from
105 to 215 px that followed from it. With an unbiased statistic and a null
matched to the reference's JPEG blocking -- which is real and large, a
column-difference ratio of 2.57 inside the flare box against 1.05 for the render
-- that ray ends at **r = 145 +- 15**. The lower-right ray's extent is
confirmed: r = 170 +- 10, against the 185 px the model carries.

**The fix.** `thin_amplitude` now removes a local linear fit rather than a local
mean, and REFUSES any radius whose ray axis lies within 12 px of arc of the mask
edge, because there the window cannot be centred and no filter rescues it. The
refusals are visible in the report as gaps, which is the point: a number that
cannot be measured should be absent rather than wrong.

**The reference's values change accordingly**, and the earlier ones in D32
should be read as superseded: on the four axes the high-pass now reads 5.69 /
6.07 / 2.62 / 5.48 code values where the boxcar read 4.50 / 4.73 / 3.92 / 5.52.
The conclusions those numbers supported -- that all four rays are real, and that
iteration 2's lower-left axis was empty -- are unchanged, because they never
depended on radii near the mask edge.

**The general lesson, which is the same one as D32's.** A filter is a claim
about the background it removes. The boxcar's claim is "locally flat", and it
was applied exactly where that is least true. Verifying the ray's existence with
a second instrument was right; it needed verifying that the second instrument
was not itself reading an artefact.

## D35. Line B was a model error that fitting could only make worse

**The symptom.** Of the three horizontal lines below the core, line B rendered
1.6 code values where the reference has 24.6 -- the worst structural deficit in
the flare, and the one the review named. The obvious reading was that its
amplitude was too low.

**That reading is refuted, twice over.** The photometric fit, re-run with the
comb cells now visible to it for the first time (D33), made line B *worse*: rms
8.13 -> 9.34, and it moved the layer's colour DOWN, from 130 to 92 in blue. An
objective given more of the relevant evidence chose to dim the line further.

Why becomes clear from the layer's own basis. Rendering `flare_spike` alone and
normalising both it and the reference at |dx| = 50:

| |dx| | -190 | -120 | -95 | -30 | +70 | +95 | +120 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| reference | 0.04 | 0.01 | 0.20 | 0.91 | 0.50 | 0.27 | -0.03 |
| basis | 0.00 | 0.09 | 0.26 | **1.87** | 0.56 | 0.24 | 0.09 |

The tails agree to 0.05. The near-core point does not: the exponential is twice
too peaked. So the fit faced a choice between matching the peak and matching the
tails, and dimming the whole layer was its least-bad compromise. No amplitude
could have been right.

**What the reference actually has**, measured without assuming any of the
previous pass's values:

* all three lines sit 1.0-1.6 px HIGHER than the render put them -- rows 512.4,
  519.7 and 531.8 against rendered basis rows 513.50, 520.70 and 533.25. The
  -0.28 px offset an earlier pass reported for line A was an artefact of taking
  `FLARE_CORE`'s y as the centroid of a SATURATED core, which the one-sided comb
  beneath drags downward; line A in fact coincides with the reference's
  brightest row to within 0.1 px.
* line B is the NARROWEST of the three (FWHM 2.1-2.7 px), where the model made
  it 2.0 px of sigma with a lower bound of 1.3 -- the measured width was not
  reachable inside the layer's own bounds.
* line B is the WHITEST of the three, where the model made it the bluest.
* the comb is strictly one-sided. The block-immune arch depth is 0.06 +- 0.15
  code values at dy -19.0 against +1.88 +- 0.15 at dy +19.0: not "3-6x weaker
  above", but no upper line at all.
* JPEG blocking is refuted as the explanation for lines A and B by a factor of
  100-400: the block-edge signature in this filter is 0.08 cv/row against 19-216
  cv*px for line A.

**The change and its effect.** Rows corrected, line B narrowed to sigma 0.4 with
its bound lowered to 0.3, re-pointed at the measured white and raised 3.5x, and
line A's falloff shortened from 64.7 to 54.4 px of e-folding. Measured against
the reference, the three lines' rms errors go

| | line A | line B | line C | total |
| --- | --- | --- | --- | --- |
| before | 3.41 | 8.13 | 1.09 | 12.63 |
| after | **3.05** | **1.80** | **1.05** | **5.90** |

a 53% reduction, and whole-image MAE improves at the same time, 1.9547 ->
1.9521. That combination is worth noting because it is rare here: most of this
iteration's structural gains cost error elsewhere, and this one did not, which
is what a genuine model error looks like when it is fixed rather than traded
against.

## D36. The west is two lobes with a gap, and the wedge is one parameter

**The review's claim, tested.** "The reference does NOT contain the current broad
triangular light region on the left." Half right, and the half it gets wrong
matters: at r = 130-165 the reference DOES carry a broad westward fan spanning
theta 141..223 and the render supplies it correctly, agreeing to within 3.7 code
values per 6-degree bin at r = 100-130. Deleting or dimming that layer would
open a 5-9 cv hole. The false wedge is confined to r < 60.

**What is actually wrong.** At r = 34..46 the reference's west light is not a
plateau. It has a bright due-west arm, a broad upper-left flank over theta
104..136 with a hard outer edge, a broad lower-left flank peaking at 226..232,
and two genuine MINIMA between them at theta ~148 and ~199..215. The render
fills both minima -- +8.6 and +10.4 cv at theta 145 and 151, +10.5 and +9.1 at
205 and 211 -- while being 1-3 cv DIM in the upper-left lobe itself.
`tools/wedge_report.py` scores this as the angular modulation over 19 cleared
bins, which is the right statistic: whole-image MAE moves the WRONG WAY when it
is fixed.

**One parameter, found by elimination.** Splitting the candidate change into its
parts and measuring each alone:

| change | wedge RMS | banding ridge |
| --- | --- | --- |
| none | 5.53 | 4.96 |
| flanks re-aimed and re-scaled only | 6.12 | 4.96 |
| flanks + west arm narrowed | 4.51 | 5.03 |
| `flare_ray_d` alone | **3.84** | 5.79 |

So the wedge is `flare_ray_d` and nothing else -- and every way of fixing it by
geometry alone trips the banding check, because the layer is a trapezoid 42 px
wide AT THE CORE whose angular half-width is 46.6 degrees at r = 40 where the
reference wants 34-37, and shrinking or relocating its near end puts that end on
the left curve ridge.

**The primitive could not express the shape.** The ray's longitudinal gradient
is already at 0.62 of peak by half of `peak_at`, so a fan the reference shows to
be zero inside r ~ 60 was unreachable: every variant that removed the near
contribution did so by moving the whole element outward. An `onset` parameter --
the fraction of `len` over which the ray is dark before it begins -- makes it
expressible. With onset 0.24, peak_at 0.45, len 190 and the near end left WIDE
at height 30, the wedge RMS falls to 3.84, the flare-region MAE falls from 7.09
to 6.97, and the banding ridge figure is 4.95, inside its ceiling. The near end
has to stay wide: narrowing it concentrates light at the ridge and the same
check rejects it (5.13 to 7.44 across the variants tried).

**Alternatives rejected, with numbers.** Raising the west arm's amplitude was
tried at six gains: every one that helped the wedge moved bright pixels to the
core. Measured, a gain of 1.55 put 30 pixels above luminance 250 at the core --
against the reference's TEN, and 96 of the reference's 106 such pixels are on a
ridge, not on the flare at all. That is worth stating plainly because it inverts
the review's "excessive central white area": the render's high-luminance area
was never too large, it was in the wrong place, and the fix was not to dim
anything but to stop adding light at the core. The shipped state has exactly ten.

## D37. The right rays, the colour trade, and a budget that is now binding

**Right rays.** The lower-right axis is 328.35 +- 0.15 degrees, not 327.8: the
render sat 1.9-2.6 px of arc clockwise of the reference at every radius from 82
to 154, and neither drifts, so it is a rotation and a 1.05-degree correction cuts
the transverse rms from 2.32 px to 0.68. Both right rays are CYAN in the
reference and the render made them blue-violet -- hue 252 against the
reference's 138.7 for the upper-right -- and both were re-pointed at the measured
ratio. The upper-right ray was shortened from 215 px to 150 for the reason in
D34. After re-pinning the amplitudes the four rays' hardness reads 0.755 / 0.820
/ 0.596 / 1.313 against the reference's 0.778 / 0.836 / 0.601 / 1.135: three
within 3%, the lower-right still 16% hard.

**Colour: one band, one layer, and an opposite sign elsewhere.** The paleness is
ridge distance 0-16 px, peaking at 4-8, where raw chroma is 22.1% short and red
39.5% high. `arc_glow1` supplies 56.9% of that ring's white depth and `arc_core`
the crest; in the basis the ring needs 6.75 cv of white out and 17.97 of cyan in.
A global boost is refuted by simulation -- the factor that would close this band
takes the broad field to +36% and the background to +40% -- and three families
are ALREADY over-saturated: measuring chroma as max-min of each family's mean
channels -- the convention of `tools/chroma_report.py` and of the 22.1% above --
broad field +4.72%, background +3.41%, ridge 16-70 px +3.43%. (An earlier version
of this entry gave +6.35%, +9.39% and +4.65%, which are 1.3 to 2.8 times too
large under the stated convention, the background worst. The direction and the
argument survive: all three are over, so a global boost still makes them worse.
See D38.) So the change is a constant-luminance white-for-cyan trade in those two
layers and a correction to `field_grad` in the OPPOSITE direction. That the two
corrections have opposite signs is the finding: no single saturation control
could have done both. Measured, the ridge 4-8 chroma deficit goes from -15.19 to
-10.74 cv, red excess from +6.75 to +3.51, hue error from +3.3 to +2.8 degrees.

**The budget is now the binding constraint, and it decided the release.** The
banding ridge figure has a ceiling of 5.00, set in the previous iteration just
above the then-shipped value. This iteration's changes each spend part of it:
the lines +0.09, the west fix +0.08, the colour trade +0.08. They do not all
fit. Measured combinations:

| candidate | MAE | wedge RMS | flare r<110 | ridge chroma | banding ridge |
| --- | --- | --- | --- | --- | --- |
| iteration 3 | 1.9547 | 5.62 | 7.138 | -8.63 | 4.87 |
| west + full line A | 1.9677 | 3.84 | **6.968** | -8.21 | 4.95 |
| west + colour, line A given back | **1.9365** | 3.83 | 7.202 | **-6.44** | 4.98 |
| west + line A + colour | 1.9553 | 3.84 | 7.235 | -6.19 | 5.03 -- **fails** |

The last row is the one that would have been best on structure and it is
rejected, by 0.03 of a figure I set myself. The alternative was to raise the
ceiling to fit the result, which is exactly what D31 declined to do for the
core's falloff and is no more defensible here. So line A's falloff was given
back -- its rms rises from 2.95 to 4.02, still well below iteration 3's 3.41 --
and the release takes the colour trade instead.

**What that costs and buys, plainly.** Against iteration 3: whole-image MAE
1.9547 -> **1.9365**, SSIM 0.97334 -> **0.97365**, pixels off by more than 2
35.67% -> **35.10%**, MAE on a display curve 5.749 -> **5.504**, the coherent
banding measure 1.81x -> **1.74x**, the wedge 5.62 -> **3.83**, the three lines
12.63 -> **6.73**, bright pixels at the core 13 -> **10** against a reference 10.
Against it: the worst single-channel error rises from 104 to 110, and the
flare-region MAE from 7.138 to 7.202 -- the region improved on every structural
measure while its mean absolute error did not, which is the pattern this whole
iteration has been about.

## D38. Six shipped claims, adversarially re-measured: five did not survive

**Why this was done.** The measurements this iteration acted on were validated the
strong way -- by applying them and measuring the rendered result. But several
statements went into these records and into `README.md` as facts about
`reference.png` that were never independently reproduced. Six of those were handed
to independent verifiers, each required to reproduce the number with its own code
and to default to REFUTED when it could not. Five did not survive. What follows is
what changed; the corrections are already applied in place above and in the README.

**1. The upper-right ray's extent -- SURVIVES, with a sharper number and a new
finding.** "Ends at r = 145 +- 15, not 230" reproduces. Measured against a matched
null built from 19 ray-free angles, with error bars inflated by the reference's own
radial autocorrelation (tau = 7.6 px, the JPEG block), the mean excess is +1.46 +-
0.35 cv over r 84-145 (z = +4.2) and -0.28 +- 0.24 over r 150-230. A taper ending
at 230 is disfavoured by dchi2 = 7.2, and any continuation past r = 150 is bounded
at 11% of the amplitude inside r = 120. The central value is L = 154 (1-sigma
143-166) rather than 145; the shipped `len` of 150 sits inside that. The pipeline
recovers the render's own known 150 and 185 px rays to about 2 px, and a positive
control on the lower-right ray shows z = +11 where a ray is present, so the null
result is not an insensitivity artefact. **New:** that ray's axis is 44.90 +- 0.37
degrees, not 45.6 -- a real 1.9-sigma offset -- and `flare_ray_e` has been moved.

**2. The lower-right ray's axis -- REFUTED, and it had changed the artwork.** The
claim was 328.35 +- 0.15 degrees. Measured by a matched filter over r = 82..154 it
is 328.0 +- 0.8. The quoted uncertainty is about five times too tight: merely
changing the filter's kernel width or wing band moves the reference's answer by
0.56 degrees while moving the renders' by under 0.10, which proves the swing is the
reference's structure and not the code. The consequence matters: **this measurement
cannot separate 327.8 from 328.35 at all** -- both sit within one sigma -- so the
rotation to -328.85 was not supported by it, and measured against the axis I now
get, the shipped render had ended up FURTHER from the reference (0.74 degrees
counter-clockwise) than the value it replaced (0.30 clockwise). `flare_ray_c` is
now at -328.1, the measured value. The underlying reason the claim over-reached:
the reference's ray is asymmetric, FWHM 7.3-10.1 px with a counter-clockwise
shoulder, against the render's symmetric 5.4-6.1, so six reasonable definitions of
"the centre" disagree by 1.2-1.7 px -- more than a degree over the lever arm. There
is no single number this axis "is" to 0.15 degrees. The offset is also not purely a
rotation: it decomposes into a constant parallel displacement plus a small angle.

**3. The comb's one-sidedness -- REFUTED as written.** Neither number reproduced,
and the claim contradicted itself: a bound of "ratio >= 3.7 at 3 sigma" cannot
refute "3-6x weaker above", since 3.7 < 6. The most sensitive search finds a
marginal positive residual exactly where a mirror of line C would sit (3.6 sigma,
the 94th percentile of null window maxima -- not a detection), so "no upper line at
all" was an upper limit misreported as a null result.

**4. The three line rows -- REFUTED on precision, not on position.** The row values
bracket the quoted ones, but line B's +-0.15 is about twice too tight (40% of
independent estimates fall outside it), and, more importantly, **no line sits at a
single row**: line A's row moves 0.82 px across the image and line C's about 1.4,
with bootstrap errors of 0.01-0.08 px. A "+- 0.3" on a feature whose row is a
function of x is not honest whatever the number. The verifier also established that
line B runs only from about dx -40 to +90 and is absent west of dx -95.

**5. The colour attribution -- REFUTED on magnitude.** The over-saturation figures
were 1.3 to 2.8 times too large under the convention the same paragraph uses, the
background worst (+3.41% measured against +9.39% claimed). The 55.7% share was the
lowest of four defensible definitions, quoted without saying which. Both arguments
survive the corrections, which is why the shipped colour change stands: all three
families are still over-saturated, so a global boost still makes them worse, and
`arc_glow1` is still the dominant white source in that ring by a factor of two.

**6. The rays' edge softness -- REFUTED, and reversed for one ray.** The reference's
left pair measures 0.306 and 0.359 on the softness index, not 0.46-0.48, and the
upper-left reference ray is FLATTER-TOPPED than the rendered one -- the opposite of
what the README said. The 0.46-0.48 came from a per-radius peak statistic, which is
biased upward on an image with this reference's blocking; the verifier manufactured
the same numbers by adding matched noise to the render, whose true edges are
unchanged. The companion claim that the upper-left carries "narrow 1.48x, broad
1.29x" also fails, because the broad component it refers to barely exists:
`flare_flank_ul` contributes about 4% of the narrow component's peak.

**What this says about the method, which is the point of recording it.** Every one
of the five failures is the same mistake in a different costume: a statistic that is
unbiased on a clean image, applied to one with real 8x8 JPEG blocking, where a PEAK
or a per-radius maximum picks up noise and reports it as signal. It produced a
too-tight error bar (2), a false null (3), a false precision (4), and an inverted
conclusion (6). The defence is the one the verifiers used throughout: an unbiased
MEAN against a null built from the same image at places where the feature is not,
with error bars inflated by the measured autocorrelation length -- and, where a
number is definitional, saying which definition.

It is also why the artwork mostly survived. Every change that was shipped had been
validated by rendering it and re-measuring the result, which is a test these
reference-side errors cannot pass through. The single exception -- the lower-right
rotation -- is the one change made from a reference-side claim alone, and it is the
one that had to be undone.

## D39. The west arm: what a matched null found that three passes of angular
## statistics had missed

The largest single error in the shipped flare was not in any of the structures
three iterations of work had been arguing about. It was a horizontal band of
light due west of the core, about 14 px tall, that the reconstruction did not
have at all -- 8.6, 18.1, 23.4 and 23.8 code values too dim at |dx| 20-28,
28-36, 36-44 and 44-52 in the band dy -5..+9.

**Why it took so long to see.** Every tool that looks west had been built to
mask the left curve ridge at 26-30 px, and the ridge crosses the core's row only
65 px west. At 30 px clearance the entire band |dx| 30..100 is deleted before
anything is measured. The arm was not being measured and found correct; it was
not being measured at all. The angular reports at r 34..46 did see part of it --
that is the `|dy| 0-8` row of `tools/wedge_report.py`, which read -17.45 -- but
it reads as one number among nineteen angular bins and had been treated as a
symptom of the wedge's shape rather than as a missing structure.

**Why the obvious fix was wrong, and what replaced it.** Lowering the clearance
to 20 px makes the band measurable, but then every cell sits 20-35 px from a
bright curve and a deficit there is equally consistent with the CURVE's glow
being modelled wrong -- which would be a fact about the curve-glow layers, not about the
flare, and would have sent the next change to the wrong layer. The two are
separated by a matched null: the identical cell, at the identical perpendicular
distance from the same ridge, evaluated at seventeen positions ALONG that ridge,
far above and below the flare. Those cells share the curve glow, the JPEG grain
and the estimator; they do not share the flare. They read +1.6 with a spread of
2.2 code values. The flare's own row read -15.7 over the same 20-row band. That
is 8 sigma against a population, with no noise model, no autocorrelation
correction and no assumption of Gaussianity -- and it says the deficit is
anchored to the flare.

The same device is what `tools/arm_report.py` now prints beside every west cell,
and it is a better instrument than the error bars of the previous iteration
precisely because it is not calculated. It is measured, from this image, at
places where the answer is known.

**The reference really is west-heavy.** At |dx| 36-44 the reference reads 154.8
west against 132.5 east, and at 44-52, 144.6 against 109.3. The shipped render
read 131.5 against 134.2 -- symmetric. So the change restores an asymmetry the
reference has and the reconstruction had lost; it is not a generic anamorphic
flare being imposed. `east_gain` is 0 because the east side was already 4-7 cv
too BRIGHT, and the first version of the layer leaked about 3 cv east through a
gradient stop that ramped to zero at the east end rather than at the core --
caught by measuring east and west separately, which is the only reason the two
corrections did not get conflated.

**Measure in the domain the model is linear in.** In code values the correction
looked like a rising ramp -- 8.6, 18.1, 23.4, 23.8, then 29.3 further out. In
the screen domain, where a layer actually acts (`u = 1 - v/255` multiplies), it
is nearly FLAT: A*k = 0.11, 0.18, 0.19, 0.18, 0.18, falling to 0.04 by |dx| 100.
One layer with a simple profile, not a ramp needing four. The apparent growth
was the background falling, not the arm rising.

**What is not measurable, and is labelled as such.** Beyond |dx| 52 the left
ridge is nearer than 20 px and nothing there can be separated from the curve.
The outer profile stops are an extrapolation. They were checked afterwards
rather than fitted, and the check passed: |dx| 74-90 improved from -29.3 to
-10.1 and 90-110 from -7.2 to +0.2 without either being a target.

**Result.** West arm RMS over the measurable bins 19.45 -> 0.82 cv. The
`|dy|` split at |dx| 22-52 went -17.45 / -5.01 / +2.33 to -0.00 / +0.65 / +2.48.
MAE 1.9373 -> 1.9228, SSIM 0.97363 -> 0.97373, flare MAE 7.21 -> 6.81, angular
residual RMS 3.83 -> 3.81, and every protected metric -- profile, profile cells,
corner, both lobes -- bit-identical. The ridge-profile banding figure FELL from
4.98% to 4.44%, which matters beyond this change: that ceiling was the binding
constraint on the previous release and it now has half a point of margin,
because part of what it had been measuring was this deficit beside the ridge.

**sigma 5.0, not 5.7.** The measured cross-section is FWHM ~13.5 px, sigma 5.7,
centred dy +1.3 with an estimator spread near +-1.5. But at sigma 5.7 the
angular modulation west of the core degrades (wedge RMS 4.01 against 3.83) and
the |dy| 8-12 band over-fills to +2.66; at 5.0 the modulation is held at 3.81
and that band lands at +0.65. Both values are inside the measurement's own
interval, so the render decided between them, not the reference.

## D40. Two structures found by changing the instrument, not the artwork

The brief for this iteration said to audit the measurement methodology before
making further visual changes, because the previous pass had made an artwork
change from a measurement that did not survive re-examination. Doing that
turned up two features of the reference that three iterations of work had never
seen -- not because they are subtle, but because every instrument pointed at
them was the wrong one.

**The vertical line, and why luminance could not see it.** The reference has a
narrow vertical line through the flare's brightest point. Within about 12 px of
the core, G and B are CLIPPED -- 421 and 453 pixels at or above 253 in a 90x90
box, against 4 for R. Every statistic that had ever been run near the core used
`mean(RGB)`, and in that region mean(RGB) measures the clip, not the light. In
R the column high-pass reads 12.3, 9.8, 4.4, 2.0, 1.5, 1.5 code values over
|dy| 16-26 out to 90-110, against the render's 2.4, 0.5, 0.7, 0.4, -0.4, -0.2.
Choosing the channel was the whole measurement.

The line straddles x = 528, which is an 8x8 JPEG block boundary, so it had to be
shown to be light rather than blocking before anything was drawn. Three
independent arguments: its per-row values are flat across all eight `y mod 8`
phases (spread 0.29 against a per-row sd of 4.4) where a block artefact is
phase-locked by construction; the seven OTHER block-boundary columns in the same
rows read 0.0-0.6 against its 4.1; and it survives 4x box downsampling at a
larger fraction of its amplitude than an injected 1.5 px line does. Any one of
these alone would be suggestive. Together they are decisive, and none of them is
a claim about the size of the effect -- which is exactly the property the
retracted claims of the previous iteration lacked.

Three absences are modelled as deliberately as the presence: no broad halo, no
extension past |dy| 110, and nothing east of the core -- where dx +6..+25 sits
inside the right ridge and the only available limit, 11.6 cv, is looser than the
streak itself. There the honest output is silence, not a feature and not an
absence. The profile is tabulated rather than fitted because it steps by a
factor of 3.1 at |dy| ~33, and both a power law and an exponential were tried
and both misplace most of the light.

**The fan's extent, measured by rendering rather than by reading.** `flare_ray_d`
is the largest layer of the flare, and "too bright" and "too long" look alike in
any regional average. They are separated by asking how the excess is distributed
ALONG the left curve: every curve-glow layer is nearly flat in along-curve angle
at fixed distance, while a flare-anchored fan falls away sharply. That statistic
(`STEP` in `tools/fan_report.py`) plus the plain sector mean were evaluated on
nine renders at len 130..190. Both move monotonically and cross zero at 154 and
157 against a shipped 190, and the excess fraction GREW outward -- 0.24 of the
layer at r 114-175 rising to 0.70 at r 136-191 -- which is what a ray that is
too long looks like and not what a ray that is too bright looks like.

This is the pattern the brief asked for and it is worth naming: the reference
was never asked "how long is the fan". It was asked "which of these nine renders
disagrees with you least", which is a question a JPEG artefact cannot answer
wrongly in a systematic direction.

**The coupling that nearly slipped through.** `onset` is stored as a FRACTION of
`len`, so shortening the ray from 190 to 155 silently dragged its inner edge
from r 45.6 to r 37.2 and put light where the reference has none. The first
render of the change looked like a modest regression -- angular residual 3.81 ->
3.88, a code value added to every band of the horizontal-arm strip -- and the
cause was not the length at all. Raising `onset` to 0.310, i.e. back to an
inner edge at r 48 where the reference shows 0.00 cv at r 20..45 and 0.79 at
r 50, restored every one of those numbers exactly while leaving both extent
statistics at zero. A parameter stored as a ratio is a parameter that changes
when something else does, and only re-measuring after the render caught it.

**Result of the two changes together.** Sector mean 3.52 -> 0.11, STEP 2.91 ->
-0.21, vertical-line rms error 5.87 -> 0.37 cv; MAE 1.9228 -> 1.8990, SSIM
0.97373 -> 0.97387, left lobe MAE 1.50 -> 1.37; banding, profile, profile cells
and corners unchanged. The west arm's measurable bins now sit within 1.2 sigma
of their matched nulls, against 4.3 to 13.4 sigma before this iteration.

## D41. The long line really is too white, and `flare_fan` is not the lever

Measured with two independent estimators, the render's long horizontal line
carries three to four times too much red. The reference's line light runs
R/G = 0.09 at |dx| 100-150 west and 0.12-0.23 east; the render runs 0.41 and
0.44-0.79. The obvious culprit is visible in the parameters: `flare_fan`, the
broad wash that stands in for the line's skirt, has colour (120.77, 120.77,
120.77) -- literally achromatic, R/G = 1.000 -- where the reference's skirt is
pure cyan (R/G = 0.00 +- 0.09).

So the change looks like a one-liner, and it is wrong. Four variants were
rendered, from a 10% red reduction to full cyan:

  white   R/G east 50-100   R at r 12-25   R at r 45-70   MAE
  0.474 (shipped)   0.789      +0.50          +5.85     1.8990
  0.420             0.754      -2.61          +5.65     1.8993
  0.380             0.714      -5.02          +5.47     1.8998
  0.340             0.675      -7.32          +5.29     1.9005
  0.000 (cyan)      0.329     -27.36          +3.79     1.9130

Every step improves the colour of the line and makes the picture worse, and the
reason is in the third column. `flare_fan` is the only substantial source of red
over r 12-25, where the reference wants it: the render's red residual there is
+0.50 code values, i.e. correct. Removing the red to fix the line's colour at
|dx| 50-210 opens a 27 cv red hole in the inner bloom. The layer is being asked
to be two colours at once because it spans both regions with one.

The real structure is a horizontal wash whose colour changes with distance --
white-hot within ~25 px of the core, cyan in the wings -- and reproducing that
means splitting the layer by distance and refitting the pair, not recolouring
the existing one. That is a structural change with its own validation cycle and
it is NOT made here.

Recording it unmade is the point. The measurement is sound and the diagnosis is
specific; what is missing is the rebuild. The alternative on offer was a
parameter nudge that moves the colour statistic a little, moves MAE the wrong
way, and leaves the line visibly white -- which is precisely the loop this
iteration was asked to break.

**Also measured, also not applied, for the same reason -- each needs a rebuild
rather than a parameter:**

  * The west angular MINIMA are still filled. Over 99 combinations of radius
    band, clearance, angular smoothing and core offset, the reference shows an
    interior local minimum at theta 140 +- 4 in 91% of them and at theta 217
    +- 5 in 84%; the render shows one in 0% of 99, on either side. The unbiased
    fill statistic is positive in 102 of 102 knob settings (median +7.2 and
    +7.5 cv). The wedge RMS improved last iteration without this improving at
    all, so the two are not the same defect: the lobes are the right height and
    the gaps between them are filled in.
  * The rendered CORE is about 2.4 px [1.9, 3.0] too far west and 0.7 px
    [0.35, 1.0] too far south, and is rounder than the reference's flat-topped,
    east-skewed plateau. Two separate cautions apply. The white core itself is
    NOT too large -- at G = 255 the render has 14 px against the reference's
    19-26, and at R >= 240 they are indistinguishable -- so the standing
    complaint is half wrong; and moving the flare centre moves every anchored
    layer, so it cannot be done without refitting them.
  * The line is not too THIN. Its narrow-core FWHM is 4.04 +- 0.54 px in the
    reference against 3.88 +- 0.26 in the render, a difference of 0.16 +- 0.60.
    It is too CONCENTRATED: the total light agrees to within 10% at every band
    inside |dx| 210, while the share lying beyond |dy| 3 px is 0.55-0.78 in the
    reference and 0.17-0.49 in the render. A redistribution, not a brightness
    error -- and the same layer split that fixes the colour is what would fix it.

## D42. There is no global saturation defect, and the one real colour error is
## two opposite errors 12 px apart

The standing request to "adjust saturation" was re-measured under both chroma
conventions and every mask knob. **Global chroma is +0.65% by max-min on code
values and -0.59% by mean C*ab -- the sign flips with the convention**, so there
is no global saturation defect to correct, and the 24-96 px glow is mildly
OVER-saturated (dC*ab +0.24 +- 0.09 and +0.21 +- 0.10), so a global boost would
move that region the wrong way. This supersedes nothing in the artwork, because
iteration 4 had already declined a global control on narrower evidence; it
closes the question.

Exactly one region carries a colour difference that survives both conventions,
and the reason it took this long to characterise is that it is **two opposite
defects that a pooled band average cancels**. In the 3-12 px band flanking the
curve ridges:

  * on the CONVEX side, between the curves, the render is short 8.7 +- 1.6 code
    values of G and 7.5 +- 1.3 of B with R correct (dC*ab -1.73 +- 0.29,
    dL* -3.61 +- 0.68);
  * on the CONCAVE side, the lobes, it is 5.9 +- 1.8 too RED with G and B
    nearly right (dC*ab -1.57 +- 0.37, dL* -1.26 +- 0.38).

Everything else is the right colour. The crest and the frame are
right-coloured and wrong-brightness (dC*ab -0.76 +- 0.54 and +0.06 +- 0.13
against dL* -2.34 and +0.61), and the flare core, the rays, the broad field and
the dark background show no established chroma difference at all.

That is a specific, sided correction to the curve layers -- add cyan on one
side, remove white on the other -- and it is not a saturation knob. It is not
made here for the same reason as D41: the layers that paint those 12 px are
shared between the two sides, so it needs a split and a refit rather than a
value.

## D43. The rays re-measured: an offset that had been mistaken for an angle

The sixth audit of this iteration re-measured all four rays with injection-
calibrated nulls at 11-19 feature-free sites, across 15 analysis knobs, at two
blur scales and at half resolution. Its most useful result explains a failure
already recorded in D38.

**The lower-right ray is DISPLACED, not rotated.** Last iteration the artwork was
changed by rotating `flare_ray_c` from 327.8 to 328.85 degrees on a claimed axis
of 328.35 +- 0.15; re-measurement gave 328.0 +- 0.8, the change had left the
render further from the reference, and it was reverted. What this audit shows is
why both of those passes were asking the wrong question. The reference's ray
direction is 328.18 +- 0.21 and the render's is 328.40 -- the two lines are
PARALLEL. The reference crosses r = 100 at 328.8 where the render crosses at
327.30, and crosses r = 80 at a difference of +1.97 +- 0.03 degrees. A constant
angular difference is rejected (chi2/dof 6.18 against 0.45 for a line); the
per-radius offset fits ds(r) = +3.72 - 0.0126 r px over 24 radii from 57.5 to
172.5. The ray misses the assumed core by about 2.6 px perpendicular.

A rotation cannot express that. It over-corrects inside r = 70 and under-corrects
beyond r = 150, which is exactly the pattern the reverted change produced. The
fix, when it is made, is to give `flare_ray_c` its own `cx`/`cy` -- which the
builder already supports -- and shift the origin along the normal.

**What else the data supports**, all robust and all with matched nulls:

  * the lower-right ray is 1.4-1.8x too narrow AND does not widen with radius
    (reference FWHM 7.89 -> 9.66 -> 11.23 px over r 57-75/75-92/92-110 against
    the render's flat 6.03 -> 6.25 -> 6.21), +7.2 sigma at r 90-125 against an
    injected control of the render's own width;
  * it carries a counter-clockwise shoulder, +1.01 px of extra half-width at
    r 57-90 and +2.88 px at r 90-125, where the render is symmetric to 0.13 px.
    A single symmetric quadrilateral cannot make this;
  * the lower-left ray has the mirror-image defect, a CLOCKWISE shoulder of
    -1.44 and -2.55 px, and a core sharper than the render's (sharpness index
    2.13/2.19 against 1.68/1.73, +6.8 and +4.4 sigma).

**What must not be changed**, which is the more valuable half:

  * `flare_ray_e` (upper-right) is correct and is to be left alone: axis matches
    to +0.08 (-0.37..+0.40) degrees, radial extent matches bin by bin within
    1 sigma, integrated flux matches. It looks about twice broader in the
    reference, but the FEATURE there is itself detected at only 2.0-2.3 sigma per
    bin, its measured asymmetry flips sign between radius bands, and every shape
    number for it is therefore conditional on something marginal.
  * The upper-left ray's SOFTNESS claim, already refuted once in D38, is not
    reproduced here either: the sharpness index reads -0.5 and +0.1 sigma from
    its injected control. That question is now closed twice over.
  * **No ray axis in this image supports a precision near 0.15 degrees.** The
    best-determined of the four spreads 0.55 degrees across the six reasonable
    definitions of a centre before any knob or noise enters; the upper-right
    spreads 1.91. The +-0.15 that changed the artwork was four to thirteen times
    tighter than the definitional spread alone.
  * A narrow-plus-broad decomposition must not be fitted to any of these rays.
    Its improvement over a single component (0.26-0.94) is inside what an
    injected SINGLE Gaussian already yields on this image's noise
    (0.33-0.77 +- 0.10-0.36), the largest excess is +2.5 sigma, and the fitted
    widths are unstable between adjacent radius bands.

**One finding is NOT acted on because two of my own instruments disagree about
its sign.** The audit reports the upper-left ray carrying 1.88x and 2.47x the
reference's integrated flux at r 70-82.5 and 82.5-95, measured at 16 px ridge
clearance with a quadratic wing baseline and confirmed by a second, different
baseline. `tools/ray_report.py`, at 30 px clearance and using a per-radius peak
of the chord excess, reads the opposite at the outer end: reference 6.17, 5.09,
2.61 against the render's 2.57, 1.97, 0.55 at r = 90, 95, 100.

The two can be reconciled -- the audit's own note says the cleared channel
between the curve ridges closes past r ~ 95 for this ray, so at 30 px clearance
those columns are a sliver, and a PEAK statistic on a sliver of a noisy image is
the exact estimator this whole iteration exists to distrust. That is an
explanation, not a measurement. Until the two are made to agree at a common
clearance with a common statistic, changing the upper-left ray's amplitude would
be picking the instrument that gives the answer one wants, and the ray is left
alone.
