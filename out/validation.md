# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 256 | reference downsampled to 256 | 1.780 | 3.403 | 74 | 4.982 | 0.9805 | 5.91 |
| resvg | 512 | reference downsampled to 512 | 1.860 | 3.806 | 94 | 5.244 | 0.9773 | 5.63 |
| resvg | 1024 | native | 1.937 | 4.194 | 110 | 5.505 | 0.9736 | 5.45 |
| resvg | 2048 | downsampled 2048->1024 | 1.932 | 4.177 | 104 | 5.496 | 0.9739 | 5.63 |
| resvg | 4096 | downsampled 4096->1024 | 1.935 | 4.155 | 98 | 5.499 | 0.9740 | 5.75 |
| chromium | 1024 | native | 3.188 | 4.970 | 136 | 9.790 | 0.9434 | 7.83 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.668 | 3.209 | 44 | 0.95556 |

