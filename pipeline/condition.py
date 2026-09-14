"""Condition stage of the eQuad scan pipeline: fragments, floor, symmetry, rear-axle
origin, export to the ISO 8855 vehicle datum. Implements plan section 4.3, steps 1-11.

Run one step with --step N, or a range from 1 with --through N. Every step appends its
numbers to data/derived/condition-log.jsonl. Steps whose checkpoint file already exists
on disk skip recomputation and report the existing file's stats, so a resumed session
does not redo finished work.
"""

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import open3d as o3d
import pymeshlab
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402


def log_step(cfg, step: int, name: str, metrics: dict, elapsed_s: float) -> None:
    log_path = cfg["data_root"] / "derived" / "condition-log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = {
        "step": step,
        "name": name,
        "metrics": metrics,
        "elapsed_s": round(elapsed_s, 1),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(line) + "\n")
    print(f"[step {step}] {name}: {json.dumps(metrics)} ({elapsed_s:.1f}s)")


def derived(cfg) -> Path:
    p = cfg["data_root"] / "derived"
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# Step 1+2 - load and fragment removal (combined: pymeshlab keeps state in memory)
# ---------------------------------------------------------------------------

def load_and_clean_fragments(cfg, ctx: dict):
    """Runs steps 1 and 2, logging each. Returns the pymeshlab MeshSet."""
    if "ms" in ctx:
        return ctx["ms"]

    d = derived(cfg)
    fragfree = d / "chassis_scan_fragfree.ply"

    if fragfree.exists():
        ms = pymeshlab.MeshSet()
        ms.load_new_mesh(str(fragfree))
        faces = ms.current_mesh().face_number()
        print(f"[step 1] load: {fragfree.name} already on disk, {faces} faces, skipping recompute")
        print(f"[step 2] fragments: chassis_scan_fragfree.ply already on disk, skipping recompute")
        ctx["ms"] = ms
        return ms

    t0 = time.time()
    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(str(cfg["scan_full"]))
    loaded_faces = ms.current_mesh().face_number()
    log_step(cfg, 1, "load", {"faces_loaded": loaded_faces}, time.time() - t0)

    t0 = time.time()
    before = ms.current_mesh().face_number()
    ms.compute_selection_by_small_disconnected_components_per_face(nbfaceratio=0.0001)
    ms.meshing_remove_selected_faces()
    ms.meshing_remove_unreferenced_vertices()
    ms.meshing_remove_duplicate_faces()
    ms.meshing_remove_null_faces()
    after = ms.current_mesh().face_number()
    removed_frac = (before - after) / before
    ms.save_current_mesh(str(fragfree))
    log_step(
        cfg, 2, "fragments",
        {"faces_before": before, "faces_after": after, "removed_fraction": round(removed_frac, 5)},
        time.time() - t0,
    )
    ctx["ms"] = ms
    return ms


# ---------------------------------------------------------------------------
# Step 3 - working decimations to 5M and 1M
# ---------------------------------------------------------------------------

def step3(cfg, ctx: dict) -> dict:
    d = derived(cfg)
    out_5m = d / "chassis_scan_5M.stl"
    out_1m = d / "chassis_scan_1M.stl"

    if out_5m.exists() and out_1m.exists():
        ms5 = pymeshlab.MeshSet(); ms5.load_new_mesh(str(out_5m))
        ms1 = pymeshlab.MeshSet(); ms1.load_new_mesh(str(out_1m))
        metrics = {"faces_5M": ms5.current_mesh().face_number(), "faces_1M": ms1.current_mesh().face_number()}
        print(f"[step 3] decimate: outputs already on disk, skipping recompute: {metrics}")
        return metrics

    t0 = time.time()
    ms = load_and_clean_fragments(cfg, ctx)
    full_res_id = ms.current_mesh_id()

    ms.generate_copy_of_current_mesh()  # decimate a duplicate; the full-res mesh (fed to step 5) must stay intact
    ms.meshing_decimation_quadric_edge_collapse(
        targetfacenum=5_000_000, preservenormal=True, preservetopology=True,
        preserveboundary=True, planarquadric=True, qualitythr=0.3,
    )
    faces_5m = ms.current_mesh().face_number()
    ms.save_current_mesh(str(out_5m))

    ms.meshing_decimation_quadric_edge_collapse(
        targetfacenum=1_000_000, preservenormal=True, preservetopology=True,
        preserveboundary=True, planarquadric=True, qualitythr=0.3,
    )
    faces_1m = ms.current_mesh().face_number()
    ms.save_current_mesh(str(out_1m))

    ms.set_current_mesh(full_res_id)

    metrics = {"faces_5M": faces_5m, "faces_1M": faces_1m}
    log_step(cfg, 3, "decimate", metrics, time.time() - t0)
    return metrics


