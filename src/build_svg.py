#!/usr/bin/env python3
"""Build reconstruction.svg from src/params.json.

Nothing here is traced.  Every mark is a primitive driven by a named
parameter: a rounded-rectangle path for the frame, two elliptical-arc paths
for the luminous curves, and gradients/blurs for the optical effects.

COMPOSITING MODEL
-----------------
Every luminous mark is composited with `mix-blend-mode:screen` over an opaque
black base, so the whole image is

    out = 1 - prod_i (1 - A_i * k_i)

where `A_i` is layer i's rendered coverage (anti-aliasing x blur x gradient
alpha) and `k_i` is its colour premultiplied by its opacity.  Screen was chosen
over plain alpha because light in the reference adds and then rolls off into a
clipped white core, and over `plus-lighter` (true addition) because resvg does
not implement `plus-lighter` while both engines implement `screen` identically.

That closed form is what `tools/fit_photometry.py` exploits: render each layer
once in white, then every layer colour can be fitted analytically without
re-rendering.

Two measured renderer facts shaped the markup:
  * a group carrying `clip-path` becomes an isolated group, which silently
    kills `mix-blend-mode` for its children (verified identical in resvg and
    Chromium), so the clip is set on every element instead of on a wrapper;
  * `color-interpolation-filters` must be pinned to sRGB - the SVG default of
    linearRGB changes the glow falloff - and blur filter regions must be given
    in user space, because the default -10%/120% object-bbox region clips wide
    blurs of a thin path.

Usage:
    python3 src/build_svg.py                        # -> reconstruction.svg
    python3 src/build_svg.py --basis arc_core       # one layer, white, for fitting
    python3 src/build_svg.py --params p.json --out o.svg
"""
from __future__ import annotations

import argparse
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_PARAMS = os.path.join(HERE, "params.json")
DEFAULT_OUT = os.path.join(ROOT, "reconstruction.svg")


# --------------------------------------------------------------------------- #
# formatting / geometry helpers
# --------------------------------------------------------------------------- #
def f(v, nd=3):
    s = ("%%.%df" % nd) % float(v)
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s or "0"


def hexc(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(c)))) for c in rgb)


def split_color(k):
    """Split premultiplied colour k (0..255 per channel) into hex + opacity."""
    m = max(k)
    if m <= 0:
        return "#000000", 0.0
    o = min(1.0, m / 255.0)
    return hexc([c / o for c in k]), o


# --------------------------------------------------------------------------- #
# squircle (superellipse) corner geometry
#
# Measurement result, not a stylistic choice: rays cast through each frame
# corner put the stroke 2.3-2.5 px further out at 45 deg than a circular arc
# tangent to the straight edges allows, on all four corners.  A circle fitted
# to the corner points lands 1.7 px (top) and 3.3 px (side) away from the
# measured straight edges, i.e. it cannot join them; a superellipse
# |dx/r|^n + |dy/r|^n = 1 with n ~ 2.45, r ~ 203 is tangent by construction and
# fits the corner points to ~0.5 px.  Three cubic Beziers reproduce that
# quadrant to 0.08 px, far inside the measurement noise.
# --------------------------------------------------------------------------- #
_CORNER_CACHE = {}


def _se_pt(phi, n):
    c, s = math.cos(phi), math.sin(phi)
    return (abs(c) ** (2.0 / n), abs(s) ** (2.0 / n))


def _se_tan(phi, n, eps=1e-6):
    a = _se_pt(max(0.0, phi - eps), n)
    b = _se_pt(min(math.pi / 2, phi + eps), n)
    dx, dy = b[0] - a[0], b[1] - a[1]
    m = math.hypot(dx, dy)
    return (dx / m, dy / m)


