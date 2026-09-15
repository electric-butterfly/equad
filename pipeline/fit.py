"""Fit stage of the eQuad scan pipeline: refine RANSAC primitives on full-resolution
crop points and record residuals, per plan section 4.6."""

import argparse
import json
import struct
import zlib
from pathlib import Path

import numpy as np

from common import fit_circle_trimmed, load_config
from segment import DEFAULT_TUBE_RADII_MM

REGIONS = [
    "engine-bay",
    "tank-mounts",
    "front-flange",
    "rear-flange",
    "duct-route",
    "rear-axle",
]

RUN_ORDER = ["rear-axle", "engine-bay", "rear-flange", "front-flange", "tank-mounts", "duct-route"]

ARTEFACTS_DIR = Path(__file__).parent.parent / "docs" / "thrifty" / "2026-09-14-scan-pipeline" / "artefacts"

CYLINDER_CANDIDATE_RMS_MAX = 1.2
PLANE_CANDIDATE_RMS_MAX = 0.6
PLANE_CANDIDATE_SUPPORT_MIN = 500

CYLINDER_ACCEPT_RMS_MAX = 1.0
PLANE_ACCEPT_RMS_MAX = 0.5

MARGIN_MM = 3.0
MIN_POINTS_FOR_FIT = 10

_PLY_TYPE_MAP = {
    "float": "<f4", "float32": "<f4",
    "double": "<f8", "float64": "<f8",
    "uchar": "<u1", "uint8": "<u1",
    "int": "<i4", "int32": "<i4",
    "uint": "<u4", "uint32": "<u4",
}


def _read_ply_mesh(path: Path):
    """Minimal binary_little_endian PLY reader: (x, y, z) vertices and triangular faces."""
    with open(path, "rb") as f:
        header = []
        while True:
            line = f.readline().decode("ascii").strip()
            header.append(line)
            if line == "end_header":
                break

        fmt = None
        elements = []
        current = None
        for line in header:
            if line.startswith("format"):
                fmt = line.split()[1]
            elif line.startswith("element"):
                parts = line.split()
                current = {"name": parts[1], "count": int(parts[2]), "props": []}
                elements.append(current)
            elif line.startswith("property") and current is not None:
                parts = line.split()
                if parts[1] == "list":
                    current["props"].append(("list", parts[2], parts[3], parts[4]))
                else:
                    current["props"].append((parts[1], parts[2]))

        if fmt != "binary_little_endian":
            raise ValueError(f"{path}: unsupported PLY format {fmt!r}")

        vertex_el = next(e for e in elements if e["name"] == "vertex")
        vdtype = np.dtype([(name, _PLY_TYPE_MAP[ptype]) for ptype, name in vertex_el["props"]])
        vbuf = f.read(vertex_el["count"] * vdtype.itemsize)
        vrec = np.frombuffer(vbuf, dtype=vdtype, count=vertex_el["count"])
        vertices = np.stack([vrec["x"], vrec["y"], vrec["z"]], axis=1).astype(np.float64)

        face_el = next((e for e in elements if e["name"] == "face"), None)
        faces = None
        if face_el is not None and face_el["count"] > 0:
            _, count_type, val_type, _ = face_el["props"][0]
            count_dtype = _PLY_TYPE_MAP[count_type]
            val_dtype = _PLY_TYPE_MAP[val_type]
            face_dtype = np.dtype([("cnt", count_dtype), ("idx", val_dtype, 3)])
            fbuf = f.read(face_el["count"] * face_dtype.itemsize)
            frec = np.frombuffer(fbuf, dtype=face_dtype, count=face_el["count"])
            if not np.all(frec["cnt"] == 3):
                raise ValueError(f"{path}: non-triangular face found")
            faces = frec["idx"].astype(np.int64)

    return vertices, faces


def face_geometry(vertices: np.ndarray, faces: np.ndarray):
    """Per-face centroid and unit normal from triangle vertices."""
    v0 = vertices[faces[:, 0]]
    v1 = vertices[faces[:, 1]]
    v2 = vertices[faces[:, 2]]
    centroids = (v0 + v1 + v2) / 3.0
    raw_normals = np.cross(v1 - v0, v2 - v0)
    lengths = np.linalg.norm(raw_normals, axis=1)
    valid = lengths > 1e-9
    normals = np.zeros_like(raw_normals)
    normals[valid] = raw_normals[valid] / lengths[valid, None]
    return centroids[valid], normals[valid]


