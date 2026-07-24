import base64
from io import BytesIO
import json
import logging
import os
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import HTTPException
from PIL import Image, ImageDraw
from pydantic import BaseModel, validator

from ..utils.posthog_client import track_api_call, track_error

logger = logging.getLogger(__name__)

MAX_XYZRGB_BYTES = 8 * 1024 * 1024
MAX_VOXELS = 350_000
DEFAULT_MODEL = os.getenv("OPENAI_LLM_RENDER_MODEL", "gpt-5.5")


class LlmRenderRequest(BaseModel):
    xyzrgb_url: str
    reference_image_url: str
    prompt: Optional[str] = None
    model: Optional[str] = None
    grid_size: Optional[int] = 4

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

    @validator("grid_size")
    def validate_grid_size(cls, value: Optional[int]) -> int:
        if value is None:
            return 4
        if value < 2 or value > 8:
            raise ValueError("grid_size must be between 2 and 8")
        return value


class LlmRenderResponse(BaseModel):
    xyzrgb_content: str
    voxel_count: int
    model: str
    applied_rules: List[Dict[str, Any]]
    message: str = "Successfully recolored xyzrgb"


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


def _bounds(voxels: List[Dict[str, int]]) -> Dict[str, Tuple[int, int]]:
    return {
        axis: (min(v[axis] for v in voxels), max(v[axis] for v in voxels))
        for axis in ("x", "y", "z")
    }


def _quantize_color(r: int, g: int, b: int, step: int = 32) -> Tuple[int, int, int]:
    return tuple(min(255, int(round(channel / step) * step)) for channel in (r, g, b))


def _dominant_colors(voxels: List[Dict[str, int]], limit: int = 18) -> List[Dict[str, Any]]:
    counter = Counter(_quantize_color(v["r"], v["g"], v["b"]) for v in voxels)
    return [
        {"rgb": list(color), "count": count}
        for color, count in counter.most_common(limit)
    ]


def _axis_value_to_cell(value: int, low: int, high: int, grid_size: int) -> int:
    if high == low:
        return 0
    normalized = (value - low) / (high - low)
    return min(grid_size - 1, max(0, int(normalized * grid_size)))


def _spatial_cells(
    voxels: List[Dict[str, int]],
    bounds: Dict[str, Tuple[int, int]],
    grid_size: int,
    limit: int = 96,
) -> List[Dict[str, Any]]:
    cells: Dict[Tuple[int, int, int], Dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "colors": Counter()}
    )

    for voxel in voxels:
        cell = (
            _axis_value_to_cell(voxel["x"], *bounds["x"], grid_size),
            _axis_value_to_cell(voxel["y"], *bounds["y"], grid_size),
            _axis_value_to_cell(voxel["z"], *bounds["z"], grid_size),
        )
        cells[cell]["count"] += 1
        cells[cell]["colors"][_quantize_color(voxel["r"], voxel["g"], voxel["b"])] += 1

    summarized = []
    for (x, y, z), data in sorted(
        cells.items(), key=lambda item: item[1]["count"], reverse=True
    )[:limit]:
        color, color_count = data["colors"].most_common(1)[0]
        summarized.append(
            {
                "cell": [x, y, z],
                "normalized_bounds": [
                    [round(x / grid_size, 3), round((x + 1) / grid_size, 3)],
                    [round(y / grid_size, 3), round((y + 1) / grid_size, 3)],
                    [round(z / grid_size, 3), round((z + 1) / grid_size, 3)],
                ],
                "count": data["count"],
                "dominant_rgb": list(color),
                "dominant_rgb_count": color_count,
            }
        )
    return summarized


