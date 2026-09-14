# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 256 | reference downsampled to 256 | 1.795 | 3.347 | 69 | 5.249 | 0.9805 | 5.92 |
| resvg | 512 | reference downsampled to 512 | 1.877 | 3.766 | 89 | 5.489 | 0.9771 | 5.72 |
| resvg | 1024 | native | 1.954 | 4.156 | 104 | 5.736 | 0.9734 | 5.53 |
| resvg | 2048 | downsampled 2048->1024 | 1.948 | 4.134 | 100 | 5.726 | 0.9736 | 5.67 |
| resvg | 4096 | downsampled 4096->1024 | 1.953 | 4.116 | 97 | 5.731 | 0.9737 | 5.80 |
| chromium | 1024 | native | 3.275 | 5.020 | 131 | 9.904 | 0.9411 | 8.12 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.815 | 3.349 | 45 | 0.95283 |

