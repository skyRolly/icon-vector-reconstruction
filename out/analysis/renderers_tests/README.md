# Renderer probe SVGs

The 224 test SVGs the renderer survey rendered in both engines; the measured
numbers are in `../renderers.json` and `../renderers.md`. Their PNG renders
were removed from the repository (6 MB of throwaway rasters) — re-render any of
them with `python3 tools/render.py <file> out.png --renderer resvg|chromium`.
