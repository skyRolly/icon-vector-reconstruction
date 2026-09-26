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

## D44. The instrument first: what a chroma row and a nearest-neighbour zoom
## showed that six iterations of metrics had not

The brief for this iteration opens by observing that repeated passes reported
the same visual errors while the numbers moved, and asks for the comparison
method to be changed before any further artwork change. That is the right
diagnosis, and the reason is specific rather than general: **every structure
under dispute is worth less than 0.01 of whole-image MAE.** The flare is 5% of
the canvas, its rays are a few code values on a background of tens, and the
optimiser will trade all of them for a hundredth of a code value somewhere
else. A whole-image metric is not a weak instrument here; it is an instrument
pointed at a different question.

`tools/flare_view.py` is the answer to section 4. One crop, three
decompositions, three scales, reference and reconstruction side by side with
both differences. Three of its choices are load-bearing:

  * **Enlargement is nearest-neighbour.** A smooth upscale invents a gradient
    between two pixels, and "is the centre a compact core with detail or a
    diffuse blob" is exactly the question a smooth upscale answers wrongly.
  * **Every gain is printed in its panel label.** A difference panel with an
    unstated multiplier is an argument, not evidence.
  * **Differences are computed at native resolution and enlarged afterwards.**
    The reverse order hides a one-pixel misalignment, which is the most common
    real defect in this artwork.

The row that earned its place is CHROMA: `rgb` minus its own mean, so any grey
at any brightness is neutral and colour alone remains. On the shipped artwork
it showed at once that **the reference's low-chroma core is not round** -- it is
extended west and vertically, where the render's is a circle. That is a
statement about shape that no chroma ratio had produced in six iterations,
because a ratio of two bright numbers is not a picture.

The first thing the instrument was pointed at was section 2's question, and it
answered it: rendering `reconstruction.svg` from eight commits spanning two
iterations gives MAE 1.8978 (head) through 1.9373 (iteration-4 final), with the
head best on every regional metric. No rollback is warranted. But the same table
carries a warning that set this iteration's agenda: **`core r<30` MAE sits at
9.12-9.24 in ALL EIGHT candidates.** Two entire iterations of parameter work had
not moved the core at all, which is section 34's question asked by the data
rather than by a reviewer: if the issue survives several iterations, is the
model capable of representing the structure?

## D45. The westward triangle: the shape was wrong and the light was not

Section 5 names the false triangular region as the primary visual target and
instructs that it be removed rather than reduced. Two things had to be
established before acting, and they pointed in opposite directions.

**The shape is indefensible.** `flare_ray_d` was a `ray`-kind quadrilateral --
half-width 15 px at the core growing to 115 px at r 155, filled with a
longitudinal gradient and blurred by 4 px. Isolating the layer and rendering it
alone shows a hard-edged trapezoid; there is no ambiguity in the picture.
Measured against a render with every west layer removed, it supplies **48-51
screen units at every dy from -40 to +46** at |dx| 84-104 -- flat to 3% across
an 86 px span -- where the reference wants a peak of 157 at dy -5 falling to
60-88 at the edges. At dy 90-130 the reference wants 0 +- 1 unit and the quad
supplied up to 7.

**The light is real, flare-anchored, and needed.** Deleting the layer opens 2-8
cv holes across theta 145-220 at r 96-170, at 4.5 to 25 sigma under three
independent null families; `fan_report` goes from S 0.113 / STEP -0.209 to
-3.577 / -2.635 against a null sd of 0.72. Swept along the left ridge, the
reference's excess over the render peaks at the flare's own row (-23.8 cv at
10-25 px beyond the ridge), falls to -13 cv at +-40 px and is within 2 cv of
zero at +-60 px: it decays away from the flare, so it belongs to the flare and
not to the curve.

**Confirmed on the shipped replacement, which is the number that was missing
here.** The -3.577 / -2.635 above is the BARE deletion, and quoting only that
leaves the entry unable to say whether the band put the light back. Run on all
three models, `fan_report` reads S 0.113 / STEP -0.209 for the pre-change
baseline (identical to the iteration-5 release), -3.577 / -2.635 for the bare
deletion, and **-0.128 / -0.488 for what shipped** -- 0.3 sigma from the
baseline against a null sd of 0.72, where the deletion sits at 5.1 and 3.4
sigma. The straight edges went and the light did not.

So the light stays and the straight edges go. `flare_arm_w2` is a west-only
streak with a Gaussian cross-section, sigma 46, centred 6 px above the core's
row, carrying the measured longitudinal profile (144 screen units at |dx| 86,
69 at 102, 35 at 119, 17 at 138, 10 at 159).

    MAE            1.8978 -> 1.8892      centre-region MAE  8.355 -> 8.018
    SSIM          0.97390 -> 0.97394     flare r<110        6.852 -> 6.631
    west field      3.015 -> 2.898       far west r 96-170  2.617 -> 2.328
    bloom beyond the left ridge   -11.10 -> -4.84 cv
    fan_report S / STEP  0.11/-0.21 -> -0.30/-0.63   (null sd 0.73)

**The alternative that measured better was rejected, and the cost is recorded.**
Keeping the quad and adding a separate bloom layer gives MAE 1.8865 against
1.8892 -- better by 0.003. It was not taken, because it improves an aggregate
while leaving in place the artefact that is the named target. That is precisely
the trade section 2 forbids ("do not let a new optimization replace a visually
better candidate merely because it improves one aggregate metric"), and the
0.003 is stated here rather than buried.

**Where the brief's premise does not survive.** "The reference does not contain
this broad triangular region" is too strong. At r 110-150 the reference's
angular profile west of the core is a smooth filled bowl: over twelve analysis
settings per radius it shows no interior minimum in theta 203-232 at any of
r 100 through 150. A filled westward region IS supported there. What is not
supported is a flat top and a straight edge. The angular minima that do exist
are real but shallow -- confined to r 34-52, median depth 0.8-1.3 cv against a
matched-null spread of 1.0-2.5 -- and the render's largest errors near them are
on the SLOPES (+5.9 cv at theta 151, +6.6 at 205) rather than in the minima
themselves (+0.9 at 139, +2.5 at 217). "The render fills in the minima"
mis-describes the defect, and an earlier record of 91%/84% minimum stability
against a render at 0% should read 76%/46% against a render that shows the
upper minimum in 62% of settings, displaced about 10 degrees.

**What is not measurable, and is not claimed.** About a quarter of this layer's
light falls within 20 px of the left ridge -- the annulus r 48-88 due west
clears a 20 px mask in only 6.9% of its pixels, and the old layer's longitudinal
peak at r 70 sat where the clearance is 4.5 px. Neither the old amplitude there
nor the new one is measured; both are extrapolations held to what keeps
`fan_report` at zero. If a human sees a false triangle in that annulus,
reference.png cannot confirm or refute it.

`flare_flank_dl` is re-aimed from -234 to -240 +- 2 in the same pass: the light
the reference wants over a render without that layer peaks at theta 230-240 with
a half-max half-width of 17 degrees, where the layer supplied a flatter
distribution with too much at 210-222 and too little at 228-240. `flare_flank_ul`
is left alone and recorded as NOT MEASURABLE -- its entire contribution is
0.06-1.21 cv against a matched-null spread of 1.0-2.5 cv in the same cells, and
where it sits the render is already too dim, so removing it would deepen a
deficit rather than remove an excess.

## D46. The core is too tall, not too large -- and its colour error is not
## reachable from here

Section 8 asserts that the central core is "a broad white mass surrounded by
excessive white feathering". Measured, **that premise is half wrong**, and
saying so is more useful than acting on it.

The truly-white region (min(R,G,B) above a threshold, equivalent radius) is
ref/render 2.39/2.39 px at 240, 3.83/3.52 at 230, and larger in the render by
only 1.0-1.3 px at 180-220. The 245->200 transition width -- "feathering" made
quantitative -- differs by a median of +0.1 px over 30 combinations of sector,
mean-versus-median and clearance, i.e. consistent with zero. Inside r 8 the two
are indistinguishable. Reducing the peak or sharpening the flare, both of which
the brief separately forbids, also both make MAE worse.

What IS wrong is the aspect ratio. From each image's own peak, the render's R
half-width north and south exceeds the reference's by 1.1-2.9 px at every level
from R=200 down to R=140, while the westward half-width matches within +-0.5 px
over nine levels with no trend. Reference W/N is 1.90 at R=200 and 2.09 at
R=160; the render's is 1.49 and 1.60. `flare_halo`'s squash goes 0.6453 -> **0.62**, and
the difference between that and the 0.58 the core's own aspect asks for is the
whole of this entry's interest.

The core alone wants 0.56-0.60: the north and south R-excess zero-crossings sit
at 0.578 and 0.577, and at 0.58 the north R excess at r 8-20 falls from +9.25 to
+2.05 cv and the south from +5.81 to -0.97. Whole-image MAE is flat to 0.0016
across 0.56-0.62 and cannot arbitrate. **But this layer does not only set the
core's aspect -- it also carries the diagonal west field at r 34-46, and the two
want opposite changes.** `wedge_report`'s angular residual RMS over 19
ridge-cleared bins runs 4.41 / 4.09 / 3.76 / 3.43 cv at squash 0.58 / 0.60 /
0.62 / 0.6453: compressing the halo dims theta 109-139 and 223-247 by about
2.5 cv apiece. Shipping 0.58 would have bought a 1-3 px core aspect at the price
of a 0.8 cv rise in the angular RMS of the very region section 5 names as the
primary target.

0.62 is the point at which BOTH instruments beat the previous release rather
than one being traded for the other: angular RMS 3.81 -> 3.76, north R excess at
r 8-20 +9.25 -> +6.67. This is the same structural fault as the colour error
below -- one isotropic layer serving two requirements that are not isotropic --
and it was found only because the west work and the core work were measured
against each other instead of separately.

**The colour error, measured and deliberately not fixed.** Beyond r 20 the
render carries too much white primary and too little cyan at nearly constant
luminance: north at r 20-40, dR +12.3 with dG -4.8 and dB -6.4, against a
36-placement matched null at z = +27, where the luminance difference is +0.4 and
sees almost none of it. This is the measurable part of the standing
under-saturation complaint, and it is LOCAL to r 20-55 rather than global --
which is why whole-image chroma statistics have missed it repeatedly, and why
D42's "no global saturation defect" was right about the global and silent about
this.

Three attempts establish that the model cannot express the correction:

  * both halo layers are already at maximum amplitude (white 1.0, cyan 1.0), so
    the only levers are geometric. A 9-point sweep of the pair's e-folding
    leaves the shipped values the MAE optimum; the best chroma cell improves the
    colour statistic from 5.73 to 4.99 and costs 0.053 of MAE;
  * a NEW mid-radius cyan halo, four geometries over r 48-75, buys a tenth of
    the defect for 0.0035 of MAE and 0.10 of flare-region MAE;
  * both fail for the same reason. The error is ANISOTROPIC -- the same annulus
    that is too white north and south is too DIM in red due west (dR -6.9 at
    r 20-40) -- and every colour carrier at that radius is isotropic.

The fix is an angular colour decomposition: white moved out of the isotropic
halo into a horizontal carrier with the cyan raised to hold the luminance,
fitted against per-direction per-radius colour cells. That is a rebuild of the
bloom's colour basis, it is a fit rather than a parameter change, and it is
recorded with its three failed routes so the next pass starts from the negative
results instead of repeating them.

**A documentation defect fixed in the same pass.** `flare.note` claimed the
flare block's cx,cy agreed with two measured positions of the reference's
brightest point. They do not and have not. The compact peak sits 2.4-3.4 px east
and 0.6-1.1 px north of cx,cy by the estimators that use R or a sub-pixel
translation fit, while the broad bloom's centroid agrees to within 0.2-0.7 px --
and the disagreement between the two is itself the finding: the PEAK is
displaced and the BLOOM is not. cx,cy is left alone, because moving it drags all
fifteen flare-anchored layers and costs 0.009 MAE; correcting the peak alone
needs a displaced compact layer, which is not built.

## D47. The horizontal line: it was never the core's width, it was the missing
## broad half

Section 12 says the line is "too white, thin, hard, isolated" and proposes
splitting the horizontal wash into a near white component and a far cyan one.
The proposal is **supported, with one correction that matters**: it is the BROAD
component whose colour changes with distance, not the narrow spike.

A transverse cut through the reference's line is two things at every distance: a
narrow spike, and a wash of sigma 12-18 px that carries **70-94% of the light**.
The reconstruction reproduced the wash inside |dx| ~80 and had essentially none
beyond. North-flank skirt fraction over three baseline annuli, reference against
the old render: 0.71/0.71/0.70 vs 0.30/0.48/0.54 at |dx| 80-130, and
0.69/0.72/0.70 vs -0.38/-0.25/0.32 at 130-190 -- where the render's statistic is
unstable precisely because its numerator is zero. Against a matched null at the
same cell displaced 110/150/190 rows: 11, 7.4 and 2.5 sigma.

**The narrow core's width was never the problem.** Reference sigma 1.32-2.81 px
against the render's 1.45-1.79 -- indistinguishable. What made the line read as
hard and isolated was the absence of the thing around it.

Colour, broad component only, with the narrow spike's shape held fixed:
R/G 0.97 +- 0.09 at |dx| 18-45, then -0.03 +- 0.05 at 80-130 and -0.07 to +0.10
beyond. The narrow spike shows no distance trend at all (0.15-0.35 everywhere)
and is left alone. The white-to-cyan transition is bracketed at |dx| 45-70 and
NOT localised more finely -- it rests on one 14-column east band -- and whether
it is a step or a ramp is unresolved.

Shipped: `flare_fan` truncated from half_len 123.2 to 62 with its profile scale
rescaled by 123.2/62 so the falloff IN PIXELS is unchanged (the scale is in
units of half_len, so shortening without rescaling would have changed the shape
as well as the extent); a new pure-cyan `flare_wash_far` at sigma_y 14,
half_len 320, with a tabulated non-monotone profile; and the three affected
amplitudes refitted together. The narrow line had been standing in for the
missing wash and came down 28% in white when the wash arrived.

    MAE  1.8886 -> 1.8860      SSIM 0.97394 -> 0.97399
    line band MAE 3.983 -> 3.800
    skirt fraction, as a fraction of the reference's:  0.635 -> 1.083

**D41 is confirmed and sharpened.** `flare_fan` is still the only near-field red
source: recolouring it cyan at equal G opens a 15-33 cv red hole over r 12-32,
and a control that only ADDS a pure-cyan far wash leaves dR bit-identical at
every radius, which is the direct proof. But D41's "correct to +0.50 cv at
r 12-25" is an average of +11.05 at r 12-18 and -3.81 at 18-25 -- two opposite
errors, the same pattern D42 found elsewhere -- so the near field is not right,
its red is mis-distributed in radius, and no monotone exponential from r 0 can
carry an annulus. That is recorded in the layer note and not fixed here.

**An instrument was correcting away the thing it was used to detect.**
`tools/line_shape.py` takes its baseline from rows at |dy| 22-26, and a sigma-15
wash is still at 0.28 of peak at dy 24 -- so most of the missing component was
being subtracted from both images before the comparison. Re-running the same sum
under five baseline annuli at |dx| 130-190 gives reference/render ratios of 2.5x
to 6x under every choice and never near 1, against the 1.0 the narrow annulus
reported. The standing claim that the line's total light agrees within 10% holds
only inside |dx| ~100; beyond that the render was missing 55-100% of it.

**The hierarchy is confirmed unchanged**: three lines at dy 0, +6.75 to +7.28
and +16.7 to +18.9, no fourth line, and no north counterpart anywhere (amplitude
-0.027 to +0.005 in all eleven windows). Line A also sags about 1 px between
|dx| 50 and 240 on both sides, survives 2x downsampling, and cannot be an
8-px-grid artefact because the windows span 4-6 blocks; it is not acted on,
because a rect with a blur cannot bow and a sub-pixel bow is not worth a new
primitive while a 2-6x amplitude error is open.

## D48. The vertical line was symmetric because nothing could see that it should
## not be

`flare_vline` shipped with `south_gain` at exactly 1.0. That is a default, not a
measurement, and there are three separate reasons it went unexamined for a
release -- which together are a better description of how this kind of error
survives than any one of them alone.

  1. **It could not be searched.** `sigma_x` and `south_gain` both carried
     carefully chosen `bounds` in params.json, and neither name was in
     `layer_specs`' key list. So `--spec shapes` and `--spec all` both left them
     frozen while every log said the shapes had been optimised.
  2. **The report could not see it.** `tools/vstreak_report.py` pooled north and
     south into one band mean. An asymmetry is invisible to that statistic by
     construction.
  3. **The report would have argued against the fix.** Because the pooled mean
     drops when one side is dimmed, setting south_gain to 0.6 moves that report's
     rms error from 0.37 to 0.88. An instrument blind to an asymmetry does not
     merely fail to find it; it actively defends the symmetric version.

The reference's line is north-dominated. south/north of A_4 over |dy| 36-110:
**reference 0.44 in B and 0.63 in R, against the shipped render's 0.97 and
1.19**; at south_gain 0.55 the render reads 0.45 and 0.65. A block bootstrap
over 8-row blocks gives B 0.52 [0.28, 0.84] with P(south >= north) = 0.004. The
honest range is 0.45-0.85 and the estimators disagree systematically inside it
(a narrow centre-minus-flank statistic says 0.35-0.42, A_4 says 0.52-0.63, a 4x
downsample says 0.75), so 0.55 is a choice within a range, not a measurement to
two figures.

The change is MAE-neutral to four decimal places. That is the point: a
whole-image metric cannot see it at all, and it is still wrong.

**A methodological correction that inverts a rule this project has been using.**
"R is the honest channel near the core" is true within about 12 px, where G and
B clip high. It is FALSE at |dy| 26-70, where R is pinned against its ZERO floor
-- 20.5%, 30.5% and 19.7% exact zeros at |dy| 26-36, 36-50 and 50-70, while G
and B sit mid-range at 105-177 with nothing clipped at either end. A
floor-clipped channel is exactly as dishonest as a ceiling-clipped one, and the
vertical line's tabulated inner profile was measured in R over precisely the
bands where R is on its floor. That profile is therefore left alone and marked
as unvalidated rather than "measured": the three channels disagree about the
required amplitude there by factors of 2-6 and contradict each other in SIGN in
three of six bands.

`sigma_x` 1.7 was re-measured at the same time and survives: the width-sensitive
ratio N/A_4, calibrated by rendering the same layer at five nominal widths, puts
it at 1.44-1.60 in G and B and 0.95-1.35 in the floor-clipped R. 1.55 is
marginally better supported; the difference is below the render's own resolution
and was not taken.

## D49. A regression suite for the failures that keep coming back

Seven structures have each been reported wrong, fixed, and reported wrong again.
None of them is worth 0.01 of whole-image MAE. That is not a weakness of the
metric, it is arithmetic: the flare is 5% of the canvas and its rays are a few
code values on a background of tens, so an optimiser will trade every one of
them for a hundredth of a code value somewhere else and the aggregate will
improve. `tools/visual_regression.py` exists because a guard that is not
explicitly about these structures will not protect them.

Every check is a RATIO TO THE REFERENCE measured by the same estimator on the
same cells, never a threshold on the render: a hard-coded pixel count would
encode one release's accidents, and on an image with real JPEG blocking it would
encode some of the compression as well. The bands are wide on purpose. These are
presence tests, not accuracy tests, and the failure they exist to catch is a
structure quietly going to zero.

**The statistic that was wrong twice, and why it is worth recording.** The ray
checks began as "the axis against two windows 14-26 degrees either side". Two of
the four came out NEGATIVE for the REFERENCE -- the lower-left ray sits 10
degrees from the lower-left flank's peak and the upper-left sits inside its own
flank, so the "background" window held another structure. A ratio of two
negative numbers is not a presence test. The second attempt used the annulus
median, and that failed differently: this field is strongly anisotropic, the
horizontal axis is far brighter than the diagonals, and the median then sits
ABOVE the left rays so both images read negative again. What works is the
QUIETER of the two flanking windows -- a neighbour raises one side, so the
smaller of the two is whichever side is actually empty.

**A check that cannot see its structure must not claim the structure is gone.**
Two guards enforce that. Each check declares a floor below which the REFERENCE's
own statistic is not trustworthy, and reports NOT MEASURABLE rather than a
ratio: the lower-right ray reads -0.18 in the reference at r 55-105, because the
right ridge deletes most of that annulus, and dividing by it produced a
confident "4.13x" out of nothing. And each ray's radii were chosen by deleting
all four rays and asking how much of the number disappeared -- at a common
r 55-105 the upper-right figure moved by 5%, i.e. the check was reading the
right arc's glow. At the shipped radii the ray's own share is 98 / 82 / 80 / 92
per cent.

Validated by breaking the artwork on purpose. Deleting the vertical line trips
it at 0.11x; deleting all four rays trips all four ray checks at 0.03-0.30x;
deleting lines B and C trips both; deleting the cyan bloom trips the colour and
skirt checks; and the PREVIOUS release -- with the flat-topped westward
quadrilateral -- trips the west-shape check at 1.23x.

**Two of the twelve currently guard a structure that is known to be wrong rather
than right, and their bands say so.** The upper-right ray measures 0.36 of the
reference and the lower-right 0.61. Setting a comfortable band would have hidden
that; the floors are instead set where the artwork actually sits, and the
deficit is written into the check's own description so it cannot be mistaken for
a pass on the merits.

## D50. What the optimiser could not reach, and what a sidecar could not prove

Four correctness defects, each of which had the same shape: a check existed, it
passed, and it was narrower than the thing it was guarding.

**`layer_specs` emitted neither `sigma_x` nor `south_gain`.** Covered in D48.
The fix is not the two names -- adding two names would leave the next
parameter to be found the same way. `verify_searchable()` now reports every
bound declared in params.json that no spec can reach, the regression suite
fails if the list is non-empty, and a second check proves the guard is not
vacuous by truncating the key list and requiring that it notices.

**`frame_rim`'s radial paint centre was reachable by no spec builder at all.**
The existing check looked only at `field_specs` and only at three layer kinds;
`frame_rim` is a `frame_ring`, so it fell outside the check and its centre was
frozen under every `--spec`. The check now tests every radial paint against the
union of all four builders. `exterior_corner`, the other radial paint, was
already reachable -- the gap was one layer, not two, and the first version of
this entry said two.

**A render sidecar recorded two digests and only one was ever read.** Replacing
out/render_1024.png with different bytes while leaving the sidecar in place left
`compare.py` and `diagnose.py` still attributing their numbers to the SVG named
there -- verified by doing it. Both had their own copy of the same function and
both copies skipped the same step, which is the ordinary fate of a check that
exists twice. `read_provenance` now hashes the raster before believing anything
the sidecar says about it, there is one implementation, `validate.py` describes
the rasters it writes (it overwrites the same canonical filename a step later in
the publish cycle), and publish requires provenance for the two JSON files the
README publishes. The three-step case is in the regression suite and fails
without the fix.

**An explicitly configured but unusable `$ICON_CHROMIUM` was a successful
skip.** "Optional" had been allowed to swallow a broken configuration. Discovery
now returns one of four states -- configured, discovered, misconfigured, absent
-- and validation exits 3 on a misconfiguration, 2 on an execution failure, 0 on
a genuine skip. All four were run rather than reasoned about: unset -> 0,
nonexistent path -> 3, non-executable file -> 3, executable that exits nonzero
-> 2.

Verified as already correct, with the evidence rather than by assumption: comb
cells survive stride 3 and 4 (51/53/45/45, every |dx| band represented, so a
subsampled shape search can still see the lower horizontal structures); flare
calibration that exhausts its round budget returns nonzero and reports NOT
converged; isolation rejects orderings its algebra cannot express; the
profile-weight cache is keyed on the target rather than on its luminance sum;
and geometry trials are re-baselined with equal colour freedom.

## D51. The left rays: an instrument conflict resolved, and two rays that are
## not parallel to their own model

D43 left an unresolved disagreement: `tools/ray_report.py` at 30 px clearance and
an integrated-flux audit at 16 px disagreed about the SIGN of the upper-left
ray's amplitude error at r 90-100. It is resolved, and the resolution is a
property of the instrument rather than of the artwork.

**A chord-excess peak measures brightness only if the chord's endpoints are off
the structure.** At 30 px clearance the cleared angular island around the
upper-left ray reaches only s = +5.8 / +4.2 / +3.0 px at r = 90 / 95 / 100 while
extending to -31 / -35 / -38 on the other side, so the chord's positive endpoint
lands ON the ray. The decisive test used no reference data at all: take the
render's own ray field (render minus a render with the layer deleted), rotate it
by 5 degrees about the flare centre -- total flux ratio 1.0000, peak 18.13
against 18.33 -- and put it back on the same background. The report's peak moves
from 2.64 to 9.11 at r = 90 and from 0.59 to 7.69 at r = 100. **A factor of 3.5
to 13 from position alone, with the light unchanged.** The audit was right.

`ISLAND_MARGIN` now makes such a radius report nothing. With the biased cells
gone the two images agree where they used to differ: reference mean peak 10.14
cv against the render's 9.34, where the unguarded report read 8.08 against 6.83.

This also answers section 19's question about `RAY_GEOMETRY` and
`ray_report.RAYS` carrying different angles. They are different quantities and
should not be reconciled by copying one into the other: `RAY_GEOMETRY` holds the
layers' geometric axes, `RAYS` holds SCAN angles that only have to put the
structure inside a +-26 px window, and the `ref angle` row reports where a
(biased) peak lands inside that window -- a third thing again. Pointing the
upper-left scan at its layer's new axis was tried and rejected: it walks the
window into the left ridge and costs r 50-70, the radii at which that ray is
brightest.

**Neither left ray is parallel to its rendered counterpart.** For the upper-left
ray, the transverse centre difference fits Delta = a + b*r with b = -3.7 to -8.9
degrees (median -6.5) and a = +1.8 to +7.6 px (median +5.2) over 39 estimator
variants; a straight line beat a pure translation in 39 of 39, median
sum-of-squares ratio 0.09. Delta is -0.2 px at r 45, -3.7 at r 75 and -7.1 at
r 105, against a render whose own ridge is flat to 0.17 degrees, so the
background's curvature cancels. Three independent cross-checks agree, including
a Cartesian row scan that uses no polar sampling anywhere.

Neither a rotation nor a translation alone describes it, and `a` and `b` are
strongly anti-correlated -- the defensible statement is the Delta(r) curve, not
either number. Shipped as rot -113.6 -> -107.1 plus dx/dy for the +5.22 px
normal offset. Its `rot` bounds were [-119.6, -107.6], which EXCLUDED the
measured value; they are now derived from the new axis.

Together with len 132 -> 100, height 12 -> 9 and peak_at 0.62 (the ray carried
1.8-3.0x too much light beyond r 70 and reached too far -- the reference is at
0.29 of its peak by r 100 where the model held 0.67):

    MAE 1.8861 -> 1.8822    centre-region MAE 8.015 -> 7.944
    upper-left sector MAE 4.375 -> 3.325   (geometry alone gets it to 3.688)
    upper-left ray, as a fraction of the reference's: 1.69 -> 1.02

The lower-left ray is too SHORT and len goes 110 -> 124: bias-calibrated peak
ratios render/reference run 1.18 / 1.07 / 0.92 / 0.33 at r 76 / 88 / 100 / 112,
so the reference is still at half its peak where a len of 110 has gone out.
Beyond r 118 the reference is not detected at all, so the length is bounded above
by absence rather than by a fit.

**Recorded and not applied**, three times over. The lower-left ray's axis is also
about +4.5 degrees out with a compensating -7 px offset, but the whole correction
is worth 3.5% of its sector error and two contaminations inflate the apparent
drift -- `flare_flank_dl` sits on its clockwise side and reads 2.6-3.1 cv there
against a reference ray amplitude of 5.6-9.6, so a third of what the instrument
calls "the ray" inside r 70 is the flank. It does carry a genuine clockwise
shoulder (positive in all six radius bands, about 3.6 sigma combined), which is
NOT fitted: an earlier pass established that a narrow-plus-broad decomposition's
improvement on this image is inside what an injected single Gaussian already
yields on the noise. And the upper-left ray has no measurable asymmetry at all --
the third independent refutation of that claim.

**A precision limit that bounds every width number in this project.** The
acceptance renderer QUANTISES `blur`. On the upper-left ray, every value from
3.91 to 4.60 renders BIT-IDENTICALLY and the first change is at 4.75 (2 cv over
1176 px). The value this iteration ships, 4.5309, and the value it replaced,
3.9088, are the same artwork. So no width claim for this ray finer than about
+-0.4 px of blur is verifiable, and the optimiser's own blur step at this value
(0.12 x 4.5 = 0.54) is comparable to the plateau -- a fraction of its blur trials
are no-ops rather than rejections. This is a property of the renderer, not of the
search, and is recorded rather than worked around.

**One process finding, from the agent that measured this.** The baseline render
it was given was two commits stale: `scratchpad/base/render_1024.png` recorded
the SVG of an earlier commit, so the shared context quoted MAE 1.8978 where the
tree measured 1.8886. It found this by checking the provenance sidecar's digest
against the SVG -- the same mechanism this iteration repaired -- and quantified
the damage rather than ignoring it: upper-left centres unchanged to 0.05 px,
lower-left centres shifted 0.5-0.8 px, about a quarter of that ray's measured
drift. Its own numbers came from renders it built from the tree, so they stand.

## D52. The right rays are a redistribution error, and section 19's question has
## a different answer than it expected

**What the two angle numbers are.** `ray_report.RAYS` held 45.6 and 327.8;
`measure_flare.RAY_GEOMETRY` holds 44.9 and 328.1. They are different kinds of
number: the first pair are diagnostic sampling-window centres, the second are the
drawn quadrilateral axes -- and the two files do not even share an origin, since
`ray_report`'s CORE is 1.41 px from the params flare centre.

The brief offers a candidate explanation to test: that `flare_ray_c`'s 3 px
perpendicular offset, sampled by rays from the origin, produces a
radius-dependent apparent angle that reconciles them. **It fails the arithmetic.**
An offset s gives an apparent direction of direction + degrees(asin(s/r)), so
3 px gives +3.44 deg at r 50, +2.29 at r 75 and +1.72 at r 100 -- a mean of +2.4
degrees over the radii `ray_report` samples, which is EIGHT TIMES the 0.3 degree
gap between 327.8 and 328.1. An offset separates those two numbers; it cannot
reconcile them.

What settles it is that the old values were simply wrong, and the tool that used
them said so. Its own `ref angle` row on reference.png reads 44.0, 47.5, 45.2,
41.9, 55.1, 43.8, 31.3 for the upper-right -- no coherent angle at all -- against
a docstring claiming the peak "sits coherently at 45.6 and 327.8 degrees at every
radius". Measured with a transverse matched filter, the reference's upper-right
line lies -0.42 +- 0.28 px from the 44.9 axis over r 65-145 across 15 analysis
choices, which excludes 45.6 at about 6 sigma. Both scan angles now sit on the
layers' axes, and the false sentence is gone.

The general statement, which is what should outlive this entry: **an offset ray
has no single angle**, and any ray angle quoted anywhere in this project has to
name the origin it was measured from.

**Both right rays are too narrow, and neither is too dim.** This is the finding
that a per-radius amplitude reading gets backwards.

The lower-right: stacked over r 55-140 the reference and the render carry equal
flux (49.2 against 53.1 cv.px) but the render's core is too bright and too narrow
(peak 7.41 against 5.97, FWHM 7.25 against 7.75) and lacks the reference's skirt,
which is strongest on the counter-clockwise side. The signed error map shows the
shape of it directly: +2.7/+4.5/+3.3 cv at s = +1/+3/+5 for r 70-85, against
deficits of -1.8/-2.1/-1.5 at s = +7/+9/+11 further out. A narrow-template radial
reading instead makes the render look 2-3x too bright at r 95-150 and would have
led to SHORTENING the ray, which makes the picture worse. height 4.85 -> 7.0 and
the colour scaled 0.80 takes the lower-right corridor MAE from 2.0924 to 1.9882.

The upper-right is 1.8x too narrow -- reference FWHM 10.0 px against the render's
5.50, with broad wings that survive all eight matched nulls -- and badly wrong in
hue. height 4.0 -> 8.0 with the width to match takes its corridor MAE from 2.4166
to 2.0329.

**A layer whose colour was outside the colour model.** `flare_ray_e` shipped with
`color` = [0, 37.4, 11.2], i.e. B/G = 0.30, while its own white/cyan/blue
coefficients imply [0, 37.4, 39.8] and B/G = 1.064. The two disagree because a
measured hue outside the white/cyan/blue cone had been written straight into
`color`, where the renderer reads it, while the coefficients the photometric fit
reads and writes were left describing something else. That is a trap rather than
a trade-off: the artwork looks one way and the next `fit_photometry` run would
silently change it to the other.

The reference's upper-right hue is B/G = 0.84 +- 0.10, which is 1.6 sigma below
the cone floor -- so the cone is NOT broken on that evidence. The layer is moved
to pure cyan, which is in-cone, 2.3 sigma away by ratio, and gives the best pixel
error of the options tested. A regression check now requires every layer's stored
colour to be reachable from its own coefficients, comparing what the RENDERER
sees so that `flare_spike`'s deliberate above-255 encoding (which clamps to
white, and whose coefficients say white) is not a false positive.

    MAE 1.8822 -> 1.8806      centre-region MAE 7.944 -> 7.904
    upper-right ray, as a fraction of the reference's:  0.35 -> 0.54
    lower-right ray:                                    0.60 -> 0.66

**Confirmed and left alone.** `flare_ray_c`'s 3 px translation is right and must
not be revisited: removing it costs +0.42 corridor MAE and pushes the position
residual to +1.58 +- 0.19 px, while the two criteria bracket the true offset at
1.2 +- 0.4 px where the shipped value sits at 1.62. Both lengths survive --
upper-right ends at r 140 +- 15 and lower-right at 165 +- 20, so len 150 is right
and len 185 sits at the upper edge of what the data allows and must not grow.

**Two corrections to earlier precision.** D43 described the lower-right
reference and render lines as "PARALLEL (328.18 +- 0.21 against 328.40)". That
was over-precise: the direction is 327.3-328.1 and not resolvable further, the
two available criteria pick opposite ends of it, and D43's own fitted
ds(r) = 3.72 - 0.0126 r contained a -0.72 degree slope that "parallel" papered
over. And the upper-right note's "a continuation past r 150 is bounded at 11% of
the amplitude inside r 120" is too strong; the supported bound is 35-45%.

**Not measurable, and now recorded as such.** The right ridge costs the inner
ends of both rays entirely -- nothing inside r 48 (lower-right) or r 62
(upper-right) survives a 16 px clearance -- so `peak_at` 0.28 and 0.32, and any
`onset`, are carried on faith rather than on measurement. Forcing the estimator
inward gives a reference "profile" of 8.84, 7.23, 18.91, 14.14, 7.39 at
r 35..55 while the ray-removed control render reads -0.41, +1.49, +1.01, +0.20,
+0.77: contamination of the same order as the scatter, and an 18.91 next to a
7.39 is not a profile.

## D53. Chroma, multi-scale, and the two audits: what the last four dimensions
## added, including one finding this record nearly dismissed by mistake

**There is no global saturation defect, and the sign flip that made earlier
claims unreliable has an explanation.** Across every convention tried the
whole-canvas chroma difference is within +-2.5%, and at matched luminance all
three measures agree the render is slightly MORE chromatic. The flip that D42
recorded as irreducible is not between colour spaces: it is between ABSOLUTE
chroma (C*ab, max-min) and RELATIVE chroma (S, C*/L*), and it appears wherever
the render's luminance is also wrong. Conditioning on luminance removes it. In
this model's own cone basis the question has no ambiguity at all, because R is
white-only and so dWhite = dR exactly.

**The flare's colour error is an azimuthal quadrupole, not two radial shells.**
North and south of the core the render is too white; east and west it is too
cyan, at overlapping radii. The radial-only sign flips D42 reported are an
artefact of the ridge mask admitting different sectors at different radii. This
does not change D46's conclusion -- one isotropic layer cannot serve four
directions that want opposite corrections -- but it names the shape of the fix:
a white carrier whose profile runs along the east-west axis, not a recolouring.

**A finding this record nearly dismissed, and the reason it did not.** The
concave, lobe-facing flank of BOTH curves carries too much white primary at
essentially correct luminance. The first check of that claim read -4.09 cv, the
opposite sign, and would have refuted it. That check was wrong: its cell did not
exclude the flare, where the render is too DARK in R, and the flare's own error
swamped the curve's. Excluding r < 200 the same cell reads **+5.38 on the left
arc and +3.27 on the right**, against -0.00 and -0.54 on the centre-facing side,
which reproduces the independent measurement.

It is recorded rather than applied. Taking `arc_glow1` from white 0.37683 to
0.28 with cyan raised to 0.41 improves both the target (lobe dR +4.33 -> +2.79)
and the curve-band MAE (2.964 -> 2.938) and costs **0.0106 of whole-image MAE** --
a regression an order of magnitude larger than the gains this iteration shipped.
And the 5.38-against-3.27 asymmetry means no single symmetric value can correct
both arcs; honouring it needs the layer split per arc. Same structural fault as
the halo, in a different place.

**Nothing in the flare is a vectorised JPEG artifact.** A five-scale persistence
test (native, gaussian 1, gaussian 2, 2x, 4x) over every flare structure the
model has returns a negative result: every structure significant at native
resolution is also significant, with the same sign and comparable amplitude, at
all five scales. No thin ray should be removed on artifact grounds. The
reference's 8x8 grid is real, un-shifted, 0.65-1.10 cv, with no 16-px MCU
superperiod and no detectable chroma-subsampling footprint.

**But one piece of the model IS built on a clipping artifact.**
`flare_vline`'s tabulated factor-3.1 step at |dy| ~33 is not a feature of the
light: it is R's ZERO floor, 20-30% occupied over exactly those bands. In the two
unclipped channels the reference's line RISES across that boundary and peaks at
|dy| 36-70 -- precisely where the table puts its collapse -- and the model's
non-monotone tail bump at |dy| 80-100 is absent from the reference altogether.
The table is wrong in SHAPE, and the layer note now says so instead of offering
the step as the reason for tabulating. It is not retuned here because doing it
properly means refitting against G and B outside |dy| 26 and against R inside it,
with `south_gain` re-checked afterwards since the two are entangled.

