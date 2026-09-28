# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 256 | reference downsampled to 256 | 1.496 | 2.401 | 37 | 4.677 | 0.9833 | 3.09 |
| resvg | 512 | reference downsampled to 512 | 1.529 | 2.472 | 40 | 4.906 | 0.9806 | 2.88 |
| resvg | 1024 | native | 1.599 | 2.714 | 77 | 5.166 | 0.9773 | 3.04 |
| resvg | 2048 | downsampled 2048->1024 | 1.591 | 2.682 | 68 | 5.155 | 0.9776 | 3.16 |
| resvg | 4096 | downsampled 4096->1024 | 1.593 | 2.685 | 67 | 5.157 | 0.9776 | 3.23 |
| chromium | 1024 | native | 2.922 | 3.848 | 77 | 9.519 | 0.9467 | 5.41 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.650 | 3.041 | 36 | 0.95580 |