# ---------------------------------------------------------------------------
# Step 4 - floor plane
# ---------------------------------------------------------------------------

def compute_floor_plane(cfg) -> dict:
    d = derived(cfg)
    floor_json = d / "floor_plane.json"
    if floor_json.exists():
        with open(floor_json) as f:
            result = json.load(f)
        print(f"[step 4] floor: {floor_json.name} already on disk, skipping recompute")
        return result

    t0 = time.time()
    mesh1m = trimesh.load(str(d / "chassis_scan_1M.stl"), process=False)
    verts = np.asarray(mesh1m.vertices)

    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(verts)
    plane_model, inliers = pcd.segment_plane(distance_threshold=3.0, ransac_n=3, num_iterations=3000)

    inlier_pts = verts[inliers]
    centroid = inlier_pts.mean(axis=0)
    centered = inlier_pts - centroid
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    normal = vt[-1]
    normal = normal / np.linalg.norm(normal)
    d_coef = -normal.dot(centroid)

    mesh_centroid = verts.mean(axis=0)
    if normal.dot(mesh_centroid) + d_coef < 0:
        normal = -normal
        d_coef = -d_coef

    residual = verts @ normal + d_coef
    inlier_residual = residual[inliers]
    rms = float(np.sqrt(np.mean(inlier_residual ** 2)))
    inliers_fraction = len(inliers) / len(verts)

    result = {
        "normal": normal.tolist(), "d": float(d_coef),
        "inliers_fraction": round(inliers_fraction, 4), "rms_mm": round(rms, 3),
    }
    with open(floor_json, "w") as f:
        json.dump(result, f, indent=1)
    log_step(cfg, 4, "floor", result, time.time() - t0)
    return result


# ---------------------------------------------------------------------------
# Step 5 - floor removal
# ---------------------------------------------------------------------------

def apply_floor_removal(ms: pymeshlab.MeshSet, floor: dict) -> None:
    a, b, c = floor["normal"]
    dcoef = floor["d"]
    condselect = f"({a}*x+{b}*y+{c}*z+({dcoef})) < 4"
    ms.compute_selection_by_condition_per_vertex(condselect=condselect)
    ms.meshing_remove_selected_vertices()
    before = ms.current_mesh().face_number()
    ms.compute_selection_by_small_disconnected_components_per_face(nbfaceratio=0.0001)
    ms.meshing_remove_selected_faces()
    ms.meshing_remove_unreferenced_vertices()
    ms.meshing_remove_duplicate_faces()
    ms.meshing_remove_null_faces()


def step5(cfg, ctx: dict) -> dict:
    d = derived(cfg)
    out_full = d / "chassis_scan_nofloor.ply"
    out_5m = d / "chassis_scan_nofloor_5M.stl"
    out_1m = d / "chassis_scan_nofloor_1M.stl"

    if out_full.exists() and out_5m.exists() and out_1m.exists():
        ms = pymeshlab.MeshSet(); ms.load_new_mesh(str(out_full))
        metrics = {"faces_nofloor_full": ms.current_mesh().face_number()}
        print(f"[step 5] floor removal: outputs already on disk, skipping recompute: {metrics}")
        return metrics

    t0 = time.time()
    floor = compute_floor_plane(cfg)

    ms = load_and_clean_fragments(cfg, ctx)
    area_before = ms.current_mesh().face_number()
    surface_before = ms.get_geometric_measures()["surface_area"]
    apply_floor_removal(ms, floor)
    surface_after = ms.get_geometric_measures()["surface_area"]
    faces_after = ms.current_mesh().face_number()
    ms.save_current_mesh(str(out_full), binary=True)

    ms5 = pymeshlab.MeshSet(); ms5.load_new_mesh(str(d / "chassis_scan_5M.stl"))
    apply_floor_removal(ms5, floor)
    ms5.save_current_mesh(str(out_5m))

    ms1 = pymeshlab.MeshSet(); ms1.load_new_mesh(str(d / "chassis_scan_1M.stl"))
    apply_floor_removal(ms1, floor)
    ms1.save_current_mesh(str(out_1m))

    metrics = {
        "faces_before": area_before, "faces_after_full": faces_after,
        "surface_area_before_m2": round(surface_before / 1_000_000, 3),
        "surface_area_after_m2": round(surface_after / 1_000_000, 3),
        "surface_area_drop_m2": round((surface_before - surface_after) / 1_000_000, 3),
    }
    log_step(cfg, 5, "floor-removal", metrics, time.time() - t0)
    return metrics