**A correction to this iteration's own published numbers.** The comb-cell counts
were measured on a grid the optimiser never builds: `1024 // st` is 341 rows at
stride 3 where `Objective.evaluate` point-samples `[::3, ::3]` and gets 342. The
real counts are **51 / 53 / 45 / 45**, not 51/53/49/45. The conclusion is
unchanged -- the comb survives every stride the pipeline uses, with every |dx|
band represented -- but a check that measures a grid nothing uses is not a check,
and the figure is corrected here and in the source.

**Reported and not acted on**, each with the reason:

  * `tools/regions.py` maps a subsampled grid as if each sample were a box centre
    while `optimize.py` point-samples, a constant +1.5 px disagreement at stride 4.
    It is a weight-ASSIGNMENT error, not a residual misalignment: it changes which
    reference rows a comb cell owns, not where anything is drawn.
  * `measure_flare` does not converge on the shipped parameters -- the upper-right
    ray's measured peak settles into a period-2 oscillation straddling the
    tolerance band, so the tool exits 1 and its own advice to raise `--rounds`
    does not help. The convergence SEMANTICS are correct (that was the thing
    under review, and it passes); chasing the tolerance would be fitting the
    instrument's own discontinuity.
  * A weak east-only inner extension of line C, and an azimuthal colour split at
    r 30-65 that is an annulus with an east notch rather than a set of rays. Both
    are single-dimension findings with no independent confirmation.

**The evidence bar, stated once for the next iteration.** A cell mean counts as
evidence when it exceeds three times the robust scatter of the SAME cell at
matched-null positions at the SAME radius, and holds to within a factor of 1.5 at
both 2x and 4x downsample. The shared constant "tau ~ 8 px^2 per independent
sample" reproduces only in the far field: inside r 100 it understates the
correlation by 1.5x to 10x, so a sigma computed with it there is overstated by
1.1x to 3.3x. Use the matched-null cell scatter directly and skip the noise model.
Inside r 60 no amount of averaging buys sensitivity; the floor there is
systematic, about 6-13 cv in R and 3-6 cv in B.

## D54. What eight adversarial refutations changed, and the one defect the
## colour basis provably cannot express

Eight independent verifiers were asked to REFUTE the claims this iteration
shipped, each required to differ from the original method in baseline, statistic,
background model and channel treatment. Every one of them landed on artwork that
had already shipped, so this is an audit of the release rather than of a
proposal. Four parameters changed: one reverted because the argument that moved
it was an artefact, two shapes replaced because a fitted law was standing in for
a measurement, and one width refitted from a bound that had made its own minimum
unreachable. Two published precisions were widened. And one finding turned out to
be the largest single residual in the image and to be outside what the model can
say.

**The verifiers' own errors are recorded too.** Three of the eight measured
against `scratchpad/base/render_1024.png`, whose sidecar names an SVG four or
five commits old (MAE 1.8978 against the shipped 1.8806); their arithmetic was
sound and their conclusions were about a model that no longer exists. That is
what the render sidecar added in D50 is for, and it worked -- the staleness was
detected by reading the provenance, not by noticing that the numbers felt wrong.

### The core is not too tall, and it IS displaced -- but not where the claim put it

`flare_halo`'s squash went 0.6453 -> 0.62 on the argument that "the render's core
is too TALL", measured as an R half-width excess of 1.1-2.9 px north and south
*from each image's own peak* against a westward match. That argument does not
survive. Displacing the shipped render against ITSELF by (3.02 east, 0.70 north)
reproduces 71% of the claimed aspect contrast with zero model error; once the two
are registered, the remaining anisotropy is +1.4 to +1.9 cv at z 1.3-1.8. An
aspect measured from each image's own peak is not an aspect measurement when the
peaks are 3 px apart.

So squash goes back to 0.6453, the value two earlier iterations of fitting
produced. That is a REVERT on provenance, not a re-optimisation, and the evidence
for it is weaker than the evidence against 0.62's stated reason -- which is worth
saying plainly. Re-measured on the corrected model (spike profile fixed, halo
re-centred) with nothing varying but squash, 0.58 / 0.62 / 0.6453 give:

| statistic | 0.58 | 0.62 | 0.6453 |
| --- | --- | --- | --- |
| whole-image MAE | 1.87888 | 1.87817 | 1.87815 |
| flare r<110 MAE | 6.4775 | 6.4578 | 6.4574 |
| r<40 MAE | 9.847 | 9.656 | 9.610 |
| west angular residual RMS, 55 ridge-masked bins | 7.110 | 6.235 | 5.734 |
| r 20-40 red deficit, N / S, ridge-masked | -7.4 / -10.7 | -5.6 / -8.9 | -4.5 / -7.8 |
| white-radius ratio (1.0 = reference) | 0.872 | 0.872 | 0.897 |
| r 6-20 luminance excess, ridge-masked | +3.53 | +4.37 | +4.88 |
| core-box MAE, x 516-548 / y 500-530 | 5.963 | 6.121 | 6.328 |

Six prefer 0.6453, two prefer 0.58, and **0.62 is best at none of them** -- but
the first two rows are a tie to four decimal places, and on the twelve structural
ratios the split runs the other way, 0.62 closer to the reference on six and
0.6453 on three. Nothing here decides the value. What decides it is that 0.62 was
adopted on a measurement that turned out to be an artefact and no measurement has
since preferred it; a parameter moved for a reason that failed goes back. The
cost is recorded: `the bloom has not gone white` reads 0.930 of the reference at
0.6453 against 0.941 at 0.62, moving back towards that check's 0.90 floor --
though not past where iteration 5 sat, which was 0.925.

The two statistics that still want a SMALLER squash are both core brightness
rather than core shape, and their proper lever is `flare_halo`'s amplitude. That
lever was swept and left alone: scaling its white to 0.92 and 0.85 halves the
r 6-20 excess and costs whole-image MAE (+0.0009, +0.0026), the west angular RMS
(4.11 -> 4.51 -> 5.00 in that sweep's units) and the core r<30 MAE (9.277 ->
9.356 -> 9.723) at the same time -- the anisotropy wall again, one isotropic
layer serving two requirements that want opposite changes.

The displacement is real, and this is where the iteration's methodology earned
its keep. The claim was that `flare.cx` should move +2.9 to +3.0 px east and
-0.75 to -0.9 px north, and that "flare.cx maps onto the peak exactly 1:1".
Applied to `flare.cx` that is simply wrong: it drags all fifteen flare-anchored
layers -- the horizontal streaks, the vertical line, the four rays -- off
structures they are registered to, and costs 0.0131 of whole-image MAE (1.8806 ->
1.8937 on the model as it then stood) and 0.37 of flare r<110 (6.52 -> 6.90),
while moving the high-pass centroid only 0.5 px for a 3 px anchor move. The direction and the magnitude were
right and the VEHICLE was wrong. A ridge-masked sub-pixel translation fit says so
directly: it wants +3.00 east / -0.75 north at r < 10 in R, +2.00 / -0.50 at
r < 20, and +0.00 / -0.25 by r < 30. The compact peak is displaced; the bloom
around it is not.

So the correction went on `flare_halo`'s own `cx, cy` -- the layer that actually
makes the compact core, as ablation along the core row confirms (it supplies
86-105 cv there; `flare_halo_far`, `flare_spike`, `flare_vline` and
`flare_wash_far` supply zero). At +3.00 east / -0.75 north nothing gets worse:

| statistic | before | after |
| --- | --- | --- |
| whole-image MAE | 1.87836 | 1.87815 |
| flare r<110 MAE | 6.4632 | 6.4574 |
| core-box MAE, x 516-548 / y 500-530 | 8.087 | 6.328 |
| r<40 MAE | 9.856 | 9.610 |
| luminance excess at r 6-20, ridge-masked | +8.28 cv | +4.88 cv |
| east-west asymmetry, \|dx\| 2-7 (reference +14.50) | -16.13 | +6.68 |
| north-south asymmetry, \|dy\| 2-7 (reference -2.56) | +6.73 | -3.10 |

(measured at the shipped squash with nothing else varying.) The r 6-20 row is
the one to note: more than half of the "isotropic core over-brightness" that
survived the aspect refutation was itself the registration error.

The last two rows are the measurement that decided it, because they need no
registration at all: the same fixed x and y in both images, so there is no
per-image peak to get wrong. +3.00 is the largest correction that degrades nothing,
not the best fit. MAE and the flare annulus are slightly better at +1.50 and
+2.25 (1.87796 against 1.87815), the asymmetry alone wants about +4.2 px, and
+3.75 and +4.50 keep improving the core box (6.087, 6.006) and the east-west
match (+12.06, +16.61) while whole MAE turns (1.87849, 1.87906) -- the first of
those already worse than no shift at all. The cost that IS paid is in one
estimator family: `visual_regression`'s right-ray excesses read 0.540 -> 0.488
and 0.659 -> 0.623 of the reference, because the statistic subtracts the quieter
flank and the shift raises the background east. No ray parameter changed and the
rays' own axial light is unchanged to 0.04 cv, so this is the instrument moving,
not the artwork -- but it is a real reading and it is recorded rather than
explained away.

### A razor-thin line where the reference has none

`flare_spike` -- line B, the narrowest of the horizontal family -- carried an
`exp(-t/0.216)` longitudinal law, which peaks at the origin by construction. It
therefore put screen-domain `A*k = 0.39` on its row *at the core*, where the
reference puts 0.00-0.06. Over rows 519-520, x 517-538, the reference's R
declines monotonically 187.3 / 182.5 / 171.0 / 162.2 at y 518/519/520/521 with no
bump at all; the render rose to 213.2 and 208.6. That is a 31-38 cv bright bar
drawn straight across the core, and it is the kind of thing the instrument built
in D44 exists to show: whole-image MAE cannot see 220 pixels.

At |dx| 30-80 the same line matched the reference to 1-5 cv, so the amplitude was
right and only the shape was wrong. Measured as the screen-domain bump above the
linear trend through y 517 and y 522, the reference's own profile is
non-monotone on both sides and not the same on the two sides: west 0.055 / 0.168
/ 0.184 / 0.104 / 0.050 / 0.019 / 0.015 / 0.014 / 0.007 and east 0.020 / 0.000 /
0.092 / 0.115 / 0.113 / 0.067 / 0.032 / 0.019 / 0.002 at |dx| 3-12 / 12-20 /
20-28 / 28-38 / 38-50 / 50-65 / 65-85 / 85-110 / 110-140, peaking near |dx| 24
west and 35 east. Those two tables, divided by the 0.48 that converts profile to
delivered `A*k` in this stack, are now the layer's `profile` and `profile_e`.
Deleting the line instead is worse than either shape (row-band MAE 10.03 against
7.78 measured and 7.84 for the exp law), which is the control that says the line
is real and only its near-field was wrong.

### A width taken from a range instead of a fit

`flare_wash_far` -- the broad cyan pedestal under the horizontal line, added this
iteration -- shipped with `sigma_y` 14.0, taken from an estimate quoted as
"10-18 px depending on how the floor is set". A range is not a fit. Fitted over
the layer's own footprint (|dy| <= 30, 60 <= |dx| <= 300, both sides, ridges
masked at 22 px), sigma_y 8 / 9 / 10 / 11 / 12 / 14 gives footprint MAE 1.848 /
1.853 / 1.864 / 1.880 / 1.903 / 1.944, whole-image MAE 1.87779 / 1.87792 /
1.87817 / 1.87859 / 1.87920 / 1.88051 (that sweep ran before squash was reverted,
which shifts every one of those by about +0.00002 and reorders none of them), and
a skirt ratio (`visual_regression`'s own statistic, 1.0 = the reference) of 0.877
/ 0.930 / 0.974 / 1.008 / 1.035 / 1.087. 10.0 beats 14.0 on all three, including the skirt, which at 14 was
overshooting by 8.7% rather than falling short -- so the two instruments were not
in conflict at all, and the appearance that they were came from reading a ratio's
distance from 1.0 in only one direction.

The bound was the more serious fault: `sigma_y` was bounded [8.0, 24.0] with the
layer shipping at 14.0, so the search could not have reached the minimum. This is
the same class of bug as `flare_spike`'s `sigma_y` bound of 1.3 against a
measured 2.1-2.7 px FWHM, and the third time a bound has hidden a value this
project wanted. The bound is now [4.0, 20.0].

### Honest precision, twice

`flare_flank_dl`'s axis was published as "-240 +- 2". Three estimators that do
not share `wedge_report`'s binning put it at -239.6 (downsampled west-lobe MAE,
95% [-236.2, -244.2]), at a median -238.8 over 36 screen-domain
amplitude-marginalised template fits spanning -236.4 to -246.0, and at -243 +- 3
by whole-image MAE. The honest bracket is -240 +- 4, and the gain over the
previous -234 is 0.29 +- 0.18 cv of west-lobe MAE, which is 1.6 sigma. The
direction survives; the precision did not, and the note now says so. That the
layer belongs at all is the solid part: deleting it opens a +12.2 cv mean-RGB /
+22.9 cv blue hole at 4.0-7.4 sigma against a matched azimuthal null, flat to 4%
across all eight 8-px JPEG phases.

The same correction applies to the claim that the reference's horizontal line
sits on a pedestal the render "largely lacks out to |dx| 260". Re-measured
against the SHIPPED model rather than the stale one, the pedestal is carried:
the on-line minus off-line deficit in G now runs +1.0 / +1.0 / +3.0 / +3.0 / +1.0
cv at r 45-170 east and reverses beyond r 195, where the render is 1-2 cv
brighter on the line than off it. What is left is not an amplitude error at all.
It is a north-south asymmetry: over |dx| 60-110 west, above the |dy| 34-46 floor,
the reference carries 8.95 / 12.05 / 13.47 cv at dy -28 / -22 / -16 against 0.89
/ 5.39 / 9.65 at +28 / +22 / +16. A streak is symmetric in dy by construction; it
has `east_gain` and no `north_gain`. That is a named gap, not a tuning target.

### The defect the basis cannot express

West of the LEFT arc ridge, over roughly x 430-463 and y 460-560, the render is
up to 63 cv too dark in RED while green and blue match to within 10. Averaged
over x 443-461, y 479-533 the reference reads R 90.92 / G 172.47 / B 183.25 and
the render R 48.40 / G 171.12 / B 182.39: a 42.5 cv red-only deficit over about
1650 px, which is roughly 0.02 of whole-image MAE -- an order of magnitude more
than everything else changed this iteration put together. It is not the arc: at
the same ridge distance on the RIGHT arc the red residual runs -3 to +7 cv at
every station from y 340 to 700, and along the left arc itself it is zero outside
y 460-560. It is a flare-anchored lobe of warm light sitting outside the left
ridge at the core row.

Section 34 asks whether the current model is capable of representing the
requested structure. Here the answer is provably no, and the proof is short.
In the screen domain the cell needs its `u` multiplied by (0.794, 0.982, 0.983),
i.e. an addition of `A*k = (+0.206, +0.018, +0.017)` -- a colour whose G/R ratio
is 0.087. The reddest primitive the fitted cone has is pure white, G/R = 1.0
(D5): white is the only red-carrying primary and it carries at least as much
green. So the red cannot be supplied without also supplying about 17 cv of green
and blue the reference does not want.

The obvious escape -- remove cyan at the same station and add white -- was
followed to the end, and every version of it fails for the same reason: each
mechanism that can put light here also puts light where the render is already
right.

  * Ablation gives the cell's suppliers as `arc_glow1` (+25.8 R, +21.4 G),
    `arc_glow3` (0.0 R, +17.5 G), `arc_glow2` (0.0 R, +16.0 G), `flare_arm_w2`
    (+2.6, +13.5), `flare_halo_far` (0.0, +6.8), `field_mid` (0.0, +5.4).
  * Boosting `arc_glow1` to supply the red needs a factor 2.65, and its own
    cyan then overshoots green even with BOTH pure-cyan glows deleted: the
    green equation requires a factor 1.178 where the maximum achievable is 1.0.
  * Re-colouring `flare_arm_w2`, the one west-only layer that reaches the cell,
    requires a negative cyan coefficient (c' = -0.087) by the same algebra, and
    measured directly it costs 0.025 of whole-image MAE for 26 cv of the cell.
  * Deleting `arc_glow3` locally is the right SIZE of cyan removal -- it gets
    green and blue within 2% of what is needed -- but its taper is a function of
    y alone, and at the same y it also supplies 30-33 cv of green at x 400-432
    where the residual is +1 cv. Dipping the taper breaks that.
  * `arc_glow2`'s x-footprint west of the ridge does match the deficit, but it
    is one path with a width, so it is symmetric across the ridge and supplies
    14 cv east of the ridge where the residual is already zero.

A half-fix was costed and REJECTED. Solving the screen-domain algebra for the
best a pure-white lobe can do -- this is arithmetic on the cell's measured `u`,
not a render -- the optimum is `A*k` about 0.16, which would take the cell's
mean absolute error over the three channels from 15.1 to 10.9 cv, worth roughly
0.007 of whole-image MAE, at the price of making green and blue 10-11 cv too
bright over the same 1650 px: a measured red error traded for a manufactured
white patch where the reference is cyan. Section 44's rule
against claiming an improvement because one aggregate moved applies to the
author of the change first.

What would actually be needed is named so the next iteration does not rediscover
it: either an arc primitive whose cross-ridge profile differs inside and outside
(so light can be added on one side only), or per-station colour along a taper
rather than per-station amplitude, or a fourth colour primitive with k_G < k_R.
The first two are additions to `src/build_svg.py`; the third contradicts D5's
whole-image fit and should not be reached for on the evidence of 1650 px.

### Where the artwork ended up

MAE 1.88059 -> **1.87815**, SSIM 0.974039 -> **0.974081**, flare r<110 6.522 ->
**6.457**, r<40 9.785 -> **9.610**, core box 7.790 -> **6.328**. All 44 pipeline
checks and all 12 structural checks pass -- 33 at the end of the iteration's
own work, and eleven more added by the review rounds recorded in D55, D56, D57
and above. Five of the twelve structural ratios
moved towards the reference (the west field, line C, the skirt, the lower-right
ray and the white-core radius) and four moved away (the two right rays by 0.05
and 0.10 in opposite directions, the vertical line by 0.02, the cyan fraction by
0.01); line B moved away on purpose, because the ratio it reports includes the
bar this iteration removed from the core. The reasons are above, and none of them
is "the aggregate improved".

## D55. The audit's own blind spot, measured instead of disclaimed

`verify_searchable()` compares `bounds` entries against emitted specs. A review
raised the obvious limit: a numeric field that carries no bound is invisible to
it, so a parameter can stay frozen for a release without ever appearing in the
audit's result -- which is the same failure `flare_vline.sigma_x` shipped with,
one level further out.

The limit is real. The first instinct -- report every unbounded number -- was
tried and is worthless: **470 of the artwork's 609 numeric leaves carry no
bound.** A report that names three quarters of the model names nothing, and
nothing in the data distinguishes "deliberately fixed" from "should have been
searched and was forgotten".

What is checkable is the inventory. Every one of those 470 falls into exactly
twelve kinds:

| kind | leaves | why it carries no bound |
|---|---|---|
| `white`, `cyan`, `blue` | 105 | fitted photometrically, not searched |
| `color` | 105 | derived from those coefficients (D5), and checked against them |
| `profile`, `profile_e` | 202 | tabulated off the reference |
| `paint/profile`, `paint/stops` | 50 | tabulated off the reference |
| `paint/x1`, `x2`, `y1`, `y2` | 8 | frozen canvas gradient extents -- see below |

Eight of the twelve are searched by a different mechanism or measured rather
than fitted. The other four are the genuine instance of the reviewed class: eight
linear-gradient extents on `field_vert` and `exterior_top`, with no bound, no
spec and no mechanism behind them. `field_vert`'s `y1 = 34.4` / `y2 = 991.7` are
plainly fitted numbers that have not moved since.

**They stay frozen, and the reason is a measurement rather than a preference.**
Rendered at +-10 and +-40 px on each:

| | -40 | -10 | +10 | +40 |
|---|---|---|---|---|
| `field_vert.paint.y1` (34.4) | -0.00008 | -0.00003 | +0.00012 | +0.00010 |
| `field_vert.paint.y2` (991.7) | **-0.00051** | -0.00024 | +0.00006 | -0.00007 |

against a baseline of 1.87815. The best of the eight sweeps is worth 0.0005 of
MAE -- an order of magnitude below anything this iteration shipped, and below
the 0.003 variant that was rejected in D45 for improving an aggregate. Adding
them to the search space would also widen it after every published number here
was measured against the current one, for a return inside the noise. Recorded,
not taken.

The part that is not a preference is the guard. `test_pipeline.py` now pins the
inventory: the twelve kinds are declared with their reason, and a numeric field
appearing in a **new** kind fails the check. That is the case `verify_searchable`
structurally cannot see, so it is caught one level up instead of passing
silently. Verified not vacuous by adding an unbounded `falloff_exponent` to a
layer and watching it be named.

The general rule, since this is the fourth bound-or-reachability fault in this
project: **an audit that cannot see a class of fault should say so in a form
that fails, not in a docstring.**

## D56. The third answer to `--quick`, and two tools that accepted what they ignored

Three review rounds have now asked the same question about `validate.py --quick`:
it rewrites two of the five canonical rasters, so `out/` can hold renders of
different SVG generations, every one of them provably authentic.

The first answer **deleted** the three sidecars it did not rewrite. That is
worse than the problem: it turns a tracked artefact that can be verified into
one that cannot, and it makes a diagnostic run mutate files nobody asked it to
touch. Reverted.

The second answer recorded `rendered_sizes` in the report and the JSON and
called the rest stale. Better, but it has two faults. It hands the problem back
to the consumer -- you have to know what `rendered_sizes` means to avoid mixing
generations -- and **"left from an earlier run" was an assumption.** A raster
this run did not write is stale only if the SVG has moved since. If it has not,
it is exactly as current as the two just rendered, and calling it stale is as
wrong as calling it fresh.

The third answer checks. `carried_rasters()` reads each untouched canonical
raster's sidecar, which authenticates the PNG, and compares the `svg_sha256` it
records with the SVG this run validated. Four outcomes, each carrying its
evidence into `validation.md` and `validation.json`:

| | meaning |
|---|---|
| `current` | same SVG as this run -- safe to read beside the table |
| `stale` | authentic, and from a different SVG generation |
| `unverifiable` | a sidecar that does not describe the file beside it |
| `absent` | no raster there at all |

Nothing on disk is touched, which was the first answer's whole failing. All four
outcomes are exercised as a check, including `unverifiable`, which is produced
by appending four bytes to a render and leaving its sidecar alone.

This is the same move as D55 one layer down, and worth stating as a rule: **when
a report cannot be sure of something, the fix is to measure it, not to annotate
it.** `rendered_sizes` was an annotation. `carried_rasters` is a measurement.

### Two tools that accepted arguments they ignored

`flare_view.py` draws a two-column sheet. Given three or more images it took
`images[0:2]`, drew the first two and exited 0 -- so `flare_view.py a.png b.png
c.png` produced a wrong sheet that looks exactly like a right one, and `c.png`
never had to exist. Verified by passing a path that did not: exit 0, sheet
written, no complaint. It is now an `ap.error`, for the same reason `--labels`
became one: an argument the tool cannot honour is an error at parse time, not
silence at draw time.

And the CI workflow's header still described the two-outcome exit scheme that
D50 replaced -- "it exits 2 only in the second case" -- while the job's own
steps had been asserting exit 3 for a misconfigured browser since. The comment
was the last place the old model survived. Corrected, and the steps that assert
the codes are named in it, so the two cannot drift apart again without the job
failing.

## D57. What a digest does not prove, and a label that renamed half a sheet

Three defects, all of them in the verification machinery rather than the
artwork, and all three of the same shape: a check that was satisfied by
something adjacent to what it was supposed to establish.

### An authentic raster under the wrong name

`carried_rasters()` (D56) classifies the canonical rasters a `--quick` run did
not rewrite. It authenticated each one by hashing the PNG against its sidecar's
`png_sha256` and comparing the recorded `svg_sha256` with this run's SVG. Both
digests are about CONTENT, and the thing that was never checked is the only
part of the row that is not: the filename.

`render_256.png` is a claim -- 256 px, rendered by resvg -- and the sidecar has
recorded `size` and `renderer` since D50 without this caller reading either. So
copy `out/render_1024.png` and its sidecar to `render_256.png` and every digest
still matches: the file is authentic, the SVG is current, and the row said

    | `render_256.png` | current | same SVG as this run |

for a raster four times the resolution the table attributes to it. `current`
means "safe to read beside the table", so the one classification whose whole
purpose is to stop a consumer mixing generations handed it a different mix
instead. Verified by doing exactly that copy; the row read `current`.

`read_provenance` has taken `expect_size` and `expect_renderer` all along and
`publish.sh` passes both for the acceptance render. They are passed here now,
and the wrong-size raster comes back `unverifiable` with the mismatch named:
*records size=1024 where 256 was required*. The five canonical names are
written by `validate.py` and by nothing else, at one size each and always by
resvg, so there is no legitimate raster these expectations reject.

### A digest that is not a digest

A sidecar is arbitrary JSON. `read_provenance` tested its two digest fields for
truthiness and nothing else, and then used them: `want[:12]` in the mismatch
message, and `recorded[:12]` in `carried_rasters`' evidence column.

    "png_sha256": 1      ->  TypeError: 'int' object is not subscriptable
    "png_sha256": ["x"]  ->  slices quietly; formats into the evidence as ['x']

The first raised out of a function whose entire contract is that a sidecar it
cannot believe raises `ProvenanceError` -- so `validate.py --quick`, whose
answer for this is `unverifiable`, aborted instead of reporting. The second is
worse for being quiet: a list slices without complaint, so a malformed sidecar
was formatted into the report as though it were a measurement.

Shape is now checked where the value is READ rather than where it is formatted.
64 lowercase hex characters is what `hashlib` emits and what every sidecar this
repository writes contains; anything else is a malformed sidecar, and a
malformed sidecar proves nothing about the raster, which is a `ProvenanceError`
like every other sidecar that proves nothing. Four malformed shapes -- an int, a
list, a short string and a non-hex string -- are exercised as checks, on both
fields, and each comes back `unverifiable`.

### Half a sheet renamed

`flare_view.py --labels "previous,candidate"` renames the two inputs. It
substituted only panels 0 and 1, on the assumption that they are the only ones
naming an input. Four of the six do: every view's last two panels are the
enhancement pair -- `reference gamma 1/2.5`, `reconstruction high-pass x4`,
`reference chroma x9`. A full sheet is 9 rows of 6, so 18 of its 54 panels kept
`reference`/`reconstruction` while the plain panels above them said
`previous`/`candidate` -- two names for the same image, in the same column, on
the instrument the acceptance decision rests on.

The substitution was also chained, and `str.replace` re-scans its own output:

    --labels "reconstruction_a,reconstruction_b"   reference -> reconstruction_b_a

The first replace writes `reconstruction_a` and the second finds the
`reconstruction` inside it. Two names sharing a word is not exotic; it is how
most people spell an A/B pair. `relabel()` scans the label once and takes the
first match at each position, so neither name can be rewritten by the other, and
the default pair is a verified no-op.

### The four questions, and the one that was a defect

Four further observations were raised as questions rather than bugs. Three were
already the documented policy and are confirmed here, with where each is
written down. The fourth was real.

**Does a browser failure block a release?** No, deliberately, and it cannot hide
either: `publish.sh` treats exit 2 and 3 as non-blocking because the
cross-engine check is documented as optional, and prints `PUBLISH OK -- EXCEPT
the optional cross-engine check, which did not run` rather than `PUBLISH OK`.
`update_readme.py` emits the cross-engine sentence only when
`validation.json`'s `cross_engine` is non-null, so the README omits the line
rather than publishing a number nothing measured. A reviewer reading only the
last line of a release is not told a check ran when it did not.

**Does `--quick` require provenance-aware consumers?** Yes -- that is D56's
answer, not an accident of it. A quick run leaves rasters of several
generations in one directory, and rather than annotate that fact it measures
it: every carried raster is classified per file with its evidence, in stdout,
in `validation.md` and in `validation.json`. As of this entry the
classification also can no longer be fooled by a renamed file.

**Are the right-ray floors fidelity checks?** No, and
`visual_regression.py`'s module docstring says so under the heading PRESENCE,
NOT FIDELITY: the bands are gates against a structure disappearing, several
floors sit where the current artwork sits rather than where agreement would be,
the two right rays pass at 0.49 and 0.76 of the reference, and fidelity is what
`out/metrics.json` and `tools/diagnose.py` report. A green run means nothing has
vanished, not that the render agrees with the reference.

**Do the tests depend on committed artefacts?** They did, and that was a real
defect. The check for `compare.py`'s preconditions ran against
`out/render_1024.png` and `out/render_1024_chromium.png`, which makes a
statement about source behaviour depend on which artefacts happen to be on
disk: `out/render_512.png` and its two larger siblings are `.gitignored`, so a
check reaching for one of those would go red on a fresh clone with nothing wrong
in the code it exists to test. It now builds its own 64-px fixtures -- the same
bytes described once as resvg and once as chromium, plus one with no sidecar at
all -- and tests the same four preconditions without touching `out/`.

Whether the shipped artefacts are sound is a separate question, so it is now a
separate check that says so in those words: the three TRACKED rasters each hash
to their own sidecar and are named what they actually are, and the two resvg
renders must additionally be current with `reconstruction.svg`. The Chromium
render is deliberately not required to be current -- a release made without a
browser legitimately leaves it describing the previous SVG, and
`validation.json` is where whether it ran is recorded. Making it a gate would
contradict the optional-check policy confirmed two paragraphs above.

44 pipeline checks and 12 structural checks pass. No artwork changed: every
artefact regenerates byte-identically.

## D58. An expectation that was never a requirement, and a sidecar that was
## never an object

Two more in the provenance reader, both in code D57 had just touched, and both
the same shape as D57's three: a check that ran only when something unrelated
happened to be true.

### An expectation is a requirement

`read_provenance` returns None for an absent sidecar when `require` is false.
That is right -- provenance is optional for an ad-hoc render. But `require`
alone gated that return, and the three `expect_*` arguments are claims about
fields that exist ONLY in a sidecar. So a caller could ask for proof and be
told nothing:

    python3 tools/compare.py reference.png bare.png --expect-renderer resvg
    exit 0

It asked to be shown the raster came from resvg; it got metrics for unverified
bytes and a success code. Not a yes and not a no, which is the one answer a
precondition must never give. `tools/diagnose.py` had it identically, and both
were confirmed at the CLI before the fix. The D57 round wired `--expect-*`
through both tools without noticing the flags could be passed on their own.

The confirming run did the damage itself, which is the clearest statement of
the cost: `diagnose.py <scratch>.png --expect-size 4096` on a copy with no
sidecar exited 0, wrote the tracked `out/diagnostics.json` from that
unverified raster, and recorded `"source_svg_sha256": null` where the published
artefact names the SVG it measured. A published diagnostic that cannot say
which SVG produced it is exactly the failure the sidecar exists to prevent, and
the flag asking for that guarantee is what let it through.

Asking for an expectation is asking for the sidecar, so any non-None
expectation now requires one however `require` was left. The error names what
was asked rather than just what is missing:

    no provenance beside bare.png: it cannot be shown to have come from any
    particular SVG, let alone to satisfy expect_renderer='resvg'

With nothing asked of it an absent sidecar is still an absence -- that is the
case that had to keep working, and it is checked. Both CLIs now say `(implies
--require-provenance)` in `--help`, because a flag whose behaviour depends on
another flag being present is worth one clause.

### A sidecar that was never an object

D57 added a shape check for the two digest FIELDS. It did not check the shape
of the thing they are fields of. `json.load` establishes that the file is JSON,
not that it is a sidecar, and `[]`, `null`, `"x"`, `3` and `true` all parse:

    AttributeError: 'list' object has no attribute 'get'

raised from `_digest_field`'s own `d.get(field)` -- straight past the
`ProvenanceError` contract, and past the `carried_rasters` classifier, that
D57's field check was added to protect. `validate.py --quick` aborted with no
report at all where its answer is a row reading `unverifiable`. The root is
checked immediately after parsing now, and the message names the JSON type it
found rather than the Python one.

Twice in two rounds a malformed sidecar has escaped by being malformed one
level further out, so the lesson is the narrow one rather than a grand one:
**a check on a value is not a check on its container.** Five non-object roots
are exercised through `read_provenance`, four more through `carried_rasters`,
and one through `compare.py`.

### The two questions, unchanged

Both were raised and answered in D57 and neither has moved. `--quick`'s
provenance-aware output is D56's deliberate answer, not an accident of it:
every carried raster is classified per file with its evidence in stdout,
`validation.md` and `validation.json`. As of D57 that classification cannot be
fooled by a renamed file, and as of this entry not by a sidecar that is not an
object either. The right-ray floors are presence gates, and
`visual_regression.py`'s module docstring says so under PRESENCE, NOT FIDELITY
-- naming the 0.49 and 0.76 readings they guard, and pointing at
`out/metrics.json` and `tools/diagnose.py` for the fidelity question they do
not answer.

44 pipeline checks and 12 structural checks pass; this round added cases to
three existing checks rather than new ones. No artwork changed: every artefact
regenerates byte-identically.

## D59. A ray that was the right brightness and the wrong shape, and a line
## whose two halves were never the same shape

### Where the residual actually is

Before changing anything, the whole-image residual was binned by flare radius,
by angular sector, by distance to the nearer luminous curve and on a free 64 px
grid, and each bin was asked the only question that matters for choosing work:
how much whole-image MAE would a perfect correction along that coordinate
recover. Most of it is not recoverable at all. Splitting the residual into a
smooth part and a grain part at sigma 4 gives rms 1.775 smooth against 2.859
grain over the whole image, so a model that nailed every structure coarser than
4 px would take the residual rms from 3.54 to 2.86 and no further. The
reference's dark background is quantised to integers with visible contour bands
-- a flat interior patch is a field of 4s with a 3/4 contour running through it
-- and no vector model removes that.

Against that ceiling the levers rank: a perfect along-curve correction of the
arc corridor is worth 0.0177 of MAE, a vertical gradient over the exterior
0.0077, one over the interior field 0.0072, a per-ring correction of the flare
0.0026. The two largest single blocks of error are the arc corridor within 12 px
of either curve (16.4% of the total absolute error) and the flare's inner rings.

**A refit is not a free improvement, and this is worth knowing before reaching
for one.** Re-running `fit_photometry` on the shipped parameters moves several
layers and reports an analytic composite MAE of 1.8387 against the shipped
1.8782 -- and the real resvg render of what it wants measures **1.9177**. The
analytic compositing model and the renderer disagree by more than the entire
improvement on offer, in the wrong direction. The shipped photometry is better
than what the fitter would replace it with, so "just refit" is a regression and
every amplitude below was checked against the real renderer instead.

### The upper-right ray: the amplitude was right and the shape was wrong

`flare_ray_e` shipped at height 8 and read 0.491 of the reference on the
presence gate -- the deficit D52 raised from 0.35 and that D57's floors were
written around. Measured across the axis over r 55-95, with the corridor's own
ramp removed, the reference carries a plateau of 8-10 cv from s = -6 to s = +20
and the model covered s = -4..+6 and was at half by s = +10: 2-4 cv short over a
12 px band, which is a SHAPE deficit and not a dim one.

Four numbers change together -- height 8 -> 26, spread 1.30 -> 1.00, len 150 ->
143, and a 5.4 px offset along the ray's own normal -- and the ablation is the
result worth recording: **each of the four applied alone is worse than the value
it replaces**, on whole-image MAE, on the weighted objective, on flare-region
MAE and on the pooled transverse error alike. Widening without the offset
over-fills the clockwise flank; offsetting without the widening moves a
too-narrow ray off the structure. Together they take the pooled transverse error
over r 35-150 from 2.55 to 2.04 and the gate from 0.491 to 0.712.

The offset is measured, not fitted loosely: scanning it gives a parabolic
minimum at 5.37 px with everything between 4 and 6 px within 2% of the minimum,
and MAE, the weighted objective, flare-region MAE and the transverse error all
minimise in the same place.

**It does not contradict D52's line position, and that had to be checked.** D52
measured the reference's upper-right line at -0.42 +- 0.28 px from the 44.9
axis; a quad displaced 5.4 px looks like a flat contradiction. It is not,
because the offset displaces a broad low-amplitude slab and not the ridge:
measured identically on both images, the composite ridge moves +0.7 px over
r 65-125, inside the scatter. An offset structure and an offset ridge are
different claims -- which is D52's own general statement, applied to itself.

`len` moves to 143, the lower edge of the fitted 1-sigma band 143-166 that the
endpoint fit cannot distinguish from 150. It is chosen by the pixel evidence
inside that band, not against it. Notably it does the job that a `spread` below
1.0 would have done: the data that looked like it wanted a converging ray --
outside the model's cone, which requires the far end to be at least as wide as
the near -- is equally well explained by a shorter one, which is inside it.

**The amplitude was already right.** Refitting this layer's colour for the new
geometry prefers cyan 0.0933 unchanged over 0.79x and 1.15x of it. The extra
flux the wider quad delivers at the same colour is exactly what was missing,
which is the cleanest statement that the error was geometric.

**And the FWHM this layer was specified by is not a measurable quantity.** The
preset stored 10.0 px as the reference's transverse FWHM. With the corridor's
ramp fitted out, the reference reads 10.55, 15.06 and 1.41 px over the adjacent
20 px bands at r 55-75, 75-95 and 95-115: the stored number was one band's
answer presented as the ray's width. `RAY_GEOMETRY` now carries the width that
inverts back to the fitted blur and says in its comment that this is what it is.

### The vertical line's south was never a scaled copy of its north

`flare_vline` carried a single `south_gain` of 0.55, which can only say that the
southern half is a constant fraction of the northern. It is not. By A_4 in R and
G the reference's southern line is BRIGHTER than its northern one inside
|dy| 36 -- 14.05 and 11.35 over the 16-26 and 26-36 bands against 10.57 and 8.26
north -- and DIMMER outside it, 3.01 and 1.42 against 5.74 and 2.66. The render's
southern inner line read 9.42 and 6.23, short by 4.6 and 5.1 cv, and both of
`vstreak_report`'s estimators agreed: southern band error 2.86 rms against the
north's 1.10.

The `vstreak` primitive has carried a separate `profile_s` all along and this
layer never used it. The southern falloff is now its own table; `south_gain`
moves to 1.0 and stays as a residual scale. Southern band error 2.86 -> 1.22,
for +0.02% of the weighted objective and +0.0001 of whole-image MAE. The
innermost southern stop sits at opacity 1.0 because that is where it clamps:
1.0, 1.15 and 1.30 render identically, which is worth writing down so the next
pass does not read the value as a fitted optimum.

### Measured, and deliberately not changed

**The vertical line's north has the same kind of error in the other direction**
-- too bright at |dy| 16-36 (A_4 12.31 and 9.79 against 10.57 and 8.26) and too
dim at 36-70 (4.50 and 2.14 against 5.74 and 2.66). Correcting it improves every
band, 1.76 -> 1.16 rms, AND LOWERS `visual_regression`'s reading from 0.561 to
about 0.55, because that check pools |dy| 16-50 and the pooled number is
flattered by the inner excess. Moving the artwork and the guard that watches it
in the same step is the exact hazard that check's own docstring records about
its own predecessor. The north is left where it is and the gate's docstring now
names its blind spot; splitting it per band comes first.

**The arc corridor's convex-side shelf.** Both curves are about 10 cv too dark
at d = +5..+12 and about 3 cv too bright at d = -9..-15, consistently in all
four along-curve bands and on both arcs. It is not a displacement -- fitting a
shift and a gain per band leaves 65-99% of the residual in the arc body, and the
shifts are tiny (mean -0.05 px, |max| 0.34). It is not an amplitude oversight
either: the layer basis shows the render has an 11 cv step where the core's edge
dies at d = +4.5 and the reference decays smoothly through it. Raising
`arc_glow1b`, the only layer covering that band, fixes the corridor and spends
the gain in the flare, because that layer runs the full length of the arc
including where it passes within 14 px of the core -- so the correction has to
be localised along the curve, which is what tapers are for. Measured and left
for its own pass.

### What the numbers did

    MAE            1.8782 -> 1.8766        centre-region MAE  7.857 -> 7.770
    RMSE           4.0523 -> 4.0487        SSIM             0.97408 -> 0.97409
    upper-right ray, as a fraction of the reference's:   0.491 -> 0.712
    upper-right pooled transverse error, r 35-150:        2.55 -> 2.04
    vertical line, southern band error:                   2.86 -> 1.22

44 pipeline checks and 12 structural checks pass. Three checks had to be brought
along and each one earned its place: the geometry preset in `measure_flare.py`
is the table that `--geometry` WRITES, so a stale entry would have silently
reverted this work on the next run; the unbounded-kind inventory had to learn
`profile_s`; and the tracked rasters were stale the moment the SVG changed. The
full publish cycle passes end to end, `src/params.json` reproduces
`reconstruction.svg` byte for byte, and cross-engine agreement is unchanged at
MAE 2.680 / SSIM 0.95546.

## D60. A layer that carried one side of the curve and the other side's profile

D59 measured the arc corridor's convex-side deficit -- about 10 cv too dark at
d = +5..+12 on both arcs, in every along-curve band -- established that it was
neither a displacement nor an amplitude oversight, and left it. It said the
correction had to be localised along the curve. This is that pass, and the cause
turned out to be sharper than "needs a taper".

### The profile was not merely wrong, it was inverted

`arc_glow1b` exists to carry the **convex** side: it is inset -6 and peaks at
d = +5.5. It was given `arc_glow1`'s taper, which is the **concave** side's --
and that curve peaks where the arcs pass closest to the flare, because that is
where the concave lobe is brightest.

Measured in the taper's own coordinate, image y, the convex band d 5-14 wants
the opposite:

    y        160   200   240   280   ...   640   680   720   760   800   840
    err     -7.1  -8.3  -7.7  -3.9   ...  +0.6  -1.1  -4.8  -8.5  -9.7  -9.3
    cov     22.9  26.6  27.6  47.7   ...  87.1  76.0  59.2  45.3  34.2  16.7

The render is 7-10 cv too dark at the arcs' ends and, at y 440-640, 3-9 cv too
BRIGHT -- exactly where the borrowed taper puts its maximum. Solving for the
coverage the band actually needs gives **70-100 units, flat, from y 200 to
y 840**, against the 27 -> 135 -> 17 the borrowed taper delivers. The convex side
of these curves has essentially no along-curve taper over the arc body.

That also explains the failure recorded in D59: raising this layer's amplitude
alone fixed the corridor and spent the gain in the flare. It was not a trade
between two regions that both wanted light. The layer's taper was concentrating
it precisely where it was already in excess.

The fix is a `ramp` taper of its own -- flat between y 220 and 830, shoulders to
zero at 87 and 945 -- with the amplitude at 0.63 of what it was, since a flat
profile held at the old peak value would be far too much everywhere. Its inset,
width and blur were re-searched afterwards and all three were already at the
optimum, so the taper was the whole of it.

    cross-curve error at d = 5.5 .. 13.5, cv
    before   -11.3  -9.5  -7.6  -6.1  -5.1  -4.2  -3.5  -2.2  -1.0
    after     -2.7  -1.0  +0.2  +0.5  +0.1  -0.6  -1.2  -0.8  -0.4

### Why this is believed

It is a larger move than anything in the last several iterations -- 0.035 of
whole-image MAE, where D52 moved 0.0016 -- so it was checked the ways a
rasterisation artefact would fail.

**It holds at every resolution.** MAE at 256 / 512 / 1024 / 2048 / 4096 goes
1.718 -> 1.685, 1.797 -> 1.758, 1.878 -> 1.842, 1.872 -> 1.837, 1.875 -> 1.841.
A gain that existed only in the 1024 raster would not survive the downsampled
4096.

**It holds in the other engine.** Cross-engine agreement is 2.679 against 2.680,
and Chromium's own MAE improves 3.148 -> 3.126.

**It is visible.** On a crop of the left arc's southern body the broad blue band
on the convex flank -- the render too dark, over 10 px of the corridor -- is gone
from the signed difference, leaving the narrow edge dipole and the reference's
grain. Crop MAE 3.527 -> 3.086, bias -1.70 -> -1.08.

**No structure was lost.** All twelve structural checks pass with every ray,
line and core statistic unchanged to three decimals; only `the bloom has not
gone white` moves, 0.929 -> 0.928.

### Left alone, with the reason

**The concave side** is still 2-4 cv too bright at d = -9..-15 and 1-2 cv too
dark at d = -5..-7. Every lever was tried -- `arc_glow1`'s width and blur,
`arc_glow3`'s amplitude and inset -- and the shipped value is the MAE optimum in
all four; the sharpest, `arc_glow1`'s width, costs 0.018 of MAE at -20% and 0.025
at +22%. The concave stack is tightly balanced and moving it needs a joint refit,
not a one-parameter nudge.

**`arc_glow2b` looks about 4% too bright** -- at 0.96 both whole-image MAE and
the weighted objective improve. It is not taken, because the two disagree about
how much: MAE is best near 0.96 while the weighted objective keeps falling to
0.85 and beyond, where MAE is clearly worse. A photometric amplitude where the
two objectives point in different directions is a refit's job, not a hand-tuned
one, and picking the value that suits the published metric is the failure this
record has named before.

**The edge dipole at d = +2.5 / -3.5** is untouched and is not this layer's to
fix: it is the core stroke's sub-pixel edge placement, and it is what remains in
the crop above.

### What the numbers did

    MAE            1.8766 -> 1.8416        centre-region MAE  7.770 -> 7.641
    RMSE           4.0487 -> 3.9741        SSIM             0.97409 -> 0.97443
    bright-region MAE   9.502 -> 9.359     mean bias        -0.241 -> -0.185
    pixels off by > 8   4.92% -> 4.52%     off by > 24      0.778% -> 0.729%
    convex corridor MAE  4.013 -> 2.423    flare r<110       6.417 -> 6.308

`edge_iou` moves 0.6922 -> 0.6912, the one statistic that does not improve.

44 pipeline checks and 12 structural checks pass. The new taper's six numbers
are all inside `taper_specs`' bounds and reachable by `--spec tapers`, so the
next search can move them; the full publish cycle passes end to end and
`src/params.json` reproduces `reconstruction.svg` byte for byte.

## D61. The flare part by part: a false triangle removed, rays that miss the core drawn where they are, and a candidate's own overdraw caught before it shipped

This pass was confined to the central flare and judged against `reference.png`
alone. No frame, curve geometry or ridge was touched; the one change to a curve
layer is `arc_glow1`'s colour, split into a white and a cyan part (below), which
moves no geometry. Every change was set from a measurement of the part it
changes, and every candidate was compared with the reference AND the previous
release AND the previous candidate, with the picture in front of the numbers.

### The instruments

**`tools/ray_lines.py`: a ray as a 2D profile on its own line.** For each 8 px
band along a line, the transverse G profile is fitted by a Gaussian plus a
straight line (the curves' glow is a ramp at this scale). R and B are the
least-squares amplitudes of the same Gaussian, so hue is compared on the same
footing. The output is amplitude, ridge offset and width per band, for the
reference and the render read on the same line. The lines themselves were found
the same way: ridge centres per band, then a weighted TLS line through them.
Three of them do not pass through the core:

    ray              line of record                       from the core
    upper-left A     140.4 deg through (519.9, 526.9)     17 px
    upper-left B     149.5 deg through (518.0, 535.6)     26 px
    lower-left       255.2 deg through (524.2, 511.7)      7 px
    upper-right core  47.6 deg through (534.8, 517.0)      5 px
    lower-right      328.1 deg, ray_c's own origin (unchanged)
    lower-left 268 / 229 lobe / upper-left inner: through the core

**`tools/flare_parts.py`** puts reference | before | after side by side for each
named part (core, upper-left, lower-left, upper-right, lower-right, vertical,
horizontal east and west), plain and local-contrast-enhanced. The LCE row is the
one that shows what "too soft", "too sharp" and "invented" look like.

**`tools/visual_regression.py`, 12 -> 16 checks.** `ray_excess` samples a wedge
about the core, so it cannot see an off-core ray. The previous release had
nothing at 140-150 degrees and scored 7.50 there against the reference's 6.63.
The new line-following statistic compares the ramp-removed peak ON the measured
line with its own flanks. It reads the reference at 6.13 and that release at
0.06, and lines rotated 10 degrees read -2.4 to +1.5 on the reference. It gates
the upper-left pair, the upper-right core, and a short lower-left lobe that has a
CEILING as well as a floor. The lower-left ray's check moved onto its measured
line (reasons in the `RAY_AXES` note). The previous release now fails four
checks, the missing pair, the missing core and the missing lobe. This pass's own
over-drawn candidate fails two. The final render fails none.

### What the previous release had wrong

* **A false triangle west of the core.** `flare_flank_ul` and `flare_flank_dl`
  were straight-edged quadrilaterals fanning out of the core, and together they
  drew a triangular region the reference does not have. Both are removed, not
  dimmed. `measure_flare --geometry` used to RE-INSERT a missing flank from a
  template, which would have redrawn the triangle on the next geometry rebuild.
  The template is retired and `test_pipeline` fails if either id comes back.
* **The upper-left pair was missing.** Ray A reads, along its line at L 112-176,
  5.5 / 7.0 / 6.2 / 7.6 / 7.9 / 7.0 / 7.7 / 6.9 / 5.5 cv in the reference against
  -1.4 to +0.7 in that release. Ray B is broader and fainter, 8.6 / 6.7 / 3.3 /
  4.4 / 6.0 cv at L 92-124.
* **The lower-left was the wrong light in the wrong places.** The 250-degree ray
  was drawn through the core and too bright inside r 72 (11.5-14.8 against
  4.5-12.2). A short lobe at 229 degrees was absent (G 2.9-3.9 against
  13.2-13.4 at r 32-40). The 267-degree ray read NEGATIVE (-9 to -20 cv at r 36-60),
  because the wedge's dark flank sat on it.
* **The upper-right ray was a soft slab without its core.** On its line: 1.9
  against the reference's 4.14, width sigma 4.3-6.8 px against 3.2-4.8.
* **The lower-right ray was flat along its length.** Reference G 17.8 at r 44
  falling to about 4 by r 150, white near the core (R 12.6). That release had 6.1
  at r 44 and 9-10 out to r 110.
* **The line below the core was a pure-white hard stroke.** It rendered
  (255, 255, 255), 2 rows high and R-heavy (R/G/B increments 18.4 / 11.7 / 11.2)
  where the reference's line is 2.5 rows FWHM and near-neutral (18.0 / 17.5 /
  19.5). West of the left curve it drew a line the reference does not have.
* **The main line's east tail was twice too bright** past dx 90 (G 10.9 / 9.7 /
  8.6 at dx 93-123 against 7.8 / 5.5 / 3.3).
