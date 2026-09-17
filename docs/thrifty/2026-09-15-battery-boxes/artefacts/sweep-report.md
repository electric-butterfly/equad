This sweep tests the frame, the placeholder motor and the propeller-shaft keep-out only; plastics, foot boards, tank and seat are not in the scan.

Grid: 525 placements, 0 pass.

| X | lean | feasible Y | feasible Z | best min_frame |
|---|---|---|---|---|
| 693.2 | 72.0 | - | - | none feasible |
| 693.2 | 77.0 | - | - | none feasible |
| 693.2 | 82.0 | - | - | none feasible |
| 693.2 | 87.0 | - | - | none feasible |
| 693.2 | 92.0 | - | - | none feasible |
| 743.2 | 72.0 | - | - | none feasible |
| 743.2 | 77.0 | - | - | none feasible |
| 743.2 | 82.0 | - | - | none feasible |
| 743.2 | 87.0 | - | - | none feasible |
| 743.2 | 92.0 | - | - | none feasible |
| 793.2 | 72.0 | - | - | none feasible |
| 793.2 | 77.0 | - | - | none feasible |
| 793.2 | 82.0 | - | - | none feasible |
| 793.2 | 87.0 | - | - | none feasible |
| 793.2 | 92.0 | - | - | none feasible |

No placement in the swept grid passes all three tests.

[placement] defaults (x=743.2, y=39.2643, z=440.4765, lean_deg=82.0) are not a grid point in this sweep, so no exact-match row exists; see the nearest grid rows above.

Motor placeholder vs frame (not part of pass, evaluated once): min_frame=0.07 mm, points inside=41066.

chamfer would not help: not evaluated in this run.

Nothing in this grid clears the frame - every one of the 525 placements has real frame points
inside the box (inside_frame never reached 0). The least-bad point found, used for the
section-*-best.png renders below, is x=793.2, y=-50.0, z=465.0, lean=87.0: min_frame=0.56mm,
inside_frame=15580 points, min_motor=178.8mm, min_keepout=0.012mm. This is not a fit; it is the
smallest measured intrusion in the swept neighbourhood, shown so the owner can see how close
"close" actually is.

Section renders: section-yz-default.png, section-xz-default.png, section-xy-default.png (the
committed [placement] defaults); section-yz-best.png, section-xz-best.png, section-xy-best.png
(the least-bad point above).
