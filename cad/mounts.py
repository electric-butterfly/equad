"""Mount pickups: frame primitives within reach of the placed battery boxes.

Runs under .venv-mesh. Plan section 4.8: for the owner's [placement], list every fitted frame
cylinder and RANSAC plane within 120 mm of either box, with its distance and nearest face.
"""

import json
from pathlib import Path

import numpy as np
import open3d as o3d

from clearance import get_shell_mesh, place_vertices, scene_from_mesh, trimesh_to_o3d
from common import artefacts_dir, load_params, repo_root

REACH_MM = 120.0
PLANE_SUPPORT_MIN = 1500

# Section 5.1: the four named engine-mount planes, by their point (support, rms) so the report
# can call them out without re-matching on floating-point coordinates.
NAMED_ENGINE_MOUNT_SUPPORTS = {14975, 6759, 5446, 5085}


# ---------------------------------------------------------------------------
# 1. Candidate primitives
# ---------------------------------------------------------------------------

def load_primitives(params: dict) -> tuple[list[dict], list[dict]]:
    repo = repo_root()
    interfaces_path = repo / params["chassis"]["interfaces"]
    planes_path = repo / params["chassis"]["primitives_engine_bay"]
    if not interfaces_path.exists():
        raise FileNotFoundError(f"interfaces.json not found: {interfaces_path}")
    if not planes_path.exists():
        raise FileNotFoundError(f"primitives-engine-bay.json not found: {planes_path}")

    interfaces = json.loads(interfaces_path.read_text(encoding="utf-8"))
    cylinders = []
    for region in interfaces:
        for prim in region["primitives"]:
            if prim.get("kind") == "cylinder" and prim.get("accepted"):
                cylinders.append(prim)

    engine_bay = json.loads(planes_path.read_text(encoding="utf-8"))
    planes = []
    for prim in engine_bay["primitives"]:
        if prim.get("kind") == "plane" and prim.get("support", 0) > PLANE_SUPPORT_MIN:
            p = dict(prim)
            p["id"] = f"{engine_bay['region']}/plane/{prim['index']:03d}"
            p["point"] = prim["centre"]
            planes.append(p)

    return cylinders, planes


# ---------------------------------------------------------------------------
# 2. Placed box shells: o3d scenes for distance, plus the box-local frame for face labelling
# ---------------------------------------------------------------------------

FACE_NAMES = {
    "+x": "rear", "-x": "front",
    "+y": "outboard", "-y": "inboard",
    "+z": "lid", "-z": "floor",
}


def left_rotation(lean_deg: float) -> np.ndarray:
    phi = np.radians(lean_deg)
    return np.array([
        [1.0, 0.0, 0.0],
        [0.0, np.cos(phi), np.sin(phi)],
        [0.0, -np.sin(phi), np.cos(phi)],
    ])


class PlacedBox:
    """One placed box: an o3d RaycastingScene for distance, and the inverse rigid transform back
    to the box-local frame (section 4.5) for face labelling."""

    def __init__(self, params: dict, side: str):
        x, y, z, lean = (params["placement"][k] for k in ("x", "y", "z", "lean_deg"))
        mesh = get_shell_mesh(params)
        local_verts = np.asarray(mesh.vertices)
        local_bounds = (local_verts.min(axis=0), local_verts.max(axis=0))

        placed_verts = place_vertices(local_verts, x, y, z, lean, side)
        faces = np.asarray(mesh.faces)
        m = o3d.t.geometry.TriangleMesh()
        m.vertex.positions = o3d.core.Tensor(placed_verts.astype(np.float32))
        m.triangle.indices = o3d.core.Tensor(faces.astype(np.int32))
        self.scene = scene_from_mesh(m)

        self.R = left_rotation(lean)
        self.origin = np.array([x, y, z])
        self.side = side
        self.local_min, self.local_max = local_bounds

    def to_local(self, p_vehicle: np.ndarray) -> np.ndarray:
        p = np.asarray(p_vehicle, dtype=float)
        if self.side == "right":
            p = p * np.array([1.0, -1.0, 1.0])
        return self.R.T @ (p - self.origin)

    def distance(self, p_vehicle: np.ndarray) -> float:
        q = o3d.core.Tensor(np.asarray([p_vehicle], dtype=np.float32))
        return float(self.scene.compute_distance(q).numpy()[0])

    def nearest_face(self, p_vehicle: np.ndarray) -> str:
        lx, ly, lz = self.to_local(p_vehicle)
        lo, hi = self.local_min, self.local_max
        # Outward offset past each face; the largest is the dominant separating (or, if the
        # point is inside every bound, least-penetrating) face.
        offsets = {
            "-x": lo[0] - lx, "+x": lx - hi[0],
            "-y": lo[1] - ly, "+y": ly - hi[1],
            "-z": lo[2] - lz, "+z": lz - hi[2],
        }
        best = max(offsets, key=offsets.get)
        return FACE_NAMES[best]


