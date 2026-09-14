# Crop stage — six regions

Boxes and fractions per `pipeline/crops.toml` and plan section 4.4. Fraction is the share of
above-floor (Z > 6 mm) vertices of `chassis_datum_5M.stl` inside each box; expected values were
measured on the owner's workstation on 2026-09-14.

| Region | Box (x / y / z, mm) | Points | Fraction | Expected | Diff (pp) |
|---|---|---|---|---|---|
| engine-bay | [400,1100] / [-350,350] / [80,800] | 1 451 797 | 0.1204 | 0.1204 | -0.005 |
| tank-mounts | [300,1200] / [-250,250] / [620,1000] | 987 377 | 0.0819 | 0.0819 | -0.005 |
| front-flange | [950,1350] / [-200,200] / [200,650] | 1 260 019 | 0.1045 | 0.1047 | -0.025 |
| rear-flange | [300,650] / [-250,250] / [150,550] | 535 154 | 0.0444 | 0.0442 | 0.016 |
| duct-route | [450,1150] / [-180,180] / [150,800] | 1 170 330 | 0.0970 | 0.0971 | -0.008 |
| rear-axle | [-150,150] / [-480,480] / [150,480] | 1 340 702 | 0.1111 | 0.1112 | -0.006 |

All six fractions are within 0.03 percentage points of expected, well inside the 1.5 pp tolerance.

Renders (plan view left, side view right, 0.6 mm per pixel):

- [crop-engine-bay.png](crop-engine-bay.png)
- [crop-tank-mounts.png](crop-tank-mounts.png)
- [crop-front-flange.png](crop-front-flange.png)
- [crop-rear-flange.png](crop-rear-flange.png)
- [crop-duct-route.png](crop-duct-route.png)
- [crop-rear-axle.png](crop-rear-axle.png)
