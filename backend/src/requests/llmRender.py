import base64
import heapq
import json
import logging
import math
import os
import re
from collections import defaultdict
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import httpx
import numpy as np
from fastapi import HTTPException
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, validator
from scipy import ndimage
from skimage.segmentation import watershed

from ..utils.posthog_client import track_api_call, track_error

logger = logging.getLogger(__name__)

MAX_XYZRGB_BYTES = 8 * 1024 * 1024
MAX_VOXELS = 350_000
MAX_GRID_CELLS = 60_000_000
DEFAULT_MODEL = os.getenv("OPENAI_LLM_RENDER_MODEL", "gpt-5.6-sol")
DEFAULT_REASONING_EFFORT = os.getenv("OPENAI_LLM_RENDER_REASONING_EFFORT", "medium")
OPENAI_TIMEOUT_SECONDS = float(os.getenv("OPENAI_LLM_RENDER_TIMEOUT_SECONDS", "240"))

DEFAULT_MAX_SEGMENTS = 16
MAX_SEGMENTS_LIMIT = 24
MAX_GEOMETRY_EDITS = 512
MAX_GEOMETRY_EDIT_FRACTION = 0.1
COLOR_CLUSTERS = 10
# Ceiling for extra clusters spent on small, distinct detail colours.
MAX_COLOR_CLUSTERS = 24
# Segments smaller than this share of the model are merged into a neighbour...
MIN_SEGMENT_FRACTION = 0.005
# ...unless they are details: at least DETAIL_CONTRAST away from every
# neighbour (eyes, mouth, buttons, logos), made of islands of at least
# MIN_DETAIL_ISLAND_VOXELS (lone voxels are texture noise), and at least
# MIN_DETAIL_VOXELS in total once same-coloured islands are grouped.
MIN_DETAIL_ISLAND_VOXELS = 2
MIN_DETAIL_VOXELS = 3
DETAIL_CONTRAST = 25.0
# Extra cost charged in phase 2 for merging a detail away, so under budget
# pressure details are sacrificed after shading and geometry splits.
DETAIL_MERGE_PENALTY = 30.0
# Segments below this share of the model are reported to the LLM as details.
DETAIL_SHARE = 0.01
PREVIEW_TILE_SIZE = 320
# Segments covering fewer pixels than this in a view get their label drawn
# beside them with a leader line instead of on top of them.
LABEL_OFFSET_AREA = 900

# Colour comparisons happen in CIELAB with lightness down-weighted, so the lit
# and shadowed sides of one part read as similar while real hue changes do not.
LIGHTNESS_WEIGHT = 0.5
# Weighted-Lab distance at which two colours stop counting as "the same part".
COLOR_TOLERANCE = 15.0
# Geometric splitting: a part needs a core at least this many voxels from the
# surface to seed its own region (distance-transform units).
MIN_PART_THICKNESS = 1.5
# Two adjacent regions merge back together when the join between them is at
# least this fraction as thick as the thinner region (no real neck)...
NECK_RATIO = 0.7
# ...and the thinner region is at least this fraction as thick as the thicker
# one (a thin limb on a thick body stays separate even without a neck).
THICKNESS_RATIO = 0.6
# Extra colour distance charged when merging components from different
# geometric regions, so same-coloured parts are the last thing to be merged.
GEOMETRY_SPLIT_PENALTY = 30.0

# Distinct ID colors used only to label segments in the preview sent to the LLM.
SEGMENT_PALETTE: List[Tuple[int, int, int]] = [
    (230, 25, 75), (60, 180, 75), (255, 225, 25), (0, 130, 200),
    (245, 130, 48), (145, 30, 180), (70, 240, 240), (240, 50, 230),
    (210, 245, 60), (250, 190, 212), (0, 128, 128), (220, 190, 255),
    (170, 110, 40), (255, 250, 200), (128, 0, 0), (170, 255, 195),
    (128, 128, 0), (255, 215, 180), (0, 0, 128), (128, 128, 128),
    (255, 105, 180), (0, 200, 120), (180, 60, 0), (90, 90, 255),
]

# Camera placements. The brick pipeline is Z-up and rotates the Y-up GLB +90 deg
# about X, so the GLB front (+Z) ends up facing -Y. Each view is defined by
# (horizontal axis, flip horizontal, vertical axis, depth axis, depth sign).
VIEWS: List[Dict[str, Any]] = [
    {"name": "front", "camera": "-Y", "h": "x", "flip_h": False, "v": "z", "d": "y", "d_sign": -1},
    {"name": "back", "camera": "+Y", "h": "x", "flip_h": True, "v": "z", "d": "y", "d_sign": 1},
    {"name": "left side", "camera": "+X", "h": "y", "flip_h": False, "v": "z", "d": "x", "d_sign": 1},
    {"name": "top", "camera": "+Z", "h": "x", "flip_h": False, "v": "y", "d": "z", "d_sign": 1},
]
AXIS_INDEX = {"x": 0, "y": 1, "z": 2}


class LlmRenderRequest(BaseModel):
    xyzrgb_url: str
    reference_image_url: str
    prompt: Optional[str] = None
    model: Optional[str] = None
    max_segments: Optional[int] = DEFAULT_MAX_SEGMENTS
    include_preview: bool = False

    @validator("xyzrgb_url", "reference_image_url")
    def validate_url(cls, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise ValueError("URL is required")
        if not value.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return value

    @validator("prompt")
    def validate_prompt(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if len(value) > 1000:
            raise ValueError("prompt must be 1000 characters or less")
        return value or None

    @validator("model")
    def validate_model(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        return value or None

    @validator("max_segments")
    def validate_max_segments(cls, value: Optional[int]) -> int:
        if value is None:
            return DEFAULT_MAX_SEGMENTS
        if value < 2 or value > MAX_SEGMENTS_LIMIT:
            raise ValueError(f"max_segments must be between 2 and {MAX_SEGMENTS_LIMIT}")
        return value


class LlmRenderResponse(BaseModel):
    xyzrgb_content: str
    voxel_count: int
    segment_count: int
    model: str
    applied_rules: List[Dict[str, Any]]
    geometry_changes: Dict[str, int]
    preview_image: Optional[str] = None
    message: str = "Successfully updated xyzrgb"


async def _fetch_text_url(url: str, max_bytes: int) -> str:
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to fetch xyzrgb_url: HTTP {e.response.status_code}",
        )
    except httpx.HTTPError as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch xyzrgb_url: {e}")

    content = response.content
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"xyzrgb file is too large. Maximum size is {max_bytes} bytes.",
        )

    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="xyzrgb_url did not return UTF-8 text")