def superellipse_quadrant(n, segments=3):
    """Cubic-Bezier control points for a unit-radius superellipse quadrant.

    Returns a list of `segments` tuples (P0, P1, P2, P3) going counter-clockwise
    from (1, 0) to (0, 1).  Handle lengths are least-squares fitted to the exact
    curve with the endpoint tangents pinned to the straight edges' directions,
    so the corner meets the straight edges with matching tangents.
    """
    key = (round(n, 6), segments)
    if key in _CORNER_CACHE:
        return _CORNER_CACHE[key]
    segs = []
    for i in range(segments):
        p0 = i * (math.pi / 2) / segments
        p1 = (i + 1) * (math.pi / 2) / segments
        A = _se_pt(p0, n)
        B = _se_pt(p1, n)
        T0 = (0.0, 1.0) if i == 0 else _se_tan(p0, n)
        T1 = (-1.0, 0.0) if i == segments - 1 else _se_tan(p1, n)
        # sample the exact quadrant and least-squares fit the two handle lengths
        m = 200
        phis = [p0 + (p1 - p0) * j / (m - 1.0) for j in range(m)]
        pts = [_se_pt(ph, n) for ph in phis]
        # chord-length initial parameters
        d = [0.0]
        for j in range(1, m):
            d.append(d[-1] + math.hypot(pts[j][0] - pts[j - 1][0], pts[j][1] - pts[j - 1][1]))
        t = [v / d[-1] for v in d]
        a = b = math.hypot(B[0] - A[0], B[1] - A[1]) * 0.4
        for _ in range(8):
            M00 = M01 = M11 = R0 = R1 = 0.0
            for j in range(m):
                tj = t[j]
                b0 = (1 - tj) ** 3
                b1 = 3 * (1 - tj) ** 2 * tj
                b2 = 3 * (1 - tj) * tj ** 2
                b3 = tj ** 3
                rx = pts[j][0] - (b0 + b1) * A[0] - (b2 + b3) * B[0]
                ry = pts[j][1] - (b0 + b1) * A[1] - (b2 + b3) * B[1]
                ax, ay = b1 * T0[0], b1 * T0[1]
                bx, by = -b2 * T1[0], -b2 * T1[1]
                M00 += ax * ax + ay * ay
                M01 += ax * bx + ay * by
                M11 += bx * bx + by * by
                R0 += ax * rx + ay * ry
                R1 += bx * rx + by * ry
            det = M00 * M11 - M01 * M01
            if abs(det) > 1e-14:
                a = max(1e-4, (R0 * M11 - R1 * M01) / det)
                b = max(1e-4, (R1 * M00 - R0 * M01) / det)
            P = ((A[0], A[1]), (A[0] + T0[0] * a, A[1] + T0[1] * a),
                 (B[0] - T1[0] * b, B[1] - T1[1] * b), (B[0], B[1]))
            for _ in range(3):  # Newton reparametrisation
                for j in range(m):
                    tj = t[j]
                    u = 1 - tj
                    qx = u ** 3 * P[0][0] + 3 * u * u * tj * P[1][0] + 3 * u * tj * tj * P[2][0] + tj ** 3 * P[3][0]
                    qy = u ** 3 * P[0][1] + 3 * u * u * tj * P[1][1] + 3 * u * tj * tj * P[2][1] + tj ** 3 * P[3][1]
                    dx = 3 * u * u * (P[1][0] - P[0][0]) + 6 * u * tj * (P[2][0] - P[1][0]) + 3 * tj * tj * (P[3][0] - P[2][0])
                    dy = 3 * u * u * (P[1][1] - P[0][1]) + 6 * u * tj * (P[2][1] - P[1][1]) + 3 * tj * tj * (P[3][1] - P[2][1])
                    den = dx * dx + dy * dy
                    if den > 1e-12:
                        t[j] = min(1.0, max(0.0, tj + ((pts[j][0] - qx) * dx + (pts[j][1] - qy) * dy) / den))
        segs.append(P)
    _CORNER_CACHE[key] = segs
    return segs


def three_arc_rect_path(x0, y0, x1, y1, r1, r2, alpha_deg):
    """Rounded rectangle with continuous-curvature ("corner-smoothed") corners.

    Each corner is three circular arcs -- a long, shallow blend arc, the main
    corner arc, then the mirror blend arc -- so the curvature steps from the
    straight edge to the corner in two stages instead of jumping.  This is the
    corner every design tool draws when "corner smoothing" is on, and it is
    what the reference has:

      * sliding 12-degree circle fits give a local radius of 250-400 px near
        the straight edges and 145-175 px through the 45-degree region, i.e. the
        curvature is not constant;
      * the stroke leaves the straight line gradually -- still 0.66 px inward
        at 195 px from the box corner, where any circular corner that fits the
        45-degree region would be exactly on the line;
      * a circle fitted to the corner points alone sits 1.9-2.7 px inside the
        measured straight edges in both axes, so it is not tangent to them.

    Residual to the measured corner outline: 0.13-0.27 px, against 0.66-0.84 px
    for a circular rounded rect and 0.44 px for a single cubic Bezier corner.
    """
    a = math.radians(alpha_deg)
    b = math.pi / 2 - 2 * a          # main arc turn
    th = [0.0, a, a + b, math.pi / 2]
    radii = [r2, r1, r2]
    run = sum(rr * (math.sin(th[i + 1]) - math.sin(th[i])) for i, rr in enumerate(radii))

    def corner(px, py, u, v):
        """Three A commands from the tangent point on edge u to the one on v."""
        out = []
        x, y = px - run * u[0], py - run * u[1]
        for i, rr in enumerate(radii):
            du = rr * (math.sin(th[i + 1]) - math.sin(th[i]))
            dv = rr * (math.cos(th[i]) - math.cos(th[i + 1]))
            x += du * u[0] + dv * v[0]
            y += du * u[1] + dv * v[1]
            out.append("A%s,%s 0 0 1 %s,%s" % (f(rr, 4), f(rr, 4), f(x, 4), f(y, 4)))
        return out

    d = ["M%s,%s" % (f(x0 + run, 4), f(y0, 4)), "L%s,%s" % (f(x1 - run, 4), f(y0, 4))]
    d += corner(x1, y0, (1, 0), (0, 1))
    d.append("L%s,%s" % (f(x1, 4), f(y1 - run, 4)))
    d += corner(x1, y1, (0, 1), (-1, 0))
    d.append("L%s,%s" % (f(x0 + run, 4), f(y1, 4)))
    d += corner(x0, y1, (-1, 0), (0, -1))
    d.append("L%s,%s" % (f(x0, 4), f(y0 + run, 4)))
    d += corner(x0, y0, (0, -1), (1, 0))
    d.append("Z")
    return " ".join(d)


