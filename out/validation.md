# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 256 | reference downsampled to 256 | 1.740 | 3.278 | 65 | 4.947 | 0.9810 | 5.52 |
| resvg | 512 | reference downsampled to 512 | 1.820 | 3.694 | 88 | 5.207 | 0.9777 | 5.26 |
| resvg | 1024 | native | 1.898 | 4.093 | 110 | 5.468 | 0.9739 | 5.14 |
| resvg | 2048 | downsampled 2048->1024 | 1.893 | 4.077 | 104 | 5.460 | 0.9742 | 5.28 |
| resvg | 4096 | downsampled 4096->1024 | 1.896 | 4.055 | 98 | 5.464 | 0.9742 | 5.39 |
| chromium | 1024 | native | 3.141 | 4.878 | 136 | 9.742 | 0.9437 | 7.24 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.667 | 3.208 | 44 | 0.95556 |