def _parse_xyzrgb(content: str) -> List[Dict[str, int]]:
    voxels: List[Dict[str, int]] = []
    for line_number, line in enumerate(content.splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        parts = re.split(r"[\s,]+", line)
        if len(parts) != 6:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid xyzrgb row at line {line_number}: expected 6 columns",
            )

        try:
            x, y, z, r, g, b = [int(float(part)) for part in parts]
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid xyzrgb row at line {line_number}: values must be numeric",
            )

        if not all(0 <= channel <= 255 for channel in (r, g, b)):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid RGB value at line {line_number}: expected 0-255",
            )

        voxels.append({"x": x, "y": y, "z": z, "r": r, "g": g, "b": b})

    if not voxels:
        raise HTTPException(status_code=400, detail="xyzrgb file contains no voxels")
    if len(voxels) > MAX_VOXELS:
        raise HTTPException(
            status_code=413,
            detail=f"xyzrgb file has too many voxels. Maximum is {MAX_VOXELS}.",
        )
    return voxels


def _voxel_arrays(voxels: List[Dict[str, int]]) -> Tuple[np.ndarray, np.ndarray]:
    coords = np.array([(v["x"], v["y"], v["z"]) for v in voxels], dtype=np.int64)
    colors = np.array([(v["r"], v["g"], v["b"]) for v in voxels], dtype=np.float32)
    return coords, colors


# ---------------------------------------------------------------------------
# Segmentation
#
# The existing voxel colors are usually wrong in hue but right in *structure*:
# neighbouring voxels with similar colors almost always belong to the same
# semantic part. We exploit that to pre-split the model into a small number of
# contiguous segments, and then ask the LLM to label each segment rather than
# guess coordinates.
#
# Colour alone fails when adjacent parts share a colour (hat on hair, arm on
# torso), so the model is also split geometrically: a distance-transform
# watershed finds thick "cores" and the thin necks between them. Components
# are the intersection of colour regions and geometric regions, and the
# merging phases prefer to merge across shading before merging across a neck.
# ---------------------------------------------------------------------------


def _rgb_to_lab(colors: np.ndarray) -> np.ndarray:
    """sRGB (0-255) -> CIELAB (D65)."""
    srgb = np.clip(colors.astype(np.float64) / 255.0, 0.0, 1.0)
    linear = np.where(srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4)
    matrix = np.array(
        [
            [0.4124564, 0.3575761, 0.1804375],
            [0.2126729, 0.7151522, 0.0721750],
            [0.0193339, 0.1191920, 0.9503041],
        ]
    )
    xyz = linear @ matrix.T / np.array([0.95047, 1.0, 1.08883])
    epsilon, kappa = 216.0 / 24389.0, 24389.0 / 27.0
    f = np.where(xyz > epsilon, np.cbrt(xyz), (kappa * xyz + 16.0) / 116.0)
    lab = np.empty_like(f)
    lab[:, 0] = 116.0 * f[:, 1] - 16.0
    lab[:, 1] = 500.0 * (f[:, 0] - f[:, 1])
    lab[:, 2] = 200.0 * (f[:, 1] - f[:, 2])
    return lab


def _perceptual_colors(colors: np.ndarray) -> np.ndarray:
    """Colour features used for clustering and merging: Lab with L scaled down."""
    lab = _rgb_to_lab(colors)
    lab[:, 0] *= LIGHTNESS_WEIGHT
    return lab.astype(np.float32)


def _grid_geometry(coords: np.ndarray) -> Tuple[np.ndarray, Tuple[int, ...]]:
    origin = coords.min(0)
    shape = tuple(int(s) for s in (coords.max(0) - origin + 1))
    if int(np.prod(shape)) > MAX_GRID_CELLS:
        raise HTTPException(
            status_code=413,
            detail=f"Voxel bounding box is too large ({shape}); cannot segment.",
        )
    return origin, shape


def _basin_saddles(basins: np.ndarray, thickness: np.ndarray) -> Dict[Tuple[int, int], float]:
    """For each pair of touching basins, the thickness of the thickest point on
    their shared boundary (the 'saddle')."""
    saddles: Dict[Tuple[int, int], float] = {}
    stride = int(basins.max()) + 1
    for axis in range(3):
        rolled_b = np.moveaxis(basins, axis, 0)
        rolled_t = np.moveaxis(thickness, axis, 0)
        a = rolled_b[:-1].reshape(-1)
        b = rolled_b[1:].reshape(-1)
        mask = (a > 0) & (b > 0) & (a != b)
        if not mask.any():
            continue
        depth = np.minimum(rolled_t[:-1].reshape(-1)[mask], rolled_t[1:].reshape(-1)[mask])
        keys = np.minimum(a[mask], b[mask]).astype(np.int64) * stride + np.maximum(a[mask], b[mask])
        unique_keys, inverse = np.unique(keys, return_inverse=True)
        best = np.zeros(len(unique_keys), dtype=np.float64)
        np.maximum.at(best, inverse.reshape(-1), depth)
        for key, value in zip(unique_keys.tolist(), best.tolist()):
            pair = divmod(key, stride)
            saddles[pair] = max(saddles.get(pair, 0.0), value)
    return saddles


def _merge_shallow_basins(basins: np.ndarray, thickness: np.ndarray) -> np.ndarray:
    """Undo watershed over-segmentation: repeatedly merge the pair of touching
    basins with the weakest neck, as long as they are of similar thickness."""
    count = int(basins.max())
    if count < 2:
        return basins
    peak = {
        index + 1: float(value)
        for index, value in enumerate(ndimage.maximum(thickness, basins, index=np.arange(1, count + 1)))
    }
    saddles = _basin_saddles(basins, thickness)
    parent = np.arange(count + 1)

    while True:
        best_pair, best_score = None, 0.0
        for (a, b), saddle in saddles.items():
            thin, thick = sorted((peak[a], peak[b]))
            if thin <= 0 or saddle < NECK_RATIO * thin or thin < THICKNESS_RATIO * thick:
                continue
            score = saddle / thin
            if score > best_score:
                best_pair, best_score = (a, b), score
        if best_pair is None:
            break

        keep, drop = best_pair
        parent[drop] = keep
        peak[keep] = max(peak[keep], peak.pop(drop))
        merged: Dict[Tuple[int, int], float] = {}
        for (p, q), saddle in saddles.items():
            p, q = (keep if p == drop else p), (keep if q == drop else q)
            if p == q:
                continue
            pair = (min(p, q), max(p, q))
            merged[pair] = max(merged.get(pair, 0.0), saddle)
        saddles = merged

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return int(i)

    roots = np.array([find(i) for i in range(count + 1)])
    return roots[basins]


