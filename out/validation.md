# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 256 | reference downsampled to 256 | 1.636 | 2.888 | 47 | 4.802 | 0.9820 | 4.53 |
| resvg | 512 | reference downsampled to 512 | 1.688 | 3.108 | 80 | 5.039 | 0.9791 | 4.26 |
| resvg | 1024 | native | 1.757 | 3.365 | 79 | 5.302 | 0.9756 | 4.21 |
| resvg | 2048 | downsampled 2048->1024 | 1.753 | 3.368 | 80 | 5.296 | 0.9758 | 4.35 |
| resvg | 4096 | downsampled 4096->1024 | 1.761 | 3.398 | 78 | 5.303 | 0.9757 | 4.46 |
| chromium | 1024 | native | 3.052 | 4.329 | 104 | 9.623 | 0.9452 | 6.52 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.697 | 3.232 | 45 | 0.95537 |

