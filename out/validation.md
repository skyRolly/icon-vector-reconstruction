# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 256 | reference downsampled to 256 | 1.674 | 3.078 | 65 | 4.849 | 0.9816 | 4.78 |
| resvg | 512 | reference downsampled to 512 | 1.747 | 3.470 | 85 | 5.096 | 0.9784 | 4.51 |
| resvg | 1024 | native | 1.831 | 3.908 | 108 | 5.366 | 0.9744 | 4.45 |
| resvg | 2048 | downsampled 2048->1024 | 1.826 | 3.889 | 101 | 5.358 | 0.9746 | 4.58 |
| resvg | 4096 | downsampled 4096->1024 | 1.831 | 3.877 | 96 | 5.364 | 0.9747 | 4.70 |
| chromium | 1024 | native | 3.107 | 4.752 | 136 | 9.666 | 0.9439 | 6.69 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.695 | 3.239 | 45 | 0.95535 |