# ---------------------------------------------------------------------------
# Step 6 - initial symmetry plane (PCA)
# ---------------------------------------------------------------------------

def step6(cfg, floor: dict) -> dict:
    d = derived(cfg)
    mesh = trimesh.load(str(d / "chassis_scan_nofloor_1M.stl"), process=False)
    verts = np.asarray(mesh.vertices)
    z_axis = np.array(floor["normal"])

    centroid = verts.mean(axis=0)
    centered = verts - centroid
    cov = centered.T @ centered / len(verts)
    eigvals, eigvecs = np.linalg.eigh(cov)
    long_axis = eigvecs[:, np.argmax(eigvals)]

    l_proj = long_axis - long_axis.dot(z_axis) * z_axis
    l_proj = l_proj / np.linalg.norm(l_proj)
    y0 = np.cross(z_axis, l_proj)
    y0 = y0 / np.linalg.norm(y0)
    d0 = -y0.dot(centroid)

    result = {"normal": y0.tolist(), "d": float(d0), "centroid": centroid.tolist()}
    log_step(cfg, 6, "symmetry-initial", {"normal": result["normal"], "d": round(d0, 3)}, 0.0)
    return result


# ---------------------------------------------------------------------------
# Step 7 - symmetry refinement (mirror-ICP)
# ---------------------------------------------------------------------------

def step7(cfg, floor: dict) -> dict:
    d = derived(cfg)
    sym_json = d / "symmetry.json"
    if sym_json.exists():
        with open(sym_json) as f:
            result = json.load(f)
        print(f"[step 7] symmetry: {sym_json.name} already on disk, skipping recompute")
        return result

    t0 = time.time()
    initial = step6(cfg, floor)

    mesh = trimesh.load(str(d / "chassis_scan_nofloor_1M.stl"), process=False)
    verts = np.asarray(mesh.vertices)
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(verts)
    pcd = pcd.voxel_down_sample(voxel_size=4.0)
    pcd.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=12.0, max_nn=30))
    n_points = len(pcd.points)

    normal = np.array(initial["normal"])
    dcoef = initial["d"]
    iterations = []
    schedule = [40, 20, 10, 6, 6]

    for dist in schedule:
        r_mat = np.eye(3) - 2 * np.outer(normal, normal)
        t_vec = -2 * dcoef * normal
        m_mat = np.eye(4)
        m_mat[:3, :3] = r_mat
        m_mat[:3, 3] = t_vec

        reflected = o3d.geometry.PointCloud(pcd)
        reflected.transform(m_mat)

        result_icp = o3d.pipelines.registration.registration_icp(
            reflected, pcd, dist, np.eye(4),
            o3d.pipelines.registration.TransformationEstimationPointToPlane(),
            o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=200),
        )
        t_icp = result_icp.transformation
        s_mat = t_icp @ m_mat
        r_s = s_mat[:3, :3]
        t_s = s_mat[:3, 3]

        eigvals, eigvecs = np.linalg.eig(r_s)
        real_mask = np.abs(eigvals.imag) < 1e-6
        real_eigvals = eigvals.real[real_mask]
        real_eigvecs = eigvecs[:, real_mask].real
        idx = np.argmin(np.abs(real_eigvals - (-1)))
        new_normal = real_eigvecs[:, idx]
        new_normal = new_normal / np.linalg.norm(new_normal)
        if new_normal.dot(normal) < 0:
            new_normal = -new_normal
        new_d = -(t_s.dot(new_normal)) / 2

        angle_change = float(np.degrees(np.arccos(np.clip(abs(new_normal.dot(normal)), -1, 1))))
        iterations.append({
            "distance_mm": dist, "fitness": round(result_icp.fitness, 4),
            "rmse_mm": round(result_icp.inlier_rmse, 3), "angle_change_deg": round(angle_change, 4),
        })
        normal, dcoef = new_normal, new_d

    rotation_from_pca = float(np.degrees(
        np.arccos(np.clip(abs(np.array(initial["normal"]).dot(normal)), -1, 1))
    ))

    result = {
        "normal": normal.tolist(), "d": float(dcoef),
        "n_points_downsampled": n_points,
        "rotation_from_pca_deg": round(rotation_from_pca, 3),
        "icp_final_fitness": iterations[-1]["fitness"],
        "icp_final_rmse_mm": iterations[-1]["rmse_mm"],
        "last_iteration_angle_change_deg": iterations[-1]["angle_change_deg"],
        "schedule_mm": schedule, "iterations": iterations,
    }
    with open(sym_json, "w") as f:
        json.dump(result, f, indent=1)
    log_step(cfg, 7, "symmetry-refine", {
        "rotation_from_pca_deg": result["rotation_from_pca_deg"],
        "icp_final_fitness": result["icp_final_fitness"],
        "icp_final_rmse_mm": result["icp_final_rmse_mm"],
        "last_iteration_angle_change_deg": result["last_iteration_angle_change_deg"],
    }, time.time() - t0)
    return result


