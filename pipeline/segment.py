"""Segment stage of the eQuad scan pipeline: CloudCompare RANSAC per region, parsed to a
primitive table, per plan section 4.5."""

import argparse
import json
import shutil
import subprocess
import tomllib
from pathlib import Path

import numpy as np

from common import load_config

REGIONS = [
    "engine-bay",
    "tank-mounts",
    "front-flange",
    "rear-flange",
    "duct-route",
    "rear-axle",
]

DEFAULT_TUBE_RADII_MM = [[11, 16], [17, 20], [22, 26]]


def load_crops(path: Path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def _read_ply_vertices(path: Path) -> np.ndarray:
    """Minimal ASCII/binary_little_endian PLY vertex reader (x, y, z only)."""
    with open(path, "rb") as f:
        header = []
        while True:
            line = f.readline().decode("ascii").strip()
            header.append(line)
            if line == "end_header":
                break

        fmt = None
        vertex_count = 0
        props = []
        in_vertex_element = False
        for line in header:
            if line.startswith("format"):
                fmt = line.split()[1]
            elif line.startswith("element vertex"):
                vertex_count = int(line.split()[-1])
                in_vertex_element = True
            elif line.startswith("element"):
                in_vertex_element = False
            elif line.startswith("property") and in_vertex_element:
                parts = line.split()
                props.append((parts[1], parts[2]))

        prop_type_map = {"float": "<f4", "float32": "<f4", "double": "<f8", "float64": "<f8"}
        if fmt == "ascii":
            data = np.loadtxt(f, max_rows=vertex_count)
            cols = {name: i for i, (_, name) in enumerate(props)}
            return data[:, [cols["x"], cols["y"], cols["z"]]]

        dtype = np.dtype([(name, prop_type_map[ptype]) for ptype, name in props])
        buf = f.read(vertex_count * dtype.itemsize)
        records = np.frombuffer(buf, dtype=dtype, count=vertex_count)
        return np.stack([records["x"], records["y"], records["z"]], axis=1).astype(np.float64)


def run_ransac(region_pts_path: Path, out_dir: Path, cloudcompare_exe: Path) -> None:
    clouds_dir = out_dir / "clouds"
    meshes_dir = out_dir / "meshes"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    clouds_dir.mkdir(parents=True, exist_ok=True)
    meshes_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(cloudcompare_exe),
        "-SILENT", "-NO_TIMESTAMP", "-AUTO_SAVE", "OFF",
        "-C_EXPORT_FMT", "PLY", "-M_EXPORT_FMT", "PLY",
        "-O", str(region_pts_path),
        "-RANSAC",
        "EPSILON_ABSOLUTE", "0.6",
        "BITMAP_EPSILON_ABSOLUTE", "4.0",
        "SUPPORT_POINTS", "300",
        "MAX_NORMAL_DEV", "15",
        "PROBABILITY", "0.01",
        "ENABLE_PRIMITIVE", "PLANE", "CYLINDER",
        "OUT_CLOUD_DIR", str(clouds_dir),
        "OUT_MESH_DIR", str(meshes_dir),
        "OUTPUT_INDIVIDUAL_SUBCLOUDS", "OUTPUT_INDIVIDUAL_PRIMITIVES",
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def parse_primitives(out_dir: Path) -> list[dict]:
    clouds_dir = out_dir / "clouds"
    meshes_dir = out_dir / "meshes"

    primitives = []
    for mesh_path in sorted(meshes_dir.glob("*.ply")):
        stem = mesh_path.stem
        if "_CYLINDER_" in stem:
            kind = "cylinder"
            index = int(stem.rsplit("_", 1)[-1])
        elif "_PLANE_" in stem:
            kind = "plane"
            index = int(stem.rsplit("_", 1)[-1])
        else:
            continue

        cloud_path = clouds_dir / f"{stem}_cloud.ply"
        if not cloud_path.exists():
            continue

        mesh_verts = _read_ply_vertices(mesh_path)
        cloud_pts = _read_ply_vertices(cloud_path)
        centre = mesh_verts.mean(axis=0)
        centred = mesh_verts - centre
        cov = centred.T @ centred / max(1, centred.shape[0])
        eigvals, eigvecs = np.linalg.eigh(cov)

        if kind == "cylinder":
            axis = eigvecs[:, -1]
            axis = axis / np.linalg.norm(axis)
            rel = mesh_verts - centre
            along = rel @ axis
            perp = rel - np.outer(along, axis)
            radius = float(np.median(np.linalg.norm(perp, axis=1)))
            length = float(along.max() - along.min())

            cloud_rel = cloud_pts - centre
            cloud_along = cloud_rel @ axis
            cloud_perp = cloud_rel - np.outer(cloud_along, axis)
            cloud_radial = np.linalg.norm(cloud_perp, axis=1)
            residual = cloud_radial - radius
        else:
            axis = eigvecs[:, 0]
            axis = axis / np.linalg.norm(axis)
            radius = None
            length = None
            residual = (cloud_pts - centre) @ axis

        support = int(cloud_pts.shape[0])
        rms = float(np.sqrt(np.mean(residual ** 2))) if support > 0 else float("nan")
        p95 = float(np.percentile(np.abs(residual), 95)) if support > 0 else float("nan")

        primitives.append({
            "kind": kind,
            "index": index,
            "support": support,
            "radius": radius,
            "length": length,
            "axis": axis.tolist(),
            "centre": centre.tolist(),
            "rms": rms,
            "p95": p95,
        })

    primitives.sort(key=lambda p: p["support"], reverse=True)
    return primitives


def summarise(primitives: list[dict], tube_radii_mm) -> dict:
    cylinders = [p for p in primitives if p["kind"] == "cylinder"]
    planes = [p for p in primitives if p["kind"] == "plane"]
    total_support = sum(p["support"] for p in primitives)

    bracket_summary = []
    for lo, hi in tube_radii_mm:
        in_bracket = [c for c in cylinders if lo <= c["radius"] <= hi and c["rms"] < 1.2]
        median_rms = float(np.median([c["rms"] for c in in_bracket])) if in_bracket else None
        bracket_summary.append({
            "range_mm": [lo, hi],
            "count": len(in_bracket),
            "median_rms": median_rms,
        })

    return {
        "primitive_count": len(primitives),
        "cylinder_count": len(cylinders),
        "plane_count": len(planes),
        "total_support": total_support,
        "brackets": bracket_summary,
    }


def segment_region(name: str, config: dict, tube_radii_mm) -> dict:
    data_root = config["data_root"]
    region_pts_path = data_root / "crops" / name / f"{name}_pts.ply"
    out_dir = data_root / "ransac" / name
    artefacts_dir = (
        Path(__file__).parent.parent
        / "docs" / "thrifty" / "2026-09-14-scan-pipeline" / "artefacts"
    )
    artefacts_dir.mkdir(parents=True, exist_ok=True)

    cloud_pts = _read_ply_vertices(region_pts_path)
    total_points = int(cloud_pts.shape[0])

    run_ransac(region_pts_path, out_dir, config["cloudcompare_exe"])
    primitives = parse_primitives(out_dir)

    assigned_points = sum(p["support"] for p in primitives)
    fraction_assigned = assigned_points / max(1, total_points)

    summary = summarise(primitives, tube_radii_mm)
    summary["region"] = name
    summary["total_points"] = total_points
    summary["fraction_assigned"] = fraction_assigned

    out_path = artefacts_dir / f"primitives-{name}.json"
    out_path.write_text(json.dumps({"region": name, "primitives": primitives}, indent=2))

    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", choices=REGIONS, default=None)
    args = parser.parse_args()

    config = load_config()
    tube_radii_mm = config.get("tube_radii_mm", DEFAULT_TUBE_RADII_MM)

    regions = [args.region] if args.region else REGIONS
    for name in regions:
        summary = segment_region(name, config, tube_radii_mm)
        bracket_str = ", ".join(
            f"[{b['range_mm'][0]}-{b['range_mm'][1]}]:{b['count']}"
            f"(rms={b['median_rms']:.2f})" if b["median_rms"] is not None
            else f"[{b['range_mm'][0]}-{b['range_mm'][1]}]:0"
            for b in summary["brackets"]
        )
        print(
            f"{summary['region']}: primitives={summary['primitive_count']} "
            f"cylinders={summary['cylinder_count']} planes={summary['plane_count']} "
            f"points_assigned={summary['fraction_assigned']:.4f} "
            f"brackets={bracket_str}"
        )


if __name__ == "__main__":
    main()
