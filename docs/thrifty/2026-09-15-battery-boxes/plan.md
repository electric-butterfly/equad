# Battery boxes: cell, block, enclosure, placement, clearance — Plan

| Property | Value |
|---|---|
| Date | 2026-09-15 |
| Owner | Jeremy |
| Repo | electric-butterfly/equad |
| Tier | 2 Sub-project |
| Status | Draft |

---

## 1. Purpose

The eQuad carries its 26S2P pack as two enclosures of 26 CALB L148N58A cells, one each side of
the frame, leaning together over the propeller-shaft channel in an inverted V. Whether that volume
exists on this frame has been an open question since the fabricator first doubted it. The scan
pipeline (`docs/thrifty/2026-09-14-scan-pipeline/`) has now put the chassis on a vehicle datum with
its tube runs and mount plates fitted, so the question can be answered by geometry rather than
argument: build the cell, pattern the block, wrap it in the enclosure, place two of them on the
datum, and measure the clearance to the frame across the whole family of lean angles and offsets.

This plan delivers the parametric CAD for the battery boxes in `cad/` and the placement study
against the scanned frame. Everything is driven from one parameter file, `cad/params.toml`
(section 4.2), so that when the owner measures the inter-cell pad, tape-measures the motor, or
Sam scans the plastics, the whole chain re-runs from the new numbers with no redesign. The output
for the fabricator is STEP; the output for the owner is a self-contained HTML viewer and a
handover document.

**How to use this document.** Each work package is standalone. Open a new session, set the model and
effort the WP names, paste its starter prompt verbatim. The prompt points back here for the schema
and the rules. **One work package per session.** Never two.

**If a work package pauses** — it hit its item cap, ran short of context, or you stopped it — paste
the *same* starter prompt into a fresh session. It finds the WP's branch, reads how far the last
session got, and carries on. There is nothing to reconstruct and nothing to decide.

---

## 2. Scope

| | |
|---|---|
| **In scope** | Six scripts under `cad/` driven by `cad/params.toml`: cell and block, enclosure, vehicle assembly, clearance sweep, mount pickups, viewer and handover. STEP for one cell, the 26-cell block, one enclosure with and without cells, and the two-box vehicle assembly with a motor placeholder. A clearance sweep of the box against the datum-aligned frame mesh over lean, lateral offset, height and X station, with section renders. A table of frame primitives within reach of the chosen placement, as mount pickups. One HTML viewer and one HTML handover document for the fabricator. |
| **Out of scope** | Busbars, BMS leads, insulating covers and their routing — represented only by the headroom parameter. Bracket design — Sam's, from the pickup table. The central contactor and paralleling box, the switchgear box, the controller box, the intermediate drive. Plastics, foot boards, tank and seat base: not in the scan, so not in the sweep (section 9, owner action 5). Any Fusion work. Any edit under `pipeline/` or `docs/thrifty/2026-09-14-scan-pipeline/`. |
| **The frame is the only obstacle in this plan** | The scan is the stripped rolling chassis. The sweep measures clearance to the frame, the placeholder motor and the propeller-shaft keep-out. It says nothing about the plastics, and the report must say so in its first line. When the plastics are scanned, the same sweep re-runs with a second obstacle mesh. |
| **The chamfer is off by default** | The front column holds eight cells; the empty ninth position is the fuse bay. A chamfer on the front top edge is a parameter (`chamfer_front_top`) defaulting to 0. WP-04 reports whether a non-zero value would buy clearance. It is fabricated only if it does. |
| **Placement is a parameter set, not a decision** | Section 4.6 defines the box-local frame and the transform. The defaults in `[placement]` are a feasible point from today's sweep (section 5.5). The owner replaces them after WP-04 and before WP-05 (section 9). |
| **build123d, not Fusion** | STEP is what Sam's SolidWorks and Fusion both read. build123d 0.11.1 in `.venv-cad` builds, exports and re-imports every solid in this plan in under a second each (section 5.2), and FreeCAD 1.1.3 re-imports the STEP with identical solid count and volume (section 5.3). That re-import is the lossless read path every WP verifies against. |
| **Derived data is local and git-ignored** | Meshes and STEP files over 1 MB live under `data/cad/`, regenerable from `params.toml`. Committed artefacts are small: STEP under 1 MB, JSON, Markdown, PNG renders, and the two HTML files, the viewer capped at 8 MB. |

---

## 3. Target state

When this plan is finished:

- `cad/params.toml` holds every dimension the boxes depend on, each with its source, and every
  script reads it and nothing else.
- `cad/cell.py` builds the cell and the 26-cell block; `cad/enclosure.py` builds the enclosure with
  its lid, end plates, compression plate, fuse bay and cable exits; both export STEP that FreeCAD
  re-imports with the same solid count and volume.
- `cad/assembly.py` places two enclosures on the ISO 8855 datum by the `[placement]` parameters,
  mirrored about the symmetry plane, with the motor placeholder and the propeller-shaft keep-out,
  and writes `placement.json` with the eight corners of each box in vehicle coordinates.
- `cad/clearance.py` evaluates any placement against the frame mesh in under a second and has
  swept the grid in section 4.7, writing `sweep.json`, a feasibility table and section renders.
- `cad/mounts.py` lists every fitted frame cylinder and RANSAC plane within reach of the chosen
  placement, with its distance to the nearest box face.
- `artefacts/viewer.html` opens in a browser with no server and shows the chassis, both boxes,
  the motor and the keep-out with per-body toggles and a section plane.
- `artefacts/sam-battery-boxes.html` is the handover: what the boxes are, the parameter table,
  the placement, the clearance result, the pickups, and the open items.

**Measured baseline, 2026-09-15:**

| | count |
|---|---|
| Scripts under `cad/` | 0 |
| STEP artefacts in the repo | 0 |
| Cells per box, columns front to rear | 26 as 8 + 9 + 9 |
| Placements evaluated at X 700 (lean 0–40°, Y 200–400, Z 300–450) | 567 |
| Of those, no frame point inside the box and 10 mm clear | 216 |
| Best frame clearance found at lean 30° | 52.1 mm at Y 400, Z 450 |

---

## 4. The CAD contract — normative

### 4.1 Files and layout

```text
cad/
  README.md                 how to run each stage, which venv, in what order
  params.toml               the parameter file, section 4.2 verbatim; the only input every script reads
  common.py                 WP-01: params loading, repo root, STEP export with FreeCAD round-trip check
  cell.py                   WP-01: cell solid and 26-cell block
  enclosure.py              WP-02: enclosure, lid, internals, fuse bay, cable exits, box STEP
  assembly.py               WP-03: two boxes on the datum, motor placeholder, keep-out, placement.json
  clearance.py              WP-04: placement evaluation, sweep, section renders
  mounts.py                 WP-05: frame primitives within reach of the placed box
  viewer.py                 WP-06: builds artefacts/viewer.html
data/cad/                   git-ignored (data/ is already in .gitignore)
  assembly-full.step        WP-03: the assembly with all 52 cells
docs/thrifty/2026-09-15-battery-boxes/artefacts/
  cell.step                 WP-01
  block.step                WP-01: 26 solids
  cell-report.md            WP-01
  box.step                  WP-02: enclosure, lid and internals, no cells
  box-full.step             WP-02: enclosure with the block
  box-shell.stl             WP-02: outer shell only, box-local frame, for the sweep
  enclosure-report.md       WP-02
  assembly.step             WP-03: two enclosures, motor placeholder, keep-out, no cells
  placement.json            WP-03
  sweep.json                WP-04
  sweep-report.md           WP-04
  section-yz-default.png, section-xz-default.png, section-xy-default.png    WP-04
  section-yz-best.png, section-xz-best.png, section-xy-best.png             WP-04
  mount-pickups.json        WP-05
  mounts-report.md          WP-05
  viewer.html               WP-06
  sam-battery-boxes.html    WP-06
```

Every script is run from the repo root. `cell.py`, `enclosure.py`, `assembly.py` and `viewer.py`
run under `.venv-cad`; `clearance.py` and `mounts.py` run under `.venv-mesh`. Every script resolves
the repo root with `git rev-parse --show-toplevel`, loads `cad/params.toml` with the standard-library
`tomllib`, writes nothing outside `data/cad/` and
`docs/thrifty/2026-09-15-battery-boxes/artefacts/`, and refuses to run if an input it names is
missing. `common.py` reads `freecad_cmd` from `pipeline/config.local.toml` for the FreeCAD
round-trip check; no other script reads that file.

### 4.2 `cad/params.toml` — verbatim

Millimetres and degrees throughout. Every value carries its source in the comment. `OWNER` marks a
value the owner replaces from a measurement; until then the default stands and every artefact is
regenerated when it changes.

```toml
# Battery box parameters. Sources: CALB L148N58A supplier drawing (cell), owner design brief
# 2026-09-15 (block, enclosure, electrical), SIAECOSYS QSJ138D-90 outline drawing (motor),
# Littelfuse JLLN datasheet (fuse). OWNER = replace from a measurement; default stands until then.

[cell]                        # CALB L148N58A
width = 148.24                # X, terminal axis, drawing "W 148.24 +/- 0.15"
thickness = 26.66             # Y, drawing "T 26.66 +/- 0.15 at 70 % SOC, 100 +/- 10 kgf"
height = 102.8                # Z, body, drawing "102.8 +/- 0.3"
height_to_stud = 105.9        # Z, drawing "105.9 +/- 0.2"
stud_pitch = 110.6            # X between terminal centres, drawing "110.6 +/- 0.3"
stud_d = 10.88                # terminal pad diameter, drawing; thread size not on the drawing
pad = 3.0                     # OWNER: supplier-provided inter-cell pad, measure it. BOM says 3
swell = 1.0                   # per-cell growth allowance along Y at full charge; design assumption

[block]
columns = [8, 9, 9]           # cells per column, front to rear along X
column_pitch_x = 152.0        # 148.24 + 3.76 clearance between columns
fuse_slot = "inboard"         # the front column's empty ninth position sits at the inboard end
flip_odd = true               # every second cell in a column rotated 180 deg about Z so terminals alternate

[enclosure]
internal = [460.0, 300.0, 200.0]   # X, Y, Z clear inside dimensions
sheet = 3.0                   # OWNER: sheet thickness; 3 mm assumed
lid_face = "+Z"               # the terminal face; removable as a whole
lid_inset = 15.0              # bolt line inset from the outer edge
lid_bolt_d = 6.5              # M6 clearance
lid_bolt_pitch_max = 60.0     # bolts along every edge at no more than this pitch
end_plate = 6.0               # fixed reaction plate at the inboard end of the stack
partition = 3.0               # plate between the fuse bay and the front column's cells
compression_plate = 6.0       # floating plate at the outboard end of the stack
compression_wall = "outboard" # OWNER: wall the grub screws pass through; outboard assumed
compression_pairs = 5         # pairs of grub screws along X
compression_rows_z = [30.0, 75.0]   # the two rows, height above the floor
compression_screw_d = 8.0     # M8 grub screws
compression_travel_min = 10.0 # clear travel required between the plate and the wall
chamfer_front_top = 0.0       # leg length of a 45 deg chamfer on the front top outer edge; 0 = none

[electrical]
fuses_per_box = 2             # Littelfuse JLLN800 Class T, one per pole; BOM lists four
fuse_envelope = [90.0, 45.0, 60.0]   # X, Y, Z envelope of one fuse in its holder; OWNER: confirm.
                              # Datasheet 700-800 A row: A = 85.7, B = 56.4; the other columns did not parse
headroom = 60.0               # clear height above stud tops for busbars, nuts, cover and leads
cable_exit_face = "inboard"   # end wall carrying the power and sense exits
cable_exit_d = [20.0, 20.0, 25.0]   # two power glands and one sense gland, diameters
cable_exit_z = 160.0          # gland centre height above the floor

[placement]                   # left box; the right box is its mirror through Y = 0. Section 4.6
x = 700.0                     # box-local origin X, datum frame
y = 300.0                     # box-local origin Y, positive = left
z = 350.0                     # box-local origin Z
lean_deg = 30.0               # lid normal tilts outboard by this angle; stack axis descends outboard
clearance_min = 10.0          # a placement passes when no frame point is inside and this is clear

[sweep]                       # WP-04 grid, applied to the left box; the right box mirrors it
x = [650.0, 700.0, 750.0]
y_range = [200.0, 400.0, 25.0]      # start, stop inclusive, step
z_range = [300.0, 450.0, 25.0]
lean_range = [0.0, 40.0, 5.0]
samples = 8000                # surface samples per placement for the distance query

[motor]                       # SIAECOSYS QSJ138D-90-4000W outline drawing, owner supplied 2026-09-15
length = 258.8                # overall along the axis, drawing "258.8 +/- 2"
housing_d = 210.0             # OWNER: tape-measure the finned housing; not dimensioned on the drawing
spigot_d = 120.0              # output-end spigot, drawing "120 -0.2"
bolt_circle_d = 131.0         # drawing "131 +/- 0.2", six M8
axis = "Y"                    # cross-shaft layout; motor axis across the vehicle
centre = [320.0, 0.0, 450.0]  # placeholder: behind the boxes; WP-04 reports its own clearance

[keepout]                     # propeller shaft plus the 150 x 100 duct, along X on the centreline
axis_y = 0.0
axis_z = 340.0                # OWNER: confirm from the front differential output height
radius = 60.0
x_range = [400.0, 1200.0]

[chassis]                     # produced by the scan pipeline, local and git-ignored
mesh = "data/derived/chassis_datum_5M.stl"      # 4 021 243 faces after floor removal
mesh_1m = "data/derived/chassis_datum_1M.stl"   # for section renders
mesh_viewer = "data/derived/chassis_datum_200k.stl"
interfaces = "docs/thrifty/2026-09-14-scan-pipeline/artefacts/interfaces.json"
primitives_engine_bay = "docs/thrifty/2026-09-14-scan-pipeline/artefacts/primitives-engine-bay.json"
```

