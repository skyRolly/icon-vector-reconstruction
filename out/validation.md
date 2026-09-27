# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 256 | reference downsampled to 256 | 1.547 | 2.602 | 36 | 4.714 | 0.9831 | 3.72 |
| resvg | 512 | reference downsampled to 512 | 1.591 | 2.726 | 49 | 4.946 | 0.9802 | 3.53 |
| resvg | 1024 | native | 1.680 | 3.090 | 67 | 5.224 | 0.9765 | 3.61 |
| resvg | 2048 | downsampled 2048->1024 | 1.679 | 3.107 | 63 | 5.219 | 0.9767 | 3.75 |
| resvg | 4096 | downsampled 4096->1024 | 1.687 | 3.145 | 67 | 5.227 | 0.9766 | 3.84 |
| chromium | 1024 | native | 2.964 | 4.033 | 90 | 9.545 | 0.9461 | 5.62 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.693 | 3.218 | 44 | 0.95543 |

