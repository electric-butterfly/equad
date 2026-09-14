# Scan pipeline: toolsets, condition, crop, segment, fit — Plan

| Property | Value |
|---|---|
| Date | 2026-09-14 |
| Owner | Jeremy |
| Repo | electric-butterfly/equad |
| Tier | 2 Sub-project |
| Status | Draft |

---

## 1. Purpose

The eQuad conversion is a packaging problem on a machine whose geometry exists only as an Artec
scan: 35,074,344 triangles of the stripped rolling chassis in a frame of the scanner's choosing,
with the workshop floor attached. Nothing downstream — the intermediate drive, the battery boxes,
the controller box, the ducting — can be drawn until that scan is cleaned, aligned to a vehicle
datum, cropped to the regions a new part touches, and its tube runs and mount plates reduced to
geometric primitives with known residuals.

This plan delivers the first four stages of the modelling workflow in `docs/scan-to-cad-options.md`:
the toolsets, then condition, crop, segment and fit. It delivers the normative pipeline contract in
section 4 and six work packages in section 8. Everything in it was measured on the owner's
workstation on 2026-09-14; the numbers in section 5 are what a session checks its own results
against.

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
| **In scope** | Two toolset installs with smoke tests (mesh side; CAD side). Four pipeline scripts under `pipeline/`: condition, crop, segment, fit. Six named crop regions. A reference datum the condition step must reproduce. Small artefacts committed under `docs/thrifty/2026-09-14-scan-pipeline/artefacts/`. |
| **Out of scope** | Interface solids (STEP) — the next plan. Any Fusion work, the Fusion MCP, and the Fusion licence decision (owner, section 9). The scanning fabricator's re-exports from the Artec project (owner). Physical measurement of tube OD, bolt holes and flanges (owner). The README correction. |
| **Origin at the rear axle, not the front** | ISO 8855 axes, with the origin below the rear axle housing axis rather than the front axle. The scan resolves the rear axle housing as two 24 mm-radius cylinders whose X agrees to 0.8 mm; the front tyres are steered, partly scanned and mixed with bumper points, and their circle fits scatter by hundreds of millimetres (section 5.4). Moving the origin to the front axle later is a single X offset. |
| **Derived data is local and git-ignored** | Meshes of 50 MB to 1 GB live under `data/` at the repo root, ignored by git, regenerable from the scan by the pipeline. Only small artefacts (JSON, reports, renders under 500 kB) are committed. |
| **Machine-local paths live in one ignored file** | `pipeline/config.local.toml`, written by the owner from `pipeline/config.example.toml`. No script, prompt or plan section carries a path to the scans, the data root or an executable. |
| **CloudCompare does the multi-primitive segmentation** | Single-model fits on box crops fail on this frame because plates are welded beside the tubes (section 5.3). CloudCompare's RANSAC shape detection separates planes and cylinders in one pass and was measured to do so (section 5.5). Python does the refinement. |
| **Fusion MCP excluded** | It needs a licence decision the owner has not made. Nothing in these four stages needs Fusion. |

---

## 3. Target state

When this plan is finished:

- Two Python virtual environments and two desktop tools are installed with pinned versions, each
  proven by a smoke test that writes a file and reads it back.
- `pipeline/condition.py` turns the full-res scan into a floor-free, datum-aligned mesh in the ISO
  8855 vehicle frame, plus 5 M, 1 M and 200 k decimations, and writes `datum.json` whose transform
  matches `artefacts/datum-reference.json` within the tolerances in section 4.3.
- `pipeline/crop.py` writes one full-resolution mesh and one point cloud per region in
  `pipeline/crops.toml`, and a silhouette render of each.
- `pipeline/segment.py` runs CloudCompare RANSAC on each region and writes one primitive table per
  region with axis, radius, support and residual.
- `pipeline/fit.py` refines every accepted primitive on full-resolution points and writes
  `interfaces.json` with residuals, plus a deviation render per region.
- Every stage is re-runnable from the scan with one command and no interactive step.

**Measured baseline, 2026-09-14:**

| | count |
|---|---|
| Faces, full-res scan | 35 074 344 |
| Faces, low-res scan | 1 844 914 |
| Surface area, full-res, before floor removal | 8.264 m² |
| Fraction of 1 M-decimation vertices on the floor plane | 13.3% |
| Rotation between the scan's principal axes and the vehicle symmetry plane | 12.08° |
| Cylinders found by RANSAC in the engine bay with radius 11–16 mm | 38 |
| Pipeline scripts in the repo | 0 |

---

## 4. The pipeline contract — normative

### 4.1 Files and layout

```text
pipeline/
  README.md                 how to run each stage
  requirements-mesh.txt     pinned: numpy scipy trimesh==5.1.0 pymeshlab==2025.7.post1
                                    open3d==0.19.0 pyransac3d==0.7.0 psutil
  requirements-cad.txt      pinned: build123d==0.11.1 (pulls cadquery-ocp-novtk 7.9.3.1.1)
  requirements-draft.txt    pinned: draftwright==0.4.29 (pulls build123d 0.10.0, cadquery-ocp 7.8.1)
  config.example.toml       template for config.local.toml
  config.local.toml         git-ignored; owner-written; machine paths
  crops.toml                the six regions, section 4.4, verbatim
  common.py                 config loading, STL streaming, PNG silhouette, circle fit
  condition.py              WP-03
  crop.py                   WP-04
  segment.py                WP-05
  fit.py                    WP-06
data/                       git-ignored
  derived/                  chassis_datum_full.ply, chassis_datum_5M.stl, _1M.stl, _200k.stl,
                            datum.json
  crops/<region>/           <region>_full.ply, <region>_pts.ply, <region>_silhouette.png
  ransac/<region>/          CloudCompare outputs (clouds/, meshes/)
.venv-mesh/ .venv-cad/ .venv-draft/   git-ignored
```

`.gitignore` (WP-01 writes it, exactly):

```text
data/
.venv-mesh/
.venv-cad/
.venv-draft/
pipeline/config.local.toml
__pycache__/
```

### 4.2 Configuration

`pipeline/config.example.toml`:

```toml
# Copy to config.local.toml and fill in. config.local.toml is git-ignored.
scan_full = "<absolute path to King Quad 400 Full Res.stl>"
scan_low = "<absolute path to King Quad 400 Low Res.stl>"
data_root = "data"                      # relative to the repo root, or absolute
cloudcompare_exe = "<absolute path to CloudCompare.exe>"
freecad_cmd = "<absolute path to FreeCADCmd.exe, or empty>"
```

Every script loads it with the standard-library `tomllib`, resolves `data_root` against the repo root
(`git rev-parse --show-toplevel`), and refuses to run if a key is missing or a file does not exist.
Every script takes `--stage-only` flags as documented in its own `--help` and writes nothing outside
`data_root` and `docs/thrifty/2026-09-14-scan-pipeline/artefacts/`.

### 4.3 Condition — the datum procedure

Units are millimetres throughout. The vehicle frame is ISO 8855: X forward, Y left, Z up. Origin:
on the floor plane, on the symmetry plane, at the X of the rear axle housing axis.

| Step | Method | Accept when |
|---|---|---|
| 1 Load | `pymeshlab.MeshSet().load_new_mesh(scan_full)` | 35 074 344 faces loaded |
| 2 Fragments | `compute_selection_by_small_disconnected_components_per_face(nbfaceratio=0.0001)`; `meshing_remove_selected_faces`; `meshing_remove_unreferenced_vertices`; `meshing_remove_duplicate_faces`; `meshing_remove_null_faces` | Faces removed between 0.05% and 0.5% |
| 3 Working decimation | `meshing_decimation_quadric_edge_collapse(targetfacenum=5_000_000, preservenormal=True, preservetopology=True, preserveboundary=True, planarquadric=True, qualitythr=0.3)`, save `chassis_scan_5M.stl`; repeat to 1 000 000, save `chassis_scan_1M.stl` | 4 999 999 and 999 999 faces |
| 4 Floor plane | Open3D on the 1 M vertices: `segment_plane(distance_threshold=3.0, ransac_n=3, num_iterations=3000)`; refine by least-squares plane on the inliers; orient the normal so the mesh centroid is on the positive side | Inliers 10–18% of vertices; RMS of inliers under 2.0 mm |
| 5 Floor removal | On the full-res MeshSet: `compute_selection_by_condition_per_vertex(condselect="(a*x+b*y+c*z+d) < 4")` with the refined plane; `meshing_remove_selected_vertices`; then step 2 again to drop fragments freed by the cut; save `chassis_scan_nofloor.ply` binary. Apply the same condition and fragment removal to the 5 M and 1 M working meshes and save `chassis_scan_nofloor_5M.stl` and `chassis_scan_nofloor_1M.stl` | Surface area falls by 2.0–3.5 m²; largest component holds over 70% of faces |
| 6 Initial symmetry plane | On the vertices of `chassis_scan_nofloor_1M.stl`: PCA long axis `L` projected perpendicular to `Z`; initial normal `Y = Z x L`; plane through the centroid | — |
| 7 Symmetry refinement | Voxel-downsample to 4 mm, normals with radius 12 mm and 30 neighbours. For each max-correspondence distance in `[40, 20, 10, 6, 6]`: reflect the cloud through the current plane (`R = I - 2 n n^T`, `t = -2 d n`), ICP point-to-plane (max 200 iterations) reflected onto original, compose `S = T_icp @ M`, new normal = real eigenvector of `S[:3,:3]` with eigenvalue nearest -1, new offset `d = -(t_S . n) / 2` | Final fitness at 6 mm at least 0.45; final inlier RMSE under 4.0 mm; last iteration changes the normal by under 0.05° |
| 8 Axes | `Y` = refined normal orthogonalised to `Z`; `X = Y x Z`; if the mean of the top 1% of vertices by height (the handlebars) has negative X, negate both X and Y | `det([X Y Z]) = +1` |
| 9 Rear axle | In the provisional frame (origin at centroid), take vertices with X between (rear-most 0.5th percentile + 100) and (+800), abs(Y) under 480, Z between 150 and 480 from `chassis_scan_nofloor_5M.stl`; write a PLY with normals; run CloudCompare RANSAC per section 4.6 with `CYLINDER` only and `SUPPORT_POINTS 400`; keep cylinders whose axis is within 8° of Y, radius 15–130 mm, support over 2000 | Exactly two kept, one each side of Y = 0, radius 20–30 mm, X within 5 mm of each other, Z 270–330 mm |
| 10 Origin | X of the mean of the two axle-housing centres; Y from the symmetry plane; Z from the floor. Build `T_scan_to_datum` (4x4) and apply it to the floor-free full-res mesh and to the floor-free 5 M and 1 M meshes; save `chassis_datum_full.ply`, `chassis_datum_5M.stl`, `chassis_datum_1M.stl`, then decimate the 1 M to 200 k as `chassis_datum_200k.stl` | The transform agrees with `artefacts/datum-reference.json`: each axis vector within 0.5°, translation within 5 mm |
| 11 Report | `data/derived/datum.json` (schema below) copied to `artefacts/datum.json`; renders `artefacts/datum-top.png` and `datum-side.png` at 2 mm per pixel with a 250 mm grid | Files exist; renders show the floor at Z = 0 and the rear wheels centred on X = 0 |

