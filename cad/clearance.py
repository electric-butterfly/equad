"""Clearance evaluation, the sweep and section renders against the datum-aligned frame mesh.

Runs under .venv-mesh. Plan section 4.7: for one placement (x, y, z, lean) of the two boxes,
test surface distance and point-inside-solid occupancy against the frame, the placeholder motor
and the propeller-shaft keep-out.
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np
import open3d as o3d
import trimesh

from common import artefacts_dir, load_params, repo_root

SAMPLE_SEED = 42


# ---------------------------------------------------------------------------
# The section 4.6 transform, in numpy
# ---------------------------------------------------------------------------

def left_matrix(lean_deg: float) -> np.ndarray:
    """R of section 4.6: local +Z -> (0, sin phi, cos phi), local +Y -> (0, cos phi, -sin phi)."""
    phi = np.radians(lean_deg)
    return np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, np.cos(phi), np.sin(phi)],
            [0.0, -np.sin(phi), np.cos(phi)],
        ]
    )


def place_vertices(local_verts: np.ndarray, x: float, y: float, z: float, lean_deg: float, side: str) -> np.ndarray:
    """p_vehicle = [x, y, z] + R . p_local for the left box; the right box mirrors through Y = 0."""
    R = left_matrix(lean_deg)
    placed = local_verts @ R.T + np.array([x, y, z])
    if side == "right":
        placed = placed * np.array([1.0, -1.0, 1.0])
    return placed


# ---------------------------------------------------------------------------
# The frame mesh (loaded once)
# ---------------------------------------------------------------------------

def load_scene(params: dict) -> tuple[o3d.t.geometry.RaycastingScene, np.ndarray, int, int]:
    """Read [chassis].mesh into an Open3D RaycastingScene. Returns (scene, vertices, n_verts, n_faces)."""
    mesh_path = repo_root() / params["chassis"]["mesh"]
    if not mesh_path.exists():
        raise FileNotFoundError(f"chassis mesh not found: {mesh_path}")
    mesh = o3d.t.io.read_triangle_mesh(str(mesh_path))
    verts = mesh.vertex.positions.numpy()
    n_verts = verts.shape[0]
    n_faces = mesh.triangle.indices.shape[0]
    scene = o3d.t.geometry.RaycastingScene()
    scene.add_triangles(mesh)
    return scene, verts, n_verts, n_faces


# ---------------------------------------------------------------------------
# The box shell: local mesh, local surface samples, per-placement transform
# ---------------------------------------------------------------------------

_SHELL_CACHE: dict[float, trimesh.Trimesh] = {}
_SAMPLE_CACHE: dict[tuple[float, int], np.ndarray] = {}


def chamfer_shell(mesh: trimesh.Trimesh, params: dict, leg: float) -> trimesh.Trimesh:
    """Cut a 45 deg chamfer of the given leg length on the box-local +X/+Z top edge (plan 4.5),
    by slicing the shell with the chamfer plane and capping the cut face."""
    e = params["enclosure"]
    outer_x = e["internal"][0] + 2 * e["sheet"]
    top_z = e["internal"][2] + e["sheet"]
    x_edge = outer_x / 2
    plane_origin = np.array([x_edge - leg, 0.0, top_z])
    plane_normal = np.array([1.0, 0.0, 1.0]) / np.sqrt(2)
    # keep the side away from the corner being chamfered off
    return mesh.slice_plane(plane_origin, -plane_normal, cap=True)


def get_shell_mesh(params: dict, chamfer_leg: float = 0.0) -> trimesh.Trimesh:
    key = round(chamfer_leg, 3)
    if key not in _SHELL_CACHE:
        path = artefacts_dir() / "box-shell.stl"
        if not path.exists():
            raise FileNotFoundError(f"box-shell.stl not found: {path}")
        mesh = trimesh.load(path, process=True)
        if key > 0:
            mesh = chamfer_shell(mesh, params, key)
        _SHELL_CACHE[key] = mesh
    return _SHELL_CACHE[key]


def get_local_samples(params: dict, n: int, chamfer_leg: float = 0.0) -> np.ndarray:
    key = (round(chamfer_leg, 3), n)
    if key not in _SAMPLE_CACHE:
        mesh = get_shell_mesh(params, chamfer_leg)
        pts, _ = trimesh.sample.sample_surface(mesh, n, seed=SAMPLE_SEED)
        _SAMPLE_CACHE[key] = np.asarray(pts)
    return _SAMPLE_CACHE[key]


def placed_shell_o3d(params: dict, x: float, y: float, z: float, lean_deg: float, side: str,
                      chamfer_leg: float = 0.0) -> o3d.t.geometry.TriangleMesh:
    mesh = get_shell_mesh(params, chamfer_leg)
    verts = place_vertices(np.asarray(mesh.vertices), x, y, z, lean_deg, side)
    faces = np.asarray(mesh.faces)
    m = o3d.t.geometry.TriangleMesh()
    m.vertex.positions = o3d.core.Tensor(verts.astype(np.float32))
    m.triangle.indices = o3d.core.Tensor(faces.astype(np.int32))
    return m


# ---------------------------------------------------------------------------
# Motor and keep-out cylinders (fixed for the whole sweep)
# ---------------------------------------------------------------------------

def _cylinder_mesh(radius: float, length: float, axis: str, centre) -> trimesh.Trimesh:
    cyl = trimesh.creation.cylinder(radius=radius, height=length, sections=64)
    if axis == "Y":
        cyl.apply_transform(trimesh.transformations.rotation_matrix(np.radians(90), [1, 0, 0]))
    elif axis == "X":
        cyl.apply_transform(trimesh.transformations.rotation_matrix(np.radians(90), [0, 1, 0]))
    cyl.apply_translation(centre)
    return cyl


def motor_mesh(params: dict) -> trimesh.Trimesh:
    m = params["motor"]
    return _cylinder_mesh(m["housing_d"] / 2, m["length"], m["axis"], m["centre"])


def keepout_mesh(params: dict) -> trimesh.Trimesh:
    k = params["keepout"]
    x_lo, x_hi = k["x_range"]
    length = x_hi - x_lo
    x_mid = (x_lo + x_hi) / 2
    return _cylinder_mesh(k["radius"], length, "X", [x_mid, k["axis_y"], k["axis_z"]])


def trimesh_to_o3d(tm: trimesh.Trimesh) -> o3d.t.geometry.TriangleMesh:
    m = o3d.t.geometry.TriangleMesh()
    m.vertex.positions = o3d.core.Tensor(np.asarray(tm.vertices, dtype=np.float32))
    m.triangle.indices = o3d.core.Tensor(np.asarray(tm.faces, dtype=np.int32))
    return m


def scene_from_mesh(mesh: o3d.t.geometry.TriangleMesh) -> o3d.t.geometry.RaycastingScene:
    s = o3d.t.geometry.RaycastingScene()
    s.add_triangles(mesh)
    return s


# ---------------------------------------------------------------------------
# Distance and occupancy primitives
# ---------------------------------------------------------------------------

def min_distance(scene: o3d.t.geometry.RaycastingScene, points: np.ndarray) -> float:
    q = o3d.core.Tensor(points.astype(np.float32))
    d = scene.compute_distance(q).numpy()
    return float(d.min())


def inside_count(box_scene: o3d.t.geometry.RaycastingScene, candidate_verts: np.ndarray,
                  aabb_min: np.ndarray, aabb_max: np.ndarray) -> int:
    mask = np.all((candidate_verts >= aabb_min) & (candidate_verts <= aabb_max), axis=1)
    inside_aabb = candidate_verts[mask]
    if inside_aabb.shape[0] == 0:
        return 0
    q = o3d.core.Tensor(inside_aabb.astype(np.float32))
    occ = box_scene.compute_occupancy(q).numpy()
    return int(occ.sum())


# ---------------------------------------------------------------------------
# evaluate(): section 4.7 steps 1-5 for one placement; motor_vs_frame(): step 6
# ---------------------------------------------------------------------------

def evaluate(params: dict, x: float, y: float, z: float, lean_deg: float,
             chassis_scene, chassis_verts: np.ndarray,
             motor_scene, motor_verts: np.ndarray,
             keepout_scene, keepout_verts: np.ndarray,
             n_samples: int, clearance_min: float, chamfer_leg: float = 0.0) -> dict:
    local_samples = get_local_samples(params, n_samples, chamfer_leg)

    min_frame = min_motor = min_keepout = float("inf")
    inside_frame = inside_motor = inside_keepout = 0

    for side in ("left", "right"):
        placed_samples = place_vertices(local_samples, x, y, z, lean_deg, side)
        box_mesh = placed_shell_o3d(params, x, y, z, lean_deg, side, chamfer_leg)
        box_scene = scene_from_mesh(box_mesh)
        box_verts = box_mesh.vertex.positions.numpy()
        aabb_min = box_verts.min(axis=0)
        aabb_max = box_verts.max(axis=0)

        min_frame = min(min_frame, min_distance(chassis_scene, placed_samples))
        inside_frame += inside_count(box_scene, chassis_verts, aabb_min, aabb_max)

        min_motor = min(min_motor, min_distance(motor_scene, placed_samples))
        inside_motor += inside_count(box_scene, motor_verts, aabb_min, aabb_max)

        min_keepout = min(min_keepout, min_distance(keepout_scene, placed_samples))
        inside_keepout += inside_count(box_scene, keepout_verts, aabb_min, aabb_max)

    passed = (
        inside_frame == 0 and min_frame >= clearance_min
        and inside_motor == 0 and min_motor >= clearance_min
        and inside_keepout == 0 and min_keepout >= clearance_min
    )

    return {
        "x": x, "y": y, "z": z, "lean": lean_deg,
        "min_frame": round(min_frame, 3), "inside_frame": inside_frame,
        "min_motor": round(min_motor, 3), "inside_motor": inside_motor,
        "min_keepout": round(min_keepout, 3), "inside_keepout": inside_keepout,
        "pass": passed,
    }


def motor_vs_frame(params: dict, chassis_scene, chassis_verts: np.ndarray,
                    motor_scene, motor_mesh_tm: trimesh.Trimesh, n_samples: int) -> tuple[float, int]:
    """Section 4.7 step 6: the motor placeholder's own clearance to the frame, computed once."""
    pts, _ = trimesh.sample.sample_surface(motor_mesh_tm, n_samples, seed=SAMPLE_SEED)
    motor_frame_min = min_distance(chassis_scene, np.asarray(pts))

    motor_o3d = trimesh_to_o3d(motor_mesh_tm)
    motor_scene_ray = scene_from_mesh(motor_o3d)
    verts = motor_o3d.vertex.positions.numpy()
    aabb_min = verts.min(axis=0)
    aabb_max = verts.max(axis=0)
    motor_frame_inside = inside_count(motor_scene_ray, chassis_verts, aabb_min, aabb_max)
    return round(motor_frame_min, 3), motor_frame_inside


