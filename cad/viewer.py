"""Viewer and handover document. Plan section 4.9.

Runs under .venv-cad (import_step needs build123d). The chassis decimation needs open3d, which
lives only in .venv-mesh, so this script shells out to that venv's interpreter for that one step
and reads the result back from a cached file under data/cad/.
"""

import base64
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

from common import artefacts_dir, repo_root, load_params

CDN_THREE = "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"

BODY_NAMES = ["chassis", "box_left", "box_right", "motor", "keepout"]
BODY_COLOURS = {
    "chassis": "0x9aa4ab",
    "box_left": "0x2b6c8f",
    "box_right": "0x2b6c8f",
    "motor": "0xd9822b",
    "keepout": "0xc0392b",
}
BODY_OPACITY = {
    "chassis": 1.0,
    "box_left": 1.0,
    "box_right": 1.0,
    "motor": 1.0,
    "keepout": 0.35,
}
BODY_LABELS = {
    "chassis": "Chassis",
    "box_left": "Battery box (left)",
    "box_right": "Battery box (right)",
    "motor": "Motor",
    "keepout": "Prop-shaft keep-out",
}


# ---------------------------------------------------------------------------
# 1. Chassis: decimate under .venv-mesh, cache the base64 soup
# ---------------------------------------------------------------------------

_DECIMATE_SCRIPT = """
import base64, sys, tomllib
from pathlib import Path
import numpy as np
import open3d as o3d
repo = Path(sys.argv[1])
out_path = Path(sys.argv[2])
with open(repo / "cad" / "params.toml", "rb") as f:
    params = tomllib.load(f)
mesh = o3d.io.read_triangle_mesh(str(repo / params["chassis"]["mesh_viewer"]))
dec = mesh.simplify_quadric_decimation(target_number_of_triangles=60000)
verts = np.asarray(dec.vertices, dtype=np.float32)
tris = np.asarray(dec.triangles, dtype=np.int64)
soup = verts[tris.reshape(-1)]
out_path.write_bytes(base64.b64encode(soup.tobytes()))
bmin = verts.min(axis=0).tolist()
bmax = verts.max(axis=0).tolist()
print(len(tris))
print(bmin)
print(bmax)
"""


def decimate_chassis(repo: Path) -> tuple[str, int, list[float], list[float]]:
    mesh_python = repo / ".venv-mesh" / "Scripts" / "python.exe"
    if not mesh_python.exists():
        raise RuntimeError(f".venv-mesh interpreter not found at {mesh_python}")
    cache = repo / "data" / "cad" / "chassis_60k.b64"
    cache.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [str(mesh_python), "-c", _DECIMATE_SCRIPT, str(repo), str(cache)],
        capture_output=True, text=True, check=True,
    )
    lines = result.stdout.strip().splitlines()
    face_count = int(lines[0])
    bmin = json.loads(lines[1].replace("'", '"'))
    bmax = json.loads(lines[2].replace("'", '"'))
    b64 = cache.read_text(encoding="ascii")
    return b64, face_count, bmin, bmax


# ---------------------------------------------------------------------------
# 2. Assembly bodies: tessellate under .venv-cad (build123d is native here)
# ---------------------------------------------------------------------------

def tessellate_assembly(repo: Path) -> dict[str, str]:
    from build123d import import_step

    assembly_path = artefacts_dir() / "assembly.step"
    if not assembly_path.exists():
        raise FileNotFoundError(assembly_path)
    assembly = import_step(str(assembly_path))
    solids = assembly.solids()
    if len(solids) != 4:
        raise RuntimeError(f"expected 4 solids in assembly.step, found {len(solids)}")

    names = ["box_left", "box_right", "motor", "keepout"]
    c0 = solids[0].bounding_box().center()
    c1 = solids[1].bounding_box().center()
    if not (c0.Y > 0 and c1.Y < 0):
        raise RuntimeError(
            f"assembly.step solid order does not match [box_left, box_right, motor, keepout]: "
            f"solid 0 centre.Y={c0.Y}, solid 1 centre.Y={c1.Y}"
        )

    out = {}
    for name, s in zip(names, solids):
        verts, tris = s.tessellate(0.5)
        verts_arr = np.array([[v.X, v.Y, v.Z] for v in verts], dtype=np.float32)
        tris_arr = np.array(tris, dtype=np.int64)
        soup = verts_arr[tris_arr.reshape(-1)]
        out[name] = base64.b64encode(soup.tobytes()).decode("ascii")
    return out