`datum.json` schema:

```json
{
  "frame": "ISO 8855, origin on floor plane and symmetry plane at rear axle housing X",
  "T_scan_to_datum": [[...4 rows of 4...]],
  "X": [..], "Y": [..], "Z": [..],
  "floor": {"inliers_fraction": 0.0, "rms_mm": 0.0},
  "symmetry": {"rotation_from_pca_deg": 0.0, "icp_final_fitness": 0.0, "icp_final_rmse_mm": 0.0},
  "rear_axle_housing": {"left": {"r": 0, "y": 0, "z": 0, "rms": 0}, "right": {...}, "x_span_mm": 0.0},
  "faces": {"loaded": 0, "after_fragments": 0, "after_floor": 0},
  "outputs": {"full_ply": "...", "5M": "...", "1M": "...", "200k": "..."}
}
```

### 4.4 Crop regions — `pipeline/crops.toml`, verbatim

Boxes are axis-aligned in the datum frame, millimetres, `[min, max]`. Expected fraction is the share
of above-floor vertices (Z over 6 mm) of `chassis_datum_5M.stl` inside the box, measured 2026-09-14;
the crop step computes the same quantity on the same mesh and verifies against it.

```toml
[engine-bay]
x = [400, 1100]
y = [-350, 350]
z = [80, 800]
expected_fraction = 0.1204

[tank-mounts]
x = [300, 1200]
y = [-250, 250]
z = [620, 1000]
expected_fraction = 0.0819

[front-flange]
x = [950, 1350]
y = [-200, 200]
z = [200, 650]
expected_fraction = 0.1047

[rear-flange]
x = [300, 650]
y = [-250, 250]
z = [150, 550]
expected_fraction = 0.0442

[duct-route]
x = [450, 1150]
y = [-180, 180]
z = [150, 800]
expected_fraction = 0.0971

[rear-axle]
x = [-150, 150]
y = [-480, 480]
z = [150, 480]
expected_fraction = 0.1112
```

Crop output per region: `<region>_full.ply` (faces of `chassis_datum_full.ply` whose centroid is in
the box, for the fit stage), `<region>_pts.ply` (unique vertices of `chassis_datum_5M.stl` in the box
with their face normals, binary, for CloudCompare - the density section 5.5 was measured at),
`<region>_silhouette.png` (plan and side, 0.6 mm per pixel, from the 5 M points).

### 4.5 Segment — CloudCompare RANSAC

One invocation per region, from the mesh venv via `subprocess`, with `cloudcompare_exe` from the
config:

```text
CloudCompare.exe -SILENT -NO_TIMESTAMP -AUTO_SAVE OFF -C_EXPORT_FMT PLY -M_EXPORT_FMT PLY
  -O <region>_pts.ply
  -RANSAC EPSILON_ABSOLUTE 0.6 BITMAP_EPSILON_ABSOLUTE 4.0 SUPPORT_POINTS 300
          MAX_NORMAL_DEV 15 PROBABILITY 0.01 ENABLE_PRIMITIVE PLANE CYLINDER
          OUT_CLOUD_DIR <ransac>/<region>/clouds OUT_MESH_DIR <ransac>/<region>/meshes
          OUTPUT_INDIVIDUAL_SUBCLOUDS OUTPUT_INDIVIDUAL_PRIMITIVES
```

Parse: for each mesh `..._CYLINDER_NNNN.ply` or `..._PLANE_NNNN.ply`, the paired cloud is
`clouds/<same stem>_cloud.ply`. Cylinder axis = eigenvector of the largest eigenvalue of the mesh
vertex covariance; radius = median perpendicular distance of mesh vertices from that axis; plane
normal = eigenvector of the smallest eigenvalue. Residual = RMS of the paired cloud's points against
the primitive. Write `artefacts/primitives-<region>.json`: a list of
`{kind, index, support, radius, length, axis, centre, rms, p95}` sorted by support.

Accept a cylinder as a tube candidate when radius is within the calliper bracket in
`config.local.toml` (`tube_radii_mm`, default `[[11, 16], [17, 20], [22, 26]]` until the owner
supplies callipers) and `rms` under 1.2 mm; accept a plane when `rms` under 0.6 mm and support over
500.

### 4.6 Fit — refinement on full-resolution points

For each accepted primitive: take the full-res crop's points within 3 mm of the RANSAC primitive.
Cylinder: axis = null direction of the face-normal covariance (smallest eigenvector of `N^T N`),
then a least-squares circle in the plane perpendicular to the axis, trimmed at 3 robust sigma for 8
iterations. Plane: least-squares plane, same trimming. Write `artefacts/interfaces.json`:

```json
{"region": "engine-bay", "primitives": [
  {"id": "engine-bay/cyl/007", "kind": "cylinder", "axis": [..], "point": [..], "radius": 0.0,
   "length": 0.0, "support": 0, "rms": 0.0, "p95": 0.0, "accepted": true}
]}
```

Accept when a cylinder's refined `rms` is under 0.8 mm and a plane's under 0.5 mm; otherwise keep
the row with `accepted: false` and the reason. Render one deviation image per region: points
coloured by signed residual, -1 to +1 mm.

---

## 5. Measured constraints — measured 2026-09-14

All on the owner's workstation: i7-12700KF, 20 threads, 31.8 GB RAM, GTX 1060 3 GB, Windows 11,
Python 3.12.10, pwsh 7.6.6, winget 1.29. The full-res STL is local and reads sequentially at
626 MB/s (PowerShell FileStream, 256 MB in 0.4 s).

### 5.1 Full-res file size and memory

| | |
|---|---|
| `pymeshlab` load of the 1.75 GB STL | 154 s, 10.7 GB RSS |
| Fragment removal + duplicate/null cleanup | 20 s, 11.9 GB |
| Decimate 35 M to 5 M (quadric, parameters as 4.3 step 3) | 435 s, about 18 GB peak observed by `Get-Process` |
| Decimate 5 M to 1 M | 59 s, 6.6 GB |
| `numpy.fromfile` on the 1.75 GB STL | returned zero records; chunked `f.readinto` of 4 M faces per chunk streams the file in 200 s |

**Rules that follow:**

1. One full-res operation at a time. Never run two pymeshlab full-res jobs concurrently.
2. Read full-res STL with pymeshlab or chunked `readinto`, never `np.fromfile`.
3. A full-res stage is a background job with a log; budget 15 minutes per full pass.

### 5.2 Low-res and per-library timings

| Operation | Tool | Time |
|---|---|---|
| Parse low-res STL, unique vertices, connected components | numpy, scipy | 0.2 s, 2.7 s, 0.2 s |
| Read, cluster, decimate to 500 k | Open3D 0.19.0 | 2.5 s, 2.2 s, 19.0 s |
| Load, split, section | trimesh 5.1.0 | 2.4 s, 3.3 s, 0.2 s |
| Load, decimate to 500 k, to 150 k | pymeshlab 2025.7.post1 | 7.9 s, 18.7 s, 4.7 s |
| Floor plane RANSAC on 600 k vertices | Open3D `segment_plane` | 0.3 s |

### 5.3 Scan geometry and fit quality

| | |
|---|---|
| Low-res: 126 connected pieces, largest 77% of faces; 58 630 boundary edges; 0 non-manifold edges; 0 degenerate faces | numpy + scipy `connected_components` |
| Full-res: fragments under 0.01% of faces total 46 539 faces (0.13%) | pymeshlab selection filter |
| Floor present in full-res only: 13.3% of 1 M-decimation vertices, plane RMS 1.26 mm, normal 2.7° off the scan's Z | Open3D `segment_plane` |
| Round cross-member, full-res crop: r = 12.94 mm, 92.6% inliers, RMS 0.40 mm, p95 0.80 mm | normals-axis + trimmed circle fit |
| Same member, low-res: r = 13.47 mm, RMS 0.88 mm | same |
| Lower rail by box crop, full-res: RMS 4.04 mm because a welded plate sits inside the crop | same — this is why segmentation precedes fitting |

### 5.4 Datum fit