def squircle_rect_path(x0, y0, x1, y1, r, n=2.45, segments=3):
    """Rounded rectangle whose corners are superellipse quadrants."""
    if abs(n - 2.0) < 1e-9:
        return rounded_rect_path(x0, y0, x1, y1, r)
    r = min(r, (x1 - x0) / 2.0, (y1 - y0) / 2.0)
    q = superellipse_quadrant(n, segments)
    out = ["M%s,%s" % (f(x0 + r, 3), f(y0, 3))]

    def corner(cx, cy, sx, sy, reverse):
        segs = list(reversed([tuple(reversed(P)) for P in q])) if reverse else q
        for P in segs:
            for k in (1, 2, 3):
                out.append("%s,%s" % (f(cx + sx * P[k][0] * r, 3), f(cy + sy * P[k][1] * r, 3)))
        out.insert(len(out) - 9, "C")

    out.append("L%s,%s" % (f(x1 - r, 3), f(y0, 3)))
    corner(x1 - r, y0 + r, 1, -1, True)
    out.append("L%s,%s" % (f(x1, 3), f(y1 - r, 3)))
    corner(x1 - r, y1 - r, 1, 1, False)
    out.append("L%s,%s" % (f(x0 + r, 3), f(y1, 3)))
    corner(x0 + r, y1 - r, -1, 1, True)
    out.append("L%s,%s" % (f(x0, 3), f(y0 + r, 3)))
    corner(x0 + r, y0 + r, -1, -1, False)
    out.append("Z")
    return " ".join(out)


def rounded_rect_path(x0, y0, x1, y1, r):
    r = min(r, (x1 - x0) / 2.0, (y1 - y0) / 2.0)
    return (
        f"M{f(x0+r)},{f(y0)} H{f(x1-r)} A{f(r)},{f(r)} 0 0 1 {f(x1)},{f(y0+r)} "
        f"V{f(y1-r)} A{f(r)},{f(r)} 0 0 1 {f(x1-r)},{f(y1)} H{f(x0+r)} "
        f"A{f(r)},{f(r)} 0 0 1 {f(x0)},{f(y1-r)} V{f(y0+r)} "
        f"A{f(r)},{f(r)} 0 0 1 {f(x0+r)},{f(y0)} Z"
    )


def bezier_arc_path(g, side, inset=0.0):
    """Arc path from explicit cubic control points (SVG user space).

    Measurement result: neither luminous curve is a conic.  An axis-aligned
    ellipse arc leaves a smooth 4-5 lobe +-0.4 px residual (RMS 0.33 left /
    0.47 right); adding rotation, a general conic, a superellipse exponent or
    a split vertical radius each removes a *different* part of it, which is the
    signature of a parameter absorbing model error rather than measuring a real
    degree of freedom.  Two cubic Beziers joined at the apex with a vertical
    tangent reach RMS 0.085/0.095 px -- the measurement noise floor -- and an
    end-to-end check (render the path, re-extract the ridge, compare with the
    reference ridge) confirms 0.11/0.13 px.  So each curve is three anchors
    (top tip, apex, bottom tip) with a vertical handle at the apex.

    `inset` moves every control point that many pixels towards the curve's own
    ellipse centre; the wide glow layers use it to bias their light inwards.
    """
    cps = g["cubics"][side]
    cx, cy = g["insetcentre"][side]

    def T(q):
        if not inset:
            return q
        dx, dy = q[0] - cx, q[1] - cy
        d = math.hypot(dx, dy) or 1.0
        k = max(0.0, 1.0 - inset / d)
        return (cx + dx * k, cy + dy * k)

    out = []
    for i, seg in enumerate(cps):
        pts = [T(q) for q in seg]
        if i == 0:
            out.append("M%s,%s" % (f(pts[0][0], 2), f(pts[0][1], 2)))
        out.append("C%s,%s %s,%s %s,%s" % (f(pts[1][0], 2), f(pts[1][1], 2),
                                           f(pts[2][0], 2), f(pts[2][1], 2),
                                           f(pts[3][0], 2), f(pts[3][1], 2)))
    return " ".join(out)


def arc_path(g, side, inset=0.0):
    """Elliptical-arc path for one luminous curve.

    `inset` shrinks both radii, which offsets the arc towards the inside of
    its own ellipse -- that is how the glow's inward bias is produced without
    duplicating geometry.
    """
    cx, cy = g["cx"], g["cy"]
    rx, ry = g["rx"] - inset, g["ry"] - inset
    rot = g.get("rot", 0.0)
    y0, y1 = g["y_top"], g["y_bottom"]
    s = 1.0 if side == "left" else -1.0

    def x_at(y):
        t = max(0.0, 1.0 - ((y - cy) / ry) ** 2)
        return cx + s * rx * math.sqrt(t)

    sweep = 1 if side == "left" else 0
    return "M%s,%s A%s,%s %s 0 %d %s,%s" % (
        f(x_at(y0), 2), f(y0, 2), f(rx, 3), f(ry, 3), f(rot, 4), sweep,
        f(x_at(y1), 2), f(y1, 2),
    )