def _build_scene_summary(voxels: List[Dict[str, int]], grid_size: int) -> Dict[str, Any]:
    bounds = _bounds(voxels)
    return {
        "format": "xyzrgb rows are x y z r g b integer voxels",
        "voxel_count": len(voxels),
        "bounds": {axis: list(values) for axis, values in bounds.items()},
        "dimensions": {
            axis: values[1] - values[0] + 1 for axis, values in bounds.items()
        },
        "dominant_colors": _dominant_colors(voxels),
        "spatial_grid": {
            "grid_size_per_axis": grid_size,
            "cell_coordinates": "0 is low/min on an axis; grid_size-1 is high/max",
            "occupied_cells": _spatial_cells(voxels, bounds, grid_size),
        },
    }


def _project_voxels(
    voxels: List[Dict[str, int]],
    horizontal_axis: str,
    vertical_axis: str,
    depth_axis: str,
    bounds: Dict[str, Tuple[int, int]],
    image_size: int = 256,
) -> Image.Image:
    width = bounds[horizontal_axis][1] - bounds[horizontal_axis][0] + 1
    height = bounds[vertical_axis][1] - bounds[vertical_axis][0] + 1
    scale = max(1, min(image_size // max(width, 1), image_size // max(height, 1)))
    canvas_width = max(1, width * scale)
    canvas_height = max(1, height * scale)
    image = Image.new("RGB", (canvas_width, canvas_height), "white")
    draw = ImageDraw.Draw(image)
    nearest_by_pixel: Dict[Tuple[int, int], Tuple[int, Tuple[int, int, int]]] = {}

    for voxel in voxels:
        px = voxel[horizontal_axis] - bounds[horizontal_axis][0]
        py = bounds[vertical_axis][1] - voxel[vertical_axis]
        depth = voxel[depth_axis]
        key = (px, py)
        color = (voxel["r"], voxel["g"], voxel["b"])
        previous = nearest_by_pixel.get(key)
        if previous is None or depth > previous[0]:
            nearest_by_pixel[key] = (depth, color)

    for (px, py), (_, color) in nearest_by_pixel.items():
        draw.rectangle(
            [px * scale, py * scale, (px + 1) * scale - 1, (py + 1) * scale - 1],
            fill=color,
        )

    return image.resize((image_size, image_size), Image.Resampling.NEAREST)


def _build_voxel_preview_data_url(voxels: List[Dict[str, int]]) -> str:
    bounds = _bounds(voxels)
    views = [
        ("front", _project_voxels(voxels, "x", "z", "y", bounds)),
        ("side", _project_voxels(voxels, "y", "z", "x", bounds)),
        ("top", _project_voxels(voxels, "x", "y", "z", bounds)),
    ]

    label_height = 28
    gap = 12
    tile_size = 256
    composite = Image.new(
        "RGB",
        (tile_size * len(views) + gap * (len(views) - 1), tile_size + label_height),
        "white",
    )
    draw = ImageDraw.Draw(composite)

    for index, (label, view) in enumerate(views):
        x = index * (tile_size + gap)
        composite.paste(view, (x, label_height))
        draw.text((x + 8, 7), label, fill=(0, 0, 0))

    buffer = BytesIO()
    composite.save(buffer, format="PNG", optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


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


async def _call_openai_for_rules(
    scene_summary: Dict[str, Any],
    reference_image_url: str,
    voxel_preview_image_url: str,
    prompt: Optional[str],
    model: str,
) -> List[Dict[str, Any]]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY not configured. Set OPENAI_API_KEY and restart the backend server.",
        )

    system_prompt = (
        "You recolor voxel xyzrgb models to match a reference image semantically. "
        "Use the reference image as the target palette and the voxel preview image "
        "as the current model appearance. Do not change geometry. Return only JSON."
    )
    user_prompt = {
        "task": (
            "Inspect both images. First infer the major semantic color regions in "
            "the reference image, then map those regions onto the visible front, side, "
            "and top voxel preview. Create recoloring rules that make the voxel object "
            "look more like the reference image while preserving shape."
        ),
        "optional_user_prompt": prompt,
        "rule_schema": {
            "rules": [
                {
                    "name": "short semantic region name",
                    "reason": "which reference-image region this rule maps to",
                    "selector": {
                        "x": [0.0, 1.0],
                        "y": [0.0, 1.0],
                        "z": [0.0, 1.0],
                        "source_colors": [[0, 0, 0]],
                        "color_tolerance": 60,
                    },
                    "color": [255, 0, 0],
                    "strength": 1.0,
                }
            ]
        },
        "selector_notes": (
            "x/y/z selector ranges are normalized 0..1 over the voxel bounds. "
            "Use [0, 1] for axes that should not be spatially constrained. "
            "Use source_colors=[] when the rule should not target existing approximate colors. "
            "Existing dominant colors in scene_summary are source colors, not the target palette. "
            "Do not simply apply high-frequency existing colors across the model. "
            "Prefer contiguous semantic regions and colors visible in the reference image. "
            "Use the fewest rules that explain the reference image; keep rules under 16. "
            "Order specific rules before broad base-color rules."
        ),
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
                    {"type": "input_image", "image_url": reference_image_url},
                    {"type": "input_image", "image_url": voxel_preview_image_url},
                ],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "voxel_recolor_rules",
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "rules": {
                            "type": "array",
                            "maxItems": 16,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "name": {"type": "string"},
                                    "reason": {"type": "string"},
                                    "selector": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "properties": {
                                            "x": {
                                                "type": "array",
                                                "minItems": 2,
                                                "maxItems": 2,
                                                "items": {"type": "number", "minimum": 0, "maximum": 1},
                                            },
                                            "y": {
                                                "type": "array",
                                                "minItems": 2,
                                                "maxItems": 2,
                                                "items": {"type": "number", "minimum": 0, "maximum": 1},
                                            },
                                            "z": {
                                                "type": "array",
                                                "minItems": 2,
                                                "maxItems": 2,
                                                "items": {"type": "number", "minimum": 0, "maximum": 1},
                                            },
                                            "source_colors": {
                                                "type": "array",
                                                "items": {
                                                    "type": "array",
                                                    "minItems": 3,
                                                    "maxItems": 3,
                                                    "items": {"type": "integer", "minimum": 0, "maximum": 255},
                                                },
                                            },
                                            "color_tolerance": {"type": "number", "minimum": 0, "maximum": 442},
                                        },
                                        "required": ["x", "y", "z", "source_colors", "color_tolerance"],
                                    },
                                    "color": {
                                        "type": "array",
                                        "minItems": 3,
                                        "maxItems": 3,
                                        "items": {"type": "integer", "minimum": 0, "maximum": 255},
                                    },
                                    "strength": {"type": "number", "minimum": 0, "maximum": 1},
                                },
                                "required": ["name", "reason", "selector", "color", "strength"],
                            },
                        }
                    },
                    "required": ["rules"],
                },
            }
        },
    }

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
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
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"OpenAI request failed: {e}")

    parsed = _extract_json_object(_extract_response_text(response.json()))
    rules = parsed.get("rules", [])
    if not isinstance(rules, list):
        raise HTTPException(status_code=502, detail="OpenAI rules must be an array")
    return rules


