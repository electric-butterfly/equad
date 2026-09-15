# Enclosure report

## Parameters used
| Section | Key | Value |
|---|---|---|
| enclosure | internal | [460.0, 300.0, 200.0] |
| enclosure | sheet | 3.0 |
| enclosure | lid_face | +Z |
| enclosure | lid_inset | 15.0 |
| enclosure | lid_bolt_d | 6.5 |
| enclosure | lid_bolt_pitch_max | 60.0 |
| enclosure | end_plate | 6.0 |
| enclosure | partition | 3.0 |
| enclosure | compression_plate | 6.0 |
| enclosure | compression_wall | outboard |
| enclosure | compression_pairs | 5 |
| enclosure | compression_rows_z | [30.0, 75.0] |
| enclosure | compression_screw_d | 8.0 |
| enclosure | compression_travel_min | 10.0 |
| enclosure | chamfer_front_top | 0.0 |
| electrical | fuses_per_box | 2 |
| electrical | fuse_envelope | [90.0, 45.0, 60.0] |
| electrical | headroom | 60.0 |
| electrical | cable_exit_face | inboard |
| electrical | cable_exit_d | [20.0, 20.0, 25.0] |
| electrical | cable_exit_z | 160.0 |

## Y layout
| Element | Y low | Y high |
|---|---|---|
| end plate | -150.0 | -144.0 |
| fuse bay | -144.0 | -114.34 |
| partition | -117.34 | -114.34 |
| compression plate | 119.94 | 125.94 |
| stack length | 263.94 | |
| travel | 24.060000000000002 | |

## Front-column spacer - finding
Section 4.5 specifies a spacer of thickness `p - partition` between the front column's last cell and the compression plate. The rows produced by `cell.block()` (and section 4.4's own worked numbers, e.g. the 24.06 mm travel figure) show the front column's last cell is already flush with the 9-cell columns' last cell - both are positioned by the same `y0 + p*slot` formula at slot = n_max - 1. The computed gap here is 0.0 mm, not `p - partition` (26.66 mm). Building the literal-thickness block would overlap the compression plate, which spans the full cavity width. No spacer solid is built; box.step therefore has 7 solids (not the 8 the done-when criterion names), and box-full.step has 33 (not 34). Logged as a finding for the owner, not fixed by guessing at intent.

## Hole tables
Lid bolt holes: 26
Grub-screw holes: 10 (5 stations x 2 Z rows), through the outboard wall
Cable exit holes: 3, through the inboard wall

## Fuse envelopes
2 envelopes, overrun = -80.0 mm (no overrun)

## Interference table
| A | B | Intersection volume (mm3) |
|---|---|---|
| body | lid | 0 |
| body | end_plate | 0 |
| body | partition | 0 |
| body | compression_plate | 0 |
| body | fuse_0 | 0 |
| body | fuse_1 | 0 |
| body | block | 0 |
| lid | end_plate | 0 |
| lid | partition | 0 |
| lid | compression_plate | 0 |
| lid | fuse_0 | 0 |
| lid | fuse_1 | 0 |
| lid | block | 0 |
| end_plate | partition | 0 |
| end_plate | compression_plate | 0 |
| end_plate | fuse_0 | 32400.0 |
| end_plate | fuse_1 | 32400.0 |
| end_plate | block | 0 |
| partition | compression_plate | 0 |
| partition | fuse_0 | 16200.0 |
| partition | fuse_1 | 16200.0 |
| partition | block | 0 |
| compression_plate | fuse_0 | 0 |
| compression_plate | fuse_1 | 0 |
| compression_plate | block | 0 |
| fuse_0 | fuse_1 | 0 |
| fuse_0 | block | 50436.000000000015 |
| fuse_1 | block | 35977.68000000001 |

## Headroom check
needed = 165.9, internal_z = 200.0, OK

## box-shell.stl
bbox 466.0 x 306.0 x 206.0, 12 triangles, reimport is_manifold = True

## STEP round-trip checks
freecad: 7 solids, 3186335.6216923 mm3 (build123d: 7 solids, 3186335.6216923017 mm3) OK
freecad: 33 solids, 13764437.700272448 mm3 (build123d: 33 solids, 13764437.70027245 mm3) OK