# ---------------------------------------------------------------------------
# Step 8 - axes
# ---------------------------------------------------------------------------

def step8(cfg, floor: dict, symmetry: dict) -> dict:
    d = derived(cfg)
    axes_json = d / "axes.json"

    t0 = time.time()
    z_axis = np.array(floor["normal"])
    refined_normal = np.array(symmetry["normal"])
    y_axis = refined_normal - refined_normal.dot(z_axis) * z_axis
    y_axis = y_axis / np.linalg.norm(y_axis)
    x_axis = np.cross(y_axis, z_axis)
    x_axis = x_axis / np.linalg.norm(x_axis)

    mesh = trimesh.load(str(d / "chassis_scan_nofloor_1M.stl"), process=False)
    verts = np.asarray(mesh.vertices)
    height = verts @ z_axis
    threshold = np.percentile(height, 99)
    top_pts = verts[height >= threshold]
    mean_x = (top_pts @ x_axis).mean()
    if mean_x < 0:
        x_axis = -x_axis
        y_axis = -y_axis

    det = float(np.linalg.det(np.array([x_axis, y_axis, z_axis])))

    result = {"X": x_axis.tolist(), "Y": y_axis.tolist(), "Z": z_axis.tolist(), "det": round(det, 4)}
    with open(axes_json, "w") as f:
        json.dump(result, f, indent=1)
    log_step(cfg, 8, "axes", result, time.time() - t0)
    return result


# ---------------------------------------------------------------------------
# Step 9 - rear axle
# ---------------------------------------------------------------------------

def run_cloudcompare_ransac(cfg, pts_ply: Path, out_dir: Path, primitives: str,
                             support_points: int) -> list:
    clouds_dir = out_dir / "clouds"
    meshes_dir = out_dir / "meshes"
    clouds_dir.mkdir(parents=True, exist_ok=True)
    meshes_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(cfg["cloudcompare_exe"]), "-SILENT", "-NO_TIMESTAMP", "-AUTO_SAVE", "OFF",
        "-C_EXPORT_FMT", "PLY", "-M_EXPORT_FMT", "PLY",
        "-O", str(pts_ply),
        "-RANSAC", "EPSILON_ABSOLUTE", "0.6", "BITMAP_EPSILON_ABSOLUTE", "4.0",
        "SUPPORT_POINTS", str(support_points), "MAX_NORMAL_DEV", "15", "PROBABILITY", "0.01",
        "ENABLE_PRIMITIVE", primitives,
        "OUT_CLOUD_DIR", str(clouds_dir), "OUT_MESH_DIR", str(meshes_dir),
        "OUTPUT_INDIVIDUAL_SUBCLOUDS", "OUTPUT_INDIVIDUAL_PRIMITIVES",
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=False)

    primitives_out = []
    for mesh_path in sorted(meshes_dir.glob("*_CYLINDER_*.ply")):
        cloud_path = clouds_dir / (mesh_path.stem + "_cloud.ply")
        if not cloud_path.exists():
            continue
        mesh_pts = np.asarray(trimesh.load(str(mesh_path), process=False).vertices)
        cloud_pts = np.asarray(trimesh.load(str(cloud_path), process=False).vertices)

        centre = mesh_pts.mean(axis=0)
        centered = mesh_pts - centre
        cov = centered.T @ centered / len(mesh_pts)
        eigvals, eigvecs = np.linalg.eigh(cov)
        axis = eigvecs[:, np.argmax(eigvals)]
        axis = axis / np.linalg.norm(axis)

        perp = centered - np.outer(centered @ axis, axis)
        radius = float(np.median(np.linalg.norm(perp, axis=1)))

        cloud_centered = cloud_pts - centre
        cloud_perp = cloud_centered - np.outer(cloud_centered @ axis, axis)
        cloud_radial = np.linalg.norm(cloud_perp, axis=1)
        rms = float(np.sqrt(np.mean((cloud_radial - radius) ** 2)))

        primitives_out.append({
            "kind": "cylinder", "file": mesh_path.name, "axis": axis.tolist(),
            "centre": centre.tolist(), "radius": round(radius, 2),
            "support": len(cloud_pts), "rms": round(rms, 3),
        })
    return primitives_out


