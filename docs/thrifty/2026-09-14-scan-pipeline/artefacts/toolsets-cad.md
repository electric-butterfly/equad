# CAD-side toolset — installed and proven, 2026-09-14

Two isolated venvs because `build123d==0.11.1` and `draftwright==0.4.29` pull incompatible
`cadquery-ocp` builds (plan section 5.6). FreeCAD is a separate desktop install with the
SheetMetal workbench added as a user Mod.

## Versions

| Component | Venv | Version |
|---|---|---|
| build123d | `.venv-cad` | 0.11.1 |
| cadquery-ocp-novtk | `.venv-cad` | 7.9.3.1.1 |
| cadquery-ocp-proxy | `.venv-cad` | 7.9.3.1.1 |
| draftwright | `.venv-draft` | 0.4.29 |
| build123d | `.venv-draft` | 0.10.0 |
| cadquery-ocp | `.venv-draft` | 7.8.1.1.post1 |
| vtk | `.venv-draft` | 9.3.1 |
| FreeCAD | desktop (winget) | 1.1.3 |
| FreeCAD_SheetMetal | user Mod (git clone) | commit `d99e89ada00c9de85243878536c52ede1bcb8953` |

Both resolutions match the dry-run predictions in plan section 5.6 exactly.

## Install locations

- FreeCAD installed per-user via winget under `%LOCALAPPDATA%\Programs\FreeCAD 1.1\`
  (winget's `FreeCAD.FreeCAD` package installs for the current user, not into
  `%ProgramFiles%` — the plan's instruction assumed a machine-wide install path; recorded
  here as a correction for the next session that looks for it).
  `freecadcmd.exe` is at `bin\` under that folder.
- SheetMetal workbench cloned into FreeCAD's user Mod directory, found via
  `FreeCAD.getUserAppDataDir()` -> `%APPDATA%\FreeCAD\v1-1\Mod\SheetMetal`.

## Smoke test outputs (verbatim)

**build123d (`.venv-cad`)** — 10 x 20 x 30 mm box, export to STEP, re-import:
```
volume 6000.0
```

**draftwright (`.venv-draft`)** — console script `draftwright.exe`, run on the STEP above:
```
C:\SANDPIT\equad\data\smoke_box.pdf
C:\SANDPIT\equad\data\smoke_box.draftwright.json
```
PDF size: 59258 bytes.

**FreeCAD** — `freecadcmd.exe -c "import Part, SheetMetalNewUnfolder; print('ok')"`:
```
ok
```
This required installing `networkx` into FreeCAD's bundled Python first
(`SheetMetalNewUnfolder.py` imports it unconditionally past a soft-fail import guard);
the workbench does not vendor it. Installed with:
```
"%LOCALAPPDATA%\Programs\FreeCAD 1.1\bin\python.exe" -m pip install networkx
```
resolved `networkx==3.6.1`.