def placed_shells(params: dict) -> dict[str, PlacedBox]:
    return {"left": PlacedBox(params, "left"), "right": PlacedBox(params, "right")}


# ---------------------------------------------------------------------------
# 3-4. Distance and nearest_face for every primitive, kept under REACH_MM
# ---------------------------------------------------------------------------

def pickups(cylinders: list[dict], planes: list[dict], boxes: dict[str, PlacedBox]) -> list[dict]:
    rows = []
    for kind, prims in (("cylinder", cylinders), ("plane", planes)):
        for prim in prims:
            point = np.array(prim["point"], dtype=float)
            best_box, best_dist, best_face = None, float("inf"), None
            for side, box in boxes.items():
                d = box.distance(point)
                if d < best_dist:
                    best_dist = d
                    best_box = side
                    best_face = box.nearest_face(point)
            if best_dist > REACH_MM:
                continue
            row = {
                "id": prim["id"],
                "kind": kind,
                "axis_or_normal": prim["axis"],
                "point": prim["point"],
                "radius": prim.get("radius"),
                "length": prim.get("length"),
                "support": prim["support"],
                "rms": prim["rms"],
                "box": best_box,
                "distance": round(best_dist, 3),
                "nearest_face": best_face,
            }
            if kind == "plane":
                row["note"] = "calliper before drilling"
            rows.append(row)
    rows.sort(key=lambda r: r["distance"])
    return rows


# ---------------------------------------------------------------------------
# 5-6. Write artefacts
# ---------------------------------------------------------------------------

CONCEPT_PARAGRAPH = (
    "The mounting concept: two locating pins on each box floor engaging bushes on brackets from "
    "the lower rails, and two tensioners at the top, inboard, pulling the box down onto the pins "
    "and reached from above so their mechanism is out of the mud. Bracket design is Sam's. The "
    "planes in the table were fitted by RANSAC at 0.15-0.35 mm RMS but did not pass the "
    "pipeline's refinement threshold (section 5.1); each row that is a plane carries the note "
    "\"calliper before drilling\"."
)


def write_pickups_json(rows: list[dict]) -> Path:
    out = artefacts_dir() / "mount-pickups.json"
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return out


def write_report(rows: list[dict], planes: list[dict]) -> Path:
    lines = []
    lines.append(f"{len(rows)} frame primitives within {REACH_MM:.0f} mm of a placed battery box.")
    lines.append("")
    lines.append("| id | kind | box | face | distance mm | support | rms |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in rows:
        lines.append(
            f"| {r['id']} | {r['kind']} | {r['box']} | {r['nearest_face']} | {r['distance']:.1f} | "
            f"{r['support']} | {r['rms']:.2f} |" + ("" if r["kind"] != "plane" else " *calliper before drilling*")
        )
    lines.append("")
    lines.append(CONCEPT_PARAGRAPH)
    lines.append("")

    named = [p for p in planes if p["support"] in NAMED_ENGINE_MOUNT_SUPPORTS]
    lines.append("Section 5.1's four named engine-mount planes:")
    for p in named:
        row = next((r for r in rows if r["id"] == p["id"]), None)
        if row:
            lines.append(
                f"- `{p['id']}` (support {p['support']}, rms {p['rms']:.2f}): "
                f"{row['distance']:.1f} mm from the {row['box']} box, nearest face {row['nearest_face']}."
            )
        else:
            lines.append(
                f"- `{p['id']}` (support {p['support']}, rms {p['rms']:.2f}): "
                f"more than {REACH_MM:.0f} mm from both boxes."
            )

    out = artefacts_dir() / "mounts-report.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


# ---------------------------------------------------------------------------

def main() -> None:
    params = load_params()

    cylinders, planes = load_primitives(params)
    print(f"candidate primitives: {len(cylinders)} accepted cylinders, {len(planes)} planes (support > {PLANE_SUPPORT_MIN})")

    boxes = placed_shells(params)

    rows = pickups(cylinders, planes, boxes)
    print(f"kept (within {REACH_MM:.0f} mm): {len(rows)}")

    pj = write_pickups_json(rows)
    print(f"wrote {pj} ({pj.stat().st_size} bytes)")

    rp = write_report(rows, planes)
    print(f"wrote {rp} ({rp.stat().st_size} bytes)")

    print("\nfirst twenty rows:")
    print(f"{'id':<24}{'kind':<10}{'box':<7}{'face':<10}{'dist mm':>9}")
    for r in rows[:20]:
        print(f"{r['id']:<24}{r['kind']:<10}{r['box']:<7}{r['nearest_face']:<10}{r['distance']:>9.1f}")


if __name__ == "__main__":
    main()
