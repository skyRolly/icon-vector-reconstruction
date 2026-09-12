# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 256 | reference downsampled to 256 | 2.104 | 3.693 | 64 | 5.884 | 0.9734 | 6.96 |
| resvg | 512 | reference downsampled to 512 | 2.195 | 4.089 | 85 | 6.142 | 0.9697 | 6.84 |
| resvg | 1024 | native | 2.262 | 4.454 | 112 | 6.361 | 0.9664 | 6.65 |
| resvg | 2048 | downsampled 2048->1024 | 2.254 | 4.417 | 106 | 6.352 | 0.9666 | 6.85 |
| resvg | 4096 | downsampled 4096->1024 | 2.251 | 4.377 | 100 | 6.352 | 0.9667 | 6.93 |
| chromium | 1024 | native | 2.888 | 4.800 | 126 | 8.668 | 0.9481 | 7.47 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.177 | 2.519 | 37 | 0.96535 |