* **The arcs' outer flank had one colour for two jobs.** Decomposed into white
  and cyan, it was too white far from the flare (white -8 to -10, cyan +7 to +19
  cv) and too cyan near it (white +12 to +39).

### A candidate of this pass that was wrong, and how it was caught

The first complete candidate improved every global number (MAE 1.8416 ->
1.8322, flare r<110 6.31 -> 5.95) and was wrong in three places that only the
side-by-side and the line profiles showed:

* the new lower-left ray at 235 degrees was the most prominent structure in
  the lower-left: 3-6x the reference's lobe beyond r 25, 2.5x on the line
  statistic, and blue where the reference's is white-then-cyan -- an invented
  shape;
* `flare_ray_b` had been refitted 1.6x too bright and too blue (B/G 1.65
  against 1.28);
* `flare_ray_c` had been lengthened to 215, which the recorded extent 165 +- 20
  rules out.

All three came from colour and shape fits on a whole-image perceptual objective.
The fit moved light into rays that belongs to a broad glow, because the rays
were the levers it had. The fix was to fit each ray to its own measured profile
and give the broad light a soft layer of its own (`flare_glow_lens`). Measured
that way, the lens interior was 12-14 cv too dark in G at r 20-40 over theta
210-270 once the rays were right. The over-bright rays and the wedges had been
standing in for that light.

### What changed

    part            change                                                  measured on its line
    triangle        flare_flank_ul, flare_flank_dl removed                  west_flatness 0.785 -> 0.852 of ref
    upper-left      flare_ray_ula (A, narrow), flare_ray_ulb (B, broad)     A 0.01 -> 1.03, B -0.01 -> 0.98 of ref
    lower-left      flare_ray_b on its measured line + flare_ray_b2         G at r 56-104 ref 11.1..8.4, now 9.7..8.0
                    (plateau as two segments), flare_ray_llc (short         lobe: 0.22 -> 1.36 of ref
                    229-degree lobe, broad, white-tinted), flare_ray_lld
                    + flare_ray_lld2 (the 267-degree ray's two maxima)
    upper-right     flare_ray_ur: the narrow core on the measured line;     core 0.46 -> 0.95 of ref
                    flare_ray_e kept as the soft flank                      width 3.3-4.2 px (ref 3.2-4.8)
    lower-right     flare_ray_c_in: bright, white inner segment;            G r 44: 6.1 -> 15.0 (ref 17.8)
                    flare_ray_c refitted as the long soft tail (len 179)    R r 44: -> 10.1 (ref 12.6)
    core            flare_core_w (compact white, amplitude set by the       R r 0-4: 233.6 (ref 233.0)
                    core's own R ring means), flare_cloud_w (west cloud),   R>=200 extent W8 E17 N5 S5
                    flare_halo squash 0.645 -> 0.514                        (ref W8 E17 N4 S5)
    lens interior   flare_glow_lens: soft ellipse, cyan                     lens-core MAE 5.55 -> 4.94
    line A          side tables fitted along the row; flare_streak_w       R at dx -42: 24.4 -> 46.1 (ref 47.0)
                    carries the white beside (not on) the core              line A 1.26 -> 1.00 of ref
    line B          (154, 224, 255) not clamped white; sigma_y 0.4 -> 0.9;  2.5 rows FWHM, R/G/B 20.1/16.5/17.3
                    tails refitted                                          (ref 18.0/17.5/19.5); line B 0.71 -> 0.96
    arcs' colour    arc_glow1 split: cyan stays, white moves to             far-field white excess removed,
                    arc_glow1w on a taper along the curve                   near-flare deficit halved

### Deliberately preserved

* **The lower-right translation.** Its dx/dy offset was found to be translational
  and confirmed twice, and it was not revisited. Its direction stays 328.1: the
  TLS line through this pass's ridge centres reads 327.2, inside the recorded
  327.3-328.1 interval that the note says is not resolvable further.
* `flare_ray_e`'s geometry (D59's joint correction). The narrow core was added
  beside it, not substituted for it: the broad transverse profile matches within
  1 cv everywhere except the +2 cv centre bump that the core supplies.
* `flare_ray_a`: an intermediate refit had raised its colour 20%. The line
  profile showed that 1.25x too bright at r 44-76, so it was reverted to the
  release value.
* The vertical line, `flare_sat_long` (line C), `flare_fan`, `flare_arm_w` and
  `flare_wash_far` are all unchanged. Line C reads 1.16 of the reference before
  and after.

### What the numbers did

    MAE              1.8416 -> 1.8306        RMSE              3.9741 -> 3.9084
    centre-region    7.641  -> 6.987         pixels off by > 8  4.52% -> 4.45%
    flare r<110      6.308  -> 5.862         off by > 24       0.729% -> 0.660%
    lens-core        5.549  -> 4.944         weighted SSE      217407 -> 184786
    SSIM             0.97443 -> 0.97436      bright-region     9.359  -> 9.654
    core r<25        8.290  -> 8.337         edge_iou          0.6912 -> 0.6893

Three numbers get worse, and they are the same fact seen three ways. SSIM drops
by 0.00007, bright-region MAE by 0.30, and the core r<25 MAE by 0.05: all three
are dominated by the pixels next to the core. That is the cost of
`flare_glow_lens` there. It removes 1.25 of lens-core MAE and 0.33 of flare r<110
MAE, and removing it makes the core better (r<25 8.58 -> 7.54 on the candidate
it was fitted on) while every flare-region figure gets worse. It was fitted with
the core ring inside its objective. A hollow-centred variant, which puts no
light at all near the core, did no better (flare 5.94 against 5.89). The light
the lens needs and the light the core does not need overlap at r 10-25, and the
reference itself is 5-7 cv less cyan there than any of these candidates. That
excess predates this pass (see Remaining). `edge_iou` moves -0.002, which is
also where it moved in D60. The frame is untouched: frame MAE 2.505 before and
after.

### Remaining, with the reason

* **The core is smooth where the reference is lumpy.** R angular sd at r 8-12
  is 21.1 against the reference's 28.4 (17.4 before). The reference's white sits
  in spokes along the ray directions and in a mottled west cloud. The spokes are
  partly there: the lower-right inner segment is white, and the streak's white
  sits beside the core. The lumps are not modelled, because a lump drawn where
  the reference's JPEG happens to have one is an invented structure.
* **G/B at r 5-25 are 5-7 cv high.** The previous release had the same excess.
  Most of that ring is the right curve's glow (the ridge crosses at dx +15), and
  the curve is out of scope.
* **The 229-degree lobe runs about 8 px long** (G 9.4 at r 64 against 3.1). Its
  white near the core is not reproduced (R 2-4 against 11-19 at r 24-32). The
  ray gradient ties its tail to its peak.
* **The 267-degree ray's inner peak** (G 11.8 at r 44) has B/G 0.4-0.5, which no
  white/cyan/blue mix produces. The fit holds G below the peak rather than
  overshoot B.
* **The upper-right core** is 4.0-4.2 against 7.0 at r 90-98.
* **The upper-left inner ray stops early:** 1.9 against 5.3 at r 100.
* **Two older findings stand.** White east of the right curve near the core
  (D54) has no lever inside the flare. A narrow cyan deficit on the curves'
  outer flank at d -8 (+7-8 G) is not moved by any inset or colour sweep of the
  split pair.

## D62. The flare tools made consistent with the segmented rays, then eleven parts of the flare refined from their own measurements

Two stages, in that order. The first made the calibration, geometry and publish
tooling agree with the segmented ray model D61 built. The second refined the
flare one named part at a time, and only where a measurement of that part asked
for it. Two states were kept as comparison states throughout: the previous
release (main 5bedbfc, now `out/baseline/` with a digest manifest) and D61's PR
head (131a456). The reference is the only ground truth. Every change below was
set against line profiles, crops and difference images of the part it changes,
and against the part sheet (`out/flare_parts.png`). No global metric chose
anything.

Each part below separates **measured** (numbers read off the reference and the
render), **inferred** (what the numbers are taken to mean), **changed** (what was
done), and **uncertain** (what the evidence does not settle).

### Stage 1: the tools

**Calibration was one peak to one layer; it is now per line, per family, joint.**
*Measured:* the old `measure_flare` scaled one layer per ray to a pooled
chord-excess peak. For a ray drawn as two segments on one line, the scale moved
whichever segment held the peak and left the other. On D61's head, a verify pass
under the new measurement asked `flare_ray_lld` x1.195, `flare_ray_ur` x1.134,
`flare_ray_e` x1.113, `flare_ray_llc` x1.097 and `flare_ray_ula` x0.881.
*Changed:* a calibration family is one measured line (tools/ray_lines.py) plus
every layer that lights it. Each band's amplitude is read with the reference's
own template (s0, sigma) held fixed, which makes it a linear functional of the
image. All families' per-layer scales are then solved together by
Levenberg-Marquardt through the exact composite of the layer stack over the
measurement crop. Each round moves a layer by at most 3x and saves, and the
saved file is re-rendered in full and re-measured. It counts as converged when
the correction that re-measurement still asks for is within TOL = 0.08 in ln for
every layer. Otherwise the exit status is 1 and the corrections are saved anyway,
so a caller can tell a calibrated state from an uncalibrated one. A scale keeps
the layer's hue.

**The residual is luminance-first.** *Measured:* with R, G and B weighted
separately (R at half), a converged solve left several families' luminance
13-26% short: Y-gain 0.84 (upper-left A), 0.74 (upper-left B), 0.95 (267),
0.87 (upper-right). Those rays are greener than white/cyan/blue can draw (B
below G above the ramp), and the solve split that hue error by dimming them.
*Changed:* each band's residual is now Rec. 709 luminance plus the R-G and B-G
differences at 0.3. The chroma terms still tell a white segment from a cyan one
on a shared line. After the change every family's Y-gain is 0.90-1.02.
*Uncertain:* the B those rays carry is 6-31% high. That is the cone, not the
calibration (part 7).

**Bands inside another structure's glow are not the ray's.** *Measured:* the
first bands of both upper-left lines lie 20-36 px beyond the left curve's ridge,
inside its glow. There the model's curve error reads as a negative ray: -3.5 and
-4.6 cv at r 104 and 84, where the reference reads +2.3 and +2.9. The solve
brightened `flare_ray_ulb` x1.23 to fill a dip that is not the ray's.
*Changed:* FAMILIES carries `r_min`, 108 and 104 for those two lines.

**The geometry of record covers every ray, and `--geometry` no longer touches
bounds.** All 13 ray layers have an entry in `RAY_GEOMETRY`: rot, dx, dy, len,
onset, peak_at, tail, height, spread and blur. A ray layer without an entry,
an entry without a layer, a canonical value outside the layer's own search
bounds, or a retired flank id present are all errors that `--geometry`
refuses. The old version rewrote every ray's bounds to generic wide intervals,
which doubled `flare_ray_b`'s rotation window on every rebuild. A search space
is a different decision from a measurement, and it is now left alone.
test_pipeline perturbs every key of every ray, rebuilds, and requires an exact
restore with the bounds unchanged.

**The ray's fade has its own parameter.** *Measured:* the ray gradient put 0.42
of peak at `peak_at` + 0.35, a constant. A ray peaking at 0.62 of its length had
to fall from 0.42 to nothing in the last 3%, and a lobe whose peak sits right
could not also end where the reference ends. *Changed:* an optional `tail`
places that stop. Absent means 0.35, which rebuilds every earlier ray
byte-identically. It is part of the geometry of record and the optimiser's keys.

**The diagnostics refuse what they cannot read.** `ray_lines.py`,
`visual_regression.py` and `flare_parts.py` exit 2, and say why, on anything but
a 1024 x 1024 canvas. The line sampler raises instead of clamping to the edge;
clamping had turned a 512-px render into a column of plausible numbers.

**`out/flare_parts.png` is a publish artefact regenerated from verified inputs.**
Its "before" column is the previous accepted release, kept as its SVG plus a
manifest naming the commit and svg_sha256. `publish.sh` renders it, and
`tools/flare_parts.py` refuses to draw if the manifest, the baseline render or this
release's render does not match the SVG it is labelled as. Without `--svg`, the
header says the inputs are unverified.

**The global fits hold the calibrated rays.** `optimize.py` and
`fit_photometry.py` hold the rays' colour (CALIBRATED_LAYERS) and shape
(RAY_GEOMETRY) unless `--include-rays` or `--fit-rays` is given, and
`prune_layers.py` never offers a ray for removal. A whole-image objective is
what drew a lower-left ray 2.5x the reference in D61. `optimize_all.sh` runs
`--geometry` after the fits.

**Optimisation readiness, checked item by item against the regression gate:**
small-step refinement ("the search refines below its first step when a whole
step fails"); flare dependencies ("flare-dependent layers are discovered from
the builder", "moving flare/cx by 6 px moves every layer that does not pin cx");
provenance (four sidecar and staleness checks); validation semantics ("a quick
run says which carried rasters are current", and the CI exit-code steps); flare
cells at strides ("the flare comb cells survive stride 3 and stride 4");
photometric weighting ("the fitting weight equalises the profile cells and lifts
the flare", "the profile weight is keyed on the target"); profile cache
("content-addressed cache re-renders without an explicit invalidate"); isolation
("isolation recovers a screen contribution under a normal layer", "isolation
refuses orderings its algebra cannot express"). New in D62: calibration
convergence of the shipped file; one segment's correction not dragging the
other (a halved inner segment restored to the converged state, the outer held
within 0.04 in ln); a two-segment ray pushed apart (x0.5 / x1.6) and calibrated
back jointly; a calibrated file rebuilt through the documented commands to
within 0.01 cv of its calibrated profile; a non-converging calibration exiting
nonzero with its corrections saved; the global fits leaving calibrated rays
untouched; and the diagnostics refusing a 512-px input.

### Stage 2: the flare, part by part

    part (priority)        head (D61)                          final                          reference
    1 upper-left inner     G r 92-116: 7.9 1.9 -3.6 -3.4       7.1 6.2 4.8 3.4                7.0 5.3 3.7 1.9
    2 lobe 229, white      R r 24-48: 2.2 4.1 5.4 5.6          8.8 17.0 8.5 1.3               11.0 19.2 7.5 -0.7
      lobe 229, extent     G r 56 / 64: 10.7 / 9.4             3.8 / 1.5                      (fixed tmpl) 4.9 / 0.2
    3 upper-right core     G r 90 / 98: 4.2 / 4.0              6.8 / 6.2                      7.0 / 7.0
    4 lower-right          G r 60-84: 13.3 10.8 10.6 10.1      12.8 13.7 13.6 11.8            15.3 13.0 12.1 11.3
                           G r 108-132: 8.9 6.8 7.0 6.8        7.9 6.1 6.5 6.2                6.1 8.2 5.7 3.6
                           R r 52 / 60 (white): 9.6 / 5.6      5.0 / 3.5                      3.0 / 1.0
    5 vertical line, N     per-band rms A_4 R/G/B 1.37/2.87/5.33   1.15/1.98/3.93
    6 line C               rms 1.56 (east dx 95-150: 3.3-4.0)  1.21 (3.7-4.7)                 (3.9-4.8)
    8 near-core ring       G/B r 12-28 (not E): +6.2 / +4.6    +0.7 / -0.9
    9 curves, concave,     R -21.0 / -23.1 (right / left)      -6.8 / -5.9
      |dy| < 45            MAE 11.79 / 13.05                   9.31 / 8.53

(Line profiles by tools/ray_lines.py, each render read with its own fit;
"fixed tmpl" is the calibration's reading with the reference's template.)

**1. Upper-left inner ray.** *Measured:* the reference peaks at r ~60 (G 22.7),
is 0.42 of that by r ~90 and fades slowly to ~0 by r ~125 (7.0 / 5.3 / 3.7 /
1.9 at r 92-116). The head's ray fell from 0.42 of peak to zero between r 97 and
100. *Inferred:* the ray does not end early. It fades late and slowly, which the
fixed 0.35 fade could not draw at any length. *Changed:* its longitudinal
profile was fitted to the fixed-template amplitudes (peak 54 px, 0.42 at 89 px,
end 148 px). Its amplitude moved +4% (x1.04 in the fit, x0.999 in the joint
calibration). It was neither lengthened as it was nor brightened. *Uncertain:*
the reference's ray is ~15% wider than the model's (sigma 5.9 against 5.0,
pooled), with band-to-band scatter of 4.1-7.9. The width was left alone.

**2. Lower-left lobe (229 degrees).** *Measured:* the reference is WHITE at r
24-40 (R 11.0 / 19.2 / 7.5) and cyan at r 32-56, and gone by r ~60. The single
white+cyan layer put white along the whole lobe (R 5-6 at r 40-56) and ran
~10 px long. *Inferred:* one layer has one colour, so a lobe that changes
colour along its length is two segments on one line, the same pattern as the
lower-right's white inner segment. *Changed:* `flare_ray_llc_in` (white,
23-46 px, peak 30) and `flare_ray_llc` (cyan only now, 34-61 px, peak 41), on
the same line with the same width, fitted jointly in shape and colour.
Unconstrained, the fit collapsed both into short, strong blobs (a fade of 1.4 px,
the cyan at 3.4x its old amount). Each part of the profile was then held to at
least 6 px, which is below the 5 px blur's resolution anyway. *Uncertain:* at r 24 the model's G is
7.8 against 5.9. The core is bright there and part of that band is the core's
own structure.

**3. Upper-right core at mid radius.** *Measured:* the reference holds G ~7
from r 74 to 98 and is down to 4.5 by r 106. The core layer's 0.42-point was at
146 px of 151, which kept light at r 110-140 that belongs at r 90-98.
*Changed:* the core's onset (28 -> 46 px) and fade (0.42 at 146 -> 106 px) were
refitted, with its peak and end kept. Its colour amount rose x2.2 because it is
now lit over a shorter length. The flank `flare_ray_e` keeps D59's geometry; a
joint fit that also reshaped it gained nothing (cost 50.0 against 52.0) and
was not taken. *Uncertain:* r 98-114 is still ~1 cv low. The reference's sigma
there (4.8 at r 90) is wider than the core's.

**4. Lower-right tail.** *Measured:* 2-4 cv low inside r 84 and 1-2 cv high at
r 108-132 on the reference's template, with the far tail (r 148-172) if
anything below the reference (3.2-1.0 against 4.0-2.0). The white inner segment
still gave R 9.6 at r 52 where the reference has 3.0. *Inferred:* "slightly
long" is too much light at r 108-132 making the ray read longer, not light
beyond r 172. *Changed:* the tail's peak 53 -> 69 px and 0.42-point 116 -> 100
px, its end kept. The inner segment's peak 30 -> 42 px and 0.42-point 54 -> 50
px. The translation was re-checked at three radii: the reference's ridge sits
+0.45 / -0.95 / -1.15 px from the line at r 36-60 / 68-124 / 132-172. That is
flat beyond r 68, which a rotation cannot produce, and inside the 1.2-1.7 px
spread of centre definitions, so the line and its translation stand.
*Uncertain:* ray_lines reads R 13.5 at r 36 against 5.9. That band is where the
line crosses the right curve's concave side 16 px from its ridge, where
`arc_bloom_w` now sits (part 9). The pixels there are close to the reference (y
530, x 552-568: 118 / 108 / 94 / 73 / 45 against 134 / 115 / 92 / 70 / 47; D61's
112 / 93 / 69 / 48 / 33). It is the fit's window catching an oblique band, not
white on the ray.

**5. Vertical diffraction.** *Measured:* in the unclipped channels the
reference's line rises across |dy| 33 and holds to ~70 (G A_4 north 7.41 / 5.46
at |dy| 36-70 against the head's 5.20 / 2.96). The layer's tables had been
fitted in R, which is floor-clipped there, and collapsed at |dy| ~33.
`flare_vline`'s own note already said so. *Changed:* both tables' stops at |dy|
31-100 were refitted by bounded linear least squares on G and B A_4 and N over
|dy| 26-110, with R only inside |dy| 36. *Result:* north per-band rms falls in
every channel and statistic. South, G and B A_4 improve (2.19 -> 1.26, 2.16 ->
1.39) and R A_4 worsens (1.06 -> 1.92). *Uncertain:* the south line near the
core is whiter than one colour allows (R 11.4 against G 6.0 at |dy| 26-36), and
that is its remaining error. The pooled regression check "the vertical
diffraction is present" falls from 0.608 to 0.469 of the reference, inside its
0.45-2.20 band. Its docstring already recorded that correcting the northern
falloff would lower it. The band was not moved to make room.

**6. Lower horizontal lines.** *Measured:* line C, east side, dx +95..+240:
3.13 / 3.92 / 3.51 / 1.98 / 0.87 against 4.61 / 4.78 / 3.91 / 0.97 / 0.45.
*Changed:* `flare_sat_long` has its own east table, the west one compressed by
0.9, with east_gain 0.85 -> 1.10. *Left alone:* line C's west (no stretch or
gain improved it), and its near-core bins, where the bloom's vertical curvature
and the line cannot be separated. Line B was not changed (rms 1.16 -> 1.06 from
the core changes), and neither was line A (1.18 -> 0.95, same reason).

**7. The 267-degree ray's colour.** *Measured:* in the screen domain (alpha_ch =
dI_ch / (255 - flank_ch)) the reference's B/G on the inner segment is 0.61-0.92
at r 40-64. The flank's B is 86-135, far from saturation, and R increments of
1.3-1.8 argue against chroma subsampling as the cause. White/cyan/blue cannot go
below ~1.06. *Decision:* the basis stays. A green basis vector would fit this
ray and the three others that share the property, but nothing else in the
artwork needs one, and it reopens the invented-colour failure the cone exists
to prevent. With the luminance residual their strength matches; the cost is B
6-31% high.

**8. Near-core ring.** *Measured:* at r 12-28 the head's G/B were +6..+15 high
in EVERY direction: west +8.8, north +4.7, south +4.9, east +13.5. The ablation
put 46 cv of G in that ring from `flare_halo_far`, against ~12 from all the
curve glows together. *Inferred:* a ring the same size in every direction is
radial and the flare's. The right curve is east only. This corrects D61's
"most of that ring is the right curve's glow". *Changed:* `flare_halo_far`'s
exp law is kept verbatim beyond r ~39, and its six inner stops were refitted to
the unclipped G and B at r 10-44 outside the curves. That leaves +0.7 / -0.9
outside the east. Its centre stop (r < 8, clipped white in both images) is a
monotone extrapolation, because nothing there can measure it. *Not changed:*
the white core's shape. West, R is +14 cv at r 40-56 from the overlap of
`flare_halo`, `flare_cloud_w` and `flare_fan`. North-west and south, R is 10-17
short at r 12-28. A radial refit of `flare_halo` was ill-conditioned
(non-monotone stops, rms 5.54 -> 5.17). Shrinking `flare_cloud_w` traded the
west's outer excess for an inner deficit (score 13.9 -> 13.2, north-west r 14-28
-12.7 -> -16.0). The direction-dependent residual is recorded, as D61 recorded
the lumps.

**9. The curves near the flare.** *Measured:* both curves are whiter on their
concave side within ~40 px of the core row: R 20-59 cv short at 3-18 px from
the ridge. On the left curve, 66 px from the core, it is as large as on the
right. *Inferred:* the light is the curves', not the flare's. It is D54's "white
east of the right curve", which had no lever inside the flare because it never
was the flare. *Changed:* `arc_bloom_w`, a white glow 16 px toward the concave
side, 8 wide, blur 4, flat over |dy| 15 and gone by |dy| 55, fitted over both
concave sides (rms 10.19 -> 8.28; the fit wanted no cyan). *Uncertain:* the
right side needed a hue shift more than more light. After the bloom, its
concave side is +4.4 in luminance where it was even (R -9.2 -> -2.1 over offsets
3-30). A separate right-side amplitude would gain 0.10 MAE, which does not pay
for another layer.

**10. Saturation.** Region by region, reference / final (HSV S, chroma
max-min):

    core r<12          0.210 / 0.220   49.4 / 52.0   (D61 head 0.233 / 56.5)
    ring r 12-40       0.720 / 0.704   116.5 / 112.3
    flare r 40-130     0.955 / 0.935   73.9 / 71.6   R 3.4 / 5.5
    arc glow, convex   0.858 / 0.864   arc glow, concave 0.862 / 0.857
    lens, |dy|>130     0.887 / 0.893   outer field 0.876 / 0.895

*Inferred:* no region is globally under- or over-saturated. The core's excess
chroma was the cyan ring (part 8), and it is mostly gone. The arc ridges clip in
20.5% of the reference's pixels against 3% of the render's, but round-tripping
the render through JPEG at q90 raises that to 13%. Most of that clipping is the
reference's compression overshoot, not colour. The one local shortfall is the
mid flare's R, +2.1 cv (5.5 against 3.4), weighted west. It is spread over
`arc_glow2b`'s white term (+1.8), the field gradient (+1.0) and the white core
layers. *Decision:* no global boost, and no change there: no layer is
responsible, and the fix would be a curve-colour change far outside the flare.

**11. Core mottling.** *Measured:* in the core box (r > 12, streak rows and the
vertical line excluded), the reference's 8-px blockiness is 1.30 / 1.41 / 1.38
in R / G / B. The render reads 0.91-0.95, and recompressing it at
q95 / 90 / 80 / 70 / 60 reaches 1.31-1.43 only at q60. The reference-minus-render
residual is grid-aligned (blockiness 1.50-1.57), most strongly in luminance
(1.62). Its chroma part is less so (Cb 1.13, Cr 1.20) and carries ~2 cv RMS at
4-8 px in R-Y. *Classified:* the block-scale mottling is JPEG (quality ~60 or
several generations). What remains is a weak, partly grid-aligned white texture
at 4-8 px, probably real light: D61's lumpy west cloud. *Decision:* neither is
vectorised. The first is noise, and the second could only be drawn as invented
lumps.

**Found on the way: upper-left B's width.** *Measured:* beyond r 104, where its
line is clear of the curve's glow, the reference's sigma is 3.6-4.1 in every
band. The model's was 5.3-5.9 (height 10, blur 4.0). A ray too wide for the
fixed template reads low and is calibrated too bright: it came out at 1.5x the
reference's peak. *Changed:* height 6, blur 3.2 (sigma 3.5-4.0). The 267-degree
inner segment's width was scanned the same way and left alone: its line is 2 px
from the vertical line, which contaminates the fit, and the shipped width is
among the better ones.

### What the numbers did

    measure                 previous release   D61 head   D62
    MAE                     1.8416             1.8306     1.8149
    RMSE                    3.9741             3.9084     3.8321
    SSIM                    0.97443            0.97436    0.97450
    MAE, display curve      5.406              5.366      5.346
    centre region           7.641              6.987      6.364
    flare r<110 (diagnose)  6.30               5.85       5.44
    core r<25               8.305              8.362      6.474
    flare box MAE / SSIM    4.177 / 0.96449    3.979 / 0.96556   3.801 / 0.96710
    pixels off by > 8       4.52%              4.45%      4.37%
    pixels off by > 24      0.729%             0.660%     0.544%
    edge_iou                0.6912             0.6893     0.6933
    bright region           9.359              9.654      9.663

SSIM, core MAE and edge IoU, the three that got worse in D61, are now better
than both earlier states. Bright-region MAE is not. All of its excess over the
previous release lies on the curves beyond r 200 (|dy| 150-520). That is D61's
curve-colour split, which this pass did not touch (+0.009 against the head);
inside r 200 it improves. The frame is untouched (frame MAE 2.505 before and
after). All 16 structural checks pass.

### Remaining, with the reason

* **Rays greener than the cone** (part 7): B 6-31% high on the 267-degree ray,
  upper-left A, the upper-right and the lobe.
* **The white core's shape** (part 8): west R +14 at r 40-56, north-west and
  south -10..-17 at r 12-28. It is not a radial error, and there is no evidence
  for a particular lump.
* **The south vertical line near the core is whiter** than its one colour
  (part 5).
* **The right curve's concave side near the core is now slightly bright** (part
  9). It needed white instead of cyan, and a screen layer can only add.
