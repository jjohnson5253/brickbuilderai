"""
Experimental LLM-driven voxel segmentation and verification (issue #43).

The brick pipeline normally segments a model into a voxel grid
algorithmically (deterministic rank-remapping + downsampling in
``sam3d_stream``/``voxel_utils``).  This module lets a vision LLM either:

1. Perform the segmentation itself (``mode="llm"``): the LLM is shown the
   source image and asked to emit the voxel grid directly as XYZRGB text.
2. Check the algorithmic segmentation (``mode="check"``): orthographic
   projections of the algorithmic voxel grid are rendered and combined with
   the source image plus multiple bundled reference images into a single
   contact sheet, which the LLM reviews and grades.

Both modes are opt-in via the ``LLM_SEGMENTATION_MODE`` environment variable
(``off`` by default) and always fall back to the algorithmic result on any
failure, so the pipeline can never be degraded by the experiment.
"""

import os
import io
import json
import logging
import re
from typing import Optional

import numpy as np
import requests
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

# Vision LLM endpoint + default model used for both segmentation and checking
VISION_LLM_ENDPOINT = "fal-ai/any-llm/vision"
DEFAULT_LLM_MODEL = "google/gemini-flash-1.5"

# Minimum voxels an LLM segmentation must produce to be considered usable
MIN_LLM_VOXELS = 20

# Contact-sheet layout
_SHEET_CELL_SIZE = 256
_SHEET_LABEL_HEIGHT = 24

_SEGMENTATION_PROMPT = (
    "You are a voxelization engine. Look at the object in this image and "
    "reconstruct it as a 3D voxel model inside a {res}x{res}x{res} grid. "
    "Output ONLY voxel lines, one per line, in the exact format "
    "'x y z r g b' where x, y and z are integer grid coordinates in "
    "[0, {max_coord}] (z is up) and r, g and b are integer colors in "
    "[0, 255] sampled from the object. Fill the full visible shape of the "
    "object, not just its outline. Do not output any other text, "
    "explanation or markdown."
)

_CHECK_PROMPT = (
    "You are verifying the quality of a deterministic voxel segmentation "
    "used to build a LEGO-style brick model. The attached contact sheet "
    "contains labeled panels: the SOURCE image the model was built from, "
    "VOXEL projections (front/side/top orthographic views of the "
    "algorithmically segmented voxel grid), and REFERENCE images showing "
    "the expected voxelized art style. Compare the voxel projections "
    "against the source image and the reference style images. Check that "
    "the silhouette, proportions and dominant colors of the voxel "
    "segmentation match the source object, and that the blocky style is "
    "consistent with the references. Respond ONLY with a JSON object: "
    '{"passes": true|false, "score": <float 0.0-1.0>, '
    '"feedback": "<one or two sentences>"}'
)


def get_llm_segmentation_mode() -> str:
    """
    Return the configured LLM segmentation mode.

    Values:
        "off"   - (default) purely algorithmic segmentation
        "check" - algorithmic segmentation verified by the LLM
        "llm"   - LLM performs the segmentation (falls back to algorithmic)
    """
    mode = os.getenv("LLM_SEGMENTATION_MODE", "off").strip().lower()
    if mode not in ("off", "check", "llm"):
        logger.warning(f"Unknown LLM_SEGMENTATION_MODE '{mode}', using 'off'")
        return "off"
    return mode


def _get_llm_model() -> str:
    return os.getenv("LLM_SEGMENTATION_MODEL", DEFAULT_LLM_MODEL)


def _call_vision_llm(prompt: str, image_url: str) -> str:
    """Call the fal.ai vision LLM endpoint and return its text output."""
    import fal_client

    result = fal_client.subscribe(
        VISION_LLM_ENDPOINT,
        arguments={
            "model": _get_llm_model(),
            "prompt": prompt,
            "image_url": image_url,
        },
    )
    output = result.get("output") or result.get("text") or ""
    if not output:
        raise Exception(f"Empty response from vision LLM: {result}")
    return output


def parse_llm_xyzrgb(text: str, grid_resolution: int) -> str:
    """
    Parse LLM output into validated XYZRGB content.

    Accepts noisy output (markdown fences, prose) and keeps only lines that
    match the ``x y z r g b`` integer format with coordinates inside
    ``[0, grid_resolution)`` and colors inside ``[0, 255]``.  Duplicate
    positions keep their first occurrence.

    Raises:
        ValueError: if fewer than MIN_LLM_VOXELS valid voxels were produced.
    """
    line_re = re.compile(
        r"^\s*(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$"
    )
    seen: set[tuple[int, int, int]] = set()
    lines: list[str] = []
    for raw_line in text.splitlines():
        match = line_re.match(raw_line)
        if not match:
            continue
        x, y, z, r, g, b = (int(v) for v in match.groups())
        if not all(0 <= c < grid_resolution for c in (x, y, z)):
            continue
        if not all(0 <= c <= 255 for c in (r, g, b)):
            continue
        if (x, y, z) in seen:
            continue
        seen.add((x, y, z))
        lines.append(f"{x} {y} {z} {r} {g} {b}")

    if len(lines) < MIN_LLM_VOXELS:
        raise ValueError(
            f"LLM segmentation produced only {len(lines)} valid voxels "
            f"(minimum {MIN_LLM_VOXELS})"
        )
    return "\n".join(lines)