| | |
|---|---|
| Mirror-ICP schedule `[40, 20, 10, 6, 6]` mm on the floor-free 1 M mesh, 282 550 points after 4 mm voxel downsampling | fitness 0.864 / 0.787 / 0.656 / 0.539 / 0.539; RMSE 11.49 / 7.08 / 4.41 / 3.18 / 3.18 mm; total rotation from PCA 12.08°; last iteration change 0.000° |
| The same ICP from PCA with a single 8 mm distance | stalled at fitness 0.13 after 5.3° — never use a single fine distance |
| Rear axle housing by RANSAC in the rear slab | two cylinders: r 24.6 mm at y +237.0, z 296.6, RMS 1.05; r 23.9 mm at y -210.4, z 302.7, RMS 1.15; X differs by 0.8 mm |
| Two vertical r 63–65 mm cylinders at x 204, y +378.2 / -382.2 | symmetric within 4 mm: independent confirmation of the symmetry plane |
| Rear tyre circle fits (convex hull in XZ) | right: r 299–309, RMS 0.85–4.7; left: r 227–292, RMS 4.7–13 (a seventh of the points). Front tyres: r 359–669, RMS 9–45 — unusable for a datum |

The resulting transform is `artefacts/datum-reference.json`.

### 5.5 Segmentation

| | |
|---|---|
| CloudCompare 2.13.2 (winget `CloudCompare.CloudCompare`) with `QRANSAC_SD_PLUGIN.dll`, command-line as in 4.5, engine-bay crop of 390 564 points with normals from the 5 M mesh | 52 s; 100 primitives: 61 cylinders, 39 planes; 42.8% of points assigned; 38 cylinders with r 11–16 mm, median RMS 0.72 mm; planes RMS 0.25 mm |
| Same on the rear slab, cylinders only, `SUPPORT_POINTS 400`, 405 161 points | 54 cylinders; the two axle housings and one 13.0 mm cross-member along Y |
| `pyransac3d.Cylinder` on 750 points of one tube | radius agreed with the circle fit (13.3 vs 13.47) but kept 19.7% inliers; its docs say the cylinder model performs poorly on real data. Planes only. |

### 5.6 Toolsets

| | |
|---|---|
| PyPI latest, `pip index versions` | pymeshlab 2025.7.post1, open3d 0.19.0, trimesh 5.1.0, pyransac3d 0.7.0, build123d 0.11.1, draftwright 0.4.29, cadquery-ocp-novtk 8.0.1.0.0 |
| `pip install --dry-run build123d==0.11.1` on Python 3.12 Windows | resolves cadquery-ocp-novtk 7.9.3.1.1 and ocp-proxy 7.9.3.1.1 |
| `pip install --dry-run draftwright` | resolves build123d 0.10.0 and cadquery-ocp 7.8.1.1.post1 with vtk 9.3.1 — incompatible with the pin above, hence its own venv |
| winget | `CloudCompare.CloudCompare 2.13.2`, `CNRISTI.MeshLab 2025.07`, `FreeCAD.FreeCAD 1.1.3` |
| `uv` | not installed; use `python -m venv` |
| Fusion | installed under the user's Autodesk webdeploy folder; not used by this plan |

### 5.7 Per-item cost — what sets every item cap

An item is one pipeline step: write or adapt one function, run it, read its output, record the
result. Measured on this session's own spikes:

| | |
|---|---|
| Script size per step (`wc -c` on eight spike scripts) | 1 350–3 289 bytes, about 340–820 tokens |
| Run output per step (task logs; the RANSAC table) | 180–2 500 bytes, about 45–620 tokens |
| Status and batch report per step | about 500 tokens |
| Reasoning allowance | 2 000 tokens |
| Measured cost of one item | 4 000 tokens |
| Working budget (half a 200 k window) | 100 000 tokens |
| **Item cap per session** | **25** |

**Rules that follow:**

1. No work package exceeds 25 items. Every WP below has 12 or fewer.
2. Reaching the cap is a normal ending: `state: paused`, `resume-from` set, and the same starter
   prompt resumes it.
3. Never read a full-res log or a whole primitive JSON into context; read counts and the first
   twenty rows.

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
`docs/thrifty/2026-09-14-scan-pipeline/findings/WP-NN.md` — its own file, never a shared one — and
carries on:

```markdown
| WP | Where | What was found | Evidence | Suggested owner |
|----|-------|----------------|----------|-----------------|
```

Findings are triaged by the owner, not by the finding session.

---

## 8. Work packages

**Order:** 1 and 2 in parallel -> 3 -> 4 -> 5 -> 6. WP-02 has no dependants in this plan.

**Precondition — this plan must be merged to `main` before WP1 starts.** Every starter prompt
resolves the repo root of `electric-butterfly/equad` for itself and opens by reading this file from
it. Until the plan is on `main`, that path does not exist and every session stops at step one.

**The WPs chain through committed artefacts, so each PR must merge before its dependants run:**

One row per file. Short forms such as `artefacts/datum.json` in this plan always mean the file under
`docs/thrifty/2026-09-14-scan-pipeline/`. Files under `data/` are git-ignored and regenerated by the
script that produces them; they reach a later session by being re-run, not by a PR.

| Artefact | Produced by | Consumed by |
|---|---|---|
| `docs/thrifty/2026-09-14-scan-pipeline/artefacts/datum-reference.json` | this plan | WP-03 |
| `.gitignore` | WP-01 | WP-02, WP-03, WP-04, WP-05, WP-06 |
| `pipeline/README.md` | WP-01 | the owner |
| `pipeline/requirements-mesh.txt` | WP-01 | WP-03, WP-04, WP-05, WP-06 |
| `pipeline/config.example.toml` | WP-01 | the owner |
| `pipeline/common.py` | WP-01 | WP-03, WP-04, WP-05, WP-06 |
| `docs/thrifty/2026-09-14-scan-pipeline/artefacts/toolsets-mesh.md` | WP-01 | the owner |
| `pipeline/config.local.toml` | the owner | WP-03, WP-04, WP-05, WP-06 |
| `pipeline/requirements-cad.txt` | WP-02 | the next plan |
| `pipeline/requirements-draft.txt` | WP-02 | the next plan |
| `docs/thrifty/2026-09-14-scan-pipeline/artefacts/toolsets-cad.md` | WP-02 | the next plan |
| `pipeline/condition.py` | WP-03 | WP-04, WP-05, WP-06 |
| `data/derived/datum.json` | WP-03 | WP-04 |
| `docs/thrifty/2026-09-14-scan-pipeline/artefacts/datum.json` | WP-03 | WP-04 |
| `artefacts/datum.json` | WP-03 | WP-04 |
| `docs/thrifty/2026-09-14-scan-pipeline/artefacts/datum-top.png` | WP-03 | the owner |
| `docs/thrifty/2026-09-14-scan-pipeline/artefacts/datum-side.png` | WP-03 | the owner |
| `docs/thrifty/2026-09-14-scan-pipeline/artefacts/condition-report.md` | WP-03 | the owner |
| `artefacts/condition-report.md` | WP-03 | the owner |
| `data/derived/chassis_datum_full.ply` | WP-03 | WP-04, WP-06 |
| `pipeline/crops.toml` | WP-04 | WP-05, WP-06 |
| `pipeline/crop.py` | WP-04 | WP-05, WP-06 |
| `docs/thrifty/2026-09-14-scan-pipeline/artefacts/crops-report.md` | WP-04 | the owner |
| `artefacts/crops-report.md` | WP-04 | the owner |
| `docs/thrifty/2026-09-14-scan-pipeline/artefacts/crop-engine-bay.png` | WP-04 | the owner |
| `docs/thrifty/2026-09-14-scan-pipeline/artefacts/crop-tank-mounts.png` | WP-04 | the owner |
| `docs/thrifty/2026-09-14-scan-pipeline/artefacts/crop-front-flange.png` | WP-04 | the owner |
| `docs/thrifty/2026-09-14-scan-pipeline/artefacts/crop-rear-flange.png` | WP-04 | the owner |
| `docs/thrifty/2026-09-14-scan-pipeline/artefacts/crop-duct-route.png` | WP-04 | the owner |
| `docs/thrifty/2026-09-14-scan-pipeline/artefacts/crop-rear-axle.png` | WP-04 | the owner |
| `data/crops/engine-bay/engine-bay_pts.ply` | WP-04 | WP-05 |
| `data/crops/engine-bay/engine-bay_full.ply` | WP-04 | WP-06 |
| `pipeline/segment.py` | WP-05 | WP-06 |
| `docs/thrifty/2026-09-14-scan-pipeline/artefacts/primitives-engine-bay.json` | WP-05 | WP-06 |
| `docs/thrifty/2026-09-14-scan-pipeline/artefacts/primitives-tank-mounts.json` | WP-05 | WP-06 |
| `docs/thrifty/2026-09-14-scan-pipeline/artefacts/primitives-front-flange.json` | WP-05 | WP-06 |
| `docs/thrifty/2026-09-14-scan-pipeline/artefacts/primitives-rear-flange.json` | WP-05 | WP-06 |
| `docs/thrifty/2026-09-14-scan-pipeline/artefacts/primitives-duct-route.json` | WP-05 | WP-06 |
| `docs/thrifty/2026-09-14-scan-pipeline/artefacts/primitives-rear-axle.json` | WP-05 | WP-06 |
| `docs/thrifty/2026-09-14-scan-pipeline/artefacts/segment-report.md` | WP-05 | the owner |
| `artefacts/segment-report.md` | WP-05 | the owner |
| `pipeline/fit.py` | WP-06 | the next plan |
| `docs/thrifty/2026-09-14-scan-pipeline/artefacts/interfaces.json` | WP-06 | the next plan |
| `artefacts/interfaces.json` | WP-06 | the next plan |
| `docs/thrifty/2026-09-14-scan-pipeline/artefacts/fit-report.md` | WP-06 | the owner |
| `artefacts/fit-report.md` | WP-06 | the owner |
| `docs/thrifty/2026-09-14-scan-pipeline/artefacts/deviation-engine-bay.png` | WP-06 | the owner |
| `docs/thrifty/2026-09-14-scan-pipeline/artefacts/deviation-tank-mounts.png` | WP-06 | the owner |
| `docs/thrifty/2026-09-14-scan-pipeline/artefacts/deviation-front-flange.png` | WP-06 | the owner |
| `docs/thrifty/2026-09-14-scan-pipeline/artefacts/deviation-rear-flange.png` | WP-06 | the owner |
| `docs/thrifty/2026-09-14-scan-pipeline/artefacts/deviation-duct-route.png` | WP-06 | the owner |
| `docs/thrifty/2026-09-14-scan-pipeline/artefacts/deviation-rear-axle.png` | WP-06 | the owner |