def _geometric_regions(coords: np.ndarray) -> np.ndarray:
    """Split the solid into thick 'core' regions separated by necks, using a
    watershed on the distance-to-surface field. Returns a 0-based region label
    per voxel."""
    origin, shape = _grid_geometry(coords)
    local = coords - origin
    idx = (local[:, 0], local[:, 1], local[:, 2])
    occupancy = np.zeros(shape, dtype=bool)
    occupancy[idx] = True
    # Generated models are usually hollow shells; fill them so thickness means
    # the thickness of the part, not of the shell wall.
    solid = ndimage.binary_fill_holes(occupancy)

    # Pad so voxels on the bounding-box face are correctly treated as surface.
    thickness = ndimage.distance_transform_edt(np.pad(solid, 1))[1:-1, 1:-1, 1:-1].astype(np.float32)
    peaks = (thickness == ndimage.maximum_filter(thickness, size=3)) & (thickness >= MIN_PART_THICKNESS)
    markers, marker_count = ndimage.label(peaks, structure=ndimage.generate_binary_structure(3, 3))
    if marker_count == 0:
        return np.zeros(len(coords), dtype=np.int32)

    basins = watershed(-thickness, markers, mask=solid, connectivity=1).astype(np.int32)

    # Thin pieces with no core of their own (antennae, tails) become regions too.
    unreached = solid & (basins == 0)
    if unreached.any():
        extra, _ = ndimage.label(unreached, structure=ndimage.generate_binary_structure(3, 1))
        basins[unreached] = extra[unreached] + marker_count

    basins = _merge_shallow_basins(basins, thickness)
    return np.unique(basins[idx], return_inverse=True)[1].reshape(-1).astype(np.int32)


def _two_means(points: np.ndarray, weights: np.ndarray, iterations: int = 10) -> Optional[np.ndarray]:
    """Deterministic weighted 2-means. Initialised by splitting along the principal
    axis at the weighted mean, which avoids seeding a cluster on a lone outlier.
    Returns 0/1 labels, or None if the points cannot be split."""
    if len(points) < 2:
        return None
    points = points.astype(np.float64)
    weights = weights.astype(np.float64)
    mean = np.average(points, axis=0, weights=weights)
    centered = points - mean
    covariance = (centered * weights[:, None]).T @ centered
    principal_axis = np.linalg.eigh(covariance)[1][:, -1]
    projection = centered @ principal_axis
    labels = (projection > 0).astype(np.int32)
    if labels.min() == labels.max():
        return None

    centers = np.stack(
        [np.average(points[labels == k], axis=0, weights=weights[labels == k]) for k in (0, 1)]
    )
    for _ in range(iterations):
        distances = ((points[:, None, :] - centers[None, :, :]) ** 2).sum(2)
        new_labels = distances.argmin(1).astype(np.int32)
        if new_labels.min() == new_labels.max():
            break
        if np.array_equal(new_labels, labels):
            break
        labels = new_labels
        for k in (0, 1):
            members = labels == k
            centers[k] = np.average(points[members], axis=0, weights=weights[members])
    return labels


def _split_off_outliers(
    points: np.ndarray, weights: np.ndarray, center: np.ndarray, iterations: int = 10
) -> Optional[np.ndarray]:
    """2-means seeded with the cluster centre and its farthest member, so a small
    group of distinct colours is split off even when it carries little weight.
    Returns 0/1 labels, or None if the points cannot be split."""
    points = points.astype(np.float64)
    weights = weights.astype(np.float64)
    farthest = np.linalg.norm(points - center, axis=1).argmax()
    centers = np.stack([center.astype(np.float64), points[farthest]])
    labels: Optional[np.ndarray] = None
    for _ in range(iterations):
        distances = ((points[:, None, :] - centers[None, :, :]) ** 2).sum(2)
        new_labels = distances.argmin(1).astype(np.int32)
        if new_labels.min() == new_labels.max():
            return None
        if labels is not None and np.array_equal(new_labels, labels):
            break
        labels = new_labels
        for k in (0, 1):
            members = labels == k
            centers[k] = np.average(points[members], axis=0, weights=weights[members])
    return labels


def _quantize_colors(colors: np.ndarray, clusters: int) -> np.ndarray:
    """Bisecting k-means over colour features (see _perceptual_colors), weighted
    by how many voxels share each colour. Always splits the cluster with the most
    variance, so clusters are spent on real colour regions rather than isolated
    outlier voxels. A second pass then gives small groups of distinct colours
    (eyes, buttons, logos) their own clusters even though they carry too little
    weight to win a variance-based split."""
    unique_colors, inverse, counts = np.unique(
        colors, axis=0, return_inverse=True, return_counts=True
    )
    inverse = inverse.reshape(-1)
    counts = counts.astype(np.float64)
    labels = np.zeros(len(unique_colors), dtype=np.int32)
    cluster_count = 1

    def cluster_center(members: np.ndarray) -> np.ndarray:
        return np.average(unique_colors[members], axis=0, weights=counts[members])

    def apply_split(members: np.ndarray, split: np.ndarray) -> None:
        nonlocal cluster_count
        labels[members[split == 1]] = cluster_count
        cluster_count += 1

    while cluster_count < min(clusters, len(unique_colors)):
        best_cluster, best_sse = -1, 0.0
        for cluster in range(cluster_count):
            members = np.nonzero(labels == cluster)[0]
            if len(members) < 2:
                continue
            center = cluster_center(members)
            sse = float((counts[members] * ((unique_colors[members] - center) ** 2).sum(1)).sum())
            if sse > best_sse:
                best_cluster, best_sse = cluster, sse
        if best_cluster < 0:
            break
        members = np.nonzero(labels == best_cluster)[0]
        split = _two_means(unique_colors[members], counts[members])
        if split is None:
            break
        apply_split(members, split)

    while cluster_count < min(MAX_COLOR_CLUSTERS, len(unique_colors)):
        best_cluster, best_outliers = -1, 0.0
        for cluster in range(cluster_count):
            members = np.nonzero(labels == cluster)[0]
            if len(members) < 2:
                continue
            center = cluster_center(members)
            far = np.linalg.norm(unique_colors[members] - center, axis=1) > DETAIL_CONTRAST
            outliers = float(counts[members][far].sum())
            if outliers >= MIN_DETAIL_VOXELS and outliers > best_outliers:
                best_cluster, best_outliers = cluster, outliers
        if best_cluster < 0:
            break
        members = np.nonzero(labels == best_cluster)[0]
        split = _split_off_outliers(unique_colors[members], counts[members], cluster_center(members))
        if split is None:
            break
        apply_split(members, split)

    return labels[inverse]


