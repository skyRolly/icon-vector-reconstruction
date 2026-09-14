# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 1024 | native | 1.899 | 4.095 | 110 | 5.470 | 0.9739 | 5.14 |
| resvg | 2048 | downsampled 2048->1024 | 1.894 | 4.078 | 104 | 5.462 | 0.9741 | 5.28 |
| chromium | 1024 | native | 3.142 | 4.878 | 136 | 9.742 | 0.9437 | 7.24 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.666 | 3.208 | 44 | 0.95556 |

