# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 256 | reference downsampled to 256 | 1.741 | 3.279 | 65 | 4.948 | 0.9809 | 5.53 |
| resvg | 512 | reference downsampled to 512 | 1.821 | 3.695 | 88 | 5.209 | 0.9777 | 5.27 |
| resvg | 1024 | native | 1.899 | 4.095 | 110 | 5.470 | 0.9739 | 5.14 |
| resvg | 2048 | downsampled 2048->1024 | 1.894 | 4.078 | 104 | 5.462 | 0.9741 | 5.28 |
| resvg | 4096 | downsampled 4096->1024 | 1.898 | 4.056 | 98 | 5.465 | 0.9742 | 5.39 |
| chromium | 1024 | native | 3.142 | 4.878 | 136 | 9.742 | 0.9437 | 7.24 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.666 | 3.208 | 44 | 0.95556 |