def _connected_components(
    coords: np.ndarray, labels: np.ndarray
) -> Tuple[np.ndarray, int, np.ndarray]:
    """26-connected components of voxels that share a label. Full connectivity
    matters because generated models are shells: neighbouring surface voxels on a
    curved part frequently touch only along an edge or corner."""
    origin, shape = _grid_geometry(coords)

    local = coords - origin
    idx = (local[:, 0], local[:, 1], local[:, 2])
    component = np.zeros(len(coords), dtype=np.int32)
    structure = ndimage.generate_binary_structure(3, 3)
    next_id = 0
    for label in np.unique(labels):
        members = labels == label
        mask = np.zeros(shape, dtype=bool)
        mask[idx[0][members], idx[1][members], idx[2][members]] = True
        labeled, count = ndimage.label(mask, structure=structure)
        component[members] = labeled[idx[0][members], idx[1][members], idx[2][members]] - 1 + next_id
        next_id += int(count)

    grid = np.full(shape, -1, dtype=np.int32)
    grid[idx] = component
    return component, next_id, grid


def _component_adjacency(grid: np.ndarray) -> Dict[int, Dict[int, int]]:
    """Number of shared faces between each pair of adjacent components."""
    adjacency: Dict[int, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for axis in range(3):
        rolled = np.moveaxis(grid, axis, 0)
        a = rolled[:-1].reshape(-1)
        b = rolled[1:].reshape(-1)
        mask = (a >= 0) & (b >= 0) & (a != b)
        if not mask.any():
            continue
        pairs = np.stack([np.minimum(a[mask], b[mask]), np.maximum(a[mask], b[mask])], axis=1)
        unique_pairs, counts = np.unique(pairs, axis=0, return_counts=True)
        for (p, q), count in zip(unique_pairs.tolist(), counts.tolist()):
            adjacency[p][q] += count
            adjacency[q][p] += count
    return adjacency


def _merge_components(
    component: np.ndarray,
    component_count: int,
    colors: np.ndarray,
    regions: np.ndarray,
    adjacency: Dict[int, Dict[int, int]],
    max_segments: int,
    min_size: int,
) -> np.ndarray:
    """Merge components in two phases and return 1-based segment ids ordered by
    descending size.

    `colors` are per-voxel perceptual colour features and `regions` is the
    geometric region of each component. Merging two components from different
    regions costs GEOMETRY_SPLIT_PENALTY on top of their colour distance.

    Phase 1 absorbs speckle: every component smaller than min_size joins the
    neighbour it shares the most boundary with (favouring similar colours), except
    details: small components that contrast strongly with every neighbour are kept.
    Detail components of near-identical colour are then grouped into one segment
    (both eyes, all buttons) so they share a single slot in the budget.
    Phase 2 enforces max_segments by repeatedly merging the *most similar* pair of
    adjacent components, so the budget is spent on genuinely different-coloured
    parts (eyes, cheeks, trim) rather than on shading variations of one part.
    """
    sizes = np.bincount(component, minlength=component_count).astype(np.int64)
    color_sums = np.zeros((component_count, 3), dtype=np.float64)
    np.add.at(color_sums, component, colors)
    region_of = regions.astype(np.int64).copy()
    parent = np.arange(component_count)
    alive = set(range(component_count))
    version = [0] * component_count
    protected: set = set()
    def mean_color(cid: int) -> np.ndarray:
        return color_sums[cid] / max(1, sizes[cid])

    def color_distance(a: int, b: int) -> float:
        return float(np.linalg.norm(mean_color(a) - mean_color(b)))

    def merge_cost(a: int, b: int) -> float:
        penalty = 0.0 if region_of[a] == region_of[b] else GEOMETRY_SPLIT_PENALTY
        if a in protected or b in protected:
            penalty += DETAIL_MERGE_PENALTY
        return color_distance(a, b) + penalty

    def nearest_by_color(cid: int) -> Optional[int]:
        candidates = [other for other in alive if other != cid]
        if not candidates:
            return None
        return min(candidates, key=lambda other: merge_cost(cid, other))

    def is_high_contrast(cid: int) -> bool:
        neighbours = [n for n in adjacency.get(cid, {}) if n in alive]
        return all(color_distance(cid, n) >= DETAIL_CONTRAST for n in neighbours)

    def merge(cid: int, target: int) -> None:
        parent[cid] = target
        alive.remove(cid)
        sizes[target] += sizes[cid]
        color_sums[target] += color_sums[cid]
        for neighbour, shared in adjacency.pop(cid, {}).items():
            if neighbour == target:
                continue
            adjacency[neighbour].pop(cid, None)
            adjacency[target][neighbour] += shared
            adjacency[neighbour][target] += shared
        adjacency[target].pop(cid, None)
        version[target] += 1

    # Details: small components that contrast strongly with everything they touch.
    # Same-coloured ones are grouped into one segment (both eyes, all buttons) so
    # they share a budget slot and so that tiny islands can add up to a detail
    # worth keeping. Groups too small to matter are left to speckle removal.
    candidates = sorted(
        (
            cid
            for cid in alive
            if MIN_DETAIL_ISLAND_VOXELS <= sizes[cid] < min_size and is_high_contrast(cid)
        ),
        key=lambda cid: -int(sizes[cid]),
    )
    groups: List[int] = []
    for cid in candidates:
        leader = next((g for g in groups if color_distance(cid, g) < COLOR_TOLERANCE), None)
        if leader is None:
            groups.append(cid)
        else:
            merge(cid, leader)
    protected.update(g for g in groups if sizes[g] >= MIN_DETAIL_VOXELS)

    # Phase 1: speckle removal.
    size_heap = [(int(sizes[i]), i) for i in alive]
    heapq.heapify(size_heap)
    while size_heap and len(alive) > 1:
        size, cid = heapq.heappop(size_heap)
        if cid not in alive or sizes[cid] != size:
            continue
        if size >= min_size:
            break
        if cid in protected:
            continue
        best, best_score = None, -1.0
        for neighbour, shared in adjacency.get(cid, {}).items():
            if neighbour not in alive:
                continue
            score = shared / (1.0 + merge_cost(cid, neighbour) / COLOR_TOLERANCE)
            if score > best_score:
                best, best_score = neighbour, score
        target = best if best is not None else nearest_by_color(cid)
        if target is None:
            break
        merge(cid, target)
        if target not in protected:
            heapq.heappush(size_heap, (int(sizes[target]), target))

    # Phase 2: enforce the segment cap by merging the most similar adjacent pair.
    pair_heap: List[Tuple[float, int, int, int, int]] = []
    for a in alive:
        for b in adjacency.get(a, {}):
            if a < b and b in alive:
                pair_heap.append((merge_cost(a, b), version[a], version[b], a, b))
    heapq.heapify(pair_heap)
    while len(alive) > max_segments and pair_heap:
        _, version_a, version_b, a, b = heapq.heappop(pair_heap)
        if a not in alive or b not in alive or version[a] != version_a or version[b] != version_b:
            continue
        target, cid = (a, b) if sizes[a] >= sizes[b] else (b, a)
        merge(cid, target)
        for neighbour in adjacency.get(target, {}):
            if neighbour in alive:
                heapq.heappush(
                    pair_heap,
                    (merge_cost(target, neighbour), version[target], version[neighbour], target, neighbour),
                )

    # Anything still over the cap consists of disconnected islands; merge by colour.
    while len(alive) > max_segments:
        cid = min(alive, key=lambda c: int(sizes[c]))
        target = nearest_by_color(cid)
        if target is None:
            break
        merge(cid, target)

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return int(i)

    roots = np.array([find(i) for i in range(component_count)])
    root_of_voxel = roots[component]
    ordered_roots = sorted(alive, key=lambda cid: -int(sizes[cid]))
    remap = {root: index + 1 for index, root in enumerate(ordered_roots)}
    return np.vectorize(remap.__getitem__)(root_of_voxel).astype(np.int32)


def _segment_voxels(voxels: List[Dict[str, int]], max_segments: int) -> np.ndarray:
    coords, colors = _voxel_arrays(voxels)
    features = _perceptual_colors(colors)
    color_labels = _quantize_colors(features, COLOR_CLUSTERS)
    region_labels = _geometric_regions(coords)
    combined = color_labels.astype(np.int64) * (int(region_labels.max()) + 1) + region_labels
    component, count, grid = _connected_components(coords, combined)
    component_regions = np.zeros(count, dtype=np.int64)
    component_regions[component] = region_labels
    adjacency = _component_adjacency(grid)
    min_size = max(3, int(round(len(voxels) * MIN_SEGMENT_FRACTION)))
    return _merge_components(
        component, count, features, component_regions, adjacency, max_segments, min_size
    )


def _normalized(values: np.ndarray, low: int, high: int) -> np.ndarray:
    if high == low:
        return np.zeros(len(values), dtype=np.float64)
    return (values - low) / (high - low)


def _island_counts(coords: np.ndarray, segment_ids: np.ndarray) -> Dict[int, int]:
    """Number of disconnected pieces each segment consists of."""
    origin, shape = _grid_geometry(coords)
    local = coords - origin
    structure = ndimage.generate_binary_structure(3, 3)
    counts: Dict[int, int] = {}
    for segment_id in np.unique(segment_ids):
        members = local[segment_ids == segment_id]
        mask = np.zeros(shape, dtype=bool)
        mask[members[:, 0], members[:, 1], members[:, 2]] = True
        counts[int(segment_id)] = int(ndimage.label(mask, structure=structure)[1])
    return counts


def _build_scene_summary(
    voxels: List[Dict[str, int]], segment_ids: np.ndarray
) -> Dict[str, Any]:
    coords, _ = _voxel_arrays(voxels)
    low = coords.min(0)
    high = coords.max(0)
    islands = _island_counts(coords, segment_ids)
    detail_threshold = max(MIN_DETAIL_VOXELS, int(round(len(voxels) * DETAIL_SHARE)))
    segments = []
    for segment_id in np.unique(segment_ids):
        members = coords[segment_ids == segment_id]
        center = {}
        extent = {}
        for axis, index in AXIS_INDEX.items():
            normalized = _normalized(members[:, index], int(low[index]), int(high[index]))
            center[axis] = round(float(normalized.mean()), 2)
            extent[axis] = [round(float(normalized.min()), 2), round(float(normalized.max()), 2)]
        segments.append(
            {
                "id": int(segment_id),
                "voxel_count": int(len(members)),
                "share": round(len(members) / len(voxels), 3),
                "is_detail": bool(len(members) < detail_threshold),
                "island_count": islands[int(segment_id)],
                "center": center,
                "extent": extent,
            }
        )
    return {
        "axes": (
            "Z is up. X is the model's left-right axis, Y is depth. The model most "
            "likely faces -Y, so the 'front' view is usually the one that matches the "
            "reference photo; confirm this from the silhouette."
        ),
        "normalized_coordinates": "center/extent are 0..1 across the voxel bounds (0=min, 1=max)",
        "details": (
            "is_detail marks small, high-contrast features (eyes, mouth, buttons, logos, "
            "jewelry, patterns) that were deliberately kept as their own segments. "
            "island_count > 1 means the segment is several matching pieces sharing one "
            "colour, e.g. both eyes or all buttons; center/extent then span all pieces."
        ),
        "voxel_count": len(voxels),
        "dimensions": {axis: int(high[i] - low[i] + 1) for axis, i in AXIS_INDEX.items()},
        "bounds": {
            axis: [int(low[i]), int(high[i])] for axis, i in AXIS_INDEX.items()
        },
        "geometry_edit_budget": min(
            MAX_GEOMETRY_EDITS,
            max(1, math.ceil(len(voxels) * MAX_GEOMETRY_EDIT_FRACTION)),
        ),
        "segment_count": len(segments),
        "segments": segments,
    }


# ---------------------------------------------------------------------------
# Preview rendering
# ---------------------------------------------------------------------------


def _load_font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _project_segments(
    coords: np.ndarray, segment_ids: np.ndarray, view: Dict[str, Any]
) -> np.ndarray:
    """Return a 2D array (rows, cols) of segment ids for the visible voxel per pixel (0 = empty)."""
    low = coords.min(0)
    high = coords.max(0)
    h, v, d = AXIS_INDEX[view["h"]], AXIS_INDEX[view["v"]], AXIS_INDEX[view["d"]]
    width = int(high[h] - low[h] + 1)
    height = int(high[v] - low[v] + 1)

    px = coords[:, h] - low[h]
    if view["flip_h"]:
        px = (width - 1) - px
    py = high[v] - coords[:, v]
    depth = coords[:, d] * view["d_sign"]

    pixel_key = py * width + px
    order = np.lexsort((-depth, pixel_key))
    _, first = np.unique(pixel_key[order], return_index=True)
    visible = order[first]

    image = np.zeros((height, width), dtype=np.int32)
    image[py[visible], px[visible]] = segment_ids[visible]
    return image


def _render_view_tile(
    coords: np.ndarray,
    segment_ids: np.ndarray,
    view: Dict[str, Any],
    tile: int,
    font: ImageFont.ImageFont,
) -> Image.Image:
    projection = _project_segments(coords, segment_ids, view)
    height, width = projection.shape
    scale = max(1, min(tile // width, tile // height))

    palette = np.array([(255, 255, 255)] + SEGMENT_PALETTE, dtype=np.uint8)
    rgb = palette[np.clip(projection, 0, len(SEGMENT_PALETTE))]
    image = Image.fromarray(rgb, "RGB")
    if scale > 1:
        image = image.resize((width * scale, height * scale), Image.NEAREST)
    if image.width > tile or image.height > tile:
        ratio = min(tile / image.width, tile / image.height)
        image = image.resize(
            (max(1, int(image.width * ratio)), max(1, int(image.height * ratio))), Image.NEAREST
        )
        scale = ratio

    canvas = Image.new("RGB", (tile, tile), "white")
    offset = ((tile - image.width) // 2, (tile - image.height) // 2)
    canvas.paste(image, offset)
    draw = ImageDraw.Draw(canvas)

    tile_center = np.array([tile / 2.0, tile / 2.0])
    for segment_id in np.unique(projection):
        if segment_id == 0:
            continue
        rows, cols = np.nonzero(projection == segment_id)
        if len(rows) < 1:
            continue
        # Anchor the label on a visible pixel closest to the segment's centroid so
        # it lands on the segment even for concave shapes.
        centroid = np.array([rows.mean(), cols.mean()])
        nearest = np.argmin(((np.stack([rows, cols], 1) - centroid) ** 2).sum(1))
        ax = offset[0] + (cols[nearest] + 0.5) * scale
        ay = offset[1] + (rows[nearest] + 0.5) * scale
        text = str(int(segment_id))
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        text_width, text_height = right - left, bottom - top
        half_w, half_h = text_width / 2 + 3, text_height / 2 + 2

        cx, cy = ax, ay
        if len(rows) * scale * scale < LABEL_OFFSET_AREA:
            # Too small to label on top of: push the label outward from the tile
            # centre and connect it with a leader line so the feature stays visible.
            direction = np.array([ax, ay]) - tile_center
            norm = float(np.linalg.norm(direction))
            direction = direction / norm if norm > 1e-6 else np.array([0.0, -1.0])
            distance = float(max(half_w, half_h)) + 14.0
            cx = float(np.clip(ax + direction[0] * distance, half_w, tile - half_w))
            cy = float(np.clip(ay + direction[1] * distance, half_h, tile - half_h))
            draw.line([(ax, ay), (cx, cy)], fill=(0, 0, 0), width=1)

        box = [cx - half_w, cy - half_h, cx + half_w, cy + half_h]
        draw.rectangle(box, fill=(255, 255, 255), outline=(0, 0, 0))
        draw.text((box[0] + 3 - left, box[1] + 2 - top), text, fill=(0, 0, 0), font=font)

    return canvas


def _build_voxel_preview_data_url(
    voxels: List[Dict[str, int]], segment_ids: np.ndarray
) -> str:
    coords, _ = _voxel_arrays(voxels)
    tile = PREVIEW_TILE_SIZE
    title_height = 26
    gap = 10
    columns = 2
    rows = (len(VIEWS) + columns - 1) // columns
    label_font = _load_font(15)
    title_font = _load_font(16)

    width = columns * tile + (columns - 1) * gap
    unique_segments = [int(s) for s in np.unique(segment_ids)]
    swatch = 18
    legend_item_width = swatch + 30
    legend_per_row = max(1, (width - 8) // legend_item_width)
    legend_rows = (len(unique_segments) + legend_per_row - 1) // legend_per_row
    legend_height = 8 + legend_rows * (swatch + 8)

    composite = Image.new(
        "RGB",
        (width, rows * (tile + title_height) + (rows - 1) * gap + legend_height),
        "white",
    )
    draw = ImageDraw.Draw(composite)

    for index, view in enumerate(VIEWS):
        col, row = index % columns, index // columns
        x = col * (tile + gap)
        y = row * (tile + title_height + gap)
        draw.text((x + 4, y + 4), f"{view['name']} (camera at {view['camera']})", fill=(0, 0, 0), font=title_font)
        composite.paste(
            _render_view_tile(coords, segment_ids, view, tile, label_font), (x, y + title_height)
        )

    legend_top = composite.height - legend_height + 8
    for index, segment_id in enumerate(unique_segments):
        x = 4 + (index % legend_per_row) * legend_item_width
        y = legend_top + (index // legend_per_row) * (swatch + 8)
        color = SEGMENT_PALETTE[(segment_id - 1) % len(SEGMENT_PALETTE)]
        draw.rectangle([x, y, x + swatch, y + swatch], fill=color, outline=(0, 0, 0))
        draw.text((x + swatch + 3, y), str(segment_id), fill=(0, 0, 0), font=label_font)

    buffer = BytesIO()
    composite.save(buffer, format="PNG", optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


# ---------------------------------------------------------------------------
# OpenAI call
# ---------------------------------------------------------------------------


def _extract_response_text(response_json: Dict[str, Any]) -> str:
    if isinstance(response_json.get("output_text"), str):
        return response_json["output_text"]

    output_parts: List[str] = []
    for output in response_json.get("output", []):
        for content in output.get("content", []):
            text = content.get("text")
            if isinstance(text, str):
                output_parts.append(text)
    return "\n".join(output_parts).strip()


def _extract_json_object(text: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise HTTPException(status_code=502, detail="OpenAI response did not contain JSON")
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            raise HTTPException(status_code=502, detail="OpenAI response JSON was invalid")

    if not isinstance(parsed, dict):
        raise HTTPException(status_code=502, detail="OpenAI response JSON must be an object")
    return parsed


def _assignment_schema(segment_ids: List[int]) -> Dict[str, Any]:
    coordinate = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "x": {"type": "integer"},
            "y": {"type": "integer"},
            "z": {"type": "integer"},
        },
        "required": ["x", "y", "z"],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "subject": {"type": "string"},
            "assignments": {
                "type": "array",
                "minItems": len(segment_ids),
                "maxItems": len(segment_ids),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "segment_id": {"type": "integer", "enum": segment_ids},
                        "part": {"type": "string"},
                        "reason": {"type": "string"},
                        "color": {
                            "type": "array",
                            "minItems": 3,
                            "maxItems": 3,
                            "items": {"type": "integer", "minimum": 0, "maximum": 255},
                        },
                    },
                    "required": ["segment_id", "part", "reason", "color"],
                },
            },
            "geometry_edits": {
                "type": "array",
                "maxItems": MAX_GEOMETRY_EDITS,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "operation": {"type": "string", "enum": ["add", "remove"]},
                        "position": coordinate,
                        "color": {
                            "type": "array",
                            "minItems": 3,
                            "maxItems": 3,
                            "items": {"type": "integer", "minimum": 0, "maximum": 255},
                        },
                    },
                    "required": ["operation", "position", "color"],
                },
            },
        },
        "required": ["subject", "assignments", "geometry_edits"],
    }


async def _call_openai_for_assignments(
    scene_summary: Dict[str, Any],
    reference_image_url: str,
    voxel_preview_image_url: str,
    prompt: Optional[str],
    model: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY not configured. Set OPENAI_API_KEY and restart the backend server.",
        )

    segment_ids = [segment["id"] for segment in scene_summary["segments"]]

    system_prompt = (
        "You improve voxel models so they match a reference image. The model has been "
        "pre-split into numbered segments; your job is to decide which part of the "
        "reference object each segment is, give it that part's color, and make small "
        "voxel-level geometry corrections where the reference clearly supports them. "
        "The reference image is the ONLY source of colors. The colors in the voxel "
        "preview are arbitrary segment IDs, not real colors. "
        "Return only JSON."
    )
    user_prompt = {
        "task": (
            "Image 1 is the reference. Image 2 shows the voxel model from four cameras "
            "with every segment drawn in a flat ID color and labelled with its number "
            "(legend at the bottom). Steps: (1) identify the subject and its major "
            "colored parts in the reference image; (2) work out which preview view "
            "corresponds to the reference photo; (3) for every segment id, decide which "
            "part of the subject it is, using its position, size and shape; (4) assign "
            "it the real-world color of that part as seen in the reference image; "
            "(5) add or remove individual voxels only when needed to better match a "
            "clear shape feature in the reference."
        ),
        "rules": [
            "Return exactly one assignment for every segment id listed in scene_summary.segments.",
            "Segments belonging to the same part must receive the exact same color.",
            "Pick saturated, representative colors as they appear in the reference; do not average shadows into grey.",
            "If a segment cannot be identified, give it the color of the adjacent part it most likely belongs to.",
            "Small segments are usually details (eyes, buttons, logos, trim); look for matching details in the reference.",
            "Segments with is_detail=true are small high-contrast features (eyes, mouth, jewelry, buttons, logos, shirt patterns) that were kept on purpose; give them the colour of the matching detail in the reference, not the colour of the part they sit on.",
            "A segment with island_count > 1 is several matching pieces (e.g. both eyes, all buttons); colour it as that repeated feature.",
            "Use geometry_edits for conservative corrections such as moving misplaced facial details, filling small holes, or smoothing a jagged silhouette.",
            "To move a voxel, remove its old position and add its new position with the appropriate reference color.",
            "Keep edit positions within one voxel of scene_summary.bounds and do not exceed scene_summary.geometry_edit_budget.",
            "Return an empty geometry_edits array when the reference does not clearly justify a shape change.",
        ],
        "optional_user_prompt": prompt,
        "scene_summary": scene_summary,
    }

    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}],
            },
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": json.dumps(user_prompt)},
                    {"type": "input_image", "image_url": reference_image_url, "detail": "high"},
                    {"type": "input_image", "image_url": voxel_preview_image_url, "detail": "high"},
                ],
            },
        ],
        "reasoning": {"effort": DEFAULT_REASONING_EFFORT},
        "text": {
            "format": {
                "type": "json_schema",
                "name": "voxel_model_updates",
                "schema": _assignment_schema(segment_ids),
            }
        },
    }

    timeout = httpx.Timeout(OPENAI_TIMEOUT_SECONDS, connect=15.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.error("OpenAI llmRender request failed: %s", e.response.text)
        raise HTTPException(
            status_code=502,
            detail=f"OpenAI request failed: HTTP {e.response.status_code}",
        )
    except httpx.TimeoutException as e:
        logger.error(
            "OpenAI llmRender request timed out after %ss (%s)",
            OPENAI_TIMEOUT_SECONDS,
            type(e).__name__,
        )
        raise HTTPException(
            status_code=504,
            detail=(
                f"OpenAI request timed out after {OPENAI_TIMEOUT_SECONDS:.0f}s "
                f"(model={model}, reasoning={DEFAULT_REASONING_EFFORT}). "
                "Lower OPENAI_LLM_RENDER_REASONING_EFFORT or raise OPENAI_LLM_RENDER_TIMEOUT_SECONDS."
            ),
        )
    except httpx.HTTPError as e:
        # httpx transport errors often stringify to "", so include the type name.
        raise HTTPException(
            status_code=502,
            detail=f"OpenAI request failed: {type(e).__name__}: {e}".rstrip(": "),
        )

    response_json = response.json()
    if response_json.get("status") == "incomplete":
        reason = (response_json.get("incomplete_details") or {}).get("reason", "unknown")
        raise HTTPException(status_code=502, detail=f"OpenAI response was incomplete: {reason}")

    parsed = _extract_json_object(_extract_response_text(response_json))
    assignments = parsed.get("assignments", [])
    if not isinstance(assignments, list):
        raise HTTPException(status_code=502, detail="OpenAI assignments must be an array")
    geometry_edits = parsed.get("geometry_edits", [])
    if not isinstance(geometry_edits, list):
        raise HTTPException(status_code=502, detail="OpenAI geometry_edits must be an array")
    subject = parsed.get("subject") if isinstance(parsed.get("subject"), str) else ""
    return assignments, geometry_edits, subject


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


def _coerce_rgb(value: Any) -> Optional[Tuple[int, int, int]]:
    if not isinstance(value, list) or len(value) != 3:
        return None
    try:
        r, g, b = (max(0, min(255, int(channel))) for channel in value)
    except (TypeError, ValueError):
        return None
    return (r, g, b)


def _apply_assignments(
    voxels: List[Dict[str, int]],
    segment_ids: np.ndarray,
    assignments: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, int]], List[Dict[str, Any]]]:
    recolored = [voxel.copy() for voxel in voxels]
    applied: List[Dict[str, Any]] = []
    seen: set = set()

    for raw in assignments:
        if not isinstance(raw, dict):
            continue
        try:
            segment_id = int(raw.get("segment_id"))
        except (TypeError, ValueError):
            continue
        color = _coerce_rgb(raw.get("color"))
        if color is None or segment_id in seen:
            continue
        seen.add(segment_id)

        member_indices = np.nonzero(segment_ids == segment_id)[0]
        for index in member_indices.tolist():
            recolored[index]["r"], recolored[index]["g"], recolored[index]["b"] = color

        applied.append(
            {
                "segment_id": segment_id,
                "name": raw.get("part", f"segment {segment_id}"),
                "reason": raw.get("reason"),
                "color": list(color),
                "changed_voxels": int(len(member_indices)),
            }
        )

    return recolored, applied


