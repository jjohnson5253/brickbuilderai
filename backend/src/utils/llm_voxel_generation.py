"""Direct LLM voxel generation experiment (issue #36).

Instead of the image -> 3D (Trellis / SAM3D) -> voxel pipeline, ask a vision
LLM (GPT-5, Gemini, or any OpenAI-compatible chat-completions model) to look
at a picture and emit a voxel structure directly in the pipeline's xyzrgb
format. Utilities here are pure and unit-testable:

- prompt/message building for the chat-completions API
- robust parsing of LLM output (JSON or plain xyzrgb lines) into voxels
- algorithmic gap filling (closes enclosed cavities and small surface holes)
- comparison metrics between an LLM model and a pipeline baseline model

The ``backend/scripts/llm_voxel_experiment.py`` CLI wires these together.

Coordinate convention matches the brick pipeline: integer grid, Z is up and
the subject's front faces -Y (see VIEWS in ``src/requests/llmRender.py``).
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

DEFAULT_GRID_SIZE = 32
MAX_GRID_SIZE = 64
MAX_LLM_VOXELS = 100_000

Voxel = Dict[str, int]


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------


def build_voxel_generation_messages(
    image_url: str,
    grid_size: int = DEFAULT_GRID_SIZE,
    prompt: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Build chat-completions messages asking a vision LLM for a voxel model.

    ``image_url`` may be an https URL or a base64 data URL.
    """
    system_prompt = (
        "You are a voxel artist. You look at a reference image and design a "
        "solid, buildable voxel model of its main subject on an integer grid. "
        "Coordinates are integers with x right, y depth (the subject's front "
        f"faces -y), z up, each from 0 to {grid_size - 1}. The model must be "
        "one connected solid volume: fill interiors, do not leave floating "
        "voxels, and keep the model standing on the z=0 ground plane. "
        "Use the real colors of the subject from the image. "
        "Respond with only JSON of the form "
        '{"voxels": [[x, y, z, r, g, b], ...]} with r/g/b in 0-255.'
    )
    user_text = (
        f"Create a voxel model of the main subject of this image on a "
        f"{grid_size}x{grid_size}x{grid_size} grid. Capture the overall shape, "
        "proportions and colors so the voxel model is recognizable as the "
        "subject from every side. Return only the JSON object."
    )
    if prompt:
        user_text += f"\nAdditional instructions: {prompt}"

    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        },
    ]


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _strip_code_fences(text: str) -> str:
    match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    return match.group(1).strip() if match else text.strip()


def _voxel_from_values(values: List[Any]) -> Optional[Voxel]:
    if len(values) != 6:
        return None
    try:
        x, y, z, r, g, b = [int(round(float(v))) for v in values]
    except (TypeError, ValueError):
        return None
    if not all(0 <= channel <= 255 for channel in (r, g, b)):
        return None
    return {"x": x, "y": y, "z": z, "r": r, "g": g, "b": b}


def _voxels_from_json(parsed: Any) -> Optional[List[Voxel]]:
    if isinstance(parsed, dict):
        parsed = parsed.get("voxels")
    if not isinstance(parsed, list):
        return None

    voxels: List[Voxel] = []
    for entry in parsed:
        if isinstance(entry, dict):
            entry = [entry.get(key) for key in ("x", "y", "z", "r", "g", "b")]
        if not isinstance(entry, list):
            return None
        voxel = _voxel_from_values(entry)
        if voxel is not None:
            voxels.append(voxel)
    return voxels


def _voxels_from_lines(text: str) -> List[Voxel]:
    voxels: List[Voxel] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        voxel = _voxel_from_values(re.split(r"[\s,]+", line))
        if voxel is not None:
            voxels.append(voxel)
    return voxels


