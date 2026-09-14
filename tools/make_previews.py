#!/usr/bin/env python3
"""Write the small side-by-side previews the README embeds."""
import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIZE = 340


def main():
    ref = Image.open(os.path.join(ROOT, "reference.png")).convert("RGB")
    rec = Image.open(sys.argv[1] if len(sys.argv) > 1
                     else os.path.join(ROOT, "out", "render_1024.png")).convert("RGB")
    d = np.abs(np.asarray(rec).astype(float) - np.asarray(ref).astype(float))
    diff = Image.fromarray(np.clip(d * 4, 0, 255).astype(np.uint8))
    out = os.path.join(ROOT, "out")
    for name, img in (("side_reference", ref), ("side_reconstruction", rec), ("side_diff", diff)):
        img.resize((SIZE, SIZE), Image.LANCZOS).save(os.path.join(out, name + ".png"))
    print("wrote previews to", out)


if __name__ == "__main__":
    main()
