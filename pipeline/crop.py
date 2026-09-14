"""Crop stage of the eQuad scan pipeline: cut the six named regions of pipeline/crops.toml
from the datum-aligned mesh, per plan section 4.4."""

import argparse
import tomllib
from pathlib import Path

import numpy as np
import open3d as o3d
import trimesh

from common import load_config, _write_gray_png

REGIONS = [
    "engine-bay",
    "tank-mounts",
    "front-flange",
    "rear-flange",
    "duct-route",
    "rear-axle",
]


def load_crops(path: Path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def in_box(points: np.ndarray, box: dict) -> np.ndarray:
    x_min, x_max = box["x"]
    y_min, y_max = box["y"]
    z_min, z_max = box["z"]
    return (
        (points[:, 0] >= x_min) & (points[:, 0] <= x_max)
        & (points[:, 1] >= y_min) & (points[:, 1] <= y_max)
        & (points[:, 2] >= z_min) & (points[:, 2] <= z_max)
    )


def _shade(points: np.ndarray, axes: tuple, depth_axis: int, mm_per_px: float) -> np.ndarray:
    """Depth-shaded 2D array of points projected onto `axes`, nearest-surface per pixel."""
    x = points[:, axes[0]]
    y = points[:, axes[1]]
    z = points[:, depth_axis]

    x_min, x_max = x.min(), x.max()
    y_min, y_max = y.min(), y.max()

    width = max(1, int(np.ceil((x_max - x_min) / mm_per_px)) + 1)
    height = max(1, int(np.ceil((y_max - y_min) / mm_per_px)) + 1)

    col = np.clip(((x - x_min) / mm_per_px).astype(np.int64), 0, width - 1)
    row = np.clip(((y_max - y) / mm_per_px).astype(np.int64), 0, height - 1)

    depth = np.full((height, width), -np.inf, dtype=np.float64)
    flat_idx = row * width + col
    np.maximum.at(depth.reshape(-1), flat_idx, z)

    mask = np.isfinite(depth)
    shaded = np.zeros((height, width), dtype=np.uint8)
    if mask.any():
        z_min, z_max = depth[mask].min(), depth[mask].max()
        span = max(z_max - z_min, 1e-9)
        shaded[mask] = (((depth[mask] - z_min) / span) * 200 + 55).astype(np.uint8)
    return shaded


def _write_silhouette(points: np.ndarray, path: Path, mm_per_px: float = 0.6) -> None:
    """One PNG: plan (XY) and side (XZ) views side by side, separated by a white column."""
    plan = _shade(points, axes=(0, 1), depth_axis=2, mm_per_px=mm_per_px)
    side = _shade(points, axes=(0, 2), depth_axis=1, mm_per_px=mm_per_px)

    height = max(plan.shape[0], side.shape[0])
    gutter = np.full((height, 4), 255, dtype=np.uint8)

    def pad(img):
        if img.shape[0] == height:
            return img
        extra = np.zeros((height - img.shape[0], img.shape[1]), dtype=np.uint8)
        return np.vstack([img, extra])

    combined = np.hstack([pad(plan), gutter, pad(side)])
    _write_gray_png(path, combined)


def crop_region(name: str, box: dict, config: dict) -> dict:
    data_root = config["data_root"]
    out_dir = data_root / "crops" / name
    out_dir.mkdir(parents=True, exist_ok=True)

    mesh_5m_path = data_root / "derived" / "chassis_datum_5M.stl"
    mesh_5m = o3d.io.read_triangle_mesh(str(mesh_5m_path))
    mesh_5m.compute_vertex_normals()
    vertices = np.asarray(mesh_5m.vertices)
    normals = np.asarray(mesh_5m.vertex_normals)

    above_floor = vertices[:, 2] > 6.0
    region_mask = in_box(vertices, box)
    above_floor_in_box = np.count_nonzero(region_mask & above_floor)
    fraction = above_floor_in_box / max(1, np.count_nonzero(above_floor))

    pts = vertices[region_mask]
    pts_normals = normals[region_mask]
    pts_cloud = o3d.geometry.PointCloud()
    pts_cloud.points = o3d.utility.Vector3dVector(pts)
    pts_cloud.normals = o3d.utility.Vector3dVector(pts_normals)
    o3d.io.write_point_cloud(str(out_dir / f"{name}_pts.ply"), pts_cloud, write_ascii=False)

    full_mesh_path = data_root / "derived" / "chassis_datum_full.ply"
    full_mesh = trimesh.load(str(full_mesh_path), process=False)
    face_centroids = full_mesh.vertices[full_mesh.faces].mean(axis=1)
    face_mask = in_box(face_centroids, box)
    cropped = full_mesh.submesh([face_mask], append=True)
    cropped.export(str(out_dir / f"{name}_full.ply"), file_type="ply", encoding="binary")

    _write_silhouette(pts, out_dir / f"{name}_silhouette.png", mm_per_px=0.6)

    return {
        "region": name,
        "point_count": int(pts.shape[0]),
        "fraction": fraction,
        "expected_fraction": box["expected_fraction"],
        "diff_pp": (fraction - box["expected_fraction"]) * 100,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", choices=REGIONS, default=None)
    args = parser.parse_args()

    config = load_config()
    crops = load_crops(Path(__file__).parent / "crops.toml")

    regions = [args.region] if args.region else REGIONS
    for name in regions:
        result = crop_region(name, crops[name], config)
        print(
            f"{result['region']}: points={result['point_count']} "
            f"fraction={result['fraction']:.4f} "
            f"expected={result['expected_fraction']:.4f} "
            f"diff_pp={result['diff_pp']:.3f}"
        )


if __name__ == "__main__":
    main()