def _coerce_rgb(value: Any) -> Optional[Tuple[int, int, int]]:
    if not isinstance(value, list) or len(value) != 3:
        return None
    try:
        rgb = tuple(max(0, min(255, int(channel))) for channel in value)
    except (TypeError, ValueError):
        return None
    return rgb


def _in_normalized_range(
    voxel_value: int,
    axis_bounds: Tuple[int, int],
    selector_range: Any,
) -> bool:
    if selector_range is None:
        return True
    if not isinstance(selector_range, list) or len(selector_range) != 2:
        return True
    low, high = axis_bounds
    if high == low:
        normalized = 0.0
    else:
        normalized = (voxel_value - low) / (high - low)
    try:
        selected_low = float(selector_range[0])
        selected_high = float(selector_range[1])
    except (TypeError, ValueError):
        return True
    if selected_low > selected_high:
        selected_low, selected_high = selected_high, selected_low
    return selected_low <= normalized <= selected_high


def _matches_source_color(voxel: Dict[str, int], selector: Dict[str, Any]) -> bool:
    source_colors = selector.get("source_colors")
    if not source_colors:
        return True
    if not isinstance(source_colors, list):
        return True

    try:
        tolerance = float(selector.get("color_tolerance", 60))
    except (TypeError, ValueError):
        tolerance = 60.0

    for source_color in source_colors:
        rgb = _coerce_rgb(source_color)
        if rgb is None:
            continue
        distance = (
            (voxel["r"] - rgb[0]) ** 2
            + (voxel["g"] - rgb[1]) ** 2
            + (voxel["b"] - rgb[2]) ** 2
        ) ** 0.5
        if distance <= tolerance:
            return True
    return False


