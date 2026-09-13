# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 256 | reference downsampled to 256 | 1.787 | 3.269 | 62 | 5.284 | 0.9804 | 5.89 |
| resvg | 512 | reference downsampled to 512 | 1.868 | 3.688 | 87 | 5.523 | 0.9768 | 5.73 |
| resvg | 1024 | native | 1.941 | 4.075 | 105 | 5.766 | 0.9731 | 5.48 |
| resvg | 2048 | downsampled 2048->1024 | 1.938 | 4.060 | 100 | 5.758 | 0.9734 | 5.66 |
| resvg | 4096 | downsampled 4096->1024 | 1.943 | 4.041 | 97 | 5.763 | 0.9734 | 5.80 |
| chromium | 1024 | native | 3.269 | 4.971 | 131 | 9.907 | 0.9412 | 8.31 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.909 | 3.473 | 45 | 0.94988 |

