"""Fusion import pack: the datum marker STEP and the import workflow document. Plan section 4.11.

Runs under .venv-cad. Writes artefacts/datum-marker.step and artefacts/fusion-import.html.
"""

from html import escape
from pathlib import Path

from build123d import Align, Box, Color, Compound, import_step

from common import COLOURS, artefacts_dir, export_step

BARS = [
    # label, (length_x, length_y, length_z), colour
    ("axis_x", (500.0, 20.0, 20.0), "axis_x"),
    ("axis_y", (20.0, 300.0, 20.0), "axis_y"),
    ("axis_z", (20.0, 20.0, 200.0), "axis_z"),
]

# Section 5.9: Open3D vertex bounds of data/derived/chassis_datum_200k.stl.
CHASSIS_MIN = (-311.4, -587.7, 4.3)
CHASSIS_MAX = (1663.0, 562.7, 1206.1)

CSS = """
  :root { --bg:#f3f5f6; --paper:#ffffff; --border:#dde3e6; --ink:#1a2226; --muted:#5b6b74;
          --accent:#2b6c8f; --accent-tint:#e5eef2; --row-alt:#f6f8f9; }
  * { box-sizing: border-box; }
  body { background:var(--bg); color:var(--ink); font-family: system-ui, -apple-system, sans-serif;
         font-size:18px; margin:0; padding:40px 16px; line-height:1.5; }
  .sheet { max-width:1220px; margin:0 auto; background:var(--paper); border:1px solid var(--border);
           border-radius:14px; padding:48px; display:flex; flex-direction:column; gap:28px; }
  header { border-bottom:3px solid var(--accent); padding-bottom:18px; }
  h1 { margin:0 0 6px 0; font-size:1.6em; }
  header p { margin:0; color:var(--muted); }
  h2 { font-size:1.2em; border-left:4px solid var(--accent); padding-left:12px; margin:0 0 10px 0; }
  table { border-collapse:collapse; width:100%; font-size:0.85em; }
  th, td { border:1px solid var(--border); padding:6px 10px; text-align:left; vertical-align:top; }
  th { background:var(--accent-tint); }
  tr:nth-child(even) { background:var(--row-alt); }
  code, .mono { font-family: ui-monospace, "SF Mono", Consolas, monospace; font-size:0.92em; }
  p { margin:0 0 10px 0; }
  ol, ul { margin:0; padding-left:22px; }
  pre { background:var(--row-alt); border:1px solid var(--border); border-radius:6px; padding:10px 14px;
        font-size:0.85em; overflow-x:auto; margin:0; }
  a { color:var(--accent); }
"""


def build_datum_marker(path: Path) -> Compound:
    solids = []
    for label, (lx, ly, lz), colour in BARS:
        bar = Box(lx, ly, lz, align=(Align.MIN, Align.MIN, Align.MIN))
        bar.label = label
        bar.color = Color(*COLOURS[colour])
        solids.append(bar)
    marker = Compound(children=solids, label="datum_marker")
    export_step(marker, path)
    return marker


def bounds(path: Path) -> list[tuple[str, tuple, tuple]]:
    """Label and axis-aligned bounds of every child of the STEP at path, from a fresh import."""
    root = import_step(str(path))
    rows = []
    for child in root.children:
        bb = child.bounding_box()
        rows.append(
            (child.label, (bb.min.X, bb.min.Y, bb.min.Z), (bb.max.X, bb.max.Y, bb.max.Z))
        )
    return rows


def fmt(v: float) -> str:
    return f"{v:.1f}"


def triple(t: tuple) -> str:
    return "(" + ", ".join(fmt(v) for v in t) + ")"


def rows_html(rows: list[list[str]]) -> str:
    return "\n".join(
        "        <tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows
    )