# ---------------------------------------------------------------------------
# Controls (plan section 4.7 table) -- the canary
# ---------------------------------------------------------------------------

CONTROLS = {
    "collision": {"x": 713.0, "y": 300.0, "z": 330.0, "lean": -30.0, "expect": "inside > 50000, min_frame < 1.0"},
    "clear": {"x": 700.0, "y": 300.0, "z": 1500.0, "lean": 30.0, "expect": "inside = 0, min_frame > 200"},
}


def run_controls(params: dict) -> None:
    print("loading chassis scene...")
    t0 = time.time()
    chassis_scene, chassis_verts, n_verts, n_faces = load_scene(params)
    print(f"chassis: {n_faces} faces, {n_verts} vertices ({time.time() - t0:.1f}s)")

    motor_tm = motor_mesh(params)
    keepout_tm = keepout_mesh(params)
    motor_scene = scene_from_mesh(trimesh_to_o3d(motor_tm))
    keepout_scene = scene_from_mesh(trimesh_to_o3d(keepout_tm))
    motor_o3d = trimesh_to_o3d(motor_tm)
    keepout_o3d = trimesh_to_o3d(keepout_tm)
    motor_verts = motor_o3d.vertex.positions.numpy()
    keepout_verts = keepout_o3d.vertex.positions.numpy()

    n_samples = params["sweep"]["samples"]
    clearance_min = params["placement"]["clearance_min"]

    for name, c in CONTROLS.items():
        t0 = time.time()
        row = evaluate(
            params, c["x"], c["y"], c["z"], c["lean"],
            chassis_scene, chassis_verts, motor_scene, motor_verts, keepout_scene, keepout_verts,
            n_samples, clearance_min,
        )
        print(f"{name} ({c['x']}, {c['y']}, {c['z']}, {c['lean']}): {row} [{time.time() - t0:.2f}s] expect {c['expect']}")

    mf_min, mf_inside = motor_vs_frame(params, chassis_scene, chassis_verts, motor_scene, motor_tm, n_samples)
    print(f"motor_frame_min: {mf_min} mm, motor_frame_inside: {mf_inside}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", type=Path, default=None)
    ap.add_argument("--controls", action="store_true")
    args = ap.parse_args()

    params = load_params(args.params)

    if args.controls:
        run_controls(params)
        return

    print("Nothing to do: pass --controls (more flags land with later batches).")


if __name__ == "__main__":
    main()
