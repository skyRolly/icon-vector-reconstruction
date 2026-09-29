# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 256 | reference downsampled to 256 | 1.501 | 2.429 | 39 | 4.676 | 0.9833 | 3.08 |
| resvg | 512 | reference downsampled to 512 | 1.525 | 2.465 | 47 | 4.901 | 0.9806 | 2.88 |
| resvg | 1024 | native | 1.591 | 2.683 | 73 | 5.160 | 0.9775 | 3.02 |
| resvg | 2048 | downsampled 2048->1024 | 1.581 | 2.644 | 65 | 5.147 | 0.9778 | 3.12 |
| resvg | 4096 | downsampled 4096->1024 | 1.583 | 2.645 | 67 | 5.149 | 0.9778 | 3.20 |
| chromium | 1024 | native | 2.908 | 3.806 | 75 | 9.507 | 0.9469 | 5.32 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.638 | 3.014 | 36 | 0.95588 |

