# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 256 | reference downsampled to 256 | 1.504 | 2.435 | 40 | 4.680 | 0.9833 | 3.09 |
| resvg | 512 | reference downsampled to 512 | 1.528 | 2.474 | 46 | 4.905 | 0.9806 | 2.89 |
| resvg | 1024 | native | 1.592 | 2.687 | 73 | 5.163 | 0.9775 | 3.03 |
| resvg | 2048 | downsampled 2048->1024 | 1.583 | 2.651 | 65 | 5.151 | 0.9778 | 3.14 |
| resvg | 4096 | downsampled 4096->1024 | 1.585 | 2.653 | 67 | 5.153 | 0.9778 | 3.22 |
| chromium | 1024 | native | 2.913 | 3.817 | 75 | 9.514 | 0.9468 | 5.38 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.638 | 3.015 | 36 | 0.95588 |

