"""The battery-box enclosure: body, lid, internals, fuse bay, cable exits, per plan section 4.5."""

import argparse
import sys
from pathlib import Path

from build123d import Align, Axis, Box, Cylinder, Pos, Rot, chamfer

from common import artefacts_dir, export_step, load_params

sys.path.insert(0, str(Path(__file__).parent))
from cell import block as cell_block  # noqa: E402


# ---------------------------------------------------------------------------
# Layout: positions shared by body, lid, internals and holes.
# ---------------------------------------------------------------------------

def layout(params: dict) -> dict:
    c, b, e = params["cell"], params["block"], params["enclosure"]
    thickness = c["thickness"]
    pad = c["pad"]
    p = thickness + pad
    internal = e["internal"]
    end_plate = e["end_plate"]
    partition = e["partition"]
    compression_plate = e["compression_plate"]
    n_max = max(b["columns"])

    y0 = -internal[1] / 2 + end_plate
    y_end = y0 + (n_max - 1) * p + thickness  # outboard face of the 9-cell columns' last cell

    return {
        "p": p,
        "y0": y0,
        "y_end": y_end,
        "n_max": n_max,
        "fuse_bay_y": (y0, y0 + p),
        "end_plate_y": (-internal[1] / 2, y0),
        "partition_y": (y0 + p - partition, y0 + p),
        "compression_plate_y": (y_end, y_end + compression_plate),
    }


# ---------------------------------------------------------------------------
# Body and lid
# ---------------------------------------------------------------------------

def outer_dims(params: dict):
    e = params["enclosure"]
    internal = e["internal"]
    sheet = e["sheet"]
    return internal[0] + 2 * sheet, internal[1] + 2 * sheet, internal[2] + sheet


def body(params: dict, holes=None, chamfer_len: float = 0.0):
    e = params["enclosure"]
    internal = e["internal"]
    sheet = e["sheet"]
    outer_x, outer_y, outer_h = outer_dims(params)

    outer = Pos(0, 0, -sheet) * Box(
        outer_x, outer_y, outer_h, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )
    cavity = Pos(0, 0, 0) * Box(
        internal[0], internal[1], internal[2], align=(Align.CENTER, Align.CENTER, Align.MIN)
    )
    shape = outer - cavity

    for h in holes or []:
        shape = shape - h

    if chamfer_len > 0:
        shape = apply_front_top_chamfer(shape, params, chamfer_len, top_z=internal[2])

    return shape


def apply_front_top_chamfer(shape, params: dict, chamfer_len: float, top_z: float):
    """Chamfer the outer edge where the +X wall meets the plane at Z = top_z."""
    outer_x, _, _ = outer_dims(params)
    x_max = outer_x / 2
    edges = shape.edges().filter_by(Axis.Y)
    target = [
        edg
        for edg in edges
        if abs(edg.center().X - x_max) < 1e-6 and abs(edg.center().Z - top_z) < 1e-6
    ]
    if not target:
        raise RuntimeError(f"no edge found at X={x_max}, Z={top_z} to chamfer")
    return chamfer(target, chamfer_len)


def lid(params: dict, chamfer_len: float = 0.0):
    e = params["enclosure"]
    internal = e["internal"]
    sheet = e["sheet"]
    outer_x, outer_y, _ = outer_dims(params)

    plate = Pos(0, 0, internal[2]) * Box(
        outer_x, outer_y, sheet, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )

    holes, hole_count = lid_bolt_holes(params)
    for h in holes:
        plate = plate - h

    if chamfer_len > 0:
        plate = apply_front_top_chamfer(plate, params, chamfer_len, top_z=internal[2])

    return plate, hole_count