def taper_stops(t, side="left", n=24):
    """Alpha-vs-y stops for a layer's fade along the arcs.

    Two forms:

    `kind: "table"` -- explicit measured (y, alpha) points, per side.  The core
    and the three glow terms were each measured station by station along both
    arcs (45 stations each), so these fades are data, not a guessed curve.
    `gamma` and `scale` stay tunable so the search can adjust them without
    discarding the measurement.

    `kind: "ramp"` (the default) -- alpha rises from 0 at `y0` to 1 at `y1` as a
    power `p0`, holds, then falls to 0 between `y2` and `y3` as `p1`.
    """
    if t.get("kind") == "table":
        pts = t[side]
        gamma = float(t.get("gamma", 1.0))
        scale = float(t.get("scale", 1.0))
        off = float(t.get("y_offset", 0.5))
        out = [(0.0, 0.0)]
        for y, a in pts:
            out.append(((y + off) / 1024.0, min(1.0, scale * max(0.0, a) ** gamma)))
        out.append((1.0, 0.0))
        return out

    y0, y1, y2, y3 = t["y0"], t["y1"], t["y2"], t["y3"]
    p0, p1 = t.get("p0", 0.5), t.get("p1", 0.7)
    lo, hi = t.get("floor", 0.0), t.get("peak", 1.0)
    ys = sorted({y0, y1, y2, y3} |
                {y0 + (y1 - y0) * i / 8.0 for i in range(9)} |
                {y2 + (y3 - y2) * i / 8.0 for i in range(9)} |
                {y1 + (y2 - y1) * i / (n / 4.0) for i in range(int(n / 4) + 1)})
    out = []
    for y in ys:
        if y <= y0 or y >= y3:
            a = 0.0
        elif y < y1:
            a = ((y - y0) / (y1 - y0)) ** p0
        elif y <= y2:
            a = 1.0
        else:
            a = ((y3 - y) / (y3 - y2)) ** p1
        out.append((y / 1024.0, lo + (hi - lo) * a))
    if out[0][0] > 0:
        out.insert(0, (0.0, out[0][1]))
    if out[-1][0] < 1:
        out.append((1.0, out[-1][1]))
    return out


def profile_stops(profile, n=18):
    """Radial falloff -> gradient stops.

    Accepts either an explicit [[offset, alpha], ...] table or a named law:
      {"kind": "gauss", "sigma": s}   exp(-u^2 / 2 s^2)
      {"kind": "exp",   "scale": s}   exp(-u / s)
      {"kind": "pow",   "n": k}       (1 - u)^k
    Named laws are renormalised so alpha(1) == 0; otherwise `spreadMethod=pad`
    would flood the rest of the shape with the last stop's colour.
    """
    if isinstance(profile, dict):
        kind = profile.get("kind", "gauss")
        if kind == "gauss":
            s = float(profile.get("sigma", 0.4))
            g = lambda u: math.exp(-(u * u) / (2 * s * s))
        elif kind == "exp":
            s = float(profile.get("scale", 0.3))
            g = lambda u: math.exp(-u / s)
        elif kind == "pow":
            k = float(profile.get("n", 2.0))
            g = lambda u: max(0.0, 1.0 - u) ** k
        else:
            raise ValueError("unknown profile kind %r" % kind)
        g1 = g(1.0)
        us = [i / float(n) for i in range(n + 1)]
        return [(u, max(0.0, (g(u) - g1) / (1.0 - g1))) for u in us]
    return [(o, a) for o, a in profile]


