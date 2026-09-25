# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 256 | reference downsampled to 256 | 1.615 | 2.808 | 40 | 4.786 | 0.9820 | 4.31 |
| resvg | 512 | reference downsampled to 512 | 1.662 | 3.018 | 80 | 5.020 | 0.9791 | 4.02 |
| resvg | 1024 | native | 1.732 | 3.284 | 79 | 5.285 | 0.9756 | 3.99 |
| resvg | 2048 | downsampled 2048->1024 | 1.729 | 3.286 | 80 | 5.279 | 0.9758 | 4.14 |
| resvg | 4096 | downsampled 4096->1024 | 1.737 | 3.318 | 78 | 5.287 | 0.9758 | 4.25 |
| chromium | 1024 | native | 3.026 | 4.261 | 104 | 9.604 | 0.9452 | 6.31 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.693 | 3.227 | 45 | 0.95539 |