def parse_llm_verdict(text: str) -> dict:
    """
    Parse the LLM check response into a verdict dict.

    Returns a dict with keys ``passes`` (bool or None when unparseable),
    ``score`` (float or None) and ``feedback`` (str).
    """
    # Try to find a JSON object anywhere in the response
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group(0))
            return {
                "passes": bool(parsed["passes"]) if "passes" in parsed else None,
                "score": float(parsed["score"]) if "score" in parsed else None,
                "feedback": str(parsed.get("feedback", "")),
            }
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    # Keyword fallback
    lowered = text.lower()
    if "pass" in lowered and "fail" not in lowered:
        return {"passes": True, "score": None, "feedback": text.strip()}
    if "fail" in lowered:
        return {"passes": False, "score": None, "feedback": text.strip()}
    return {"passes": None, "score": None, "feedback": text.strip()}


def _load_xyzrgb(xyzrgb_content: str) -> tuple[np.ndarray, np.ndarray]:
    """Parse XYZRGB text into normalized integer coords and uint8 colors."""
    data = np.loadtxt(io.StringIO(xyzrgb_content))
    if data.ndim == 1:
        data = data.reshape(1, -1)
    coords = data[:, :3].astype(int)
    coords -= coords.min(axis=0)
    colors = np.clip(data[:, 3:6], 0, 255).astype(np.uint8)
    return coords, colors


def render_voxel_projections(xyzrgb_content: str, scale: int = 12) -> list[bytes]:
    """
    Render front/side/top orthographic projections of an XYZRGB voxel grid.

    For each view the voxel nearest the camera wins each pixel.  Returns a
    list of three PNG-encoded images (views along the Y, X and Z axes).
    """
    coords, colors = _load_xyzrgb(xyzrgb_content)

    # (depth_axis, horizontal_axis, vertical_axis, flip_depth)
    views = [
        (1, 0, 2, False),  # front: looking along +Y, x right, z up
        (0, 1, 2, False),  # side: looking along +X, y right, z up
        (2, 0, 1, True),   # top: looking along -Z (from above), x right, y "up"
    ]

    pngs: list[bytes] = []
    for depth_axis, h_axis, v_axis, flip_depth in views:
        width = int(coords[:, h_axis].max()) + 1
        height = int(coords[:, v_axis].max()) + 1

        canvas = np.full((height, width, 3), 255, dtype=np.uint8)
        best_depth = np.full((height, width), np.iinfo(np.int64).max, dtype=np.int64)

        depths = coords[:, depth_axis]
        if flip_depth:
            depths = depths.max() - depths
        for i in range(len(coords)):
            u = int(coords[i, h_axis])
            v = int(coords[i, v_axis])
            row = height - 1 - v  # image rows go top -> bottom
            if depths[i] < best_depth[row, u]:
                best_depth[row, u] = depths[i]
                canvas[row, u] = colors[i]

        image = Image.fromarray(canvas, mode="RGB")
        image = image.resize((width * scale, height * scale), Image.Resampling.NEAREST)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        pngs.append(buffer.getvalue())

    return pngs


