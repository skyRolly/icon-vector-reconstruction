# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 256 | reference downsampled to 256 | 1.646 | 2.952 | 63 | 4.811 | 0.9818 | 4.56 |
| resvg | 512 | reference downsampled to 512 | 1.720 | 3.369 | 88 | 5.060 | 0.9787 | 4.27 |
| resvg | 1024 | native | 1.804 | 3.815 | 110 | 5.330 | 0.9746 | 4.22 |
| resvg | 2048 | downsampled 2048->1024 | 1.799 | 3.797 | 101 | 5.323 | 0.9748 | 4.36 |
| resvg | 4096 | downsampled 4096->1024 | 1.804 | 3.783 | 96 | 5.328 | 0.9748 | 4.47 |
| chromium | 1024 | native | 3.092 | 4.704 | 136 | 9.650 | 0.9441 | 6.50 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.702 | 3.248 | 45 | 0.95533 |