def parse_llm_voxel_output(text: str, grid_size: int = DEFAULT_GRID_SIZE) -> List[Voxel]:
    """Parse LLM output into voxels.

    Accepts a JSON object ``{"voxels": [[x,y,z,r,g,b], ...]}``, a bare JSON
    array (of arrays or of {x,y,z,r,g,b} objects), or plain xyzrgb lines,
    optionally wrapped in a markdown code fence. Voxels outside the grid are
    dropped and duplicate coordinates keep the first occurrence.
    """
    stripped = _strip_code_fences(text or "")
    voxels: Optional[List[Voxel]] = None
    try:
        voxels = _voxels_from_json(json.loads(stripped))
    except json.JSONDecodeError:
        match = re.search(r"[\{\[].*[\}\]]", stripped, re.DOTALL)
        if match:
            try:
                voxels = _voxels_from_json(json.loads(match.group(0)))
            except json.JSONDecodeError:
                voxels = None
    if voxels is None:
        voxels = _voxels_from_lines(stripped)

    seen: set = set()
    result: List[Voxel] = []
    for voxel in voxels:
        key = (voxel["x"], voxel["y"], voxel["z"])
        if key in seen:
            continue
        if not all(0 <= voxel[axis] < grid_size for axis in ("x", "y", "z")):
            continue
        seen.add(key)
        result.append(voxel)

    if not result:
        raise ValueError("LLM output contained no valid voxels")
    if len(result) > MAX_LLM_VOXELS:
        raise ValueError(f"LLM output has too many voxels. Maximum is {MAX_LLM_VOXELS}.")
    return result


def parse_xyzrgb(content: str) -> List[Voxel]:
    """Parse pipeline xyzrgb text (``x y z r g b`` per line) into voxels."""
    voxels = _voxels_from_lines(content)
    if not voxels:
        raise ValueError("xyzrgb content contains no voxels")
    return voxels


def serialize_xyzrgb(voxels: List[Voxel]) -> str:
    return "\n".join(
        f"{v['x']} {v['y']} {v['z']} {v['r']} {v['g']} {v['b']}" for v in voxels
    )


# ---------------------------------------------------------------------------
# Gap filling
# ---------------------------------------------------------------------------