* **Line B near the core** reads 22.0 against 24.6 at dx -36, and line C's
  near-core bins are not separable from the bloom's curvature (part 6).
* **The mid flare is +2 cv in R** (part 10), spread over several layers.
* **The upper-left inner ray is ~15% narrower** than the reference's pooled
  width, and the **upper-right is ~1 cv low at r 98-114** (parts 1 and 3). In
  both the reference's band-to-band scatter is comparable to the difference.

## D63. Four tooling defects fixed before any tuning; then the core's white arms, the lower-right tail, the 229-degree lobe, line B and one ray's hue

Two stages, in that order. The first fixed four defects in the flare tooling
that a review named, and proved each fix with a regression check before any
visual work began. The second refined only the flare parts that were still
wrong by measurement. Three states were compared under identical conditions:
the previous best (D62's head, baecddf), the tools-only state after stage 1
("D63-B"), and the final state. The reference is the only ground truth, and no
global metric chose anything.

Each visual decision below records the **evidence**, the **alternatives** tried,
the **action**, its **measured** and **visible** effect, and what stays
**uncertain**.

### Stage 1: the tools

**1. `--geometry` could not put a ray back where it was measured.** The review
said `--geometry` restored only four of the rays. On D62's head the record
already listed all 13, so that was not the defect. The real defect was
underneath it. The record held each ray's origin as `dx`/`dy` *relative to the
flare centre*, and the optimiser's geometry stage searches `flare/cx,cy` over
+-30 px. A search that moved the centre therefore moved all 13 rays off their
measured lines. `--geometry` then restored the relative offsets, so it could
not bring them back. The record was also missing keys the builder reads:
`cx`/`cy`, a ray's own origin. *Changed:* the geometry of record is now every
key the builder reads for a ray: `rot, cx, cy, dx, dy, len, onset, peak_at,
tail, height, spread, blur`, with their meanings stated in
`tools/measure_flare.py`. Every ray's origin is absolute: its measured foot in
canvas pixels, pinned by `cx`/`cy`, with `dx`/`dy` absent. A ray pinned that way
is not flare-dependent, so the flare-centre search no longer touches it.
`apply_geometry` writes or removes every key and never touches bounds.
*Regression:* every key of every ray (now 15 rays, 180 perturbations) is
perturbed and must be restored exactly, with every ray's bounds unchanged. A
3 px flare-centre move must change no ray's render, and an out-of-bounds
canonical value is refused.

**2. An onset the builder could not draw.** `onset` is where a ray starts to
fade in and `peak_at` where it peaks, both as fractions of `len`. The builder
clamps the onset to 0.95 x `peak_at` and the 0.42 stop to 0.999 of the length.
`flare_ray_b`'s record held onset 0.4463 against a peak of 0.4011, an onset
after its own peak. It rendered clamped at 0.381, a hard start at 36 px, so the
stored value described nothing anyone saw. *Changed:*
- `profile_problems` reports any onset or tail past a clamp, in the record and
  in the shipped layers. `--geometry` refuses such a record.
- The optimiser's sweep skips a trial past a clamp, since such a trial can tie
  but never be drawn.
- The two lower-left segments were refitted on their line with every stop
  reachable, against the rendered profile rather than the JSON inequality:
  - inner: onset 24, peak 38, 0.42 at 72, end 119 px;
  - outer: onset 50, peak 97, 0.42 at 135, end 149 px;
  - band error 159 -> 49 on the reference's templates.
- Two tails that the default 0.35 had put past the clamp were made explicit
  (`flare_ray_lld2` 0.2917, `flare_ray_ula` 0.349).

*Regression:*
- no clamped stop exists in the record or in the params;
- the builder's gradient for `flare_ray_b` carries the stored onset and peak;
- +-0.03 of onset inside its valid range changes the render, while two onsets
  past the clamp render identically;
- the D62 record is refused.

**3. The before/after sheet could go stale without anyone noticing.**
`publish.sh` already regenerated `out/flare_parts.png` (D62), so the review's
premise did not hold on the head. Nothing recorded what a sheet had been drawn
from, though, so a sheet left behind by a hand-run release could not be told
from a fresh one. *Changed:* every sheet gets a provenance sidecar
(`flare_parts/1`) holding:
- the sheet's digest;
- each column's image and SVG digests;
- whether the inputs were verified;
- the baseline manifest.

`flare_parts.py --verify` checks a sheet on disk against the current SVG and
baseline, and `publish.sh` runs it right after drawing. *Regression:* a fresh
sheet verifies, while a sheet checked against another SVG or with a byte
changed is caught. `test_pipeline` also verifies the committed sheet itself,
so a stale one fails CI.

**4. Calibration reused a stack whose geometry was stale.**
`calibrate(stack=...)` reused a supplied layer stack whenever the layer names
matched. After a geometry change, with the same names, it solved against the
old coverage. *Changed:* each layer's basis is fingerprinted by the digest of
its white basis SVG. A supplied stack is reused only for the same crop and the
same layers, and `Stack.refresh` re-renders exactly the layers whose
fingerprint changed. A colour-only change re-renders nothing, because colour is
not in the basis. *Regression:* after a ray is reshaped, exactly one layer is
re-rendered and the result equals a fresh stack's (difference 0). A x1.3 colour
change re-renders none and also equals. A stack for another crop is never
reused.

All four regressions and the rest of the gate passed before any stage-2 change
was made. The only failures were the two checks of published artefacts,
render_256 and the sheet's sidecar, which only a publish regenerates.

### Stage 2: the flare

    part                         measure                      D62               final             reference
    core, NW arm region          R / G / B minus reference    -17.6 -9.0 -10.2  +1.2 -0.5 -2.5
    core, S arm region           R / G / B minus reference    -18.5 -7.7 -9.7   +1.5 +0.8 -1.9
    core, 30-40 px west          R / G / B minus reference    +14.1 +6.0 +2.4   +7.4 +2.7 -0.7
    core, 2D bins r 2-64         mse (293 bins)               56.9              40.5
    vertical line, south         A_4 R / G / B at dy 20-28    11.2 9.2 11.1     14.4 9.9 11.6     14.9 7.5 10.2
    267 line, white              R at r 28                    8.7               13.8              15.6
    lower-right tail             sigma at r 132 / 140         5.0 / 5.8         3.8 / 3.9         2.6 / 2.5
                                 G at r 132 / 140             6.2 / 5.3         5.7 / 4.5         3.6 / 3.6
    229 lobe                     G / R / sigma at r 32        15.8 / 17.0 / 6.0 17.0 / 22.5 / 6.0 13.4 / 19.2 / 4.3
                                 G at r 24                    7.8               6.3               5.9
    line B, dx -36..-17          row difference (D35)         22.0              25.4              24.6
    line B, dx -32..-15          rms over 3 bins              6.3               2.4
    upper-left B hue             B/G at r 108-148             1.65              1.54              1.47

(Region means are smoothed at sigma 1.5; line profiles by tools/ray_lines.py
with each render read by its own fit. In D63-B, the lobe at r 32 read G 19.9,
R 26.9: see (c).)

**(a) The white core's shape: two white arms.**
- *Evidence:* the model's core was a horizontal white ellipse plus a round
  cloud to the west. The reference's core differs in four places:
  - it leans north-west, in a ridge through the core at 116.6 deg over r 13-27
    (R -18, G -9, B -10 against the reference);
  - south of the core it carries a broad white ridge 2-4 px west of the
    vertical line at dy +12..+28 (R about 90 at dy +20, FWHM about 10 px; R -19,
    G -8, B -10);
  - it is dark 30-40 px west, above and below the horizontal line, where the
    model had +14 R;
  - it is dark between the vertical line and the right curve at dy -30..-20.

  Both deficits are 12-15 px across, two to three JPEG blocks. They show in all
  three channels, so they are light rather than hue, and they are stable from
  sigma 1 to 4. The north-west one is radial through the core. That makes them
  structure, not compression. The south ridge is also D62's "south vertical
  line whiter than one colour allows": the line is one narrow cyan layer
  (sigma 1.7) and cannot carry it.
- *Alternatives:*
  - The west cloud reshaped alone, into a tall ellipse: the 2D bin error went
    56.3 -> 50.5, but the fit moved the cloud 19 px west and left both deficits.
  - Halo, cloud and compact core reshaped together (10 parameters): 47.5, core
    metrics better, both deficits unchanged. A radial layer cannot put light
    north-west and south without putting it everywhere between.
  - Two short white segments on the directions the residual shows. Unbounded,
    this fit ran to 1-px-wide arms at 2.7x full white, a colour no layer can
    have. Bounded (height >= 3 px, colour <= 255, north-west arm <= 36 px), it
    is what shipped.
- *Action:*
  - Two new layers, fitted with the radials' amplitudes on the core's 2D
    residual (4 px x 15 deg bins, r 2-64, the line cores and the right curve's
    ridge masked):
    - `flare_ray_a_in` at 116.4 deg from the core: onset 7, peak 21, end
      35 px, white 0.39;
    - `flare_ray_s_in`, vertical at x 526.1: dy +11 -> +29, peak +17, white
      0.52.
  - With them, `flare_cloud_w` became tighter and taller (r 40 -> 27.9, squash
    0.9 -> 1.19, centre 25 -> 22 px west).
  - `flare_halo` became smaller (r 92.4 -> 84.5, white 1.00 -> 0.87; its r
    bound 90 -> 70 to admit that).
  - `flare_core_w` carries more of the white (0.20 -> 0.76).
- *Measured:*
  - 2D bin error 56.9 -> 40.5;
  - core r<25 MAE 6.46 -> 5.45;
  - the checks that set `flare_core_w`'s old amplitude still hold: R mean at
    r 0-4 228.6 against the reference's 230.8, and R >= 200 extent W6 E18 N5 S5
    against W7 E18 N5 S5;
  - the arms' directions came out of the fit independently: 116.4 deg against
    the residual ridge's 116.6.
- *Visible:* the core's white leans up-left and reaches down, as in the
  reference, instead of a flat ellipse.
- *Uncertain:*
  - The arms are measured in 2D, not on a line, so they are not in a
    calibration family. Like the core's radials, their colour is free to the
    whole-image fits, while their shape is held (RAY_GEOMETRY) and prune never
    offers them.
  - North of the core, between the vertical line and the right curve, the model
    is still R +12 (+17 before). The reference is dark there, and a screen
    layer can only add light.
  - The vertical line north of the core (dy 12-20) reads A_4 11.8 / 8.7 / 10.0
    against 4.0 / 3.6 / -0.7. It is not the line: drawn at 10% of its strength
    there, it still reads 8.2 / 5.7 / 6.5. It is the glow's curvature, and was
    left alone.

**(b) The lower-right tail is a line, not a widening band.**
- *Evidence:* beyond r 128 the reference's ray is narrow: sigma 2.2
  [2.0..3.1] at r 136 across a 9 / 12 / 15 px window and a +-1 px line offset,
  and 3.2-4.4 at r 128-168. The spread-2.2 wedge measured 5.0-5.8 and carried
  2-4x the reference's light (amplitude x width) at r 128-144.

  Of the four suggested readings, it is **too wide**:
  - not fading too slowly: its peak amplitude is only 1-2 cv high;
  - not starting late;
  - not the wrong geometry: the translation was re-checked in D62 and kept.
- *Alternatives:* spread {1.0, 1.4, 1.8, 2.2} x blur {2.4, 3.1}, each with its
  fade refitted. 1.0 / 3.1 had the lowest fixed-template error (28.2 against
  32.4 for the old shape) and the lowest width error over clean bands (rms 0.78
  against 1.17). Dimming the whole ray was not considered.
- *Action:* spread 2.2 -> 1.0, blur 3.09 -> 3.1, 0.42-point 100 -> 103 px, end
  177 -> 185 px; the translation unchanged; calibrated (x0.99).
- *Measured:* sigma at r 132 / 140 5.0 / 5.8 -> 3.8 / 3.9 (reference 2.6 / 2.5);
  G 6.2 / 5.3 -> 5.7 / 4.5 (3.6 / 3.6).
- *Visible:* the tail reads as a thin line fading out by r ~150, as the
  reference's does.
- *Uncertain:*
  - At r 116-124 the reference is wider (6.5) and the parallel ray is now too
    narrow there (3.7).
  - Over the whole corridor the pixel error fell 2.87 -> 2.72 (most of it at
    r 60-100), but at r 120-160 it rose slightly (2.07 / 2.48 -> 2.31 / 2.63).
    The old wide tail had been filling a background that is 2-3 cv too dark in
    G across the whole east and south-east of the flare at r 120-180; the north
    at r 100-180 is 3-5 too bright. That asymmetry belongs to the far glow, not
    to this ray, and was not changed.

**(c) The 229-degree lobe was too wide where it meets the lower-left ray.**
- *Evidence:* at r 32 the lobe read G 19.9 and R 26.9 at sigma 8.0 in D63-B,
  against the reference's 13.4 and 19.2 at 4.3. Stage 1's refit of the
  lower-left ray gave it a reachable onset at r 24. At r ~30 that ray's inner
  segment lies 7 px from the lobe's line, inside the lobe's measurement
  window, so the two lines share pixels. Of the suggested readings, it is not
  length or falloff: it is width, the white segment's blur 5.0, plus that
  overlap.
- *Alternatives:*
  - Narrowing the lower-left ray at its foot (height 9.5 -> 6 or 4, the far
    width kept) was worse on both lines (error 34.1 -> 35.6 / 36.9).
  - Narrowing the white segment, blur 4.0 / 3.6 / 3.2, each refitted jointly,
    with 3.6 best (30.6).
- *Action:* the lobe's two segments and the lower-left ray's inner segment
  were refitted together on BOTH lines (shape and colour, luminance-first):
  - white segment: blur 5.0 -> 3.6, end 46 -> 42 px;
  - cyan lobe: peak 41 -> 40, end 61 -> 60 px;
  - lower-left inner segment: onset 24 -> 25, peak 38 -> 34 px.
- *Measured:* two-line error 40.8 -> 30.6. At r 32, G 17.0, R 22.5, sigma 6.0;
  at r 24, G 6.3 against 5.9 (D62 7.8).
- *Visible:* the lobe no longer spreads into a broad white patch south of its
  line.
- *Uncertain:* at r 32 the lobe is still +3.6 G and +3.3 R over the reference
  (D62: +2.4 G, -2.2 R). That is the price of the lower-left ray's reachable
  onset: the two lines' shared pixels cannot be separated further.

**(d) Line B near the core was too white and peaked too far out.**
- *Evidence:* the D35 row difference read 22.0 against 24.6 at dx -36..-17. In
  finer bins at dx -32 / -26 / -20 it read 23.6 / 22.1 / 17.8 against 20.8 /
  29.0 / 27.0. Read per 3-px column with a Gaussian over a quadratic background
  (the core's glow curves under the line), its R matched and its G was 30-45%
  low at dx -26..-14. The reference peaks at dx -23..-26, the model at
  -32..-35. So the line was too white and its fall-off too early, not wrong in
  amplitude alone, and not in width.
- *Alternatives:*
  - Colour only: the Gaussian read improved, 6.9 -> 6.1 rms, but the D35 read
    fell to 21.8.
  - A pixel-level fit of rows y 516-523: dominated by the glow under the line,
    it drove the line to a bluish white and was rejected.
  - Colour plus the near-core stops, on the Gaussian read: taken.
- *Action:* `flare_spike`:
  - colour w/c/b 0.60/0.29/0.11 -> 0.37/0.56/0.07;
  - its stops within 44 px of the core, both sides, refitted by bounded least
    squares;
  - sigma_y unchanged, so it stays a soft line, not the hard white one D35
    removed.
- *Measured:*
  - D35 read at dx -36..-17: 22.0 -> 25.4 (reference 24.6);
  - the three near-core bins: rms 6.3 -> 2.4;
  - whole line: rms 1.06 -> 1.05;
  - Gaussian-read G at dx -26..-17: 21.5 / 19.9 / 16.2 / 12.3 -> 32.7 / 32.6 /
    32.6 / 25.2 (reference 35.5 / 36.2 / 30.8 / 23.7).
- *Uncertain:*
  - On that read, R now overshoots by 8-10 at dx -20..-14, and the east side's
    R is 3-5 low at dx +38..+47.
  - The D35 read's bins at dx +47 and +70 fell 17.0 / 7.8 -> 15.9 / 6.9
    (reference 17.6 / 8.8).
  - The pixel rows around the line at dx -20 are 3-11 cv too bright in G above
    and below it. That is the core's glow, not the line.

**(e) Upper-left inner ray, width and 2D profile: preserved.**
- *Evidence:* the reference is wider at r 60-84: sigma 5.8-7.9 against
  4.6-5.1, robust in 4 of 6 bands to window and offset. Its profile along the
  line is bumpy: peaks at r 60 and r 84, the latter 14.4 [10.4..20.9] across
  variants.
- *Alternatives:* height 9 -> 12 / 15 and blur 4.5 -> 5.5 / 6.5, amplitude
  re-solved. At best (height 12) the width rms went 1.55 -> 1.38 and the G rms
  2.59 -> 2.56. Anything wider made G worse (up to 6.3).
- *Action:* none.
- *Visible:* none. At 4x, side by side, the wider variant is indistinguishable.
  What did read differently in this area was the core's north-west arm, (a).
- *Uncertain:* the reference's band-to-band width scatter (4.1-7.9) is as large
  as the difference.

**(f) Upper-right ray at r 98-114: preserved.**
- *Evidence:* G 6.2 / 3.9 / 3.5 against 7.0 / 4.5 / 4.5. The reference itself
  drops from 7.0 to 4.5 in one 8 px band. B there is 20-27% high (this ray is
  greener than the cone, see (g)).
- *Alternatives:*
  - Refitting the core's fade and the flank on luminance (0.42-point
    106 -> 118 px) took r 106 / 114 to 5.2 / 3.7. But the flank then carried
    more light near the core: flare MAE +0.02, core +0.13, corridor rms
    3.18 -> 3.46.
  - Widening the core (blur 2.5 -> 3.2 / 4.0) gained nothing at r 98-114.
  - Scaling the whole ray was not considered.
- *Action:* none.

**(g) The 267-degree ray's colour: the basis stays, and compositing is not the
cause.**
- *Evidence:* B/G above the ramp, amplitude-weighted over each line's clean
  bands, reference against model:

  | ray | reference | model | cone? |
  |---|---|---|---|
  | 267 | 0.85 | 1.04 | greener than the cone |
  | upper-right | 0.78 | 1.00 | greener than the cone |
  | upper-left A | 0.73 | 1.01 | greener than the cone |
  | 229 lobe | 0.74 | 0.83 | greener than the cone |
  | upper-left inner | 1.15 | 1.09 | bluer than cyan |
  | lower-left | 1.30 | 1.30 | bluer than cyan |
  | lower-right | 1.06 | 1.11 | bluer than cyan |
  | upper-left B | 1.47 | 1.54, after (h) | bluer than cyan |

  Four other causes were checked:
  - **Compositing, tested directly.** Suppose the reference was composited in
    linear light rather than on sRGB values. Then every band's implied colour
    moves. Over 75 clean bands the median B/G goes 1.07 -> 1.19 (IQR
    0.84-1.27 -> 0.91-1.45). The green rays stay green and the blue ones get
    bluer, so compositing does not explain them.
  - Chroma subsampling cannot make G exceed B out of a surround where B exceeds
    G (D62).
  - The weighting is luminance-first, and every family's Y-gain is 0.94-1.03.
  - Other components: B/G is read above each band's local ramp, so a broad
    background layer does not enter it.
- *Decision:* keep white/cyan/blue. A green basis vector would serve four of
  15 ray segments at 2-8 cv, while four others need the opposite direction. The
  cost stays as recorded: B 12-38% high on those four rays.

**(h) The upper-left B ray was too blue: fixed inside the cone.**
- *Evidence:* on its clean bands (r >= 104), B/G was 1.65 against 1.47, and the
  reference carries R ~1 on the ray.
- *Action:* colour refit, w/c/b 0/0.054/0.031 -> 0.009/0.043/0.026; calibrated.
- *Measured:* B/G 1.54, R 1.2 against 0.95.

**(i) Mid-flare red and near-core chroma: attributed.**
- *Measured:* the mid flare (r 40-130 between the curves, off the lines)
  carries R +2.1 in D62 and +1.5 now; r 40-80 carries +4.1 and +2.6.
- *Where it comes from:* the per-layer R there (the full stack minus the stack
  without the layer):

  | layer | R |
  |---|---|
  | `arc_glow2b` | 1.8 |
  | `field_grad` | 1.0 |
  | `arc_glow1w` | 0.5 |
  | `flare_halo` | 0.4 |
  | `field_base` | 0.3 |
  | `flare_fan` | 0.3 |
  | `field_vert` | 0.2 |
  | `flare_arm_w` | 0.15 |
  | `arc_glow1` | 0.14 |
  | `flare_cloud_w` | 0.1 |

  The flare's own white bloom was 1.5 of it and is 0.9 now; (a) tightened the
  halo and the cloud. The rest is the curves' glow (2.4) and the interior field
  (1.5). Both of those match the reference elsewhere: the curve glow's R is
  within 1.4 on both sides of the curves, and the far lens interior's within
  0.3.
- *Action:* none beyond (a). Taking white out of the curve glow or the field
  would turn their R low where it is right.

**(j) Saturation, compared region by region.** The model minus the reference.
Y is luminance and C is chroma (max - min of the region's mean); S, saturation,
is shown x100.

    region                       dY     dC     dS    class
    core r<12                   -1.3   +4.3   +1.8   clipping: 22% of pixels clip against 26%
    ring r 12-40                +1.4   -3.1   -1.2   chroma: R +1.6, B -1.5 (white bloom)
    mid flare r 40-130          +1.6   -2.0   -1.9   chroma + luminance: R +1.5, G +1.9 -- (i)
    upper-left rays             -0.5   -0.1   +1.0   none
    lower-left rays             +0.5   -4.0   -0.9   chroma: B -3.4 in the corridor; the rays' own hue matches (g)
    upper-right ray             +1.8   +2.3    0.0   luminance: G/B +2.3/2.5, the north's far glow
    lower-right ray             +0.3   +0.1   -0.6   none
    curve ridges                -2.4   +2.1   +1.1   clipping: 21% against 27%
    curve glow, outer side      -1.3   -0.9   +0.1   luminance
    curve glow, inner side      -0.7   +0.8   +1.8   chroma: R -1.4
    lens interior |dy|>130      -0.1   +0.2   +1.6   none (R 1.8 against 2.0)
    outer field                 -0.2   +0.2   +1.5   none (R 2.3 against 2.6)

  The signs disagree across regions: the flare's ring and middle are slightly
  less saturated, and the dark field and the curves' inner glow slightly more.
  A global saturation change would worsen half the table. The one systematic
  difference is the white in the flare's middle, and it is attributed in (i).
  *Decision:* no global change.

**(k) Core texture: which is JPEG and which is structure.** The two arms of (a)
are structure. They are 12-15 px across, in all three channels, stable across
smoothing, and one is radial through the core. The block-scale mottling D62
classified is compression: its 8 px blocks match the render re-encoded at JPEG
quality ~60. The weak ~2 cv residual texture at 4-8 px is still not vectorised.

### Limitations of the model that this pass ran into

- One layer has one colour, so a ray that changes colour along its length needs
  segments. The white arms of (a) are that pattern again.
- A screen layer can only add light. Where the reference is darker than
  everything the stack puts there, only removing light elsewhere helps: north
  of the core between the line and the curve, and the right curve's concave
  side near the core.
- The white/cyan/blue cone cannot draw rays greener than cyan (g).
- The far glow's asymmetry at r 100-180 (east and south-east too dark, north
  too bright) is a property of the whole flare's bloom. The single squashed
  radial `flare_halo_far` does not have it, and this pass did not change it.

### What the numbers did

    measure                 previous release   D62 (baecddf)   D63-B (tools)   D63 final
    MAE                     1.8416             1.8149          1.8147          1.8051
    RMSE                    3.974              3.832           3.832           3.816
    SSIM                    0.97443            0.97450         0.97450         0.97455
    edge IoU                0.6912             0.6933          0.6933          0.6944
    centre-region MAE       7.641              6.364           6.356           5.971
    flare r<110 MAE         6.309              5.452           5.445           5.178
    core r<25 MAE           8.280              6.460           6.450           5.446
    bright-region MAE       9.359              9.663           9.663           9.662

All 16 structural checks pass. "The vertical diffraction is present" reads
0.509 (D62 0.469).

### Remaining, with the reason

* **Rays greener than the cone** (g): B 12-38% high on the 267-degree ray,
  upper-left A, the upper-right and the lobe. The basis is the limit, not the
  compositing.
* **North of the core, between the vertical line and the right curve**, R +12
  (a). The reference is dark there, and a screen layer only adds light.
* **The vertical line north of the core** (dy 12-20) reads high in A_4; the
  glow's curvature, not the line (a).
* **The 229-degree lobe at r 32** is +3.6 G, +3.3 R where it shares pixels with
  the lower-left ray (c).
* **Line B**: R overshoots at dx -20..-14 on the Gaussian read; the east side is
  slightly low (d).
* **The lower-right ray** is now too narrow at r 116-124, where the reference
  widens, and the far glow around its tail is 2-3 cv dark in G (b).
* **The upper-left inner ray** is 15-30% narrower than the reference at r 60-84
  (e); **the upper-right** is ~1 cv low at r 98-114 (f). In both, the
  reference's band-to-band scatter is comparable, and every tried change cost
  more than it gained.
* **The mid flare** is +1.5 cv in R, from the curves' glow and the interior field
  (i).
* **Inside r 12 the core is slightly less white.** The flare's worst radial
  ring (the README's diagnostic) is now -2.1 cv at r 6-12; before, it was +2.4
  at r 30-45. R there is 4.0 below the reference, against 2.4 below in D62. The
  white that moved from the wide halo into the arms and the compact core left
  that ring a little short.
* **Bright-region MAE** is still D61's curve-colour split beyond r 200, which
  this pass did not touch.

## D64. A stale review finding checked first; then the core's west white, a fourth colour primary for four rays, the lower-right ray's soft flank, line B's white, the vertical line north of the core and the lobe's white segment

One review finding was checked against the current commit before any artwork
changed. Then the flare was refined part by part, each change local and each
judged on its own profile or 2D residual, never on a global metric. The
reference is the only ground truth. "Base" below is e9fa99c (D63's head);
"final" is this commit. Every candidate was rendered and measured under the
same conditions as the base.

As in D63, each decision records the **evidence**, the **alternatives**, the
**action**, the **measured** and **visible** effect, and what stays
**uncertain**. Nothing here is recovered source construction: every layer is a
model of what the reference shows, not a claim about how it was made.

### Stage 1: the tools

**1. The review's `flare_ray_b` onset finding is stale.** The review
(`tools/measure_flare.py`, lines 131-132) says `flare_ray_b` holds onset 0.4463
after its 0.4011 peak and renders clamped. That was true of baecddf, D62's head,
where those lines held the pair. D63 fixed it (D63, stage 1, item 2), and on
e9fa99c:
- the record holds onset 0.2123, peak_at 0.2871, tail 0.2713, all reachable,
  and `src/params.json` holds the same;
- the builder emits `flare_ray_b`'s gradient at offsets 0 / 0.2123 / 0.2497 /
  0.2871 / 0.5584 / 1, the stored onset and peak verbatim;
- +-0.03 of onset inside its valid range changes the render (D63's test);
- `--geometry` refuses a record holding the D62 pair (D63's test);
- the pair survives only in comments and in that test.

So no artwork was changed for it. *Regression strengthened:* D63's check
injected the pair into the RECORD only. It now also injects it into the PARAMS
and requires that `drift()` reports it and that `--geometry` repairs it: the
gradient's stops come back to the record's, and the render comes back to the
shipped one exactly (pixel difference 0).

**2. A fourth colour primary, TEAL (0, 1, 0.7), for the rays of record that
need it.** See (b) for why. `tools/fit_photometry.py` gains TEAL as a fourth
basis vector. `wc_from_color` decomposes a layer's colour over white/cyan/blue
unless the layer carries a `teal` key, and `fit()` holds the teal column at zero
on every other layer. `tools/measure_flare.py` names the six layers of record
(`TEAL_LAYERS`), and its `scale()` never gives a cone layer a teal amount.
Before any colour changed, every shipped colour decomposed identically under
the new code (to 1e-4 cv). *Regression:* every layer's colour must be reachable
from its own coefficients; no layer without a teal amount may leave the
white/cyan/blue cone; and the layers carrying teal must be exactly
`TEAL_LAYERS`.

**3. Two-colour lines stay one line.** Line A has carried its white in a layer
of its own since D61, and line B now does too, (e). A new check requires each
pair to share its row and length, so a search cannot pull one colour of a line
away from the other.

### Stage 2: the flare

    part                              measure                            base               final              reference
    line A west, dx -24 / -20 / -16    R minus reference (5x5 mean)       +16.8 +14.2 +8.1   +3.3 +3.2 +4.0
    core red, r 12-18                  mean |R residual| over 24 sectors  3.7                2.4
    four green rays                    B/G above the ramp (UL A, UR,      1.01 1.00          0.73 0.77          0.73 0.78
                                         267 ray, lobe)                   1.04 0.83          0.83 0.72          0.85 0.74
    lower-right ray, sigma             r 92-108 / 108-128 / 132-156       3.33 3.57 2.99     4.75 5.03 4.86     4.75 5.42 5.72
                                         (band-averaged, ramp removed)
    lower-right ray, flux              the same bands                     71 52 26           117 100 61         97 93 67
    line B, R/G                        dx -20 / -17 / -14                 1.10 1.23 1.35     0.82 0.86 1.02     0.93 0.88 0.87
                                       dx +17 / +20 / +23                 1.70 1.46 1.33     0.97 0.95 1.01     1.07 1.02 1.06
    line B, R                          dx -20 / -17 / -14                 33.4 27.8 17.5     28.2 21.5 14.3     28.6 20.9 14.5
    vertical line north, dy 12-20      A_4, R / G / B                     11.8 8.7 10.0      6.3 2.9 3.8        4.0 3.6 -0.7
    229 lobe                           R at r 24 / 32 / 40                6.9 22.5 5.8       10.3 19.1 3.9      10.3 19.2 7.5
                                       G at r 24 / 32 / 40 / 48           5.8 17.0 13.1 9.4  6.8 16.1 13.7 10.6 5.9 13.4 13.2 10.5

(Line readings are per column or per band, each image read with the same fixed
linear functional. The ray bands are tools/ray_lines.py's; line B's is the
reference's own row Gaussian above a quadratic background.)

**(a) The core: the contour was right; the white on the west line and the red
tail were not.**
- *Evidence:*
  - The core's R contour at six thresholds (230 to 80) and in 24 directions
    matches the reference within +-0.5 px in every direction, at every
    threshold that is not a line or a curve. The exceptions are where the east
    line joins the core (R >= 230 reaches 16.8 px east in the reference against
    5.6) and where the right curve's ridge crosses (315-330 deg). So the
    two-arm core of D63 is right and incomplete in only two places, and no
    white arm was added.
  - On the horizontal line west of the core the model carried R +14..+17 at
    dx -24..-20.
  - Beyond r ~27 the reference's red ends in a steep edge: west of the vertical
    line it falls 47 -> 9 -> 1 between dy +24, +30 and +36 (north: 34 -> 7.5
    -> 3). The model's red had a
    long tail there (+10..+13 at |dy| 28-32). Attributed layer by layer, that
    tail was `flare_cloud_w`'s exponential (its vertical e-folding was 17 px),
    the NW arm's end and the halo.
- *Alternatives:*
  - The core refit of D63 with the line band admitted to the fit and the cloud
    still exponential: line R +8.2 / +4.1 at dx -24 / -20, 2D bin error
    40.4 -> 39.1.
  - The halo's squash and centre, the fan's vertical sigma and the south arm's
    width and direction, fitted together: 38.70 -> 38.60, and nothing visible.
    The fit does not narrow the symmetric halo, because what it would take from
    the north it would also take from the south, where the reference needs it.
  - A Gaussian profile for the cloud, refitted with the core radials and arms
    (line band included): 2D bin error 38.7, taken.
- *Action:* `flare_cloud_w`:
  - profile exp -> Gaussian (sigma 0.29);
  - r 27.9 -> 25.5, squash 1.19 -> 2.03 (its bound widened to 2.4 to admit it);
  - white 0.38 -> 0.18.

  With it, the fan's white rose 0.48 -> 0.56, the compact core's fell
  0.76 -> 0.63, and the halo moved 0.3 px.
- *Measured:*
  - line R at dx -24 / -20 / -16: +16.8 / +14.2 / +8.1 -> +3.3 / +3.2 / +4.0;
  - the azimuthal |R residual| at r 8-12 / 12-18 / 18-25 / 25-32:
    3.7 / 3.7 / 5.5 / 6.5 -> 3.2 / 2.4 / 4.2 / 5.7. The fan's rise does not
    re-open the red ring its note warns of;
  - the west R >= 170 contour overshoot: +3.0 -> +1.0 px;
  - core r<25 MAE 5.446 -> 5.153.
- *Visible:* less white haze along the line west of the core. Side by side at
  5x, the core's size and the lean of its arms are unchanged, and there is no
  dead-white blob.
- *Uncertain:*
  - The R >= 230 area is 145 px against the reference's 214, most of it where
    the east line meets the core.
  - The ring at r 10 is R +5.0 north and +3.1 south (base +4.7 / +1.2).
  - The junction with the right curve (R -18 at dx +10) is the curve's
    concave-side deficit and was not touched.

**(b) Four rays are greener than white/cyan/blue can draw: a minimal fourth
primary.**
- *Evidence:* D63 (g) measured it: four rays read B/G 0.73-0.85 above their
  local ramp, below cyan's floor of about 1.06. A controlled experiment then
  refitted every family's colours by bounded linear least squares, on the
  calibration's own band cost (luminance plus 0.3 x chroma, summed over the
  eight families):

  | basis | band cost | what it uses |
  |---|---|---|
  | shipped | 171.7 | |
  | white/cyan/blue, refitted | 132.5 | |
  | plus teal (0, 1, 0.6 / 0.7 / 0.8) | 122.6-122.7 | changes hue only on the four green families |
  | plus green (0, 1, 0) | 122.6 | the same |

  On the bluer rays both solutions also used the new primary, but only mixed
  with blue into the colour cyan already draws: the same colour, decomposed
  differently. So teal and green tie on the evidence. They differ in what they
  PERMIT. With pure green a later fit could draw a ray of any B/G down to 0,
  far greener than anything the reference shows. Teal's floor, 0.7, is the
  greenest ray measured (0.73). The smaller extension was taken.
- *Action:* TEAL (0, 1, 0.7) is allowed on six layers:
  - upper-left A (`flare_ray_ula`);
  - the upper-right pair (`flare_ray_ur`, `flare_ray_e`);
  - the 267-degree pair (`flare_ray_lld`, `flare_ray_lld2`);
  - the lobe's cyan segment (`flare_ray_llc`).

  Their colours come from the least-squares solution, then the family
  calibration (converged). The lower-left and lower-right rays, the upper-left
  inner and B rays, and every white segment stay in the cone.
- *Measured:* B/G above the ramp, reference / base / final:

  | ray | reference | base | final |
  |---|---|---|---|
  | upper-left A | 0.73 | 1.01 | 0.73 |
  | upper-right | 0.78 | 1.00 | 0.77 |
  | 267 | 0.85 | 1.04 | 0.83 |
  | 229 lobe | 0.74 | 0.83 | 0.72 |

  In the +-5 px corridor, B's MAE went 3.10 -> 2.52 (upper-left A),
  3.51 -> 3.18 (upper-right) and 3.23 -> 2.83 (267).
- *Visible:* those four rays read green-cyan rather than blue-cyan; no ray
  changed brightness.
- *Uncertain:*
  - In the lobe's corridor B got worse (MAE 5.52 -> 6.25). Its flanks are
    already 4-7.5 B low, which is the far glow's error, not the lobe's. The
    lobe's own B contrast against those flanks now matches.
  - The 267 corridor is +4.6 G throughout, also background.
  - Whole-image metrics do not move. The rays are a few cv over a few thousand
    pixels.

**(c) The lower-right ray is a narrow line inside a soft flank.**
- *Evidence:* averaged over 16-28 px bands, with each band's ramp removed at
  |s| 16-22, the reference's transverse sigma grows:
  - 2.6 at r 60-88;
  - 4.75 at 92-108;
  - 5.4 at 108-128;
  - 5.7-5.8 at 132-184.

  It is identical after a 2x box downsample. The model's single narrow line
  stayed at 3.0-3.6 and carried 0.07-0.73 of the reference's flux there.

  D63 read the tail as narrow because the free-template band fit takes the
  flank into its ramp. So D61's widening and D63's narrowing were each half
  right.

  An unwrapped difference map adds a second, separate error: a corridor-wide
  G deficit of 2-5 beyond r 104, stronger on the north-east side. That is the
  far glow, not the ray.
- *Alternatives,* each fitted with the narrow segments' amplitudes in the same
  ramp-removed corridor, r 40-184:

  | model | error |
  |---|---|
  | narrow line alone | 3.50 |
  | the narrow line widened (spread, height, blur): a spread-3.6 wedge, D62's rejected shape | 2.68 |
  | narrow line plus a soft flank segment | 2.44 |

  Fitted over r 84-184 only, the flank came out 8 px north-east of the line.
  Over the whole line it sits on the line (0.6 px off) and is soft.
- *Action:*
  - A new layer, `flare_ray_c_fl`, on `flare_ray_c`'s line:
    - direction 329.4 deg, 1.3 deg off the line;
    - starts 81 px out, peaks at 93, is 0.42 of peak by 151, gone by 200;
    - height 8.0, blur 7.4.
  - It is in RAY_GEOMETRY, so its shape is held and `--geometry` restores it.
  - It is NOT in the calibration family. The family's fixed narrow templates
    cannot tell a flank from a line: calibrated jointly, the flank went to
    0.19x and the line to 1.34x, back to the old narrow ray, and the solve and
    its verification then disagreed by 7 tolerances. So the flank's amplitude
    is the corridor fit's, as the core arms' are the 2D fit's.
  - The family (inner segment and line) was recalibrated with the flank
    present: the line x0.89. The translation is unchanged.
- *Measured:* sigma 4.75 / 5.03 / 4.86 / 5.07 at r 92-108 / 108-128 / 132-156 /
  156-184, against 4.75 / 5.42 / 5.72 / 5.79. Flux 117 / 100 / 61 / 22 against
  97 / 93 / 67 / 33.
- *Visible:* the ray broadens and softens beyond its middle, as the reference's
  does, instead of running on as a thin line.
- *Uncertain:*
  - Per-band free fits at r 132-140 still read the reference as narrow (sigma
    2.6) and the model as 4.3-4.7 and 1.5-2x brighter on its centre. Two honest
    readings of the same pixels disagree there.
  - The flux at r 92-108 is now 20% high.
  - The far glow's deficit on the north-east side stays (section (i)).

**(d) The upper-right ray at r 98-114: preserved.**
- *Evidence:* the narrow component reads G 6.2 / 4.0 / 3.6 against
  6.8 / 4.5 / 4.1. That is 0.1-0.4 below the reference's window range in each
  band, so it is small but consistent. In raw pixels, though, the whole
  corridor at r 62-110 is 2-7 G too BRIGHT, most of all 6-12 px north-west of
  the line. By layer that light is the curve glows (`arc_glow3`, `arc_glow2`),
  `flare_halo_far` and the `flare_ray_e` slab, not the narrow ray.
- *Alternatives:* the narrow ray's fade and width refitted alone in a
  ramp-removed corridor (r 86-134). The fit preferred LESS narrow ray, because
  the domain's ramp overlaps the slab. So the reading depends on the
  background model.
- *Action:* none. Scaling or brightening the ray would add to pixels that are
  already too bright.

**(e) Line B: its white and its cyan follow different profiles.**
- *Evidence:* read per 3-px column as the amplitude of the reference's own row
  Gaussian above a quadratic background, line B's R/G is 0.87-0.93 at
  dx -20..-14 and 1.0-1.1 at dx +29..+62. One colour gave 1.10-1.35 near the
  core on the west, 1.23-1.70 at dx +17..+26, and 0.66-0.95 at dx +35..+62. A line
  drawn over a bright glow takes its hue from the glow, so one colour cannot
  follow the reference's.
- *Alternatives:* the single layer's stops alone cannot change hue along the
  line, and D63's colour-only refit had moved R up where G was short.
- *Action:* line B's white moved into `flare_spike_w`, on the same row with the
  same sigma_y (0.9) and length, as line A's is in `flare_streak_w`.
  `flare_spike` keeps the cyan and blue, with its colour x1.5 and stops /1.5
  for headroom. Both layers' stops were fitted jointly by bounded linear least
  squares on the linearised composite: west 0.11-0.29 (plus a knot at 0.135),
  east 0.11-0.38.
- *Measured:*
  - weighted per-column rms over 28 columns 2.66 -> 1.40;
  - R at dx -20 / -17 / -14: 33.4 / 27.8 / 17.5 -> 28.2 / 21.5 / 14.3
    (reference 28.6 / 20.9 / 14.5);
  - east R/G within 0.1 of the reference at dx +17..+62.
- *Visible:* the line is no whiter next to the core than further out. Its width
  is unchanged, so it is still soft, not D35's hard white line.
- *Uncertain:*
  - G is now +3.5 at dx -20 (base -0.5) and +2.7 at dx -23 (base -3.5);
    -2.6 at dx -14 (base -3.6).
  - D35's luminance row difference at dx -36..-17 reads 26.2 against 24.6
    (base 25.4); the whole line's rms is unchanged at 1.06.
  - R/G at dx -20 undershoots (0.82 against 0.93).

**(f) The vertical line north of the core: the reference has no line at
dy 12-20.**
- *Evidence:*
  - In the raw columns at dy -14..-22, the reference's R and B fall
    monotonically east from the north-west arm's ridge at x 524-526, with no
    bump at the line's x 529. The line reappears at dy -26.
  - South of the core the bump is clear.
  - The model's north profile was at full strength out to dy 21.
- *Correction to D63 (a):* D63 read the north A_4 excess as the glow's
  curvature, because the line at 10% strength still read 8.2 / 5.7 / 6.5. On
  this commit, a fixed Gaussian at x 529.4 above a quadratic in x, read
  identically on both images, gives R 12.6-14.6 at dy -11..-17 against
  -0.3..8.8. Taking the line down there halves the A_4 excess too. So the line
  was about half of it.
- *Alternatives:* five north stops fitted together (rms 5.43 -> 3.65) also
  raised the line at dy 21-27, where B was already 4-5 high. Taken instead:
  the two stops of the gap only.
- *Action:* `flare_vline`'s north profile gains knots at dy 14 and 19, fitted
  to 0.30 and 0.07 of full. The south profile is unchanged.
- *Measured:*
  - Gaussian read rms over dy 9-41: 5.43 -> 3.89;
  - R at dy -11 / -13 / -15 / -17: 12.6 / 13.7 / 14.6 / 14.1 ->
    9.0 / 8.7 / 7.9 / 5.4 (reference 8.8 / 5.9 / 2.8 / -0.3);
  - A_4 at dy 12-20: 11.8 / 8.7 / 10.0 -> 6.3 / 2.9 / 3.8 (reference
    4.0 / 3.6 / -0.7).
- *Visible:* subtle at 7x. The north stub of the line next to the core is gone,
  and the line starts where the reference's does.
- *Uncertain:*
  - G at dy -13..-15 now undershoots (5 against 9-11). The reference's line
    there is greener than this layer's colour.
  - The reference's reading at dy 19-29 (R 13-21) is partly the steep east
    edge of the dark region in (g), not a line.

**(g) North of the core, between the vertical line and the right curve:
attributed, not fixed.**
- *Evidence:*
  - The reference's R there is 2-8 at dy -24..-30. The model's is +15 at
    (+4, -24), from `flare_fan` (7.5) and `flare_halo` (8.6).
  - At the mirror point south, (+4, +24), the reference reads R 43 against
    the model's 37.
  - G and B are symmetric north and south in the reference. So the north-east
    is missing WHITE, not all light. An occluder would darken every channel,
    so masking is not supported.
- *Alternatives:* (a)'s fits of the halo's squash and centre, and of the
  fan's vertical sigma, did not move. The white the north lacks, the south
  needs.
- *Action:* none beyond (a), which took it +16.9 -> +15.1.
- *Uncertain:* this needs the symmetric white (halo and fan) replaced by
  directional white, which is a redesign of the core's white. It was not
  attempted.

**(h) The 229-degree lobe's white segment peaked too far out.**
- *Evidence:*
  - The lobe's R at r 24 / 32 / 40 read 6.9 / 22.5 / 5.8 on the base and
    5.0 / 24.0 / 9.6 after (b)'s recalibration, against 10.3 / 19.2 / 7.5:
    the white peaked too far out.
  - At r ~35 the white segment gave 17 R of a pixel whose total error was
    +10.
  - Its G was within the reference's wide window spread at every radius. The
    lower-left ray shares the window at r 28-36.
- *Alternatives:* a 2D-bin fit over all angles at r 16-64. Most of its gain
  was amplitude (44.7 -> 43.1), and it pushed the calibrated lobe and
  lower-left ray up 1.4-1.8x to fill broad background errors, so it was
  rejected. Instead, the white segment's longitudinal shape and width alone
  were refitted in the lobe line's ramp-removed corridor (r 16-64, with the
  cyan segment's amplitude): error 13.0 -> 11.0.
- *Action:* `flare_ray_llc_in`:
  - onset 21 -> 15.5 px, peak 29 -> 28, end 42 -> 35;
  - blur 3.6 -> 2.65 (its bound 3 -> 2 to admit it);
  - recorded in RAY_GEOMETRY;
  - the lobe family recalibrated.
- *Measured:*
  - R at r 24 / 32 / 40: 10.3 / 19.1 / 3.9 against 10.3 / 19.2 / 7.5;
  - G at r 24 / 32 / 40 / 48: 6.8 / 16.1 / 13.7 / 10.6 against
    5.9 / 13.4 / 13.2 / 10.5;
  - summed |error| over r 24-48 against the base: R 9.1 -> 5.8,
    G 4.9 -> 4.2.
- *Visible:* the lobe is white next to the core and turns cyan sooner.
- *Uncertain:*
  - R at r 40 is now 3.6 low.
  - The width read at r 32 is 6.8 against 4.3, where the lower-left ray shares
    the window. The reference's own range there is 3.2-7.9.
  - The 267-degree region was inspected with the lobe. Its hue is (b)'s; its
    corridor is G +4.6 throughout, which is background.

**(i) Saturation, far glow and the west.**
- *Saturation,* region by region after the local fixes, is unchanged within
  0.005 in S. The signs still disagree across regions:
  - mid flare -0.020 and lower-left rays -0.013;
  - upper-left rays +0.009, concave curve glow +0.018 and lens interior
    +0.016.

  The mid flare's deficit is a +1.5 cv red excess from the symmetric white of
  (g) and D63 (i). *Decision:* no global change.
- *Far glow:* not changed. What the local fits left is attributable and
  broad:
  - 2-5 G low on the north-east side of the lower-right ray beyond r 104;
  - 4-7.5 B low on the lobe's flanks;
  - 2-7 G high around the upper-right ray at r 62-110.

  These sit in different layers: the curve glows, `flare_halo_far`,
  `flare_glow_lens`. The flare was not used to compensate for any of them.
- *The west:* the triangle D61 removed is still absent (visual_regression),
  and nothing broad was added west of the core. The one west change, (a),
  took light away.

### Limitations of the model that this pass ran into

- A family calibration with fixed narrow templates cannot calibrate a soft
  flank: it trades it for the line (c). A flank's amplitude comes from a
  ramp-removed corridor fit instead.
- A screen layer can only add light, and the core's white is still largely
  symmetric (g).
- One layer has one colour. Line B needed two layers (e), and the vertical
  line's north is greener than its colour (f).

### What the numbers did

    measure                 previous release   D62 (baecddf)   D63 (e9fa99c)   D64 final
    MAE                     1.8416             1.8149          1.8051          1.8039
    RMSE                    3.974              3.832           3.816           3.815
    SSIM                    0.97443            0.97450         0.97455         0.97456
    edge IoU                0.6912             0.6933          0.6944          0.6936
    centre-region MAE       7.641              6.364           5.971           5.946
    flare r<110 MAE         6.309              5.452           5.178           5.170
    core r<25 MAE           8.280              6.460           5.446           5.153
    bright-region MAE       9.359              9.663           9.662           9.664

These are consequences, not the criterion. Edge IoU fell by 24 matched edge
pixels out of 34,700. All 305 edge pixels that flipped lie inside the flare
core (x 439-601, y 459-549), where luminance gradients sit near the Sobel
threshold of 40. The core refit (a) and the lobe (h) each account for part of
it.

### Remaining, with the reason

* **North of the core**, R +15 between the vertical line and the right curve:
  the core's white is symmetric where the reference's is not (g).
* **The lower-right ray** reads narrower-and-brighter at r 132-140 on per-band
  free fits while its band averages match (c). The far glow on its north-east
  side is 2-5 G dark.
* **Line B** is G +3.5 at dx -20, and its luminance row read at dx -36..-17 is
  +1.6 over (e).
* **The vertical line's north** is greener than its colour at dy 12-16 (f).
* **The lobe** is R 3.6 low at r 40 (h). The lobe's corridor B and the 267's
  corridor G are background (b).
* **The upper-right** narrow ray is 0.1-0.4 G below the reference's window
  range at r 98-114, inside a corridor that is too bright (d).
* **The core** is R -18 where it meets the right curve, and its R >= 230 area
  is 145 against 214, mostly on the east line (a).
* **Bright-region MAE** is still D61's curve-colour split beyond r 200.

## D65. Three review findings fixed first, the flank's among them; then the lower-right ray re-read, the lobe's outer fade, the core's east white and a colour refit

Three review findings were fixed before any artwork changed, and a fourth
(informational) was checked and documented. Then a short list of local items
was worked through, each judged on its own reading of the reference. "Base"
below is e61e46a (D64's head); "final" is this commit. Every candidate was
rendered at 1024 px by resvg and read with the same fixed functionals as the
base and the reference. The reference is the only ground truth, and the
whole-image numbers at the end are consequences, not the criterion.

As before, each decision records the **evidence**, the **alternatives**, the
**action**, the **measured** and **visible** effect, and what stays
**uncertain**.

**0. The baseline reproduces.** On e61e46a, `src/params.json` rebuilt
`reconstruction.svg` byte for byte, an independent render matched
`out/render_1024.png` exactly (maximum pixel difference 0), and both
`regression-gate` runs on the PR were green.

### Stage 1: the tools

**1. The lower-right flank escaped calibration (review finding): it is now
calibrated with its line, read by a split template.**
- *Evidence:*
  - D64 held `flare_ray_c_fl` outside every calibration family, because the
    family's fixed narrow templates traded its light for the line's. But the
    global fits hold exactly `CALIBRATED_LAYERS`, so the flank was free to any
    whole-image fit, and a later calibration re-balanced only the narrow
    segments around wherever the flank had been left. D64's own note on the
    layer said it was calibrated with the family; it was not.
  - A reading that can tell the two apart: per 8-px band along the line, two
    FIXED Gaussian templates on the reference's own centre, a narrow one
    (sigma 3.0) and a broad one (sigma 7.5), above a ramp over a half-width of
    22 px. Least squares with the templates fixed is linear in the image, so
    each band gives a narrow and a broad amplitude per channel, and both are
    linear in every layer's colour, which is what the calibration solves
    through. The pair's condition number is 3.7.
  - It separates what it should. Scaling the flank 1.5x or 0.3x on a test
    render moved the broad amplitude by +1.7 / -2.3 G at r 100 and the narrow
    one by only +0.1 / +0.5. Scaling the line 1.2x moved the narrow amplitude
    by +1.3 and the broad by +0.3.
- *Alternatives:*
  - Adding the flank to the family as it was: D64 showed the narrow templates
    trade it for the line.
  - A ramp-removed corridor term, like the upper-right family's: it reads the
    combined profile only, so it cannot say which segment is wrong.
- *Action:* in `tools/measure_flare.py`:
  - a family may carry a `split` range (r0, r1, sigma_n, sigma_b, half-width);
    its bands inside the range are read by the pair instead of the single
    template;
  - the lower-right family is `flare_ray_c_in`, `flare_ray_c` and
    `flare_ray_c_fl`, split over r 88-184;
  - the split rows enter the solve with the same luminance-and-chroma weight
    as every other band;
  - the report prints the narrow and broad gains.

  Because the flank is now in `CALIBRATED_LAYERS`, the global fits hold its
  amplitude, as the search already held its shape (`RAY_GEOMETRY`), with no
  special case.
- *What it showed at once:* read this way, D64's shipped state was not
  calibrated: narrow gain 1.31, broad gain 0.86, the flank asking for x1.25,
  worst correction 2.79 of tolerance. That is not an amplitude problem. It is
  (a) below, and the geometry was refitted there before anything was
  calibrated.
- *Regression:* case (f) of the calibration check:
  - displaces the flank alone (0.4x), and against the line (2.0x with the
    line 1.3x);
  - runs the global fit on the displaced file, which must leave all three
    segments exactly where the displacement put them;
  - calibrates, and requires all three segments back within 0.04 in ln of
    the calibrated state, and the split readings back within 0.5 cv.

  Result: the global fit moved the three segments by exactly 0 in both cases
  (other layers by up to 0.04 and 0.06). Calibration then returned inner /
  line / flank to 1.000 / 1.000 / 1.001 and 1.000 / 1.000 / 1.000 of the
  calibrated state, with the split readings within 0.005 cv. With the flank
  outside the family (D64's design), the same case fails as the review
  described. The global fit moved the flank (by 0.0045 and 0.017), and
  calibration left it where the displacement put it: 0.4x and 2.0x of its
  calibrated amount.
  Calibration then re-balanced the inner segment and the line around it, to
  1.047 / 1.056 and 1.073 / 1.102.

  Case (d) now also rebuilds the recalibrated flank file through
  `build_svg.py` and `render.py`, and requires every band and split reading of
  that render to match the in-process one within 0.01 cv. The check
  `the global fits never move a calibrated ray` covers the flank now that it
  is calibrated.
- *Found in passing:* `control()`, which prints the radial interval each
  layer controls, read each band's R-G chroma row of the Jacobian instead of
  its luminance row. The intervals it printed were for the wrong row. It now
  reads the luminance row and includes the split bands.

**2. The before/after sheet re-verifies its source images (review finding).**
`flare_parts.sheet_problems` checked each column's SVG digest, never the image
the column was drawn from. So a sheet kept verifying after its source render
had been replaced. Now, for every column:
- the image must still exist and hash to the column's `image_sha256`;
- a rendered column's SVG must exist and hash to its `svg_sha256`;
- the image's provenance is required, and must name that SVG at 1024 px from
  resvg.

*Regression,* on temporary copies of the sources:
- the valid sheet passes;
- it fails when a source render is replaced by another authentic render;
- it fails when a source keeps its name but its bytes change;
- it fails when a source has no provenance, or provenance naming another SVG.

The old code passed all four failure cases, and the published sheet passes
the new check.

**3. The calibration measures the saved, rounded colours (informational
finding): intended, now documented.** The final verdict of
`measure_flare.calibrate` renders the file it has just saved. That includes
the rounding `scale()` applies when it saves (basis amounts to 1e-6, colours
to 0.01 cv). This is deliberate: the verdict is about the colours that will be
rendered, not the solver's floats, and the rounding moves a band by well
under 0.01 cv. A comment at that line now says so. The algorithm is unchanged.

**4. Teal eligibility is a permission, not the current amount (review
finding).**
- `fit_photometry.fit()` locked a layer's teal column when its current teal
  amount was 0. So an eligible ray that reached 0 (or started there) was
  locked into the cone for good, and no refit could give its teal back.
- Eligibility is now an explicit argument, `teal_ok`. `teal_eligible(params)`
  derives it from the layer's own `teal` key, which only the six
  `TEAL_LAYERS` carry. `teal_ok=None` locks teal everywhere.
- Every caller passes it: `fit_photometry.py`'s own fit, `optimize.py`,
  `prune_layers.py`, `isolate.py`, and the test's global-fit check.
- No layer was given a positive teal starting value to get round the bug.

*Regression:*
- `flare_ray_ur`'s teal is zeroed, and it is fitted alone against a target
  that needs teal. From 0 it reaches 0.0485 of the target's 0.109 in 40
  iterations, at B/G 0.89, off the cone. The old code stays at exactly 0, at
  cyan's B/G 1.06.
- `flare_ray_c`, which is not eligible, never gains teal against the same
  kind of target.

The slow approach is real, not a limit: cyan and teal differ only in blue, a
near-collinear direction for the fit, and 120 iterations reach 0.088. The
test asserts the permission, not the speed.

### Stage 2: the flare

    part                              measure                              base               final              reference
    lower-right, split reading (G)    narrow / broad, r 92-108             5.94 4.87          5.28 5.42          4.15 4.67
      sigma_n 3.0, sigma_b 7.5         r 108-140                          3.98 4.04          1.24 4.69          1.38 5.04
                                       r 140-172                          1.23 2.28          -0.65 3.02         0.48 3.52
    lower-right, width (sigma)        r 92-108 / 108-128 / 132-156 /       4.75 5.03          4.94 5.54          4.75 5.42
      band-averaged, ramp removed       156-184                            4.86 5.07          6.09 6.05          5.72 5.79
    lower-right, flux                 the same bands                       117 100 61 22      122 96 53 30       97 93 67 33
    lower-right line, G               r 52 / 60 / 68 / 76 (family bands)   14.0 12.5 11.6 12.0 16.3 15.5 13.0 12.1 15.8 15.3 13.0 12.1
    229 lobe, R (family bands)        r 24 / 32 / 40 / 48                  12.0 15.3 3.5 1.3  9.4 18.3 7.2 0.0   11.0 19.2 7.5 -0.7
    229 lobe, G                       r 24 / 32 / 40 / 48                  8.5 11.8 12.2 11.9 7.5 13.0 13.0 10.1 5.9 13.4 13.2 10.5
    core / right-curve junction       R, G minus reference, dx +4..+8      -10.6 -2.3         -1.6 -0.2
                                        just past the ridge, dx 14..24     -6.0 +5.4          -0.5 +6.5
    core                              area R >= 230 (px)                   145                175                214
                                      mean R, r 4-8 / 8-12                 202.5 170.2        204.6 175.1        204.5 175.7
    north of the core                 R minus reference, dx 2..9,          +8.7               +8.7
                                        dy -30..-18

(The lobe and lower-right rows are the calibration's own fixed functionals
(`measure_flare.Lines`), identical for every image. The widths and fluxes are
the band-averaged transverse profile with its ramp removed at |s| 16-22. The
junction boxes are about (531, 513.5).)

**(a) The lower-right ray: the measurement disagreement, resolved.**
- *Evidence:*
  - D63 and D64 read this ray two ways and got two answers. Per-band free
    Gaussian fits said narrow and bright at r 132-140; band averages said
    wide. The split reading of stage 1 says why: the reference's NARROW line
    is nearly gone beyond r ~105 (r 108-140: 1.38 against the model's 3.98),
    and its soft flank carries the light (5.04 against 4.04). A free single
    Gaussian on a fading line inside a flank latches onto whichever part
    dominates the band, so the two older readings were each half right.
  - The sign and size hold for six template choices: narrow sigma 2.0-3.5,
    broad 6.0-9.0, half-width 16-26 px, the reference's centre or the line's.
    Every choice reads the reference's narrow line at r 108-140 at 0.03-2.82,
    against the base's 2.29-5.27.
- *Alternatives:*
  - Another width change: not made. The width and the translation were
    already right where the line is strong; the fade was wrong.
  - Recalibrating amplitudes alone: the line was too LOW where it is strong
    (G 1.8-2.8 under the reference at r 52-68; narrow reading at r 44-92 12.89
    against 15.76) and too HIGH beyond r 108. No single amplitude fixes both;
    the fade's shape was wrong.
- *Action:* the line's and the flank's fades, and nothing else, were refitted
  on the family's own residual (single-template bands inside r 88, split bands
  beyond), with the three amplitudes solved inside every trial. Translation,
  width and blur were held.
  - `flare_ray_c`: peak r 69 -> 59, 0.42 of peak at r 103 -> 91, end
    r 185 -> 131. Its length bound was widened from 140 to 110 to admit this.
  - `flare_ray_c_fl`: peak r 93 -> 98, 0.42 of peak at r 151 -> 175, end
    r 200 -> 192. Its tail bound was widened from 0.6 to 0.75.
  - Family residual 71.4 -> 41.4. Calibration then took `c_in` x0.82, `c`
    x1.27 and `c_fl` x1.22.
- *Measured:* see the table.
  - The calibration's split gains went from narrow 1.31 / broad 0.86 to
    0.91 / 1.00.
  - The line itself is better where it is strong (G at r 52-76 now within 0.5
    of the reference). Its narrow reading at r 44-92 is 13.75 against the
    reference's 15.76 (base 12.89).
- *Visible:* in the lower-right crops of the comparison sheet, the narrow line
  now ends before r ~130 and the soft band carries on beyond it, as in the
  reference. The change map shows no new structure.
- *Uncertain:*
  - From r ~140 the narrow reading undershoots slightly (-0.2..-1.1 against
    the reference's -0.4..2.4, noisy).
  - In the line's +-5 px corridor, G MAE rose 3.64 -> 3.99 and R 1.78 -> 1.80,
    while B fell 2.42 -> 2.01. The corridor also holds the flank's own light.
  - At r 60-88 the band flux reads 90 against 46 (base 84), while the narrow
    template reads the model BELOW the reference there (13.75 against 15.76).
    The two readings disagree in sign. Not acted on.
  - The white inner segment `flare_ray_c_in`, unchanged in shape, reads R 11.3
    / 7.3 at r 36 / 44 against 5.9 / 12.6 (base 14.1 / 10.6). Its white
    peaks too far in; that is its geometry, which this pass did not change.
    Calibration took its amplitude x0.82 with the joint solve.

**(b) Colours after the teal fix.**
- *Evidence:* with eligibility fixed, every ray family's colour was refitted
  by bounded least squares on the calibration's own band cost, on the
  candidate that already carried (a), (c) and (e):

      basis                                      band cost    fourth primary used on
      shipped (no refit)                         127.6        --
      white/cyan/blue, refitted                  129.0        --
      + teal on the six layers of record         121.3        ula, llc, lld, lld2, ur, e
      + teal on every calibrated ray             120.6        also b, b2, c_in, c_fl
      + pure green on the six (reference only)   121.2        ula, llc, lld, lld2, ur

- *Alternatives:*
  - The cone alone is worse than shipped: the four green rays need the fourth
    primary.
  - Teal on every ray gains 0.6 by putting teal on four rays the reference
    shows cyan (B/G 1.03-1.30). Nothing measured supports that.
  - Pure green ties teal and was not introduced: its floor is B/G 0, far below
    the greenest ray measured (0.7).
- *Action:* the teal-on-six refit was adopted. It is small hue corrections on
  13 ray layers: mostly less blue on the lower-left and lower-right rays, a
  little white on the upper-left inner ray, and the lobe's colour as teal 0.52
  with blue 0.11.
  Then every family was recalibrated. Converged, worst correction 0.90 of
  tolerance.
- *Measured,* B/G above the ramp per ray (base -> final, reference):

      upper-left inner 1.09 -> 1.12 (1.15)    upper-left A 0.73 -> 0.73 (0.73)
      upper-left B     1.65 -> 1.65 (1.18)    229 lobe     0.72 -> 0.78 (0.74)
      lower-left       1.36 -> 1.26 (1.30)    268 ray      0.83 -> 0.84 (0.85)
      upper-right      0.77 -> 0.78 (0.78)    lower-right  1.11 -> 1.06 (1.06)

  Five rays moved toward the reference, two stayed, and the lobe moved away
  (0.02 -> 0.04 off). The core's chroma excess (r < 12) fell from +4.1 to
  +1.2. Some ray corridors moved the other way: upper-left inner R +0.4 ->
  +1.6, lower-left B -3.5 -> -4.0.
- *Visible:* nothing at normal scale. Every channel of every changed colour
  moved by 4.3 cv or less.
- *Uncertain:* the colour refit cost 0.020 of centre-region MAE (5.927 before
  it, 5.947 after). It was taken on the per-ray hue evidence, not the MAE.

**(c) The 229-degree lobe: only the white segment's outer fade.**
- *Evidence:* on the family's own reading, the near lobe was right (R 12.0
  against 11.0 at r 24) but the white fell short from r 32 outward: R 15.3 /
  3.5 against 19.2 / 7.5 at r 32 / 40.
- *Alternatives:* a free fit of the white segment's tail and length, with the
  amplitudes, cut the family's residual 26.8 -> 13.3. But it moved the near
  and mid lobe (free-fit R at r 24 7.0, reference 10.3) and was rejected.
  Brightening or extending the whole lobe was not tried: it would have
  raised r 24 too, which was right.
- *Action:* `flare_ray_llc_in`'s onset (15.5 px) and peak (28.3 px) were held
  at the same radii. Only the outer fade moved: 0.42 of peak 33.5 -> 37.6 px,
  end 35 -> 40 px. Then the lobe family was recalibrated (`llc_in` x0.86,
  `llc` x0.90).
- *Measured:* R at r 24 / 32 / 40 / 48 went 12.0 / 15.3 / 3.5 / 1.3 ->
  9.4 / 18.3 / 7.2 / 0.0, against 11.0 / 19.2 / 7.5 / -0.7. The summed |R
  error| over those bands fell 10.9 -> 3.5, and G's 6.5 -> 2.6. The lobe's
  segmentation is unchanged.
- *Visible:* the lobe's white reaches a little further along the lobe; its
  near end is unchanged.
- *Uncertain:* R at r 24 went from 1.0 over the reference to 1.6 under it on
  the family reading. The reference's own free-fit window range there is wide
  (7.0-22.5). The lobe's hue moved slightly away in (b).

**(d) The upper-right ray at mid radius: examined, not changed.**
- *Evidence:* read with a split template (sigma 2.5 / 8.0), the narrow line is
  low at r 98-118 (1.24 against 3.76), while the slab `flare_ray_e` carries
  broad light the reference does not (2.66 against 0.25). This is the same
  redistribution as the lower-right ray.
- *Alternatives tried, both rejected:*
  - Refitting both fades with the split reading: family residual 34.0 -> 21.8.
    But the line's peak moved inward, the free fits at r 90-98 fell out of the
    reference's range (5.2 against 6.8, range 6.5-8.3), and centre-region MAE
    rose 5.946 -> 5.984.
  - The fades with the line's onset and peak held: residual 34.0 -> 25.7, but
    most of it came from scaling the whole line x1.26 and the slab x0.84.
    Scaling the whole ray was ruled out, and the free fits fell out of range at
    r 58 and r 114.
- *Action:* none. The family keeps D62's broad term.
- *Uncertain:* the narrow line is still 0.1-0.4 G below the reference's window
  range at r 98-114 (D64 (d)).

**(e) Where the core meets the right curve: a white east arm.**
- *Evidence:* between the core and the right curve, at dx +4..+8 and
  dy -8..+10, the model was R -10.6 with G -2.3: WHITE missing, not light.
  Just past the curve's ridge it was R -6.0 with G +5.4. The reference's
  R >= 230 core runs 16.8 px east, to the curve; the model's stopped at 5.6.
  - The one-column R/G/B spikes on the curve's inner edge, at every height,
    are the curve's edge placement (about a pixel), not this, and were left
    out of the fit.
- *Alternatives:*
  - Enlarging the core's symmetric white: it would also whiten the west and
    north, which are right or already too red ((f)).
  - A first fit that left the curve out entirely put the segment's peak inside
    the curve, where nothing constrained it. It was rejected for that.
- *Action:* a short white segment, `flare_ray_east_in`, from the core toward
  the curve: axis 5.7 degrees south of east, length 25.4 px, peak at 14.6 px,
  height 22.2 px, blur 2.7, white 0.40.
  - It was fitted on dx -8..+24, |dy| <= 16, with the curve's edge columns
    (dx +9..+13) and clipped pixels left out.
  - Like D63's north-west and south arms, it is measured in 2D, not on a line.
    So its shape is held in `RAY_GEOMETRY` (`--geometry` restores it), and it
    is in no calibration family.
- *Measured:* the table.
  - The junction box went from R -10.6 to -1.6.
  - The R >= 230 core grew 145 -> 175 px (the reference has 214), and its
    ring means now match to 0.6. Due east, its R >= 230 contour reaches only
    6.3 px (was 5.6; the reference's 16.8): the arm adds white across the
    junction without drawing the reference's full-strength bridge.
  - The west side of the core is unchanged (R -0.4 both).
  - Core r < 25 MAE fell 5.153 -> 4.705.
- *Visible:* in the core crops, the darker gap between the core and the right
  curve is mostly filled at the core's row. At full strength the bridge is
  still shorter than the reference's. The core does not grow west or north.
- *Uncertain:*
  - G past the ridge rose +5.4 -> +6.5, and at |dy| 11-16 +2.3 -> +3.7. The
    arm is white, and the reference's light there is not quite.
  - The curve's inner-edge spikes remain; they are curve geometry.

**(f) North of the core, R +15: attributed, not changed.**
- *Evidence:* unchanged from D64 (g). R at (+4, -24) is 21.4 against the
  reference's 6.1, from `flare_fan` and `flare_halo`. The mirror point south
  is 7 R low. G and B are symmetric north and south in the reference, so the
  north is missing white, not light.
- *Alternative tried:* moving the fan's centre south (`dy`, free with the
  core's amplitudes on the core's 2D bins) changed the bin error only from
  39.16 to 39.12, with the offset staying at 0.
- *Action:* none. Lowering red globally, or darkening the north with an
  occluder, would contradict the G and B that match.
- *Uncertain:* this still needs the core's symmetric white made directional,
  which is a redesign.

**(g) The vertical line: not changed.** Its remaining differences are hue, not
strength.
- North at dy 20-28, the reference is whiter than the line (R 12.5 against
  7.4, B 5.1 against 9.4). Per D64 (f) that reading is partly the steep edge
  of (f)'s dark region.
- South at dy 28-36, the reference is whiter than the line's single cyan
  colour.

Scaling the line up or down cannot fix a hue difference. It is the one-colour
limit, recorded rather than chased.

**(h) Saturation, far glow and the west.**
- *Saturation:* region by region, the model-minus-reference chroma after this
  pass was:
  - core r < 12: +4.1 -> +1.2;
  - ring r 12-40: -3.4 -> -3.8;
  - mid flare r 40-130: -2.1 -> -2.3;
  - upper-left rays: -0.6 -> -0.9;
  - lower-left rays: -4.6 -> -5.2;
  - lower-right ray: +1.0 -> +0.9;
  - upper-right ray: unchanged.

  The signs still disagree across regions, so there is no global change, and
  no claim that saturation is fixed.
- *Far glow:* attributed per layer at seven points 120-160 px from the core.
  The light there is the curve glows' (`arc_glow1b`, `arc_glow2`,
  `arc_glow3`), `arc_haze`'s and the field layers'. Of the flare's layers only
  `flare_sat_long` appears among the contributors, at one point (6.5 G). Not
  changed, and the flare was not used to compensate.
- *The west:* the triangle D61 removed is still absent (visual_regression
  passes), and nothing was added west of the core. Everything added is vector
  geometry: one ray segment. No JPEG block or mottling was drawn.

### Candidates

    candidate                      centre MAE   flare MAE (metr)   core r<40   decision
    base (e61e46a)                 5.946        3.676              6.581
    lower-right fades (a)          5.955        3.676              6.599       taken
    lobe free fit (c)              5.949        3.677              6.577       rejected: moved the near/mid lobe
    upper-right fades (d)          5.984        3.668              6.567       rejected
    upper-right, onset held (d)    5.961        3.664              6.564       rejected: whole-ray scaling
    east arm (e)                   5.912        3.667              6.411       taken
    (a) + (c) + (e), calibrated    5.927        3.668              6.428       taken
    + colour refit (b)             5.947        3.673              6.463       taken (final)

Each was rendered and compared against the reference and the base in a
region sheet (reference / base / candidate / difference x6 / better-worse
map). The rejected ones looked as their readings said:
- the lobe fit improved the lobe's outer part and worsened its near part;
- both upper-right fits improved the ray's outer half and worsened a patch
  nearer the core.

The final sheet shows improvement at the core/right-curve junction and along
the outer lower-right ray. North of the core, the upper rays and the west are
unchanged, and there is no new structure.

### Limitations of the model that this pass ran into

- One template per band cannot calibrate a narrow line inside a soft flank;
  two can (stage 1, item 1).
- The core's white is still largely symmetric ((f)).
- One layer has one colour: the vertical line's hue, and the east arm's G past
  the ridge ((e), (g)).

### What the numbers did

    measure                 previous release   D62 (baecddf)   D63 (e9fa99c)   D64 (e61e46a)   D65 final
    MAE                     1.8416             1.8149          1.8051          1.8039          1.8036
    RMSE                    3.974              3.832           3.816           3.815           3.812
    SSIM                    0.97443            0.97450         0.97455         0.97456         0.97457
    edge IoU                0.6912             0.6933          0.6944          0.6936          0.6937
    centre-region MAE       7.641              6.364           5.971           5.946           5.947
    flare r<110 MAE         6.309              5.452           5.178           5.170           5.171
    core r<25 MAE           8.280              6.460           5.446           5.153           4.705
    bright-region MAE       9.359              9.663           9.662           9.664           9.664

These are consequences, not the criterion. Most of the whole-image numbers did
not move, because the changes are local. The core number fell because of (e).

### Remaining, with the reason

* **North of the core**, R +15: the core's white is symmetric where the
  reference's is not ((f)).
* **The lower-right ray** beyond r ~145: the narrow reading undershoots by ~1;
  the ray's white inner segment peaks ~8 px too far in; at r 60-88 two
  readings disagree in sign ((a)).
* **The upper-right** narrow line is 0.1-0.4 G below the reference's window
  range at r 98-114; no remedy was robust ((d)).
* **The core** has an R >= 230 area of 175 against 214, and G is +6.5 just
  past the right curve's ridge ((e)).
* **The vertical line** is a hue mismatch, not a strength one ((g)).
* **The 229 lobe** is 0.04 off in B/G after the colour refit ((b)).
* **Bright-region MAE** is still D61's curve-colour split beyond r 200.

## D66. The gate made reproducible from a clean checkout, two tooling bugs fixed and reviewed twice; then every local item re-read: both curves' flare-side core edge and their concave glow near the flare changed, the rest left on the evidence

This iteration had two jobs, in order. First, the regression, photometry and
calibration tools had to be correct and reproducible in a clean checkout.
Only then was the artwork looked at again, one named item at a time, each
judged on its own reading of the reference. "Base" below is e8f522d (D65's
head; its artwork is unchanged through the three tooling commits 508e868,
186cc40 and 2db920a). Every candidate was rendered at 1024 px by resvg and
read with the same fixed functionals as the base and the reference. The
reference is the only ground truth, and whole-image numbers are
consequences, not the criterion.

As before, each decision records the **evidence**, the **alternatives**, the
**action**, the **measured** and **visible** effect, and what stays
**uncertain**.

### Stage 1: the tools

**0. The starting state reproduces.** On e8f522d, `src/params.json` rebuilt
`reconstruction.svg` byte for byte, an independent render matched
`out/render_1024.png` exactly (maximum pixel difference 0), and
`measure_flare.py --rounds 0` verified the shipped calibration at 0.90 of
tolerance.

**1. CI's regression gate failed on a file a clean checkout never has; a
pinned, deterministic setup step now makes it.**
- *Evidence:* CI failed on e8f522d in one check, the published before/after
  sheet's. That sheet's baseline column is drawn from
  `out/baseline/render_1024.png`, which `.gitignore` keeps out of the
  repository, and which only `tools/publish.sh` ever made. A fresh clone in
  a fresh virtual environment reproduced the failure exactly. The artwork
  was not at fault: a missing setup artefact was reading as a regression.
- *Alternatives:*
  - Committing the render: rejected. It is a derived artefact, and the
    repository's contract (`.gitignore`, the manifest's note) keeps derived
    renders out. A committed PNG could also drift from the SVG it claims to
    be.
  - Letting the gate render it on the fly from whatever SVG is in the working
    tree: rejected. The check exists to compare against the previous
    ACCEPTED release, so the input must be pinned, not "whatever is there".
  - Skipping the check when the file is absent: rejected. A gate that passes
    because its input is missing is not a gate.
- *Action:*
  - `tools/setup_baseline.py` is the one setup step. In order:
    1. The baseline SVG must hash to the manifest's `svg_sha256`. That digest
       is the pin.
    2. If git can see the manifest's commit, that commit's SVG must hash to
       the same digest. A shallow clone (CI's default) cannot see it and says
       so, and the digest alone is then the pin. A full clone that cannot
       find the commit is a failure. So is an enclosing repository that is
       not this checkout.
    3. The SVG is rendered at 1024 px by resvg, the acceptance renderer.
    4. If the published sheet has a column drawn from this baseline (matched
       by SVG digest, not by path), the render must be byte-for-byte the image
       that column recorded.
    5. Only then is the render written with its provenance sidecar and read
       back against every expectation.

    Any failure removes the render and exits 3 ("SETUP FAILURE"). A
    directory without a manifest is refused untouched.
  - `requirements.txt` pins numpy, Pillow and resvg-py. Byte identity relies
    on the resvg-py version, and CI installs exactly this file.
  - CI runs "Baseline setup (exit 3 = setup failure, nothing tested)" and
    "Regression gate (exit 1 = a regression; exit 3 = setup incomplete)" as
    separate steps, before the validation steps.
  - `tools/test_pipeline.py` begins with a pre-flight that runs every setup
    check except the render (`setup_baseline.verify`) and exits 3 before
    running any check if one fails. A missing or foreign baseline render can
    no longer be reported as an artwork regression.
  - `publish.sh` uses the same setup, with `--for-publish`: that skips the
    sheet comparison, because publish redraws the sheet next and then
    verifies it, so a renderer upgrade can still be published. It still
    refuses a resvg-py other than the pin.
- *Measured:*
  - A clean clone, emulated end to end three times (fresh clone, fresh venv,
    `pip install -r requirements.txt`, then the CI steps in order):
    - the gate before setup exits 3 with "out/baseline/render_1024.png is
      absent (a clean checkout does not carry it)";
    - setup renders png 57acd7f6… and reports that it matches the published
      sheet's baseline column;
    - the gate then passes every check;
    - validation, the misconfigured-browser exit 3 and the SVG rebuild all
      pass.
  - GitHub CI was green on 508e868, 186cc40 and 2db920a. CI's shallow clone
    printed the "not in this clone (shallow?); pinned by digest" note and
    produced the same 57acd7f6… render.
- *Regression:* "the baseline setup renders only the pinned SVG and
  reproduces the sheet's baseline". It covers:
  - an absent render;
  - a render set up byte for byte;
  - a re-encoded leftover render (caught);
  - a differing render;
  - `--for-publish` skipping the comparison;
  - a wrong renderer version (refused);
  - an unpinned SVG;
  - a missing baseline (exit 3);
  - a directory without a manifest (left untouched);
  - an enclosing repository;
  - a bogus commit in a full clone.
- *Uncertain:* nothing about the artwork. The setup trusts resvg-py's PNG
  encoder to be deterministic for a pinned version. Three emulated clean
  clones and three CI runs agree byte for byte.

**2. The documented photometric fit raised `KeyError` and saved nothing (Devin
finding).**
- *Evidence:* the report printed after the fit read `L["teal"]` for every
  layer. A cone layer has no `teal` key, because it is not ALLOWED teal. So
  the first cone layer raised `KeyError`, after the fit and before the save,
  and `tools/optimize_all.sh`'s `fit_photometry.py --iters 30 --stride 2`
  saved nothing.
- *Alternatives:*
  - Giving every layer a `teal` key (0 for cone layers): rejected. The key IS
    the eligibility (D65), so this would make every layer eligible, and the
    next fit could put teal on rays the reference shows cyan.
  - Defaulting a missing teal to 0 inside the fit: not needed. The fit
    already locks an ineligible layer's teal column. Only the report was
    wrong.
- *Action:*
  - `main()` saves before it reports.
  - The report prints an absent teal as `teal=    ---` (ineligible), distinct
    from `teal=0.0000` (eligible, currently no teal).
  - Permission and amount stay two separate things. Eligibility is the
    presence of the key (`teal_eligible`). The amount is its value, which may
    be 0 on an eligible layer.
- *Regression:* "the documented photometric fit completes and saves on every
  layer schema". It runs the real CLI, the same `main()` path as the
  documented command, with fewer iterations so the suite stays fast. It runs
  in both modes (documented, and `--fit-rays`) on a file holding every
  schema:
  - cone layers without a teal key;
  - the six eligible rays, one of them (`flare_ray_ur`) with no light at all;
  - a layer carrying only a colour;
  - the normal-blended frame.

  It requires, for both modes:
  - exit 0 and a saved fit;
  - no calibrated ray moved in the documented mode;
  - no cone layer given a teal key;
  - no eligible layer's key dropped;
  - the colour-only layer's amounts stored;
  - the ineligible layers reported as `---`.

  The old code fails it.

**3. A calibrated ray with no light verified as calibrated (Devin finding).**
- *Evidence:* `correction()` computes each layer's scale through the
  Jacobian. A layer whose colour is zero has a zero column (a scale of
  nothing is nothing), and a zero column was read as "needs nothing"
  (correction 1.0). So a file with a zeroed ray verified as converged, with
  the ray missing, both from `--rounds 0` and after the default eight rounds.
- *Alternatives:*
  - Replacing zero with an epsilon amount and letting the scale grow it:
    rejected. Calibration is multiplicative by design: it keeps each layer's
    hue and sets its amount. A dark layer has no hue, so any seed colour is a
    colour decision the tool has no evidence for, and the result would depend
    on the epsilon.
  - Treating every zero-light ray as a failure: rejected. A layer the
    reference has no use for (a duplicate, or one no band sees) must not fail
    the calibration.
- *Action:* a calibrated layer is DARK when it is faint (summed amounts below
  0.01) and its own Jacobian column moves no reading by more than 0.01 cv.
  Each dark layer is probed. A small white amount shows what its SHAPE would
  add to each band's luminance. The probe and the residual are both
  projected off the span of the lit calibrated layers' columns, because
  those layers can be re-scaled. The non-negative least-squares amount of the
  probe shape then says how much light the reference asks of it beyond what
  re-scaling can give.
  - **missing**: it is asked at least 1.0 cv, and that explains at least half
    of the unexplained residual where the layer reaches. Calibration FAILS
    (correction infinite, exit 1) and names the remedy: restore the last
    calibrated colour, or fit a colour from zero with
    `fit_photometry.py --fit-rays`.
  - **not needed**: nothing is asked, or its shape is (to within 10%) a
    re-scaling of lit layers.
  - **unobservable**: no band sees it.

  The check runs BEFORE anything is solved, and the file is left untouched on
  failure. Otherwise the solve pushes a dark ray's light onto its lit
  neighbours (see 4).
- *Why a probe amount is not an epsilon:* the composite is affine in any one
  layer's colour (every flare layer is a screen layer, and
  1-(1-c·a)·P is affine in c), and each band reading is a fixed linear
  functional of the image. So the probe's response is exactly proportional to
  the probe amount. The asked light and the explained fraction are ratios in
  which the amount cancels. Checked on the shipped file with three rays
  zeroed in turn, at probe amounts 0.005, 0.05 and 0.3:
  - `flare_ray_e`: 5.3648 cv, explained 0.90321, at all three;
  - `flare_ray_ula`: 6.3533, 0.95762;
  - `flare_ray_c_fl`: 3.9308, 0.88347.

  Only luminance rows are read, because a dark layer's hue is unknown.
- *Thresholds, from the shipped rays:*
  - zeroing any one of the fourteen, the reference asks 3.7-20.5 cv, which
    explains 0.90-1.00;
  - a zero-light copy of a calibrated ray, which the reference has no use
    for, is asked 0.01-0.05 cv.

  1.0 cv sits between them with a margin of about 4x on each side.
- *Regressions:*
  - `--rounds 0` on the CLI reports MISSING and fails.
  - `flare_ray_e` zeroed on the default (eight-round) path fails, and the
    file is byte-identical afterwards.
  - An already-absorbed state (`e` dark, `ur` x2.09) fails.
  - A faint ray (`ula` x1e-4) is dark and missing.
  - A lit ray at 5% (`ula` x0.05) is NOT called dark: it is asked to scale up.
  - A duplicate probe is "not needed", and an off-image one "unobservable".
  - A genuinely absent ray (`ula` and `c_fl` zeroed) is missing.
  - Teal 0 on `lld`, which still has cyan, calibrates. `ur` zeroed, whose
    light is all teal, fails.
  - A zero-initialised teal ray is recoverable: the colour fit brings
    `flare_ray_ur` back from no light at all to 0.109 of the target's 0.109,
    off the cone (B/G at most 0.8).

**4. Two adversarial review rounds on the tooling itself.**
Two independent review passes (several reviewers each, every finding then
verified by refutation) were run on the tooling commits before any artwork
work.
- *Round 1 (on 508e868):* 11 findings confirmed, 8 refuted. Fixed in 186cc40:
  - **Absorption.** Zeroing `flare_ray_e` made round 0 take `flare_ray_ur`
    x2.09. The leftover then no longer asked for `e`, and calibration
    converged. Hence the pre-solve check and the projection in 3.
  - **Zero Jacobian in `fit()`.** A channel at exactly 0 was treated as
    clipped. With non-negative amounts, 0 is a bound, where the one-sided
    derivative is the real one. So a dark layer had no gradient at all, and
    a zero-initialised ray could never be fitted back. Also, a cyan layer's R
    term was missing from its white amount's gradient.
  - **`params_wc` rewrote clipped colours.** It re-derived amounts from each
    stored colour and moved `arc_core` by 1.23 cv on every run. It now uses
    the stored amounts whenever they reproduce the colour within 0.02 cv.
    The render is unchanged.
  - **Setup gaps:**
    - the gate's pre-flight was weaker than the setup;
    - a leftover render from another renderer read as a stale sheet;
    - the sheet column was matched by path;
    - a pin bump could not be published;
    - a render survived a failed setup;
    - the suite crashed on a sheet without columns.
  - **Faint rays and vacuous tests.** A ray scaled to 1e-4 was not "dark",
    and two regressions could not fail.
- *Round 2 (on 186cc40):* the ten fixes confirmed (one with a residual gap),
  six new defects confirmed. Fixed in 2db920a:
  - **The fit stalled at a bound.** Once a channel at 0 had its real
    derivative, an amount at a bound whose gradient pointed outward dragged
    every Levenberg-Marquardt step out of the box. On the documented
    configuration the objective was 13.67, against 13.40 before D66.
    `fit()` now solves the projected problem: an amount at a bound with an
    outward gradient is held for that iteration. A channel at exactly 1 is
    an edge too, so a clipped layer can come back down. The objective is now
    13.34, and the fit runs 3x faster. With this, teal refits from zero
    exactly (0.109 of 0.109, against 0.049 in D65's test). D65's "slow teal
    convergence" was this stall, not collinearity.
  - **An absolute amount threshold for "dark".** It would have refused a lit
    ray at 5%, which a scale recovers. It is now the Jacobian test in 3.
  - **Setup hazards:**
    - `--baseline out` could delete `out/render_1024.png` (a manifest is now
      required first);
    - an enclosing repository was trusted as this clone;
    - `verify()` skipped the commit check;
    - `--for-publish` accepted any renderer version.
- *Measured:* the suite grew from 59 checks (D65) to 63, all passing. After
  every tooling commit the artwork was re-verified: the SVG rebuilds byte for
  byte, and calibration verifies at 0.90 of tolerance.

**5. Found in passing: `publish.sh` checked the README before writing it.**
The README's generated blocks (metrics, layer count, SVG size) were written
by step 5, after the regression gate in step 4. The gate checks that the
README states the layer count of `src/params.json`. So the first release
to change the layer count, this one (53 -> 54), failed its own gate on the
previous release's README. `update_readme.py` reads only step 3's
measurements, so it now runs before the gate, and the gate checks what
ships.

### Stage 2: the artwork

The visual baseline was re-established first. After the three tooling
commits the SVG rebuilt byte for byte, and calibration verified at 0.90 of
tolerance: the tooling did not change the artwork.

The items were then taken in the order the brief set. Each was judged on its
own reading, and changed only if its discrepancy was stable across
measurement choices and the change improved that reading without damaging
its neighbours.
- **Investigations:** nine, each by an investigator working only on scratch
  copies.
- **Review:** every recommended candidate was then handed to independent
  reviewers (five in all) whose job was to refute it with their own
  measurements. One candidate was refuted and dropped: see (j).

| item | decision |
|---|---|
| (a) ray colour basis, per-ray chroma | no change: the shipped colours are already the optimum of the controlled teal refit |
| (b) the core's white shape | no change: its contours and ring means match, and it is not less white than D64's |
| (c) core/right-curve junction | no change on the flare: the remaining deficit is the curves' edge, (d) |
| (d) both curves' flare-facing core edge | **changed**: a thin edge stroke, confined to mid-height |
| (e) the 229-degree lobe's outer fade | no change: D65 fixed the user's figures, and the rest is not the lobe's |
| (f) upper-right, mid radius | no change: the corridor is already brighter than the reference |
| (g) lower-right profile | no change: no stable width error; the inner segment's misplacement is coupled to the core's red edge |
| (h) vertical line, hue | no change: a local fix worsens the pixels |
| (i) north of the core, red | no change: the fan's and halo's symmetric white; no existing lever is local |
| (j) right-ridge G | attributed: part flare light (left), part the curves' concave glow (**changed**, both curves, station by station) |
| (k) background hue, saturation | no change: three sources that need opposite corrections; no global operation |

Readings over the two changes. D65 is the base, "(d)" is the curve edge
alone, and "final" also includes (j). All are model minus reference unless
marked absolute:

| reading | D65 | (d) | final | reference |
|---|---|---|---|---|
| junction, 3-row R at columns 539 / 540 / 541 | -9.0 / -16.3 / -16.3 | -9.0 / -13.3 / -8.0 | -9.0 / -13.3 / -8.0 | 0 |
| flare-side core edge, middle bands (px) | -0.55..-0.75 | -0.15..-0.31 | the same | 0 |
| R ≥ 230 area r < 60, core side + curve band (px, absolute) | 40 + 177 | 40 + 188 | 40 + 206 | 51 + 205 |
| core ring R r < 4 / 4-8 / 8-12 (absolute) | 232.5 / 204.6 / 175.1 | 232.5 / 204.6 / 175.7 | 232.5 / 204.7 / 175.7 | 233.0 / 204.5 / 175.7 |
| right-ridge item box R / G / B | +0.5 / +6.4 / +3.9 | +0.5 / +6.4 / +3.9 | +1.7 / +3.2 / +0.9 | 0 |
| concave glow u 1..12, \|dy\| ≤ 100, rms, left / right | 11.5 / 10.4 | 11.5 / 10.4 | 5.2 / 6.6 | 0 |
| north of the core, R, (i)'s box on whole pixels (it reads +10.0 on D65 with half-open edges) | +9.4 | +9.4 | +11.5 | 0 |
| lobe family R, r 24 / 32 / 40 / 48 (absolute) | 9.4 / 18.3 / 7.2 / 0.0 | the same | 9.4 / 18.3 / 7.2 / 0.0 | 11.0 / 19.2 / 7.5 / -0.7 |
| upper-right family G, sum \|err\| over 14 bands | 13.1 | 13.1 | 12.5 | 0 |
| lower-right family R, r 36 / 44 / 52 (absolute) | 11.3 / 7.3 / 3.7 | the same | 8.4 / 6.3 / 3.3 | 5.9 / 12.6 / 3.0 |

**(a) Ray colours: the controlled teal-aware refit returns the shipped colours.**
- *Evidence:*
  - The calibration's own band reading, band cost per basis (colour-basis refit
    on the current state):

    | basis | band cost |
    |---|---|
    | shipped | 121.24 |
    | teal on the six layers of record, refitted | 121.25 |
    | white/cyan/blue only (the cone) | 129.01 |
    | teal on every calibrated ray | 120.63 |
    | pure green on the six (diagnostic) | 121.19 |

    The teal-on-six refit moves no colour by more than 0.4 cv, so D65's
    colours are already its optimum with the corrected eligibility.
  - A second opinion from the corrected production fit (`fit_photometry.fit`,
    rays only, projected solve) converges to one optimum from four starts:
    stored, cone-projected, zero-teal and pure cyan. Teal on `ula` and `ur`
    comes back from 0 within 15 iterations, so the D66 fix works in
    production. But that fit turns 8 of 14 rays bluer, and after
    recalibration they read 14-69% too blue above the ramp. Its hue is
    driven by a broad, flat background error around the flare, not by the
    rays. Off the ray corridors, the flare's background reads G +2.0..+2.9
    and d(B)-d(G) -2.2..-3.3 cv in all four quadrants. With that broad
    residual high-passed out of its target (sigma 16 / 10 / 6), the same fit
    returns to the stored hue within about 0.1 B/G on 10 of 14 layers.
  - Per ray, B/G above the ramp, as model/reference, is the median of 12
    readings (three half-widths, linear or quadratic ramp, two band
    selections):
    - 0.98-1.02 on seven of eight lines;
    - calibration's own B-gain/G-gain 0.95-1.02 on the same seven.

    The eighth is upper-left B. Its reference hue is undetermined: 1.09-1.63
    across window and ramp choices. The one reading that called it too blue
    (1.18 against 1.65) includes two bands, r 92 and 100, inside the left
    curve's concave glow, which calibration excludes (r_min 104).
  - The "blue 12-38% high" pattern the user reported is what the CONE basis
    produces, not the current state. With the cone, calibrated, B/G reads
    upper-left A 1.37x, 268 1.23x, upper-right 1.20x and lobe 1.13x of the
    reference.
- *Alternatives:*
  - The cone: band cost +7.8, and the four green rays 13-37% too blue.
    Rejected, as in D64/D65.
  - Teal on every ray: -0.61, all in the lower-right family, from teal on
    `c_in` and `c_fl`, whose reference B/G (1.05) lies inside the cone. It
    would also widen `TEAL_LAYERS` with no ray-specific evidence. Rejected.
  - Pure green: a tie, which only re-decomposes the same hue and permits
    B/G down to 0. Diagnostic only, as the user asked.
  - The production fit's colours: they paint the background's missing blue
    into the rays (corridor B MAE on 268 2.96 -> 5.73). Rejected.
  - A less blue upper-left B (B/G 1.56 -> 1.40 or 1.25): its calibration B/G
    moves from 1.08x to 0.95x / 0.84x, inside the reference's own spread, and
    its corridor B MAE worsens. Not robust.
- *Action:* none. The shipped colours stand.
- *Measured / visible:* no change.
- *Uncertain:*
  - Upper-left B's hue, as above.
  - The lower-right ray's hue changes along its length (reference B/G
    0.96-1.01 at r 44-60, 1.16-1.30 at r 68-116); one colour per layer
    averages it (1.05-1.06 against 1.06).
  - The remaining hue error near the flare is its background, not its rays.
    See (k).

**(b) The core's white: its shape matches; "less white than D64" is not what
the render shows.**
- *Evidence:*
  - D65 minus D64, pixel by pixel inside r<12 about (531, 513.5): 0 to +22 R,
    and not one of 452 pixels is lower in any channel.
  - Ring means r<4 / 4-8 / 8-12:

    | | reference | D65 | D64 |
    |---|---|---|---|
    | R | 233.0 / 204.5 / 175.7 | 232.5 / 204.6 / 175.1 | 232.1 / 202.5 / 170.2 |
    | luminance | 247.2 / 232.7 / 215.6 | 246.4 / 232.6 / 216.0 | 246.3 / 231.7 / 213.8 |
    | chroma | 20.9 / 41.2 / 59.6 | 20.3 / 41.6 / 61.1 | 20.7 / 43.4 / 65.1 |

  - The only place the model is less white than the reference is the hottest
    centre. The reference's G/B clip at 255 over 54% of r<4, against 10% in
    both models. That is about 1 cv of G.
  - The R contours at 230 / 200 / 170, and the luminance contours at
    238-190, match within ±0.5-0.8 px in all 24 directions except where a
    threshold crosses a saddle.
  - Due east, the reference's R≥230 region reaches 16.8 px against the
    model's 6.3. This is a threshold effect at a saddle: the reference's
    east-row saddle is R 231-233, 1-3 cv above the threshold, and at T 235
    the reference also stops at 7.2 px. The model's saddle is 221 (D64 210).
  - The R≥230 area shortfall (217 against 256 px, sigma 0) is mostly the
    curve: 28 of the 39 missing pixels are in the curve band dx 9..19.
- *Alternatives:* enlarging or whitening the core. Excluded by the brief, and
  not indicated: the contours and ring means already match.
- *Action:* none.
- *Uncertain:* a small south-east core-side deficit (R about -6 at dx 5..8,
  dy 1..7) is robust in sign. It is too small to act on. The best refit of
  the east arm (all eight keys) improves its box by 2% and trades north for
  south.

**(c) The core/right-curve junction ("R -18"): D64's number, now -9; the rest
is the curve's edge.**
- *Evidence:*
  - D64's -18 reproduces exactly as the 3-row mean (dy -1..+1) at pixel
    column 539 (dx +8.5): D64 -18.0, D65 -9.0.
  - The reading's minimum now sits at columns 540/541 (-16.3 / -16.3, D64
    -27.3 / -24.7). There the right curve's flare-facing edge, at R half
    level, lies 0.37-0.95 px east of the reference's at every height from dy
    -80 to +80, identically in D64 and D65. The outer edge is within ±0.35.
  - The left curve mirrors it: both curves are 0.7-0.9 px too narrow on the
    flare side over |dy| ≤ 200.
  - The east arm cannot reach that edge without painting the curve.
- *Alternatives:*
  - Truncating the east arm at the ridge (end 17 or 20 px): the junction is
    unchanged (-1.6) and R past the ridge falls to -8.0 / -6.4 for 1.4 G;
    re-aiming it, or refitting all eight keys, improves its box by at most
    2% and trades north for south. Rejected.
  - Widening the whole curve core (`arc_core` inset -0.4, width 7.632): it
    closes the junction (-16.3 -> -6.3), but costs global MAE 1.804 -> 1.850
    and RMSE 3.812 -> 4.429. The curves' ends are already 0.25 px too wide.
    Rejected. The curve edge had its own investigation: see (d).
- *Action:* none on the flare.
- *Uncertain:* the edge offset depends on the level read (+0.62..+0.96 px at
  R 0.3/0.5/0.7, +0.22..+0.41 in B). Its sign and its constancy along the
  curve hold at every choice.

**(d) Both curves' flare-facing core edge: 0.4-0.9 px too narrow along their
whole middle. A thin edge stroke, confined to the middle.**
- *Evidence:*
  - Measured along the normal of the curve of record, the reference's core is
    about symmetric. Its R half-level edges sit at -3.85..-4.01 px (flare side)
    and +4.04..+4.21 px (lens side) at mid-height, and about ±3.1 px at the
    tips. That makes it about 6.2 px wide at the tips and 7.9-8.1 px at
    mid-height.
  - The model widens toward mid-height on the lens side only. `arc_core_wide`
    (inset 2.0, width 4.03) covers s 0..+4.0 over y 204-810. The flare side
    stays at `arc_core`'s 3.42 px half-width along the whole curve.
  - Flare-side edge offset, model minus reference, R half-level, px, per
    height band:

    | y | 100-230 | 240-330 | 340-470 | 480-550 | 560-690 | 700-790 | 800-930 |
    |---|---|---|---|---|---|---|---|
    | left | +0.19 | -0.27 | -0.55 | -0.63 | -0.70 | -0.17 | +0.21 |
    | right | +0.20 | -0.37 | -0.61 | -0.75 | -0.61 | -0.27 | +0.24 |

    It is no worse near the flare (y 480-550) than far from it, so it is the
    curve's profile, not missing flare light.
  - The deficit is robust in the middle bands over R levels 0.3/0.5/0.7,
    tangential windows ±0.5/±1.5/±4 px, an absolute threshold, G and
    luminance: -0.41..-0.75 px, standard error 0.02.
  - The per-height least-squares strength of a flare-side edge stroke,
    measured independently on each curve, gives the same shape on both:
    negative at y < 230 and y > 800, rising over y 240-300, about 1.0 from
    y 330 to 700, and zero by y ~790.
  - At the core row this edge IS the junction reading at columns 540/541
    (item (c)).
- *Alternatives:*
  - Moving `arc_core` toward the flare side (inset -0.3 / -0.5): fixes the
    middle, but pushes the tips' flare-side edge to +0.47..+0.72. Tip-band
    R MAE goes 10.1 -> 13.1 (left) and 12.8 -> 17.2 (right). Rejected.
  - Widening `arc_core` (inset -0.4, width 7.632): MAE 1.850, RMSE 4.429.
    Rejected.
  - Re-centring `arc_core_wide` to cover both edges (inset 0, width 8.2): the
    plateau gains R +25..+43, and the R ≥ 230 curve area overshoots (225
    against 205). Rejected.
  - An exact mirror of `arc_core_wide` (inset -2.0): overlaps the
    already-bright plateau and removes only 38% of the error. Rejected.
  - The new stroke on `arc_core_wide`'s own ramp: valid, but under-serves the
    north shoulder (MAE 1.7608 against 1.7567). Kept as the fallback.
  - A fitted colour for the stroke: marginally closer in R, but the two curves
    disagree on it. `arc_core_wide`'s colour is used instead, which adds no
    fitted numbers.
  - The flare-side glows (`arc_glow1b` etc.): cyan/blue only, blur 2.4+, so
    they cannot draw an R edge.
- *Action:* a new arc layer `arc_core_edge`, directly after `arc_core_wide`:
  - inset -3.4 (flare side; the stroke spans s -4.1..-2.7), width 1.4;
  - `arc_core_wide`'s blur and colour;
  - its own ramp taper `core_edge` (y 235 / 300 / 705 / 790, p 1.0 / 1.0),
    zero above y 235 and below y 790, so the tips are untouched.

  It is not a ray, so `RAY_GEOMETRY` is unchanged, and calibration verifies at
  0.90 with the file unchanged.
- *Measured:*
  - Flare-side edge offsets in the middle bands: -0.55 / -0.70 / -0.61 /
    -0.61 -> -0.15 / -0.27 / -0.18 / -0.15. Flare band y 480-550: -0.63 /
    -0.75 -> -0.25 / -0.31. Shoulders within ±0.11.
  - Tips and the lens-side edge unchanged exactly.
  - Curve band |s| ≤ 7 MAE R/G/B over the middle (y 300-700): left
    14.09 / 12.75 / 12.54 -> 10.86 / 8.56 / 8.03; right 14.02 / 11.75 /
    11.81 -> 10.13 / 8.87 / 8.77.
  - The junction (item (c)), R minus reference in 3-row means: column 540
    -16.3 -> -13.3, column 541 -16.3 -> -8.0. Column 539 (the core's own
    white) stays -9.0.
  - Only 3,483 pixels change, all in y 235-789 and x 392-617. Their summed
    |error| (per pixel, mean over channels) falls from 91,116 to 41,864.
    That accounts for the whole-image change: MAE 1.804 -> 1.757, RMSE
    3.812 -> 3.365, bright-region MAE 9.664 -> 8.471.
- *Visible:* at normal scale nothing jumps out. At 3x and 6x, the dark line of
  missing core width along both curves' flare side is gone, and the cores are a
  little wider toward the flare, as in the reference. There is no double edge
  and no step where the ramp starts or ends. Red (worse) pixels in the
  better/worse map are isolated 2-3 px specks where the stroke is faint at the
  ramp ends.
- *Verified independently:* a reviewer with their own normal-profile sampler
  tried to refute this:
  - It is width, not a displaced centreline. In G/B the lens-side edges
    already match within ±0.1 px, and the reference's peak sits toward the
    lens, not the flare.
  - It is not a JPEG artefact:
    - the flare-side deficit does not depend on the 8x8 block phase (x mod 8:
      -0.56..-0.64 px; y mod 8: -0.56..-0.61);
    - it is smooth along the curve;
    - it is consistent in R, G, B and luminance;
    - it survives a 3x3 median and Gaussian sigma 0.7 / 1.0 applied to both
      images (-0.49..-0.70).
  - The 3,483 changed pixels account for 100.0% of the whole-image change.
  - A steeper south ramp end or a whiter stroke colour does not improve the
    net result.
  - A second reviewer judged the render visually at 1x/3x/6x and found no new
    artefact. Nothing changes outside the curves (west box: 0).
- *Uncertain:*
  - The R edge is still 0.12-0.21 px narrow in the middle, while G and
    luminance are within ±0.14. The added colour is slightly cyan against the
    reference's edge.
  - In G/B the flare-side edge now overshoots by 0.1-0.37 px at the ramp
    shoulders (right curve y ~295-370, both curves y ~715-790) and slightly on
    the right curve's middle. The cyan fringe outside the R edge widens from
    0.10-0.31 px to 0.25-0.41 px (reference 0.01-0.11). This costs up to 1.1
    MAE in the band 4-6 px out, in 5 of 14 cells, against a gain in the edge
    band about 50 times larger. At offset -1 px G/B rise +3..+5, and the
    right curve's existing G/B excess at its flare-side foot (+12..+14, from
    its cyan glows) becomes +15..+17.
  - The tips stay 0.2-0.36 px too wide on both edges. A screen layer cannot
    subtract, and they were not touched.
  - The "4.8 px concave / 3.3 px convex" asymmetry that `arc_core_wide` was
    built on (METHOD §4b) does not hold against the current curve of record.
    The asymmetry is 0.1-0.3 px. METHOD §4b, the README and `arc_core_wide`'s
    note are corrected.

**(e) The 229-degree lobe's outer fade: D65 fixed what the user's numbers
describe; what is left does not belong to the lobe on any stable reading.**
- *Evidence:*
  - The figures quoted for this item (R 3.9 against 7.5 at r 40) are D64's.
    On the current render, the calibration's own family reading gives R at
    r 24/32/40/48 of 9.4 / 18.3 / 7.2 / 0.0, against the reference's 11.0 /
    19.2 / 7.5 / -0.7.
  - With the window varied (half-width 9/12/15 × offset -1/0/+1), every R
    band from r 24 to 48 is inside the reference's own range, for example
    r 40: 7.7 against 7.5 [6.1..9.6].
  - At r 24 the readings disagree in sign. The family reading is 1.6 low,
    but a two-centre fixed-template reading has the model higher in all 54
    variants (+0.73 [+0.06..+2.33]). That band's R is dominated by the core
    layers' ramp shapes.
  - Beyond r ~52 the reference's lobe is not a clean ray by the
    calibration's own test: the free fit's centre and width run to their
    bounds at r 56. The readings that can be taken there disagree in sign:

    | reading at r 48-64 | model against reference |
    |---|---|
    | two-centre reading | G -1.3..-4.3 |
    | xprof flux at r 48 | 0.82-0.86 of the reference |
    | centre-minus-flank contrast | +1.4..+2.1 G (more contrasty) |

  - Raw sector means at r 48-57 put the G deficit at -2.8 on the lobe axis,
    -3.0 on the far side (214-223 degrees), and -3.9 in the trough between
    the lobe and the lower-left ray. That is broad, not lobe-shaped, and B is
    9-14 low throughout: the far glow (D64 (i)).
- *Alternatives:* the only change the brief allows here is the cyan lobe's
  outer fade, with onset (33.4 px) and peak (39.8 px) held. Both candidates
  were calibrated:

  | candidate | family sum\|err\| R/G/B (base 4.9 / 5.6 / 8.3) | G at r 40 (ref 13.2) | B at r 56 (base matches the reference) | notes |
  |---|---|---|---|---|
  | A: 0.42-point 46.3 -> 49 px, end 60 -> 64 | 3.8 / 6.7 / 10.0 | 13.0 -> 12.1 | 3.2 -> 4.7 | |
  | B: end 60 -> 68 only | 4.3 / 5.6 / 8.9 | | 3.2 -> 5.4 | on-axis G at r 57-66 -1.6 -> +1.1; trough -3.9 -> -3.3 |

  B's lower screening cost came from the r 72 band beside the left curve's
  convex glow: the lobe making up for the curve glow's shape. Both were
  rejected.
  - Filling the 238-degree trough would need a broad fill of the kind D61
    removed with the false triangle, and would use the flare to make up a
    glow deficit. Not attempted.
  - The lobe's hue (B/G 0.78 against 0.74) sits in the white segment's
    domain (r 24-32), where the reference's own B/G spans 0.66-0.86 with the
    window width. The cyan segment's own bands (r 40-48) match: 0.71-0.75
    against 0.73-0.77.
- *Action:* none.
- *Measured / visible:* no change. In the sheets, neither candidate differs
  visibly from the base.
- *Uncertain:* whether the r 48-57 G deficit (about 3 cv) belongs to the lobe
  or to the far glow cannot be settled. It is the same size on the far side
  as on the axis, which points to the glow.

**(f) The upper-right ray at mid radius: no ray-specific deficit once the
corridor is accounted for.**
- *Evidence:*
  - On the family reading, G at r 98/106/114 is 5.8 / 4.0 / 2.8 against
    7.0 / 4.5 / 4.5. With the window varied, the model is inside or just
    below the reference's range: 6.2 / 4.0 / 3.6 against 6.8 [6.5..8.3] /
    4.5 [4.1..5.7] / 4.1 [4.0..4.7].
  - The surrounding ±5 px corridor at r 90-122 is already G +3.2 too bright
    (MAE 3.26). With the narrow ray removed entirely it would be +1.24 / 1.60.
    The slab (`flare_ray_e`) carries 4.9-7.9 G at s +8..+14 where the
    reference has 0.2-1.8 above the rest of the model.
  - The narrow amplitude, reference minus base, over 132 readings (template,
    window, centre, band phase): +1.17 / +0.29 / +1.57 / +1.35 / -0.85 at
    r 90-98 … 122-130. With a slab-centred broad term, +0.41 / -0.23 /
    +0.77 / +0.08 / -1.19. It is sign-unstable across neighbouring bands and
    depends on the centre and on the background model.
- *Alternatives:*
  - Brightening or widening the narrow ray: rejected. The brief's condition
    applies: the corridor is already brighter than the reference.
  - Dimming the slab, which the raw decomposition asks for: not attempted.
    The family's own broad term reads the slab as right or slightly short,
    because the rest of the model is +2..+8 too bright at its ramp edge, and
    D65 (d) rejected fade refits that dimmed it.
- *Action:* none.
- *Uncertain:* a narrow line about 1 G low relative to its surroundings
  (15-20% of its contrast) could be real at r 94-114. It cannot be separated
  from the slab's excess and the corridor's other light (curve glows, far
  halo) until those are corrected at their source.

**(g) The lower-right profile: no blind width change, and the inner white
segment's misplacement is real but coupled to the core's red edge.**
- *Evidence:*
  - From r ~140 the narrow reading undershoots by 1.0-1.7 over 16 readings.
    The profile there is wider and weaker than the reference's (sigma 6.23
    against 5.43, flux 43.5 against 52.1). But the narrow reading at r 108-132
    is already at or above the reference's (4.12 against 1.94 at r 108).
  - At r 60-88 the peak above the local ramp matches (family G within 0.3 at
    r 60-76). The sign disagreement between flux and template readings comes
    from a dark valley in the reference's background. The model's extra width
    (+0.4-0.7 sigma) is inside overlapping window ranges in 2 of 3 bands.
  - The white inner segment `flare_ray_c_in` peaks too far in, robustly in R
    and chroma. R at r 36 / 44 / 52 is 11.3 / 7.3 / 3.7 against 5.9 /
    12.6 / 3.0.
- *Alternatives:*
  - Extending the narrow line past r 131: contradicts the r 108-132 reading.
    Narrowing the flank with r needs spread below the primitive's bound, and
    a whole-flank change would break the matched widths at r 92-128.
    Rejected.
  - Re-widening or rescaling the line at r 60-88: its peak matches. Rejected.
  - `flare_ray_c_in` onset and peak refitted on the family residual,
    amplitudes solved, recalibrated (converged at 0.90):
    - R at r 36/44/52 went 7.8 / 9.5 / 4.7, and the family residual 47.4 ->
      39.4;
    - but G at r 44 left the reference's range (19.4 against [16.8..17.8]);
    - raw corridor R MAE at r 24-72 worsened 5.48 -> 6.50, because the
      base's white was partly filling the core's broad red deficit at r 24-36;
    - the luminance-weighted error improved at one band phase and worsened
      at the other.

    It trades hue along the segment, and it is not visible at region scale.
    Rejected.
- *Action:* none.
- *Uncertain:* the segment carries white and cyan in one colour, so its white
  cannot move outward without its cyan. A proper fix needs the core's red
  radial edge corrected first, or the white split from the cyan.

**(h) The vertical line's hue: white near the core in the reference, cyan in
the model; a local fix worsens the pixels.**
- *Evidence:*
  - A fixed template (sigma 1.7 at x 529.4 above a quadratic, the same pixels
    in every image): at |dy| 24-36, on BOTH sides, the reference's line is
    white. Its screen-colour ratio kR/kG is 0.9-1.14, against the layer's
    0.45-0.57. Median of 54 template choices: R -9.1 at N 24-28, -5.4 at
    N 28-32, -3.7 at S 24-28, -5.3 at S 28-32.
  - Where R is unclipped further out (N 72-104), the reference's hue matches
    the layer's colour exactly: kR/kG 0.36 vs 0.34, kB/kG 1.24 vs 1.21. So
    the colour is right; only the inner part is whiter.
  - Beyond |dy| 36 the G and B amplitudes agree within template noise, so it
    is not the line's strength or its north/south balance.
- *Alternatives:*
  - A paired white streak on the line's inner part, with the line
    re-tabulated there (the shape-optimal fit, stable across knot phase,
    half-width and rows). It halves the line's own R deficit and matches its
    N 24-28 hue. But raw on-axis MAE north worsens (R/G/B 4.23 / 4.50 /
    6.07 -> 5.53 / 6.08 / 8.60), centre-region MAE rises 5.947 -> 5.957,
    and core r<40 rises 6.463 -> 6.511. The line sits on backgrounds that are
    wrong in the opposite sense: north R +4..+6 from (i)'s white, G/B
    -4..-7 from the far glow. Rejected.
  - South only, raw-optimal: a third of the measured difference on one side,
    below visibility. It would also build a north/south asymmetry the
    reference's line (white on both sides) does not have. Rejected.
  - A whiter colour for the whole line: breaks the outer line, whose hue
    already matches. Rejected.
- *Action:* none.
- *Uncertain:* the whiteness is robust in sign on both sides across 54
  templates, but its size is not: the white dR is +5..+19 depending on the
  template. Fixing the line's hue first needs (i)'s broad white fixed.

**(i) North of the core: the red excess is the core's symmetric white meeting
a notch in the reference's.**
- *Evidence:*
  - D65's box (dx 2..9, dy -30..-18), model minus reference: R +10.0, G +3.7,
    B +2.2. Over seven box choices: R +8.6..+14.5.
  - The reference's R has a notch in the north-east quadrant, between the
    vertical line and the right curve (sectors 70-80 degrees, r 20-32). Its
    R=25 contour sits at dy about -22 where the model's is at -26/-27. Its G
    and B contours show no notch and match the model's.
  - All the R there comes from `flare_fan` (7.6) and `flare_halo` (8.5) at
    (+4, -24), and both are north/south symmetric. With the fan removed the
    north box reads R +2.8, G -0.3, B -1.1. So it is white that is in excess,
    not a hue.
  - The southern mirror is a different error: R -7.5 with G/B already +5.
    The reference asks for about 0.04 more white there, with no more G or B.
- *Alternatives,* each on an existing parameter, as north R / south R / core
  r<40 MAE (base +10.6 / -7.3 / 4.39):

  | lever | north R | south R | core r<40 MAE | other effect |
  |---|---|---|---|---|
  | fan moved 2 px south | +7.4 | | 5.03 | south G/B +7 |
  | halo moved 2 px south | +8.5 | | 4.98 | |
  | fan sigma_y 9 | +5.2 | -15.6 | 5.40 | |
  | fan east_gain 0.70 | +8.4 | -11.4 | 4.59 | a step in the fan at the axis |
  | halo squash 0.40 | +6.9 | -11.0 | 4.62 | |

  - A neutral darkening layer would need alpha 0.40, taking G/B to 96/102
    against 157/168. Rejected, as in D64.
  - Making the fan north/south asymmetric: a builder change, and the
    reference's asymmetry exists only east of the axis, so a whole-fan
    asymmetry would break the west.
- *Action:* none. Every existing lever trades north against south or damages
  the core, and a screen layer cannot remove light.
- *Uncertain:* the component is identified (the fan's and the halo's
  symmetric white). The real fix is a directional core white with a
  north-east gap: a redesign of those two layers, not a parameter change.

**(j) Right-ridge G: part flare light, part the curves' own concave glow,
which was too cyan near the flare on BOTH curves. The glow part is changed,
station by station; the flare part is not.**
- *Evidence, attribution:*
  - In the item box (dx 14..24, |dy| ≤ 10 about (531, 513.5)), model minus
    reference, on the curve-edge state of (d), is R +0.5, G +6.4, B +3.9. At
    those rows the screen composite is near saturation.
  - Two things are there:
    - **Flare light.** A compact excess 14-26 px beyond the right curve's
      ridge (G +10..+12 at |dy| < 20, +6 at 20-44, -2 at 44-74). It falls off
      within about 30 px of the core, is best fitted by the fan's or the
      halo's shape (R² 0.87-0.89, against 0.65-0.74 for the curve glow), and
      is larger than all of `arc_glow1`'s cyan there. Removing every bit of the
      right curve's `arc_glow1` cyan would still leave the item box at
      G +2.8.
    - **The curves' own narrow concave glow**, 1-12 px beyond each curve's
      outer edge, too cyan and not white enough near the flare's rows on BOTH
      curves. Left: G +15.2 / +15.8 / +14.6 at dy 0..60, R -25.1 at dy
      -20..0. Right: G +13.9 / +14.0 at dy 0..40, R -24.4 at dy -40..-20. The
      left curve is 66+ px from the core, where the fan contributes nothing,
      so this is not flare light. Its profile across the curve is the glow's,
      gone by 12-16 px.
  - `arc_glow1`'s taper stations across the flare's rows (about y 440-580,
    both curves) were never measured. The original station fit interpolated
    them, with their endpoints inflated 15-20% by the flare
    (`out/analysis/arc_photometry.json`).
- *First candidate, refuted:* a cyan-only dip in the RIGHT curve's
  `arc_glow1` only, a Gaussian (depth 0.9, sigma 40) centred on the flare's
  row, with its white returned through `arc_glow1w`. It cut the item box to
  G +3.5. An independent reviewer refuted it:
  - it used a flare-centred shape to absorb light that is partly the flare's;
  - it left the left curve, which has the same excess and supports the same
    change more strongly, untouched, encoding a left/right asymmetry the
    reference does not have;
  - it made B worse on the right flank (dy -74..-44: -2.4 -> -6.1).

  It was dropped.
- *Action (second candidate):* the two glow layers were re-measured station
  by station (20-px stations, y 380-680) on both curves. At each station, the
  cyan+white `arc_glow1` and the white `arc_glow1w` amounts that match the
  reference's concave band (u 1..12) were solved with every other layer
  fixed, both bounded below by 0 and `arc_glow1` above by its current value.
  On the right curve's flare rows (|dy| < 25) the fit carried a flare-shaped
  nuisance term (free fan and far-halo amplitudes, pinned by the band
  u 2..30 where that light lies) so that the curve glow could not absorb the
  flare's light. The flare itself was not changed.
  - `arc_glow1`: its cyan goes to 0 at y 520-560 (left) and 500-560 (right),
    and to 0.3-0.8x at the neighbouring stations. Its left and right tables
    change only at those stations.
  - `arc_glow1w`: its white rises to 1.1-1.9x the ramp's old flat top (left
    y 520: 1.85; right y 500: 1.81; right y 520: 1.04). The white must differ
    by side and by station, so its shared ramp becomes a per-side table,
    written first on the ramp's own knots (byte-identical SVG). Its white
    rises x1.9, with every table value /1.9, to stay under the table's
    ceiling of 1 (render-neutral within 1 cv).
  - The calibration then re-balanced four rays whose windows overlap the
    curves' concave band: `flare_ray_c_in` x0.949, `flare_ray_e` x1.033,
    `flare_ray_ur` x0.968 and `flare_ray_lld` x0.987; every other ray moved
    by at most 0.5%. It converged at 0.78 of tolerance. The same run on the
    unchanged file moves nothing, so every re-balance comes from the glow
    change.
