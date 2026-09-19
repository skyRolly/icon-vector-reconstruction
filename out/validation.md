# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 256 | reference downsampled to 256 | 1.717 | 3.219 | 67 | 4.924 | 0.9814 | 5.26 |
| resvg | 512 | reference downsampled to 512 | 1.797 | 3.644 | 90 | 5.184 | 0.9780 | 5.01 |
| resvg | 1024 | native | 1.877 | 4.049 | 110 | 5.447 | 0.9741 | 4.92 |
| resvg | 2048 | downsampled 2048->1024 | 1.872 | 4.032 | 104 | 5.439 | 0.9744 | 5.06 |
| resvg | 4096 | downsampled 4096->1024 | 1.875 | 4.010 | 98 | 5.442 | 0.9744 | 5.17 |
| chromium | 1024 | native | 3.148 | 4.871 | 136 | 9.749 | 0.9437 | 7.25 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.680 | 3.220 | 44 | 0.95546 |

