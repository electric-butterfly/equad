# Segment report — CloudCompare RANSAC per region

CloudCompare command as plan section 4.5, run once per region's `<region>_pts.ply` (full-res
crop points), full-res, not the 5 M-decimation reference cloud of section 5.5.

| Region | Primitives | Cylinders | Planes | Points assigned | 11–16 mm bracket | 17–20 mm bracket | 22–26 mm bracket |
|---|---|---|---|---|---|---|---|
| engine-bay | 347 | 193 | 154 | 70.3% | 71 (rms 0.65) | 9 (rms 0.58) | 0 |
| rear-axle | 477 | 314 | 163 | 61.5% | 42 (rms 0.56) | 13 (rms 0.59) | 10 (rms 0.58) |
| rear-flange | 150 | 92 | 58 | 70.7% | 31 (rms 0.51) | 4 (rms 0.69) | 1 (rms 0.55) |
| front-flange | 362 | 246 | 116 | 57.6% | 42 (rms 0.62) | 7 (rms 0.63) | 8 (rms 0.55) |
| tank-mounts | 208 | 138 | 70 | 73.4% | 57 (rms 0.62) | 2 (rms 0.51) | 3 (rms 0.35) |
| duct-route | 265 | 159 | 106 | 71.5% | 65 (rms 0.60) | 8 (rms 0.51) | 7 (rms 0.59) |

The fraction of points assigned runs 58–73% across regions, well above the 42.8% reference in
plan section 5.5. That reference was measured on the 5 M-decimation-derived engine-bay cloud;
this WP runs RANSAC on the full-res crop points per section 4.4, which are denser and evidently
segment more completely under the same parameters.

## engine-bay — top ten primitives by support

| Kind | Index | Support | Radius (mm) | RMS (mm) |
|---|---|---|---|---|
| cylinder | 3 | 29137 | 12.70 | 0.852 |
| cylinder | 1 | 28912 | 13.13 | 0.822 |
| cylinder | 9 | 25830 | 13.16 | 0.840 |
| cylinder | 11 | 25646 | 14.69 | 0.468 |
| cylinder | 12 | 24492 | 13.91 | 0.915 |
| cylinder | 4 | 24076 | 13.31 | 0.767 |
| cylinder | 10 | 24002 | 86.96 | 0.665 |
| cylinder | 2 | 23943 | 12.72 | 0.739 |
| cylinder | 6 | 23461 | 14.73 | 0.829 |
| cylinder | 13 | 23448 | 14.44 | 0.823 |

## rear-axle — top ten primitives by support

| Kind | Index | Support | Radius (mm) | RMS (mm) |
|---|---|---|---|---|
| cylinder | 3 | 24117 | 27.03 | 0.869 |
| cylinder | 1 | 21407 | 24.97 | 0.547 |
| cylinder | 2 | 19172 | 70.71 | 33.104 |
| plane | 1 | 14464 | — | 0.329 |
| cylinder | 6 | 14277 | 87.44 | 45.236 |
| cylinder | 4 | 13609 | 136.77 | 77.597 |
| cylinder | 7 | 10793 | 119.12 | 37.814 |
| cylinder | 5 | 9947 | 19.08 | 0.624 |
| cylinder | 31 | 9932 | 87.86 | 35.436 |
| cylinder | 14 | 9781 | 25.90 | 0.588 |

The two highest-support cylinders (index 3, r 27.03 mm; index 1, r 24.97 mm) are the rear axle
housings — radius in range 22–30 mm as the plan's section 5.4 reference (r 24.6 / 23.9 mm), rms
under 0.87 mm. A further four cylinders in the 20–30 mm bracket with axis within 8° of Y also
appear (support 1489–4156, a tenth or less of the two housings' support) — smaller-radius,
lower-support finds in the same bracket rather than a second pair of housings; RANSAC parameters
are unchanged from section 4.5 per the scope fence, so this is reported as observed rather than
filtered by support.