- *Measured (model minus reference; base = the curve-edge state):*

  | reading | base | changed |
  |---|---|---|
  | item box R / G / B | +0.5 / +6.4 / +3.9 | +1.7 / +3.2 / +0.9 |
  | left concave band u 1..12, \|dy\| ≤ 100, R / G / B (rms) | -1.8 / +9.7 / +8.0 (11.5) | +0.1 / +2.2 / +0.5 (5.2) |
  | right concave band, the same | -7.2 / +8.5 / +3.4 (10.4) | -0.2 / +6.2 / +0.8 (6.6) |
  | right flank dy -74..-44, u 1..12, R / G / B | -4.7 / +4.5 / -2.5 | +1.9 / +5.4 / -1.9 |
  | flare-shaped band, right u 14..26, G at dy -20..0 / 0..20 | +6.8 / +10.5 | +6.6 / +10.2 (not absorbed) |
  | far band u 15..40, rms, left / right | 4.8 / 4.6 | 4.8 / 4.6 |

  - In 20-px bins over dy -160..160, R/G/B rms went from 10.3 / 10.2 / 9.2 to
    5.8 / 4.7 / 4.8 on the left (every bin better), and from 12.2 / 8.9 / 7.0
    to 6.1 / 6.9 / 5.2 on the right.
  - Perceptual error ΔE (CIE76) at 4-8 px beyond the edge, y 380-680: left
    6.32 -> 3.64, right 6.34 -> 4.41.
  - The curve edges move by at most 0.11 px.
  - Rays crossing the curves improve there: corridor MAE `flare_ray_e`
    9.71 -> 7.02, `flare_ray_ur` 10.61 -> 6.14.