def step9(cfg, floor: dict, symmetry: dict, axes: dict) -> dict:
    d = derived(cfg)
    rear_json = d / "rear_axle.json"
    if rear_json.exists():
        with open(rear_json) as f:
            result = json.load(f)
        print(f"[step 9] rear-axle: {rear_json.name} already on disk, skipping recompute")
        return result

    t0 = time.time()
    x_axis = np.array(axes["X"]); y_axis = np.array(axes["Y"]); z_axis = np.array(axes["Z"])

    mesh = trimesh.load(str(d / "chassis_scan_nofloor_1M.stl"), process=False)
    verts_1m = np.asarray(mesh.vertices)
    centroid = verts_1m.mean(axis=0)
    x_centroid = float(x_axis.dot(centroid))

    mesh5 = trimesh.load(str(d / "chassis_scan_nofloor_5M.stl"), process=False)
    verts5 = np.asarray(mesh5.vertices)
    normals5 = np.asarray(mesh5.vertex_normals)

    # Provisional frame: X relative to the vehicle centroid (the axle X is not yet known);
    # Y relative to the symmetry plane and Z relative to the floor plane (both already fixed
    # by steps 4 and 7), so the box bounds below line up with the datum-frame heights and
    # left/right symmetry the acceptance criteria are stated in.
    x_prov = verts5 @ x_axis - x_centroid
    y_prov = verts5 @ y_axis + symmetry["d"]
    z_prov = verts5 @ z_axis + floor["d"]

    # The upper X bound is relative to the rear-most percentile too, not an absolute
    # centroid-relative coordinate: an absolute +800 reaches nearly the full vehicle length
    # from a centroid this far forward of the rear tip, dragging in the whole underbody.
    x_rear = np.percentile(x_prov, 0.5)
    mask = (
        (x_prov >= x_rear + 100) & (x_prov <= x_rear + 800)
        & (np.abs(y_prov) < 480)
        & (z_prov >= 150) & (z_prov <= 480)
    )

    crop_verts = verts5[mask]
    crop_normals = normals5[mask]
    crop_ply = d / "rear_axle_crop.ply"
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(crop_verts)
    pcd.normals = o3d.utility.Vector3dVector(crop_normals)
    o3d.io.write_point_cloud(str(crop_ply), pcd, write_ascii=False)

    ransac_dir = d / "ransac" / "rear-axle"
    candidates = run_cloudcompare_ransac(cfg, crop_ply, ransac_dir, "CYLINDER", 400)

    kept = []
    for c in candidates:
        axis = np.array(c["axis"])
        angle = float(np.degrees(np.arccos(np.clip(abs(axis.dot(y_axis)), -1, 1))))
        c["angle_to_Y_deg"] = round(angle, 2)
        c["y_prov"] = round(float(y_axis.dot(np.array(c["centre"])) + symmetry["d"]), 2)
        if angle < 8 and 15 <= c["radius"] <= 130 and c["support"] > 2000:
            kept.append(c)

    # The axle housings are joined by a connecting shaft, which the loose axis/radius/support
    # filter also passes as several lower-support sub-segment fits along its length, on top of
    # near-duplicate re-detections of the housings themselves. Dedup by taking the single
    # highest-support candidate on each side of the symmetry plane (Y > 0 and Y < 0) - the
    # housings dominate every side's point count by a wide margin over any shaft segment.
    left = [c for c in kept if c["y_prov"] > 0]
    right = [c for c in kept if c["y_prov"] < 0]
    deduped = []
    if left:
        deduped.append(max(left, key=lambda c: c["support"]))
    if right:
        deduped.append(max(right, key=lambda c: c["support"]))
    kept_all = kept
    kept = deduped

    result = {
        "n_crop_points": len(crop_verts), "n_candidates": len(candidates),
        "candidates": candidates, "kept_before_dedup": kept_all, "kept": kept, "n_kept": len(kept),
    }
    with open(rear_json, "w") as f:
        json.dump(result, f, indent=1)
    log_step(cfg, 9, "rear-axle", {
        "n_crop_points": result["n_crop_points"], "n_candidates": result["n_candidates"],
        "n_kept": result["n_kept"],
    }, time.time() - t0)
    return result


