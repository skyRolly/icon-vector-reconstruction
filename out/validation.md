# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 1024 | native | 1.922 | 4.118 | 110 | 5.495 | 0.9738 | 5.41 |
| resvg | 2048 | downsampled 2048->1024 | 1.917 | 4.101 | 104 | 5.486 | 0.9741 | 5.59 |
| chromium | 1024 | native | 3.176 | 4.919 | 136 | 9.784 | 0.9435 | 7.83 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.668 | 3.210 | 44 | 0.95555 |