| WP | Title | Model | Effort | Item cap | Depends on | Writes |
|---|---|---|---|---|---|---|
| 1 | Install the mesh toolset | Sonnet | low | 9 | — | `.gitignore`, `pipeline/README.md`, `pipeline/requirements-mesh.txt`, `pipeline/config.example.toml`, `pipeline/common.py`, `artefacts/toolsets-mesh.md`, status |
| 2 | Install the CAD toolset | Sonnet | low | 8 | — | `pipeline/requirements-cad.txt`, `pipeline/requirements-draft.txt`, `artefacts/toolsets-cad.md`, status |
| 3 | Condition the scan to the vehicle datum | Sonnet | medium | 11 | 1, owner config | `pipeline/condition.py`, `artefacts/datum.json`, `artefacts/datum-top.png`, `artefacts/datum-side.png`, `artefacts/condition-report.md`, status |
| 4 | Crop the six regions | Sonnet | low | 8 | 3 | `pipeline/crops.toml`, `pipeline/crop.py`, `artefacts/crops-report.md`, `artefacts/crop-<region>.png`, status |
| 5 | Segment each region with RANSAC | Sonnet | low | 8 | 4 | `pipeline/segment.py`, `artefacts/primitives-<region>.json`, `artefacts/segment-report.md`, status |
| 6 | Fit and verify the primitives | Sonnet | medium | 8 | 5 | `pipeline/fit.py`, `artefacts/interfaces.json`, `artefacts/fit-report.md`, `artefacts/deviation-<region>.png`, status |

---

### WP1 — Install the mesh toolset

**Model:** Sonnet · **Effort:** low · **Item cap:** 9 (from section 5.7; the WP has 9 items) ·
**Branch:** `thrifty/2026-09-14-scan-pipeline/wp-01` · **Writes:** `.gitignore`,
`pipeline/README.md`, `pipeline/requirements-mesh.txt`, `pipeline/config.example.toml`,
`pipeline/common.py`, `docs/thrifty/2026-09-14-scan-pipeline/artefacts/toolsets-mesh.md`, status

**Goal.** A pinned mesh venv, CloudCompare and MeshLab installed, the config template and the shared
helper module in place, every tool proven by a smoke test that writes a file and reads it back.

**Done when.** `.venv-mesh/Scripts/python -c "import pymeshlab, open3d, trimesh, pyransac3d, scipy, numpy, tomllib"`
exits 0 and prints the pinned versions; a synthetic 12.5 mm-radius cylinder point cloud run through
CloudCompare RANSAC returns one cylinder whose measured radius is within 0.5 mm of 12.5;
`artefacts/toolsets-mesh.md` lists every version and the smoke results with their command output.

```
Install the mesh-side toolset for the eQuad scan pipeline and prove each tool works.
Repo: electric-butterfly/equad. Work from the root of your local clone - find it, do not
assume a path.
Make NO writes outside this repo except the winget installs named in TASK and the venv
inside the repo root.

PRECONDITION 1 - right tree. Run `git rev-parse --show-toplevel` and
`git remote get-url origin`. origin must be electric-butterfly/equad, and every path
below is relative to the toplevel the first command printed. If origin names a
different repo, or git errors because this is not a work tree, say so and STOP,
and ask the owner to repoint the session. Do not clone it, do not search the
filesystem for a copy, do not guess a path. Write nothing.

PRECONDITION 2 - plan present. Confirm docs/thrifty/2026-09-14-scan-pipeline/plan.md exists in
that tree. If it does not, the plan PR has not merged - say so and STOP. Write
nothing: the directory you would write to does not exist either. Do not improvise
a substitute.

BRANCH. Your branch is thrifty/2026-09-14-scan-pipeline/wp-01 - derived from the plan, never
invented. Before touching anything:
  git fetch origin
  git ls-remote --exit-code --heads origin thrifty/2026-09-14-scan-pipeline/wp-01
A missing branch means a fresh start. Cut it from origin/main:
  git switch -c thrifty/2026-09-14-scan-pipeline/wp-01 origin/main
Write docs/thrifty/2026-09-14-scan-pipeline/status/WP-01.md with state: started. Commit it
("chore(thrifty): WP-01 start") and push -u. Do NOT open a PR yet. That commit only
stakes the branch so a dead session is still findable. The PR comes once, at the
very end of this prompt.
An existing branch means a RESUME, not a new start. Check it out:
  git switch -c thrifty/2026-09-14-scan-pipeline/wp-01 origin/thrifty/2026-09-14-scan-pipeline/wp-01
Read that status file and carry on from its resume-from, setting state:
in-progress. Do not start over and do not re-apply what is already done.
Never commit to main.

THEN read docs/thrifty/2026-09-14-scan-pipeline/plan.md section 4.1, section 4.2,
section 5.6 and section 6.

Load: ToolSearch query "select:Read,Write,Edit,Bash,Grep"

Do NOT load or call WebSearch or WebFetch. Every version is pinned in section 4.1 and
section 5.6; a search invites a newer version that breaks the pins downstream.
Do NOT load or call the Agent tool. This WP is nine sequential installs; a subagent
cannot report what a command printed.

TASK. Nine items, in this order. Use `python -m venv` (uv is not installed) and pwsh 7
for winget. Windows.
  1. Write .gitignore exactly as section 4.1 shows.
  2. Create .venv-mesh at the repo root with `python -m venv .venv-mesh`; upgrade pip.
  3. Write pipeline/requirements-mesh.txt with the pins in section 4.1 (numpy and
     scipy unpinned, psutil unpinned, the rest pinned) and install it into
     .venv-mesh.
  4. `winget install --id CloudCompare.CloudCompare --exact --silent
     --accept-package-agreements --accept-source-agreements`. Then locate
     CloudCompare.exe under the Program Files directory (use the environment
     variable, never a literal path) and confirm plugins/QRANSAC_SD_PLUGIN.dll sits
     beside it.
  5. `winget install --id CNRISTI.MeshLab --exact --silent
     --accept-package-agreements --accept-source-agreements`.
  6. Write pipeline/config.example.toml exactly as section 4.2 shows.
  7. Write pipeline/common.py with four functions: load_config() (reads
     pipeline/config.local.toml with tomllib, resolves data_root against
     `git rev-parse --show-toplevel`, raises if a key is missing or a file absent);
     stream_stl(path, chunk_faces=4_000_000) (a generator yielding (normals, vertices)
     numpy arrays per chunk using f.readinto - never np.fromfile);
     silhouette_png(points, path, axes=(0,1), depth_axis=2, mm_per_px=1.0)
     (numpy-only PNG writer via zlib: nearest-surface depth shading);
     fit_circle_trimmed(x, y, iterations=8) (Kasa least squares with 3-sigma robust
     trimming, returns centre, radius, inlier mask, rms).
  8. Smoke test, from .venv-mesh: (a) import the six packages and print versions;
     (b) generate 20 000 points on a cylinder of radius 12.5 mm, length 200 mm, with
     outward normals and 0.1 mm gaussian noise, write PLY with normals via Open3D,
     run CloudCompare RANSAC with the exact command of section 4.5 (CYLINDER only),
     parse the one output mesh per section 4.5 and print its radius; (c) pymeshlab
     creates a sphere, decimates it to 500 faces, saves STL, reloads it, prints the
     face count.
  9. Write pipeline/README.md (how to create the venv, fill config.local.toml, and
     run each stage - stages 3 to 6 are documented as "written by WP-03..06") and
     docs/thrifty/2026-09-14-scan-pipeline/artefacts/toolsets-mesh.md with every
     version, the CloudCompare and MeshLab install paths' parent folder names (not
     full paths), and the smoke outputs verbatim.
Hard cap: 9 items this session. 9 is the measured budget from section 5, not a
target - reaching it is a normal ending, not a failure.

PROCEDURE:
1. Read the nine items above and write them out as your list.
2. CANARY item 1 only. Stop. Show the .gitignore content and `git status --short`.
   Wait for the go-ahead.
3. Then items 2-9 in one batch of eight. After the batch: report, update the status
   file (progress, resume-from, updated), commit, push. Serial calls only. No PR yet.
   If a winget install fails, record the exact error in the findings file and the
   status Notes, mark the item skipped, and continue - the venv items do not depend
   on it.
4. If you hit the hard cap, or context runs short, or the owner pauses you: write
   state: paused with resume-from and pause-reason, commit, push, and STOP. Do
   NOT open a PR yet - that is the job of the session that resumes this prompt.

VERIFY BEFORE FINISHING:
  .venv-mesh/Scripts/python -c "import pymeshlab, open3d, trimesh, pyransac3d; print(open3d.__version__, trimesh.__version__)"
     -> expect "0.19.0 5.1.0"
  smoke (b) parsed cylinder radius -> expect between 12.0 and 13.0 mm
  smoke (c) reloaded face count -> expect 500
  git status --short -> only the files listed under Writes for WP1. Add files by
    name, never `git add -A` or `git add .`; .venv-mesh/ must not appear once
    .gitignore is in place
Report the numbers. If any does not match, say so and do not claim completion.

SCOPE FENCE. You may create the files listed under Writes and the venv. Do NOT
change README.md, docs/scan-to-cad-options.md, docs/figures, or anything under
docs/thrifty other than your own status and findings files and toolsets-mesh.md. Do
NOT install FreeCAD, build123d or draftwright - that is WP-02. Do NOT write
config.local.toml - the owner does. Out-of-scope observations go in
docs/thrifty/2026-09-14-scan-pipeline/findings/WP-01.md, not into an action.

STOP CONDITION: when every item in your list has been handled once, or the hard
cap is reached. Do not look for more work.

Write docs/thrifty/2026-09-14-scan-pipeline/status/WP-01.md per section 6 of the plan.
On a terminal state - done, blocked, stopped, or canary-waiting - commit to your
branch cut from origin/main, push it, and open one PR. Then STOP - the owner merges.
Do NOT add commits to a PR that is already open.
```