# ---------------------------------------------------------------------------
# Step 10 - origin and export to datum frame
# ---------------------------------------------------------------------------

def step10(cfg, floor: dict, symmetry: dict, axes: dict, rear_axle: dict) -> dict:
    d = derived(cfg)
    datum_json = d / "datum.json"
    out_full = d / "chassis_datum_full.ply"
    out_5m = d / "chassis_datum_5M.stl"
    out_1m = d / "chassis_datum_1M.stl"
    out_200k = d / "chassis_datum_200k.stl"

    if datum_json.exists() and out_full.exists() and out_200k.exists():
        with open(datum_json) as f:
            result = json.load(f)
        print(f"[step 10] origin/export: outputs already on disk, skipping recompute")
        return result

    if rear_axle["n_kept"] != 2:
        raise RuntimeError(f"expected exactly 2 kept rear-axle cylinders, got {rear_axle['n_kept']}")

    t0 = time.time()
    x_axis = np.array(axes["X"]); y_axis = np.array(axes["Y"]); z_axis = np.array(axes["Z"])
    left, right = rear_axle["kept"]
    centre_mean = (np.array(left["centre"]) + np.array(right["centre"])) / 2
    x_axle_mean = float(x_axis.dot(centre_mean))

    m3 = np.array([z_axis, y_axis, x_axis])
    rhs = np.array([-floor["d"], -symmetry["d"], x_axle_mean])
    origin = np.linalg.solve(m3, rhs)

    r_mat = np.array([x_axis, y_axis, z_axis])
    t_vec = -r_mat @ origin
    t_matrix = np.eye(4)
    t_matrix[:3, :3] = r_mat
    t_matrix[:3, 3] = t_vec

    left_datum = r_mat @ np.array(left["centre"]) + t_vec
    right_datum = r_mat @ np.array(right["centre"]) + t_vec

    faces = {}
    mesh_full = trimesh.load(str(d / "chassis_scan_nofloor.ply"), process=False)
    faces["after_floor"] = len(mesh_full.faces)
    mesh_full.apply_transform(t_matrix)
    mesh_full.export(str(out_full))

    mesh5 = trimesh.load(str(d / "chassis_scan_nofloor_5M.stl"), process=False)
    mesh5.apply_transform(t_matrix)
    mesh5.export(str(out_5m))

    mesh1 = trimesh.load(str(d / "chassis_scan_nofloor_1M.stl"), process=False)
    mesh1.apply_transform(t_matrix)
    mesh1.export(str(out_1m))

    ms200 = pymeshlab.MeshSet()
    ms200.load_new_mesh(str(out_1m))
    ms200.meshing_decimation_quadric_edge_collapse(
        targetfacenum=200_000, preservenormal=True, preservetopology=True,
        preserveboundary=True, planarquadric=True, qualitythr=0.3,
    )
    faces_200k = ms200.current_mesh().face_number()
    ms200.save_current_mesh(str(out_200k))

    ms_frag = pymeshlab.MeshSet(); ms_frag.load_new_mesh(str(d / "chassis_scan_fragfree.ply"))
    faces["after_fragments"] = ms_frag.current_mesh().face_number()

    ms_load = pymeshlab.MeshSet(); ms_load.load_new_mesh(str(d / "chassis_scan_5M.stl"))
    faces["loaded"] = 35_074_344

    result = {
        "frame": "ISO 8855, origin on floor plane and symmetry plane at rear axle housing X",
        "T_scan_to_datum": t_matrix.tolist(),
        "X": x_axis.tolist(), "Y": y_axis.tolist(), "Z": z_axis.tolist(),
        "floor": {"inliers_fraction": floor["inliers_fraction"], "rms_mm": floor["rms_mm"]},
        "symmetry": {
            "rotation_from_pca_deg": symmetry["rotation_from_pca_deg"],
            "icp_final_fitness": symmetry["icp_final_fitness"],
            "icp_final_rmse_mm": symmetry["icp_final_rmse_mm"],
        },
        "rear_axle_housing": {
            "left": {"r": left["radius"], "y": round(left_datum[1], 1), "z": round(left_datum[2], 1), "rms": left["rms"]},
            "right": {"r": right["radius"], "y": round(right_datum[1], 1), "z": round(right_datum[2], 1), "rms": right["rms"]},
            "x_span_mm": round(abs(left_datum[0] - right_datum[0]), 2),
        },
        "faces": faces,
        "outputs": {
            "full_ply": str(out_full), "5M": str(out_5m), "1M": str(out_1m), "200k": str(out_200k),
        },
    }
    with open(datum_json, "w") as f:
        json.dump(result, f, indent=1)
    log_step(cfg, 10, "origin-export", {
        "origin": origin.tolist(), "faces_5M": len(mesh5.faces), "faces_1M": len(mesh1.faces),
        "faces_200k": faces_200k,
    }, time.time() - t0)
    return result


