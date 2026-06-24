#!/usr/bin/env python3
"""
Trimesh-based voxelizer.

Replaces the C++ `obj2voxel` pipeline (and the intermediate GLB -> OBJ
conversion) with a pure-Python voxelizer built on top of trimesh. The GLB is
loaded directly, its textures/materials are baked into per-vertex colors, and
the surface is voxelized while preserving color for every occupied voxel.

The output is a standard `.xyzrgb` file (one `x y z r g b` per line, RGB in the
0-255 range) which is byte-for-byte compatible with the rest of the brick
pipeline, so no downstream code needs to change.
"""

import struct
from pathlib import Path
from typing import Tuple

import numpy as np
import trimesh
from scipy.spatial import cKDTree


def _load_colored_mesh(glb_path: str) -> trimesh.Trimesh:
    """Load a GLB and return a single Trimesh, preserving texture/UVs when possible.

    Scene transforms are applied so every sub-mesh ends up in a common
    coordinate space. A single-geometry GLB (the common case for generated
    meshes) keeps its original `TextureVisuals`, which lets us sample the PNG
    directly per voxel. When a scene has multiple geometries we fall back to
    baking per-vertex colors so they can be safely concatenated.
    """
    loaded = trimesh.load(glb_path, force="scene", process=False)

    geometries = [
        geom
        for geom in loaded.dump()
        if isinstance(geom, trimesh.Trimesh) and len(geom.faces) > 0
    ]

    if not geometries:
        raise RuntimeError(f"No mesh geometry found in GLB: {glb_path}")

    if len(geometries) == 1:
        # Keep the textured visual intact for accurate per-voxel UV sampling.
        return geometries[0]

    # Multiple geometries: bake to vertex colors so concatenation is lossless.
    for geom in geometries:
        try:
            geom.visual = geom.visual.to_color()
        except Exception:
            pass
    return trimesh.util.concatenate(geometries)


def _material_image(visual) -> object:
    """Extract the base-color texture image (PIL) from a TextureVisuals, if any."""
    material = getattr(visual, "material", None)
    if material is None:
        return None
    for attr in ("baseColorTexture", "image"):
        image = getattr(material, attr, None)
        if image is not None:
            return image
    return None


def _coerce_rgb(colors: np.ndarray, count: int) -> np.ndarray:
    """Normalize an arbitrary color array to shape (count, 3).

    Handles grayscale textures/vertex-colors (which come back 1-D) and arrays
    with fewer than 3 channels, so downstream `[:, :3]` indexing is always safe.
    """
    colors = np.asarray(colors)
    if colors.ndim == 1:
        if colors.shape[0] == count and count != 3:
            # Per-point grayscale value -> replicate across RGB.
            colors = np.repeat(colors.reshape(-1, 1), 3, axis=1)
        elif colors.shape[0] >= 3:
            # A single flat color -> broadcast to every point.
            colors = np.tile(colors[:3], (count, 1))
        else:
            fill = int(colors.reshape(-1)[0]) if colors.size else 180
            colors = np.full((count, 3), fill)
    if colors.ndim >= 2 and colors.shape[-1] < 3:
        reps = 3 - colors.shape[-1]
        colors = np.concatenate([colors, np.repeat(colors[..., -1:], reps, axis=-1)], axis=-1)
    return colors[..., :3]


