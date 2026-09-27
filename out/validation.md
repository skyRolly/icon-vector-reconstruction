# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 256 | reference downsampled to 256 | 1.539 | 2.574 | 36 | 4.708 | 0.9832 | 3.65 |
| resvg | 512 | reference downsampled to 512 | 1.582 | 2.695 | 49 | 4.940 | 0.9802 | 3.48 |
| resvg | 1024 | native | 1.673 | 3.060 | 67 | 5.219 | 0.9765 | 3.58 |
| resvg | 2048 | downsampled 2048->1024 | 1.672 | 3.077 | 63 | 5.215 | 0.9767 | 3.71 |
| resvg | 4096 | downsampled 4096->1024 | 1.681 | 3.118 | 67 | 5.223 | 0.9766 | 3.81 |
| chromium | 1024 | native | 2.961 | 4.024 | 90 | 9.543 | 0.9461 | 5.59 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.693 | 3.220 | 44 | 0.95543 |