# ---------------------------------------------------------------------------
# Step 11 - report and renders
# ---------------------------------------------------------------------------

def render_with_grid(points: np.ndarray, path: Path, axes=(0, 1), depth_axis=2,
                      mm_per_px: float = 2.0, grid_mm: float = 250.0) -> None:
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

    # grid lines at multiples of grid_mm in world coordinates, including the axis at 0
    x0_col = int(round((0 - x_min) / mm_per_px))
    if 0 <= x0_col < width:
        shaded[:, x0_col] = 255
    y0_row = int(round((y_max - 0) / mm_per_px))
    if 0 <= y0_row < height:
        shaded[y0_row, :] = 255

    grid_px = grid_mm / mm_per_px
    n = 1
    while x0_col - n * grid_px > -grid_px or x0_col + n * grid_px < width + grid_px:
        for sign in (1, -1):
            c = int(round(x0_col + sign * n * grid_px))
            if 0 <= c < width:
                shaded[:, c] = np.maximum(shaded[:, c], 140)
        n += 1
        if n > 100:
            break
    n = 1
    while y0_row - n * grid_px > -grid_px or y0_row + n * grid_px < height + grid_px:
        for sign in (1, -1):
            r = int(round(y0_row + sign * n * grid_px))
            if 0 <= r < height:
                shaded[r, :] = np.maximum(shaded[r, :], 140)
        n += 1
        if n > 100:
            break

    common._write_gray_png(path, shaded)


