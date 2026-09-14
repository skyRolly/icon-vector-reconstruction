# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 256 | reference downsampled to 256 | 1.764 | 3.311 | 65 | 4.971 | 0.9807 | 5.89 |
| resvg | 512 | reference downsampled to 512 | 1.845 | 3.724 | 88 | 5.233 | 0.9774 | 5.60 |
| resvg | 1024 | native | 1.923 | 4.120 | 110 | 5.495 | 0.9737 | 5.42 |
| resvg | 2048 | downsampled 2048->1024 | 1.918 | 4.103 | 104 | 5.486 | 0.9740 | 5.60 |
| resvg | 4096 | downsampled 4096->1024 | 1.921 | 4.081 | 98 | 5.489 | 0.9741 | 5.73 |
| chromium | 1024 | native | 3.176 | 4.919 | 136 | 9.782 | 0.9435 | 7.82 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.668 | 3.209 | 44 | 0.95556 |

