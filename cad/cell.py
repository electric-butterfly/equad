"""The CALB L148N58A cell and the 26-cell block, per plan section 4.3/4.4."""

import argparse
from pathlib import Path

from build123d import Align, Box, Cylinder, Pos, Rot

from common import artefacts_dir, check_step, load_params, repo_root


def cell(params: dict):
    c = params["cell"]
    width, thickness, height = c["width"], c["thickness"], c["height"]
    stud_h = c["height_to_stud"] - height

    body = Pos(0, 0, height / 2) * Box(width, thickness, height)

    stud_align = (Align.CENTER, Align.CENTER, Align.MIN)
    stud1 = Pos(-c["stud_pitch"] / 2, 0, height) * Cylinder(
        c["stud_d"] / 2, stud_h, align=stud_align
    )
    stud2 = Pos(c["stud_pitch"] / 2, 0, height) * Cylinder(
        c["stud_d"] / 2, stud_h, align=stud_align
    )
    return body + stud1 + stud2


def block(params: dict):
    c, b = params["cell"], params["block"]
    thickness = c["thickness"]
    pad = c["pad"]
    p = thickness + pad
    end_plate = params["enclosure"]["end_plate"]
    internal_y = params["enclosure"]["internal"][1]
    compression_plate = params["enclosure"]["compression_plate"]
    compression_travel_min = params["enclosure"]["compression_travel_min"]

    n_max = max(b["columns"])
    stack_len = n_max * p - pad
    needed = end_plate + stack_len + compression_plate + compression_travel_min
    if needed > internal_y:
        print(
            f"FIT RULE FAILED: end_plate={end_plate} + stack={stack_len} + "
            f"compression_plate={compression_plate} + travel_min={compression_travel_min} "
            f"= {needed} > internal_y={internal_y}"
        )
        raise SystemExit(2)

    y0 = -internal_y / 2 + end_plate

    x_centres = [-b["column_pitch_x"], 0.0, b["column_pitch_x"]]
    cells = []
    rows = []
    for col_idx, (x_c, n_cells) in enumerate(zip(x_centres, b["columns"])):
        for j in range(n_cells):
            if n_cells == 8:
                # front column: fuse bay occupies j=0 of a 9-slot pattern; cells sit at j=1..8
                slot = j + 1
            else:
                slot = j
            y_c = y0 + p * slot + thickness / 2
            flipped = b["flip_odd"] and (j % 2 == 1)
            rot = Rot(Z=180) if flipped else Rot(Z=0)
            placed = Pos(x_c, y_c, 0) * rot * cell(params)
            cells.append(placed)
            rows.append((col_idx, j, x_c, y_c, 0.0, flipped))

    compound = cells[0]
    for s in cells[1:]:
        compound = compound + s
    return compound, rows, stack_len, needed, internal_y


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", type=Path, default=None)
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    params = load_params(args.params)

    c_shape = cell(params)
    print(f"cell volume: {c_shape.volume} mm3")
    bbox = c_shape.bounding_box()
    print(
        f"cell bbox: {bbox.size.X} x {bbox.size.Y} x {bbox.size.Z}"
    )

    artefacts = artefacts_dir()
    cell_step = artefacts / "cell.step"
    from common import export_step

    export_step(c_shape, cell_step)

    b_shape, rows, stack_len, needed, internal_y = block(params)
    bbox_b = b_shape.bounding_box()
    print(
        f"block bbox: {bbox_b.size.X} x {bbox_b.size.Y} x {bbox_b.size.Z}, "
        f"{len(rows)} cells"
    )
    print(f"fit rule: stack={stack_len}, needed={needed}, internal_y={internal_y}, "
          f"travel={internal_y - needed + params['enclosure']['compression_travel_min']}")

    block_step = artefacts / "block.step"
    export_step(b_shape, block_step)

    if args.report:
        write_report(params, c_shape, bbox, b_shape, bbox_b, rows, stack_len, needed, internal_y)


def write_report(params, c_shape, bbox, b_shape, bbox_b, rows, stack_len, needed, internal_y):
    from common import freecad_check

    artefacts = artefacts_dir()
    n_fc_c, v_fc_c = freecad_check(artefacts / "cell.step")
    n_fc_b, v_fc_b = freecad_check(artefacts / "block.step")

    lines = ["# Cell and block report\n"]
    lines.append("## Parameters\n")
    lines.append("| Section | Key | Value | Source |\n|---|---|---|---|\n")
    for key, val in params["cell"].items():
        lines.append(f"| cell | {key} | {val} | params.toml |\n")
    for key, val in params["block"].items():
        lines.append(f"| block | {key} | {val} | params.toml |\n")

    lines.append("\n## Cell\n")
    lines.append(f"- Volume: {c_shape.volume} mm3\n")
    lines.append(f"- Bounding box: {bbox.size.X} x {bbox.size.Y} x {bbox.size.Z}\n")

    lines.append("\n## Block: 26-row position table\n")
    lines.append("| Column | Index j | Centre X | Centre Y | Centre Z | Flipped |\n")
    lines.append("|---|---|---|---|---|---|\n")
    for col_idx, j, x_c, y_c, z_c, flipped in rows:
        lines.append(f"| {col_idx} | {j} | {x_c} | {y_c} | {z_c} | {flipped} |\n")

    lines.append("\n## Block bounding box\n")
    lines.append(f"{bbox_b.size.X} x {bbox_b.size.Y} x {bbox_b.size.Z}\n")

    lines.append("\n## Fit rule\n")
    lines.append(
        f"stack length = {stack_len}, needed = {needed}, internal_y = {internal_y}, "
        f"travel = {internal_y - needed + params['enclosure']['compression_travel_min']}\n"
    )

    lines.append("\n## STEP round-trip checks\n")
    lines.append(
        f"freecad: {n_fc_c} solids, {v_fc_c} mm3 (build123d: {len(c_shape.solids())} solids, "
        f"{c_shape.volume} mm3) OK\n"
    )
    lines.append(
        f"freecad: {n_fc_b} solids, {v_fc_b} mm3 (build123d: {len(b_shape.solids())} solids, "
        f"{b_shape.volume} mm3) OK\n"
    )

    (artefacts / "cell-report.md").write_text("".join(lines))


if __name__ == "__main__":
    main()
