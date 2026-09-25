# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 256 | reference downsampled to 256 | 1.646 | 2.949 | 63 | 4.811 | 0.9819 | 4.56 |
| resvg | 512 | reference downsampled to 512 | 1.720 | 3.366 | 88 | 5.061 | 0.9787 | 4.28 |
| resvg | 1024 | native | 1.804 | 3.812 | 110 | 5.331 | 0.9746 | 4.23 |
| resvg | 2048 | downsampled 2048->1024 | 1.799 | 3.794 | 101 | 5.323 | 0.9748 | 4.37 |
| resvg | 4096 | downsampled 4096->1024 | 1.804 | 3.781 | 96 | 5.329 | 0.9749 | 4.48 |
| chromium | 1024 | native | 3.092 | 4.703 | 136 | 9.651 | 0.9441 | 6.52 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.702 | 3.248 | 45 | 0.95534 |