### 4.3 The cell — `cad/cell.py`

Cell-local axes: X along the cell width (terminal axis), Y through the thickness, Z from the floor
up to the terminals. The cell origin is the centre of its bottom face.

| Element | Geometry | Check |
|---|---|---|
| Body | `Box(width, thickness, height)` with its bottom face on Z = 0 | volume = 148.24 × 26.66 × 102.8 = 406 274 mm³ |
| Studs | Two cylinders, diameter `stud_d`, height `height_to_stud − height` = 3.1, on the top face at X = ± `stud_pitch` / 2, Y = 0 | one solid after union; volume 406 850 ± 10 mm³ (measured, section 5.2) |
| Bounding box | 148.24 × 26.66 × 105.9 | exact to 0.01 |

Terminal polarity is not modelled as geometry. Cell index 0 in a column has its positive stud at
−X; `flip_odd` rotates every odd-indexed cell 180° about its own Z so terminals alternate along the
column.

### 4.4 The block — `cad/cell.py`

The block is the 26 cells in the enclosure's box-local frame (section 4.5), not their own.

| Rule | Value |
|---|---|
| Column centres along X, front to rear | −`column_pitch_x`, 0, +`column_pitch_x` |
| Cell pitch along Y | `p = thickness + pad` |
| Stack origin | the inboard end: the first cell's inboard face at `y0 = −internal[1]/2 + end_plate` |
| Cell j in a 9-cell column | centre Y = `y0 + p·j + thickness/2`, j = 0…8 |
| Front column (8 cells) | the fuse bay occupies position j = 0; cells j = 1…8 sit at the same Y as the 9-cell columns' j = 1…8; a `partition` plate sits at the outboard side of the fuse bay |
| Stack length (9 cells) | `9·p − pad` |
| Fit rule, checked by the script | `end_plate + (9·p − pad) + compression_plate + compression_travel_min ≤ internal[1]`; on failure print the four numbers and exit 2 |
| Z | every cell's bottom face on Z = 0 |
| Compound | 26 solids; bounding box X = 2·152 + 148.24 = 452.24, Y = 9·p − pad, Z = 105.9 |

With `pad = 3.0`: p = 29.66, stack = 263.94, cells span Y from −144 to 119.94, and the fit rule
leaves 24.06 mm of travel. With `pad = 1.0` the stack is 248 and the travel is 40. Both pass.

### 4.5 The enclosure — `cad/enclosure.py`

Box-local frame: origin at the centre of the floor's inside face; X forward; Y the stack axis with
+Y outboard; Z toward the lid. The internal cavity is `internal`, centred in X and Y, from Z = 0 to
Z = `internal[2]`. Every wall is `sheet` thick, outside the cavity. Folded-and-welded is a
fabrication note for Sam, not a modelling constraint: model the body as one solid.

| Element | Geometry |
|---|---|
| Body | outer box `internal + 2·sheet` in X and Y, height `internal[2] + sheet`, minus the cavity, open at +Z |
| Lid | plate `internal[0] + 2·sheet` × `internal[1] + 2·sheet` × `sheet` sitting on the wall tops; bolt holes `lid_bolt_d` on a line `lid_inset` in from the outer edge, along all four edges, at the largest pitch not exceeding `lid_bolt_pitch_max` with a hole at each corner |
| Chamfer | if `chamfer_front_top` > 0: a 45° chamfer of that leg on the outer edge where the +X wall meets the lid plane, applied to the body and the lid; else none |
| End plate | `end_plate` thick, full cavity width in X, full cavity height in Z, against the inboard wall: at the defaults Y ∈ [−150, −144] |
| Partition | `partition` thick, spanning only the front column's X range (`width` wide, centred on −152), full Z, at the outboard face of the fuse bay: at the defaults Y ∈ [−144 + p − partition, −144 + p] |
| Compression plate | `compression_plate` thick, full cavity width in X, height `height_to_stud`, floating at the outboard end of the stack: Y ∈ [y_end, y_end + compression_plate] where y_end is the outboard face of the 9-cell columns' last cell; the front column needs a spacer of `p − partition` between its last cell and the plate, modelled as a separate block |
| Grub-screw holes | `compression_pairs` × 2 holes of `compression_screw_d` through the `compression_wall`, at X stations evenly spaced across the cavity width, Z at `compression_rows_z` |
| Fuse envelopes | `fuses_per_box` boxes of `fuse_envelope`, placed in the fuse bay and the headroom above it: the first with its bottom on the floor inside the fuse bay footprint, the second on top of the first; if the second's top exceeds the cavity height, report the overrun and continue |
| Cable exits | three through-holes of `cable_exit_d` in the `cable_exit_face` wall at Z = `cable_exit_z`, spaced evenly across the middle third of the wall's X extent |
| Headroom check | `height_to_stud + headroom ≤ internal[2]`; on failure print the numbers and exit 2 |
| Interference check | the block, the end plate, the partition, the compression plate, the spacer and the fuse envelopes must have zero pairwise intersection volume with each other and with the body; report every pair with its intersection volume |

Exports: `box.step` (body, lid, end plate, partition, compression plate, spacer, fuse envelopes),
`box-full.step` (the same plus the 26 cells), and `box-shell.stl` (one closed solid the size of the
outer box, with the chamfer if any, tessellated; this is the sweep body).

### 4.6 Placement — `cad/assembly.py`

The vehicle frame is the datum frame of the scan pipeline: ISO 8855, X forward, Y left, Z up,
origin on the floor plane and the symmetry plane at the rear axle housing X.

The **left box** is placed by, for every box-local point `p`:

```text
p_vehicle = [x, y, z] + R · p_local
R = | 1    0        0     |
    | 0  cos φ    sin φ   |
    | 0 −sin φ    cos φ   |        φ = lean_deg
```

Consequences the script asserts after placement: the lid normal (box-local +Z) becomes
`(0, sin φ, cos φ)` — it tilts outboard; the stack axis (box-local +Y) becomes `(0, cos φ, −sin φ)`
— it descends outboard. The floor faces down and inboard, forming the channel roof. The inboard end
of the stack is the high end, nearest the centreline: the fuse bay and cable exits sit at the top of
the inverted V.

The **right box** is the placed left box mirrored through the plane Y = 0 (`mirror(about=Plane.XZ)`
in build123d). Nothing else is computed for it.

The **motor placeholder** is a cylinder of `housing_d` and `length` with its axis along
`[motor].axis` through `[motor].centre`. The **keep-out** is a cylinder of `[keepout].radius` along X
from `x_range[0]` to `x_range[1]` through `(axis_y, axis_z)`.

`placement.json` schema:

```json
{
  "params": {"x": 700.0, "y": 300.0, "z": 350.0, "lean_deg": 30.0},
  "left": {"corners": [[0, 0, 0], "... 8 outer-shell corners"], "lid_normal": [0, 0.5, 0.866], "stack_axis": [0, 0.866, -0.5]},
  "right": {"corners": [], "lid_normal": [0, -0.5, 0.866], "stack_axis": [0, -0.866, -0.5]},
  "motor": {"centre": [320, 0, 450], "axis": "Y", "d": 210.0, "length": 258.8},
  "keepout": {"axis_y": 0.0, "axis_z": 340.0, "radius": 60.0, "x_range": [400, 1200]},
  "inboard_gap_at_floor": 0.0
}
```

`inboard_gap_at_floor` is the Y distance between the two boxes' inboard-bottom outer edges: the
channel width at its narrowest.

### 4.7 Clearance — `cad/clearance.py`

Runs under `.venv-mesh`. Loads `[chassis].mesh` into an Open3D `RaycastingScene` once. For one
placement `(x, y, z, lean)`:

| Step | Method |
|---|---|
| 1 Place | transform `box-shell.stl` by section 4.6 for the left box; mirror for the right |
| 2 Surface distance | sample `[sweep].samples` points uniformly on each box's surface; `scene.compute_distance` → `min_dist_left`, `min_dist_right` |
| 3 Frame inside the box | take chassis vertices inside each placed box's axis-aligned bounding box; build a `RaycastingScene` from the placed box; `compute_occupancy` → `inside_left`, `inside_right` (counts) |
| 4 Motor and keep-out | the same two tests for each box against the motor cylinder and the keep-out cylinder (each tessellated at 64 segments) |
| 5 Verdict | `pass` when every `inside` count is 0 and every minimum distance is at least `clearance_min` for the three box tests: frame, motor, keep-out |
| 6 Motor against the frame | computed once per run, not per placement, because the motor does not move in the sweep: `motor_frame_min` and `motor_frame_inside`, reported as their own line in `sweep-report.md` and never part of `pass` |

Controls, run first and printed, with these expected results from section 5.5:

| Control | Placement | Expect |
|---|---|---|
| Collision | (713, 300, 330, −30) | frame points inside the left box > 50 000; min distance < 1 mm |
| Clear | (700, 300, 1500, 30) | inside = 0; min distance > 200 mm |

The sweep evaluates every point of the `[sweep]` grid — 3 × 9 × 7 × 9 = 1 701 placements — and
writes `sweep.json` as a list of rows
`{x, y, z, lean, min_frame, inside_frame, min_motor, inside_motor, min_keepout, inside_keepout, pass}`,
with one top-level line for `motor_frame_min` and `motor_frame_inside` printed by the run.
`sweep-report.md` opens with the sentence "This sweep tests the frame, the placeholder motor and the
propeller-shaft keep-out only; plastics, foot boards, tank and seat are not in the scan." and then
tabulates, per X and per lean, the feasible Y and Z ranges and the best `min_frame`, names the
single best placement, states whether the `[placement]` defaults pass, and carries the motor
placeholder's own clearance to the frame as a separate line.

Section renders, for the `[placement]` defaults and for the best placement: project vertices of
`[chassis].mesh_1m` in a slab onto the section plane at 1 mm per pixel with a 100 mm grid, the axes
through the origin in red, and overlay both boxes' outer-shell edges, the motor and the keep-out in
colour. YZ section: slab X ∈ [x − 100, x + 100], viewed from the rear (+Y to the left of the image).
XZ: slab |Y| ≤ 450. XY: slab Z ∈ [150, 700]. PNG, under 500 kB each.

### 4.8 Mount pickups — `cad/mounts.py`