def _load_bundled_reference_images() -> list[Image.Image]:
    """Load the bundled voxel-style reference images from src/images."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    images_dir = os.path.normpath(os.path.join(current_dir, "..", "images"))
    references: list[Image.Image] = []
    for name in ("references.png", "references-old.png"):
        path = os.path.join(images_dir, name)
        if os.path.exists(path):
            try:
                references.append(Image.open(path).convert("RGB"))
            except Exception as e:
                logger.warning(f"Failed to load reference image {path}: {e}")
    return references


def _download_image(url: str) -> Optional[Image.Image]:
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return Image.open(io.BytesIO(response.content)).convert("RGB")
    except Exception as e:
        logger.warning(f"Failed to download image for LLM check: {e}")
        return None


def build_check_sheet(panels: list[tuple[str, Image.Image]]) -> bytes:
    """
    Compose labeled image panels into a single PNG contact sheet.

    Combining every image into one sheet lets the vision LLM see the source
    image, the voxel projections and multiple reference images at once.
    """
    if not panels:
        raise ValueError("No panels to compose")

    columns = min(len(panels), 3)
    rows = (len(panels) + columns - 1) // columns
    cell = _SHEET_CELL_SIZE
    label_h = _SHEET_LABEL_HEIGHT

    sheet = Image.new(
        "RGB", (columns * cell, rows * (cell + label_h)), (255, 255, 255)
    )
    draw = ImageDraw.Draw(sheet)

    for index, (label, image) in enumerate(panels):
        col = index % columns
        row = index // columns
        x0 = col * cell
        y0 = row * (cell + label_h)

        draw.text((x0 + 4, y0 + 4), label, fill=(0, 0, 0))

        thumb = image.copy()
        thumb.thumbnail((cell, cell), Image.Resampling.LANCZOS)
        offset_x = x0 + (cell - thumb.width) // 2
        offset_y = y0 + label_h + (cell - thumb.height) // 2
        sheet.paste(thumb, (offset_x, offset_y))

    buffer = io.BytesIO()
    sheet.save(buffer, format="PNG")
    return buffer.getvalue()


def segment_voxels_with_llm(source_image_url: str, grid_resolution: int) -> str:
    """
    Have the vision LLM perform the voxel segmentation directly.

    Returns validated XYZRGB content produced by the LLM.

    Raises:
        Exception / ValueError: when the LLM call fails or its output does
        not contain enough valid voxels.
    """
    prompt = _SEGMENTATION_PROMPT.format(
        res=grid_resolution, max_coord=grid_resolution - 1
    )
    logger.info(
        f"Requesting LLM voxel segmentation (grid {grid_resolution}) "
        f"with model {_get_llm_model()}"
    )
    output = _call_vision_llm(prompt, source_image_url)
    xyzrgb_content = parse_llm_xyzrgb(output, grid_resolution)
    voxel_count = len(xyzrgb_content.splitlines())
    logger.info(f"LLM segmentation produced {voxel_count} voxels")
    return xyzrgb_content


def check_segmentation_with_llm(
    xyzrgb_content: str,
    source_image_url: Optional[str] = None,
) -> dict:
    """
    Have the vision LLM check the algorithmic segmentation.

    Renders orthographic projections of the voxel grid, combines them with
    the source image and multiple bundled reference images into a contact
    sheet, and asks the vision LLM for a verdict.

    Returns a verdict dict: {"passes": bool|None, "score": float|None,
    "feedback": str}.
    """
    import fal_client

    panels: list[tuple[str, Image.Image]] = []

    if source_image_url:
        source_image = _download_image(source_image_url)
        if source_image is not None:
            panels.append(("SOURCE", source_image))

    view_names = ("VOXELS (front)", "VOXELS (side)", "VOXELS (top)")
    for name, png in zip(view_names, render_voxel_projections(xyzrgb_content)):
        panels.append((name, Image.open(io.BytesIO(png)).convert("RGB")))

    for index, reference in enumerate(_load_bundled_reference_images(), start=1):
        panels.append((f"REFERENCE {index}", reference))

    sheet_png = build_check_sheet(panels)
    sheet_url = fal_client.upload(sheet_png, "image/png")
    logger.info(
        f"Submitting segmentation check sheet ({len(panels)} panels) "
        f"to vision LLM: {sheet_url[:80]}..."
    )

    output = _call_vision_llm(_CHECK_PROMPT, sheet_url)
    verdict = parse_llm_verdict(output)
    logger.info(f"LLM segmentation check verdict: {verdict}")
    return verdict


def apply_llm_segmentation(
    xyzrgb_content: str,
    source_image_url: Optional[str],
    grid_resolution: int,
    mode: Optional[str] = None,
) -> tuple[str, dict]:
    """
    Apply the configured LLM segmentation mode to algorithmic XYZRGB content.

    Never raises — on any failure the original algorithmic content is
    returned unchanged so the pipeline is never degraded.

    Returns:
        Tuple of (xyzrgb_content, info) where info describes what happened:
        {"mode": str, "used_llm_segmentation": bool, "verdict": dict|None,
         "error": str|None}
    """
    mode = mode or get_llm_segmentation_mode()
    info: dict = {
        "mode": mode,
        "used_llm_segmentation": False,
        "verdict": None,
        "error": None,
    }

    if mode == "off":
        return xyzrgb_content, info

    try:
        if mode == "llm":
            if not source_image_url:
                raise ValueError("No source image available for LLM segmentation")
            llm_content = segment_voxels_with_llm(source_image_url, grid_resolution)
            info["used_llm_segmentation"] = True
            # Have the LLM double-check its own segmentation as well
            try:
                info["verdict"] = check_segmentation_with_llm(
                    llm_content, source_image_url
                )
            except Exception as check_error:
                logger.warning(f"LLM segmentation self-check failed: {check_error}")
            return llm_content, info

        # mode == "check": advisory verification of the algorithmic result
        info["verdict"] = check_segmentation_with_llm(
            xyzrgb_content, source_image_url
        )
        if info["verdict"].get("passes") is False:
            logger.warning(
                "LLM flagged the deterministic segmentation: "
                f"{info['verdict'].get('feedback')}"
            )
        return xyzrgb_content, info

    except Exception as e:
        logger.warning(
            f"LLM segmentation (mode={mode}) failed, falling back to "
            f"algorithmic result: {e}"
        )
        info["error"] = str(e)
        info["used_llm_segmentation"] = False
        return xyzrgb_content, info
