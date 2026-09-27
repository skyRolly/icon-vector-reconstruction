# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 256 | reference downsampled to 256 | 1.508 | 2.451 | 34 | 4.684 | 0.9833 | 3.27 |
| resvg | 512 | reference downsampled to 512 | 1.544 | 2.538 | 49 | 4.914 | 0.9805 | 3.09 |
| resvg | 1024 | native | 1.614 | 2.782 | 79 | 5.174 | 0.9772 | 3.20 |
| resvg | 2048 | downsampled 2048->1024 | 1.605 | 2.750 | 71 | 5.163 | 0.9775 | 3.31 |
| resvg | 4096 | downsampled 4096->1024 | 1.608 | 2.750 | 69 | 5.165 | 0.9776 | 3.39 |
| chromium | 1024 | native | 2.941 | 3.924 | 85 | 9.530 | 0.9466 | 5.57 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.650 | 3.044 | 36 | 0.95580 |