Runs under `.venv-mesh`. Inputs: `placement.json`, `box-shell.stl`, `[chassis].interfaces` and
`[chassis].primitives_engine_bay`. For every accepted cylinder in `interfaces.json` (all regions)
and every RANSAC plane in `primitives-engine-bay.json` with support over 1 500, compute the distance
from the primitive's point (cylinder) or centre (plane) to each placed box's shell, and keep those
under 120 mm. Write `mount-pickups.json` rows
`{id, kind, axis_or_normal, point, radius, length, support, rms, box, distance, nearest_face}`
where `nearest_face` is one of `floor, lid, inboard, outboard, front, rear`, sorted by distance.

`mounts-report.md` tabulates the rows and states the mounting concept as a fixed paragraph: two
locating pins on each box floor engaging bushes on brackets from the lower rails, and two
tensioners at the top, inboard, pulling the box down onto the pins and reached from above so their
mechanism is out of the mud. Bracket design is Sam's. The planes in the table were fitted by RANSAC
at 0.15–0.35 mm RMS but did not pass the pipeline's refinement threshold (section 5.1); each row
that is a plane carries the note "calliper before drilling".

### 4.9 Viewer and handover — `cad/viewer.py`

`viewer.html` is one file, no server, no build step. It loads exactly one external script,
`https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js` (measured reachable, section
5.6); orbit control is implemented inline (drag to rotate about the scene centre, wheel to zoom,
right-drag to pan) because the r128 examples are not on that CDN. Geometry is embedded as base64
Float32 triangle soups: the chassis decimated to 60 000 faces (2.9 MB as base64, section 5.6), both
box shells, the motor and the keep-out, tessellated from `assembly.step`. Each body has a checkbox;
a slider moves a YZ clipping plane along X. Axes triad and a 100 mm grid on the floor. File size
under 8 MB. Light background, chassis grey, boxes blue, motor orange, keep-out translucent red.

`sam-battery-boxes.html` follows the layout of
the chassis interface handover document `sam-chassis-interfaces.html` in the scan-pipeline plan's
artefacts directory (18 px base, single sheet, tables): purpose, the parameter table from `params.toml` with sources, the placement and the
transform in words, the sweep result and the best placement, the three default-placement renders
inline, the pickup table, links to the STEP files by relative path, and the open items (pad,
housing diameter, plastics scan, sheet thickness, compression wall, fuse envelope, keep-out). No
narrative about how the document was produced. Australian English.

---

## 5. Measured constraints — measured 2026-09-15

All on the owner's workstation (i7-12700KF, 31.8 GB, Windows 11, Python 3.12). Commands were run
from the repo root.

### 5.1 The frame around the engine bay, from the datum-aligned mesh

Projections of `data/derived/chassis_datum_1M.stl` vertices onto YZ (X slabs), XZ and XY at 1 mm
per pixel, and the accepted primitives in `interfaces.json`:

| | |
|---|---|
| Bay is open (no frame points) for X 450–950, Z 320–590, all Y | YZ slabs 500–700, 700–900 |
| Lower rails, along X: r 14.3–14.9 mm at Y ±188 (X 611–630, Z 281), ±170 (X 760–771), ±145 (X 824, Z 279), ±131 (X 860), ±115 (X 901), ±71 (X 971–1003, Z 274–277) | accepted cylinders with axis within 25° of X |
| Rail top surface therefore at Z ≈ 296 | 281 + 15 |
| Upper rails: r 12.9 at Y ±120–125, Z 725–731 (X 500–560); Y ±64–72, Z 772–777 (X 676–701); Y ±98–145, Z 776–777 (X 853–1092) | same |
| Upper trapezoid in the X 500–700 slab: Y ±200 at Z 600 narrowing to ±110 at Z 780 | YZ slab 500–700 |
| Front downtubes converge from Y ±100 at Z 300 up to the front differential, X 900–1100 | YZ slab 900–1100 |
| Front differential output stub: a circle at Y ≈ +30, Z ≈ 350 in the X 900–1100 slab | same render; `[keepout].axis_z` default 340 derives from it and is an owner check |
| Rear cross-member on the floor: r 13.1 along Y at X 508, Z 284, length 372 | `engine-bay/cyl/013`, `cyl/029` |
| Engine-mount planes: normal Y at (454, +204, 362) support 14 975 rms 0.34 and (434, −206, 369) support 6 759 rms 0.30; normal Z at (643, −200, 300) support 5 446 rms 0.27 and (645, +199, 299) support 5 085 rms 0.18 | `primitives-engine-bay.json`, planes by support |
| Plane rows in `interfaces.json`: 123 in the engine bay, all `accepted: false` with refined rms 0.9–1.5 mm against the 0.5 mm threshold | `interfaces.json` |

**Rules that follow:**

1. Mount pickups come from the RANSAC plane table, not from `interfaces.json` planes, and every
   plane row says "calliper before drilling".
2. The keep-out height is an owner check, not a fact; the default is the render's reading.

### 5.2 build123d in `.venv-cad`

`.venv-cad` at the repo root imports build123d 0.11.1 (built this day from
`pipeline/requirements-cad.txt` with `python -m venv .venv-cad` then `pip install -r`).

| Operation | Time |
|---|---|
| `from build123d import *` | 3.0 s |
| Cell: box plus two stud cylinders | volume 406 850 mm³, bbox 148.24 × 26.66 × 105.9 |
| 26 cells as a `Compound` of moved copies | 0.0 s, bbox 452.24 × 247.94 × 105.9 at pitch 27.66 |
| Enclosure shell 466 × 306 × 203 minus cavity | 0.1 s, volume 1 208 988 mm³ |
| `export_step` cell, enclosure, and a 28-solid assembly | 0.1 s total; 23 437, 29 267 and 700 178 bytes |
| `export_gltf(binary=True)` of the assembly | 921 584 bytes |
| `import_step` of the assembly | 0.1 s, volume 12 214 878 mm³ |
| Whole spike script end to end | 3.9 s |

**Rules that follow:**

1. STEP files with the 26 cells are around 0.7 MB; the two-box assembly without cells is small.
   `assembly-full.step` (52 cells) goes to `data/cad/`; everything else in section 4.1 is committed.
2. No CAD item takes more than seconds. Budget is context, not wall clock.

### 5.3 FreeCAD as the lossless read path

`freecadcmd.exe` from `pipeline/config.local.toml` (`freecad_cmd`), on the same assembly STEP:

| | |
|---|---|
| `Part.read(step)`: solids, volume | 28 solids, 12 214 878 mm³, 0.66 s |
| build123d's own count and volume | 28 solids, 12 214 878 mm³ |

**Rules that follow:**

1. Every STEP export is verified by FreeCAD re-import: same solid count, volume within 0.01 %.
   `common.py` implements it once; every WP calls it and prints both numbers.

### 5.4 Chassis mesh state

| | |
|---|---|
| `data/derived/chassis_datum_5M.stl` | 4 021 243 triangles, 12 062 993 vertices as read by Open3D (the 5 M decimation, floor removed); 201 MB |
| `data/derived/chassis_datum_1M.stl` | 41 MB; 2 471 967 vertices as read by trimesh |
| `data/derived/chassis_datum_200k.stl` | 207 461 triangles, 10.4 MB |
| `.venv-mesh` at the repo root | imports open3d 0.19.0 and trimesh 5.1.0 |

**Rules that follow:**

1. The sweep body count is 4 021 243 faces; a script that asserts "5 000 000" fails.
2. Both venvs at the repo root work. Do not create venvs elsewhere.

### 5.5 Clearance evaluation and the sweep

Open3D `RaycastingScene` on `chassis_datum_5M.stl`; box outer shell 466 × 306 × 206; the transform
of section 4.6.

| | |
|---|---|
| Read the 5 M mesh and build the BVH | 5.8 s |
| 20 000 surface samples, `compute_distance` | 1.15 s first call, then under 0.1 s |
| Occupancy of the chassis vertices inside the placed box's bounding box | 0.01 s |
| Control, collision (713, 300, 330, lean −30) | 70 550 chassis points inside the box; min distance 0.01 mm |
| Control, clear (700, 300, 1500, lean 30) | 0 inside; min distance 233.9 mm |
| Sweep: 567 placements at X 700, lean 0–40 step 5, Y 200–400 step 25, Z 300–450 step 25, 8 000 samples | 122.9 s |
| Feasible (0 inside, ≥ 10 mm): 216 of 567 | |
| Lean 0: Y 375–400 · lean 15: Y 325–400 · lean 30: Y 275–400 · lean 40: Y 275–400; Z 300–450 feasible at every lean | |
| Best frame clearance: lean 10, Y 400, Z 450, 61.5 mm; lean 30 best 52.1 mm at Y 400, Z 450 | |

**Rules that follow:**

1. The full grid of section 4.7 (1 701 placements) costs about 6.5 minutes. Run it once as one
   item, in the foreground, with a 15-minute timeout.
2. The bare frame admits every lean from 0 to 40°. The report must say so and must say that the
   plastics are the missing constraint; a session must not present the frame result as a fit.
3. `[placement]` defaults (700, 300, 350, 30) lie inside the feasible set at 10 mm.

### 5.6 Viewer assets

| | |
|---|---|
| `https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js` | HTTP 200, 603 445 bytes |
| `https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/examples/js/controls/OrbitControls.js` and the matching `STLLoader.js` | HTTP 404 — not on that CDN |
| Decimate the 200 k mesh to 100 000 faces (Open3D quadric) | 1.0 s; Float32 soup 3.6 MB; base64 4.8 MB |
| Decimate to 60 000 faces | 1.1 s; 2.2 MB; base64 2.9 MB |

**Rules that follow:**

1. Orbit control is written inline. No second CDN script.
2. The viewer embeds the 60 000-face chassis and stays under 8 MB.

### 5.7 Electrical parts from the BOM and datasheets

| | |
|---|---|
| Cells purchased | 60 (52 fitted, 8 spare); "1C – 8C 10 s"; pack 26S2P, 96.2 V nominal, 113.1 V max | EB-Quad BOM sheet |
| Fuses | 4 × Littelfuse JLLN800 Class T with holders; datasheet DC rating 125 V for 70–1 200 A; 700–800 A dimension row A = 85.7 mm, B = 56.4 mm | BOM; datasheet page 2 and the dimension table |
| Contactors | 4 × TE LEV200, 500 A, bottom mount, M8 terminals — central box, not in the battery boxes | BOM; TE datasheet |
| BMS | ANT 21–30S — central, sense leads from each box | BOM |
| Motor | BOM lists "QS138 90H V1 (QSD138A-90)"; the outline drawing supplied is SIAECOSYS QSJ138D-90-4000W: 258.8 long, 131 bolt circle, 120 spigot, Ø20 spline; housing diameter not dimensioned in the visible text | BOM; drawing |

**Rules that follow:**

1. Two fuse envelopes per box. Their size is the parameter; the owner confirms it with the holder in
   hand.
2. The motor housing diameter is a placeholder until measured.

### 5.8 Per-item cost — what sets every item cap

An item is one script function or stage: write or adapt it, run it, read its output, record the
result. Measured on this session's own spikes:

| | |
|---|---|
| Script per item (`wc -c` on the CAD spike) | 2 263 bytes, about 570 tokens |
| Run output per item | 15–25 lines, about 250 tokens; the sweep summary about 600 |
| Status and batch report per item | about 500 tokens |
| Reasoning allowance | 2 000 tokens |
| Measured cost of one item | 4 000 tokens |
| Working budget (half a 200 k window) | 100 000 tokens |
| **Item cap per session** | **25** |

**Rules that follow:**

1. No work package exceeds 25 items. Every WP below has 12 or fewer.
2. Reaching the cap is a normal ending: `state: paused`, `resume-from` set, and the same starter
   prompt resumes it.
3. Never read a STEP file, a sweep JSON or a mesh into context. Read counts, the first twenty rows,
   and the script's own summary lines.

---

## 6. Execution rules — every work package obeys these

<!-- Copied verbatim from cau-thrifty/references/execute.md. Edit there first. -->

