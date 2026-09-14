# Pipeline

Condition, crop, segment and fit the King Quad scan against the vehicle datum. See
`docs/thrifty/2026-09-14-scan-pipeline/plan.md` section 4 for the full contract.

## Setup

1. Create the mesh venv and install its pins:
   ```
   python -m venv .venv-mesh
   .venv-mesh/Scripts/python -m pip install -r pipeline/requirements-mesh.txt
   ```
2. Install CloudCompare (`winget install --id CloudCompare.CloudCompare --exact`) and MeshLab
   (`winget install --id CNRISTI.MeshLab --exact`).
3. Copy `pipeline/config.example.toml` to `pipeline/config.local.toml` and fill in the absolute
   paths on this machine (scan files, `data_root`, `CloudCompare.exe`, `FreeCADCmd.exe`).
   `config.local.toml` is git-ignored.

## Stages

| Script | Written by | Purpose |
|---|---|---|
| `pipeline/condition.py` | WP-03 | Clean the full-res scan, remove the floor, align to the ISO 8855 vehicle datum, write decimations and `datum.json`. |
| `pipeline/crop.py` | WP-04 | Cut the six named regions from `pipeline/crops.toml` into per-region meshes, point clouds and silhouettes. |
| `pipeline/segment.py` | WP-05 | Run CloudCompare RANSAC on each region's point cloud and write a primitive table per region. |
| `pipeline/fit.py` | WP-06 | Refine each accepted primitive on full-resolution points and write `interfaces.json` with residuals. |

Each script loads `pipeline/config.local.toml` via `pipeline/common.py`, resolves `data_root`
against the repo root, and refuses to run if a required key or file is missing. Run from the mesh
venv:

```
.venv-mesh/Scripts/python pipeline/condition.py
.venv-mesh/Scripts/python pipeline/crop.py
.venv-mesh/Scripts/python pipeline/segment.py
.venv-mesh/Scripts/python pipeline/fit.py
```

Every script takes `--stage-only` flags as documented in its own `--help`, and writes nothing
outside `data_root` and `docs/thrifty/2026-09-14-scan-pipeline/artefacts/`.
