"""Shared helpers for the eQuad scan pipeline: config, STL streaming, PNG silhouettes, circle fits."""

import struct
import subprocess
import tomllib
import zlib
from pathlib import Path

import numpy as np


def _repo_root() -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True,
    )
    return Path(out.stdout.strip())


def load_config(path: str | Path = "pipeline/config.local.toml") -> dict:
    root = _repo_root()
    config_path = Path(path)
    if not config_path.is_absolute():
        config_path = root / config_path
    if not config_path.exists():
        raise FileNotFoundError(f"config file not found: {config_path}")

    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    required = ["scan_full", "scan_low", "data_root", "cloudcompare_exe", "freecad_cmd"]
    for key in required:
        if key not in config:
            raise KeyError(f"missing required config key: {key}")

    data_root = Path(config["data_root"])
    if not data_root.is_absolute():
        data_root = root / data_root
    config["data_root"] = data_root

    for key in ["scan_full", "scan_low", "cloudcompare_exe"]:
        p = Path(config[key])
        if not p.exists():
            raise FileNotFoundError(f"{key} does not exist: {p}")
        config[key] = p

    if config["freecad_cmd"]:
        config["freecad_cmd"] = Path(config["freecad_cmd"])

    return config


def stream_stl(path, chunk_faces: int = 4_000_000):
    """Yield (normals, vertices) numpy arrays per chunk of a binary STL, via readinto."""
    with open(path, "rb") as f:
        f.seek(80)
        (face_count,) = struct.unpack("<I", f.read(4))

        record_dtype = np.dtype([
            ("normal", "<f4", 3),
            ("v0", "<f4", 3),
            ("v1", "<f4", 3),
            ("v2", "<f4", 3),
            ("attr", "<u2"),
        ])
        record_size = record_dtype.itemsize

        remaining = face_count
        while remaining > 0:
            n = min(chunk_faces, remaining)
            buf = bytearray(n * record_size)
            read = f.readinto(buf)
            if read != len(buf):
                raise IOError(f"short read: expected {len(buf)} bytes, got {read}")
            records = np.frombuffer(buf, dtype=record_dtype, count=n)
            normals = records["normal"].copy()
            vertices = np.stack([records["v0"], records["v1"], records["v2"]], axis=1).copy()
            yield normals, vertices
            remaining -= n


def silhouette_png(points, path, axes=(0, 1), depth_axis=2, mm_per_px: float = 1.0):
    """Write a numpy-only PNG: nearest-surface depth shading of points projected onto `axes`."""
    points = np.asarray(points, dtype=np.float64)
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

    _write_gray_png(Path(path), shaded)


def _write_gray_png(path: Path, image: np.ndarray) -> None:
    height, width = image.shape

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data))
        )

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)

    raw = bytearray()
    for r in range(height):
        raw.append(0)
        raw.extend(image[r].tobytes())
    idat = zlib.compress(bytes(raw), level=6)

    png = sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def fit_circle_trimmed(x, y, iterations: int = 8):
    """Kasa least-squares circle fit with 3-sigma robust trimming."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    mask = np.ones(x.shape[0], dtype=bool)

    cx = cy = r = 0.0
    for _ in range(max(1, iterations)):
        xs, ys = x[mask], y[mask]
        A = np.column_stack([xs, ys, np.ones_like(xs)])
        b = xs**2 + ys**2
        sol, *_ = np.linalg.lstsq(A, b, rcond=None)
        cx, cy = sol[0] / 2, sol[1] / 2
        r = float(np.sqrt(sol[2] + cx**2 + cy**2))

        residual = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) - r
        sigma = residual[mask].std()
        if sigma < 1e-9:
            mask = np.abs(residual) <= 1e-9
            break
        mask = np.abs(residual) <= 3 * sigma

    residual = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) - r
    rms = float(np.sqrt(np.mean(residual[mask] ** 2)))

    return {"centre": (cx, cy), "radius": r, "inlier_mask": mask, "rms": rms}