def _to_grids(voxels: List[Voxel]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    coords = np.array([(v["x"], v["y"], v["z"]) for v in voxels], dtype=np.int64)
    colors = np.array([(v["r"], v["g"], v["b"]) for v in voxels], dtype=np.int64)
    origin = coords.min(axis=0)
    shifted = coords - origin
    shape = tuple(shifted.max(axis=0) + 1)
    occupancy = np.zeros(shape, dtype=bool)
    color_grid = np.zeros(shape + (3,), dtype=np.int64)
    occupancy[tuple(shifted.T)] = True
    color_grid[tuple(shifted.T)] = colors
    return occupancy, color_grid, origin


def _grids_to_voxels(
    occupancy: np.ndarray, color_grid: np.ndarray, origin: np.ndarray
) -> List[Voxel]:
    coords = np.argwhere(occupancy)
    colors = color_grid[occupancy]
    return [
        {
            "x": int(x + origin[0]),
            "y": int(y + origin[1]),
            "z": int(z + origin[2]),
            "r": int(r),
            "g": int(g),
            "b": int(b),
        }
        for (x, y, z), (r, g, b) in zip(coords, colors)
    ]


def fill_gaps(voxels: List[Voxel]) -> List[Voxel]:
    """Algorithmically fill gaps in an LLM-generated voxel model.

    Closes fully enclosed cavities and one-voxel-wide surface holes (binary
    closing), which LLMs commonly leave behind. New voxels take the color of
    the nearest original voxel. Original voxels are never removed or
    recolored.
    """
    if not voxels:
        return voxels

    occupancy, color_grid, origin = _to_grids(voxels)

    closed = ndimage.binary_closing(np.pad(occupancy, 1), iterations=1)[
        (slice(1, -1),) * 3
    ]
    filled = ndimage.binary_fill_holes(occupancy | closed)

    added = filled & ~occupancy
    if added.any():
        original_coords = np.argwhere(occupancy)
        tree = cKDTree(original_coords)
        added_coords = np.argwhere(added)
        _, nearest = tree.query(added_coords)
        color_grid[tuple(added_coords.T)] = color_grid[
            tuple(original_coords[nearest].T)
        ]

    return _grids_to_voxels(filled, color_grid, origin)


# ---------------------------------------------------------------------------
# Comparison with the image-to-3d voxel pipeline
# ---------------------------------------------------------------------------


def _normalized_occupancy(voxels: List[Voxel], grid_size: int) -> np.ndarray:
    """Resample a voxel model into a shared ``grid_size`` cube.

    The model is translated to the origin and uniformly scaled so its longest
    side spans the grid, making models produced at different resolutions
    comparable.
    """
    coords = np.array([(v["x"], v["y"], v["z"]) for v in voxels], dtype=np.float64)
    coords -= coords.min(axis=0)
    extent = coords.max()
    scale = (grid_size - 1) / extent if extent > 0 else 1.0
    scaled = np.round(coords * scale).astype(np.int64)
    occupancy = np.zeros((grid_size,) * 3, dtype=bool)
    occupancy[tuple(scaled.T)] = True
    if scale > 1.0:
        # Upsampling leaves regular gaps between voxels; close them so the
        # occupancy stays solid.
        occupancy = ndimage.binary_closing(
            np.pad(occupancy, 1), structure=np.ones((3, 3, 3), dtype=bool)
        )[(slice(1, -1),) * 3]
    return occupancy


def _silhouette_iou(a: np.ndarray, b: np.ndarray, axis: int) -> float:
    sil_a = a.any(axis=axis)
    sil_b = b.any(axis=axis)
    union = np.logical_or(sil_a, sil_b).sum()
    if union == 0:
        return 0.0
    return float(np.logical_and(sil_a, sil_b).sum() / union)


def _connected_component_count(voxels: List[Voxel]) -> int:
    occupancy, _, _ = _to_grids(voxels)
    _, count = ndimage.label(occupancy)
    return int(count)


def describe_voxels(voxels: List[Voxel]) -> Dict[str, Any]:
    """Standalone structural stats for one voxel model."""
    coords = np.array([(v["x"], v["y"], v["z"]) for v in voxels], dtype=np.int64)
    dims = coords.max(axis=0) - coords.min(axis=0) + 1
    return {
        "voxel_count": len(voxels),
        "bounding_box": [int(d) for d in dims],
        "connected_components": _connected_component_count(voxels),
    }


def compare_voxel_models(
    candidate: List[Voxel],
    baseline: List[Voxel],
    grid_size: int = DEFAULT_GRID_SIZE,
) -> Dict[str, Any]:
    """Compare an LLM-generated voxel model against a pipeline baseline.

    Both models are normalized into a shared cube before comparison, so an
    LLM working on a 32-grid can be scored against a higher-resolution
    pipeline output. Returns occupancy IoU, per-view silhouette IoU (front,
    side, top) and structural stats for both models.
    """
    occ_candidate = _normalized_occupancy(candidate, grid_size)
    occ_baseline = _normalized_occupancy(baseline, grid_size)

    union = np.logical_or(occ_candidate, occ_baseline).sum()
    intersection = np.logical_and(occ_candidate, occ_baseline).sum()

    return {
        "occupancy_iou": float(intersection / union) if union else 0.0,
        "silhouette_iou": {
            # Axis indices follow (x, y, z): collapsing y gives the front
            # view, x the side view and z the top view.
            "front": _silhouette_iou(occ_candidate, occ_baseline, axis=1),
            "side": _silhouette_iou(occ_candidate, occ_baseline, axis=0),
            "top": _silhouette_iou(occ_candidate, occ_baseline, axis=2),
        },
        "candidate": describe_voxels(candidate),
        "baseline": describe_voxels(baseline),
    }
