# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 256 | reference downsampled to 256 | 1.648 | 2.955 | 64 | 4.812 | 0.9818 | 4.58 |
| resvg | 512 | reference downsampled to 512 | 1.722 | 3.371 | 87 | 5.062 | 0.9787 | 4.28 |
| resvg | 1024 | native | 1.805 | 3.816 | 108 | 5.331 | 0.9745 | 4.23 |
| resvg | 2048 | downsampled 2048->1024 | 1.801 | 3.798 | 101 | 5.324 | 0.9748 | 4.37 |
| resvg | 4096 | downsampled 4096->1024 | 1.806 | 3.785 | 96 | 5.329 | 0.9748 | 4.48 |
| chromium | 1024 | native | 3.089 | 4.703 | 136 | 9.643 | 0.9441 | 6.51 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.698 | 3.244 | 45 | 0.95535 |

