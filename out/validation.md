# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 256 | reference downsampled to 256 | 1.504 | 2.436 | 37 | 4.681 | 0.9833 | 3.10 |
| resvg | 512 | reference downsampled to 512 | 1.526 | 2.465 | 40 | 4.904 | 0.9806 | 2.86 |
| resvg | 1024 | native | 1.594 | 2.696 | 77 | 5.164 | 0.9774 | 3.01 |
| resvg | 2048 | downsampled 2048->1024 | 1.585 | 2.661 | 68 | 5.152 | 0.9777 | 3.12 |
| resvg | 4096 | downsampled 4096->1024 | 1.587 | 2.660 | 67 | 5.154 | 0.9777 | 3.20 |
| chromium | 1024 | native | 2.918 | 3.840 | 77 | 9.517 | 0.9468 | 5.40 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.650 | 3.041 | 36 | 0.95580 |