def _sample_voxel_colors(mesh: trimesh.Trimesh, points: np.ndarray) -> np.ndarray:
    """Return an (N, 3) uint8 color for each voxel center.

    Preferred path: for a textured mesh, find each point's closest surface
    location, interpolate that triangle's UVs (barycentric), and read the PNG
    pixel directly so we keep full texture detail at voxel resolution.

    Fallback path: nearest-vertex color (used for vertex-colored meshes or when
    no texture/UVs are available).
    """
    n = len(points)
    visual = mesh.visual
    uv = getattr(visual, "uv", None)
    image = _material_image(visual)
    if image is not None:
        # Normalize palette/grayscale textures to RGB so sampling returns
        # consistent (N, 3+) arrays.
        try:
            image = image.convert("RGB")
        except Exception:
            pass

    if uv is not None and image is not None:
        # Preferred: closest surface point + barycentric UV -> direct PNG pixel.
        # Requires a triangle spatial index (rtree); fall back if unavailable.
        try:
            uv = np.asarray(uv)
            closest, _distance, face_idx = mesh.nearest.on_surface(points)
            triangles = mesh.triangles[face_idx]
            bary = trimesh.triangles.points_to_barycentric(triangles, closest)
            face_uv = uv[mesh.faces[face_idx]]            # (N, 3, 2)
            sample_uv = (bary[:, :, None] * face_uv).sum(axis=1)  # (N, 2)
            colors = np.asarray(trimesh.visual.color.uv_to_color(sample_uv, image))
            colors = _coerce_rgb(colors, n)
            print("  🎨 Color source: per-voxel texture UV sampling")
            return np.clip(colors.astype(int), 0, 255)
        except Exception as exc:  # e.g. rtree not installed
            print(f"  ⚠️  Surface UV sampling unavailable ({exc}); using nearest-vertex colors")

    # Fallback: nearest-vertex color. For a textured mesh, `to_color()` samples
    # the texture at each vertex's UV to produce per-vertex colors.
    visual_colors = visual
    if not hasattr(visual_colors, "vertex_colors"):
        try:
            visual_colors = visual.to_color()
        except Exception:
            visual_colors = None

    vertex_colors = None
    if visual_colors is not None:
        try:
            vertex_colors = np.asarray(visual_colors.vertex_colors)
        except Exception:
            vertex_colors = None

    tree = cKDTree(mesh.vertices)
    _, nearest_vertex = tree.query(points)

    if vertex_colors is None or vertex_colors.size == 0:
        # No usable color information; fall back to a neutral gray.
        return np.full((n, 3), 180, dtype=int)

    vertex_colors = _coerce_rgb(vertex_colors, len(mesh.vertices))
    return np.clip(vertex_colors[nearest_vertex].astype(int), 0, 255)


