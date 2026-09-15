"""Vehicle assembly: two placed enclosures, motor placeholder, keep-out, per plan section 4.6."""

import argparse
import json
import math
import sys
from pathlib import Path

from build123d import Align, Compound, Cylinder, Location, Matrix, Plane, Pos, Rot, Vector

from common import artefacts_dir, export_step, load_params

sys.path.insert(0, str(Path(__file__).parent))
from cell import block as cell_block  # noqa: E402
from enclosure import box_shell, outer_dims  # noqa: E402


# ---------------------------------------------------------------------------
# The section 4.6 transform
# ---------------------------------------------------------------------------

def left_location(params: dict) -> Location:
    """p_vehicle = [x, y, z] + R . p_local, R the section 4.6 matrix with phi = lean_deg.

    R rotates a box-local point the same way build123d's Rot(X=-lean_deg) does: both send
    local +Z to (0, sin(phi), cos(phi)) and local +Y to (0, cos(phi), -sin(phi)).
    """
    pl = params["placement"]
    return Pos(pl["x"], pl["y"], pl["z"]) * Rot(X=-pl["lean_deg"])


def place_left(shape, params: dict):
    return left_location(params) * shape


def mirror_right(placed):
    return placed.mirror(Plane.XZ)


def loc_matrix(loc: Location) -> Matrix:
    return Matrix(loc.wrapped.Transformation())


def transform_point(loc: Location, v: tuple[float, float, float]) -> Vector:
    return Vector(*v).transform(loc_matrix(loc))


def transform_direction(loc: Location, v: tuple[float, float, float]) -> Vector:
    return Vector(*v).transform(loc_matrix(loc), is_direction=True)


def local_face_normals(shell) -> tuple[Vector, Vector]:
    """Find the shell's own +Z (lid) and +Y (stack-axis) face normals from its faces."""
    lid_normal = None
    stack_normal = None
    for f in shell.faces():
        n = f.normal_at()
        if abs(n.X) < 1e-6 and abs(n.Y) < 1e-6 and n.Z > 0.999:
            lid_normal = n
        elif abs(n.X) < 1e-6 and n.Y > 0.999 and abs(n.Z) < 1e-6:
            stack_normal = n
    if lid_normal is None or stack_normal is None:
        raise RuntimeError("could not find local +Z (lid) and +Y (stack) faces on box_shell")
    return lid_normal, stack_normal


def placed_axes(params: dict, mirrored: bool = False):
    """Lid normal and stack axis of the placed (and optionally mirrored) box, read off its
    own faces per section 4.6."""
    shell = box_shell(params)
    lid_n_local, stack_n_local = local_face_normals(shell)

    loc = left_location(params)
    placed = loc * shell
    lid_n = transform_direction(loc, (lid_n_local.X, lid_n_local.Y, lid_n_local.Z))
    stack_n = transform_direction(loc, (stack_n_local.X, stack_n_local.Y, stack_n_local.Z))
    if mirrored:
        placed = mirror_right(placed)
        lid_n = Vector(lid_n.X, -lid_n.Y, lid_n.Z)
        stack_n = Vector(stack_n.X, -stack_n.Y, stack_n.Z)

    return placed, lid_n, stack_n


# ---------------------------------------------------------------------------
# Motor placeholder and keep-out
# ---------------------------------------------------------------------------

def motor_cylinder(params: dict):
    m = params["motor"]
    cx, cy, cz = m["centre"]
    cyl = Cylinder(m["housing_d"] / 2, m["length"], align=(Align.CENTER, Align.CENTER, Align.CENTER))
    if m["axis"] == "Y":
        cyl = Rot(X=90) * cyl
    elif m["axis"] == "X":
        cyl = Rot(Y=90) * cyl
    return Pos(cx, cy, cz) * cyl


def keepout_cylinder(params: dict):
    k = params["keepout"]
    x_lo, x_hi = k["x_range"]
    length = x_hi - x_lo
    x_mid = (x_lo + x_hi) / 2
    cyl = Cylinder(k["radius"], length, align=(Align.CENTER, Align.CENTER, Align.CENTER))
    cyl = Rot(Y=90) * cyl
    return Pos(x_mid, k["axis_y"], k["axis_z"]) * cyl


# ---------------------------------------------------------------------------
# Corners and the inboard gap
# ---------------------------------------------------------------------------

def local_corners(params: dict) -> list[Vector]:
    outer_x, outer_y, outer_h = outer_dims(params)
    sheet = params["enclosure"]["sheet"]
    x_lo, x_hi = -outer_x / 2, outer_x / 2
    y_lo, y_hi = -outer_y / 2, outer_y / 2
    z_lo, z_hi = -sheet, outer_h - sheet
    return [
        Vector(x, y, z)
        for x in (x_lo, x_hi)
        for y in (y_lo, y_hi)
        for z in (z_lo, z_hi)
    ]


def placed_corners(params: dict, mirrored: bool = False) -> list[Vector]:
    loc = left_location(params)
    corners = [transform_point(loc, (c.X, c.Y, c.Z)) for c in local_corners(params)]
    if mirrored:
        corners = [Vector(c.X, -c.Y, c.Z) for c in corners]
    return corners