**1. One work package per session. Never two.**
Finishing early is not a reason to start the next one. The next WP may depend on yours being
reviewed first, and you cannot see the review.

**2. Canary first.** Apply the change to exactly one item. Stop. Report what the write returned.
Wait for the go-ahead. A systematic mistake caught on item one costs one item; caught at the end it
costs the whole set, and the rollback is harder than the work was.

**3. Operate on an explicit list, never a live query.** Your target set comes from the prompt or
from a file the prompt names. A live query can return something different on the second call —
someone else's edit, a new item, a changed status — and a set that moves underneath you means your
verification proves nothing.

**4. Verify by comparison against a path proven lossless.** Read back through a route the plan has
demonstrated to be faithful and compare byte for byte. Never verify through a path whose fidelity
you have not seen proven, and never read a result out of a write or transition response echo —
those are frequently rendered through a converter that is not the storage format.

**5. Serial calls wherever a rate limit is shared.** Most estate-wide limits are global, not
per-session. Parallel calls buy nothing and trip the limit for everyone.

**6. Batch size about ten. Report after each batch, and checkpoint the branch.** Small enough that
a defect is bounded, big enough that the reporting is not the work. The checkpoint — status file
updated, committed, pushed — is what makes the session restartable. Work that exists only inside
your session is work nobody else can recover.

**7. Out-of-scope findings are documented, not acted on.**
This is the single most important anti-wandering control. You *will* find real problems outside your
scope — that is what happens when a careful reader looks at a system. Fixing one is how a session
that was going to take twenty minutes takes three hours and produces a diff nobody asked for and
nobody can review. Append a row to your findings file, then carry on with your own scope. The owner
triages findings. You do not.

**8. Artefacts chain through merged PRs.** If your WP consumes something an earlier WP produced and
it is not in your working tree, that PR has not merged. Say so and stop. Do not reconstruct it.

**9. One branch, named by the plan. One PR, opened once, at the end.**
Your branch is `thrifty/<plan-dir>/wp-NN` — **derived, never invented**, so that a later session can
find it without being told. Cut it from `origin/main`, push a start commit before you touch
anything, checkpoint after each batch, and open exactly one PR when the WP reaches a terminal state.
**Never commit to `main`.** Never add commits to a PR that is already open. The owner merges.

**10. Check your inputs exist before doing anything.** If the plan file or a named input artefact is
missing from the working tree, the prerequisite PR has not merged. Say so and stop. Do not
improvise a substitute.

**11. Stay inside your context budget — pause, do not die.** Read narrowly: the named sections, a
line range, a grep. Never a whole file you need six lines of, and never the same thing twice. Your
prompt names a **hard item cap**; when you reach it, or when context is running short, or when the
owner pauses you, write `state: paused` with the next item in `resume-from`, checkpoint, and stop.
A session that runs to the wall leaves half-applied work and no record of where it stopped, and
reconstructing that costs more than the sweep ever did.

### The branch protocol — start, checkpoint, resume, publish

Each WP works on one branch, and its name is derived from this plan, never invented:

```text
thrifty/2026-09-14-scan-pipeline/wp-NN
```

**Start.** After the preconditions pass and before touching anything: `git fetch origin`, then test
`git ls-remote --exit-code --heads origin thrifty/2026-09-14-scan-pipeline/wp-NN`. A missing branch
means a fresh start. Cut it from `origin/main`. Write
`docs/thrifty/2026-09-14-scan-pipeline/status/WP-NN.md` with `state: started`. Commit and push.
**Do not open a PR yet.** That commit only stakes the branch so a dead session is still findable;
the PR comes once, at Publish, below. An existing branch means a **resume**: check it out, read that
status file, and carry on from its `resume-from`. Never commit to `main`.

**Checkpoint.** After each batch: update the status file (`progress`, `resume-from`, `updated`),
commit, push. Same branch, no PR yet.

**Publish.**

| Ending | What the session does |
|---|---|
| **The plan file itself is missing** | Report it in the session and stop. There is nowhere to write: if the plan has not merged, `docs/thrifty/2026-09-14-scan-pipeline/` does not exist either |
| **`paused`** — hard cap reached, context running short, or the owner paused the session | Checkpoint and stop. Do not open a PR yet - that is the job of the session that resumes this work package and finishes it |
| **Every terminal ending** — `done`, `blocked`, `stopped`, or `canary-waiting` and never answered | Commit the status file carrying the state actually reached, push, open **one** PR, stop |

A canary pause is not an ending — the owner is in the session. Every WP writes
`docs/thrifty/2026-09-14-scan-pipeline/status/WP-NN.md`, including one that produces nothing else.
It records the session's derived **branch**, never a PR URL: a session cannot know its PR number
before it commits. `started`, `in-progress` and `paused` live on the branch; only a terminal state
ends in a PR. Full schema, all eight states and the required fields per state:
`cau-thrifty/references/execute.md`.

Status file front matter, for reference:

```markdown
---
wp: 3
plan: 2026-09-14-scan-pipeline
state: paused
model: sonnet
effort: medium
branch: thrifty/2026-09-14-scan-pipeline/wp-03
progress: 6/11
resume-from: step-7-symmetry
pause-reason: context
updated: 2026-09-15
---

## Done-when evidence
<the command or query, and its actual output>

## Notes
<anything the owner needs>
```

---
## 7. Out-of-scope findings

A session that finds a real problem outside its WP scope **must not fix it**. It appends a row to
`docs/thrifty/2026-09-15-battery-boxes/findings/WP-NN.md` — its own file, never a shared one — and
carries on:

```markdown
| WP | Where | What was found | Evidence | Suggested owner |
|----|-------|----------------|----------|-----------------|
```

Findings are triaged by the owner, not by the finding session.

---

## 8. Work packages

**Order:** 1 -> 2 -> 3 -> 4 -> owner sets `[placement]` -> 5 -> 6. Strictly sequential: every WP
consumes the previous one's committed artefact.

**Precondition — this plan must be merged to `main` before WP1 starts.** Every starter prompt
resolves the repo root of `electric-butterfly/equad` for itself and opens by reading this file from
it. Until the plan is on `main`, that path does not exist and every session stops at step one.

**The WPs chain through committed artefacts, so each PR must merge before its dependants run:**

| Artefact | Produced by | Consumed by |
|---|---|---|
| `cad/params.toml` | WP1 | WP2, WP3, WP4, WP5, WP6 |
| `cad/common.py` | WP1 | WP2, WP3, WP4, WP5, WP6 |
| `cad/README.md` | WP1 | WP2, WP3, WP4, WP5, WP6 |
| `cad/cell.py` | WP1 | WP2, WP6 |
| `docs/thrifty/2026-09-15-battery-boxes/artefacts/cell.step` | WP1 | WP6 |
| `docs/thrifty/2026-09-15-battery-boxes/artefacts/block.step` | WP1 | WP6 |
| `docs/thrifty/2026-09-15-battery-boxes/artefacts/cell-report.md` | WP1 | WP6 |
| `cad/enclosure.py` | WP2 | WP3, WP6 |
| `docs/thrifty/2026-09-15-battery-boxes/artefacts/box.step` | WP2 | WP6 |
| `docs/thrifty/2026-09-15-battery-boxes/artefacts/box-full.step` | WP2 | WP6 |
| `docs/thrifty/2026-09-15-battery-boxes/artefacts/box-shell.stl` | WP2 | WP3, WP4, WP5 |
| `docs/thrifty/2026-09-15-battery-boxes/artefacts/enclosure-report.md` | WP2 | WP6 |
| `cad/assembly.py` | WP3 | WP5 |
| `docs/thrifty/2026-09-15-battery-boxes/artefacts/assembly.step` | WP3 | WP5, WP6 |
| `docs/thrifty/2026-09-15-battery-boxes/artefacts/placement.json` | WP3 | WP4, WP5, WP6 |
| `data/cad/assembly-full.step` | WP3 (local, git-ignored) | owner |
| `cad/clearance.py` | WP4 | owner |
| `docs/thrifty/2026-09-15-battery-boxes/artefacts/sweep.json` | WP4 | WP6 |
| `docs/thrifty/2026-09-15-battery-boxes/artefacts/sweep-report.md` | WP4 | owner (placement decision), WP5, WP6 |
| `docs/thrifty/2026-09-15-battery-boxes/artefacts/section-yz-default.png` | WP4 | WP6 |
| `docs/thrifty/2026-09-15-battery-boxes/artefacts/section-xz-default.png` | WP4 | WP6 |
| `docs/thrifty/2026-09-15-battery-boxes/artefacts/section-xy-default.png` | WP4 | WP6 |
| `docs/thrifty/2026-09-15-battery-boxes/artefacts/section-yz-best.png` | WP4 | owner |
| `docs/thrifty/2026-09-15-battery-boxes/artefacts/section-xz-best.png` | WP4 | owner |
| `docs/thrifty/2026-09-15-battery-boxes/artefacts/section-xy-best.png` | WP4 | owner |
| `cad/params.toml `[placement]` revised` | owner, after WP4 | WP5, WP6 |
| `cad/mounts.py` | WP5 | owner |
| `docs/thrifty/2026-09-15-battery-boxes/artefacts/mount-pickups.json` | WP5 | WP6 |
| `docs/thrifty/2026-09-15-battery-boxes/artefacts/mounts-report.md` | WP5 | WP6 |
| `cad/viewer.py` | WP6 | owner |
| `docs/thrifty/2026-09-15-battery-boxes/artefacts/viewer.html` | WP6 | owner |
| `docs/thrifty/2026-09-15-battery-boxes/artefacts/sam-battery-boxes.html` | WP6 | owner, Sam |

| WP | Title | Model | Effort | Item cap | Depends on | Writes |
|---|---|---|---|---|---|---|
| 1 | Parameters, common, cell and block | Sonnet | low | 25 (9 items) | — | `cad/params.toml`, `cad/common.py`, `cad/cell.py`, `cad/README.md`, three artefacts |
| 2 | Enclosure | Sonnet | medium | 25 (12 items) | WP1 | `cad/enclosure.py`, four artefacts |
| 3 | Vehicle assembly | Sonnet | low | 25 (8 items) | WP2 | `cad/assembly.py`, two artefacts, one local file |
| 4 | Clearance sweep and renders | Sonnet | medium | 25 (11 items) | WP3 | `cad/clearance.py`, eight artefacts |
| 5 | Mount pickups | Sonnet | medium | 25 (7 items) | WP4 and the owner's placement | `cad/mounts.py`, two artefacts |
| 6 | Viewer and handover | Sonnet | medium | 25 (10 items) | WP5 | `cad/viewer.py`, two artefacts |

---

### WP1 — Write the parameters, the common module, the cell and the block

**Model:** Sonnet · **Effort:** low · **Item cap:** 25 (this WP has 9 items) ·
**Branch:** `thrifty/2026-09-15-battery-boxes/wp-01` · **Writes:** `cad/params.toml`,
`cad/common.py`, `cad/cell.py`, `cad/README.md`, `artefacts/cell.step`, `artefacts/block.step`,
`artefacts/cell-report.md`

**Goal.** Put the parameter file and the shared helpers in place, build the cell and the 26-cell
block from them, and prove the STEP round trip through FreeCAD.

**Done when.** `.venv-cad/Scripts/python cad/cell.py` prints the cell volume within 10 mm³ of
406 850, the block bounding box `452.24 x 263.94 x 105.9` (at pad 3.0), and for each of the two
STEP files a line `freecad: N solids, V mm3 (build123d: N solids, V mm3) OK` with N = 1 and N = 26;
`cell-report.md` exists with the 26-row position table; `git diff --stat origin/main` shows only
the files this WP writes.

