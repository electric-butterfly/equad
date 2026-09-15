# Battery box CAD

All parameters come from `params.toml`. Run every script from the repo root.

| Script | venv | Run order | What it builds |
|---|---|---|---|
| `cell.py` | `.venv-cad` | 1 | The cell and the 26-cell block; `--report` writes `cell-report.md` |
| `enclosure.py` | `.venv-cad` | 2 | The enclosure, lid, internals, fuse bay and cable exits |
| `assembly.py` | `.venv-cad` | 3 | Two boxes on the datum, motor placeholder, keep-out, `placement.json` |
| `clearance.py` | `.venv-mesh` | 4 | Placement evaluation, the sweep, section renders |
| `mounts.py` | `.venv-mesh` | 5 | Frame primitives within reach of the placed box |
| `viewer.py` | `.venv-cad` | 6 | `viewer.html` and `sam-battery-boxes.html` |

Every script resolves the repo root with `git rev-parse --show-toplevel`, loads `cad/params.toml`,
writes only to `data/cad/` and `docs/thrifty/2026-09-15-battery-boxes/artefacts/`, and refuses to
run if a named input is missing. `common.py` reads `freecad_cmd` from
`pipeline/config.local.toml` for the STEP round-trip check; no other script reads that file.

```
.venv-cad/Scripts/python cad/cell.py
.venv-cad/Scripts/python cad/enclosure.py
.venv-cad/Scripts/python cad/assembly.py
.venv-mesh/Scripts/python cad/clearance.py
.venv-mesh/Scripts/python cad/mounts.py
.venv-cad/Scripts/python cad/viewer.py
```