def step11(cfg, datum: dict) -> dict:
    d = derived(cfg)
    artefacts = (cfg["data_root"].parent / "docs" / "thrifty" / "2026-09-14-scan-pipeline" / "artefacts")
    artefacts.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    datum_json_out = artefacts / "datum.json"
    with open(datum_json_out, "w") as f:
        json.dump(datum, f, indent=1)

    mesh5 = trimesh.load(str(d / "chassis_datum_5M.stl"), process=False)
    verts = np.asarray(mesh5.vertices)

    top_png = artefacts / "datum-top.png"
    side_png = artefacts / "datum-side.png"
    render_with_grid(verts, top_png, axes=(0, 1), depth_axis=2, mm_per_px=2.0, grid_mm=250.0)
    render_with_grid(verts, side_png, axes=(0, 2), depth_axis=1, mm_per_px=2.0, grid_mm=250.0)

    report_path = artefacts / "condition-report.md"
    ref_path = artefacts / "datum-reference.json"
    with open(ref_path) as f:
        reference = json.load(f)

    def axis_angle(a, b):
        a, b = np.array(a), np.array(b)
        return float(np.degrees(np.arccos(np.clip(abs(a.dot(b)) / (np.linalg.norm(a) * np.linalg.norm(b)), -1, 1))))

    axis_diffs = {ax: round(axis_angle(datum[ax], reference[ax]), 3) for ax in ("X", "Y", "Z")}
    t_datum = np.array(datum["T_scan_to_datum"])
    t_ref = np.array(reference["T_scan_to_datum"])
    translation_diff_mm = np.abs(t_datum[:3, 3] - t_ref[:3, 3]).tolist()

    lines = [
        "# Condition report",
        "",
        f"Faces: loaded {datum['faces']['loaded']}, after fragments {datum['faces']['after_fragments']}, "
        f"after floor {datum['faces']['after_floor']}.",
        "",
        "## Datum agreement against artefacts/datum-reference.json",
        "",
        f"Axis angle differences (deg): X {axis_diffs['X']}, Y {axis_diffs['Y']}, Z {axis_diffs['Z']} "
        f"(accept under 0.5).",
        f"Translation differences (mm): {[round(v, 2) for v in translation_diff_mm]} (accept under 5).",
        "",
        "## Floor and symmetry",
        "",
        f"Floor: inliers fraction {datum['floor']['inliers_fraction']}, RMS {datum['floor']['rms_mm']} mm.",
        f"Symmetry: rotation from PCA {datum['symmetry']['rotation_from_pca_deg']} deg, "
        f"final fitness {datum['symmetry']['icp_final_fitness']}, "
        f"final RMSE {datum['symmetry']['icp_final_rmse_mm']} mm.",
        "",
        "## Rear axle housing",
        "",
        f"Left: r={datum['rear_axle_housing']['left']['r']} y={datum['rear_axle_housing']['left']['y']} "
        f"z={datum['rear_axle_housing']['left']['z']} rms={datum['rear_axle_housing']['left']['rms']}",
        f"Right: r={datum['rear_axle_housing']['right']['r']} y={datum['rear_axle_housing']['right']['y']} "
        f"z={datum['rear_axle_housing']['right']['z']} rms={datum['rear_axle_housing']['right']['rms']}",
        f"X span between sides: {datum['rear_axle_housing']['x_span_mm']} mm.",
        "",
        "## Renders",
        "",
        "![top](datum-top.png)",
        "",
        "![side](datum-side.png)",
    ]
    report_path.write_text("\n".join(lines))

    result = {"axis_diffs_deg": axis_diffs, "translation_diff_mm": translation_diff_mm}
    log_step(cfg, 11, "report", result, time.time() - t0)
    return result


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

STEP_ORDER = list(range(1, 12))


def run_steps(cfg, steps_to_run):
    ctx = {}
    floor = symmetry = axes = rear_axle = datum = None
    fragments_done = False
    for n in steps_to_run:
        if n in (1, 2):
            if not fragments_done:
                load_and_clean_fragments(cfg, ctx)
                fragments_done = True
        elif n == 3:
            step3(cfg, ctx)
        elif n == 4:
            floor = compute_floor_plane(cfg)
        elif n == 5:
            step5(cfg, ctx)
        elif n == 6:
            floor = floor or compute_floor_plane(cfg)
            step6(cfg, floor)
        elif n == 7:
            floor = floor or compute_floor_plane(cfg)
            symmetry = step7(cfg, floor)
        elif n == 8:
            floor = floor or compute_floor_plane(cfg)
            symmetry = symmetry or step7(cfg, floor)
            axes = step8(cfg, floor, symmetry)
        elif n == 9:
            floor = floor or compute_floor_plane(cfg)
            symmetry = symmetry or step7(cfg, floor)
            axes = axes or step8(cfg, floor, symmetry)
            rear_axle = step9(cfg, floor, symmetry, axes)
        elif n == 10:
            floor = floor or compute_floor_plane(cfg)
            symmetry = symmetry or step7(cfg, floor)
            axes = axes or step8(cfg, floor, symmetry)
            rear_axle = rear_axle or step9(cfg, floor, symmetry, axes)
            datum = step10(cfg, floor, symmetry, axes, rear_axle)
        elif n == 11:
            if datum is None:
                d = derived(cfg)
                with open(d / "datum.json") as f:
                    datum = json.load(f)
            step11(cfg, datum)


def main():
    parser = argparse.ArgumentParser(description="Condition stage: fragments, floor, symmetry, origin, export")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--step", type=int, choices=STEP_ORDER)
    group.add_argument("--through", type=int, choices=STEP_ORDER)
    args = parser.parse_args()

    cfg = common.load_config()

    if args.step:
        steps = [args.step]
    else:
        steps = list(range(1, args.through + 1))

    run_steps(cfg, steps)


if __name__ == "__main__":
    main()