```
WP-01 of the battery-boxes plan: parameters, common module, cell and block.
Repo: electric-butterfly/equad. Work from the root of your local clone - find it, do not
assume a path. Make NO writes outside this repo.

PRECONDITION 1 - right tree. Run `git rev-parse --show-toplevel` and
`git remote get-url origin`. origin must be electric-butterfly/equad, and every path
below is relative to the toplevel the first command printed. If origin names a
different repo, or git errors because this is not a work tree, say so and STOP,
and ask the owner to repoint the session. Do not clone it, do not search the
filesystem for a copy, do not guess a path. Write nothing.

PRECONDITION 2 - plan present. Confirm docs/thrifty/2026-09-15-battery-boxes/plan.md
exists in that tree. If it does not, the plan PR has not merged - say so and STOP.
Write nothing: the directory you would write to does not exist either. Do not
improvise a substitute.

PRECONDITION 3 - tools. Confirm pipeline/config.local.toml exists and names
freecad_cmd, and that `.venv-cad/Scripts/python -c "import build123d"` succeeds. If
the venv import fails, rebuild it in place - it is git-ignored and the plan allows
this: `python -m venv .venv-cad` then
`.venv-cad/Scripts/python -m pip install -r pipeline/requirements-cad.txt`, then
retry the import. If config.local.toml is missing, write
docs/thrifty/2026-09-15-battery-boxes/status/WP-01.md with state: blocked and the
absent path in Notes, commit, push, open one PR, and STOP.

BRANCH. Your branch is thrifty/2026-09-15-battery-boxes/wp-01 - derived from the
plan, never invented. Before touching anything:
  git fetch origin
  git ls-remote --exit-code --heads origin thrifty/2026-09-15-battery-boxes/wp-01
A missing branch means a fresh start. Cut it from origin/main:
  git switch -c thrifty/2026-09-15-battery-boxes/wp-01 origin/main
Write docs/thrifty/2026-09-15-battery-boxes/status/WP-01.md with state: started.
Commit it ("chore(thrifty): WP-01 start") and push -u. Do NOT open a PR yet. That
commit only stakes the branch so a dead session is still findable. The PR comes
once, at the very end of this prompt.
An existing branch means a RESUME, not a new start. Check it out:
  git switch -c thrifty/2026-09-15-battery-boxes/wp-01 origin/thrifty/2026-09-15-battery-boxes/wp-01
Read that status file and carry on from its resume-from, setting state:
in-progress. Do not start over and do not re-apply what is already done.
Never commit to main.

THEN read docs/thrifty/2026-09-15-battery-boxes/plan.md sections 4.1, 4.2, 4.3, 4.4,
5.2, 5.3, 5.8 and 6. Section 4.2 is the parameter file, to be written verbatim.

Load: ToolSearch query "select:Read,Write,Edit,Bash,Grep"

Do NOT load or call WebSearch or WebFetch. Every number in this WP comes from section
4.2; a web figure that disagrees with it is a finding, not a correction.
Do NOT load or call the Agent tool. Nine sequential items need one session; a
subagent cannot see the FreeCAD output you must report.

TASK. Write the files below, in this order, running each script as you go.
Hard cap: 25 items this session. 25 is the measured budget from section 5.8, not a
target - reaching it is a normal ending, not a failure.
  1. cad/params.toml - the section 4.2 block, byte for byte, nothing added.
  2. cad/common.py - repo_root() via `git rev-parse --show-toplevel`; load_params()
     reading cad/params.toml with tomllib; artefacts_dir() returning
     docs/thrifty/2026-09-15-battery-boxes/artefacts (created if absent);
     freecad_cmd() from pipeline/config.local.toml; export_step(shape, path)
     that exports and then runs freecad_check(path) -> (n_solids, volume) by
     invoking freecad_cmd with `-c "import Part; s=Part.read(r'<path>');
     print(len(s.Solids), s.Volume)"` and parsing the last line; and
     check_step(shape, path) that compares FreeCAD's count and volume with
     build123d's (shape.solids() count and shape.volume), prints
     `freecad: N solids, V mm3 (build123d: N solids, V mm3) OK|FAIL`, and raises on
     FAIL or on a volume mismatch over 0.01 %.
  3. cad/README.md - the venv per script, the run order, and one line per script.
  4. cad/cell.py: cell() per section 4.3. Print the volume and bounding box.
     Export artefacts/cell.step through check_step. THIS IS THE CANARY.
  5. cad/cell.py: block() per section 4.4 - 26 cells positioned in the box-local
     frame, flip_odd applied, the fit rule checked (exit 2 with the four numbers
     on failure). Print the bounding box and the count.
  6. Export artefacts/block.step through check_step (expect 26 solids).
  7. cad/cell.py --report writes artefacts/cell-report.md: the [cell] and [block]
     parameters with sources, a 26-row table (column, index, centre X Y Z,
     flipped), the bounding boxes, the fit-rule numbers, and both check_step lines
     verbatim.
  8. Run cad/cell.py twice more with pad = 1.0 and pad = 5.0 edited in a scratch
     copy of params.toml passed via --params <file>; report the block Y span and
     the travel each time; leave cad/params.toml at pad = 3.0.
  9. Confirm `git status --short` lists only the files this WP writes plus the
     status file.

PROCEDURE:
1. Write items 1-3 (setup files, no run). Report their sizes.
2. CANARY = item 4 only. Stop. Show the printed volume, the bounding box and the
   check_step line. Wait for the go-ahead.
3. Then items 5-9 as one batch. After the batch: report, update the status file
   (progress, resume-from, updated), commit, push. Serial calls only. No PR yet.
4. If you hit the hard cap, or context runs short, or the owner pauses you: write
   state: paused with resume-from and pause-reason, commit, push, and STOP. Do
   NOT open a PR yet - that is the job of the session that resumes this prompt.

VERIFY BEFORE FINISHING:
  .venv-cad/Scripts/python cad/cell.py   -> cell volume within 10 of 406850;
     block bbox 452.24 x 263.94 x 105.9; two lines ending in OK with 1 and 26 solids
  ls docs/thrifty/2026-09-15-battery-boxes/artefacts/   -> cell.step, block.step,
     cell-report.md present; block.step under 1 MB
  grep -c "^| " docs/thrifty/2026-09-15-battery-boxes/artefacts/cell-report.md
     -> at least 28 (26 rows plus header lines)
Report the numbers. If any does not match, say so and do not claim completion.

SCOPE FENCE. You may write cad/params.toml, cad/common.py, cad/cell.py,
cad/README.md, the three artefacts named above, and your own status and findings
files. Do NOT change any value in section 4.2 - if a number looks wrong, it is a
finding. Do NOT touch pipeline/, docs/thrifty/2026-09-14-scan-pipeline/, README.md,
.gitignore, or requirements files. Do NOT create a venv anywhere but .venv-cad at
the repo root. Out-of-scope observations go in
docs/thrifty/2026-09-15-battery-boxes/findings/WP-01.md, not into an action.

STOP CONDITION: when every item in your list has been handled once, or the hard
cap is reached. Do not look for more work.

Write docs/thrifty/2026-09-15-battery-boxes/status/WP-01.md per section 6 of the
plan. On a terminal state - done, blocked, stopped, or canary-waiting - commit to
your branch cut from origin/main, push it, and open one PR. Then STOP - the owner
merges. Do NOT add commits to a PR that is already open.
```

---

### WP2 — Build the enclosure

**Model:** Sonnet · **Effort:** medium · **Item cap:** 25 (this WP has 12 items) ·
**Branch:** `thrifty/2026-09-15-battery-boxes/wp-02` · **Writes:** `cad/enclosure.py`,
`artefacts/box.step`, `artefacts/box-full.step`, `artefacts/box-shell.stl`,
`artefacts/enclosure-report.md`

**Goal.** Model the sheet enclosure, its lid, the internal plates, the fuse bay and the cable
exits around the block from WP1, prove there is no interference, and export the three files the
later WPs consume.

**Done when.** `.venv-cad/Scripts/python cad/enclosure.py` prints the headroom and fit-rule
numbers, an interference table whose every intersection volume is 0.0, and two `check_step` lines
ending in OK (box.step with 8 solids at the default parameters: body, lid, end plate, partition,
compression plate, spacer and two fuse envelopes; box-full.step with 8 + 26 = 34);
`box-shell.stl` is one closed mesh whose bounding box is
`466 x 306 x 206`; `enclosure-report.md` exists.

```
WP-02 of the battery-boxes plan: the enclosure.
Repo: electric-butterfly/equad. Work from the root of your local clone - find it, do not
assume a path. Make NO writes outside this repo.

PRECONDITION 1 - right tree. Run `git rev-parse --show-toplevel` and
`git remote get-url origin`. origin must be electric-butterfly/equad, and every path
below is relative to the toplevel the first command printed. If origin names a
different repo, or git errors because this is not a work tree, say so and STOP,
and ask the owner to repoint the session. Do not clone it, do not search the
filesystem for a copy, do not guess a path. Write nothing.

PRECONDITION 2 - plan present. Confirm docs/thrifty/2026-09-15-battery-boxes/plan.md
exists in that tree. If it does not, the plan PR has not merged - say so and STOP.
Write nothing: the directory you would write to does not exist either. Do not
improvise a substitute.

PRECONDITION 3 - inputs. Confirm cad/params.toml, cad/common.py, cad/cell.py and
docs/thrifty/2026-09-15-battery-boxes/artefacts/block.step exist. If any does not,
WP-01's PR has not merged. Write
docs/thrifty/2026-09-15-battery-boxes/status/WP-02.md with state: blocked and the
absent path in Notes, commit, push, open one PR, and STOP. Do not reconstruct it.
Confirm `.venv-cad/Scripts/python -c "import build123d"` succeeds; if not, rebuild
the venv as cad/README.md describes.

BRANCH. Your branch is thrifty/2026-09-15-battery-boxes/wp-02 - derived from the
plan, never invented. Before touching anything:
  git fetch origin
  git ls-remote --exit-code --heads origin thrifty/2026-09-15-battery-boxes/wp-02
A missing branch means a fresh start. Cut it from origin/main:
  git switch -c thrifty/2026-09-15-battery-boxes/wp-02 origin/main
Write docs/thrifty/2026-09-15-battery-boxes/status/WP-02.md with state: started.
Commit it ("chore(thrifty): WP-02 start") and push -u. Do NOT open a PR yet. That
commit only stakes the branch so a dead session is still findable. The PR comes
once, at the very end of this prompt.
An existing branch means a RESUME, not a new start. Check it out:
  git switch -c thrifty/2026-09-15-battery-boxes/wp-02 origin/thrifty/2026-09-15-battery-boxes/wp-02
Read that status file and carry on from its resume-from, setting state:
in-progress. Do not start over and do not re-apply what is already done.
Never commit to main.

THEN read docs/thrifty/2026-09-15-battery-boxes/plan.md sections 4.1, 4.2, 4.4, 4.5,
5.2, 5.3, 5.8 and 6, and cad/README.md.

Load: ToolSearch query "select:Read,Write,Edit,Bash,Grep"

Do NOT load or call WebSearch or WebFetch. Every dimension is in cad/params.toml;
sheet-metal practice you look up is not this plan's contract.
Do NOT load or call the Agent tool. The interference table must be read by the
session that reports it.

TASK. Write cad/enclosure.py per section 4.5 and run it, one element per item.
Hard cap: 25 items this session. 25 is the measured budget from section 5.8, not a
target - reaching it is a normal ending, not a failure.
  1. Body: outer box minus cavity, open at +Z. Print volume. THIS IS THE CANARY.
  2. Lid with bolt holes per the pitch rule; print the hole count per edge.
  3. Chamfer branch: implement it, run once with chamfer_front_top = 20.0 through
     --params on a scratch copy to prove it builds, then run with the committed
     value 0.0. Report both volumes.
  4. End plate and partition.
  5. Compression plate and the front-column spacer; grub-screw holes through the
     compression_wall.
  6. Fuse envelopes in the fuse bay; report whether the second overruns the cavity.
  7. Cable exits.
  8. Headroom check and fit rule; interference table over every pair (use
     build123d intersect and print the volume of each result).
  9. Export artefacts/box.step through check_step.
 10. Import the block from cad/cell.py (call block(), do not re-read block.step)
     and export artefacts/box-full.step through check_step.
 11. Export artefacts/box-shell.stl: a single solid box the size of the outer
     shell (with the chamfer if any), tessellated; print its bounding box and
     confirm it is watertight (trimesh is not in .venv-cad; count faces and check
     the STL loads back with build123d import_stl and reports a closed shell).
 12. cad/enclosure.py --report writes artefacts/enclosure-report.md: parameters
     used, the Y layout table (end plate, fuse bay, partition, cells, spacer,
     compression plate, travel), hole tables, the interference table, the fuse
     overrun line, and both check_step lines verbatim.

