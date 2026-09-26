# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 256 | reference downsampled to 256 | 1.566 | 2.663 | 36 | 4.740 | 0.9823 | 3.90 |
| resvg | 512 | reference downsampled to 512 | 1.609 | 2.790 | 49 | 4.970 | 0.9796 | 3.70 |
| resvg | 1024 | native | 1.699 | 3.152 | 67 | 5.248 | 0.9760 | 3.77 |
| resvg | 2048 | downsampled 2048->1024 | 1.697 | 3.170 | 63 | 5.243 | 0.9762 | 3.90 |
| resvg | 4096 | downsampled 4096->1024 | 1.705 | 3.204 | 67 | 5.250 | 0.9762 | 3.98 |
| chromium | 1024 | native | 2.967 | 4.041 | 90 | 9.545 | 0.9459 | 5.67 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.691 | 3.212 | 44 | 0.95541 |