def build_html(marker_bounds: list, assembly_bounds: list) -> str:
    files = [
        ("datum-marker.step", "Three bars from the origin. Import this first, alone."),
        ("assembly.step", "Both battery boxes, the motor placeholder and the propeller-shaft keep-out, at their vehicle coordinates."),
        ("box.step", "One enclosure with its lid, plates and fuses, no cells."),
        ("box-full.step", "One enclosure with its 26 cells."),
        ("block.step", "The 26-cell block on its own."),
        ("cell.step", "One CALB L148N58A cell."),
        ("chassis_datum_200k.stl", "The scanned frame, 200 000 faces, in the same vehicle frame. A mesh, not a solid; it lives in the cleaned scan folder, not in this folder."),
    ]
    files_html = rows_html([[f"<code>{n}</code>", escape(d)] for n, d in files])

    marker_html = rows_html(
        [
            [f"<code>{escape(lbl)}</code>", triple(lo), triple(hi), "0.5 mm"]
            for lbl, lo, hi in marker_bounds
        ]
    )
    lengths = ", ".join(
        f"{lbl} {fmt(max(h - l for l, h in zip(lo, hi)))} mm" for lbl, lo, hi in marker_bounds
    )

    asm_html = rows_html(
        [
            [f"<code>{escape(lbl)}</code>", triple(lo), triple(hi), "0.5 mm"]
            for lbl, lo, hi in assembly_bounds
        ]
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>eQuad battery boxes: Fusion import</title>
<style>{CSS}</style>
</head>
<body>
<div class="sheet">
  <header>
    <h1>Importing the battery boxes into Fusion</h1>
    <p>Files, import order and the checks that prove the origin, axes and units arrived unchanged.</p>
  </header>

  <section>
    <h2>1. What the files are</h2>
    <p>Every file is in the vehicle datum frame: ISO 8855, millimetres, X forward, Y left, Z up,
    origin below the rear axle housing axis. No file carries a transform; each body sits at its
    vehicle coordinates.</p>
    <table>
      <thead><tr><th>File</th><th>What it holds</th></tr></thead>
      <tbody>
{files_html}
      </tbody>
    </table>
  </section>

  <section>
    <h2>2. Before you import</h2>
    <ol>
      <li>Start an empty design and set its modelling orientation to Z up. Look for the setting
      named Default modeling orientation in Preferences, or the equivalent in your release.</li>
      <li>Import <code>datum-marker.step</code> alone, first, before anything else.</li>
    </ol>
  </section>

  <section>
    <h2>3. The origin and axis check</h2>
    <p>The three bars have different lengths on purpose ({escape(lengths)}). Each starts at the
    origin and runs in the positive direction. Read the bounding box of each bar in Fusion and
    compare it with this table, in Fusion's X, Y and Z.</p>
    <table>
      <thead><tr><th>Body</th><th>Minimum corner (mm)</th><th>Maximum corner (mm)</th><th>Tolerance</th></tr></thead>
      <tbody>
{marker_html}
      </tbody>
    </table>
    <p>What a failure looks like: the wrong bar longest means an axis is swapped; a bar running
    into negative coordinates means an axis is mirrored; sizes out by a factor of 25.4 or 1000
    mean a unit error; a minimum corner away from (0.0, 0.0, 0.0) means the origin moved.</p>
    <p>If any value fails, stop. Write down the three observed bar lengths and which Fusion axis
    each one lies along. Do not rotate or move anything to make it pass.</p>
  </section>

  <section>
    <h2>4. Import the assembly</h2>
    <p>With the check in section 3 passed, import <code>assembly.step</code> into a new design in
    the same orientation. Each body should appear under its name with its own colour; the keep-out
    is written with 35 % opacity. Axis-aligned bounding boxes, in vehicle coordinates:</p>
    <table>
      <thead><tr><th>Body</th><th>Minimum corner (mm)</th><th>Maximum corner (mm)</th><th>Tolerance</th></tr></thead>
      <tbody>
{asm_html}
      </tbody>
    </table>
  </section>

  <section>
    <h2>5. Import the chassis</h2>
    <p>Insert <code>chassis_datum_200k.stl</code> as a mesh body, choosing millimetres if you are
    asked for a unit. Expected bounding box:</p>
    <table>
      <thead><tr><th>Body</th><th>Minimum corner (mm)</th><th>Maximum corner (mm)</th><th>Tolerance</th></tr></thead>
      <tbody>
{rows_html([["<code>chassis_datum_200k</code>", triple(CHASSIS_MIN), triple(CHASSIS_MAX), "1.0 mm"]])}
      </tbody>
    </table>
    <p>A result 25.4 times too large or small means the wrong unit was chosen.</p>
  </section>

  <section>
    <h2>6. Combine and look</h2>
    <p>With the datum marker, the assembly and the chassis in one design and nothing moved, the
    marker's bars lie along the chassis' origin, the left box is on the +Y side, the motor is
    behind the boxes (smaller X), and the keep-out runs along X at Z 340 mm.</p>
  </section>

  <section>
    <h2>7. Rules</h2>
    <ul>
      <li>The CAD is the master. A placement or parameter change is made in <code>cad/params.toml</code>,
      the files are regenerated, and the new files are imported again. Do not edit the imported
      geometry and treat it as the source.</li>
      <li>The committed placement has not been checked clear of the frame: no placement in the swept
      grid passed (<a href="sweep-report.md">sweep-report.md</a>).</li>
      <li>The plastics, foot boards, tank and seat base are not in the scan and are not in these files.</li>
    </ul>
  </section>

  <section>
    <h2>8. Regenerate</h2>
    <p>From the repository root:</p>
    <pre>.venv-cad/Scripts/python cad/cell.py
.venv-cad/Scripts/python cad/enclosure.py
.venv-cad/Scripts/python cad/assembly.py
.venv-cad/Scripts/python cad/fusion_pack.py</pre>
  </section>
</div>
</body>
</html>
"""


def main() -> None:
    artefacts = artefacts_dir()

    marker_path = artefacts / "datum-marker.step"
    build_datum_marker(marker_path)
    marker_bounds = bounds(marker_path)
    for lbl, lo, hi in marker_bounds:
        print(f"{lbl}: min {triple(lo)} max {triple(hi)}")

    assembly_bounds = bounds(artefacts / "assembly.step")
    for lbl, lo, hi in assembly_bounds:
        print(f"{lbl}: min {triple(lo)} max {triple(hi)}")

    html_path = artefacts / "fusion-import.html"
    html_path.write_text(build_html(marker_bounds, assembly_bounds), encoding="utf-8")
    print(f"wrote {html_path} ({html_path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