- *Visible:* both curves' concave glow at the flare's rows reads paler and
  whiter, as the reference's does, instead of a saturated cyan band. The
  R-deficit patches beside both ridges and the left curve's G/B stripe below
  the flare row are mostly gone. With `arc_glow1` at zero over 4-5 stations
  there is no luminance hole, notch or step, because the white carries it.
  The broad flare-shaped excess right of the right curve is visibly unchanged,
  as intended.
- *Verified independently:*
  - An attribution reviewer's own station fit (own geometry, own resvg-rendered
    bases) reproduced both tables. They held over seven band windows and two
    shifted station grids; the features follow image position, not the grid.
    There is no 8-px block content. The left curve alone independently asks
    for the cyan to go to 0.
  - A visual reviewer at 1x/3x/6x found no step, seam or band. The hue lands
    between the base and the reference everywhere, never past it.
  - Neither could refute it.
- *Costs:*
  - North of the core, on the right curve's flare side (box x 531-541,
    y 478-496), R +7.5 -> +9.5. That region already carries the symmetric
    white excess of (i), and the right curve's raised white spills about
    2 cv of R into it. It shows as a faint stripe at 6x only.
  - On the right curve at y 460-500, 4-8 px out, luminance now overshoots
    (+5 -> +11 at y 460). ΔE there still improves (8.0 -> 6.7).
  - The core's concave shoulder (1-4 px) is slightly worse: left G -5.1 ->
    -7.0, right R +5.4 -> +7.7.
  - Item-box R +0.5 -> +1.7.
  - Edge IoU 0.6981 -> 0.6947: pixels on the glow's shoulders crossing the
    edge detector's threshold.
  - Calibration side effects:
    - `flare_ray_c_in`'s x0.949 is induced by glow light inside its window.
      Lower-right R at r 44 is 1.3 further from the reference, and G/B at
      r 36 are 0.9/1.0 further;
    - upper-right B at r 66 +0.3, and its corridor G MAE +0.07.