# ---------------------------------------------------------------------------
# 3. viewer.html
# ---------------------------------------------------------------------------

def build_viewer_html(bodies_b64: dict[str, str], x_min: float, x_max: float) -> str:
    checkboxes = "\n".join(
        f'      <label><input type="checkbox" checked data-body="{name}"> {BODY_LABELS[name]}</label>'
        for name in BODY_NAMES
    )
    body_defs = ",\n".join(
        f'      {name}: {{ b64: BODIES["{name}"], colour: {BODY_COLOURS[name]}, '
        f'opacity: {BODY_OPACITY[name]} }}'
        for name in BODY_NAMES
    )
    bodies_json = ",\n".join(f'    "{name}": "{b64}"' for name, b64 in bodies_b64.items())

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>eQuad battery box viewer</title>
<script src="{CDN_THREE}"></script>
<style>
  html, body {{ margin: 0; height: 100%; background: #f3f5f6; overflow: hidden; font-family: system-ui, sans-serif; }}
  #panel {{
    position: fixed; top: 12px; left: 12px; background: #ffffffdd; border: 1px solid #dde3e6;
    border-radius: 8px; padding: 12px 16px; font-size: 14px; color: #1a2226; z-index: 10;
  }}
  #panel label {{ display: block; margin: 4px 0; }}
  #panel .row {{ margin-top: 10px; }}
  #panel input[type="range"] {{ width: 220px; }}
</style>
</head>
<body>
<div id="panel">
  <strong>Bodies</strong>
{checkboxes}
  <div class="row">
    <label for="clip">Clip plane (vehicle X, mm)</label>
    <input id="clip" type="range" min="{x_min:.0f}" max="{x_max:.0f}" value="{x_max:.0f}" step="10">
    <span id="clip-value">{x_max:.0f}</span>
  </div>
</div>
<canvas id="c"></canvas>
<script>
const BODIES = {{
{bodies_json}
}};
const DEFS = {{
{body_defs}
}};

function decode(b64) {{
  const bin = atob(b64);
  const buf = new ArrayBuffer(bin.length);
  const view = new Uint8Array(buf);
  for (let i = 0; i < bin.length; i++) view[i] = bin.charCodeAt(i);
  return new Float32Array(buf);
}}

const renderer = new THREE.WebGLRenderer({{ canvas: document.getElementById('c'), antialias: true }});
renderer.setPixelRatio(window.devicePixelRatio);
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setClearColor(0xf3f5f6);
renderer.localClippingEnabled = true;

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 1, 20000);
camera.up.set(0, 0, 1);

const ambient = new THREE.AmbientLight(0xffffff, 0.55);
scene.add(ambient);
const key = new THREE.DirectionalLight(0xffffff, 0.7);
key.position.set(1000, -800, 1500);
scene.add(key);
const fill = new THREE.DirectionalLight(0xffffff, 0.35);
fill.position.set(-800, 900, 600);
scene.add(fill);

const clipPlane = new THREE.Plane(new THREE.Vector3(-1, 0, 0), {x_max:.0f});

const meshes = {{}};
for (const name of Object.keys(DEFS)) {{
  const def = DEFS[name];
  const positions = decode(def.b64);
  const geom = new THREE.BufferGeometry();
  geom.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geom.computeVertexNormals();
  const material = new THREE.MeshStandardMaterial({{
    color: def.colour, transparent: def.opacity < 1, opacity: def.opacity,
    side: THREE.DoubleSide, clippingPlanes: [clipPlane], metalness: 0.05, roughness: 0.85,
  }});
  const mesh = new THREE.Mesh(geom, material);
  scene.add(mesh);
  meshes[name] = mesh;
}}

const axes = new THREE.AxesHelper(300);
scene.add(axes);

const grid = new THREE.GridHelper(2400, 24, 0xb7c0c6, 0xd6dcdf);
grid.rotation.x = Math.PI / 2;
grid.position.set(700, 0, 0);
scene.add(grid);

// Custom orbit control: Z-up spherical camera. Left-drag rotates, wheel zooms, right-drag pans.
const target = new THREE.Vector3(700, 0, 400);
let radius = 3200, azimuth = -0.9, polar = 1.1;
let panOffset = new THREE.Vector3();

function updateCamera() {{
  const p = target.clone().add(panOffset);
  const x = p.x + radius * Math.sin(polar) * Math.cos(azimuth);
  const y = p.y + radius * Math.sin(polar) * Math.sin(azimuth);
  const z = p.z + radius * Math.cos(polar);
  camera.position.set(x, y, z);
  camera.lookAt(p);
}}
updateCamera();