---

### WP2 — Install the CAD toolset

**Model:** Sonnet · **Effort:** low · **Item cap:** 8 (from section 5.7; the WP has 8 items) ·
**Branch:** `thrifty/2026-09-14-scan-pipeline/wp-02` · **Writes:**
`pipeline/requirements-cad.txt`, `pipeline/requirements-draft.txt`,
`docs/thrifty/2026-09-14-scan-pipeline/artefacts/toolsets-cad.md`, status

**Goal.** build123d, draftwright and FreeCAD with the SheetMetal workbench installed for the next
plan, each proven by a smoke test that writes a STEP, PDF or DXF and reads it back. No pipeline
script uses them in this plan.

**Done when.** A 10 x 20 x 30 mm build123d box exported to STEP re-imports with volume 6000 mm³
within 0.01; draftwright writes a PDF over 10 kB from that STEP; `FreeCADCmd` imports `Part` and
`SheetMetalNewUnfolder` without error; `artefacts/toolsets-cad.md` records every version and output.

```
Install the CAD-side toolset for the eQuad pipeline and prove each tool writes and reads a file.
Repo: electric-butterfly/equad. Work from the root of your local clone - find it, do not
assume a path.
Make NO writes outside this repo except the winget install, the FreeCAD user Mod
directory, and the two venvs inside the repo root.

PRECONDITION 1 - right tree. Run `git rev-parse --show-toplevel` and
`git remote get-url origin`. origin must be electric-butterfly/equad, and every path
below is relative to the toplevel the first command printed. If origin names a
different repo, or git errors because this is not a work tree, say so and STOP,
and ask the owner to repoint the session. Do not clone it, do not search the
filesystem for a copy, do not guess a path. Write nothing.

PRECONDITION 2 - plan present. Confirm docs/thrifty/2026-09-14-scan-pipeline/plan.md exists in
that tree. If it does not, the plan PR has not merged - say so and STOP. Write
nothing: the directory you would write to does not exist either. Do not improvise
a substitute.

BRANCH. Your branch is thrifty/2026-09-14-scan-pipeline/wp-02 - derived from the plan, never
invented. Before touching anything:
  git fetch origin
  git ls-remote --exit-code --heads origin thrifty/2026-09-14-scan-pipeline/wp-02
A missing branch means a fresh start. Cut it from origin/main:
  git switch -c thrifty/2026-09-14-scan-pipeline/wp-02 origin/main
Write docs/thrifty/2026-09-14-scan-pipeline/status/WP-02.md with state: started. Commit it
("chore(thrifty): WP-02 start") and push -u. Do NOT open a PR yet. That commit only
stakes the branch so a dead session is still findable. The PR comes once, at the
very end of this prompt.
An existing branch means a RESUME, not a new start. Check it out:
  git switch -c thrifty/2026-09-14-scan-pipeline/wp-02 origin/thrifty/2026-09-14-scan-pipeline/wp-02
Read that status file and carry on from its resume-from, setting state:
in-progress. Do not start over and do not re-apply what is already done.
Never commit to main.

THEN read docs/thrifty/2026-09-14-scan-pipeline/plan.md section 4.1, section 5.6 and
section 6.

Load: ToolSearch query "select:Read,Write,Bash,Grep"

Do NOT load or call WebSearch or WebFetch. The pins are in section 4.1 and 5.6; a
search invites a version that breaks them.
Do NOT load or call Edit. This WP creates three new files and changes nothing that
exists; an edit tool invites fixing what you find outside the fence.

TASK. Eight items, in this order. Windows, pwsh 7, `python -m venv`.
  1. Write pipeline/requirements-cad.txt: `build123d==0.11.1`. Create .venv-cad,
     upgrade pip, install it. Record the resolved cadquery-ocp-novtk version.
  2. Write pipeline/requirements-draft.txt: `draftwright==0.4.29`. Create
     .venv-draft, upgrade pip, install it. It pulls its own older build123d; that is
     expected and is why it has its own venv.
  3. `winget install --id FreeCAD.FreeCAD --exact --silent
     --accept-package-agreements --accept-source-agreements` (version 1.1.3 per
     section 5.6). Locate FreeCADCmd.exe under the Program Files directory (use the
     environment variable, never a literal path).
  4. Ask FreeCAD where its user data lives:
     FreeCADCmd -c "import FreeCAD; print(FreeCAD.getUserAppDataDir())". Clone
     https://github.com/shaise/FreeCAD_SheetMetal into <that>/Mod/SheetMetal. If
     that folder already exists, leave it. Record the commit hash you cloned.
  5. Smoke build123d from .venv-cad: Box(10, 20, 30), export_step to a temp file
     inside data/ (create data/ if absent - it is git-ignored), import_step it back,
     print the volume.
  6. Smoke draftwright from .venv-draft: run its command-line entry point on the STEP
     from item 5 to produce a PDF in data/. Print the PDF size in bytes. If the entry
     point name is unclear, read `python -m pip show -f draftwright` for the console
     script name; do not guess.
  7. Smoke FreeCAD: FreeCADCmd -c "import Part, SheetMetalNewUnfolder; print('ok')".
  8. Write docs/thrifty/2026-09-14-scan-pipeline/artefacts/toolsets-cad.md with every
     version, the FreeCAD install folder's parent name (not a full path), the
     SheetMetal commit hash, and every smoke output verbatim.
Hard cap: 8 items this session. 8 is the measured budget from section 5, not a
target - reaching it is a normal ending, not a failure.

PROCEDURE:
1. Read the eight items above and write them out as your list.
2. CANARY item 1 only. Stop. Show `python -m pip freeze` from .venv-cad. Wait for the
   go-ahead.
3. Then items 2-8 in one batch. After the batch: report, update the status file
   (progress, resume-from, updated), commit, push. Serial calls only. No PR yet.
   If a winget or git clone step fails, record the exact error in findings and
   status Notes, mark it skipped, continue with the venv items.
4. If you hit the hard cap, or context runs short, or the owner pauses you: write
   state: paused with resume-from and pause-reason, commit, push, and STOP. Do
   NOT open a PR yet - that is the job of the session that resumes this prompt.

VERIFY BEFORE FINISHING:
  item 5 volume -> expect 6000.00 within 0.01
  item 6 PDF size -> expect greater than 10000 bytes
  item 7 output -> expect "ok"
  git status --short -> the tracked changes are only pipeline/requirements-cad.txt,
    pipeline/requirements-draft.txt, artefacts/toolsets-cad.md and your status and
    findings files. Untracked .venv-cad/, .venv-draft/ and data/ may also show if
    WP-01's .gitignore has not merged yet: leave them untracked. Add files by name,
    never `git add -A` or `git add .`
Report the numbers. If any does not match, say so and do not claim completion.

SCOPE FENCE. You may create the three files under Writes and the two venvs. Do NOT
touch .gitignore, pipeline/README.md, pipeline/common.py or anything WP-01 writes,
even if WP-01 has not merged yet - your PRs are independent. Do NOT install the
Fusion MCP or any Fusion add-in. Out-of-scope observations go in
docs/thrifty/2026-09-14-scan-pipeline/findings/WP-02.md, not into an action.

STOP CONDITION: when every item in your list has been handled once, or the hard
cap is reached. Do not look for more work.

Write docs/thrifty/2026-09-14-scan-pipeline/status/WP-02.md per section 6 of the plan.
On a terminal state - done, blocked, stopped, or canary-waiting - commit to your
branch cut from origin/main, push it, and open one PR. Then STOP - the owner merges.
Do NOT add commits to a PR that is already open.
```

---

### WP3 — Condition the scan to the vehicle datum

**Model:** Sonnet · **Effort:** medium · **Item cap:** 11 (from section 5.7; the WP has 11 items) ·
**Branch:** `thrifty/2026-09-14-scan-pipeline/wp-03` · **Writes:** `pipeline/condition.py`,
`docs/thrifty/2026-09-14-scan-pipeline/artefacts/datum.json`, `artefacts/datum-top.png`,
`artefacts/datum-side.png`, `artefacts/condition-report.md`, status

**Goal.** Implement section 4.3 as one script with one flag per step, run it end to end, and
reproduce the reference datum.

**Done when.** `data/derived/datum.json` exists and its `T_scan_to_datum` agrees with
`artefacts/datum-reference.json` to within 0.5° per axis vector and 5 mm in translation;
`chassis_datum_full.ply`, `_5M.stl`, `_1M.stl` and `_200k.stl` exist with the face counts the report
states; the two renders show the floor at Z = 0 and the rear wheels centred on X = 0.

