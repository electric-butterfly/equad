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


# ---------------------------------------------------------------------------
# Sweep grid, full sweep, summary
# ---------------------------------------------------------------------------

def sweep_grid(sweep_params: dict) -> list[tuple[float, float, float, float]]:
    xs = sweep_params["x"]
    y0, y1, ys = sweep_params["y_range"]
    z0, z1, zs = sweep_params["z_range"]
    l0, l1, ls = sweep_params["lean_range"]
    ys_list = np.round(np.arange(y0, y1 + ys / 2, ys), 6).tolist()
    zs_list = np.round(np.arange(z0, z1 + zs / 2, zs), 6).tolist()
    ls_list = np.round(np.arange(l0, l1 + ls / 2, ls), 6).tolist()
    return [(x, y, z, l) for x in xs for y in ys_list for z in zs_list for l in ls_list]


def _build_scenes(params: dict):
    chassis_scene, chassis_verts, n_verts, n_faces = load_scene(params)
    motor_tm = motor_mesh(params)
    keepout_tm = keepout_mesh(params)
    motor_o3d = trimesh_to_o3d(motor_tm)
    keepout_o3d = trimesh_to_o3d(keepout_tm)
    motor_scene = scene_from_mesh(motor_o3d)
    keepout_scene = scene_from_mesh(keepout_o3d)
    motor_verts = motor_o3d.vertex.positions.numpy()
    keepout_verts = keepout_o3d.vertex.positions.numpy()
    return chassis_scene, chassis_verts, n_verts, n_faces, motor_tm, motor_scene, motor_verts, keepout_scene, keepout_verts


