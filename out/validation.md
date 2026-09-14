# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 256 | reference downsampled to 256 | 1.800 | 3.357 | 67 | 5.261 | 0.9805 | 5.91 |
| resvg | 512 | reference downsampled to 512 | 1.881 | 3.771 | 87 | 5.499 | 0.9771 | 5.72 |
| resvg | 1024 | native | 1.958 | 4.160 | 104 | 5.746 | 0.9733 | 5.54 |
| resvg | 2048 | downsampled 2048->1024 | 1.952 | 4.138 | 100 | 5.737 | 0.9736 | 5.68 |
| resvg | 4096 | downsampled 4096->1024 | 1.957 | 4.120 | 97 | 5.741 | 0.9736 | 5.81 |
| chromium | 1024 | native | 3.275 | 5.017 | 131 | 9.901 | 0.9411 | 8.12 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.803 | 3.339 | 45 | 0.95284 |