# --------------------------------------------------------------------------- #
# layer emission
# --------------------------------------------------------------------------- #
class Builder:
    def __init__(self, p):
        self.p = p
        self.defs = []
        self._filters = {}
        self._ids = set()
        fr = p["frame"]
        if fr.get("corner_model", "three_arc") == "three_arc":
            self.frame_d = three_arc_rect_path(
                fr["left"], fr["top"], fr["right"], fr["bottom"],
                fr["corner_r_main"], fr["corner_r_blend"], fr["corner_blend_deg"])
        else:
            self.frame_d = squircle_rect_path(fr["left"], fr["top"], fr["right"], fr["bottom"],
                                              fr["radius"], fr.get("corner_n", 2.45),
                                              int(fr.get("corner_segments", 3)))
        self.defs.append('<clipPath id="fc"><path d="%s"/></clipPath>' % self.frame_d)
        # everything outside the frame: canvas rect minus the frame shape, via
        # the even-odd rule (identical in both engines used here)
        self.defs.append(
            '<clipPath id="fo" clip-rule="evenodd">'
            '<path clip-rule="evenodd" d="M0,0 H1024 V1024 H0 Z %s"/></clipPath>' % self.frame_d)
        self.defs.append('<path id="frame" d="%s"/>' % self.frame_d)
        for side in ("left", "right"):
            g = p["geometry"]["arc_" + side]
            self.defs.append('<path id="a%s" d="%s"/>' % (side[0], self.arc_d(side)))
            # The broad glow lives only on the concave side of each arc, so it
            # is clipped to that arc's own ellipse intersected with the frame
            # (a clipPath carrying its own clip-path intersects -- verified
            # identical in resvg and Chromium).
            if not any(L.get("clip") == "lens" for L in p["layers"]):
                continue
            grow = p["geometry"].get("lens_grow", 1.5)
            le = p["geometry"]["lens_ellipse"][side]
            self.defs.append(
                '<clipPath id="lens%s" clip-path="url(#fc)">'
                '<ellipse cx="%s" cy="%s" rx="%s" ry="%s"/></clipPath>'
                % (side[0].upper(), f(le["cx"]), f(le["cy"]),
                   f(le["rx"] + grow), f(le["ry"] + grow)))

    def arc_d(self, side, inset=0.0):
        g = self.p["geometry"]["arc_" + side]
        return bezier_arc_path(g, side, inset) if "cubics" in g else arc_path(g, side, inset)

    # -- defs helpers ------------------------------------------------------ #
    def blur(self, sigma, region=None):
        """A Gaussian blur filter, with an explicit user-space region.

        Two things are deliberate.  `color-interpolation-filters="sRGB"`:
        the SVG default is linearRGB, which changes the glow falloff and is not
        handled identically by every engine.  And the region is given in user
        space rather than left at the default -10%/120% of the object bounding
        box, which clips wide blurs of a thin path badly.

        The region is clamped to the frame's bounding box plus a small margin.
        Filtering happens before clipping in the SVG rendering model, so output
        outside the frame clip would be thrown away anyway; clamping turns a
        2400x2400 px filter area for the widest blur into 900x970 and makes the
        whole render several times faster without changing a pixel.
        """
        if isinstance(sigma, (list, tuple)):
            sd, key = "%s %s" % (f(sigma[0]), f(sigma[1])), "b%s_%s" % (f(sigma[0]), f(sigma[1]))
        else:
            sd, key = f(sigma), "b%s" % f(sigma)
        key = key.replace(".", "p").replace("-", "n")
        if region is not None:
            key += "_r%s" % "_".join(f(v, 1).replace(".", "p").replace("-", "n") for v in region)
        if key not in self._filters:
            pad = 4.0 * (max(sigma) if isinstance(sigma, (list, tuple)) else sigma) + 20
            if region is not None:
                # A rotated element's filter region is interpreted in that
                # element's own (rotated) user space, so the canvas-clamped
                # region below would clip it -- or, for some angles, miss it
                # entirely.  Rotated layers pass their own local region.
                x0, y0 = region[0] - pad, region[1] - pad
                x1, y1 = region[0] + region[2] + pad, region[1] + region[3] + pad
            else:
                fr = self.p["frame"]
                x0 = max(-pad, fr["left"] - 4.0)
                y0 = max(-pad, fr["top"] - 4.0)
                x1 = min(1024 + pad, fr["right"] + 4.0)
                y1 = min(1024 + pad, fr["bottom"] + 4.0)
            self._filters[key] = (
                '<filter id="%s" filterUnits="userSpaceOnUse" x="%s" y="%s" width="%s" height="%s" '
                'color-interpolation-filters="sRGB"><feGaussianBlur stdDeviation="%s"/></filter>'
                % (key, f(x0), f(y0), f(x1 - x0), f(y1 - y0), sd)
            )
        return key

    def add_def(self, d, gid):
        if gid not in self._ids:
            self._ids.add(gid)
            self.defs.append(d)
        return gid

    def taper_paint(self, gid, name, color, side="left"):
        stops = taper_stops(self.p["tapers"][name], side)
        body = "".join(
            '<stop offset="%s" stop-color="%s" stop-opacity="%s"/>' % (f(o, 5), color, f(a, 4))
            for o, a in stops
        )
        return self.add_def(
            '<linearGradient id="%s" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2="1024">%s</linearGradient>'
            % (gid, body), gid)

    def radial_paint(self, gid, color, cx, cy, r, profile, squash=1.0, rot=0.0):
        body = "".join(
            '<stop offset="%s" stop-color="%s" stop-opacity="%s"/>' % (f(o, 5), color, f(a, 5))
            for o, a in profile_stops(profile)
        )
        tr = ""
        if squash != 1.0 or rot:
            parts = []
            if rot:
                parts.append("rotate(%s %s %s)" % (f(rot), f(cx), f(cy)))
            if squash != 1.0:
                parts.append("translate(%s %s) scale(1 %s) translate(%s %s)"
                             % (f(cx), f(cy), f(squash, 5), f(-cx), f(-cy)))
            tr = ' gradientTransform="%s"' % " ".join(parts)
        return self.add_def(
            '<radialGradient id="%s" gradientUnits="userSpaceOnUse" cx="%s" cy="%s" r="%s"%s>%s</radialGradient>'
            % (gid, f(cx), f(cy), f(r), tr, body), gid)

    # -- one layer --------------------------------------------------------- #
    def layer(self, L, white=False):
        """Return the SVG element for layer L (white/full opacity when fitting).

        Screen-blended layers are emitted as a bright colour times a small
        `opacity`, which keeps their premultiplied colour accurate to far better
        than 8 bits: screen composites as `out + alpha*opacity*C*(1-out)`, so
        only the product matters.

        Normal-blended layers must NOT do that. Their composite is
        `out*(1 - alpha*opacity) + alpha*opacity*C`, i.e. the opacity also
        weakens the backdrop, so splitting the colour into a bright hex plus a
        low opacity lets the backdrop bleed through -- which made the frame rim
        render at B 148 where the measurement says 128. They are emitted at
        opacity 1 with the colour itself, at the cost of 8-bit rounding
        (under half a code value on a 6 px ring).
        """
        if white:
            col, op = "#ffffff", 1.0
        elif L.get("blend", "screen") == "normal":
            col, op = hexc(L.get("color", [255, 255, 255])), 1.0
        else:
            col, op = split_color(L.get("color", [255, 255, 255]))
        kind = L["kind"]
        clip = '' if L.get("clip", True) in (False, None, "none") else ' clip-path="url(#fc)"'
        blend = ' style="mix-blend-mode:screen"' if L.get("blend", "screen") == "screen" else ""
        filt = ' filter="url(#%s)"' % self.blur(L["blur"]) if L.get("blur") else ""
        opa = "" if op >= 1.0 else ' opacity="%s"' % f(op, 4)
        gid = "g_" + L["id"]

        if kind == "canvas":
            # `region: "outside"` confines the layer to the area outside the
            # frame.  The exterior is not one flat colour: measured along the
            # left strip its blue channel runs 7.7 (top) -> 5.6 (middle) ->
            # 8.4 (bottom), and directly under the frame's bottom edge it falls
            # to 1.1 while the bottom canvas corners stay at 8.  Clipping these
            # layers to the exterior keeps that structure from leaking into the
            # interior field, which is modelled separately.
            reg = {"outside": ' clip-path="url(#fo)"',
                   "inside": ' clip-path="url(#fc)"'}.get(L.get("region"), "")
            paint = col
            pt = L.get("paint")
            if isinstance(pt, dict) and pt.get("kind") == "linear":
                body = "".join('<stop offset="%s" stop-color="%s" stop-opacity="%s"/>'
                               % (f(o, 4), col, f(av, 4)) for o, av in pt["stops"])
                self.add_def('<linearGradient id="%s" gradientUnits="userSpaceOnUse" x1="%s" y1="%s" '
                             'x2="%s" y2="%s">%s</linearGradient>'
                             % (gid, f(pt.get("x1", 0)), f(pt.get("y1", 0)),
                                f(pt.get("x2", 0)), f(pt.get("y2", 1024)), body), gid)
                paint = "url(#%s)" % gid
            elif isinstance(pt, dict) and pt.get("kind") == "radial":
                self.radial_paint(gid, col, pt["cx"], pt["cy"], pt["r"], pt["profile"],
                                  pt.get("squash", 1.0))
                paint = "url(#%s)" % gid
            return ('<rect width="1024" height="1024" fill="%s"%s%s%s/>'
                    % (paint, reg, opa, blend))

        if kind == "field":
            return '<use href="#frame" fill="%s"%s%s/>' % (col, opa, blend)

        if kind == "field_radial":
            self.radial_paint(gid, col, L["cx"], L["cy"], L["r"], L["profile"],
                              L.get("squash", 1.0), L.get("rot", 0.0))
            return '<use href="#frame" fill="url(#%s)"%s%s%s/>' % (gid, filt, opa, blend)

        if kind == "arc":
            out = []
            for side in ("left", "right"):
                if L.get("side") and L["side"] != side:
                    continue
                d = self.arc_d(side, L.get("inset", 0.0))
                paint = ("url(#%s)" % self.taper_paint(gid + side[0], L["taper"], col, side)
                         if L.get("taper") else col)
                cl = L.get("clip", "frame")
                if cl == "lens":
                    cattr = ' clip-path="url(#lens%s)"' % side[0].upper()
                elif cl in (False, None, "none"):
                    cattr = ""
                else:
                    cattr = ' clip-path="url(#fc)"'
                out.append(
                    '<path d="%s" fill="none" stroke="%s" stroke-width="%s" stroke-linecap="%s"%s%s%s%s/>'
                    % (d, paint, f(L["width"]), L.get("linecap", "round"), filt, cattr, opa, blend)
                )
            return "".join(out)

        if kind == "arc_lens":
            # The broad glow is confined to the inside of each arc's own
            # ellipse and decays with distance from the central light, so it is
            # painted as that ellipse filled with a light-centred gradient.
            # This is what makes the glow strongly brighter on the concave side
            # -- a symmetric blurred stroke cannot do it.
            fl = self.p["flare"]
            out = []
            for side in ("left", "right"):
                if L.get("side") and L["side"] != side:
                    continue
                g = self.p["geometry"]["arc_" + side]
                ins = L.get("inset", 0.0)
                gid2 = gid + side[0]
                self.radial_paint(gid2, col, L.get("cx", fl["cx"]), L.get("cy", fl["cy"]),
                                  L["r"], L["profile"], L.get("squash", 1.0))
                out.append(
                    '<ellipse cx="%s" cy="%s" rx="%s" ry="%s" fill="url(#%s)"%s%s%s%s/>'
                    % (f(g["cx"]), f(g["cy"]), f(g["rx"] - ins), f(g["ry"] - ins),
                       gid2, filt, clip, opa, blend)
                )
            return "".join(out)

        if kind == "radial":
            fl = self.p["flare"]
            cx = L.get("cx", fl["cx"]); cy = L.get("cy", fl["cy"])
            self.radial_paint(gid, col, cx, cy, L["r"], L["profile"],
                              L.get("squash", 1.0), L.get("rot", 0.0))
            rx = L["r"]; ry = L["r"] * L.get("squash", 1.0)
            tr = ' transform="rotate(%s %s %s)"' % (f(L["rot"]), f(cx), f(cy)) if L.get("rot") else ""
            return ('<ellipse cx="%s" cy="%s" rx="%s" ry="%s" fill="url(#%s)"%s%s%s%s%s/>'
                    % (f(cx), f(cy), f(rx), f(ry), gid, tr, filt, clip, opa, blend))

        if kind == "streak":
            # The central light's horizontal streak.  Measured: horizontal to
            # 0.1 degrees, an exponential falloff with e-folding length ~30 px
            # over +-250 px, and a vertical Gaussian of sigma 2.2 px (FWHM 5.2).
            # A radial gradient cannot do that (its transverse profile would be
            # the same law as the longitudinal one), so it is a rect with a
            # gradient along x and an anisotropic blur across y.
            fl = self.p["flare"]
            cx = L.get("cx", fl["cx"])
            cy = L.get("cy", fl["cy"])
            half, h = L["half_len"], L["height"]
            prof = profile_stops(L["profile"])
            body = []
            for o, a in reversed(prof):
                body.append('<stop offset="%s" stop-color="%s" stop-opacity="%s"/>'
                            % (f(0.5 - 0.5 * o, 5), col, f(a, 5)))
            for o, a in prof[1:]:
                body.append('<stop offset="%s" stop-color="%s" stop-opacity="%s"/>'
                            % (f(0.5 + 0.5 * o, 5), col, f(a, 5)))
            self.add_def('<linearGradient id="%s" gradientUnits="userSpaceOnUse" x1="%s" y1="0" '
                         'x2="%s" y2="0">%s</linearGradient>'
                         % (gid, f(cx - half), f(cx + half), "".join(body)), gid)
            return ('<rect x="%s" y="%s" width="%s" height="%s" fill="url(#%s)"%s%s%s%s/>'
                    % (f(cx - half), f(cy - h / 2.0), f(2 * half), f(h), gid, filt, clip, opa, blend))

        if kind == "ray":
            # One-sided diagonal spike.  The three measured rays are one-sided
            # (peak 2.9-4.7 code values above the local background) and are not
            # arranged with 4- or 6-fold symmetry, so each is placed from its
            # measured outward angle and streak-crossing point; a symmetric
            # primitive would invent three rays that are not there.
            #
            # Built as an explicit quadrilateral in canvas coordinates rather
            # than a rotated rect: `transform` on an element reinterprets that
            # element's clip-path AND its filter region in the rotated space,
            # which silently dropped two of the three rays entirely.
            fl = self.p["flare"]
            cx = L.get("cx", fl["cx"])
            cy = L.get("cy", fl["cy"])
            ln, h, pk = L["len"], L["height"], L.get("peak_at", 0.3)
            th = math.radians(L["rot"])
            ux, uy = math.cos(th), math.sin(th)
            nx, ny = -uy * h / 2.0, ux * h / 2.0
            pts = [(cx + nx, cy + ny), (cx + ln * ux + nx, cy + ln * uy + ny),
                   (cx + ln * ux - nx, cy + ln * uy - ny), (cx - nx, cy - ny)]
            d = "M%s,%s L%s,%s L%s,%s L%s,%s Z" % tuple(
                f(v, 2) for q in pts for v in q)
            body = "".join('<stop offset="%s" stop-color="%s" stop-opacity="%s"/>' % (f(o, 4), col, f(av, 4))
                           for o, av in ((0.0, 0.0), (pk * 0.5, 0.62), (pk, 1.0),
                                         (min(0.999, pk + 0.35), 0.42), (1.0, 0.0)))
            self.add_def('<linearGradient id="%s" gradientUnits="userSpaceOnUse" x1="%s" y1="%s" '
                         'x2="%s" y2="%s">%s</linearGradient>'
                         % (gid, f(cx, 2), f(cy, 2), f(cx + ln * ux, 2), f(cy + ln * uy, 2),
                            body), gid)
            return ('<path d="%s" fill="url(#%s)"%s%s%s%s/>' % (d, gid, filt, clip, opa, blend))

        if kind == "frame_ring":
            # The frame's brightness is not one gradient: it peaks at the middle
            # of each edge, falls into the corners, and the top edge is roughly
            # twice as bright as the bottom.  That needs more than one paint, so
            # the ring is built from a few stroked copies whose paints are
            # named, measurable things (uniform rim, top-lit gradient,
            # edge-midpoint highlight) and whose amplitudes are fitted.
            pt = L["paint"]
            if pt["kind"] == "uniform":
                paint = col
            elif pt["kind"] == "linear":
                body = "".join(
                    '<stop offset="%s" stop-color="%s" stop-opacity="%s"/>' % (f(o, 4), col, f(av, 4))
                    for o, av in pt["stops"])
                self.add_def(
                    '<linearGradient id="%s" gradientUnits="userSpaceOnUse" x1="%s" y1="%s" x2="%s" y2="%s">%s</linearGradient>'
                    % (gid, f(pt["x1"]), f(pt["y1"]), f(pt["x2"]), f(pt["y2"]), body), gid)
                paint = "url(#%s)" % gid
            elif pt["kind"] == "radial":
                self.radial_paint(gid, col, pt["cx"], pt["cy"], pt["r"], pt["profile"],
                                  pt.get("squash", 1.0))
                paint = "url(#%s)" % gid
            else:
                raise ValueError(pt["kind"])
            return ('<use href="#frame" fill="none" stroke="%s" stroke-width="%s"%s%s%s/>'
                    % (paint, f(L.get("width", self.p["frame"]["stroke_width"])), filt, opa, blend))

        if kind == "frame_stroke":
            stops = L["stops"]
            body = "".join('<stop offset="%s" stop-color="%s" stop-opacity="%s"/>' % (f(o, 4), c, f(a, 4))
                           for o, c, a in stops)
            if white:
                body = "".join('<stop offset="%s" stop-color="#ffffff" stop-opacity="%s"/>' % (f(o, 4), f(a, 4))
                               for o, c, a in stops)
            fr = self.p["frame"]
            self.add_def(
                '<linearGradient id="%s" gradientUnits="userSpaceOnUse" x1="0" y1="%s" x2="0" y2="%s">%s</linearGradient>'
                % (gid, f(fr["top"]), f(fr["bottom"]), body), gid)
            return ('<use href="#frame" fill="none" stroke="url(#%s)" stroke-width="%s"%s%s%s/>'
                    % (gid, f(L.get("width", fr["stroke_width"])), filt, opa, blend))

        if kind == "frame_corner_glow":
            # Brightness along the frame varies; a radial gradient stroke adds
            # the extra light near the middle of each edge.
            self.radial_paint(gid, col, L["cx"], L["cy"], L["r"], L["profile"], L.get("squash", 1.0))
            return ('<use href="#frame" fill="none" stroke="url(#%s)" stroke-width="%s"%s%s%s/>'
                    % (gid, f(L["width"]), filt, opa, blend))

        raise ValueError("unknown layer kind %r" % kind)

    # -- whole document ---------------------------------------------------- #
    def document(self, basis=None):
        """The whole SVG.  With `basis` set, only that layer, painted white --
        that is the coverage field the photometric fit needs."""
        body = ['<rect width="1024" height="1024" fill="#000000"/>']
        for L in self.p["layers"]:
            if basis is not None and L["id"] != basis:
                continue
            el = self.layer(L, white=(basis is not None))
            if basis is None:
                body.append("<!-- %s -->" % L["id"])
            body.append(el)
        head = [
            '<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024">',
            "<!-- Reconstruction of reference.png.  Generated by src/build_svg.py from",
            "     src/params.json; see docs/METHOD.md and docs/DECISIONS.md.",
            "     Every luminous mark is screen-blended over the black base, so the",
            "     composite is out = 1 - prod(1 - coverage_i * colour_i).",
            "     Clips are per-element on purpose: a group carrying clip-path becomes",
            "     an isolated group, which silently disables mix-blend-mode. -->",
        ]
        return "%s\n<defs>\n%s\n</defs>\n%s\n</svg>\n" % (
            "\n".join(head),
            "\n".join(list(self._filters.values()) + self.defs),
            "\n".join(body),
        )


def build(params, basis=None):
    b = Builder(params)
    return b.document(basis)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", default=DEFAULT_PARAMS)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--basis", default=None, help="emit only this layer, in white (for fitting)")
    a = ap.parse_args()
    svg = build(json.load(open(a.params)), a.basis)
    open(a.out, "w", encoding="utf-8").write(svg)
    print("wrote %s (%d bytes)" % (a.out, len(svg)))


if __name__ == "__main__":
    main()