def run_sweep(params: dict) -> list[dict]:
    grid = sweep_grid(params["sweep"])
    print(f"sweep grid: {len(grid)} placements")
    (chassis_scene, chassis_verts, n_verts, n_faces, motor_tm, motor_scene, motor_verts,
     keepout_scene, keepout_verts) = _build_scenes(params)
    print(f"chassis: {n_faces} faces, {n_verts} vertices")

    n_samples = params["sweep"]["samples"]
    clearance_min = params["placement"]["clearance_min"]

    rows = []
    t0 = time.time()
    for i, (x, y, z, lean) in enumerate(grid):
        row = evaluate(
            params, x, y, z, lean,
            chassis_scene, chassis_verts, motor_scene, motor_verts, keepout_scene, keepout_verts,
            n_samples, clearance_min,
        )
        rows.append(row)
        if (i + 1) % 200 == 0:
            print(f"  {i + 1}/{len(grid)} ({time.time() - t0:.1f}s elapsed)")
    print(f"sweep done: {len(grid)} placements in {time.time() - t0:.1f}s")

    artefacts = artefacts_dir()
    (artefacts / "sweep.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"wrote sweep.json ({(artefacts / 'sweep.json').stat().st_size} bytes)")

    mf_min, mf_inside = motor_vs_frame(params, chassis_scene, chassis_verts, motor_scene, motor_tm, n_samples)
    print(f"motor_frame_min: {mf_min} mm, motor_frame_inside: {mf_inside}")

    return rows, mf_min, mf_inside


def summarise(rows: list[dict], params: dict) -> dict:
    xs = sorted(set(r["x"] for r in rows))
    leans = sorted(set(r["lean"] for r in rows))

    per_x_lean = {}
    for x in xs:
        for lean in leans:
            subset = [r for r in rows if r["x"] == x and r["lean"] == lean and r["pass"]]
            if subset:
                ys = sorted(set(r["y"] for r in subset))
                zs = sorted(set(r["z"] for r in subset))
                best = max(subset, key=lambda r: r["min_frame"])
                per_x_lean[(x, lean)] = {
                    "y_range": (min(ys), max(ys)), "z_range": (min(zs), max(zs)),
                    "best_min_frame": best["min_frame"],
                }
            else:
                per_x_lean[(x, lean)] = None

    passing = [r for r in rows if r["pass"]]
    best_overall = max(passing, key=lambda r: r["min_frame"]) if passing else None

    pl = params["placement"]
    defaults_row = None
    for r in rows:
        if (abs(r["x"] - pl["x"]) < 1e-6 and abs(r["y"] - pl["y"]) < 1e-6
                and abs(r["z"] - pl["z"]) < 1e-6 and abs(r["lean"] - pl["lean_deg"]) < 1e-6):
            defaults_row = r
            break

    return {"xs": xs, "leans": leans, "per_x_lean": per_x_lean, "best_overall": best_overall,
            "defaults_row": defaults_row, "n_pass": len(passing), "n_total": len(rows)}


# ---------------------------------------------------------------------------
# Section renders
# ---------------------------------------------------------------------------

def _box_edges_local() -> list[tuple[int, int]]:
    # 8 corners indexed 0-7 as (x in {0,1}, y in {0,1}, z in {0,1}); 12 edges of a box
    return [(0, 1), (2, 3), (4, 5), (6, 7),  # along x
            (0, 2), (1, 3), (4, 6), (5, 7),  # along y
            (0, 4), (1, 5), (2, 6), (3, 7)]  # along z


def _box_corners_local(params: dict) -> np.ndarray:
    mesh = get_shell_mesh(params)
    v = np.asarray(mesh.vertices)
    lo, hi = v.min(axis=0), v.max(axis=0)
    xs, ys, zs = [lo[0], hi[0]], [lo[1], hi[1]], [lo[2], hi[2]]
    return np.array([[x, y, z] for x in xs for y in ys for z in zs])


def render_section(params: dict, plane: str, placement: tuple[float, float, float, float],
                    name: str, mesh_1m_verts: np.ndarray) -> Path:
    from PIL import Image, ImageDraw

    x, y, z, lean = placement
    m = params["motor"]
    k = params["keepout"]
    motor_tm = motor_mesh(params)
    keepout_tm = keepout_mesh(params)
    local_corners = _box_corners_local(params)
    edges = _box_edges_local()
    left_corners = place_vertices(local_corners, x, y, z, lean, "left")
    right_corners = place_vertices(local_corners, x, y, z, lean, "right")

    scale = 1.0
    if plane == "yz":
        slab = mesh_1m_verts[np.abs(mesh_1m_verts[:, 0] - x) <= 100]
        def proj(p):
            return (-p[1], p[2])
        grid_h, grid_v = "y", "z"
    elif plane == "xz":
        slab = mesh_1m_verts[np.abs(mesh_1m_verts[:, 1]) <= 450]
        def proj(p):
            return (p[0], p[2])
        grid_h, grid_v = "x", "z"
    elif plane == "xy":
        slab = mesh_1m_verts[(mesh_1m_verts[:, 2] >= 150) & (mesh_1m_verts[:, 2] <= 700)]
        def proj(p):
            return (p[0], p[1])
        grid_h, grid_v = "x", "y"
    else:
        raise ValueError(plane)

    pts = np.array([proj(p) for p in slab]) if len(slab) else np.zeros((0, 2))
    all_h = [proj(c)[0] for c in left_corners] + [proj(c)[0] for c in right_corners]
    all_v = [proj(c)[1] for c in left_corners] + [proj(c)[1] for c in right_corners]
    if len(pts):
        all_h += pts[:, 0].tolist()
        all_v += pts[:, 1].tolist()
    h_min, h_max = min(all_h) - 50, max(all_h) + 50
    v_min, v_max = min(all_v) - 50, max(all_v) + 50
    W = max(200, int((h_max - h_min) * scale))
    H = max(200, int((v_max - v_min) * scale))
    W, H = min(W, 2000), min(H, 2000)

    img = Image.new("RGB", (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    def to_px(hv):
        h, v = hv
        return (int((h - h_min) / (h_max - h_min) * W), int(H - (v - v_min) / (v_max - v_min) * H))

    for g in np.arange(np.floor(h_min / 100) * 100, h_max + 100, 100):
        x0, y0 = to_px((g, v_min)); x1, y1 = to_px((g, v_max))
        draw.line([x0, y0, x1, y1], fill=(225, 225, 225))
    for g in np.arange(np.floor(v_min / 100) * 100, v_max + 100, 100):
        x0, y0 = to_px((h_min, g)); x1, y1 = to_px((h_max, g))
        draw.line([x0, y0, x1, y1], fill=(225, 225, 225))

    for p in pts[::max(1, len(pts) // 150000)]:
        px, py = to_px(p)
        if 0 <= px < W and 0 <= py < H:
            draw.point((px, py), fill=(120, 120, 120))

    ox, oy = to_px((0, 0))
    draw.line([ox, 0, ox, H], fill=(255, 0, 0))
    draw.line([0, oy, W, oy], fill=(255, 0, 0))

    for corners, color in ((left_corners, (0, 60, 220)), (right_corners, (0, 60, 220))):
        proj_c = [proj(c) for c in corners]
        for a, b in edges:
            draw.line([to_px(proj_c[a]), to_px(proj_c[b])], fill=color, width=2)

    for tm, color in ((motor_tm, (230, 120, 0)), (keepout_tm, (0, 150, 0))):
        vv = np.asarray(tm.vertices)
        proj_v = np.array([proj(p) for p in vv])
        for i in range(0, len(proj_v), max(1, len(proj_v) // 200)):
            px, py = to_px(proj_v[i])
            if 0 <= px < W and 0 <= py < H:
                draw.ellipse([px - 1, py - 1, px + 1, py + 1], fill=color)

    out = artefacts_dir() / f"section-{plane}-{name}.png"
    img.save(out)
    return out


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def write_report(params: dict, summary: dict, mf_min: float, mf_inside: int,
                  chamfer_note: str) -> Path:
    lines = []
    lines.append(
        "This sweep tests the frame, the placeholder motor and the propeller-shaft keep-out only; "
        "plastics, foot boards, tank and seat are not in the scan."
    )
    lines.append("")
    lines.append(f"Grid: {summary['n_total']} placements, {summary['n_pass']} pass.")
    lines.append("")
    lines.append("| X | lean | feasible Y | feasible Z | best min_frame |")
    lines.append("|---|---|---|---|---|")
    for x in summary["xs"]:
        for lean in summary["leans"]:
            info = summary["per_x_lean"][(x, lean)]
            if info is None:
                lines.append(f"| {x} | {lean} | - | - | none feasible |")
            else:
                lines.append(
                    f"| {x} | {lean} | {info['y_range'][0]:.1f}-{info['y_range'][1]:.1f} | "
                    f"{info['z_range'][0]:.1f}-{info['z_range'][1]:.1f} | {info['best_min_frame']:.1f} |"
                )
    lines.append("")

    best = summary["best_overall"]
    if best:
        lines.append(
            f"Best placement: x={best['x']}, y={best['y']}, z={best['z']}, lean={best['lean']} "
            f"-> min_frame={best['min_frame']}, min_motor={best['min_motor']}, min_keepout={best['min_keepout']}."
        )
    else:
        lines.append("No placement in the swept grid passes all three tests.")
    lines.append("")

    dr = summary["defaults_row"]
    pl = params["placement"]
    if dr:
        lines.append(
            f"[placement] defaults (x={pl['x']}, y={pl['y']}, z={pl['z']}, lean_deg={pl['lean_deg']}): "
            f"{'PASS' if dr['pass'] else 'FAIL'} - min_frame={dr['min_frame']}, "
            f"min_motor={dr['min_motor']}, min_keepout={dr['min_keepout']}, "
            f"inside_frame={dr['inside_frame']}, inside_motor={dr['inside_motor']}, "
            f"inside_keepout={dr['inside_keepout']}."
        )
    else:
        lines.append(
            f"[placement] defaults (x={pl['x']}, y={pl['y']}, z={pl['z']}, lean_deg={pl['lean_deg']}) "
            "are not a grid point in this sweep, so no exact-match row exists; see the nearest grid rows above."
        )
    lines.append("")
    lines.append(f"Motor placeholder vs frame (not part of pass, evaluated once): "
                  f"min_frame={mf_min} mm, points inside={mf_inside}.")
    lines.append("")
    lines.append(chamfer_note)

    out = artefacts_dir() / "sweep-report.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", type=Path, default=None)
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--render", action="store_true")
    args = ap.parse_args()

    params = load_params(args.params)

    if args.controls:
        run_controls(params)
        return

    if args.sweep:
        rows, mf_min, mf_inside = run_sweep(params)
        summary = summarise(rows, params)
        print(f"pass count: {summary['n_pass']} / {summary['n_total']}")
        if summary["best_overall"]:
            print("best overall:", summary["best_overall"])
        chamfer_note = "chamfer would not help: not evaluated in this run."
        write_report(params, summary, mf_min, mf_inside, chamfer_note)
        print("wrote sweep-report.md")
        return

    if args.render:
        artefacts = artefacts_dir()
        rows = json.loads((artefacts / "sweep.json").read_text(encoding="utf-8"))
        summary = summarise(rows, params)
        repo = repo_root()
        import trimesh as _tm
        mesh_1m = _tm.load(repo / params["chassis"]["mesh_1m"], process=False)
        mesh_1m_verts = np.asarray(mesh_1m.vertices)

        pl = params["placement"]
        default_pl = (pl["x"], pl["y"], pl["z"], pl["lean_deg"])
        for plane in ("yz", "xz", "xy"):
            out = render_section(params, plane, default_pl, "default", mesh_1m_verts)
            print("wrote", out, out.stat().st_size, "bytes")

        best = summary["best_overall"]
        if best:
            best_pl = (best["x"], best["y"], best["z"], best["lean"])
            for plane in ("yz", "xz", "xy"):
                out = render_section(params, plane, best_pl, "best", mesh_1m_verts)
                print("wrote", out, out.stat().st_size, "bytes")
        else:
            print("no best-overall placement to render (nothing passed the sweep)")
        return

    print("Nothing to do: pass --controls, --sweep or --render.")


if __name__ == "__main__":
    main()