def glb_to_xyzrgb(
    glb_path: str,
    input_stem: str,
    voxel_size: float,
    output_dir: Path,
) -> Path:
    """Voxelize a GLB directly into an `.xyzrgb` file using trimesh.

    Args:
        glb_path: Path to the input GLB file.
        input_stem: Base name used for the output file.
        voxel_size: Voxel resolution (number of voxels along the largest axis).
        output_dir: Directory to write the `.xyzrgb` file into.

    Returns:
        Path to the generated `.xyzrgb` file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n🔄 Voxelizing GLB with trimesh: {glb_path}")
    mesh = _load_colored_mesh(glb_path)
    print(f"  📐 Mesh: {len(mesh.vertices)} verts, {len(mesh.faces)} faces")

    # GLB is Y-up; the brick pipeline expects Z-up. obj2voxel achieved this with
    # the "xZy" permutation, which is a +90° rotation about the X axis.
    mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2.0, [1, 0, 0]))

    resolution = max(int(voxel_size), 1)
    pitch = float(mesh.extents.max()) / resolution
    if pitch <= 0:
        raise RuntimeError("Mesh has zero extent; cannot voxelize.")

    print(f"  🧊 Resolution: {resolution} (pitch={pitch:.6f})")
    voxel_grid = mesh.voxelized(pitch=pitch)

    indices = np.asarray(voxel_grid.sparse_indices)  # integer grid coords (N, 3)
    points = np.asarray(voxel_grid.points)           # world-space voxel centers (N, 3)
    if len(indices) == 0:
        raise RuntimeError("Voxelization produced no voxels.")

    # Sample a color for each occupied voxel (direct PNG/UV sampling when textured).
    colors = _sample_voxel_colors(mesh, points)

    print(f"  ✅ Voxelized to {len(indices)} colored voxels")

    xyzrgb_path = output_dir / f"{input_stem}.xyzrgb"
    lines = [
        f"{int(x)} {int(y)} {int(z)} {int(r)} {int(g)} {int(b)}"
        for (x, y, z), (r, g, b) in zip(indices, colors)
    ]
    xyzrgb_path.write_text("\n".join(lines) + "\n")
    print(f"  💾 Wrote XYZRGB file: {xyzrgb_path}")

    return xyzrgb_path


def _parse_xyzrgb(xyzrgb_content: str) -> Tuple[np.ndarray, np.ndarray]:
    """Parse `x y z r g b` content into integer coord and color arrays."""
    coords = []
    colors = []
    for line in xyzrgb_content.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) < 6:
            continue
        coords.append((int(parts[0]), int(parts[1]), int(parts[2])))
        colors.append((int(float(parts[3])), int(float(parts[4])), int(float(parts[5]))))
    return np.asarray(coords, dtype=int), np.asarray(colors, dtype=int)


def write_vox_from_xyzrgb(vox_path: str, xyzrgb_content: str) -> None:
    """Write a MagicaVoxel `.vox` file from `.xyzrgb` content.

    Produces the same secondary artifact the old obj2voxel pipeline emitted so
    downstream storage uploads keep working. The palette is built from the
    (already palette-limited) colors in the xyzrgb content.
    """
    coords, colors = _parse_xyzrgb(xyzrgb_content)
    if len(coords) == 0:
        return

    # Shift coordinates so they start at 0 and fit MagicaVoxel's 0-255 grid.
    coords = coords - coords.min(axis=0)
    coords = np.clip(coords, 0, 255)
    dims = coords.max(axis=0) + 1

    # Build a palette (MagicaVoxel supports up to 255 colors + an unused index 0).
    unique_colors, inverse = np.unique(colors, axis=0, return_inverse=True)
    if len(unique_colors) > 255:
        # Keep the 255 most frequent colors and remap the rest to the nearest.
        counts = np.bincount(inverse)
        keep = np.argsort(counts)[::-1][:255]
        palette = unique_colors[keep]
        palette_tree = cKDTree(palette)
        _, color_index = palette_tree.query(colors)
    else:
        palette = unique_colors
        color_index = inverse

    def _chunk(chunk_id: bytes, content: bytes) -> bytes:
        return chunk_id + struct.pack("<ii", len(content), 0) + content

    # SIZE chunk
    size_content = struct.pack("<iii", int(dims[0]), int(dims[1]), int(dims[2]))
    size_chunk = _chunk(b"SIZE", size_content)

    # XYZI chunk (voxel color indices are 1-based)
    voxel_bytes = bytearray()
    voxel_bytes += struct.pack("<i", len(coords))
    for (x, y, z), idx in zip(coords, color_index):
        voxel_bytes += struct.pack("<BBBB", int(x), int(y), int(z), int(idx) + 1)
    xyzi_chunk = _chunk(b"XYZI", bytes(voxel_bytes))

    # RGBA palette chunk. A voxel index i references file entry i-1, so storing
    # palette[p] at position p means a voxel index (p+1) resolves back to it.
    rgba_bytes = bytearray()
    for i in range(256):
        if i < len(palette):
            r, g, b = palette[i]
            rgba_bytes += struct.pack("<BBBB", int(r), int(g), int(b), 255)
        else:
            rgba_bytes += struct.pack("<BBBB", 0, 0, 0, 0)
    rgba_chunk = _chunk(b"RGBA", bytes(rgba_bytes))

    children = size_chunk + xyzi_chunk + rgba_chunk
    main_chunk = b"MAIN" + struct.pack("<ii", 0, len(children)) + children

    data = b"VOX " + struct.pack("<i", 150) + main_chunk
    Path(vox_path).write_bytes(data)
    print(f"  💾 Wrote VOX file: {vox_path}")