- *Alternatives rejected:*
  - The right-only dip above.
  - Interpolating the right curve's flare-row station from clean neighbours:
    the reference contradicts it at the item's own rows (item-box R +11.9).
  - A flare nuisance pinned only in u 2..12: unconstrained, it trades the
    flare's white for the glow's (item-box R +9.5).
  - A G/B-only fit: degenerate between white and cyan, and it leaves the
    R -10..-25 deficit.
  - Capping the right curve's y 500 white to spare the north box: that would
    tune the curve glow to hide a flare-zone error, the converse of the
    brief's rule. Not done.
- *Uncertain:*
  - The right curve's white dips at y 520 (1.04, between 1.81 and 1.41),
    where the left curve's peaks (1.85). At that station the flare supplies
    about 80% of the band's R. Rescaling the fan, halo, far halo, east arm
    and white bloom does not remove the dip (1.08-1.22), so it is not
    mis-scaled flare light. But it is attributed to the curve only on the
    assumption that the flare's SHAPE there is right. Recorded as
    unconfirmed.
  - `arc_glow1` is at its lower bound at 4-5 stations per curve. Allowed
    below zero, both curves would take out more cyan, so part of the excess
    belongs to other cyan layers. What remains on the right (G +6..+10 at
    dy -40..+40) is partly teal hue, which white and cyan cannot draw.
  - The white sits 0.06-0.16 below its R-only need where `arc_glow1` is at
    zero, and the left curve's y 520 station is at the table's ceiling.
  - The right curve's y 500 white peak coincides with `flare_ray_e`
    crossing the band. Part of it may be crossing-localised light.

**(k) The flare's background hue and the saturation question: three sources
that need opposite corrections, so no change and no global operation.**
- *Evidence:*
  - Off the ray corridors (rays masked ±7 px, streaks masked), the flare's
    background is about 2-3 cv too green in all four quadrants. Model minus
    reference, R/G/B:

    | quadrant | R | G | B |
    |---|---|---|---|
    | LL | +0.67 | +2.18 | -1.10 |
    | UL | +0.20 | +2.03 | -0.19 |
    | UR | +0.27 | +2.88 | +0.46 |
    | LR | +0.82 | +2.06 | -0.29 |

    This is what made the whole-image colour fit read "rays not blue enough"
    in (a). Mapped by radius and direction with the mask varied, the average
    comes from three different things:
    1. **Between the curves** (their flare-facing side), G is +3..+8 at
       14-40 px from either ridge and -1.4..-2.5 at 6-14 px. The band runs the
       whole length of both curves (y 280-750) and is as large 140-250 px from
       the core, where `flare_halo_far` and `flare_glow_lens` contribute
       exactly 0. It is the curves' flare-side glow profile (too bright at
       14-40 px, too dark at 6-14), not the flare's colour.
    2. **East of the right ridge next to the core:** G +6..+17 with R -8..-28.
       That is (j), the reference being WHITER, not bluer.
    3. **Inside the flare layers' footprint (r < 100):** the sign changes with
       direction. At r 25-40, G is +12.2 / +10.6 / +10.3 to the E / NE / SE,
       but -5.9 (with B -8.2) to the N, -2.0 to the S and +2.4 to the W. The
       per-direction change to `flare_halo_far`'s G this implies runs from
       -37..-51% to +17%. No isotropic layer can follow that.
  - Region by region (satcmp: mean colour, chroma and saturation per region
    against the reference), the chroma differences still disagree in sign:
    core +1.0, ring r 12-40 -3.8, mid flare -2.3, lower-left rays -5.2,
    upper-right ray +1.6, lower-right ray +0.9, curve ridges +2.0.
- *Alternatives,* each a diagnostic render:
  - `flare_halo_far` less cyan with blue added, holding B (G -10%): 20
    background cells better and 7 worse. Every worse cell is at r < 70 to the
    N, W or S. The ring's G overshoots (+2.0 -> -2.5), corridor G MAE worsens
    on 4 of 8 lines, and the between-curve excess is untouched. Rejected.
  - `field_mid` cyan x0.8 with blue: E and W quadrant MAE worsen, and
    whole-image MAE rises 1.804 -> 1.817. Rejected.
  - `flare_glow_lens` G -20%, or bluer: 9/6 and 9/8 cells better/worse. The
    south-west B deficit peaks at theta 240, but the layer covers theta
    195-285 evenly. Rejected.
  - A radial profile change to `flare_halo_far`: opposite signs by direction
    at the same radius. Not built.
  - A global saturation or colour operation: excluded by the brief and by the
    sign disagreement above. A G-only correction would not even move the
    chroma statistic (B-R).
- *Action:* none on the flare. The one region-level colour change in D66
  comes from (d): the flare-facing curve band's saturation moves toward the
  reference (+1.8 -> +0.2, x100) and its luminance from -0.7 to +0.9.
- *Uncertain:*
  - The between-curve profile error (1 above) is real and robust. It belongs
    to the curves' flare-side glow (`arc_glow2`'s tail and `arc_glow2b`), to
    be fitted as shape and hue together. It is recorded, not attempted:
    no single amplitude fixes a profile that is too bright at 14-40 px and
    too dark at 6-14.
  - The ring's red excess (R +2.4) is the same anisotropic symmetric-white
    issue as (i).

### What was preserved

- The west-side triangular field stays absent. `visual_regression`'s west
  check reads 0.782, as before. The west box does not change at all between
  D65 and the final render.
- Every structure D65 listed is kept, and no layer was removed:
  - the upper-left rays;
  - the lower-left segments and the 229-degree lobe;
  - the upper-right line and slab;
  - the lower-right translation, line and flank;
  - the vertical line and the soft horizontal lines;
  - the core's three white arms;
  - the curves and the frame.
- The one new layer, `arc_core_edge`, is a vector stroke on the curves of
  record. The glow change re-measures existing layers' fades. The deliverable
  is still vector only: 54 named layers (53 before), no bitmap.
- No JPEG texture was drawn. The curve-edge deficit is independent of the
  8-px block phase, and the glow's new stations carry no block content (both
  checked by reviewers).
- No global saturation, blur, sharpen or colour operation was used. Both
  changes are local, at their source.

### How the decisions were made

- Every discrepancy was read with more than one functional (window,
  template, offset, channel, level) before anything was built. Where the
  readings disagreed in sign, the item was left, and the disagreement
  recorded.
- Every candidate was a full copy of the parameters with one local change:
  - rendered by resvg at 1024 px;
  - recalibrated where rays could be affected, and required to converge;
  - read with the item's own functionals and its neighbours';
  - compared in a region sheet (reference / base / candidate / difference
    x6 / better-worse) that was looked at, not just scored.
- Whole-image metrics were recorded as consequences, never as the criterion.
- Every recommended candidate was then given to independent reviewers
  instructed to refute it with their own code. One was refuted ((j)'s first
  candidate) and dropped. The two that shipped survived with their costs
  recorded.

### What the numbers did

    measure                 previous release   D63 (e9fa99c)   D64 (e61e46a)   D65 (e8f522d)   D66 final
    MAE                     1.8416             1.8051          1.8039          1.8036          1.7323
    RMSE                    3.974              3.816           3.815           3.812           3.284
    SSIM                    0.97443            0.97455         0.97456         0.97457         0.97561
    edge IoU                0.6912             0.6944          0.6936          0.6937          0.6947
    centre-region MAE       7.641              5.971           5.946           5.947           4.706
    flare r<110 MAE         6.309              5.178           5.170           5.171           4.184
    core r<25 MAE           8.280              5.446           5.153           4.705           3.902
    bright-region MAE       9.359              9.662           9.664           9.664           8.159

By change (MAE / RMSE / centre / bright):
- D65: 1.8036 / 3.812 / 5.947 / 9.664.
- The curve edge (d) alone: 1.7567 / 3.365 / 5.373 / 8.471.
- The concave glow (j) added on top: 1.7323 / 3.284 / 4.706 / 8.159.

These are consequences, not the criterion. They move more than in any pass
since D61 for one reason: both changes sit on the curves, whose cores and
near glow are the brightest, highest-error pixels in the image. In (d), the
3,483 changed pixels account for the whole change. Edge IoU fell 0.0034 in
(j), on the glow's shoulders (see (j)'s costs). The flare's radial ring means
in `out/diagnostics.json` rose by 0.3-0.8 cv. They include the curves: with
the curve bands masked they are identical before and after, so the smaller
D65 values were the flare's own slight excess cancelled by the curves'
missing edge.

### Remaining, with the reason

* **North of the core**, R +11.5 (box dx 2..9, dy -30..-18). The core's
  white is symmetric where the reference's has a north-east notch ((i)).
  (j)'s whiter right-curve glow added about 2 cv.
* **Just past the right curve at the core's height**, G +3.2. It is flare
  light compact within ~30 px of the core, plus some cyan beyond what the
  concave glow can remove ((j)).
* **Between the curves**, the flare-side glow is too bright at 14-40 px and
  too dark at 6-14 px along their whole length: a glow-profile item for the
  curves, not the flare ((k)).
* **The flare's background** near the core is anisotropic in G by direction,
  beyond any isotropic layer ((k)).
* **The vertical line** is white near the core in the reference ((h)).
* **The lower-right ray's** white inner segment peaks too far in, coupled to
  the core's red edge ((g)).
* **The upper-right** narrow line may be about 1 G low relative to a corridor
  that is itself too bright ((f)).
* **The curves' tips** are 0.2-0.36 px too wide on both edges. A screen layer
  cannot subtract ((d)).
* **Upper-left B's** hue is undetermined by the reference ((a)).

### Validation

- `sh tools/publish.sh`: **PUBLISH OK**. That includes:
  - the cross-engine check (resvg against Chromium, MAE 2.693);
  - the before/after sheet's `--verify` step;
  - the reproducibility step.
- `tools/test_pipeline.py`: all 63 checks pass (59 in D65).
- `measure_flare` calibration verifies as converged, worst correction 0.78 of
  tolerance.
- `visual_regression`: 0 of 16 structural checks fail. The west triangle
  stays absent.
- `src/params.json` rebuilds `reconstruction.svg` byte for byte. The
  published render is pixel-identical to the evaluated candidate.
- The CI workflow's steps were run in a fresh clone with a fresh virtual
  environment: the gate before setup exits 3, then setup, the gate,
  validation and the SVG rebuild pass.

## D67. The optimiser's objective made to score the parameters it is given; then the local items re-read: the halo given a directional gap, the curves' flare-side glow its own fade, and the curves' tips narrowed; the rest left on the evidence

This pass had the same two jobs as D66, in the same order: correctness first,
then local refinement, each item judged on its own reading of `reference.png`.
"Base" below is D66 (dbb0087). Whole-image numbers are consequences, not the
criterion.

As before, each decision records the **evidence**, the **alternatives**, the
**action**, the **measured** and **visible** effect, and what stays
**uncertain**.

### Stage 1: the tools

**0. The D66 baseline reproduces.** On dbb0087:
- `src/params.json` rebuilt `reconstruction.svg` byte for byte;
- an independent render was byte-identical to `out/render_1024.png`;
- `out/metrics.json`, `out/diagnostics.json`, `out/validation.json` and the
  render's and sheet's provenance all name that SVG's digest;
- `flare_parts.py --verify` passed.

**1. The optimiser scored stale held-ray colours (Devin finding).**
- *Evidence:*
  - `Objective.evaluate` (`tools/optimize.py`) starts every colour fit from
    `self.K`, and scores every layer the fit does not free with `self.K`'s
    row. `self.K` was seeded from the parameters once, and again only if the
    number of layers changed.
  - The calibrated rays are held: never fitted, so their rows were never
    rewritten. An `Objective` that scored parameters A and then B, with B
    differing only in a held ray's colour, therefore scored B with A's
    colour.
  - Reproduced on the shipped file (stride 8, one fit iteration), reused
    objective against a fresh one:

    | state | old code, reused / fresh | new code |
    |---|---|---|
    | B (`flare_ray_c` x1.5) | 0.000203675 / 0.000204201 | equal |
    | C (three rays changed) | 0.000203675 / 0.000203732 | equal |
    | the stack with two layers swapped | 0.000233999 / 0.000203675 (15% off: rows misaligned) | equal |

    On the old code B and C score exactly as A.
- *Scope:* `optimize.py`'s own sweep never changes a held colour. The rays'
  shapes are out of the search and their colours out of the fit, so no D61-D66
  optimisation result was affected. Scoring the D66 file with a fresh
  objective gives 0.000203675212 on the old code and the new. The defect is in
  the API: any caller reusing one `Objective` across parameter states (a
  test, a tool, a later pass after recalibration) was scored wrongly.
- *Alternatives:*
  - Re-seeding the whole of `self.K` from the parameters on every evaluation:
    rejected. The rows of movable layers are the optimiser's own fitted state.
    `sweep` carries them from one accepted move to the next, and `main` writes
    them back at the end. Discarding them would change what the search does,
    not just fix the score.
  - Refreshing only when the layer count changes: that was the bug.
- *Action:* `Objective.colours(params)`, called at the start of every
  `evaluate`:
  - it re-seeds `self.K` from the parameters when the layer schema differs
    from the one its rows belong to (`self.K_ids`): the ids or their order,
    or which layers may use teal;
  - otherwise it refreshes exactly the held rows from `params_wc(params)` and
    leaves the movable rows alone;
  - `self.K` is replaced, not written in place, so an array a caller already
    holds is never changed under it.

  The teal part came from review. A movable layer that lost the teal
  permission between two evaluations kept its old teal amount, which the fit
  then locked in (`flare_ray_ur` with the rays free: reused 0.000203626
  against fresh 0.000203622, teal 0.1055 kept). No current caller changes
  eligibility mid-run, but the score must describe the parameters given.
- *Regression:* "the optimiser's objective scores the held ray colours it is
  given". It scores four successive states through one reused objective and
  through a fresh one (sharing only the basis cache, which is keyed on each
  layer's markup and so valid for any parameters):
  - A, the shipped file;
  - B, one held ray changed and nothing movable;
  - C, three held rays changed;
  - D, back to A.

  It requires:
  - the two scores equal for each state;
  - the reused objective's held rows equal each state's own colours;
  - the held change to move the score (0.26%, so the test is not vacuous);
  - a sweep's accepted colour state for the movable layers to survive a
    held-row refresh;
  - a reordered stack to re-seed.

  Two further requirements:
  - on a family-restricted trial, the path `sweep` actually takes, every
    other movable layer is scored at the accepted colours, not re-read from
    the parameters;
  - a layer that loses teal eligibility is scored without teal.

  Scores must be bitwise equal, since the arithmetic is the same. Run against
  HEAD's `optimize.py`, the check fails on B, C, the held rows, the
  reordered stack and the lost eligibility; the fixed code passes all of them.
- *Reviewed independently:*
  - A reviewer ran a main-style sweep (arc width, core radius, flare centre;
    rays held) with HEAD's module and the fixed one. The best score, the final
    score, K and the written parameters were bitwise identical, so the fix is
    a no-op for a normal run. `fit()` never writes a row it does not free,
    and the float32/float64 round trip is exact, so the held rows already
    equalled the file's colours there.
  - The first version of the regression let a wrong variant pass (resetting
    every non-freed movable row from the parameters, which changes sweep
    results). The family-restricted requirement above now rejects it, and
    six other partial fixes the reviewer tried fail as well.
  - `Objective` has no callers besides `optimize.py` and the test suite.
- *Artwork:* unchanged. This is a tooling change, and the SVG, the render and
  every published number are those of D66.

### Stage 2: the artwork

The tooling fix did not change the artwork: the D66 file rebuilt byte for byte
and scored identically on the old and the new objective. The items were then
taken in the brief's order, each judged on its own reading of the reference:
- **Round 1:** the colour basis, north of the core, the curves' flare-side
  glow and the lower-right.
- **Round 2:** the glow's revision after review, the vertical line, the
  junction and the curves' tips.

Each investigator worked only on scratch copies. Every candidate recommended
for a change was handed to two independent reviewers to refute.

| item | decision |
|---|---|
| (a) ray colour basis, re-checked with the corrected objective | no change: unaffected by the bug; teal on the six layers of record stays |
| (b) north of the core, red | **changed**: the halo gets one fitted directional gap north-east of the core |
| (c) the curves' flare-facing glow (and the right-ridge G box) | **changed**: `arc_glow2`'s flare side gets its own measured fade, and `arc_glow1b` a measured table; the right-ridge box is the flare's light, left |
| (d) lower-right inner segment | no change: misplaced, robustly, but no correction holds yet |
| (e) vertical line near the core | no change: its strength is right; the chroma gap sits on a background with the opposite error |
| (f) core/right-curve junction | no change: the core's white is too even by direction; an east-only fix overshoots the ring means |
| (g) the curves' tips | **changed**: the core narrows at its ends, drawn as a filled outline |
| (h) saturation | no global operation: the regions still disagree in sign |

**(a) The teal-aware colour basis, re-checked: unaffected by the optimiser bug,
and still the right basis.**
- *Evidence:*
  - None of the paths behind D66's colour decision used a reused
    `Objective`:
    - the colour-basis refit scores every candidate through an explicit
      colour array on one fixed stack;
    - the production-fit comparison starts `fit()` from an explicit array per
      run;
    - calibration re-reads the colours from the file on every refresh.

    `import optimize` appears only in the test suite, and D66 never ran
    `optimize.py`. The same script on the D65 file still reproduces D66's
    121.24 exactly.
  - Re-run on the D66 state (band cost on the calibration's reading, stack
    composite):

    | basis | band cost |
    |---|---|
    | shipped | 122.11 |
    | teal on six, refitted | 120.89 |
    | cone | 128.65 |
    | teal on every ray | 120.41 |
    | pure green on six | 120.84 |

  - The teal-on-six refit moves every teal layer, and five of the six other
    families, by at most 0.5 cv. Its whole gain is the lower-right family.
    There `flare_ray_c_in` moves R +2.95, G -2.27, B -2.60.
  - On the actual render, after recalibration, that gain nearly vanishes: the
    lower-right family goes 46.91 -> 46.73. Its direction also flips with the
    band subset (dropping r 36 gives R +8.9; dropping r 44 gives R -3.5,
    G -8.6). It is compensating the inner segment's misplaced geometry (g),
    not a hue.
  - The corrected `Objective` scores the D66 file with held rows equal to the
    file's colours (to their 0.01 cv rounding). Scoring D66, then the refit,
    then D66 again through one objective matches fresh objectives bitwise. The
    old module scores the refit with D66's `c_in` colour, 2.95 cv stale.
- *Alternatives:* the cone (render +7.14, four green rays 1.07-1.35x too
  blue); teal on every ray (render -0.25, all in the lower-right family,
  whose reference B/G 1.03-1.06 lies inside the cone, and on different layers
  than in D66); pure green (a tie that only re-decomposes the same hue). All
  rejected as in D64-D66.
- *Action:* none. The shipped colours stand, with teal on the six layers of
  record.
- *Uncertain:*
  - The stack composite reads the rays 8.6-9% lower than the render, so a
    small colour gain on it can vanish on the render. The render decides.
  - Upper-left B's reference hue is still undetermined.

**(b) North of the core: the red excess is white the reference lacks in the
north-east. Changed: the halo is given one fitted, directional gap.**
- *Evidence:*
  - On D66, box dx 2..9, dy -30..-18 about (531, 513.5): R +11.5, G +3.7,
    B +1.9. D65 read +9.4. D66's whiter right-curve glow added +2.1.
  - Column profiles of R, |dy| 15..33. In the north-east column (dx 1..7) the
    reference falls to its floor by dy -24: 84 / 55 / 29 / 7 / 3. The model
    reads 85 / 58 / 38 / 25 / 16. The west columns and the south match
    within about 5 out to |dy| 24. The notch is in the north-east only.
  - Its reference R=10 and R=25 contours sit 4-7 px closer to the core than
    the model's; G and B have no notch.
  - Removing white explains 0.74-0.90 of the RGB error variance in the
    north-east cells at 70-88 degrees, r 21-30. The reference lacks WHITE
    there, not R alone. That argues against a threshold effect.
  - Per-layer removal in the notch sector (70-90 degrees, r 20-35, error
    R +10.7):

    | layer | R contribution |
    |---|---|
    | `flare_halo` | 6.3 |
    | `flare_fan` | 5.1 |
    | `arc_glow1w` (the right curve's flare-side spill) | 4.5 |
    | `arc_glow2b` | 2.2 |

    The halo's own removal image explains 0.68-0.90 of the error variance
    there.
  - The fan's light sits at |dy| < 18, where the north-east is already right.
    A hard-wedge fit with every core white free takes the halo's wedge piece
    to 0-0.2 and raises the fan's.
  - Robust:
    - six north boxes and nine box offsets read R +5.8..+14.5;
    - it persists under Gaussian 1 / 2 and median-3 smoothing;
    - its edges fall mid-block and cross the 8-px block edges with no step,
      so it is light structure, not JPEG blocking.
- *Alternatives:* every existing lever, re-measured:
  - the fan's east half moved south: the north box reaches 4.8, but the
    near north-east goes to -18, the south mirror to +11.5 and core r<40 MAE
    to 5.72;
  - halo squash, cy, cx, rot and amplitude: each trades the far north-east
    against the near core;
  - an amplitude re-balance of every core white: gains 0.93-1.26, box only
    to 10.7;
  - a per-quadrant north/south gain on the fan's east half, idealised in the
    stack: box 11.7 -> 10.8, the same as a plain re-balance;
  - white arms moved out of the symmetric white: would need new arms in at
    least three other directions, and is dominated by the gap;
  - a white-to-cyan swap inside the wedge: the cyan is fitted at 0;
  - a darkening layer: impossible under screen, as in D64 and D66.

  The south mirror's apparent "needs more white" is mostly the right curve's
  flare-side foot (dx 7..9: R -11.7, G +6.2, B +8.5). On the flare-only
  columns it is only R -1.7..-3.1, so D66's "every lever trades north for
  south" was partly the curve.
- *Action:* a builder extension, `gap`, on radial layers
  (`Builder.gap_mask`): a luminance mask that removes a blurred annular
  sector of that layer's own coverage.
  - `flare_halo` gets gap `{cx 531, cy 513.5, th0 63, th1 88.5, r0 21.4,
    r1 60, depth 1, blur 2}`.
  - It only ever lowers one layer's coverage, so the composite remains a
    screen of non-negative layers: a directional layer, not a darkening one.
  - It is not arbitrary masking:
    - its eight numbers are fitted to the reference and held;
    - it acts on the one layer whose shape carries the missing white;
    - its gain is stable across th0 47-63, r0 19.4-23.4, blur 1.4-3 and
      depth 0.7-1;
    - a narrower variant (th0 68, r1 34) tested worse overall.
  - A file without a `gap` builds byte-identically (every parameter file in
    the repository and 60 scratch candidates checked).
- *Measured:* box R/G/B +11.5 / +3.7 / +1.9 -> +6.6 / +1.5 / 0.0.
  - Every one of six north boxes improves by 3.7-5.5 R, and every one of nine
    shifted boxes by 3.5-4.9.
  - North-east r 8-40 MAE 5.60 -> 5.34; the other quadrants are unchanged.
  - Core r<40 MAE 5.169 -> 5.117.
  - 260 pixels change, every one darker, none brighter. Their summed error
    falls 13.5%.
  - Calibration output is identical, line for line. `visual_regression`:
    0 of 16 fail. The west does not change.
- *Visible:* the north-east pocket between the vertical line and the right
  curve becomes a darker, cleaner cyan, as in the reference, and the model's
  R contours now dip into the reference's U-shaped notch. The change is a
  smooth blob: no step, wedge edge, hole or texture at 1x, 3x or 6x.
- *Verified independently:* two reviewers, one on the evidence and one
  visual, could not refute it.
- *Uncertain:*
  - The gap is at its limit (depth 1). The reference asks for 1.3-2.8x the
    halo's light at r 24-30. The remaining +6.6 R is the fan's tail and the
    right curve's white glow: a later fix must stay on those, not deepen the
    gap.
  - The north-west's R excess past r ~27 (+11) is a separate HUE error
    (G -4, B -7), not white. It is open, and untouched.
  - Inside the notch B is close to a wash. The east/west R step across the
    vertical line overshoots slightly at dy -34..-28. R at 60-70 degrees goes
    +2.0 -> -1.4.
  - Chromium renders the mask about 22% stronger in the item region. It also
    rounds about 855 pixels around the flare by ±1 cv (unbiased, invisible).

**(c) The curves' flare-facing glow: too slow a fall-off, 14-30 px out.
Changed: the broad glow gets its own fade on the flare side.**
- *Evidence:*
  - Measured station by station on both curves: 40-px foot-y stations, s =
    0..60 px from the curve of record. Masked: the rays (±8 px), the streak
    rows, the vertical line and r < 60 about the core.
  - Each layer's contribution was separated from per-layer maps, with the
    flare's own light kept as a separate term, so neither could absorb the
    other.
  - Pooled over y 300-740, model minus reference R/G/B (station rms of G):

    | band | left curve | right curve |
    |---|---|---|
    | near, s 6-12 | +0.7 / -2.1 / -4.3 (3.1) | +2.0 / +2.8 / +3.0 (3.8) |
    | mid, s 14-30 | -0.1 / +5.4 / +2.1 (5.7) | +0.1 / +6.3 / +3.2 (6.2) |
    | far, s 34-60 | -0.0 / -0.2 / +0.1 | +0.1 / +0.5 / +1.4 |

    The concave side's bands are already right (D66).
  - Separated into its parts:
    - the far field is right;
    - the excess is as large at r >= 150, where the flare's layers
      contribute nothing, as nearer the core;
    - the mid band's excess is `arc_glow2`'s sigma-19 convex tail, which
      falls off too slowly away from the curve.

    Its fade along the curve is a table measured on the CONCAVE side.
    Nothing ever measured it on the flare side, where the reference's glow
    falls off faster.
  - The mismatch is fall-off (width on the flare side), not brightness,
    position or overlap. The near band must rise as the mid band falls, and
    `arc_glow1b` (the near band, 6-14 px out) carries that.
  - The right-ridge box from D66 (dx 14..24, |dy| <= 10, G +3.2) is not this.
    It lies outside the curves at the core's rows. Its excess (+10..+12 G at
    u 12-26, |dy| < 10, down to about 0 by |dy| 30-60) follows the flare
    layers' own footprint (flare G 68 -> 45 -> 20-28 -> 2). It is the flare's
    light and is recorded, not acted on: a curve lever there would be using
    the curve to fix the flare.
- *Alternatives:*
  - `arc_glow2`'s width, blur, inset or amplitude: these are shared by both
    sides, and the concave side is right. Every one of them trades the flare
    side against the concave side.
  - A second glow layer on the flare side: duplicates the light the split
    already carries.
  - The central flare: excluded by rule. It is also not where the error is:
    the excess runs along the curves' whole middle length, far from the core.
  - Glow fixes by channel alone:
    - G only: the flare-side gain is 0.42-0.77, and it leaves B at -2..-4;
    - B only: 0.68-1.06, and it leaves G at +3..+5.
  - Blue added to `arc_glow2b` against the remaining hue: tested and
    rendered. The fit is tiny (+0.0025) and unstable in sign (left +0.0070,
    right -0.0020). It leaves the band's B MAE at 2.32 and worsens the right
    curve.
  - v1 of this change (review round 1): refined, not taken as it stood.
    - The right curve's flare-row knots were interpolated. They removed curve
      light where the flare hides the evidence, and cost north-of-core R.
    - Several gains rose above 1.0 at the tips.
  - A 40-px ramp into the held rows: the same item readings, but a worse
    flare zone (B MAE 6.08 against 6.00).
  - Capping `arc_glow1b`'s left gains at 1.25 or 1.35: lowers the edge-foot
    overshoot, but only by giving back near-band gain. Rejected.
  - Leaving `arc_glow1b`'s right flare rows at their interpolated raise
    (the investigator's version). It helps the north-east flare sector at
    r 30-60 (G/B MAE 4.79 / 7.73 -> 4.29 / 6.85) and the north box. But it
    adds unmeasured light into the box north of the core, the first
    priority of this pass. Not taken; the sector's cost is recorded.
  - Holding the LEFT curve's flare rows as well (review suggestion, tested
    on both layers, calibrated at 0.51):
    - it helps the south-west flare zone (sector 180-225 B MAE 5.94 ->
      5.33);
    - but the left curve's own measured stations beside the flare rows get
      worse: 440 mid band G / B +3.1 / +1.1 -> +5.6 / +3.7, 520 ΔE 2.59 ->
      2.98;
    - r 60-90 goes 2.52 / 3.62 -> 2.81 / 3.91;
    - the between-curve band 2.45 / 2.32 -> 2.49 / 2.35.

    The curve's own reading decides this item, so the left curve stays
    interpolated.
- *Action:* a builder option, `convex_taper`, on a tapered, frame-clipped arc
  layer.
  - The layer is split along its curve of record moved 1.5 px toward the
    flare, inside the curve's bright core. The concave part keeps the
    layer's own taper, and the flare-facing part takes the convex taper.
  - The two clip regions are complements, extended along the curve's end
    tangents past the frame.
  - `arc_glow2` gets `convex_taper: glow2_cv`. That table is `glow2`'s own,
    on its own 20-px knots and convention, times a per-side gain g(y):
    - g is 1.0 at y <= 200 and y >= 840;
    - left, y 240..800: 1.00 1.00 1.00 0.96 0.86 0.69 [0.74 0.79
      interpolated] 0.85 0.86 0.73 0.73 0.87 1.00 1.00;
    - right, y 240..440: 0.89 0.78 0.62 0.59 0.73 0.89;
    - right, y 460-540: HELD at 1.00, with 20-px ramps. There is no clean
      data under the flare, so the curve glow does not remove light there
      without evidence;
    - right, y 560..800: 0.75 0.74 0.73 0.79 0.89 1.00 1.00;
    - every gain is capped at 1.0: the flare side never gets more of glow2
      than the concave side.
  - `arc_glow1b`'s shared ramp becomes a measured per-side table on the
    ramp's own stops plus 20-px knots, peaking 1.49x on the left and 1.22x on
    the right. Its colour is doubled and its table halved, so every stop
    stays <= 1. Its width, blur and inset are unchanged.
  - Over the right curve's flare rows, `arc_glow1b` is held at its old level
    too (from review, below). Its interpolated raise there (1.12-1.19) had
    no data under it, and it landed in the box north of the core: G/B MAE
    2.63 / 2.71 -> 3.30 / 2.97. Held, that box reads 2.67 / 2.69.
  - On the left curve the flare rows are 66 px from the core, and the
    interpolated knots are kept: they are what the left curve's own band
    readings support (below).
  - The calibrated rays re-balance to the new background:
    - upper-left A x0.967, B x0.965, B2 x0.944;
    - lower-left `llc` x0.960, `llc_in` x0.987, `lld2` x0.958, `lld` x1.004;
    - the other seven are unchanged.

    Calibration converges at 0.51 of tolerance (base 0.78).
  - `optimize.taper_specs` counts a convex taper's user, so `glow2_cv` stays
    in the search space.
  - A file without `convex_taper` builds byte-identically: every one of
    2,168 parameter files in the repository and the scratch area.
- *Regression:* "an arc's convex taper acts only on its flare-facing side".
  - With the convex taper set to the layer's own taper, the whole composite
    equals the unsplit build (max 1.00 cv). The split is a partition, and
    its anti-aliased seam is screened by the core.
  - The shipped convex taper changes `arc_glow2` by 0 cv anywhere on the
    concave side (d < -1 px), and by up to 28 cv on the flare side.
  - A stack without a convex taper emits no split.
  - The optimiser searches `glow2_cv` for `arc_glow2`.

  With the two clips swapped, the check fails on both the concave and the
  flare-side conditions. Without the optimiser change, it fails on the
  search.
- *Measured* (base = D66 plus the halo gap):
  - the three bands, as in the table above:
    - left: near -2.1 / -4.3 -> -1.0 / -2.2 (G / B), mid G +5.4 -> +2.6;
    - right: near +2.8 / +3.0 -> -0.8 / -0.3, mid G +6.3 -> +3.1;
    - station rms of G: left 3.1 / 5.7 -> 1.5 / 3.2, right 3.8 / 6.2 ->
      1.1 / 2.8;
  - the band between the curves (s 5-60, r >= 60, rays masked):
    - MAE R/G/B 1.39 / 3.22 / 2.90 -> 1.39 / 2.45 / 2.32;
    - CIE76 ΔE 2.50 -> 2.21;
  - the right curve's flare-side edge foot: G/B MAE 12.39 / 13.14 -> 10.91 /
    11.97;
  - the rays stand out more from the background between the curves. Their
    transverse flux above the local ramp goes toward the reference: upper-left
    inner 50 -> 72 (reference 114), lower-left -56 -> -29 (reference 10);
  - the concave side: 1 px changes, by 1 cv. The core r < 12, the junction
    columns, the right-ridge box and the west check are unchanged.
- *Costs, recorded:*
  - The flare zone between the curves at r 30-60: mean B -3.73 -> -5.02, in
    the south-west sectors. This is the left curve's interpolated flare rows
    and the recalibrated lower-left rays.
  - Background B along three corridors: upper-left inner 2.49 -> 3.26,
    229 6.15 -> 7.28, lower-left 4.97 -> 5.72. 268 improves (G 4.64 ->
    2.49).
  - The left curve's edge foot (s 3-6): G/B MAE 9.14 / 9.22 -> 9.34 / 9.70.
    Its G = 100 crossing moves to 5.05 px, against the reference's 4.67.
  - The right near band at y 240-360: ΔE 6.03 / 4.90 / 2.53 -> 6.24 / 5.32 /
    2.99. The mid band there improves strongly.
  - The north-east flare sector at r 30-60 (331 px): G/B MAE 4.60 / 7.43 ->
    4.79 / 7.73. The north box x 505-560, y 440-490: 3.64 / 5.27 -> 3.85 /
    5.62. This is glow2's reduced tail next to the held rows.
  - 268's hue B/G: 0.85 -> 0.80.
  - Upper-left ray presence: 0.935 -> 0.871, inside its band [0.40, 2.20].
- *Visible:* on the curve sheets, the broad over-bright shoulder 10-30 px out
  on the flare side becomes dimmer and narrower, as in the reference.
  - The better/worse maps are green along both flare-facing bands over their
    whole middle length.
  - The right curve's darkening fades smoothly into the held rows, with no
    step, notch or band.
  - No seam shows at the split at 1x, 3x or 6x.
  - The concave glow, the cores, edges, lobes, upper-right and lower-right
    look identical.
  - Faint red remains beside the left curve at the core's rows, and as specks
    along two ray corridors.
- *Verified independently:* two reviewers, one on evidence and attribution
  and one visual, each with their own code. Neither could refute it.
  - Evidence:
    - the between-curve G excess is stable under every window, mask, curve
      offset and JPEG block phase tried, and at r >= 150 as much as nearer;
    - of the layers removed one at a time, the flare-facing tail of
      `arc_glow2` explains it best (R² 0.69 / 0.81);
    - the change improves G in every 2-px bin from 12 to 40 px on both
      curves.

    It found two more things:
    - the flare zone's B cost lies almost entirely in the ray corridors (+754
      of +783 summed error), and the background there, rays masked,
      improves;
    - the rays' 3-6% recalibration comes from the calibration's linear-ramp
      template reading the glow's new background shape. The reviewer's own
      reference-fitted ray amplitudes did not move with the glow change.

    Its suggested hold of `arc_glow1b`'s right flare rows was taken.
  - Visual:
    - an identity split changes 286 px by at most 1 cv, and nothing changes
      at the split line itself;
    - the item region's hue moves toward the reference;
    - the cross-curve profiles stay monotonic, with no double edge;
    - there is no new texture;
    - Chromium's change matches resvg's (difference-of-differences 0.023
      cv).

    Its suggested left-curve hold was tested and not taken (Alternatives).
