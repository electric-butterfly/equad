# Mesh toolset — installed and smoke-tested 2026-09-14

## Versions

| Package | Version |
|---|---|
| numpy | 2.5.3 |
| scipy | 1.18.1 |
| trimesh | 5.1.0 |
| pymeshlab | 2025.7.post1 |
| open3d | 0.19.0 |
| pyransac3d | 0.7.0 |
| psutil | 7.2.2 |
| CloudCompare (winget `CloudCompare.CloudCompare`) | already installed on this machine; install folder `CloudCompare` |
| MeshLab (winget `CNRISTI.MeshLab`) | 2025.07; install folder `MeshLab` |

`plugins/QRANSAC_SD_PLUGIN.dll` confirmed present beside `CloudCompare.exe`.

## Smoke results

### (a) Import six packages

```
pymeshlab ok
open3d 0.19.0
trimesh 5.1.0
numpy 2.5.3
scipy 1.18.1
pymeshlab 2025.7.post1 (via pip show)
pyransac3d 0.7.0 (via pip show)
```

### (b) Synthetic cylinder through CloudCompare RANSAC

20,000 points on a cylinder of radius 12.5 mm, length 200 mm, outward normals, 0.1 mm gaussian
noise. CloudCompare RANSAC (command per plan section 4.5, `CYLINDER` only) found one cylinder:

```
returncode: 0
mesh files found: ['_smoke_cylinder__smoke_cylinder - Cloud_CYLINDER_0001.ply']
measured radius: 12.550 mm
```

Expected 12.0–13.0 mm — pass.

### (c) pymeshlab sphere decimate/reload

```
face count: 500
```

Expected 500 — pass.
