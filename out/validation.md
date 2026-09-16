# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 256 | reference downsampled to 256 | 1.720 | 3.241 | 67 | 4.924 | 0.9813 | 5.34 |
| resvg | 512 | reference downsampled to 512 | 1.801 | 3.661 | 90 | 5.184 | 0.9780 | 5.06 |
| resvg | 1024 | native | 1.881 | 4.066 | 110 | 5.447 | 0.9740 | 4.98 |
| resvg | 2048 | downsampled 2048->1024 | 1.876 | 4.050 | 104 | 5.439 | 0.9743 | 5.12 |
| resvg | 4096 | downsampled 4096->1024 | 1.879 | 4.027 | 98 | 5.442 | 0.9744 | 5.23 |
| chromium | 1024 | native | 3.154 | 4.884 | 136 | 9.756 | 0.9436 | 7.27 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.684 | 3.223 | 44 | 0.95543 |