PROCEDURE:
1. Write the file skeleton (params, imports, main with --params and --report).
2. CANARY = item 1 only. Stop. Show the printed body volume and the outer
   dimensions. Wait for the go-ahead.
3. Then items 2-12 in batches of about six. After each batch: report, update the
   status file (progress, resume-from, updated), commit, push. Serial calls only.
   No PR yet.
4. If you hit the hard cap, or context runs short, or the owner pauses you: write
   state: paused with resume-from and pause-reason, commit, push, and STOP. Do
   NOT open a PR yet - that is the job of the session that resumes this prompt.

VERIFY BEFORE FINISHING:
  .venv-cad/Scripts/python cad/enclosure.py   -> every interference volume 0.0;
     check_step OK with 8 solids (box.step) and 34 solids (box-full.step)
  bounding box of artefacts/box-shell.stl   -> 466 x 306 x 206 within 0.01
  ls -la docs/thrifty/2026-09-15-battery-boxes/artefacts/   -> box.step, box-full.step
     (under 1 MB), box-shell.stl, enclosure-report.md present
Report the numbers. If any does not match, say so and do not claim completion.

SCOPE FENCE. You may write cad/enclosure.py, the four artefacts named above, and
your own status and findings files. Do NOT edit cad/params.toml, cad/common.py or
cad/cell.py - if one of them needs a change to make this WP work, record it as a
finding with the exact line and STOP with state: blocked. Do NOT touch pipeline/
or docs/thrifty/2026-09-14-scan-pipeline/. Out-of-scope observations go in
docs/thrifty/2026-09-15-battery-boxes/findings/WP-02.md, not into an action.

STOP CONDITION: when every item in your list has been handled once, or the hard
cap is reached. Do not look for more work.

Write docs/thrifty/2026-09-15-battery-boxes/status/WP-02.md per section 6 of the
plan. On a terminal state - done, blocked, stopped, or canary-waiting - commit to
your branch cut from origin/main, push it, and open one PR. Then STOP - the owner
merges. Do NOT add commits to a PR that is already open.
```

---

### WP3 — Place two boxes on the vehicle datum

**Model:** Sonnet · **Effort:** low · **Item cap:** 25 (this WP has 8 items) ·
**Branch:** `thrifty/2026-09-15-battery-boxes/wp-03` · **Writes:** `cad/assembly.py`,
`artefacts/assembly.step`, `artefacts/placement.json`, `data/cad/assembly-full.step` (local,
git-ignored)

**Goal.** Apply the section 4.6 transform to the enclosure, mirror it, add the motor placeholder
and the keep-out, and write the placement record every later WP reads.

**Done when.** `.venv-cad/Scripts/python cad/assembly.py` prints the left lid normal within 0.001
of `(0, 0.5, 0.866)` and stack axis within 0.001 of `(0, 0.866, -0.5)` at the default lean of 30°,
a `check_step` OK line for `assembly.step` with 4 solids (two shells, motor, keep-out) and one for
`data/cad/assembly-full.step` with 4 + 52 solids, and `placement.json` validates against the
section 4.6 schema with eight corners per box.

```
WP-03 of the battery-boxes plan: the vehicle assembly.
Repo: electric-butterfly/equad. Work from the root of your local clone - find it, do not
assume a path. Make NO writes outside this repo.

PRECONDITION 1 - right tree. Run `git rev-parse --show-toplevel` and
`git remote get-url origin`. origin must be electric-butterfly/equad, and every path
below is relative to the toplevel the first command printed. If origin names a
different repo, or git errors because this is not a work tree, say so and STOP,
and ask the owner to repoint the session. Do not clone it, do not search the
filesystem for a copy, do not guess a path. Write nothing.

PRECONDITION 2 - plan present. Confirm docs/thrifty/2026-09-15-battery-boxes/plan.md
exists in that tree. If it does not, the plan PR has not merged - say so and STOP.
Write nothing: the directory you would write to does not exist either. Do not
improvise a substitute.

PRECONDITION 3 - inputs. Confirm cad/enclosure.py and
docs/thrifty/2026-09-15-battery-boxes/artefacts/box-shell.stl exist. If either does
not, WP-02's PR has not merged. Write
docs/thrifty/2026-09-15-battery-boxes/status/WP-03.md with state: blocked and the
absent path in Notes, commit, push, open one PR, and STOP. Do not reconstruct it.

BRANCH. Your branch is thrifty/2026-09-15-battery-boxes/wp-03 - derived from the
plan, never invented. Before touching anything:
  git fetch origin
  git ls-remote --exit-code --heads origin thrifty/2026-09-15-battery-boxes/wp-03
A missing branch means a fresh start. Cut it from origin/main:
  git switch -c thrifty/2026-09-15-battery-boxes/wp-03 origin/main
Write docs/thrifty/2026-09-15-battery-boxes/status/WP-03.md with state: started.
Commit it ("chore(thrifty): WP-03 start") and push -u. Do NOT open a PR yet. That
commit only stakes the branch so a dead session is still findable. The PR comes
once, at the very end of this prompt.
An existing branch means a RESUME, not a new start. Check it out:
  git switch -c thrifty/2026-09-15-battery-boxes/wp-03 origin/thrifty/2026-09-15-battery-boxes/wp-03
Read that status file and carry on from its resume-from, setting state:
in-progress. Do not start over and do not re-apply what is already done.
Never commit to main.

THEN read docs/thrifty/2026-09-15-battery-boxes/plan.md sections 4.1, 4.2, 4.6, 5.2,
5.3, 5.8 and 6, and cad/README.md.

Load: ToolSearch query "select:Read,Write,Edit,Bash,Grep"

Do NOT load or call WebSearch or WebFetch. The transform is section 4.6; a rotation
convention from the web with the opposite sign puts the boxes in a V instead of an
inverted V and nothing downstream would notice.
Do NOT load or call the Agent tool. Eight items, one session.

TASK. Write cad/assembly.py per section 4.6 and run it.
Hard cap: 25 items this session. 25 is the measured budget from section 5.8, not a
target - reaching it is a normal ending, not a failure.
  1. place_left(shape, params): the section 4.6 transform as a build123d
     Location built from the rotation matrix, applied to the enclosure body from
     cad/enclosure.py (call its builder; do not re-read STEP). Compute and print
     the lid normal and the stack axis from the placed body's faces.
     THIS IS THE CANARY.
  2. mirror_right(placed): Plane.XZ mirror; print its lid normal and stack axis.
  3. Motor cylinder and keep-out cylinder from [motor] and [keepout].
  4. corners(): the eight outer-shell corners of each placed box in vehicle
     coordinates, and inboard_gap_at_floor; print them.
  5. Export artefacts/assembly.step (two shells from box-shell geometry rebuilt as
     solids, motor, keep-out; 4 solids) through check_step.
  6. Export data/cad/assembly-full.step (both placed box-full sets, motor,
     keep-out; 56 solids) through check_step. Do not commit it.
  7. Write artefacts/placement.json per the section 4.6 schema.
  8. Run once more with lean_deg = 0.0 via --params on a scratch copy: the lid
     normal must be (0, 0, 1) and the stack axis (0, 1, 0); report, then leave
     cad/params.toml untouched.

PROCEDURE:
1. Write the file skeleton.
2. CANARY = item 1 only. Stop. Show the printed lid normal and stack axis against
   (0, 0.5, 0.866) and (0, 0.866, -0.5). Wait for the go-ahead.
3. Then items 2-8 as one batch. After the batch: report, update the status file
   (progress, resume-from, updated), commit, push. Serial calls only. No PR yet.
4. If you hit the hard cap, or context runs short, or the owner pauses you: write
   state: paused with resume-from and pause-reason, commit, push, and STOP. Do
   NOT open a PR yet - that is the job of the session that resumes this prompt.

VERIFY BEFORE FINISHING:
  .venv-cad/Scripts/python cad/assembly.py   -> lid normal (0, 0.500, 0.866) and
     stack axis (0, 0.866, -0.500) within 0.001; check_step OK, 4 solids; OK, 56 solids
  python -c "import json; d=json.load(open('docs/thrifty/2026-09-15-battery-boxes/artefacts/placement.json')); print(len(d['left']['corners']), len(d['right']['corners']), d['left']['lid_normal'][1] > 0, d['right']['lid_normal'][1] < 0)"
     -> 8 8 True True
Report the numbers. If any does not match, say so and do not claim completion.

SCOPE FENCE. You may write cad/assembly.py, the two artefacts named above,
data/cad/assembly-full.step, and your own status and findings files. Do NOT edit
cad/params.toml, cad/common.py, cad/cell.py or cad/enclosure.py - a needed change
is a finding and state: blocked. Do NOT commit anything under data/. Out-of-scope
observations go in docs/thrifty/2026-09-15-battery-boxes/findings/WP-03.md, not
into an action.

STOP CONDITION: when every item in your list has been handled once, or the hard
cap is reached. Do not look for more work.

Write docs/thrifty/2026-09-15-battery-boxes/status/WP-03.md per section 6 of the
plan. On a terminal state - done, blocked, stopped, or canary-waiting - commit to
your branch cut from origin/main, push it, and open one PR. Then STOP - the owner
merges. Do NOT add commits to a PR that is already open.
```

---

### WP4 — Sweep the placement against the frame and render sections

**Model:** Sonnet · **Effort:** medium · **Item cap:** 25 (this WP has 11 items) ·
**Branch:** `thrifty/2026-09-15-battery-boxes/wp-04` · **Writes:** `cad/clearance.py`,
`artefacts/sweep.json`, `artefacts/sweep-report.md`, six `artefacts/section-*.png`

**Goal.** Evaluate any placement against the frame, the motor placeholder and the keep-out; run the
section 4.7 grid; render the sections the owner needs to choose a placement.

**Done when.** `.venv-mesh/Scripts/python cad/clearance.py --controls` prints the two control rows
with the section 4.7 expected results; `--sweep` writes `sweep.json` with 1 701 rows; `--render`
writes six PNGs under 500 kB each; `sweep-report.md` opens with the section 4.7 sentence and names
the best placement and whether the defaults pass.

```
WP-04 of the battery-boxes plan: clearance sweep and section renders.
Repo: electric-butterfly/equad. Work from the root of your local clone - find it, do not
assume a path. Make NO writes outside this repo.

PRECONDITION 1 - right tree. Run `git rev-parse --show-toplevel` and
`git remote get-url origin`. origin must be electric-butterfly/equad, and every path
below is relative to the toplevel the first command printed. If origin names a
different repo, or git errors because this is not a work tree, say so and STOP,
and ask the owner to repoint the session. Do not clone it, do not search the
filesystem for a copy, do not guess a path. Write nothing.

PRECONDITION 2 - plan present. Confirm docs/thrifty/2026-09-15-battery-boxes/plan.md
exists in that tree. If it does not, the plan PR has not merged - say so and STOP.
Write nothing: the directory you would write to does not exist either. Do not
improvise a substitute.

PRECONDITION 3 - inputs. Confirm
docs/thrifty/2026-09-15-battery-boxes/artefacts/placement.json and
docs/thrifty/2026-09-15-battery-boxes/artefacts/box-shell.stl exist. If either does
not, WP-03's PR has not merged. Write
docs/thrifty/2026-09-15-battery-boxes/status/WP-04.md with state: blocked and the
absent path in Notes, commit, push, open one PR, and STOP. Do not reconstruct it.
Confirm data/derived/chassis_datum_5M.stl and data/derived/chassis_datum_1M.stl
exist and that `.venv-mesh/Scripts/python -c "import open3d, trimesh, PIL"`
succeeds (install pillow into .venv-mesh if PIL is the only failure). If a mesh is
missing, the scan pipeline needs to be run on this machine first. Record state:
blocked with the absent path in Notes, commit, push, open one PR, STOP.