def _apply_rules(
    voxels: List[Dict[str, int]],
    rules: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, int]], List[Dict[str, Any]]]:
    bounds = _bounds(voxels)
    recolored = [voxel.copy() for voxel in voxels]
    applied_rules: List[Dict[str, Any]] = []

    for raw_rule in rules[:16]:
        if not isinstance(raw_rule, dict):
            continue
        color = _coerce_rgb(raw_rule.get("color"))
        selector = raw_rule.get("selector")
        if color is None or not isinstance(selector, dict):
            continue

        try:
            strength = float(raw_rule.get("strength", 1.0))
        except (TypeError, ValueError):
            strength = 1.0
        strength = max(0.0, min(1.0, strength))

        changed = 0
        for voxel in recolored:
            if not all(
                _in_normalized_range(voxel[axis], bounds[axis], selector.get(axis))
                for axis in ("x", "y", "z")
            ):
                continue
            if not _matches_source_color(voxel, selector):
                continue

            voxel["r"] = round(voxel["r"] * (1 - strength) + color[0] * strength)
            voxel["g"] = round(voxel["g"] * (1 - strength) + color[1] * strength)
            voxel["b"] = round(voxel["b"] * (1 - strength) + color[2] * strength)
            changed += 1

        applied_rules.append(
            {
                "name": raw_rule.get("name", "unnamed rule"),
                "reason": raw_rule.get("reason"),
                "selector": selector,
                "color": list(color),
                "strength": strength,
                "changed_voxels": changed,
            }
        )

    return recolored, applied_rules


def _serialize_xyzrgb(voxels: List[Dict[str, int]]) -> str:
    return "\n".join(
        f"{v['x']} {v['y']} {v['z']} {v['r']} {v['g']} {v['b']}" for v in voxels
    ) + "\n"


async def llm_render(request: LlmRenderRequest, auth_info: dict) -> LlmRenderResponse:
    endpoint = "/llmRender"
    user_id = auth_info.get("user_email") or auth_info.get("user_id") or "anonymous"
    model = request.model or DEFAULT_MODEL

    try:
        xyzrgb_content = await _fetch_text_url(request.xyzrgb_url, MAX_XYZRGB_BYTES)
        voxels = _parse_xyzrgb(xyzrgb_content)
        scene_summary = _build_scene_summary(voxels, request.grid_size or 4)
        voxel_preview_image_url = _build_voxel_preview_data_url(voxels)
        rules = await _call_openai_for_rules(
            scene_summary=scene_summary,
            reference_image_url=request.reference_image_url,
            voxel_preview_image_url=voxel_preview_image_url,
            prompt=request.prompt,
            model=model,
        )
        recolored, applied_rules = _apply_rules(voxels, rules)

        track_api_call(
            endpoint=endpoint,
            user_id=user_id,
            success=True,
            model=model,
            voxel_count=len(voxels),
            rules_count=len(applied_rules),
        )

        return LlmRenderResponse(
            xyzrgb_content=_serialize_xyzrgb(recolored),
            voxel_count=len(recolored),
            model=model,
            applied_rules=applied_rules,
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