```
Implement and run the condition stage of the eQuad scan pipeline: fragments, floor, symmetry,
rear-axle origin, export.
Repo: electric-butterfly/equad. Work from the root of your local clone - find it, do not
assume a path.
Make NO writes outside this repo. Large outputs go under data_root from the config,
which is inside the repo and git-ignored.

PRECONDITION 1 - right tree. Run `git rev-parse --show-toplevel` and
`git remote get-url origin`. origin must be electric-butterfly/equad, and every path
below is relative to the toplevel the first command printed. If origin names a
different repo, or git errors because this is not a work tree, say so and STOP,
and ask the owner to repoint the session. Do not clone it, do not search the
filesystem for a copy, do not guess a path. Write nothing.

PRECONDITION 2 - plan present. Confirm docs/thrifty/2026-09-14-scan-pipeline/plan.md exists in
that tree. If it does not, the plan PR has not merged - say so and STOP. Write
nothing: the directory you would write to does not exist either. Do not improvise
a substitute.

Confirm pipeline/common.py exists. If it does not, the producing WP's PR has not merged.
Write docs/thrifty/2026-09-14-scan-pipeline/status/WP-03.md with state: blocked and the absent
path in Notes, commit, push, open one PR, and STOP. Do not reconstruct it.
Confirm pipeline/config.local.toml exists and that the two scan paths it names open.
If not, the owner has not written it (plan section 9). Write status WP-03.md with
state: blocked naming pipeline/config.local.toml, commit, push, open one PR, STOP.
Confirm docs/thrifty/2026-09-14-scan-pipeline/artefacts/datum-reference.json exists. When it
is absent: write state: blocked naming it, commit, push, open one PR, and STOP.

BRANCH. Your branch is thrifty/2026-09-14-scan-pipeline/wp-03 - derived from the plan, never
invented. Before touching anything:
  git fetch origin
  git ls-remote --exit-code --heads origin thrifty/2026-09-14-scan-pipeline/wp-03
A missing branch means a fresh start. Cut it from origin/main:
  git switch -c thrifty/2026-09-14-scan-pipeline/wp-03 origin/main
Write docs/thrifty/2026-09-14-scan-pipeline/status/WP-03.md with state: started. Commit it
("chore(thrifty): WP-03 start") and push -u. Do NOT open a PR yet. That commit only
stakes the branch so a dead session is still findable. The PR comes once, at the
very end of this prompt.
An existing branch means a RESUME, not a new start. Check it out:
  git switch -c thrifty/2026-09-14-scan-pipeline/wp-03 origin/thrifty/2026-09-14-scan-pipeline/wp-03
Read that status file and carry on from its resume-from, setting state:
in-progress. Do not start over and do not re-apply what is already done - the
intermediate meshes under data/derived are still on disk.
Never commit to main.

THEN read docs/thrifty/2026-09-14-scan-pipeline/plan.md section 4.2, section 4.3,
section 5.1, section 5.4 and section 6. Read pipeline/common.py in full (it is short).

Load: ToolSearch query "select:Read,Write,Edit,Bash,Grep"

Do NOT load or call WebSearch or WebFetch. Every filter name, parameter and threshold
is in section 4.3; a search invites a different algorithm whose numbers cannot be
compared with the reference.
Do NOT load or call the Agent tool. The full-res steps must run one at a time
(section 5.1) and you must read each step's numbers yourself.

TASK. Eleven items: the eleven steps of section 4.3, each a function in
pipeline/condition.py selectable with --step N and --through N, using
.venv-mesh/Scripts/python. Every step writes its numbers to data/derived/condition-log.jsonl
(one JSON line per step) so a resumed session can skip finished steps. Full-res
steps (1, 2, 3, 5, 10) run as background jobs with a log file; poll the log, do not
sit in a foreground call for 15 minutes.
Hard cap: 11 items this session. 11 is the measured budget from section 5, not a
target - reaching it is a normal ending, not a failure.

PROCEDURE:
1. Write out the eleven steps as your list.
2. CANARY step 1 and step 2 only, on the full-res file. Stop. Report the loaded face
   count, the faces removed and their percentage, and the wall time and RSS. Wait for
   the go-ahead. (Expected: 35 074 344 loaded; about 0.13% removed; about 3 min.)
3. Then steps 3-11, reporting after step 5, after step 9 and after step 11; after
   each report update the status file (progress, resume-from, updated), commit, push.
   Serial calls only. No PR yet. At step 7, if the final fitness is under 0.45 or the
   total rotation from PCA is under 9 degrees or over 15 degrees, STOP and report the
   per-iteration table - do not tune the schedule. At step 9, if the kept cylinder
   count is not exactly two, STOP and report the full cylinder table.
4. If you hit the hard cap, or context runs short, or the owner pauses you: write
   state: paused with resume-from (the next step number) and pause-reason, commit,
   push, and STOP. Do NOT open a PR yet - that is the job of the session that resumes
   this prompt.

VERIFY BEFORE FINISHING:
  For each of X, Y, Z in data/derived/datum.json against artefacts/datum-reference.json:
     angle between the vectors -> expect under 0.5 degrees
  Translation column of T_scan_to_datum, per component -> expect within 5 mm
  Face counts of chassis_datum_5M.stl, _1M.stl, _200k.stl -> expect 4999999, 999999, 199999
  artefacts/datum-top.png: the vertical white grid line at X = 0 passes through both
     rear wheels -> state yes or no from the rendered image
Report the numbers. If any does not match, say so and do not claim completion.

SCOPE FENCE. You may create pipeline/condition.py, the artefacts listed under Writes,
and anything under data/. You may add a helper to pipeline/common.py only if
condition.py cannot work without it, and you say so in the report. Do NOT change
pipeline/config.example.toml, .gitignore, pipeline/README.md, or any file outside
pipeline/ and your own status, findings and artefacts. Do NOT write crops.toml or
crop.py - that is WP-04. Out-of-scope observations go in
docs/thrifty/2026-09-14-scan-pipeline/findings/WP-03.md, not into an action.

STOP CONDITION: when every step in your list has been handled once, or the hard
cap is reached. Do not look for more work.

Write docs/thrifty/2026-09-14-scan-pipeline/status/WP-03.md per section 6 of the plan.
On a terminal state - done, blocked, stopped, or canary-waiting - commit to your
branch cut from origin/main, push it, and open one PR. Then STOP - the owner merges.
Do NOT add commits to a PR that is already open.
```

---

### WP4 — Crop the six regions

**Model:** Sonnet · **Effort:** low · **Item cap:** 8 (from section 5.7; the WP has 8 items) ·
**Branch:** `thrifty/2026-09-14-scan-pipeline/wp-04` · **Writes:** `pipeline/crops.toml`,
`pipeline/crop.py`, `docs/thrifty/2026-09-14-scan-pipeline/artefacts/crops-report.md`,
`artefacts/crop-<region>.png` for six regions, status

**Goal.** Cut the six regions of section 4.4 from the datum-aligned full-res mesh, write each as a
face mesh and a normal-bearing point cloud, and render each so the owner can see what was cut.

**Done when.** `data/crops/<region>/` holds `_full.ply`, `_pts.ply` and `_silhouette.png` for all
six regions; each region's vertex fraction of the above-floor full mesh is within 1.5 percentage
points of `expected_fraction`; `artefacts/crops-report.md` tabulates the six fractions and point
counts and links the six renders.

```
Implement and run the crop stage of the eQuad scan pipeline: six named regions from the
datum-aligned mesh.
Repo: electric-butterfly/equad. Work from the root of your local clone - find it, do not
assume a path.
Make NO writes outside this repo. Large outputs go under data_root from the config.

PRECONDITION 1 - right tree. Run `git rev-parse --show-toplevel` and
`git remote get-url origin`. origin must be electric-butterfly/equad, and every path
below is relative to the toplevel the first command printed. If origin names a
different repo, or git errors because this is not a work tree, say so and STOP,
and ask the owner to repoint the session. Do not clone it, do not search the
filesystem for a copy, do not guess a path. Write nothing.

PRECONDITION 2 - plan present. Confirm docs/thrifty/2026-09-14-scan-pipeline/plan.md exists in
that tree. If it does not, the plan PR has not merged - say so and STOP. Write
nothing: the directory you would write to does not exist either. Do not improvise
a substitute.

Confirm pipeline/condition.py and docs/thrifty/2026-09-14-scan-pipeline/artefacts/datum.json
exist. If either does not, the producing WP's PR has not merged. Write
docs/thrifty/2026-09-14-scan-pipeline/status/WP-04.md with state: blocked and the absent
path in Notes, commit, push, open one PR, and STOP. Do not reconstruct it.
Confirm data/derived/chassis_datum_full.ply exists on this machine. If it does not,
run `.venv-mesh/Scripts/python pipeline/condition.py --through 11` first (about 20
minutes; background it and poll its log) - that is regeneration, not reconstruction.

BRANCH. Your branch is thrifty/2026-09-14-scan-pipeline/wp-04 - derived from the plan, never
invented. Before touching anything:
  git fetch origin
  git ls-remote --exit-code --heads origin thrifty/2026-09-14-scan-pipeline/wp-04
A missing branch means a fresh start. Cut it from origin/main:
  git switch -c thrifty/2026-09-14-scan-pipeline/wp-04 origin/main
Write docs/thrifty/2026-09-14-scan-pipeline/status/WP-04.md with state: started. Commit it
("chore(thrifty): WP-04 start") and push -u. Do NOT open a PR yet. That commit only
stakes the branch so a dead session is still findable. The PR comes once, at the
very end of this prompt.
An existing branch means a RESUME, not a new start. Check it out:
  git switch -c thrifty/2026-09-14-scan-pipeline/wp-04 origin/thrifty/2026-09-14-scan-pipeline/wp-04
Read that status file and carry on from its resume-from, setting state:
in-progress. Do not start over and do not re-apply what is already done.
Never commit to main.

THEN read docs/thrifty/2026-09-14-scan-pipeline/plan.md section 4.1, section 4.4,
section 5.1 and section 6. Read pipeline/common.py in full.

Load: ToolSearch query "select:Read,Write,Bash,Grep"

Do NOT load or call WebSearch or WebFetch. The boxes are fixed in section 4.4; a
search has nothing to add.
Do NOT load or call Edit. This WP creates new files; it changes nothing that exists.

TASK. Eight items.
  1. Write pipeline/crops.toml verbatim from section 4.4.
  2. Write pipeline/crop.py: loads config and crops.toml; reads
     data/derived/chassis_datum_5M.stl (Open3D, then numpy) and, for the face crops,
     data/derived/chassis_datum_full.ply; keeps faces whose centroid lies inside each
     box; writes <region>_full.ply (binary, faces of the full mesh), <region>_pts.ply
     (unique vertices of the 5 M mesh in the box with per-face normals, binary) and
     <region>_silhouette.png (plan and side, 0.6 mm per pixel from the 5 M points, via
     common.silhouette_png) under data/crops/<region>/; prints per region the 5 M
     point count and the fraction of above-floor (Z over 6 mm) 5 M vertices inside
     the box; takes --region NAME to do one region.
  3-8. Run one region each in this order: engine-bay, rear-axle, tank-mounts,
     front-flange, rear-flange, duct-route. Copy each silhouette to
     docs/thrifty/2026-09-14-scan-pipeline/artefacts/crop-<region>.png (under 500 kB
     each; if larger, render at 1.2 mm per pixel for the copy).
  Then write artefacts/crops-report.md: a table of region, box, point count,
  fraction, expected_fraction, difference in percentage points.
Hard cap: 8 items this session. 8 is the measured budget from section 5, not a
target - reaching it is a normal ending, not a failure.

PROCEDURE:
1. Write out the eight items as your list.
2. CANARY items 1, 2 and 3 (engine-bay only). Stop. Report the engine-bay point
   count and fraction against expected_fraction 0.1204, and attach the silhouette.
   Wait for the go-ahead - the owner will look at the render.
3. Then items 4-8 in one batch. After the batch: report, update the status file
   (progress, resume-from, updated), commit, push. Serial calls only. No PR yet.
4. If you hit the hard cap, or context runs short, or the owner pauses you: write
   state: paused with resume-from and pause-reason, commit, push, and STOP. Do
   NOT open a PR yet - that is the job of the session that resumes this prompt.

VERIFY BEFORE FINISHING:
  For each region: abs(fraction - expected_fraction) -> expect under 0.015
  ls data/crops -> expect exactly six directories, each with three files
  Each artefacts/crop-<region>.png -> expect under 500 000 bytes
Report the numbers. If any does not match, say so and do not claim completion.

SCOPE FENCE. You may create crops.toml, crop.py, the report, the six renders and
anything under data/crops. Do NOT change condition.py, common.py, datum.json or
datum-reference.json. Do NOT adjust a box to make a fraction match - report the
mismatch. Do NOT run RANSAC - that is WP-05. Out-of-scope observations go in
docs/thrifty/2026-09-14-scan-pipeline/findings/WP-04.md, not into an action.

STOP CONDITION: when every item in your list has been handled once, or the hard
cap is reached. Do not look for more work.

Write docs/thrifty/2026-09-14-scan-pipeline/status/WP-04.md per section 6 of the plan.
On a terminal state - done, blocked, stopped, or canary-waiting - commit to your
branch cut from origin/main, push it, and open one PR. Then STOP - the owner merges.
Do NOT add commits to a PR that is already open.
```