- *Uncertain:*
  - The hue is not fixed. The mid band keeps G +2.6 / +3.1 with B already
    matched (-0.7 / -0.3). The reference's B/G there is 1.28 / 1.34, the
    model's 1.19 / 1.22. The remaining error is excess green, which blue
    cannot fix. It would need the flare-facing part to carry its own bluer
    colour: a colour-basis step, not taken here.
  - The flare rows are an assumption. The right curve is held, the left
    interpolated; neither has clean data under the flare.

**(d) The lower-right inner segment: misplaced, robustly; no correction is
robust yet.**
- *Evidence:* the line was read at 4-px steps from r 24 to 100 over 18
  template variants: half-width 9/12/15, offset -1/0/+1, linear or quadratic
  ramp.
  - r 24-31: no ray is measurable; the line crosses the right curve.
  - r 32-40: the onset is too early in all channels (R +3.7 / +3.4 at r 32 /
    36, 18 of 18 variants).
  - r 40-50: the white peak is ~5 px too far in and too spread. Reference
    peak at r 44.7, half-maximum r 38-48; model at r 38.6, r 34-46. The white
    flux is the SAME (230 against 234). At r 40-46 the reference is nearly
    pure white (cyan above the ramp 0.9-3.4, model 5.0-10.2).
  - r 50-58: the falloff is slightly strong.
  - r 60-76: matches.
  - r 78-92: the line-to-flank hand-over (G/B -1.6..-2.7), not this segment.

  Width and position match within the centre-definition spread; the
  translation of record is kept.
- *Alternatives:*
  - A true white/cyan split, a new cyan layer on the old shape: the best fit,
    reproducing the reference's white peak (16.0 at r 44.4, flux 233). But
    calibration cannot converge (1.45 of tolerance), because the family
    reading has no band that separates the inner cyan from `flare_ray_c`.
  - `c_in` white only: the calibration piles on white (flux 297).
  - `c_in` whiter, fade refitted: calibrates. G and B improve at r 32-48, but
    R gets worse at r 40 and r 52 (18 of 18), the white is 14% too strong, G
    at r 44 leaves the reference's range, and the core's SE quadrant R
    worsens.

  Every placement that corrects the ray also exposes a broad red-field error
  east of the right curve. It is too dark at r 28-40 and too red at r 44-58,
  over the sectors -40..+40 degrees, not only on the line. The misplaced
  white partly hides it. This is D66's objection, and it still holds.
- *Action:* none.
- *Uncertain:* the prerequisites, in order:
  1. correct that broad red radial edge at its source (the core's symmetric
     white and the curve's white glows);
  2. give the lower-right family a reading that separates the inner cyan
     (for example 4-px single-template bands inside r 60), so the colour
     split can be calibrated.

**(e) The vertical line near the core: its strength is right; its chroma gap
sits on a background with the opposite error. No change.**
- *Evidence:*
  - Line strength and colour. On fixed templates (the median of 54: centre
    529.0 / 529.4 / 529.8, sigma 1.4 / 1.7 / 2.1, half-width 5 / 6 / 8,
    background order 1 / 2), the reference's narrow component at |dy| 24-32
    has the same luma as the model's line on both sides (dY -0.9 / -0.6 north,
    +1.2 / +0.2 south). The difference is a narrow Cr bump the model lacks
    (dCr -4.5 / -2.3 north, -4.5 / -4.2 south). This holds for every template
    and both 8-row band phases. At |dy| 32-36 and at N 72-104 the reference's
    hue is back to the layer's own (kR/kG 0.36 against 0.34).
  - So the mismatch is not the line's amplitude, its north/south balance or
    the core arms. The streaks, `flare_core_w`, `flare_ray_east_in` and
    `flare_cloud_w` contribute 0.0-0.3 there.
  - North: the axis R is already right or high (+1.2 / +4.5 at N 24-28 /
    28-32). The line's R contrast deficit comes from both flanks being too
    red, where the reference's R is near its floor:
    - west flank +7.1 / +11.5, from `flare_ray_a_in` 9.7, `flare_halo` 4.3,
      `flare_fan` 2.0 and `arc_glow2b` 1.8;
    - east flank +7.9 / +5.6.

    Separated into line and background, the background errs by R +7.5..+8.6
    and G/B -3..-7 (the far glow's), about 1.3-2x the line's own R deficit.
  - South: the axis R is 0..+3.5 at S 28-36 and the flanks are red from the
    S arm (19.2 R on the west flank).
  - The D67 halo gap moved the north line reading 5.11 -> 3.89 (mean |d| R,
    |dy| 20-36) and the east flank at N 24-28 from +12.1 to +7.9. Both are
    toward the reference.
- *Alternatives:*
  - A paired white line with the line re-tabulated (D66's candidate, rebuilt
    on the current base): the line's own reading improves (north 3.89 ->
    1.62, south 3.78 -> 1.66). But the raw north axis MAE worsens (3.83 /
    3.75 / 5.27 -> 5.33 / 5.81 / 8.73), and the south axis R and B worsen as
    well. The same outcome as in D66.
  - The raw-optimal line: it wants no white in the north, only a brighter
    cyan line. That would fill the background's G/B deficit with the line
    (north line reading G/B 1.00 / 3.12 -> 5.29 / 9.16).
  - White on the south side only: better at S 24-28, one JPEG block row, and
    worse at S 28-36. The reference's line is white on both sides, so the
    asymmetry is unsupported.
  - A whiter colour for the whole line: breaks N 72-104, where the hue
    already matches.
  - Extending the halo gap across the axis: the axis G/B get worse, and so
    does the line's R reading.
  - Moving the S arm east: the south box and axis get worse.
- *Action:* none. The line itself is not globally modified.
- *Visible:* at normal scale the reference, the shipped render and every
  candidate look the same along the line near the core. The reference's line
  is a faintly whiter streak at |dy| ~24-32. The model's line is slightly
  more cyan there, but its surroundings north of the core are paler, so the
  line stands out less.
- *Uncertain:*
  - Whether the chroma gap is real light. JPEG 4:2:0 alone, at q55-85, moves
    the model's own line's Cr by up to about ±4-5 in these bands. The
    reference's per-row line amplitudes are block-locked in R, G, B and Y,
    but not in Cr. It is not claimed to be an artefact, only that it is no
    finer than the compression.
  - A whiter near-core line helps the raw pixels only once the north
    background around the axis is less white and more cyan. That is the open
    north-west hue item of (b), not a line lever.

**(f) Where the core meets the right curve: four parts, none of them the east
arm's fit. No change.**
- *Evidence:* read at 1-px resolution (columns 527-555, rows 489-537).
  - The 3-row readings (rows 512-514, R) stand at -9.0 / -13.3 / -8.0 at
    columns 539 / 540 / 541. G/B there are within +2.3, so white is missing,
    not light.
  - **Column 539 and the south-east core side are the core's own shape.** By
    45-degree sector at r 4-12, R is -3..-11 to the east and south-east, and
    +2..+5 in every other direction (for example N +3.7, S +4.6, NE +5.2 at
    r 8-12). G is within about ±3 everywhere.
    - This holds under two sector phasings.
    - The whole-ring means match the reference (232.5 / 204.7 / 175.7 against
      233.0 / 204.5 / 175.7) only because the east's deficit cancels the
      excess elsewhere.
    - The reference's bridge to the curve is narrow: about 10 px across at
      half height, centred about 1.5 px south of the core row. It needs
      0.30-0.50 screen-white at dx 5.5-9.5, where the 22-px-tall east arm
      gives 0.13-0.25.
  - **Column 541 is the curve's edge.** Along the whole right curve (y
    386-644) the first bright column past the steepest R rise is R -7..-55.
    - The model's R edge sits 0.1-0.6 px east of the reference's; its G edge
      matches within ±0.1.
    - No arm variant moves it by more than 0.04 px.
  - **Column 540 is a mixture:** white foot light at the core rows only (R
    -7..-17), plus that curve edge.
  - **The flanks (|dy| 11-16) are a colour mismatch,** not missing white:
    R -11 / -19 with G/B +16 / +20 (north) and +5 / +8 (south), from the
    cyan of `flare_halo_far`, `arc_glow2` and `arc_glow1b`.
  - It is not compositing. At the core rows G/B are 247-255 in both images.
- *Alternatives:* refits of the east arm (`flare_ray_east_in`, all eight
  geometry keys, white solved each trial, every other layer fixed).
  - On boxes that include the edge columns: better on all five boxes, and the
    columns go to -5.7 / -9.0 / -5.7. But:
    - the r 8-12 ring mean overshoots the reference (175.7 -> 176.5);
    - onset is pinned at its bound;
    - its rotation and cy are not unique across restarts;
    - the flank G/B and the south core get worse.

    Freed from its bound, the arm becomes a white stripe on the curve's edge
    (onset 8.3 px, white 0.95): the flare making up for the curve.
  - Penalised so that no ring mean rises: 1-3 R at the columns, paid for by
    darkening the east at r 4-8 (221.6 -> 219.6, against the reference's
    225.7). A trade.
  - A narrow arm (13-15 px) fitted on the core side: best at the core rows (3-
    row sum 55 -> 28). But:
    - the junction box worsens by 5% and D65's by 8%;
    - the flanks darken by 5-6 R;
    - the r 4-8 ring overshoots by 1.1;
    - the arm's height depends on which box is fitted.
  - More white on the flanks worsens their G/B.
  - Raising the right curve's white glow at the core's row: brightens the
    concave side, where the right-ridge box is already R +1.7.
- *Action:* none.
  - The ring-mean limit decides it: any east-only white overshoots them,
    because the base matches only by cancellation.
  - The fix the evidence points to changes `flare_fan`, `flare_halo` and
    `flare_core_w`, not only the arm: it makes the core's symmetric white
    directional (less to the north, west and south at r 4-12, more to the
    east and south-east), then fits a narrower, brighter arm. That is a
    redesign of the core, which this pass was asked not to do, and it would
    move every quadrant's reading.
  - Column 541 and the flanks belong to the curve's edge and its cyan glows.
- *Visible:* at normal scale the best refit is indistinguishable from the
  base. In a 7x zoom, the reference's white bridge is narrow and slightly
  south of the core row. The narrow arm looks closest there, but it visibly
  darkens the edge above and below the core row.
- *Uncertain:*
  - The split of column 540 between flare foot light and the curve's edge.
    The edge offset depends on the level read, and both channels are close to
    clipping there.
  - The needed-white map rests on R alone near the core, where the
    reference's G/B clip and its R is 240-247, which amplifies JPEG noise.

**(g) The curves' tips: the core is 0.2-0.45 px too wide on both edges.
Changed: the core narrows at its ends, drawn as a filled outline.**
- *Evidence:*
  - Read along the normal of the curve of record, image minus reference (+
    = wider). Medians over 29 variants: R, G and luminance; level 0.3 / 0.5
    / 0.7; tangential window ±0.5 / ±1.5 / ±4 px; absolute R thresholds 80
    and 110.

    | tips | flare side, left / right | lens side, left / right |
    |---|---|---|
    | y 100-170 | +0.22 / +0.19 | +0.38 / +0.33 |
    | y 850-930 | +0.28 / +0.30 | +0.38 / +0.36 |

  - Smoothed images (Gaussian 0.7 / 1.0, 3x3 median) read +0.14..+0.45.
    The excess does not depend on JPEG block phase: split by x mod 8, y mod
    8, and on a block boundary against the interior, it is the same.
  - It is not positive in every reading, as first claimed. On the right
    curve's flare side, the 70% level reads +0.02 at the north tip and an
    absolute R >= 110 threshold reads -0.19 / -0.21. There the plateau is
    13-20 R too dark, which confounds absolute thresholds.
  - The reference's core narrows toward its ends:
    - about 6.7 px at y 220-240;
    - 6.1-6.4 px at y 110-170;
    - 6.6 -> 5.9-6.3 px from y 800 to 930.

    The model's single stroke is 6.85-6.9 px there. D66's "a screen layer
    cannot subtract" is true of adding layers, but not of the core's own
    width.
- *Alternatives:*
  - Narrow `arc_core` along its whole length and give the width back at
    mid-height through `arc_core_wide` / `arc_core_edge`. Rejected:
    - the tips improve, but those two strokes are cyan (R 94) and cannot
      replace the white core ring that narrowing removes;
    - even with a free alpha at every station, the middle gets worse (mid
      profile rms 5.62 / 7.80 -> 6.33 / 8.50);
    - the left flare-side mid edges leave D66's range (-0.23..-0.35);
    - junction column 541 goes -7.8 -> -8.7 at 6.6 px and -11.4 at 6.4 px.
  - Re-shaped thin strokes: every variant worsens the middle.
  - A sharper core blur: the reference's tip edge is sharper, but its
    mid-height edge is softer, and one blur per layer cannot do both.
  - Refitting the edge strokes' colour: adds fitted numbers where D66 chose
    not to, and would raise the mid-height plateau, which is already 7-15 cv
    too bright.
  - A polyline outline: exact, but it grows the SVG by 37 KB. The cubic
    outline is within 0.005-0.02 px of it.
- *Action:* a builder option, `width_taper`, on arc layers.
  - The layer is drawn as one filled outline: the curve of record offset by
    ±w(y)/2 along its normal, with round ends. It is sampled every px of arc
    length and emitted as cubic Hermite pieces every 24 px.
  - `arc_core` gets `width_taper [[170, 0.9368], [210, 1.0], [820, 1.0],
    [860, 0.9368]]`: 6.832 px from y 210 to 820, narrowing linearly to 6.40
    px by y 170 and 860, held beyond. The tip width is flat in effect over
    6.3-6.5 px.
  - A layer without the key is still a stroke. The two new options do not
    combine on one layer; the builder refuses that.
- *The switch itself is not neutral.* Rendered at factor 1 (no narrowing),
  the outline is not identical to the stroke:
  - Over the right curve's rows 400-540, resvg's stroke of the long upper
    cubic sits 0.10-0.26 px east of the analytic curve of record. Its
    flattening chords fall on the concave side.
  - The outline, built from 24-px pieces, stays within ±0.08 px of the curve
    of record there, and within 0.14 px everywhere.

  So the switch also moves `arc_core` back onto the curve of record by up to
  about 0.25 px near the junction.
  - It changes about 6,600 pixels, all within 12 px of the curves.
  - It is neutral to slightly better: middle-corridor error -0.9%;
    junction columns 540 / 541 -13.3 / -8.0 -> -13.0 / -7.0.
  - The thin strokes around the core (`arc_core_wide`, `arc_core_edge`)
    keep the stroke's flattening. D66 measured and fitted their placement
    in that state, and it is left as it is.
- *Regression:* "a width-tapered arc narrows only where its table says".
  - `arc_core`'s coverage across the curve is 0.9366 / 0.9376 of the
    stroke's at the tips (table 0.9368) and 1.0001 in the middle.
    Coverage integrates the blur, so this reads the width itself.
  - At factor 1, the outline's half-level centre stays within 0.13 / 0.14 px
    of the analytic curve of record (left / right). resvg's stroke reads
    0.18 / 0.26.
  - An arc without the key is still a stroke.

  It fails when the builder ignores the table (coverage 1.000 at the tips)
  or the key.
- *Measured:*
  - R half-level tip edges (flare / lens side):
    - left north +0.24 / +0.43 -> +0.03 / +0.19;
    - right north +0.19 / +0.40 -> +0.00 / +0.17;
    - left south +0.28 / +0.46 -> +0.09 / +0.24;
    - right south +0.26 / +0.45 -> +0.07 / +0.23.

    The 29-variant medians are now flare side +0.01..+0.11 and lens side
    +0.09..+0.16.
  - Changed pixels in the tip corridors: summed |error| 79,108 -> 68,225
    (-13.8%).
  - Curve-band MAE R/G/B at the ends:
    - left north 10.1 / 12.4 / 11.3 -> 8.5 / 11.5 / 10.1;
    - left south 9.5 / 11.5 / 11.1 -> 7.9 / 10.4 / 10.0;
    - right north 13.0 / 14.4 / 12.9 -> 11.9 / 14.2 / 12.3;
    - right south 9.8 / 12.6 / 12.6 -> 8.7 / 11.9 / 11.8.
  - Mid-height flare-side edges stay in D66's band. Calibration is
    unchanged: no ray moved, and it verifies at the same tolerance.
- *Visible:* at 1x the tips look a touch slimmer, as in the reference.
  - At 3.75x the better/worse maps are mostly green along both edges of all
    four tips.
  - There is no step at the transitions (y 170-210, 820-860) and no
    artefact at the round ends.
  - The difference panel still shows the tips' softness mismatch, weaker: a
    thin line just outside each edge.
- *Verified independently:* two reviewers, one on evidence and attribution
  and one visual. Neither could refute it.
  - `arc_core` rendered alone has the composite's tip widths within 0.01
    px. A blur-only control leaves the width error where it was. The gain
    is the taper's (-13.6% on the tips), not the switch's (-0.1%).
  - Chromium renders the outline correctly, and more faithfully than its
    stroke (centroid rms 0.032 / 0.036 px against 0.066 / 0.061).
  - At 12x the round ends match the stroke's caps. There is no ripple at the
    24-px knot spacing.

  Both corrected the record on three points:
  - **The gain is confined to the edge zone.** Over the tips and
    transitions, the edge zone (3 < |s| <= 5) improves: R / G / B summed
    error 115 / 100 / 110 -> 69 / 78 / 79. But the shoulder just inside the
    edge (2 < |s| <= 3) gets worse by 15-23% (R 85 -> 98, G 92 -> 113, B 93
    -> 109), and the plateau by about 5%. The right north tip's G gets
    slightly worse.
  - **The narrowing removes light.** On three of the four tips the core's
    total light falls a further 2-5% below the reference, whose core there
    is narrower but not dimmer. About 60% of the changed tip pixels get
    worse, while the summed error falls 7.5-18% per tip. These tips' dimness
    must not later be read as evidence for more narrowing; it is the next
    item (a sharper edge or a brighter plateau), not this one.
  - **Some width remains.** The core is still +0.25..+0.42 px wide at the
    south tips and in the transition bands, where the reference is already
    6.34-6.45 px.
  - The visual reviewer also saw an existing mismatch this item does not
    touch: the reference's curves continue further toward the frame corners
    than the model's tips. That is a fade-table matter, not width.
- *Uncertain:*
  - About 0.1 px of lens-side excess remains at the tips. About half of it
    is the model's own: `arc_core`'s along-y alpha paint tilts its profile
    across the oblique ends (+0.12..+0.14 px). The rest would need a
    centre-line shift, which the curve of record forbids.
  - The tips' dominant remaining error is profile shape, not width:
    - the reference's edge is sharper (10-90% about 1.45 px, against
      1.75);
    - it has faint bright rims near s ±2;
    - the right curve's north tip plateau is 13-17 cv too dark, which is
      its fade table, not its width.
  - The switch relies on resvg flattening the cubic outline as it was
    checked here, for the pinned resvg-py. Chromium agrees: cross-engine
    MAE 2.691 (D66 2.693).
  - The SVG grows by about 8.6 KB.

**(h) Saturation: still no global operation.**
- *Evidence:* region by region, the final render's saturation against the
  reference's (S = 1 - min/max of the region's mean colour, x100; D66 in
  brackets):

  | region | saturation | what drives it |
  |---|---|---|
  | core r < 12 | +0.3 [+0.3] | |
  | ring r 12-40 | -1.8 [-1.8] | R +2.3, B -2.0 |
  | mid flare r 40-130 | -2.4 [-2.2] | R +1.7, B -2.7 |
  | lower-left rays | -1.8 [-1.7] | |
  | upper-left rays | +0.4 [+0.4] | |
  | upper-right ray | 0.0 [0.0] | |
  | lower-right ray | -0.1 [-0.1] | |
  | curve ridges | +0.8 [+0.6] | |
  | between the curves, 3-30 px from a ridge | -0.1 [+0.1] | |
  | outside the curves, 3-30 px | -0.6 [-0.8] | |
  | lens far | +1.5 [+1.6] | |
  | outer field | +1.5 [+1.5] | |

  The signs still disagree:
  - the flare's ring and middle are under-saturated;
  - the field and the far lens are over-saturated.

  A global saturation change would move them all one way, fixing one group
  and worsening the other. Where the flare is under-saturated, the cause is
  local hue, not a missing saturation:
  - an R excess from the core's white (the open north-west item of (b), and
    (f)'s directional white);
  - B deficits along the ray corridors and in the south-west flare zone
    ((c)'s cost).
- *Effect of D67's changes:*
  - The between-curve band's luminance and chroma moved onto the
    reference: Y +0.8 -> -0.1, chroma +0.7 -> -0.1. That is (c).
  - In the mid flare, luminance now matches (+1.6 -> +0.1), and its chroma
    deficit grew (-2.4 -> -4.3), because the glow's tail carried G and B
    there as well as the excess.
  - The curve ridges lose 1.1 of luminance (Y -2.3 -> -3.4). That is (g)'s
    narrowing at the tips.
- *Action:* none. No global saturation, desaturation, blur or sharpening was
  used anywhere in D67.

### What was preserved

- The west-side triangular field stays absent. `visual_regression`'s west
  check reads 0.782 as before. The west box's only changed pixels (22, by at
  most 1 cv) lie on the left curve's own core.
- Every reference-supported structure D66 listed is kept, and no layer was
  added or removed (54 named layers):
  - the upper-left rays;
  - the lower-left segments and the 229-degree lobe;
  - the upper-right line and slab;
  - the lower-right translation, line and flank;
  - the vertical line and the soft horizontal lines;
  - the core's three white arms;
  - the curves and the frame.
- The ray architecture is unchanged: no ray geometry moved (RAY_GEOMETRY is
  untouched). Seven calibrated rays re-balanced by 0.944-1.004 to (c)'s new
  background, and calibration converges at 0.51 of tolerance (D66 0.78).
- The curves of record, the lens ellipses and the flare centre are
  unchanged. The one geometric consequence is (g)'s switch, which puts
  `arc_core` back onto the curve of record where resvg's stroke had drifted.
- The deliverable is still vector only, with no bitmap and no JPEG texture.
  None of the three changes follows 8-px block structure; each was checked
  at both block phases.
- The three builder options (`gap`, `convex_taper`, `width_taper`) are
  byte-neutral: 2,168 existing parameter files build identically.

### How the decisions were made

- The order was the brief's:
  1. the tooling bug, fixed and regression-tested before anything else;
  2. the colour basis re-checked with the corrected objective;
  3. then the visual items in the brief's priority order;
  4. the curve tips last.
- Every item was read with several functionals (windows, templates, offsets,
  channels, levels, JPEG block phases) before anything was built. Where
  readings disagreed in sign, the item was left, and the disagreement was
  recorded.
- Every candidate was a full copy of the parameters with one local change:
  - rendered by resvg at 1024;
  - recalibrated where rays could be affected, and required to converge;
  - read with the item's own functionals and its neighbours';
  - looked at in reference / base / candidate / difference / better-worse
    sheets at 1x to 12x.
- Every candidate recommended for a change went to two independent
  reviewers, one on evidence and one visual, told to refute it with their
  own code. Six reviews over three candidates: none refuted. The two
  adjustments they proposed were measured. One was taken, (c)'s right-curve
  hold; one was not, (c)'s left-curve hold, which is worse on the item's own
  reading. Their corrections to the claims are written into (c) and (g).
- Whole-image metrics were recorded as consequences, never as the criterion.

### What the numbers did

    measure                 D63 (e9fa99c)   D64 (e61e46a)   D65 (e8f522d)   D66 (dbb0087)   D67 final
    MAE                     1.8051          1.8039          1.8036          1.7323          1.6986
    RMSE                    3.816           3.815           3.812           3.284           3.152
    SSIM                    0.97455         0.97456         0.97457         0.97561         0.97603
    edge IoU                0.6944          0.6936          0.6937          0.6947          0.6981
    centre-region MAE       5.971           5.946           5.947           4.706           4.589
    flare r<110 MAE         5.178           5.170           5.171           4.184           4.044
    core r<25 MAE           5.446           5.153           4.705           3.902           3.747
    bright-region MAE       9.662           9.664           9.664           8.159           7.994

By change (MAE / RMSE / centre / flare r<110 / core r<25 / bright):
- D66: 1.7323 / 3.284 / 4.706 / 4.184 / 3.902 / 8.159.
- (b), the halo gap: 1.7321 / 3.283 / 4.696 / 4.177 / 3.835 / 8.159.
- (c), the curves' flare-side glow, added: 1.7094 / 3.247 / 4.599 / 4.051 /
  3.806 / 8.087.
- (g), the curve tips, added (final): 1.6986 / 3.152 / 4.589 / 4.044 / 3.747
  / 7.994.

These are consequences, not the criterion. The per-item readings in (b),
(c) and (g) are what each decision rests on.
- RMSE and the bright-region MAE fall most in (g), which moves the highest-
  contrast pixels in the image: the curves' core edges.
- The core metric falls in (b) and (g). In (g) that is the switch's return
  of the right curve's core onto its geometry next to the flare.

### Remaining, with the reason

- **North of the core,** R about +7 (box dx 2..9, dy -30..-18). The halo's
  gap is at its limit. The rest is the fan's tail and the right curve's
  white glow ((b)).
- **The north-west of the core,** R +11 past r ~27: a hue error, G -4 and B
  -7, not white ((b)). It is also what keeps a whiter vertical line from
  helping the pixels ((e)).
- **The core's white is too even by direction.** East and south-east are
  short and the other directions long at r 4-12. Fixing it means making the
  core's symmetric white directional, a redesign ((f)).
- **Between the curves,** the flare-facing glow still carries excess G (+2.6
  / +3.1) with B matched. It needs its own bluer colour on the flare side
  ((c)).
- **(c)'s recorded costs:**
  - B along three ray corridors and in the south-west flare zone;
  - the left curve's edge foot;
  - the north-east flare sector.
- **Just past the right curve at the core's height,** G +3.2: the flare's
  own light, recorded and not moved with a curve lever ((c)).
- **The lower-right** white inner segment peaks about 5 px too far in. Its
  correction waits on the broad red field east of the right curve ((d)).
- **The vertical line's** near-core chroma is at the size of the
  compression's own noise ((e)).
- **The curves' tips:**
  - they are still +0.1..+0.4 px wide in places;
  - their edges are softer than the reference's;
  - three of four tips are 2-5% short of light;
  - the curves end short of where the reference's fade toward the frame
    corners ((g)).
- **Upper-left B's** hue is undetermined by the reference (D66).

### Validation

- `sh tools/publish.sh`: **PUBLISH OK**. That includes:
  - the cross-engine check (resvg against Chromium, MAE 2.691; D66 2.693);
  - the before/after sheet's `--verify` step;
  - the reproducibility step.
- `tools/test_pipeline.py`: all 67 checks pass (63 in D66). The four new
  ones are:
  - the objective's held-row scoring (1);
  - the halo's gap (b);
  - the convex taper (c);
  - the width taper (g).
- `measure_flare` calibration verifies as converged, worst correction 0.51
  of tolerance (D66 0.78), and leaves the file byte-unchanged.
- `visual_regression`: 0 of 16 structural checks fail. The west check reads
  0.782, so the west triangle stays absent.
- `src/params.json` rebuilds `reconstruction.svg` byte for byte. The
  published render is pixel-identical to the evaluated candidate, and
  `out/flare_parts.png` and its provenance describe this release's SVG.
- The three builder options leave every existing parameter file (2,168)
  building byte-identically.
- The CI workflow's steps were run in a fresh clone of this commit with a
  fresh virtual environment:
  - the gate before setup exits 3;
  - then setup, the gate (67 of 67), validation and the SVG rebuild all
    pass.
