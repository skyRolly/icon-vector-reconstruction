# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 256 | reference downsampled to 256 | 1.818 | 3.278 | 65 | 5.790 | 0.9795 | 5.64 |
| resvg | 512 | reference downsampled to 512 | 1.905 | 3.711 | 84 | 5.990 | 0.9760 | 5.67 |
| resvg | 1024 | native | 1.979 | 4.092 | 112 | 6.210 | 0.9724 | 5.40 |
| resvg | 2048 | downsampled 2048->1024 | 1.972 | 4.063 | 104 | 6.195 | 0.9727 | 5.56 |
| resvg | 4096 | downsampled 4096->1024 | 1.974 | 4.033 | 99 | 6.197 | 0.9728 | 5.68 |
| chromium | 1024 | native | 3.124 | 4.882 | 131 | 9.393 | 0.9454 | 8.17 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.629 | 3.129 | 39 | 0.95546 |