---

### WP5 — Segment each region with RANSAC

**Model:** Sonnet · **Effort:** low · **Item cap:** 8 (from section 5.7; the WP has 8 items) ·
**Branch:** `thrifty/2026-09-14-scan-pipeline/wp-05` · **Writes:** `pipeline/segment.py`,
`docs/thrifty/2026-09-14-scan-pipeline/artefacts/primitives-<region>.json` for six regions,
`artefacts/segment-report.md`, status

**Goal.** Run the section 4.5 CloudCompare command on each region's point cloud, parse every
primitive into a table with axis, radius, support and residual, and flag tube and plane candidates.

**Done when.** Six `primitives-<region>.json` files exist; for engine-bay at least 30 cylinders have
radius 11–16 mm, at least 30% of points are assigned, and the median RMS of those cylinders is under
1.0 mm; for rear-axle the two axle-housing cylinders of section 5.4 appear with radius 20–30 mm;
`artefacts/segment-report.md` tabulates counts per region.

```
Implement and run the segment stage of the eQuad scan pipeline: CloudCompare RANSAC per region,
parsed to a primitive table.
Repo: electric-butterfly/equad. Work from the root of your local clone - find it, do not
assume a path.
Make NO writes outside this repo. CloudCompare outputs go under data_root/ransac.

PRECONDITION 1 - right tree. Run `git rev-parse --show-toplevel` and
`git remote get-url origin`. origin must be electric-butterfly/equad, and every path
below is relative to the toplevel the first command printed. If origin names a
different repo, or git errors because this is not a work tree, say so and STOP,
and ask the owner to repoint the session. Do not clone it, do not search the
filesystem for a copy, do not guess a path. Write nothing.

PRECONDITION 2 - plan present. Confirm docs/thrifty/2026-09-14-scan-pipeline/plan.md exists in
that tree. If it does not, the plan PR has not merged - say so and STOP. Write
nothing: the directory you would write to does not exist either. Do not improvise
a substitute.

Confirm pipeline/crops.toml and pipeline/crop.py exist. If either does not, the
producing WP's PR has not merged. Write
docs/thrifty/2026-09-14-scan-pipeline/status/WP-05.md with state: blocked and the absent
path in Notes, commit, push, open one PR, and STOP. Do not reconstruct it.
Confirm data/crops/engine-bay/engine-bay_pts.ply exists on this machine. If not, run
`.venv-mesh/Scripts/python pipeline/crop.py` (regeneration; if it fails because
data/derived is missing, run condition.py --through 11 first, backgrounded).

BRANCH. Your branch is thrifty/2026-09-14-scan-pipeline/wp-05 - derived from the plan, never
invented. Before touching anything:
  git fetch origin
  git ls-remote --exit-code --heads origin thrifty/2026-09-14-scan-pipeline/wp-05
A missing branch means a fresh start. Cut it from origin/main:
  git switch -c thrifty/2026-09-14-scan-pipeline/wp-05 origin/main
Write docs/thrifty/2026-09-14-scan-pipeline/status/WP-05.md with state: started. Commit it
("chore(thrifty): WP-05 start") and push -u. Do NOT open a PR yet. That commit only
stakes the branch so a dead session is still findable. The PR comes once, at the
very end of this prompt.
An existing branch means a RESUME, not a new start. Check it out:
  git switch -c thrifty/2026-09-14-scan-pipeline/wp-05 origin/thrifty/2026-09-14-scan-pipeline/wp-05
Read that status file and carry on from its resume-from, setting state:
in-progress. Do not start over and do not re-apply what is already done.
Never commit to main.

THEN read docs/thrifty/2026-09-14-scan-pipeline/plan.md section 4.5, section 5.5 and
section 6. Read pipeline/common.py in full.

Load: ToolSearch query "select:Read,Write,Bash,Grep"

Do NOT load or call WebSearch or WebFetch. The command and its parameters are fixed
in section 4.5 and were measured in 5.5; a search invites a parameter change that
makes the counts incomparable.
Do NOT load or call Edit. This WP creates new files; it changes nothing that exists.

TASK. Eight items.
  1. Write pipeline/segment.py: loads config and crops.toml; for --region NAME runs
     the section 4.5 command via subprocess with cloudcompare_exe from the config,
     into data/ransac/<region>/{clouds,meshes} (emptied first); parses per section
     4.5 into a list sorted by support; writes
     docs/thrifty/2026-09-14-scan-pipeline/artefacts/primitives-<region>.json; prints
     primitive count, cylinder and plane counts, points assigned and fraction, and the
     count of cylinders inside each tube_radii_mm bracket with their median rms.
  2-7. Run one region each in this order: engine-bay, rear-axle, rear-flange,
     front-flange, tank-mounts, duct-route.
  8. Write artefacts/segment-report.md: per region the printed counts, plus for
     engine-bay and rear-axle the top ten primitives by support.
Hard cap: 8 items this session. 8 is the measured budget from section 5, not a
target - reaching it is a normal ending, not a failure.

PROCEDURE:
1. Write out the eight items as your list.
2. CANARY items 1 and 2 (engine-bay). Stop. Report: primitive count, cylinders with
   radius 11-16 mm, fraction assigned, median rms. Expected from section 5.5 on the
   5 M-derived cloud: 100 primitives, 38 such cylinders, 42.8%, 0.72 mm; full-res
   crops will give more primitives and a similar fraction. Wait for the go-ahead.
3. Then items 3-8 in one batch. After the batch: report, update the status file
   (progress, resume-from, updated), commit, push. Serial calls only - one
   CloudCompare process at a time. No PR yet.
4. If you hit the hard cap, or context runs short, or the owner pauses you: write
   state: paused with resume-from and pause-reason, commit, push, and STOP. Do
   NOT open a PR yet - that is the job of the session that resumes this prompt.

VERIFY BEFORE FINISHING:
  engine-bay: cylinders with radius 11-16 mm -> expect at least 30
  engine-bay: fraction of points assigned -> expect at least 0.30
  engine-bay: median rms of those cylinders -> expect under 1.0 mm
  rear-axle: cylinders with radius 20-30 mm and axis within 8 degrees of Y -> expect 2
  ls artefacts/primitives-*.json -> expect 6 files, each under 400 000 bytes
Report the numbers. If any does not match, say so and do not claim completion.

SCOPE FENCE. You may create segment.py, the six JSON files, the report and anything
under data/ransac. Do NOT change crops.toml, crop.py, condition.py or common.py. Do
NOT change any RANSAC parameter from section 4.5 - if a region yields nothing, report
it. Do NOT refine primitives on full-res points - that is WP-06. Out-of-scope
observations go in docs/thrifty/2026-09-14-scan-pipeline/findings/WP-05.md, not into
an action.

STOP CONDITION: when every item in your list has been handled once, or the hard
cap is reached. Do not look for more work.

Write docs/thrifty/2026-09-14-scan-pipeline/status/WP-05.md per section 6 of the plan.
On a terminal state - done, blocked, stopped, or canary-waiting - commit to your
branch cut from origin/main, push it, and open one PR. Then STOP - the owner merges.
Do NOT add commits to a PR that is already open.
```

---

### WP6 — Fit and verify the primitives

**Model:** Sonnet · **Effort:** medium · **Item cap:** 8 (from section 5.7; the WP has 8 items) ·
**Branch:** `thrifty/2026-09-14-scan-pipeline/wp-06` · **Writes:** `pipeline/fit.py`,
`docs/thrifty/2026-09-14-scan-pipeline/artefacts/interfaces.json`, `artefacts/fit-report.md`,
`artefacts/deviation-<region>.png` for six regions, status

