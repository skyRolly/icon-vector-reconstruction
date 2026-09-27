# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 256 | reference downsampled to 256 | 1.504 | 2.432 | 34 | 4.681 | 0.9833 | 3.20 |
| resvg | 512 | reference downsampled to 512 | 1.540 | 2.520 | 49 | 4.912 | 0.9805 | 3.02 |
| resvg | 1024 | native | 1.610 | 2.766 | 77 | 5.172 | 0.9772 | 3.14 |
| resvg | 2048 | downsampled 2048->1024 | 1.601 | 2.733 | 68 | 5.160 | 0.9775 | 3.25 |
| resvg | 4096 | downsampled 4096->1024 | 1.604 | 2.733 | 67 | 5.162 | 0.9776 | 3.33 |
| chromium | 1024 | native | 2.939 | 3.920 | 85 | 9.529 | 0.9466 | 5.53 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.650 | 3.044 | 36 | 0.95580 |