let dragging = null;
let lastX = 0, lastY = 0;
renderer.domElement.addEventListener('contextmenu', (e) => e.preventDefault());
renderer.domElement.addEventListener('pointerdown', (e) => {{
  dragging = e.button === 2 ? 'pan' : 'rotate';
  lastX = e.clientX; lastY = e.clientY;
}});
window.addEventListener('pointerup', () => {{ dragging = null; }});
window.addEventListener('pointermove', (e) => {{
  if (!dragging) return;
  const dx = e.clientX - lastX, dy = e.clientY - lastY;
  lastX = e.clientX; lastY = e.clientY;
  if (dragging === 'rotate') {{
    azimuth -= dx * 0.005;
    polar = Math.min(Math.max(polar - dy * 0.005, 0.05), Math.PI - 0.05);
  }} else {{
    const panScale = radius * 0.0015;
    const forward = new THREE.Vector3().subVectors(target, camera.position).normalize();
    const right = new THREE.Vector3().crossVectors(forward, camera.up).normalize();
    const up = new THREE.Vector3().crossVectors(right, forward).normalize();
    panOffset.addScaledVector(right, -dx * panScale);
    panOffset.addScaledVector(up, dy * panScale);
  }}
  updateCamera();
}});
renderer.domElement.addEventListener('wheel', (e) => {{
  e.preventDefault();
  radius *= (1 + Math.sign(e.deltaY) * 0.1);
  radius = Math.min(Math.max(radius, 200), 12000);
  updateCamera();
}}, {{ passive: false }});

for (const cb of document.querySelectorAll('#panel input[type="checkbox"]')) {{
  cb.addEventListener('change', () => {{
    meshes[cb.dataset.body].visible = cb.checked;
  }});
}}

const clipInput = document.getElementById('clip');
const clipValue = document.getElementById('clip-value');
clipInput.addEventListener('input', () => {{
  clipPlane.constant = parseFloat(clipInput.value);
  clipValue.textContent = clipInput.value;
}});

window.addEventListener('resize', () => {{
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
}});

function animate() {{
  requestAnimationFrame(animate);
  renderer.render(scene, camera);
}}
animate();
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# 4. sam-battery-boxes.html
# ---------------------------------------------------------------------------

PARAM_ROWS = [
    ("cell.width", "148.24 mm", "CALB L148N58A drawing, W"),
    ("cell.thickness", "26.66 mm", "CALB L148N58A drawing, T at 70% SOC"),
    ("cell.height", "102.8 mm", "CALB L148N58A drawing, body"),
    ("cell.height_to_stud", "105.9 mm", "CALB L148N58A drawing"),
    ("cell.stud_pitch", "110.6 mm", "CALB L148N58A drawing"),
    ("cell.pad", "3.0 mm", "OWNER: BOM figure, confirm with a measurement"),
    ("block.columns", "8, 9, 9 cells front to rear", "owner design brief 2026-09-15"),
    ("block.column_pitch_x", "152.0 mm", "148.24 mm cell width + 3.76 mm clearance"),
    ("enclosure.internal", "460 x 300 x 200 mm", "owner design brief 2026-09-15"),
    ("enclosure.sheet", "3.0 mm", "OWNER: assumed sheet thickness"),
    ("enclosure.compression_wall", "outboard", "OWNER: assumed"),
    ("electrical.fuses_per_box", "2", "Littelfuse JLLN800 Class T, one per pole"),
    ("electrical.fuse_envelope", "90 x 45 x 60 mm", "OWNER: confirm against the datasheet and the holder"),
    ("motor.length", "258.8 mm", "SIAECOSYS QSJ138D-90 outline drawing"),
    ("motor.housing_d", "210.0 mm", "OWNER: tape-measure the finned housing"),
    ("keepout.axis_z", "340.0 mm", "OWNER: confirm from the front differential output height"),
]

OPEN_ITEMS = [
    "Inter-cell pad thickness — measure the supplier-provided pad, BOM says 3 mm.",
    "Enclosure sheet thickness — 3 mm assumed, confirm against the material on hand.",
    "Compression wall — outboard assumed, confirm which wall carries the grub screws.",
    "Fuse envelope — 90 x 45 x 60 mm from the datasheet's 700-800 A row; confirm with the holder in hand.",
    "Motor housing diameter — 210 mm placeholder, not dimensioned on the supplied drawing; tape-measure the finned housing.",
    "Prop-shaft keep-out height — 340 mm read from the scan render, confirm from the front differential output height.",
    "Plastics and duct scan — the frame-only sweep found every lean from 0 to 40 degrees clear; the tank, ducts and plastics are the missing constraint and have not been scanned.",
]


