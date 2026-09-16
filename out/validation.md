# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 256 | reference downsampled to 256 | 1.718 | 3.224 | 67 | 4.925 | 0.9814 | 5.28 |
| resvg | 512 | reference downsampled to 512 | 1.799 | 3.648 | 90 | 5.185 | 0.9780 | 5.03 |
| resvg | 1024 | native | 1.878 | 4.052 | 110 | 5.448 | 0.9741 | 4.95 |
| resvg | 2048 | downsampled 2048->1024 | 1.873 | 4.035 | 104 | 5.440 | 0.9744 | 5.09 |
| resvg | 4096 | downsampled 4096->1024 | 1.877 | 4.013 | 98 | 5.443 | 0.9744 | 5.20 |
| chromium | 1024 | native | 3.146 | 4.868 | 136 | 9.747 | 0.9437 | 7.20 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.680 | 3.220 | 44 | 0.95546 |

