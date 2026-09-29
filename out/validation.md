# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 256 | reference downsampled to 256 | 1.504 | 2.437 | 40 | 4.681 | 0.9833 | 3.10 |
| resvg | 512 | reference downsampled to 512 | 1.528 | 2.477 | 46 | 4.905 | 0.9806 | 2.90 |
| resvg | 1024 | native | 1.594 | 2.696 | 73 | 5.164 | 0.9774 | 3.03 |
| resvg | 2048 | downsampled 2048->1024 | 1.584 | 2.662 | 65 | 5.152 | 0.9778 | 3.14 |
| resvg | 4096 | downsampled 4096->1024 | 1.587 | 2.665 | 67 | 5.154 | 0.9778 | 3.21 |
| chromium | 1024 | native | 2.914 | 3.823 | 75 | 9.515 | 0.9468 | 5.38 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.638 | 3.015 | 36 | 0.95588 |