def read_sweep_summary(repo: Path) -> str:
    """Prose paragraphs from sweep-report.md, dropping the grid table (section 4.9 wants the
    result and the best placement, not the full sweep grid)."""
    path = artefacts_dir() / "sweep-report.md"
    text = path.read_text(encoding="utf-8")
    paragraphs = []
    current = []
    for line in text.splitlines():
        if line.startswith("|"):
            continue
        if line.strip() == "":
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        current.append(line.strip())
    if current:
        paragraphs.append(" ".join(current))
    paragraphs = [
        p.replace(
            "so no exact-match row exists; see the nearest grid rows above.",
            "so no exact-match row exists in the swept grid.",
        )
        for p in paragraphs
    ]
    return paragraphs


def read_placement(repo: Path) -> dict:
    path = artefacts_dir() / "placement.json"
    return json.loads(path.read_text(encoding="utf-8"))


def read_pickups(repo: Path, n: int = 20) -> list[dict]:
    path = artefacts_dir() / "mount-pickups.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    return rows[:n]


def build_handover_html(repo: Path) -> str:
    sweep_paragraphs = read_sweep_summary(repo)
    placement = read_placement(repo)
    pickups = read_pickups(repo)

    p = placement.get("params", {})
    left = placement.get("left", {})
    corners = left.get("corners", [])
    lid_normal = left.get("lid_normal", [])
    stack_axis = left.get("stack_axis", [])
    gap = placement.get("inboard_gap_at_floor")

    param_rows_html = "\n".join(
        f"        <tr><td class=\"mono\">{name}</td><td>{value}</td><td>{source}</td></tr>"
        for name, value, source in PARAM_ROWS
    )

    pickup_rows_html = "\n".join(
        f"        <tr><td class=\"mono\">{r['id']}</td><td>{r['kind']}</td><td>{r['box']}</td>"
        f"<td>{r['nearest_face']}</td><td>{r['distance']:.1f}</td><td>{r['support']}</td>"
        f"<td>{r['rms']:.2f}</td></tr>"
        for r in pickups
    )

    open_items_html = "\n".join(f"        <li>{item}</li>" for item in OPEN_ITEMS)

    sweep_html = "\n".join(f"      <p>{p}</p>" for p in sweep_paragraphs)

    corners_str = ", ".join(f"({c[0]:.1f}, {c[1]:.1f}, {c[2]:.1f})" for c in corners)
    lid_str = f"({lid_normal[0]:.3f}, {lid_normal[1]:.3f}, {lid_normal[2]:.3f})" if lid_normal else "n/a"
    stack_str = f"({stack_axis[0]:.3f}, {stack_axis[1]:.3f}, {stack_axis[2]:.3f})" if stack_axis else "n/a"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>eQuad battery boxes -- fabrication handover</title>
<style>
  :root {{
    --bg: #f3f5f6; --paper: #ffffff; --border: #dde3e6; --ink: #1a2226;
    --muted: #5b6b74; --accent: #2b6c8f; --accent-tint: #e5eef2; --row-alt: #f6f8f9;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    background: var(--bg); color: var(--ink); font-family: system-ui, -apple-system, sans-serif;
    font-size: 18px; margin: 0; padding: 40px 16px;
  }}
  .sheet {{
    max-width: 1220px; margin: 0 auto; background: var(--paper); border: 1px solid var(--border);
    border-radius: 14px; padding: 48px; display: flex; flex-direction: column; gap: 32px;
  }}
  header {{ border-bottom: 3px solid var(--accent); padding-bottom: 20px; }}
  header h1 {{ margin: 0 0 8px 0; font-size: 1.7em; }}
  header p {{ margin: 0; color: var(--muted); }}
  h2 {{ font-size: 1.2em; border-left: 4px solid var(--accent); padding-left: 12px; margin-bottom: 12px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 0.85em; }}
  th, td {{ border: 1px solid var(--border); padding: 6px 10px; text-align: left; }}
  th {{ background: var(--accent-tint); }}
  tr:nth-child(even) {{ background: var(--row-alt); }}
  .mono {{ font-family: ui-monospace, "SF Mono", monospace; font-size: 0.95em; }}
  .renders {{ display: flex; gap: 16px; flex-wrap: wrap; }}
  .renders figure {{ margin: 0; flex: 1 1 280px; }}
  .renders img {{ width: 100%; border: 1px solid var(--border); border-radius: 6px; }}
  .renders figcaption {{ color: var(--muted); font-size: 0.85em; margin-top: 4px; }}
  ul {{ margin: 0; padding-left: 22px; }}
  a {{ color: var(--accent); }}