def inboard_gap_at_floor(params: dict) -> float:
    """Y distance between the two boxes' inboard-bottom outer edges."""
    outer_x, outer_y, outer_h = outer_dims(params)
    sheet = params["enclosure"]["sheet"]
    loc = left_location(params)
    p_left = transform_point(loc, (0, -outer_y / 2, -sheet))
    p_right = Vector(p_left.X, -p_left.Y, p_left.Z)
    return abs(p_left.Y - p_right.Y)


# ---------------------------------------------------------------------------
# Assembly and export
# ---------------------------------------------------------------------------

def build_shells(params: dict):
    shell = box_shell(params)
    left = place_left(shell, params)
    right = mirror_right(place_left(box_shell(params), params))
    return left, right


def build_cells(params: dict):
    left_cells, _, _, _, _ = cell_block(params)
    right_cells, _, _, _, _ = cell_block(params)
    loc = left_location(params)
    left_placed = loc * left_cells
    right_placed = mirror_right(loc * right_cells)
    return left_placed, right_placed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", type=Path, default=None)
    args = ap.parse_args()

    params = load_params(args.params)

    _, lid_n_left, stack_n_left = placed_axes(params, mirrored=False)
    print(f"left lid normal: ({lid_n_left.X:.6f}, {lid_n_left.Y:.6f}, {lid_n_left.Z:.6f})")
    print(f"left stack axis: ({stack_n_left.X:.6f}, {stack_n_left.Y:.6f}, {stack_n_left.Z:.6f})")

    _, lid_n_right, stack_n_right = placed_axes(params, mirrored=True)
    print(f"right lid normal: ({lid_n_right.X:.6f}, {lid_n_right.Y:.6f}, {lid_n_right.Z:.6f})")
    print(f"right stack axis: ({stack_n_right.X:.6f}, {stack_n_right.Y:.6f}, {stack_n_right.Z:.6f})")

    motor = motor_cylinder(params)
    keepout = keepout_cylinder(params)
    print(f"motor volume: {motor.volume} mm3, bbox {motor.bounding_box().size}")
    print(f"keepout volume: {keepout.volume} mm3, bbox {keepout.bounding_box().size}")

    left_corners = placed_corners(params, mirrored=False)
    right_corners = placed_corners(params, mirrored=True)
    gap = inboard_gap_at_floor(params)
    print(f"left corners: {[tuple(round(v, 2) for v in (c.X, c.Y, c.Z)) for c in left_corners]}")
    print(f"right corners: {[tuple(round(v, 2) for v in (c.X, c.Y, c.Z)) for c in right_corners]}")
    print(f"inboard_gap_at_floor: {gap} mm")

    artefacts = artefacts_dir()

    left_shell, right_shell = build_shells(params)
    assembly = Compound(children=[left_shell, right_shell, motor, keepout])
    assembly_step = artefacts / "assembly.step"
    export_step(assembly, assembly_step)
    assembly_n_solids, assembly_volume = len(assembly.solids()), assembly.volume

    left_cells, right_cells = build_cells(params)
    full = Compound(
        children=[left_shell, right_shell, motor, keepout] + list(left_cells.solids())
        + list(right_cells.solids())
    )
    full_step = params_repo_root(params) / "data" / "cad" / "assembly-full.step"
    export_step(full, full_step)
    full_n_solids, full_volume = len(full.solids()), full.volume

    placement = {
        "params": {
            "x": params["placement"]["x"],
            "y": params["placement"]["y"],
            "z": params["placement"]["z"],
            "lean_deg": params["placement"]["lean_deg"],
        },
        "left": {
            "corners": [[round(c.X, 3), round(c.Y, 3), round(c.Z, 3)] for c in left_corners],
            "lid_normal": [round(lid_n_left.X, 6), round(lid_n_left.Y, 6), round(lid_n_left.Z, 6)],
            "stack_axis": [round(stack_n_left.X, 6), round(stack_n_left.Y, 6), round(stack_n_left.Z, 6)],
        },
        "right": {
            "corners": [[round(c.X, 3), round(c.Y, 3), round(c.Z, 3)] for c in right_corners],
            "lid_normal": [round(lid_n_right.X, 6), round(lid_n_right.Y, 6), round(lid_n_right.Z, 6)],
            "stack_axis": [round(stack_n_right.X, 6), round(stack_n_right.Y, 6), round(stack_n_right.Z, 6)],
        },
        "motor": {
            "centre": params["motor"]["centre"],
            "axis": params["motor"]["axis"],
            "d": params["motor"]["housing_d"],
            "length": params["motor"]["length"],
        },
        "keepout": {
            "axis_y": params["keepout"]["axis_y"],
            "axis_z": params["keepout"]["axis_z"],
            "radius": params["keepout"]["radius"],
            "x_range": params["keepout"]["x_range"],
        },
        "inboard_gap_at_floor": round(gap, 3),
    }
    (artefacts / "placement.json").write_text(json.dumps(placement, indent=2), encoding="utf-8")

    print(f"assembly.step: {assembly_n_solids} solids, {assembly_volume} mm3")
    print(f"assembly-full.step: {full_n_solids} solids, {full_volume} mm3")
    print("placement.json written")


def params_repo_root(params: dict) -> Path:
    from common import repo_root

    return repo_root()


if __name__ == "__main__":
    main()