BRANCH. Your branch is thrifty/2026-09-15-battery-boxes/wp-04 - derived from the
plan, never invented. Before touching anything:
  git fetch origin
  git ls-remote --exit-code --heads origin thrifty/2026-09-15-battery-boxes/wp-04
A missing branch means a fresh start. Cut it from origin/main:
  git switch -c thrifty/2026-09-15-battery-boxes/wp-04 origin/main
Write docs/thrifty/2026-09-15-battery-boxes/status/WP-04.md with state: started.
Commit it ("chore(thrifty): WP-04 start") and push -u. Do NOT open a PR yet. That
commit only stakes the branch so a dead session is still findable. The PR comes
once, at the very end of this prompt.
An existing branch means a RESUME, not a new start. Check it out:
  git switch -c thrifty/2026-09-15-battery-boxes/wp-04 origin/thrifty/2026-09-15-battery-boxes/wp-04
Read that status file and carry on from its resume-from, setting state:
in-progress. Do not start over and do not re-apply what is already done.
Never commit to main.

THEN read docs/thrifty/2026-09-15-battery-boxes/plan.md sections 4.1, 4.2, 4.6, 4.7,
5.1, 5.4, 5.5, 5.8 and 6, and cad/README.md.

Load: ToolSearch query "select:Read,Write,Edit,Bash,Grep"

Do NOT load or call WebSearch or WebFetch. Nothing here needs the web.
Do NOT load or call the Agent tool. The sweep is one foreground run; splitting it
across sessions would produce two half-grids nobody can merge.

TASK. Write cad/clearance.py per section 4.7 and run it.
Hard cap: 25 items this session. 25 is the measured budget from section 5.8, not a
target - reaching it is a normal ending, not a failure.
  1. load_scene(): read [chassis].mesh into an Open3D RaycastingScene; print face
     and vertex counts (expect 4 021 243 faces).
  2. place_shell(x, y, z, lean, side): transform box-shell.stl by section 4.6
     (mirror for the right); return an Open3D mesh.
  3. evaluate(x, y, z, lean): steps 2-5 of section 4.7 for the boxes against
     frame, motor and keep-out; return the sweep.json row. motor_vs_frame(): step
     6, once.
  4. --controls: run the two control placements and print both rows next to the
     expected values. THIS IS THE CANARY.
  5. --sweep: the [sweep] grid, 1 701 rows, written to artefacts/sweep.json. Run
     it in the foreground with a 15-minute timeout; print progress every 200
     rows and the elapsed time at the end.
  6. summarise(): per X and per lean the feasible Y and Z ranges and the best
     min_frame; the single best placement; whether the [placement] defaults pass
     (evaluate them explicitly).
  7. render_section(plane, placement, name): section 4.7 renders using
     [chassis].mesh_1m vertices, with the box edges, motor and keep-out overlaid.
  8. --render for the defaults: section-yz-default.png, section-xz-default.png,
     section-xy-default.png.
  9. --render for the best placement: the three -best.png files.
 10. Write artefacts/sweep-report.md per section 4.7, opening with the required
     sentence, then the summary tables, the best placement, the defaults verdict,
     and a one-line chamfer note: the min_frame at the defaults with
     chamfer_front_top 0 and, if the closest frame point lies within 60 mm of the
     front top edge, the distance a 20 mm chamfer would add (compute it by
     re-running evaluate on a chamfered shell built from the same STL with the
     edge cut; if the closest point is elsewhere, write "chamfer would not help").
 11. Sizes: every PNG under 500 kB, sweep.json under 1 MB; report each.

PROCEDURE:
1. Write items 1-3 (no run beyond an import check).
2. CANARY = item 4 only. Stop. Show the two control rows against the expected
   values. Wait for the go-ahead.
3. Then items 5-11 in two batches (5-6, then 7-11). After each batch: report,
   update the status file (progress, resume-from, updated), commit, push. Serial
   calls only. No PR yet.
4. If you hit the hard cap, or context runs short, or the owner pauses you: write
   state: paused with resume-from and pause-reason, commit, push, and STOP. Do
   NOT open a PR yet - that is the job of the session that resumes this prompt.

VERIFY BEFORE FINISHING:
  .venv-mesh/Scripts/python cad/clearance.py --controls   -> collision row: inside
     over 50 000 and min_frame under 1.0; clear row: inside 0 and min_frame over 200
  python -c "import json; r=json.load(open('docs/thrifty/2026-09-15-battery-boxes/artefacts/sweep.json')); print(len(r), sum(1 for x in r if x['pass']))"
     -> 1701 and a pass count greater than 0
  head -c 200 docs/thrifty/2026-09-15-battery-boxes/artefacts/sweep-report.md
     -> begins with "This sweep tests the frame"
  ls -la docs/thrifty/2026-09-15-battery-boxes/artefacts/section-*.png   -> six files
Report the numbers. If any does not match, say so and do not claim completion.

SCOPE FENCE. You may write cad/clearance.py, the eight artefacts named above, and
your own status and findings files. Do NOT edit cad/params.toml - the placement
decision is the owner's, made from your report. Do NOT edit any other cad/ script.
Do NOT touch pipeline/ or data/derived/. Do NOT present the frame result as a fit
- the report's first sentence is fixed for that reason. Out-of-scope observations
go in docs/thrifty/2026-09-15-battery-boxes/findings/WP-04.md, not into an action.

STOP CONDITION: when every item in your list has been handled once, or the hard
cap is reached. Do not look for more work.

Write docs/thrifty/2026-09-15-battery-boxes/status/WP-04.md per section 6 of the
plan. On a terminal state - done, blocked, stopped, or canary-waiting - commit to
your branch cut from origin/main, push it, and open one PR. Then STOP - the owner
merges. Do NOT add commits to a PR that is already open.
```

---

### WP5 — List the mount pickups within reach of the placed boxes

**Model:** Sonnet · **Effort:** medium · **Item cap:** 25 (this WP has 7 items) ·
**Branch:** `thrifty/2026-09-15-battery-boxes/wp-05` · **Writes:** `cad/mounts.py`,
`artefacts/mount-pickups.json`, `artefacts/mounts-report.md`

**Goal.** For the owner's chosen placement, list every fitted frame cylinder and RANSAC plane
within 120 mm of either box with its distance and nearest face, and state the mounting concept.

**Done when.** `.venv-mesh/Scripts/python cad/mounts.py` prints the count of candidate primitives
read (cylinders from all six regions plus engine-bay planes with support over 1 500) and the count
kept; `mount-pickups.json` rows are sorted by distance and every plane row carries
`"note": "calliper before drilling"`; `mounts-report.md` contains the concept paragraph.

```
WP-05 of the battery-boxes plan: mount pickups.
Repo: electric-butterfly/equad. Work from the root of your local clone - find it, do not
assume a path. Make NO writes outside this repo.

PRECONDITION 1 - right tree. Run `git rev-parse --show-toplevel` and
`git remote get-url origin`. origin must be electric-butterfly/equad, and every path
below is relative to the toplevel the first command printed. If origin names a
different repo, or git errors because this is not a work tree, say so and STOP,
and ask the owner to repoint the session. Do not clone it, do not search the
filesystem for a copy, do not guess a path. Write nothing.

PRECONDITION 2 - plan present. Confirm docs/thrifty/2026-09-15-battery-boxes/plan.md
exists in that tree. If it does not, the plan PR has not merged - say so and STOP.
Write nothing: the directory you would write to does not exist either. Do not
improvise a substitute.

PRECONDITION 3 - inputs. Confirm
docs/thrifty/2026-09-15-battery-boxes/artefacts/sweep-report.md,
docs/thrifty/2026-09-15-battery-boxes/artefacts/placement.json,
docs/thrifty/2026-09-15-battery-boxes/artefacts/box-shell.stl,
docs/thrifty/2026-09-14-scan-pipeline/artefacts/interfaces.json and
docs/thrifty/2026-09-14-scan-pipeline/artefacts/primitives-engine-bay.json exist.
If any does not, the producing PR has not merged. Write
docs/thrifty/2026-09-15-battery-boxes/status/WP-05.md with state: blocked and the
absent path in Notes, commit, push, open one PR, and STOP. Do not reconstruct it.
Then run `git log -1 --format=%ct -- cad/params.toml` and `git log -1 --format=%ct --
docs/thrifty/2026-09-15-battery-boxes/artefacts/sweep-report.md`: both print a
unix time, and the params time must be the larger number, which shows the owner
has set [placement] after the sweep. If it is not, record state: blocked with Notes "placement not yet set by
the owner after WP-04", commit, push, open one PR, STOP.

BRANCH. Your branch is thrifty/2026-09-15-battery-boxes/wp-05 - derived from the
plan, never invented. Before touching anything:
  git fetch origin
  git ls-remote --exit-code --heads origin thrifty/2026-09-15-battery-boxes/wp-05
A missing branch means a fresh start. Cut it from origin/main:
  git switch -c thrifty/2026-09-15-battery-boxes/wp-05 origin/main
Write docs/thrifty/2026-09-15-battery-boxes/status/WP-05.md with state: started.
Commit it ("chore(thrifty): WP-05 start") and push -u. Do NOT open a PR yet. That
commit only stakes the branch so a dead session is still findable. The PR comes
once, at the very end of this prompt.
An existing branch means a RESUME, not a new start. Check it out:
  git switch -c thrifty/2026-09-15-battery-boxes/wp-05 origin/thrifty/2026-09-15-battery-boxes/wp-05
Read that status file and carry on from its resume-from, setting state:
in-progress. Do not start over and do not re-apply what is already done.
Never commit to main.

THEN read docs/thrifty/2026-09-15-battery-boxes/plan.md sections 4.1, 4.2, 4.6, 4.8,
5.1, 5.8 and 6, and cad/README.md.

Load: ToolSearch query "select:Read,Write,Edit,Bash,Grep"

Do NOT load or call WebSearch or WebFetch. Nothing here needs the web.
Do NOT load or call the Agent tool. Seven items, one session.

TASK. Write cad/mounts.py per section 4.8 and run it.
Hard cap: 25 items this session. 25 is the measured budget from section 5.8, not a
target - reaching it is a normal ending, not a failure.
  1. Re-run `.venv-cad/Scripts/python cad/assembly.py` so placement.json reflects
     the owner's [placement]; print the params block it wrote. THIS IS THE CANARY.
  2. load_primitives(): accepted cylinders from every region of interfaces.json
     and planes with support over 1 500 from primitives-engine-bay.json; print
     the two counts.
  3. placed_shells(): both boxes from box-shell.stl and placement.json, as Open3D
     RaycastingScenes; also label each of the six faces of each box by its
     outward normal so nearest_face can be named.
  4. distance and nearest_face for every primitive to each box; keep rows under
     120 mm; print kept count.
  5. Write artefacts/mount-pickups.json sorted by distance, plane rows carrying
     the note.
  6. Write artefacts/mounts-report.md: the table, the concept paragraph from
     section 4.8 verbatim, and the four engine-mount planes from section 5.1
     called out by name with their distance to the nearest box.
  7. Print the first twenty rows as a table in the session report.

PROCEDURE:
1. CANARY = item 1 only. Stop. Show the params block. Wait for the go-ahead.
2. Then items 2-7 as one batch. After the batch: report, update the status file
   (progress, resume-from, updated), commit, push. Serial calls only. No PR yet.
3. If you hit the hard cap, or context runs short, or the owner pauses you: write
   state: paused with resume-from and pause-reason, commit, push, and STOP. Do
   NOT open a PR yet - that is the job of the session that resumes this prompt.

VERIFY BEFORE FINISHING:
  python -c "import json; r=json.load(open('docs/thrifty/2026-09-15-battery-boxes/artefacts/mount-pickups.json')); print(len(r), all(r[i]['distance'] <= r[i+1]['distance'] for i in range(len(r)-1)), all(x.get('note')=='calliper before drilling' for x in r if x['kind']=='plane'))"
     -> a count over 0, True, True
  grep -c "calliper before drilling" docs/thrifty/2026-09-15-battery-boxes/artefacts/mounts-report.md
     -> at least 1
Report the numbers. If any does not match, say so and do not claim completion.

