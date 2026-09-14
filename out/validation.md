# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 256 | reference downsampled to 256 | 1.779 | 3.403 | 74 | 4.981 | 0.9805 | 5.90 |
| resvg | 512 | reference downsampled to 512 | 1.859 | 3.805 | 94 | 5.243 | 0.9773 | 5.63 |
| resvg | 1024 | native | 1.936 | 4.193 | 110 | 5.504 | 0.9736 | 5.44 |
| resvg | 2048 | downsampled 2048->1024 | 1.931 | 4.176 | 104 | 5.495 | 0.9739 | 5.62 |
| resvg | 4096 | downsampled 4096->1024 | 1.935 | 4.155 | 98 | 5.499 | 0.9740 | 5.75 |
| chromium | 1024 | native | 3.187 | 4.969 | 136 | 9.789 | 0.9434 | 7.82 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.668 | 3.209 | 44 | 0.95556 |

