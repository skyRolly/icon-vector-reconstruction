# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 256 | reference downsampled to 256 | 1.551 | 2.617 | 36 | 4.716 | 0.9831 | 3.74 |
| resvg | 512 | reference downsampled to 512 | 1.595 | 2.742 | 49 | 4.948 | 0.9802 | 3.56 |
| resvg | 1024 | native | 1.684 | 3.107 | 67 | 5.226 | 0.9764 | 3.63 |
| resvg | 2048 | downsampled 2048->1024 | 1.683 | 3.124 | 63 | 5.221 | 0.9766 | 3.77 |
| resvg | 4096 | downsampled 4096->1024 | 1.690 | 3.161 | 67 | 5.229 | 0.9766 | 3.85 |
| chromium | 1024 | native | 2.966 | 4.035 | 90 | 9.546 | 0.9461 | 5.63 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.693 | 3.215 | 44 | 0.95544 |

