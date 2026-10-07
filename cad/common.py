"""Shared helpers for the battery-box CAD scripts: repo root, params, artefact paths, STEP export
with FreeCAD round-trip verification."""

import subprocess
import tomllib
from pathlib import Path

# name -> (r, g, b, alpha), channels 0 to 1; plan section 4.10
COLOURS = {
    "cell": (0.31, 0.62, 0.42, 1.0),
    "shell": (0.169, 0.424, 0.561, 1.0),
    "lid": (0.357, 0.608, 0.741, 1.0),
    "plate": (0.541, 0.604, 0.639, 1.0),
    "fuse": (0.878, 0.690, 0.188, 1.0),
    "motor": (0.851, 0.510, 0.169, 1.0),
    "keepout": (0.753, 0.224, 0.169, 0.35),
    "axis_x": (0.80, 0.15, 0.15, 1.0),
    "axis_y": (0.15, 0.60, 0.25, 1.0),
    "axis_z": (0.15, 0.30, 0.80, 1.0),
}


def repo_root() -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
    )
    return Path(out.stdout.strip())


def load_params(path: Path | None = None) -> dict:
    if path is None:
        path = repo_root() / "cad" / "params.toml"
    with open(path, "rb") as f:
        return tomllib.load(f)


def artefacts_dir() -> Path:
    d = repo_root() / "docs" / "thrifty" / "2026-09-15-battery-boxes" / "artefacts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def freecad_cmd() -> str:
    cfg_path = repo_root() / "pipeline" / "config.local.toml"
    with open(cfg_path, "rb") as f:
        cfg = tomllib.load(f)
    cmd = cfg.get("freecad_cmd", "")
    if not cmd:
        raise RuntimeError(f"freecad_cmd not set in {cfg_path}")
    return cmd


def freecad_check(step_path: Path) -> tuple[int, float]:
    """Read step_path with FreeCAD and return (solid count, volume mm3)."""
    script = (
        f"import Part; s = Part.read(r'{step_path}'); "
        f"print(len(s.Solids), s.Volume)"
    )
    out = subprocess.run(
        [freecad_cmd(), "-c", script], capture_output=True, text=True, check=True
    )
    last_line = out.stdout.strip().splitlines()[-1]
    n_str, v_str = last_line.split()
    return int(n_str), float(v_str)


def export_step(shape, path: Path) -> None:
    """Export shape to path and verify the round trip through FreeCAD."""
    from build123d import export_step as _export_step

    path.parent.mkdir(parents=True, exist_ok=True)
    _export_step(shape, str(path))
    check_step(shape, path)


def check_step(shape, path: Path) -> None:
    """Compare FreeCAD's solid count and volume against build123d's for the STEP at path.

    Prints `freecad: N solids, V mm3 (build123d: N solids, V mm3) OK|FAIL` and raises on
    FAIL or on a volume mismatch over 0.01 %.
    """
    n_fc, v_fc = freecad_check(path)
    n_bd = len(shape.solids())
    v_bd = sum(solid.volume for solid in shape.solids())

    ok = n_fc == n_bd
    if v_bd != 0:
        pct_diff = abs(v_fc - v_bd) / abs(v_bd) * 100
    else:
        pct_diff = 0.0 if v_fc == 0 else float("inf")
    ok = ok and pct_diff <= 0.01

    status = "OK" if ok else "FAIL"
    print(
        f"freecad: {n_fc} solids, {v_fc} mm3 "
        f"(build123d: {n_bd} solids, {v_bd} mm3) {status}"
    )
    if not ok:
        raise RuntimeError(
            f"STEP round-trip check failed for {path}: "
            f"freecad {n_fc} solids / {v_fc} mm3 vs build123d {n_bd} solids / {v_bd} mm3"
        )
