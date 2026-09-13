#!/usr/bin/env python3
"""Write the current metrics into README.md.

Keeps the headline numbers in the README honest: it regenerates the table
between the two marker comments from out/metrics.json and out/validation.json,
so the README cannot drift from the last measured run.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
START = "<!-- METRICS:START -->"
END = "<!-- METRICS:END -->"


def main():
    m = json.load(open(os.path.join(ROOT, "out", "metrics.json")))
    v = None
    vp = os.path.join(ROOT, "out", "validation.json")
    if os.path.exists(vp):
        v = json.load(open(vp))
    d = None
    dp = os.path.join(ROOT, "out", "diagnostics.json")
    if os.path.exists(dp):
        d = json.load(open(dp))
    lines = [
        START,
        "## Fidelity",
        "",
        "Reconstruction rendered at 1024 px (resvg) against `reference.png`:",
        "",
        "| metric | value | for scale |",
        "|---|---|---|",
        "| mean absolute error | **%.3f** / 255 | a flat black canvas scores 17.89 |" % m["mae"],
        "| RMSE | %.3f | |" % m["rmse"],
        "| MAE on a 1/2.2 display curve | %.3f | weights the dark background as the eye does; black scores 59.7 |" % m["mae_gamma"],
        "| SSIM (luminance) | **%.4f** | black scores 0.142 |" % m["ssim"],
        "| worst single-channel error | %.0f | |" % m["max_ch"],
        "| pixels off by more than 2 / 8 / 24 | %.1f%% / %.1f%% / %.1f%% | |" % (m["pct_gt2"], m["pct_gt8"], m["pct_gt24"]),
        "| mean bias | %+.3f | |" % m["mean_bias"],
        "",
        "Per region (MAE): frame band %.2f, centre 90 px %.2f, bright pixels %.2f, "
        "dark background %.2f, everything else %.2f."
        % (m["mae_frame"], m["mae_centre"], m["mae_bright"], m["mae_dark"], m["mae_rest"]),
        "",
        "About a quarter of that error is the reference's own JPEG noise: decomposed by",
        "scale, the background residual implies an MAE floor of 0.57-0.61 per channel",
        "that no reconstruction of the underlying design can go below.",
    ]
    if d:
        # The two regions a whole-image metric cannot police get their own
        # numbers here, so the README cannot claim fidelity the targeted
        # diagnostics do not support.
        rad = d.get("flare_radial") or []
        worst = max((abs(r["rec"] - r["ref"]), r) for r in rad)[1] if rad else None
        prof = d.get("profile") or []
        pw = max((abs(b["rec"] - b["ref"]) / max(b["ref"], 1e-6), b) for b in prof)[1] if prof else None
        lines += [
            "",
            "The two regions a whole-image average cannot police, from",
            "`tools/diagnose.py` (full report in `out/diagnostics.json`):",
            "",
            "| targeted measurement | value |",
            "|---|---|",
        ]
        if "flare_mae" in d:
            lines.append("| MAE within 110 px of the central light | %.2f |" % d["flare_mae"])
        if worst:
            lines.append("| worst ring of the flare's radial profile | %+.1f code values at r = %d-%d |"
                         % (worst["rec"] - worst["ref"], worst["r"][0], worst["r"][1]))
        if "profile_rms_rel" in d:
            lines.append("| curve glow, rms relative error over %d signed-distance bins | %.1f%% |"
                         % (len(prof), 100 * d["profile_rms_rel"]))
        if "profile_cells_rms_rel" in d:
            lines.append("| the same, resolved along the curve (%d cells) | %.1f%% |"
                         % (len(d.get("profile_cells") or []),
                            100 * d["profile_cells_rms_rel"]))
        if "corner_rms_rel" in d:
            lines.append("| light in the four interior corners, rms relative error | %.1f%% |"
                         % (100 * d["corner_rms_rel"]))
        if pw:
            lines.append("| worst single bin of that profile | %+.1f%% at s = %d..%d px |"
                         % (100 * (pw["rec"] - pw["ref"]) / max(pw["ref"], 1e-6),
                            pw["s"][0], pw["s"][1]))
        for side in ("left", "right"):
            k = "lobe_mae_" + side
            if k in d:
                lines.append("| %s lobe, MAE more than 25 px from the ridge | %.2f (bias %+.2f) |"
                             % (side, d[k], d.get("lobe_bias_" + side, 0.0)))
    if v and v.get("cross_engine"):
        ce = v["cross_engine"]
        lines += [
            "",
            "Cross-engine: the same SVG in resvg and headless Chromium agrees to MAE %.3f "
            "(SSIM %.4f); see `out/validation.md` for the resolution sweep." % (ce["mae"], ce["ssim"]),
        ]
    lines.append(END)
    path = os.path.join(ROOT, "README.md")
    s = open(path).read()
    block = "\n".join(lines)
    if START in s and END in s:
        s = s[: s.index(START)] + block + s[s.index(END) + len(END):]
    else:
        s = s.replace("METRICS_TABLE_PLACEHOLDER", block)
    open(path, "w").write(s)
    print("README.md updated")


if __name__ == "__main__":
    main()
