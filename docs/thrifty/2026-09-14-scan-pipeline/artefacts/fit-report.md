# Fit report — full-resolution refinement of RANSAC primitives

Per plan section 4.6. Candidates are RANSAC primitives that pass the section 4.5 acceptance rule
(cylinder: radius in a `tube_radii_mm` bracket and RANSAC rms under 1.2 mm; plane: RANSAC rms under
0.6 mm and support over 500). Each candidate is refined on full-resolution crop points within 3 mm
of the RANSAC surface (cylinders additionally bounded to the RANSAC primitive's own axial extent,
so the fit is not pulled in by unrelated points sharing the same infinite axis and radius). A
candidate is accepted when its refined rms is under 0.8 mm (cylinder) or 0.5 mm (plane); otherwise
it is written with `accepted: false` and a reason.

`tube_radii_mm` used: the default `[[11, 16], [17, 20], [22, 26]]` (`pipeline/config.local.toml`
carries no override).

## Per-region counts

| Region | Candidates | Accepted | Rejected |
|---|---|---|---|
| engine-bay | 203 | 25 | 178 |
| tank-mounts | 118 | 26 | 92 |
| front-flange | 139 | 23 | 116 |
| rear-flange | 85 | 8 | 77 |
| duct-route | 167 | 33 | 134 |
| rear-axle | 165 | 12 | 153 |
| **Total** | **877** | **127** | **750** |

Row count in `interfaces.json` equals the independently recomputed candidate count across the six
`primitives-<region>.json` files: 877 both ways.

## Rear-axle housing rows, in full

The two axle-housing cylinders WP-05 identified by support (RANSAC-stage) are `rear-axle/cyl/001`
(r 24.97 mm, support 21407) and `rear-axle/cyl/003` (r 27.03 mm, support 24117).

| id | RANSAC radius | RANSAC support | Candidate? | Refined radius | Refined support | Refined rms | Accepted |
|---|---|---|---|---|---|---|---|
| rear-axle/cyl/001 | 24.97 mm | 21407 | yes | 25.606 mm | 79547 | 0.223 mm | true |
| rear-axle/cyl/003 | 27.03 mm | 24117 | **no — 27.03 mm is outside the `[22, 26]` bracket** | — | — | — | — (never fitted) |

`rear-axle/cyl/003` never reaches the fit stage: its RANSAC radius falls 1.03 mm above the default
bracket's upper bound, so section 4.5's candidate rule excludes it before refinement runs. This
reproduces, downstream, the boundary case WP-05's own findings file already flagged. Per this WP's
scope fence ("do not loosen a threshold to accept a primitive — record it rejected with the
reason"), the bracket was left as specified rather than widened; see `findings/WP-06.md`.

A different, much smaller-support RANSAC cylinder (`rear-axle/cyl/114`, RANSAC radius 23.72 mm,
support 949) does fall inside the bracket and refines to accepted (radius 27.40 mm, rms 0.537 mm,
axis 3.47° from `rear-axle/cyl/001`'s axis). It is not the second housing — its RANSAC support is
23–25x smaller than either true housing detection — so the **done-when expectation of "the two
rear-axle-housing cylinders accepted, radius 22–27 mm, axes within 1°" is not met exactly**: one
housing (`cyl/001`) is accepted correctly; the other (`cyl/003`) is excluded by the bracket, and the
accepted cylinder nearest to it in radius (`cyl/114`) is a separate, smaller feature, 3.47° off
axis — outside the 1° tolerance. Reported here rather than corrected, per the scope fence.

## Ten worst residuals across all regions

| Region | id | Kind | Refined rms (mm) | p95 (mm) | Accepted |
|---|---|---|---|---|---|
| front-flange | front-flange/cyl/100 | cylinder | 8.557 | 14.987 | false |
| rear-axle | rear-axle/cyl/227 | cylinder | 7.872 | 14.484 | false |
| engine-bay | engine-bay/cyl/189 | cylinder | 6.396 | 11.781 | false |
| front-flange | front-flange/cyl/193 | cylinder | 6.294 | 10.370 | false |
| rear-flange | rear-flange/cyl/023 | cylinder | 5.731 | 9.525 | false |
| front-flange | front-flange/cyl/091 | cylinder | 5.669 | 11.347 | false |
| rear-axle | rear-axle/cyl/226 | cylinder | 5.342 | 8.872 | false |
| duct-route | duct-route/cyl/132 | cylinder | 5.271 | 9.110 | false |
| front-flange | front-flange/cyl/207 | cylinder | 5.162 | 9.226 | false |
| front-flange | front-flange/cyl/177 | cylinder | 4.714 | 8.765 | false |

All ten worst residuals are rejected cylinders; no accepted row (cylinder or plane) appears in this
list, consistent with the 0.8 mm / 0.5 mm acceptance thresholds.