SCOPE FENCE. You may write cad/mounts.py, the two artefacts named above,
artefacts/placement.json and artefacts/assembly.step (regenerated by item 1), and
your own status and findings files. Do NOT edit cad/params.toml or any other cad/
script. Do NOT design brackets. Out-of-scope observations go in
docs/thrifty/2026-09-15-battery-boxes/findings/WP-05.md, not into an action.

STOP CONDITION: when every item in your list has been handled once, or the hard
cap is reached. Do not look for more work.

Write docs/thrifty/2026-09-15-battery-boxes/status/WP-05.md per section 6 of the
plan. On a terminal state - done, blocked, stopped, or canary-waiting - commit to
your branch cut from origin/main, push it, and open one PR. Then STOP - the owner
merges. Do NOT add commits to a PR that is already open.
```

---

### WP6 — Build the viewer and the handover document

**Model:** Sonnet · **Effort:** medium · **Item cap:** 25 (this WP has 10 items) ·
**Branch:** `thrifty/2026-09-15-battery-boxes/wp-06` · **Writes:** `cad/viewer.py`,
`artefacts/viewer.html`, `artefacts/sam-battery-boxes.html`

**Goal.** One HTML file the owner opens to see the boxes on the chassis, and one HTML file Sam
reads to start the fabrication design.

**Done when.** `artefacts/viewer.html` is under 8 MB, references exactly one external URL (the
three.js r128 script on cdnjs), and embeds five bodies; `artefacts/sam-battery-boxes.html` is under
2 MB, contains the parameter table, the placement, the best-placement line from `sweep-report.md`,
the three default renders inline, the pickup table and the open-items list; neither file contains
the strings "draft", "corrected", "previously" or "verification".

```
WP-06 of the battery-boxes plan: viewer and handover document.
Repo: electric-butterfly/equad. Work from the root of your local clone - find it, do not
assume a path. Make NO writes outside this repo.

PRECONDITION 1 - right tree. Run `git rev-parse --show-toplevel` and
`git remote get-url origin`. origin must be electric-butterfly/equad, and every path
below is relative to the toplevel the first command printed. If origin names a
different repo, or git errors because this is not a work tree, say so and STOP,
and ask the owner to repoint the session. Do not clone it, do not search the
filesystem for a copy, do not guess a path. Write nothing.

PRECONDITION 2 - plan present. Confirm docs/thrifty/2026-09-15-battery-boxes/plan.md
exists in that tree. If it does not, the plan PR has not merged - say so and STOP.
Write nothing: the directory you would write to does not exist either. Do not
improvise a substitute.

PRECONDITION 3 - inputs. Confirm these exist under
docs/thrifty/2026-09-15-battery-boxes/artefacts/: assembly.step, placement.json,
sweep-report.md, section-yz-default.png, section-xz-default.png,
section-xy-default.png, mount-pickups.json, mounts-report.md. If any does not, the
producing PR has not merged. Write
docs/thrifty/2026-09-15-battery-boxes/status/WP-06.md with state: blocked and the
absent path in Notes, commit, push, open one PR, and STOP. Do not reconstruct it.
Confirm data/derived/chassis_datum_200k.stl exists; if not, state: blocked as
above.

BRANCH. Your branch is thrifty/2026-09-15-battery-boxes/wp-06 - derived from the
plan, never invented. Before touching anything:
  git fetch origin
  git ls-remote --exit-code --heads origin thrifty/2026-09-15-battery-boxes/wp-06
A missing branch means a fresh start. Cut it from origin/main:
  git switch -c thrifty/2026-09-15-battery-boxes/wp-06 origin/main
Write docs/thrifty/2026-09-15-battery-boxes/status/WP-06.md with state: started.
Commit it ("chore(thrifty): WP-06 start") and push -u. Do NOT open a PR yet. That
commit only stakes the branch so a dead session is still findable. The PR comes
once, at the very end of this prompt.
An existing branch means a RESUME, not a new start. Check it out:
  git switch -c thrifty/2026-09-15-battery-boxes/wp-06 origin/thrifty/2026-09-15-battery-boxes/wp-06
Read that status file and carry on from its resume-from, setting state:
in-progress. Do not start over and do not re-apply what is already done.
Never commit to main.

THEN read docs/thrifty/2026-09-15-battery-boxes/plan.md sections 4.1, 4.2, 4.9, 5.6,
5.8 and 6, cad/README.md, and
the file named sam-chassis-interfaces.html under
docs/thrifty/2026-09-14-scan-pipeline/artefacts/ for its layout only (if that file is absent, use an 18 px base font, one centred sheet
of 1 220 px maximum width, and plain tables).

Load: ToolSearch query "select:Read,Write,Edit,Bash,Grep"

Do NOT load or call WebSearch or WebFetch. The one CDN URL is in section 4.9 and
was measured reachable; do not look for another.
Do NOT load or call the Artifact tool. The viewer is a repo file the owner opens
locally; publishing it would put project geometry on a hosted page nobody asked for.
Do NOT load or call the Agent tool. Ten items, one session.

TASK. Write cad/viewer.py and produce the two HTML files per section 4.9.
Hard cap: 25 items this session. 25 is the measured budget from section 5.8, not a
target - reaching it is a normal ending, not a failure.
  1. Under .venv-mesh: decimate [chassis].mesh_viewer to 60 000 faces with Open3D
     quadric decimation; write the Float32 triangle soup as base64 to a scratch
     file under data/cad/; print face count and base64 length (expect about
     2.9 MB). THIS IS THE CANARY.
  2. Under .venv-cad: tessellate the four solids of assembly.step (import_step,
     then tessellate at 0.5 mm) to Float32 soups, base64, one per body; print
     each length.
  3. cad/viewer.py assembles artefacts/viewer.html: the single three.js script
     tag, inline orbit control (drag rotate, wheel zoom, right-drag pan), the five
     bodies as BufferGeometry from the base64 buffers, per-body checkboxes, the
     YZ clipping-plane slider along X, an axes triad, a 100 mm floor grid, the
     colours of section 4.9. Vehicle X to the right, Z up.
  4. Open viewer.html in a browser is the owner's check; your check is: file size
     under 8 MB, exactly one https:// URL in the file, five occurrences of the
     base64 marker you use per body.
  5. Read sweep-report.md, mounts-report.md, placement.json and cad/params.toml
     (only the lines you need: grep for the best-placement line, the defaults
     verdict, and the first twenty pickup rows).
  6. Write artefacts/sam-battery-boxes.html: purpose (three sentences), the
     parameter table with sources, the placement in words with the transform,
     the sweep result and best placement, the three default renders inline by
     relative path, the pickup table (first twenty rows), links to cell.step,
     block.step, box.step, box-full.step and assembly.step by relative path, and
     the open-items list from section 4.9. Australian English. No narrative about
     how it was produced.
  7. grep both files for "draft", "corrected", "previously", "verification",
     "TODO" (case-insensitive) -> expect 0 hits; remove any.
  8. Confirm every relative link in sam-battery-boxes.html resolves to a file
     in the artefacts directory (script it: parse href and src, test existence).
  9. Sizes of both files.
 10. Confirm `git status --short` lists only cad/viewer.py, the two HTML files
     and the status file.

PROCEDURE:
1. CANARY = item 1 only. Stop. Show the face count and the base64 length. Wait
   for the go-ahead.
2. Then items 2-10 in two batches (2-4, then 5-10). After each batch: report,
   update the status file (progress, resume-from, updated), commit, push. Serial
   calls only. No PR yet.
3. If you hit the hard cap, or context runs short, or the owner pauses you: write
   state: paused with resume-from and pause-reason, commit, push, and STOP. Do
   NOT open a PR yet - that is the job of the session that resumes this prompt.

VERIFY BEFORE FINISHING:
  ls -la docs/thrifty/2026-09-15-battery-boxes/artefacts/viewer.html   -> under 8 000 000 bytes
  grep -o "https://[^\"' ]*" docs/thrifty/2026-09-15-battery-boxes/artefacts/viewer.html | sort -u | wc -l   -> 1
  grep -ciE "draft|corrected|previously|verification|todo" docs/thrifty/2026-09-15-battery-boxes/artefacts/sam-battery-boxes.html   -> 0
  the link check of item 8   -> every link resolves
Report the numbers. If any does not match, say so and do not claim completion.

SCOPE FENCE. You may write cad/viewer.py, the two HTML files, scratch files under
data/cad/, and your own status and findings files. Do NOT edit cad/params.toml or
any other cad/ script. Do NOT edit any file under
docs/thrifty/2026-09-14-scan-pipeline/. Do NOT publish either HTML file through the
Artifact tool or any hosting service; the PR is their only route out.
Out-of-scope observations go in
docs/thrifty/2026-09-15-battery-boxes/findings/WP-06.md, not into an action.

STOP CONDITION: when every item in your list has been handled once, or the hard
cap is reached. Do not look for more work.

Write docs/thrifty/2026-09-15-battery-boxes/status/WP-06.md per section 6 of the
plan. On a terminal state - done, blocked, stopped, or canary-waiting - commit to
your branch cut from origin/main, push it, and open one PR. Then STOP - the owner
merges. Do NOT add commits to a PR that is already open.
```

---

## 9. Owner actions

| # | Action | When |
|---|---|---|
| 1 | **Commit this plan directory and merge it to `main`.** Nothing can start until the plan is on `main`. | **First** |
| 2 | **Keep `callistofarm` as the active `gh` account.** It has push on electric-butterfly/equad (checked 2026-09-15). | Before WP1 |
| 3 | **Measure the supplier's inter-cell pad** and put it in `cad/params.toml` `[cell].pad`. The default is 3.0 from the BOM. Every later artefact regenerates from it, so it can land any time, but before WP2 saves a re-run. | Before WP2, ideally |
| 4 | **Confirm or replace the `OWNER` values in `params.toml`:** sheet thickness, compression wall, fuse envelope (with the JLLN800 holder in hand), motor housing diameter (tape measure), keep-out height. | Any time; each is a one-line PR and a re-run |
| 5 | **Ask Sam for a scan of the plastics, foot boards, tank and seat base** from the Artec project, aligned to the same datum by the scan pipeline. Until it exists, the sweep tests the frame only. This is the constraint that decides the lean. | Any time; it gates the next plan, not this one |
| 6 | **Merge each WP's PR before its dependant runs.** Eyeball the six renders in WP4's PR. | Between WPs |
| 7 | **After WP4: choose the placement.** Edit `[placement]` in `cad/params.toml` to the chosen `x, y, z, lean_deg` and merge that as its own PR. WP5's precondition checks that this commit is newer than the sweep report. | Between WP4 and WP5 |
| 8 | **Callipers on the lower rails and the four engine-mount plates** (section 5.1) before Sam drills anything from the pickup table. | Before fabrication |
| 9 | **Resume anything showing `paused`.** Paste the same starter prompt into a fresh session; it picks up from the branch. A paused WP has no PR and will not surface as your turn. | Whenever the rollup shows one |

---

## 10. Known collisions

- The owner's working tree has the scan-pipeline handover document `sam-chassis-interfaces.html`
  deleted and an untracked `chassis scan cleanup review.html` beside it. Resolving that is the
  owner's, before or after this plan's PR; no WP touches that directory, and WP6 reads the
  interface document for layout only if it is present.
- `origin/thrifty/2026-09-14-scan-pipeline/sam-doc-layout-redesign` is one commit ahead of `main`
  and unmerged. It touches the same interface document. Not this plan's concern.
- `.venv-cad` and `.venv-mesh` at the repo root are git-ignored and were both working on the
  owner's machine on 2026-09-15. A WP that finds a venv broken rebuilds it from the pinned
  requirements in place; it does not create one elsewhere.
- `data/derived/` is produced by the scan pipeline and git-ignored. WP4, WP5 and WP6 read it. A
  machine without it cannot run those WPs; the pipeline is re-run first (section 4 of the scan
  pipeline plan).
- The README's battery-box paragraph describes the inverted V and the channel as the duct. Nothing
  in this plan edits `README.md`. Resolving any of the above is NOT part of this plan.