def refine_cylinder(points: np.ndarray, normals: np.ndarray) -> dict:
    """Axis from the null direction of the face-normal covariance, then a trimmed
    circle fit in the plane perpendicular to it, per plan section 4.6."""
    cov = normals.T @ normals
    eigvals, eigvecs = np.linalg.eigh(cov)
    axis = eigvecs[:, 0]
    axis = axis / np.linalg.norm(axis)

    origin = points.mean(axis=0)
    rel = points - origin
    seed = np.array([1.0, 0.0, 0.0]) if abs(axis[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = np.cross(axis, seed)
    u = u / np.linalg.norm(u)
    v = np.cross(axis, u)

    pu = rel @ u
    pv = rel @ v
    along = rel @ axis

    fit = fit_circle_trimmed(pu, pv)
    cx, cy = fit["centre"]
    radius = fit["radius"]
    mask = fit["inlier_mask"]

    residual = np.sqrt((pu - cx) ** 2 + (pv - cy) ** 2) - radius
    support = int(mask.sum())
    rms = float(np.sqrt(np.mean(residual[mask] ** 2))) if support else float("nan")
    p95 = float(np.percentile(np.abs(residual[mask]), 95)) if support else float("nan")
    length = float(along[mask].max() - along[mask].min()) if support else 0.0
    point3d = origin + cx * u + cy * v

    return {
        "axis": axis.tolist(), "point": point3d.tolist(), "radius": float(radius),
        "length": length, "support": support, "rms": rms, "p95": p95,
        "render_points": points[mask], "render_residuals": residual[mask],
    }


def refine_plane(points: np.ndarray) -> dict:
    """Trimmed least-squares plane, same 3-sigma / 8-iteration scheme as the circle fit."""
    mask = np.ones(points.shape[0], dtype=bool)
    centre = points.mean(axis=0)
    normal = np.array([0.0, 0.0, 1.0])

    for _ in range(8):
        subset = points[mask]
        centre = subset.mean(axis=0)
        centred = subset - centre
        cov = centred.T @ centred
        eigvals, eigvecs = np.linalg.eigh(cov)
        normal = eigvecs[:, 0]
        normal = normal / np.linalg.norm(normal)

        residual_all = (points - centre) @ normal
        sigma = residual_all[mask].std()
        if sigma < 1e-9:
            mask = np.abs(residual_all) <= 1e-9
            break
        mask = np.abs(residual_all) <= 3 * sigma

    residual_all = (points - centre) @ normal
    support = int(mask.sum())
    rms = float(np.sqrt(np.mean(residual_all[mask] ** 2))) if support else float("nan")
    p95 = float(np.percentile(np.abs(residual_all[mask]), 95)) if support else float("nan")

    return {
        "axis": normal.tolist(), "point": centre.tolist(), "radius": None,
        "length": None, "support": support, "rms": rms, "p95": p95,
        "render_points": points[mask], "render_residuals": residual_all[mask],
    }


def _write_rgb_png(path: Path, image: np.ndarray) -> None:
    height, width, _ = image.shape

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data))
        )

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)

    raw = bytearray()
    for r in range(height):
        raw.append(0)
        raw.extend(image[r].tobytes())
    idat = zlib.compress(bytes(raw), level=9)

    png = sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def write_deviation_png(points: np.ndarray, residuals: np.ndarray, path: Path,
                         axes=(0, 1), mm_per_px: float = 1.0) -> None:
    """Points coloured by signed residual, -1 to +1 mm: blue negative, white zero, red positive."""
    if points.shape[0] == 0:
        _write_rgb_png(path, np.full((10, 10, 3), 255, dtype=np.uint8))
        return

    x = points[:, axes[0]]
    y = points[:, axes[1]]
    x_min, x_max = x.min(), x.max()
    y_min, y_max = y.min(), y.max()

    width = max(1, int(np.ceil((x_max - x_min) / mm_per_px)) + 1)
    height = max(1, int(np.ceil((y_max - y_min) / mm_per_px)) + 1)

    col = np.clip(((x - x_min) / mm_per_px).astype(np.int64), 0, width - 1)
    row = np.clip(((y_max - y) / mm_per_px).astype(np.int64), 0, height - 1)
    flat_idx = row * width + col

    clipped = np.clip(residuals, -1.0, 1.0)
    sum_res = np.zeros(width * height, dtype=np.float64)
    count = np.zeros(width * height, dtype=np.float64)
    np.add.at(sum_res, flat_idx, clipped)
    np.add.at(count, flat_idx, 1.0)

    has_data = count > 0
    mean_res = np.zeros_like(sum_res)
    mean_res[has_data] = sum_res[has_data] / count[has_data]
    t = (mean_res + 1.0) / 2.0

    image = np.full((width * height, 3), 255, dtype=np.uint8)
    r = np.where(t < 0.5, t * 2 * 255, 255.0)
    g = np.where(t < 0.5, t * 2 * 255, (1 - t) * 2 * 255)
    b = np.where(t < 0.5, 255.0, (1 - t) * 2 * 255)
    image[has_data, 0] = r[has_data].astype(np.uint8)
    image[has_data, 1] = g[has_data].astype(np.uint8)
    image[has_data, 2] = b[has_data].astype(np.uint8)

    _write_rgb_png(path, image.reshape(height, width, 3))


