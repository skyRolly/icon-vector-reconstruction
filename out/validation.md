# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 256 | reference downsampled to 256 | 1.726 | 3.255 | 67 | 4.930 | 0.9811 | 5.42 |
| resvg | 512 | reference downsampled to 512 | 1.807 | 3.674 | 90 | 5.190 | 0.9779 | 5.14 |
| resvg | 1024 | native | 1.886 | 4.076 | 110 | 5.453 | 0.9740 | 5.06 |
| resvg | 2048 | downsampled 2048->1024 | 1.882 | 4.060 | 104 | 5.445 | 0.9742 | 5.20 |
| resvg | 4096 | downsampled 4096->1024 | 1.885 | 4.038 | 98 | 5.448 | 0.9743 | 5.32 |
| chromium | 1024 | native | 3.158 | 4.895 | 136 | 9.759 | 0.9436 | 7.35 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.683 | 3.222 | 44 | 0.95543 |