**Goal.** Refine every accepted RANSAC primitive on the full-resolution crop points with the
section 4.6 method, record residuals, and render the deviation per region.

**Done when.** `artefacts/interfaces.json` holds one entry per accepted primitive across the six
regions; every accepted cylinder has RMS under 0.8 mm and every accepted plane under 0.5 mm; the
two rear-axle-housing cylinders are accepted with radius 22–27 mm and axes within 1° of each other;
six deviation renders exist; `artefacts/fit-report.md` tabulates accepted and rejected counts and
the ten worst residuals.

```
Implement and run the fit stage of the eQuad scan pipeline: refine RANSAC primitives on full-res
points and record residuals.
Repo: electric-butterfly/equad. Work from the root of your local clone - find it, do not
assume a path.
Make NO writes outside this repo.

PRECONDITION 1 - right tree. Run `git rev-parse --show-toplevel` and
`git remote get-url origin`. origin must be electric-butterfly/equad, and every path
below is relative to the toplevel the first command printed. If origin names a
different repo, or git errors because this is not a work tree, say so and STOP,
and ask the owner to repoint the session. Do not clone it, do not search the
filesystem for a copy, do not guess a path. Write nothing.

PRECONDITION 2 - plan present. Confirm docs/thrifty/2026-09-14-scan-pipeline/plan.md exists in
that tree. If it does not, the plan PR has not merged - say so and STOP. Write
nothing: the directory you would write to does not exist either. Do not improvise
a substitute.

Confirm pipeline/segment.py and
docs/thrifty/2026-09-14-scan-pipeline/artefacts/primitives-engine-bay.json exist. If
either does not, the producing WP's PR has not merged. Write
docs/thrifty/2026-09-14-scan-pipeline/status/WP-06.md with state: blocked and the absent
path in Notes, commit, push, open one PR, and STOP. Do not reconstruct it.
Confirm data/crops/engine-bay/engine-bay_full.ply exists on this machine. If not,
regenerate with crop.py (and condition.py --through 11 before it if data/derived is
missing, backgrounded).

BRANCH. Your branch is thrifty/2026-09-14-scan-pipeline/wp-06 - derived from the plan, never
invented. Before touching anything:
  git fetch origin
  git ls-remote --exit-code --heads origin thrifty/2026-09-14-scan-pipeline/wp-06
A missing branch means a fresh start. Cut it from origin/main:
  git switch -c thrifty/2026-09-14-scan-pipeline/wp-06 origin/main
Write docs/thrifty/2026-09-14-scan-pipeline/status/WP-06.md with state: started. Commit it
("chore(thrifty): WP-06 start") and push -u. Do NOT open a PR yet. That commit only
stakes the branch so a dead session is still findable. The PR comes once, at the
very end of this prompt.
An existing branch means a RESUME, not a new start. Check it out:
  git switch -c thrifty/2026-09-14-scan-pipeline/wp-06 origin/thrifty/2026-09-14-scan-pipeline/wp-06
Read that status file and carry on from its resume-from, setting state:
in-progress. Do not start over and do not re-apply what is already done.
Never commit to main.

THEN read docs/thrifty/2026-09-14-scan-pipeline/plan.md section 4.5, section 4.6,
section 5.3 and section 6. Read pipeline/common.py in full.

Load: ToolSearch query "select:Read,Write,Bash,Grep"

Do NOT load or call WebSearch or WebFetch. The fit method and thresholds are fixed in
section 4.6 and measured in 5.3; a search invites a different estimator whose
residuals are not comparable.
Do NOT load or call Edit. This WP creates new files; it changes nothing that exists.

TASK. Eight items.
  1. Write pipeline/fit.py: for --region NAME loads primitives-<region>.json and the
     region's _full.ply (faces, so face normals are available); for each accepted
     primitive gathers full-res faces whose centroid lies within 3 mm of the RANSAC
     primitive surface; cylinders: axis from the face-normal covariance null
     direction, then common.fit_circle_trimmed in the perpendicular plane; planes:
     trimmed least-squares plane; writes rows per section 4.6 into
     artefacts/interfaces.json (merge per region, keyed by id) and a deviation render
     (signed residual, -1 to +1 mm, 0.6 mm per pixel) to artefacts/deviation-<region>.png.
     Prints accepted and rejected counts and the worst five residuals.
  2-7. Run one region each in this order: rear-axle, engine-bay, rear-flange,
     front-flange, tank-mounts, duct-route.
  8. Write artefacts/fit-report.md: per region accepted and rejected counts, the two
     axle-housing rows in full, and the ten worst residuals across all regions with
     their ids.
Hard cap: 8 items this session. 8 is the measured budget from section 5, not a
target - reaching it is a normal ending, not a failure.

PROCEDURE:
1. Write out the eight items as your list.
2. CANARY items 1 and 2 (rear-axle). Stop. Report the two axle-housing rows: radius,
   rms, p95, axis. Expected from section 5.4 on 5 M-derived points: r 24.6 and 23.9,
   rms about 1.1; full-res refinement should land under 0.8. Wait for the go-ahead.
3. Then items 3-8 in one batch. After the batch: report, update the status file
   (progress, resume-from, updated), commit, push. Serial calls only. No PR yet.
4. If you hit the hard cap, or context runs short, or the owner pauses you: write
   state: paused with resume-from and pause-reason, commit, push, and STOP. Do
   NOT open a PR yet - that is the job of the session that resumes this prompt.

VERIFY BEFORE FINISHING:
  Every row with accepted true and kind cylinder -> rms under 0.8 mm
  Every row with accepted true and kind plane -> rms under 0.5 mm
  rear-axle: the two housing cylinders -> accepted, radius 22-27 mm, axes within 1 deg
  ls artefacts/deviation-*.png -> expect 6 files, each under 500 000 bytes
  Count of rows in interfaces.json equals the count of accepted candidates across the
     six primitives-<region>.json files -> report both numbers
Report the numbers. If any does not match, say so and do not claim completion.

SCOPE FENCE. You may create fit.py, interfaces.json, the report and the six renders.
Do NOT change segment.py, crop.py, condition.py, common.py, crops.toml or any
primitives-<region>.json. Do NOT loosen a threshold to accept a primitive - record
it rejected with the reason. Do NOT build STEP or any CAD solid - that is the next
plan. Out-of-scope observations go in
docs/thrifty/2026-09-14-scan-pipeline/findings/WP-06.md, not into an action.

STOP CONDITION: when every item in your list has been handled once, or the hard
cap is reached. Do not look for more work.

Write docs/thrifty/2026-09-14-scan-pipeline/status/WP-06.md per section 6 of the plan.
On a terminal state - done, blocked, stopped, or canary-waiting - commit to your
branch cut from origin/main, push it, and open one PR. Then STOP - the owner merges.
Do NOT add commits to a PR that is already open.
```

---

## 9. Owner actions

| # | Action | When |
|---|---|---|
| 1 | **Commit and push `docs/` and merge this plan to `main`.** The report, its figures and this plan directory are uncommitted in the working tree. Nothing can start until the plan is on `main`. | **First** |
| 2 | **Switch `gh` and git credentials to the account that has push access to electric-butterfly/equad** before pasting any starter prompt. The work account is active on this machine and every WP push will fail under it. | Before WP-01 |
| 3 | **Write `pipeline/config.local.toml`** from `pipeline/config.example.toml` after WP-01 merges: the two scan paths on the project drive, `data_root = "data"`, the CloudCompare executable path from `artefacts/toolsets-mesh.md`. Optional `tube_radii_mm` brackets once callipers are in hand. | After WP-01, before WP-03 |
| 4 | **Merge each WP's PR before its dependants run.** The WPs chain through committed artefacts, so an unmerged PR stalls the sequence. This is also the review gate. Eyeball the renders in WP-03 and WP-04 PRs. | Between WPs |
| 5 | **Resume anything showing `paused`.** Paste the same starter prompt into a fresh session; it picks up from the branch. A paused WP has no PR and will not surface as your turn. | Whenever the rollup shows one |
| 6 | **Callipers on the frame tubes** in the engine bay and on the rear axle housing: outside diameters, to 0.1 mm. Put them in `tube_radii_mm` before WP-05 if available; otherwise WP-05 uses the default brackets and WP-06's report says which. | Before WP-05, ideally |
| 7 | **Ask the fabricator who made the scan for re-exports from the Artec project**: the floor-free full-res mesh, OBJ or PLY with colour, the fusion resolution and any shape-deviation decimation applied, and whether hole filling was used. Not a prerequisite for any WP; a cross-check for WP-03's floor removal and for the next plan. | Any time |
| 8 | **Fusion licence**: Flex at 3 tokens (A$14) per Fusion day and 4 tokens (A$18) per Design Extension day, tokens expiring 365 days after purchase, is the pay-per-use route for the next plan's Fusion days. Nothing in this plan needs a Fusion day. | Before the next plan |

---

## 10. Known collisions

- `docs/scan-to-cad-options.md` and `docs/figures/` are uncommitted in the owner's working tree
  alongside this plan. They travel in the same plan PR. No WP touches them.
- `README.md` states that the CVT ducts and fan bracket are in the scan; the renders show they are
  not. Correcting it is the owner's, not any WP's. WP sessions must not edit `README.md`.
- WP-01 and WP-02 run in parallel and both create venvs at the repo root and write under
  `pipeline/`. Their file sets are disjoint by design; neither touches the other's files even if it
  notices a problem. WP-02 does not add its venv names to `.gitignore` — WP-01's `.gitignore`
  already lists them.
- The session that wrote this plan installed CloudCompare 2.13.2 on the owner's machine and left a
  temporary venv and scratch meshes in its own scratch directory. WP-01's winget step will report
  "already installed" for CloudCompare; that is the expected outcome, not an error. Resolving any of
  the above is NOT part of this plan.
