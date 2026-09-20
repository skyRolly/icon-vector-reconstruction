# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 256 | reference downsampled to 256 | 1.685 | 3.133 | 67 | 4.887 | 0.9815 | 4.84 |
| resvg | 512 | reference downsampled to 512 | 1.758 | 3.542 | 90 | 5.139 | 0.9784 | 4.56 |
| resvg | 1024 | native | 1.842 | 3.974 | 110 | 5.406 | 0.9744 | 4.52 |
| resvg | 2048 | downsampled 2048->1024 | 1.837 | 3.957 | 104 | 5.398 | 0.9747 | 4.66 |
| resvg | 4096 | downsampled 4096->1024 | 1.841 | 3.943 | 98 | 5.403 | 0.9747 | 4.77 |
| chromium | 1024 | native | 3.126 | 4.828 | 136 | 9.728 | 0.9439 | 7.05 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.679 | 3.211 | 44 | 0.95549 |

