# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 256 | reference downsampled to 256 | 1.657 | 2.973 | 60 | 4.827 | 0.9818 | 4.71 |
| resvg | 512 | reference downsampled to 512 | 1.731 | 3.387 | 85 | 5.077 | 0.9786 | 4.42 |
| resvg | 1024 | native | 1.815 | 3.832 | 108 | 5.346 | 0.9745 | 4.37 |
| resvg | 2048 | downsampled 2048->1024 | 1.811 | 3.814 | 101 | 5.339 | 0.9748 | 4.51 |
| resvg | 4096 | downsampled 4096->1024 | 1.816 | 3.802 | 96 | 5.345 | 0.9748 | 4.63 |
| chromium | 1024 | native | 3.101 | 4.724 | 136 | 9.657 | 0.9440 | 6.63 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.695 | 3.240 | 45 | 0.95535 |