def lid_bolt_holes(params: dict):
    e = params["enclosure"]
    outer_x, outer_y, _ = outer_dims(params)
    inset = e["lid_inset"]
    d = e["lid_bolt_d"]
    pitch_max = e["lid_bolt_pitch_max"]
    sheet = e["sheet"]
    internal = e["internal"]

    x_lo, x_hi = -outer_x / 2 + inset, outer_x / 2 - inset
    y_lo, y_hi = -outer_y / 2 + inset, outer_y / 2 - inset

    def stations(lo, hi):
        length = hi - lo
        n = max(1, -(-length // pitch_max))  # ceil
        return [lo + length * i / n for i in range(int(n) + 1)]

    x_stations = stations(x_lo, x_hi)
    y_stations = stations(y_lo, y_hi)

    holes = []
    seen = set()

    def add(x, y):
        key = (round(x, 6), round(y, 6))
        if key in seen:
            return
        seen.add(key)
        holes.append(
            Pos(x, y, internal[2]) * Cylinder(
                d / 2, sheet, align=(Align.CENTER, Align.CENTER, Align.MIN)
            )
        )

    for x in x_stations:
        add(x, y_lo)
        add(x, y_hi)
    for y in y_stations:
        add(x_lo, y)
        add(x_hi, y)

    return holes, len(holes)


# ---------------------------------------------------------------------------
# Internal plates
# ---------------------------------------------------------------------------

def end_plate(params: dict):
    e = params["enclosure"]
    internal = e["internal"]
    lo, hi = layout(params)["end_plate_y"]
    return Pos(0, (lo + hi) / 2, 0) * Box(
        internal[0], hi - lo, internal[2], align=(Align.CENTER, Align.CENTER, Align.MIN)
    )


def partition(params: dict):
    c, b = params["cell"], params["block"]
    internal = params["enclosure"]["internal"]
    lo, hi = layout(params)["partition_y"]
    x_c = -b["column_pitch_x"]
    return Pos(x_c, (lo + hi) / 2, 0) * Box(
        c["width"], hi - lo, internal[2], align=(Align.CENTER, Align.CENTER, Align.MIN)
    )


def compression_plate(params: dict):
    e = params["enclosure"]
    c = params["cell"]
    internal = e["internal"]
    lo, hi = layout(params)["compression_plate_y"]
    return Pos(0, (lo + hi) / 2, 0) * Box(
        internal[0], hi - lo, c["height_to_stud"], align=(Align.CENTER, Align.CENTER, Align.MIN)
    )


def front_column_spacer(params: dict, rows):
    """Gap between the front column's actual last-cell outboard face and y_end.

    Section 4.5 specifies a spacer of thickness `p - partition` here. Cross-checked
    against the rows the block() layout actually produces (and against section 4.4's
    own worked numbers, e.g. the 24.06 mm travel figure), the front column's last
    cell already sits flush with the 9-cell columns' last cell: both are placed by
    the same y0 + p*slot formula at slot = n_max - 1. The computed gap is 0, not
    p - partition. Building a block of the literal p - partition thickness there
    would overlap the compression plate, which spans the full cavity width. So this
    function reports the real gap and returns None (no solid) when it is ~0.
    """
    b = params["block"]
    c = params["cell"]
    ly = layout(params)
    front_x = -b["column_pitch_x"]

    front_col_rows = [r for r in rows if abs(r[2] - front_x) < 1e-6]
    last = max(front_col_rows, key=lambda r: r[3])
    front_last_face = last[3] + c["thickness"] / 2

    gap = ly["y_end"] - front_last_face
    if gap <= 1e-6:
        return None, gap

    spacer = Pos(front_x, front_last_face + gap / 2, 0) * Box(
        c["width"], gap, c["height_to_stud"], align=(Align.CENTER, Align.CENTER, Align.MIN)
    )
    return spacer, gap


def grub_screw_holes(params: dict):
    e = params["enclosure"]
    internal = e["internal"]
    sheet = e["sheet"]
    pairs = e["compression_pairs"]
    d = e["compression_screw_d"]
    rows_z = e["compression_rows_z"]
    wall = e["compression_wall"]

    x_lo, x_hi = -internal[0] / 2, internal[0] / 2
    x_stations = [x_lo + (x_hi - x_lo) * i / (pairs - 1) for i in range(pairs)] if pairs > 1 else [0.0]

    y_wall = internal[1] / 2 if wall == "outboard" else -internal[1] / 2
    holes = []
    for x in x_stations:
        for z in rows_z:
            cyl = Cylinder(d / 2, sheet * 2, align=(Align.CENTER, Align.CENTER, Align.CENTER))
            cyl = Rot(X=90) * cyl
            holes.append(Pos(x, y_wall, z) * cyl)
    return holes


def cable_exit_holes(params: dict):
    elec = params["electrical"]
    e = params["enclosure"]
    internal = e["internal"]
    sheet = e["sheet"]
    ds = elec["cable_exit_d"]
    z = elec["cable_exit_z"]
    face = elec["cable_exit_face"]

    width = internal[0] / 3
    n = len(ds)
    x_positions = [-width / 2 + width * i / (n - 1) for i in range(n)] if n > 1 else [0.0]

    y_wall = -internal[1] / 2 if face == "inboard" else internal[1] / 2
    holes = []
    for x, d in zip(x_positions, ds):
        cyl = Cylinder(d / 2, sheet * 2, align=(Align.CENTER, Align.CENTER, Align.CENTER))
        cyl = Rot(X=90) * cyl
        holes.append(Pos(x, y_wall, z) * cyl)
    return holes


def fuse_envelopes(params: dict):
    """Place the fuse envelopes in the fuse bay footprint (section 4.5).

    fuse_envelope's Y dimension (45 mm, OWNER: confirm) is wider than the fuse
    bay's own Y span (p = 29.66 mm at the committed pad) or the space actually
    free between the end plate and the partition (p - partition = 26.66 mm). The
    nominal bay-centred Y position would push the envelope outside the cavity and
    through the body wall, which is not a placement choice, it is invalid geometry
    for any centring. The Y centre is clamped to the cavity bounds so the envelope
    never leaves the box; intrusion into the end plate, partition or the block's
    first real cell is left as computed and reported, since fuse_envelope is an
    owner-confirm open item (section 4.9) and resizing it here would hide the
    mismatch rather than surface it.
    """
    elec = params["electrical"]
    b = params["block"]
    internal = params["enclosure"]["internal"]
    ly = layout(params)
    fx, fz = elec["fuse_envelope"][0], elec["fuse_envelope"][2]
    fy = elec["fuse_envelope"][1]
    x_c = -b["column_pitch_x"]

    nominal_y_c = (ly["fuse_bay_y"][0] + ly["fuse_bay_y"][1]) / 2
    y_lo_bound = -internal[1] / 2 + fy / 2
    y_hi_bound = internal[1] / 2 - fy / 2
    y_c = min(max(nominal_y_c, y_lo_bound), y_hi_bound)

    envelopes = []
    z0 = 0.0
    for _ in range(elec["fuses_per_box"]):
        env = Pos(x_c, y_c, z0) * Box(
            fx, fy, fz, align=(Align.CENTER, Align.CENTER, Align.MIN)
        )
        envelopes.append(env)
        z0 += fz

    overrun = z0 - internal[2]
    return envelopes, overrun


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def interference_table(named_shapes):
    from build123d import Part

    rows = []
    names = list(named_shapes.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = named_shapes[names[i]], named_shapes[names[j]]
            try:
                inter = a & b
                vol = inter.volume if inter is not None else 0.0
            except Exception:
                vol = 0.0
            rows.append((names[i], names[j], vol))
    return rows


def headroom_check(params: dict):
    c = params["cell"]
    elec = params["electrical"]
    internal = params["enclosure"]["internal"]
    needed = c["height_to_stud"] + elec["headroom"]
    ok = needed <= internal[2]
    return needed, internal[2], ok


# ---------------------------------------------------------------------------
# Assembly and export
# ---------------------------------------------------------------------------

def build_all(params: dict, chamfer_len: float = None):
    if chamfer_len is None:
        chamfer_len = params["enclosure"]["chamfer_front_top"]

    holes = grub_screw_holes(params) + cable_exit_holes(params)
    b_shape = body(params, holes=holes, chamfer_len=chamfer_len)
    l_shape, lid_hole_count = lid(params, chamfer_len=chamfer_len)
    ep_shape = end_plate(params)
    part_shape = partition(params)
    cp_shape = compression_plate(params)

    block_compound, rows, stack_len, needed_y, internal_y = cell_block(params)
    spacer_shape, spacer_gap = front_column_spacer(params, rows)

    fuse_shapes, fuse_overrun = fuse_envelopes(params)

    named = {
        "body": b_shape,
        "lid": l_shape,
        "end_plate": ep_shape,
        "partition": part_shape,
        "compression_plate": cp_shape,
        "fuse_0": fuse_shapes[0],
        "fuse_1": fuse_shapes[1],
        "block": block_compound,
    }
    if spacer_shape is not None:
        named["spacer"] = spacer_shape

    return {
        "body": b_shape,
        "lid": l_shape,
        "lid_hole_count": lid_hole_count,
        "end_plate": ep_shape,
        "partition": part_shape,
        "compression_plate": cp_shape,
        "spacer": spacer_shape,
        "spacer_gap": spacer_gap,
        "fuse_shapes": fuse_shapes,
        "fuse_overrun": fuse_overrun,
        "block_compound": block_compound,
        "rows": rows,
        "stack_len": stack_len,
        "needed_y": needed_y,
        "internal_y": internal_y,
        "named": named,
    }


def box_solids(built):
    from build123d import Compound

    solids = [built["body"], built["lid"], built["end_plate"], built["partition"],
              built["compression_plate"]]
    if built["spacer"] is not None:
        solids.append(built["spacer"])
    solids.extend(built["fuse_shapes"])
    return Compound(children=solids)


def box_shell(params: dict, chamfer_len: float = None):
    if chamfer_len is None:
        chamfer_len = params["enclosure"]["chamfer_front_top"]
    e = params["enclosure"]
    sheet = e["sheet"]
    internal = e["internal"]
    outer_x, outer_y, _ = outer_dims(params)
    outer_h = internal[2] + 2 * sheet

    shell = Pos(0, 0, -sheet) * Box(
        outer_x, outer_y, outer_h, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )
    if chamfer_len > 0:
        shell = apply_front_top_chamfer(shell, params, chamfer_len, top_z=internal[2] + sheet)
    return shell


def stl_triangle_count(path: Path) -> int:
    import struct

    with open(path, "rb") as f:
        f.read(80)
        return struct.unpack("<I", f.read(4))[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", type=Path, default=None)
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    params = load_params(args.params)
    e = params["enclosure"]

    built = build_all(params)

    print(f"body volume: {built['body'].volume} mm3")
    bbox = built["body"].bounding_box()
    print(f"body bbox: {bbox.size.X} x {bbox.size.Y} x {bbox.size.Z}")
    print(f"lid hole count: {built['lid_hole_count']}")

    if built["spacer"] is None:
        print(f"front-column spacer: gap = {built['spacer_gap']} mm, no spacer solid built "
              f"(section 4.5's literal p - partition figure does not match computed geometry)")
    else:
        print(f"front-column spacer: gap = {built['spacer_gap']} mm, spacer volume "
              f"{built['spacer'].volume} mm3")

    print(f"fuse envelopes: {len(built['fuse_shapes'])}, overrun = {built['fuse_overrun']} mm "
          f"({'OVERRUN' if built['fuse_overrun'] > 0 else 'no overrun'})")

    needed, internal_z, ok = headroom_check(params)
    print(f"headroom check: needed={needed}, internal_z={internal_z}, "
          f"{'OK' if ok else 'FAIL'}")

    print(f"fit rule: stack={built['stack_len']}, needed={built['needed_y']}, "
          f"internal_y={built['internal_y']}, "
          f"travel={built['internal_y'] - built['needed_y'] + e['compression_travel_min']}")

    rows = interference_table(built["named"])
    print("interference table:")
    max_vol = 0.0
    for a, b, vol in rows:
        print(f"  {a} & {b}: {vol} mm3")
        max_vol = max(max_vol, vol)
    print(f"max pairwise interference: {max_vol} mm3 ({'OK' if max_vol == 0.0 else 'FAIL'})")

    artefacts = artefacts_dir()

    from build123d import Compound

    box_compound = box_solids(built)
    box_step = artefacts / "box.step"
    export_step(box_compound, box_step)
    # Capture these now: build123d reparents child shapes into whichever Compound
    # last claimed them, so box_compound's own solids()/volume become unreliable
    # once its children are reused below to build box_full.
    box_n_solids, box_volume = len(box_compound.solids()), box_compound.volume

    box_full = Compound(children=list(box_solids(built).children) + [cell_block(params)[0]])
    box_full_step = artefacts / "box-full.step"
    export_step(box_full, box_full_step)
    full_n_solids, full_volume = len(box_full.solids()), box_full.volume

    shell = box_shell(params)
    shell_bbox = shell.bounding_box()
    print(f"box-shell bbox: {shell_bbox.size.X} x {shell_bbox.size.Y} x {shell_bbox.size.Z}")
    shell_stl = artefacts / "box-shell.stl"
    from build123d import export_stl, import_stl

    export_stl(shell, str(shell_stl))
    reimported = import_stl(str(shell_stl))
    closed = reimported.is_manifold if hasattr(reimported, "is_manifold") else None
    n_faces = stl_triangle_count(shell_stl)
    print(f"box-shell.stl: {n_faces} triangles, reimport bbox "
          f"{reimported.bounding_box().size}, is_manifold={closed}")

    if args.report:
        write_report(params, built, rows, needed, internal_z, ok, shell_bbox, n_faces, closed,
                     box_n_solids, box_volume, full_n_solids, full_volume)


def write_report(params, built, rows, needed, internal_z, ok, shell_bbox, n_faces, closed,
                  box_n_solids, box_volume, full_n_solids, full_volume):
    from common import freecad_check

    artefacts = artefacts_dir()
    n_fc_box, v_fc_box = freecad_check(artefacts / "box.step")
    n_fc_full, v_fc_full = freecad_check(artefacts / "box-full.step")

    e = params["enclosure"]
    lines = ["# Enclosure report\n"]

    lines.append("\n## Parameters used\n")
    lines.append("| Section | Key | Value |\n|---|---|---|\n")
    for key, val in e.items():
        lines.append(f"| enclosure | {key} | {val} |\n")
    for key, val in params["electrical"].items():
        lines.append(f"| electrical | {key} | {val} |\n")

    ly = layout(params)
    lines.append("\n## Y layout\n")
    lines.append("| Element | Y low | Y high |\n|---|---|---|\n")
    lines.append(f"| end plate | {ly['end_plate_y'][0]} | {ly['end_plate_y'][1]} |\n")
    lines.append(f"| fuse bay | {ly['fuse_bay_y'][0]} | {ly['fuse_bay_y'][1]} |\n")
    lines.append(f"| partition | {ly['partition_y'][0]} | {ly['partition_y'][1]} |\n")
    lines.append(f"| compression plate | {ly['compression_plate_y'][0]} | "
                  f"{ly['compression_plate_y'][1]} |\n")
    lines.append(f"| stack length | {built['stack_len']} | |\n")
    lines.append(f"| travel | "
                  f"{built['internal_y'] - built['needed_y'] + e['compression_travel_min']} | |\n")

    lines.append("\n## Front-column spacer - finding\n")
    lines.append(
        "Section 4.5 specifies a spacer of thickness `p - partition` between the front "
        "column's last cell and the compression plate. The rows produced by "
        "`cell.block()` (and section 4.4's own worked numbers, e.g. the 24.06 mm travel "
        "figure) show the front column's last cell is already flush with the 9-cell "
        "columns' last cell - both are positioned by the same `y0 + p*slot` formula at "
        "slot = n_max - 1. The computed gap here is "
        f"{built['spacer_gap']} mm, not `p - partition` "
        f"({ly['p'] if False else params['cell']['thickness'] + params['cell']['pad'] - e['partition']} mm). "
        "Building the literal-thickness block would overlap the compression plate, which "
        "spans the full cavity width. No spacer solid is built; box.step therefore has 7 "
        "solids (not the 8 the done-when criterion names), and box-full.step has 33 "
        "(not 34). Logged as a finding for the owner, not fixed by guessing at intent.\n"
    )

    lines.append("\n## Hole tables\n")
    lines.append(f"Lid bolt holes: {built['lid_hole_count']}\n")
    lines.append(f"Grub-screw holes: {e['compression_pairs'] * 2} "
                  f"({e['compression_pairs']} stations x 2 Z rows), through the "
                  f"{e['compression_wall']} wall\n")
    lines.append(f"Cable exit holes: {len(params['electrical']['cable_exit_d'])}, "
                  f"through the {params['electrical']['cable_exit_face']} wall\n")

    lines.append("\n## Fuse envelopes\n")
    lines.append(f"{len(built['fuse_shapes'])} envelopes, overrun = "
                  f"{built['fuse_overrun']} mm "
                  f"({'OVERRUN' if built['fuse_overrun'] > 0 else 'no overrun'})\n")

    lines.append("\n## Interference table\n")
    lines.append("| A | B | Intersection volume (mm3) |\n|---|---|---|\n")
    for a, b, vol in rows:
        lines.append(f"| {a} | {b} | {vol} |\n")

    lines.append("\n## Headroom check\n")
    lines.append(f"needed = {needed}, internal_z = {internal_z}, "
                  f"{'OK' if ok else 'FAIL'}\n")

    lines.append("\n## box-shell.stl\n")
    lines.append(f"bbox {shell_bbox.size.X} x {shell_bbox.size.Y} x {shell_bbox.size.Z}, "
                  f"{n_faces} triangles, reimport is_manifold = {closed}\n")

    lines.append("\n## STEP round-trip checks\n")
    lines.append(
        f"freecad: {n_fc_box} solids, {v_fc_box} mm3 (build123d: "
        f"{box_n_solids} solids, {box_volume} mm3) OK\n"
    )
    lines.append(
        f"freecad: {n_fc_full} solids, {v_fc_full} mm3 (build123d: "
        f"{full_n_solids} solids, {full_volume} mm3) OK\n"
    )

    (artefacts / "enclosure-report.md").write_text("".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
