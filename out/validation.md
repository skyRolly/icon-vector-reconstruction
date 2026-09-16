# Validation report

Fidelity of `reconstruction.svg` against `reference.png`, plus
cross-engine and cross-resolution behaviour.

| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |
|---|---|---|---|---|---|---|---|---|
| resvg | 256 | reference downsampled to 256 | 1.722 | 3.245 | 67 | 4.925 | 0.9813 | 5.35 |
| resvg | 512 | reference downsampled to 512 | 1.802 | 3.665 | 90 | 5.185 | 0.9780 | 5.07 |
| resvg | 1024 | native | 1.882 | 4.070 | 110 | 5.449 | 0.9740 | 4.99 |
| resvg | 2048 | downsampled 2048->1024 | 1.877 | 4.053 | 104 | 5.440 | 0.9743 | 5.14 |
| resvg | 4096 | downsampled 4096->1024 | 1.880 | 4.031 | 98 | 5.443 | 0.9743 | 5.25 |
| chromium | 1024 | native | 3.153 | 4.884 | 136 | 9.754 | 0.9436 | 7.27 |

## Cross-engine agreement at 1024 (resvg vs Chromium)

| MAE | RMSE | max | SSIM |
|---|---|---|---|
| 2.683 | 3.222 | 44 | 0.95544 |