def _apply_geometry_edits(
    voxels: List[Dict[str, int]],
    edits: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, int]], Dict[str, int]]:
    by_position = {
        (voxel["x"], voxel["y"], voxel["z"]): voxel.copy() for voxel in voxels
    }
    coordinates = np.array(list(by_position), dtype=np.int64)
    low = coordinates.min(axis=0) - 1
    high = coordinates.max(axis=0) + 1
    budget = min(
        MAX_GEOMETRY_EDITS,
        max(1, math.ceil(len(voxels) * MAX_GEOMETRY_EDIT_FRACTION)),
    )
    added = removed = 0

    for raw in edits[:budget]:
        if not isinstance(raw, dict) or raw.get("operation") not in ("add", "remove"):
            continue
        position = raw.get("position")
        if not isinstance(position, dict):
            continue
        values = [position.get(axis) for axis in AXIS_INDEX]
        if any(not isinstance(value, int) or isinstance(value, bool) for value in values):
            continue
        coordinate = tuple(values)
        if any(value < low[index] or value > high[index] for index, value in enumerate(coordinate)):
            continue

        if raw["operation"] == "remove":
            if by_position.pop(coordinate, None) is not None:
                removed += 1
            continue

        color = _coerce_rgb(raw.get("color"))
        if color is None or coordinate in by_position:
            continue
        by_position[coordinate] = {
            "x": coordinate[0],
            "y": coordinate[1],
            "z": coordinate[2],
            "r": color[0],
            "g": color[1],
            "b": color[2],
        }
        added += 1

    return list(by_position.values()), {"added": added, "removed": removed}


