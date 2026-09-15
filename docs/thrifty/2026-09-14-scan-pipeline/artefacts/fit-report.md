# Fit report — full-resolution refinement of RANSAC primitives

Per plan section 4.6. Candidates are RANSAC primitives that pass the section 4.5 acceptance rule
(cylinder: radius in a `tube_radii_mm` bracket and RANSAC rms under 1.2 mm; plane: RANSAC rms under
0.6 mm and support over 500). Each candidate is refined on full-resolution crop points within 3 mm
of the RANSAC surface (cylinders additionally bounded to the RANSAC primitive's own axial extent,
so the fit is not pulled in by unrelated points sharing the same infinite axis and radius). A
candidate is accepted when its refined rms is under 1.0 mm (cylinder) or 0.5 mm (plane); otherwise
it is written with `accepted: false` and a reason.

`tube_radii_mm` used: `[[11, 16], [17, 20], [22, 26], [26, 29]]` — the owner's
`pipeline/config.local.toml` extends the plan's default with a 26–29 mm bracket to admit the
rear-axle housing's left side. `CYLINDER_ACCEPT_RMS_MAX` is 1.0 mm in this run (`pipeline/fit.py`),
raised from the plan's original 0.8 mm. Neither change is reproducible from a fresh clone without
also setting `tube_radii_mm` locally, since `config.local.toml` is git-ignored by design.

## Per-region counts

| Region | Candidates | Accepted | Rejected |
|---|---|---|---|
| engine-bay | 206 | 32 | 174 |
| tank-mounts | 118 | 37 | 81 |
| front-flange | 142 | 26 | 116 |
| rear-flange | 85 | 11 | 74 |
| duct-route | 167 | 46 | 121 |
| rear-axle | 173 | 21 | 152 |
| **Total** | **891** | **173** | **718** |

## Rear-axle housing rows, in full

The two axle-housing cylinders identified by support are `rear-axle/cyl/001` (right side) and
`rear-axle/cyl/003` (left side).

| id | RANSAC radius | RANSAC support | Candidate? | Refined radius | Refined support | Refined rms | Accepted |
|---|---|---|---|---|---|---|---|
| rear-axle/cyl/001 | 24.97 mm | 21407 | yes | 25.601 mm | 79603 | 0.219 mm | true |
| rear-axle/cyl/003 | 27.03 mm | 24117 | yes (26–29 mm bracket) | 25.921 mm | 106842 | 1.940 mm | **false — refined rms 1.940 mm >= 1.0 mm** |

Widening the bracket got `cyl/003` into refinement, but it does not resolve to a clean cylinder:
its refined rms (1.940 mm) is well above even the relaxed 1.0 mm threshold, despite 106,842
supporting points. This is not a threshold or bracket problem — the real surface at that location
does not fit a constant-radius cylinder as well as the coarser RANSAC-stage estimate suggested,
which points to a physical feature near the housing (a flange, weld, or step) rather than a fitting
artefact. Confirming this needs a calliper or an individual rescan of the housing, not a further
threshold change.

## Ten worst residuals across all regions

| Region | id | Kind | Refined rms (mm) | p95 (mm) | Accepted |
|---|---|---|---|---|---|
| rear-axle | rear-axle/cyl/227 | cylinder | 8.019 | 14.644 | false |
| front-flange | front-flange/cyl/100 | cylinder | 8.019 | 13.794 | false |
| engine-bay | engine-bay/cyl/189 | cylinder | 6.378 | 11.597 | false |
| front-flange | front-flange/cyl/091 | cylinder | 5.690 | 11.245 | false |
| front-flange | front-flange/cyl/207 | cylinder | 5.657 | 10.209 | false |
| rear-axle | rear-axle/cyl/226 | cylinder | 5.646 | 9.303 | false |
| rear-flange | rear-flange/cyl/023 | cylinder | 5.545 | 9.154 | false |
| duct-route | duct-route/cyl/132 | cylinder | 5.323 | 9.125 | false |
| front-flange | front-flange/cyl/193 | cylinder | 5.149 | 8.158 | false |
| duct-route | duct-route/cyl/076 | cylinder | 4.759 | 9.780 | false |

All ten worst residuals are rejected cylinders; no accepted row (cylinder or plane) appears in this
list.

## The ~13 mm tube family

Widening the accept threshold to 1.0 mm was aimed at a cluster of well-supported ~13 mm-radius
cylinders that were rejected under the original 0.8 mm cutoff. Checking every cylinder with radius
12.5–15.5 mm and support over 50,000 points (81 candidates across five regions): 48 are now
accepted, 33 remain rejected, several with rms well over 1.0 mm (up to 2.29 mm). This is not one
tube gauge landing just past a threshold — it is a mix of genuinely clean fits and messier ones,
likely where the same tube family crosses welds or other features. The cleanest example is
`tank-mounts/cyl/001` (r 13.50 mm, rms 0.223 mm, support 181,694) — the candidate to calliper first
if confirming this tube gauge.