</style>
</head>
<body>
<div class="sheet">
  <header>
    <h1>eQuad battery boxes</h1>
    <p>Fabrication design handover</p>
  </header>

  <section>
    <h2>Purpose</h2>
    <p>Two battery boxes sit either side of the chassis centreline, each holding half the 26S2P
    pack. This document gives the geometry needed to start the fabrication design: the enclosure
    parameters, where each box sits on the vehicle, how the frame around it was checked, and which
    frame features are close enough to carry a mounting bracket.</p>
    <p>The boxes, motor placeholder and prop-shaft keep-out are STEP solids linked below; open them
    in any CAD package for exact dimensions.</p>
  </section>

  <section>
    <h2>Parameters</h2>
    <table>
      <thead><tr><th>Parameter</th><th>Value</th><th>Source</th></tr></thead>
      <tbody>
{param_rows_html}
      </tbody>
    </table>
  </section>

  <section>
    <h2>Placement</h2>
    <p>The left box sits at vehicle X {p.get('x')}, Y {p.get('y')}, Z {p.get('z')} mm, leaned
    {p.get('lean_deg')} degrees off vertical about the vehicle X axis so its largest face (lid and
    floor) tilts toward the centreline. The right box is the left box's mirror image through
    vehicle Y = 0. At the floor, the inboard edges of the two boxes are {gap} mm apart.</p>
    <p>Left box outer-shell corners, vehicle coordinates (mm): {corners_str}.</p>
    <p>Lid normal, outward from the +Z face: {lid_str}. Cell-stack axis: {stack_str}.</p>
  </section>

  <section>
    <h2>Frame clearance</h2>
{sweep_html}
  </section>

  <section>
    <h2>Renders</h2>
    <div class="renders">
      <figure><img src="section-yz-default.png" alt="YZ section at the default placement"><figcaption>YZ section, default placement</figcaption></figure>
      <figure><img src="section-xz-default.png" alt="XZ section at the default placement"><figcaption>XZ section, default placement</figcaption></figure>
      <figure><img src="section-xy-default.png" alt="XY section at the default placement"><figcaption>XY section, default placement</figcaption></figure>
    </div>
  </section>

  <section>
    <h2>Mount pickups (nearest 20)</h2>
    <table>
      <thead><tr><th>id</th><th>kind</th><th>box</th><th>face</th><th>distance mm</th><th>support</th><th>rms</th></tr></thead>
      <tbody>
{pickup_rows_html}
      </tbody>
    </table>
    <p>Every plane pickup was fitted by RANSAC and did not pass the scan pipeline's refinement
    threshold: calliper each one before drilling.</p>
  </section>

  <section>
    <h2>STEP files</h2>
    <ul>
      <li><a href="cell.step">cell.step</a> -- one CALB L148N58A cell</li>
      <li><a href="block.step">block.step</a> -- the 26-cell block</li>
      <li><a href="box.step">box.step</a> -- enclosure, lid and internals, no cells</li>
      <li><a href="box-full.step">box-full.step</a> -- enclosure with the cell block fitted</li>
      <li><a href="assembly.step">assembly.step</a> -- both boxes, motor placeholder and keep-out, on the vehicle datum</li>
    </ul>
  </section>

  <section>
    <h2>Open items</h2>
    <ul>
{open_items_html}
    </ul>
  </section>
</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------

def main() -> None:
    repo = repo_root()
    params = load_params()

    b64, face_count, bmin, bmax = decimate_chassis(repo)
    print(f"chassis: {face_count} faces, base64 {len(b64)} chars")

    bodies_b64 = tessellate_assembly(repo)
    for name, b in bodies_b64.items():
        print(f"{name}: base64 {len(b)} chars")
    bodies_b64["chassis"] = b64

    viewer_html = build_viewer_html(bodies_b64, bmin[0], bmax[0])
    viewer_path = artefacts_dir() / "viewer.html"
    viewer_path.write_text(viewer_html, encoding="utf-8")
    print(f"wrote {viewer_path} ({viewer_path.stat().st_size} bytes)")

    handover_html = build_handover_html(repo)
    handover_path = artefacts_dir() / "sam-battery-boxes.html"
    handover_path.write_text(handover_html, encoding="utf-8")
    print(f"wrote {handover_path} ({handover_path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