def _serialize_xyzrgb(voxels: List[Dict[str, int]]) -> str:
    return "\n".join(
        f"{v['x']} {v['y']} {v['z']} {v['r']} {v['g']} {v['b']}" for v in voxels
    ) + "\n"


async def llm_render(request: LlmRenderRequest, auth_info: dict) -> LlmRenderResponse:
    endpoint = "/llmRender"
    user_id = auth_info.get("user_email") or auth_info.get("user_id") or "anonymous"
    model = request.model or DEFAULT_MODEL
    max_segments = request.max_segments or DEFAULT_MAX_SEGMENTS

    try:
        xyzrgb_content = await _fetch_text_url(request.xyzrgb_url, MAX_XYZRGB_BYTES)
        voxels = _parse_xyzrgb(xyzrgb_content)
        segment_ids = _segment_voxels(voxels, max_segments)
        scene_summary = _build_scene_summary(voxels, segment_ids)
        voxel_preview_image_url = _build_voxel_preview_data_url(voxels, segment_ids)
        assignments, geometry_edits, subject = await _call_openai_for_assignments(
            scene_summary=scene_summary,
            reference_image_url=request.reference_image_url,
            voxel_preview_image_url=voxel_preview_image_url,
            prompt=request.prompt,
            model=model,
        )
        recolored, applied = _apply_assignments(voxels, segment_ids, assignments)
        updated_voxels, geometry_changes = _apply_geometry_edits(
            recolored, geometry_edits
        )

        segment_count = int(segment_ids.max())
        if len(applied) < segment_count:
            logger.warning(
                "llmRender: LLM returned %d assignments for %d segments",
                len(applied),
                segment_count,
            )

        track_api_call(
            endpoint=endpoint,
            user_id=user_id,
            success=True,
            model=model,
            voxel_count=len(updated_voxels),
            segment_count=segment_count,
            assignments_count=len(applied),
        )

        return LlmRenderResponse(
            xyzrgb_content=_serialize_xyzrgb(updated_voxels),
            voxel_count=len(updated_voxels),
            segment_count=segment_count,
            model=model,
            applied_rules=applied,
            geometry_changes=geometry_changes,
            preview_image=voxel_preview_image_url if request.include_preview else None,
            message=(
                f"Updated {len(applied)} of {segment_count} segment colors; "
                f"added {geometry_changes['added']} and removed "
                f"{geometry_changes['removed']} voxels"
            )
            + (f" as '{subject}'" if subject else ""),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("llmRender failed")
        track_error(
            error_type=type(e).__name__,
            error_message=str(e),
            endpoint=endpoint,
            user_id=user_id,
        )
        raise HTTPException(status_code=500, detail=f"llmRender failed: {e}")