def _is_candidate(prim: dict, tube_radii_mm) -> bool:
    if prim["kind"] == "cylinder":
        in_bracket = any(lo <= prim["radius"] <= hi for lo, hi in tube_radii_mm)
        return in_bracket and prim["rms"] < CYLINDER_CANDIDATE_RMS_MAX
    return prim["rms"] < PLANE_CANDIDATE_RMS_MAX and prim["support"] > PLANE_CANDIDATE_SUPPORT_MIN


def fit_region(name: str, config: dict, tube_radii_mm) -> dict:
    primitives_path = ARTEFACTS_DIR / f"primitives-{name}.json"
    primitives = json.loads(primitives_path.read_text())["primitives"]

    data_root = config["data_root"]
    full_path = data_root / "crops" / name / f"{name}_full.ply"
    vertices, faces = _read_ply_mesh(full_path)
    centroids, normals = face_geometry(vertices, faces)

    rows = []
    render_points, render_residuals = [], []

    for prim in primitives:
        if not _is_candidate(prim, tube_radii_mm):
            continue

        kind = prim["kind"]
        centre = np.array(prim["centre"])
        axis_or_normal = np.array(prim["axis"])
        id_ = f"{name}/{'cyl' if kind == 'cylinder' else 'plane'}/{prim['index']:03d}"

        if kind == "cylinder":
            rel = centroids - centre
            along = rel @ axis_or_normal
            perp = rel - np.outer(along, axis_or_normal)
            dist = np.linalg.norm(perp, axis=1) - prim["radius"]
            half_length = prim["length"] / 2.0 + MARGIN_MM
            sel = (np.abs(dist) <= MARGIN_MM) & (np.abs(along) <= half_length)
        else:
            dist = (centroids - centre) @ axis_or_normal
            sel = np.abs(dist) <= MARGIN_MM
        pts = centroids[sel]
        nrm = normals[sel]

        if pts.shape[0] < MIN_POINTS_FOR_FIT:
            rows.append({
                "id": id_, "kind": kind, "axis": None, "point": None, "radius": None,
                "length": None, "support": int(pts.shape[0]), "rms": None, "p95": None,
                "accepted": False,
                "reason": f"fewer than {MIN_POINTS_FOR_FIT} full-res points within {MARGIN_MM} mm",
            })
            continue

        result = refine_cylinder(pts, nrm) if kind == "cylinder" else refine_plane(pts)
        accept_max = CYLINDER_ACCEPT_RMS_MAX if kind == "cylinder" else PLANE_ACCEPT_RMS_MAX
        accepted = result["rms"] < accept_max

        row = {
            "id": id_, "kind": kind, "axis": result["axis"], "point": result["point"],
            "radius": result["radius"], "length": result["length"],
            "support": result["support"], "rms": result["rms"], "p95": result["p95"],
            "accepted": accepted,
        }
        if not accepted:
            row["reason"] = f"refined rms {result['rms']:.3f} mm >= {accept_max} mm"
        rows.append(row)

        render_points.append(result["render_points"])
        render_residuals.append(result["render_residuals"])

    all_points = np.concatenate(render_points, axis=0) if render_points else np.zeros((0, 3))
    all_residuals = np.concatenate(render_residuals, axis=0) if render_residuals else np.zeros((0,))
    write_deviation_png(all_points, all_residuals, ARTEFACTS_DIR / f"deviation-{name}.png")

    return {"region": name, "primitives": rows}


def merge_interfaces(region_result: dict) -> list:
    path = ARTEFACTS_DIR / "interfaces.json"
    doc = json.loads(path.read_text()) if path.exists() else []
    doc = [r for r in doc if r["region"] != region_result["region"]]
    doc.append(region_result)
    doc.sort(key=lambda r: REGIONS.index(r["region"]))
    path.write_text(json.dumps(doc, indent=2))
    return doc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", choices=REGIONS, required=True)
    args = parser.parse_args()

    config = load_config()
    tube_radii_mm = config.get("tube_radii_mm", DEFAULT_TUBE_RADII_MM)

    result = fit_region(args.region, config, tube_radii_mm)
    merge_interfaces(result)

    accepted = [r for r in result["primitives"] if r["accepted"]]
    rejected = [r for r in result["primitives"] if not r["accepted"]]
    worst = sorted(
        (r for r in result["primitives"] if r.get("rms") is not None),
        key=lambda r: r["rms"], reverse=True,
    )[:5]

    print(
        f"{args.region}: candidates={len(result['primitives'])} "
        f"accepted={len(accepted)} rejected={len(rejected)}"
    )
    for r in worst:
        print(f"  worst: {r['id']} kind={r['kind']} rms={r['rms']:.3f} p95={r['p95']:.3f}")


if __name__ == "__main__":
    main()
