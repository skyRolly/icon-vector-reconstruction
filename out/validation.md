# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 256 | reference downsampled to 256 | 1.796 | 3.350 | 69 | 5.250 | 0.9805 | 5.94 |
| resvg | 512 | reference downsampled to 512 | 1.878 | 3.768 | 89 | 5.490 | 0.9771 | 5.73 |
| resvg | 1024 | native | 1.955 | 4.158 | 104 | 5.737 | 0.9733 | 5.55 |
| resvg | 2048 | downsampled 2048->1024 | 1.949 | 4.136 | 100 | 5.728 | 0.9736 | 5.69 |
| resvg | 4096 | downsampled 4096->1024 | 1.954 | 4.118 | 97 | 5.732 | 0.9737 | 5.81 |
| chromium | 1024 | native | 3.279 | 5.025 | 131 | 9.911 | 0.9411 | 8.13 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.816 | 3.350 | 45 | 0.95282 |

