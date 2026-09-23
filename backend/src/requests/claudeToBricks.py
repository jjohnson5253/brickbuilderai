import asyncio
import base64
import json
import logging
import math
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import Depends, HTTPException
from pydantic import BaseModel, field_validator, model_validator

from ..utils.auth import deduct_credits, get_user_with_optional_auth, handle_auth_and_tracking
from ..utils.brick_design import (
    DesignError,
    audit_ldraw,
    build_design,
    load_palette,
    palette_prompt_text,
    render_preview_png,
)
from ..utils.generation_storage import generation_storage
from ..utils.pack_ldraw_model import LDrawPacker
from ..utils.posthog_client import track_error, track_image_conversion
from .imageToBricks import ImageToBricksResponse

logger = logging.getLogger(__name__)

# Keep the model configurable so deployments can pin a different Anthropic
# model without a code release.
DEFAULT_MODEL = os.getenv("ANTHROPIC_LDR_MODEL", "claude-opus-5-5")
ANTHROPIC_API_VERSION = os.getenv("ANTHROPIC_API_VERSION", "2023-06-01")
ANTHROPIC_MAX_TOKENS = int(os.getenv("ANTHROPIC_LDR_MAX_TOKENS", "65536"))
ANTHROPIC_TIMEOUT_SECONDS = float(os.getenv("ANTHROPIC_LDR_TIMEOUT_SECONDS", "600"))

# "design" (default): Claude describes the model as colored voxel shapes on a stud grid and
# brick_design.py turns that into bricks deterministically (no overlaps, off-grid parts or
# floating bricks), with a build -> feedback -> review loop.
# "direct": Claude writes raw LDraw (the original path), now audited for overlaps/floating
# parts with a correction round.
LDR_MODE = os.getenv("CLAUDE_LDR_MODE", "design").strip().lower()
DESIGN_MAX_ATTEMPTS = max(1, int(os.getenv("CLAUDE_DESIGN_MAX_ATTEMPTS", "3")))
DESIGN_REVIEW_ROUNDS = max(0, int(os.getenv("CLAUDE_DESIGN_REVIEW_ROUNDS", "1")))
DIRECT_FIX_ROUNDS = max(0, int(os.getenv("CLAUDE_DIRECT_FIX_ROUNDS", "1")))

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_LDR_BYTES = 750_000
MAX_LDR_PARTS = 5_000
SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
PART_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+\.dat$", re.IGNORECASE)


class ClaudeToBricksRequest(BaseModel):
    prompt: Optional[str] = None
    image_base64: Optional[str] = None
    image_media_type: str = "image/png"
    detail_level: float = 40.0

    @field_validator("prompt")
    @classmethod
    def normalize_prompt(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if len(value) > 2_000:
            raise ValueError("Prompt must be 2000 characters or less")
        return value or None

    @field_validator("image_media_type")
    @classmethod
    def validate_image_media_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized == "image/jpg":
            normalized = "image/jpeg"
        if normalized not in SUPPORTED_IMAGE_TYPES:
            raise ValueError("image_media_type must be JPEG, PNG, GIF, or WebP")
        return normalized

    @field_validator("image_base64")
    @classmethod
    def validate_image_base64(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if value.startswith("data:"):
            _, separator, value = value.partition(",")
            if not separator:
                raise ValueError("Invalid image data URL")
        try:
            decoded = base64.b64decode(value, validate=True)
        except Exception as exc:
            raise ValueError("Invalid base64 image data") from exc
        if not decoded:
            raise ValueError("Image cannot be empty")
        if len(decoded) > MAX_IMAGE_BYTES:
            raise ValueError("Image must be 10 MB or smaller")
        return value

    @field_validator("detail_level")
    @classmethod
    def validate_detail_level(cls, value: float) -> float:
        if not math.isfinite(value) or value <= 0:
            raise ValueError("detail_level must be a positive number")
        return value

    @model_validator(mode="after")
    def require_prompt_or_image(self) -> "ClaudeToBricksRequest":
        if not self.prompt and not self.image_base64:
            raise ValueError("Provide a text prompt, an image, or both")
        return self


def _user_content(request: ClaudeToBricksRequest) -> List[Dict[str, Any]]:
    user_content: List[Dict[str, Any]] = []
    if request.image_base64:
        user_content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": request.image_media_type,
                    "data": request.image_base64,
                },
            }
        )
    user_content.append(
        {
            "type": "text",
            "text": request.prompt
            or "Recreate the main subject in the reference image as a recognizable brick model.",
        }
    )
    return user_content


def _anthropic_payload(
    request: ClaudeToBricksRequest,
    model: str = DEFAULT_MODEL,
    messages: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Payload for the direct (raw LDraw) mode."""
    user_content = _user_content(request)
    system_prompt = """You are an expert LEGO-compatible model designer using the LDraw file format.
Create a complete, physically connected, stable model from the user's text and/or image. Return only
official LDraw part references through the submit_ldr_model tool. Use common, currently available parts,
standard integer LDraw color codes, valid type-1 transformation matrices, and useful 0 STEP boundaries.
Orient the finished model upright with its lowest bricks at y=0. Prefer a practical 150-500 piece model;
use fewer pieces for a simple subject and never exceed 5,000 pieces. Do not use MPD submodels, embedded
files, custom geometry, stickers, base64, Markdown fences, or explanatory prose inside ldr_content."""

    return {
        "model": model,
        "max_tokens": ANTHROPIC_MAX_TOKENS,
        "system": system_prompt,
        "thinking": {"type": "adaptive"},
        "messages": messages or [{"role": "user", "content": user_content}],
        "tools": [
            {
                "name": "submit_ldr_model",
                "description": "Submit the finished model as a single valid LDraw .ldr file.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "maxLength": 120},
                        "ldr_content": {
                            "type": "string",
                            "description": "Complete plain-text LDraw model content.",
                        },
                    },
                    "required": ["ldr_content"],
                    "additionalProperties": False,
                },
            }
        ],
        # Opus 5.5 rejects forced tool use. The system prompt still tells it to
        # submit through this tool, while auto keeps the request API-compatible.
        "tool_choice": {"type": "auto"},
    }


def _extract_ldr_content(response_json: Dict[str, Any]) -> str:
    if response_json.get("stop_reason") == "max_tokens":
        raise ValueError("Claude's LDraw response was truncated; try a simpler model")
    for block in response_json.get("content", []):
        if block.get("type") != "tool_use" or block.get("name") != "submit_ldr_model":
            continue
        tool_input = block.get("input") or {}
        if not isinstance(tool_input, dict):
            continue
        ldr_content = tool_input.get("ldr_content")
        if isinstance(ldr_content, str):
            return ldr_content

    # Tool choice must remain automatic for Opus 5.5, so tolerate a plain-text
    # final answer and pass it through the same strict LDraw validator.
    text_content = "\n".join(
        block.get("text", "")
        for block in response_json.get("content", [])
        if block.get("type") == "text" and isinstance(block.get("text"), str)
    ).strip()
    if text_content:
        try:
            decoded = json.loads(text_content)
        except json.JSONDecodeError:
            return text_content
        if isinstance(decoded, dict) and isinstance(decoded.get("ldr_content"), str):
            return decoded["ldr_content"]
    raise ValueError("Claude did not return an LDraw model")


def validate_ldr_content(raw_content: str) -> str:
    content = raw_content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:ldr|ldraw)?\s*", "", content, flags=re.IGNORECASE)
        content = re.sub(r"\s*```$", "", content)
    if not content or len(content.encode("utf-8")) > MAX_LDR_BYTES:
        raise ValueError("Claude returned an empty or oversized LDraw model")

    normalized_lines = []
    part_count = 0
    saw_file_header = False
    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        tokens = line.split()
        if tokens[0] == "0":
            if len(tokens) > 1 and tokens[1].upper() == "FILE":
                is_standalone_header = (
                    not normalized_lines
                    and not saw_file_header
                    and len(tokens) == 3
                    and tokens[2].lower().endswith(".ldr")
                )
                if is_standalone_header:
                    saw_file_header = True
                    continue
                raise ValueError("MPD and embedded FILE sections are not supported")
            if len(tokens) > 1 and tokens[1].upper() == "NOFILE":
                raise ValueError("MPD and embedded FILE sections are not supported")
            normalized_lines.append(line)
            continue
        if tokens[0] != "1" or len(tokens) != 15:
            raise ValueError(f"Invalid LDraw command on line {line_number}")
        try:
            color = int(tokens[1])
            numeric_values = [float(token) for token in tokens[2:14]]
        except ValueError as exc:
            raise ValueError(f"Invalid LDraw values on line {line_number}") from exc
        if color < 0 or color > 511 or not all(math.isfinite(value) for value in numeric_values):
            raise ValueError(f"Invalid LDraw values on line {line_number}")
        if not PART_NAME_RE.fullmatch(tokens[14]):
            raise ValueError(f"Unsafe or unsupported LDraw part name on line {line_number}")
        part_count += 1
        if part_count > MAX_LDR_PARTS:
            raise ValueError(f"LDraw model exceeds the {MAX_LDR_PARTS:,}-piece limit")
        normalized_lines.append(" ".join(tokens))

    if part_count == 0:
        raise ValueError("Claude returned an LDraw model with no parts")

    if not any(line.lower().startswith("0 name:") for line in normalized_lines):
        normalized_lines.insert(0, "0 Name: claude-model.ldr")
    if not any(line.lower().startswith("0 author:") for line in normalized_lines):
        normalized_lines.insert(1, "0 Author: BrickBuilder AI with Claude")
    return "\n".join(normalized_lines) + "\n"


DESIGN_SYSTEM_PROMPT = """You are an expert LEGO-compatible model designer. Design a model from the user's text
and/or reference image and submit it with the submit_brick_design tool. You do NOT write LDraw: you describe
the model as colored voxels on a stud grid, and a deterministic builder turns every voxel into real bricks,
checks that everything connects, and sends you back a report and preview renders.

GRID AND COORDINATES
- One voxel = 1 x 1 stud footprint and one layer tall. x runs left -> right (0..width-1), z runs front -> back
  (0..depth-1; z = 0 is the side facing the viewer), y is the layer number from the ground (0..layers-1).
- layer_unit "brick" (default): a layer is one brick tall = 1.2 studs. A shape that should look round and 10
  studs tall needs about 8 layers. Good for most models.
- layer_unit "plate": a layer is one plate tall = 0.4 studs (3 plates = 1 brick). Finer vertical detail (faces,
  gentle slopes, small models) at about 3x the pieces.
- Size: {size_hint} Hard limits: 64 x 64 studs, 96 brick or 240 plate layers, 5,000 pieces.

SHAPES (applied in order; later shapes override earlier ones)
- {{"shape":"box","x":[x0,x1],"y":[y0,y1],"z":[z0,z1],"color":C}}  (inclusive integer ranges)
- {{"shape":"ellipsoid","center":[x,y,z],"radius":[rx,ry,rz],"color":C}}  (y and ry in layers; cells whose
  center is inside are filled)
- {{"shape":"cylinder","axis":"x"|"y"|"z","center":[a,b],"radius":[ra,rb] or r,"range":[lo,hi],"color":C}}
  (center/radius are the two coordinates other than the axis, in x,y,z order: axis "y" -> [x,z])
- {{"shape":"layer","y":Y or [y0,y1],"rows":["....AAAA....", ...],"legend":{{"A":C}}}}  a pixel map of one
  layer (or repeated over a range): rows[z] is a row from front (z=0) to back, character index = x,
  "." = leave unchanged. Best for detailed patterns, lettering, mosaics and irregular outlines.
- every shape takes "mode": "fill" (default, adds voxels), "paint" (recolors only voxels that already
  exist: use it for faces, stripes, windows and details on a surface) or "carve" (removes voxels; no color).

COLORS: use only these LDraw color codes (code name): {palette}

BUILD RULES (the builder enforces them; follow them to avoid rework)
- Everything must connect to layer 0 through touching voxels. Nothing may float.
- Bricks only hold together by overlapping the layer above or below, and one brick is one color. So a
  one-stud-wide feature of a different color stacked straight up against the side of the model (an ear,
  a trim line, the edge of hair) cannot attach. Make such details at least 2 studs deep, match the color
  of the cells they sit against, or support them from below.
- Overhangs: each layer should step out at most 1-2 studs beyond the layer below it.
- Solid volumes are hollowed automatically (hollow: true); keep walls you design at least 2 studs thick.
- Set base_color to put the whole model on one plate base (recommended for scenes, buildings, vehicles on
  display, and anything made of separate parts standing on the ground).

WORKFLOW: think about proportions and the recognizable features first, then submit one complete design.
After each build you get a report and two isometric renders (front-left and back-right). Fix any errors you
are told about. When you review a successful build, compare it to the request/reference; if it looks
right call accept_design, otherwise submit an improved design."""

DESIGN_TOOLS = [
    {
        "name": "submit_brick_design",
        "description": "Submit a complete voxel design for the builder to turn into bricks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "maxLength": 120},
                "layer_unit": {"type": "string", "enum": ["brick", "plate"]},
                "grid": {
                    "type": "object",
                    "properties": {
                        "width": {"type": "integer", "minimum": 1, "maximum": 64},
                        "depth": {"type": "integer", "minimum": 1, "maximum": 64},
                        "layers": {"type": "integer", "minimum": 1, "maximum": 240},
                    },
                    "required": ["width", "depth", "layers"],
                },
                "hollow": {"type": "boolean"},
                "base_color": {"type": "integer"},
                "shapes": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Ordered shape operations (box, ellipsoid, cylinder, layer).",
                },
            },
            "required": ["grid", "shapes"],
        },
    },
    {
        "name": "accept_design",
        "description": "Accept the most recent successful build as the final model.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


def _design_size_hint(detail_level: float) -> str:
    target = int(min(64, max(12, round(detail_level))))
    return (f"aim for about {target} studs across the largest horizontal dimension unless the subject "
            "clearly needs a different size.")


def _design_payload(
    request: ClaudeToBricksRequest,
    messages: List[Dict[str, Any]],
    model: str = DEFAULT_MODEL,
) -> Dict[str, Any]:
    return {
        "model": model,
        "max_tokens": ANTHROPIC_MAX_TOKENS,
        "system": DESIGN_SYSTEM_PROMPT.format(
            size_hint=_design_size_hint(request.detail_level),
            palette=palette_prompt_text(),
        ),
        "thinking": {"type": "adaptive"},
        "messages": messages,
        "tools": DESIGN_TOOLS,
        # Opus 5.5 rejects forced tool use; the prompt asks for the tool.
        "tool_choice": {"type": "auto"},
    }


def _anthropic_headers() -> Dict[str, str]:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY is not configured")
    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_API_VERSION,
        "content-type": "application/json",
    }
    workspace_id = os.getenv("ANTHROPIC_WORKSPACE_ID")
    if workspace_id:
        headers["anthropic-workspace-id"] = workspace_id
    return headers


async def _post_messages(client: httpx.AsyncClient, headers: Dict[str, str], payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        response = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Claude LDraw generation timed out") from exc
    except httpx.HTTPStatusError as exc:
        logger.error("Claude LDraw request failed with HTTP %s", exc.response.status_code)
        raise HTTPException(
            status_code=502,
            detail=f"Claude LDraw request failed: HTTP {exc.response.status_code}",
        ) from exc
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail="Claude LDraw request failed") from exc


def _tool_uses(response_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [b for b in response_json.get("content", []) if b.get("type") == "tool_use"]


def _tool_result(tool_use_id: str, content: Any, is_error: bool = False) -> Dict[str, Any]:
    result: Dict[str, Any] = {"type": "tool_result", "tool_use_id": tool_use_id, "content": content}
    if is_error:
        result["is_error"] = True
    return result


async def _generate_ldr_with_design(request: ClaudeToBricksRequest) -> str:
    """Claude designs voxels; brick_design builds, verifies and renders; Claude fixes and reviews."""
    headers = _anthropic_headers()
    palette = load_palette()
    loop = asyncio.get_running_loop()
    messages: List[Dict[str, Any]] = [{"role": "user", "content": _user_content(request)}]
    best = None
    failures = 0
    reviews = 0

    def build(design: Dict[str, Any], repair: bool):
        return build_design(design, max_pieces=MAX_LDR_PARTS, repair=repair, palette=palette)

    async with httpx.AsyncClient(timeout=ANTHROPIC_TIMEOUT_SECONDS) as client:
        for _ in range(DESIGN_MAX_ATTEMPTS + DESIGN_REVIEW_ROUNDS + 2):
            response_json = await _post_messages(client, headers, _design_payload(request, messages))
            if response_json.get("stop_reason") == "max_tokens":
                if best:
                    break
                raise ValueError("Claude's design was truncated; try a simpler model")
            messages.append({"role": "assistant", "content": response_json.get("content", [])})
            uses = _tool_uses(response_json)
            submits = [u for u in uses if u.get("name") == "submit_brick_design"]

            if not uses:
                if best:
                    break  # answered in text after a successful build: keep that build
                failures += 1
                if failures >= DESIGN_MAX_ATTEMPTS:
                    break
                messages.append({"role": "user", "content": "Please submit the model with the submit_brick_design tool."})
                continue
            if best and not submits and any(u.get("name") == "accept_design" for u in uses):
                break  # Claude accepted the reviewed build

            results: List[Dict[str, Any]] = []
            done = False
            for use in uses:
                use_id = use.get("id")
                if use is not (submits[0] if submits else None):
                    message = ("No successful build to accept yet." if use.get("name") == "accept_design"
                               else "Submit exactly one submit_brick_design call per turn.")
                    results.append(_tool_result(use_id, message, True))
                    continue
                design = use.get("input") or {}
                try:
                    result = await loop.run_in_executor(None, build, design, False)
                except DesignError as exc:
                    failures += 1
                    if failures < DESIGN_MAX_ATTEMPTS:
                        results.append(_tool_result(use_id, f"Build failed: {exc}", True))
                        continue
                    if best:  # a revision failed on the last try: keep the earlier good build
                        done = True
                        break
                    # Out of retries: repair what can't connect rather than failing the generation.
                    try:
                        result = await loop.run_in_executor(None, build, design, True)
                    except DesignError as final_exc:
                        if best:
                            done = True
                            break
                        raise ValueError(f"Claude's brick design could not be built: {final_exc}") from final_exc
                best = result
                if reviews >= DESIGN_REVIEW_ROUNDS or failures >= DESIGN_MAX_ATTEMPTS:
                    done = True
                    break
                reviews += 1
                preview = await loop.run_in_executor(None, render_preview_png, result.grid, result.unit, palette)
                results.append(_tool_result(use_id, [
                    {"type": "text", "text": result.summary(palette) + "\n\nReview the renders against the"
                     " request (and reference image, if any). Call accept_design if it is right, or"
                     " submit_brick_design with a corrected complete design."},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                 "data": base64.b64encode(preview).decode()}},
                ]))
            if done:
                break
            messages.append({"role": "user", "content": results})

    if not best:
        raise ValueError("Claude did not produce a buildable brick design")
    return best.ldr


async def _generate_ldr_direct(request: ClaudeToBricksRequest) -> str:
    """Original mode: Claude writes LDraw; basic bricks/plates are audited for overlaps, off-grid
    and floating parts, and Claude gets DIRECT_FIX_ROUNDS chances to correct them."""
    headers = _anthropic_headers()
    messages: List[Dict[str, Any]] = [{"role": "user", "content": _user_content(request)}]
    best: Optional[str] = None
    async with httpx.AsyncClient(timeout=ANTHROPIC_TIMEOUT_SECONDS) as client:
        for round_number in range(DIRECT_FIX_ROUNDS + 1):
            response_json = await _post_messages(client, headers, _anthropic_payload(request, messages=messages))
            try:
                ldr = validate_ldr_content(_extract_ldr_content(response_json))
            except ValueError as exc:
                if best:
                    break
                raise HTTPException(status_code=502, detail=str(exc)) from exc
            best = ldr
            audit = audit_ldraw(ldr)
            uses = [u for u in _tool_uses(response_json) if u.get("name") == "submit_ldr_model"]
            if audit.ok or round_number == DIRECT_FIX_ROUNDS or not uses:
                break
            messages.append({"role": "assistant", "content": response_json.get("content", [])})
            feedback = (f"The model has placement problems: {audit.describe()}. Positions must be on the stud "
                        "grid (x/z centers at multiples of 10 LDU consistent with the part size; brick tops at "
                        "multiples of 8 LDU in y), parts may not overlap, and every part must rest on or hang "
                        "from another part. Submit the corrected complete model with submit_ldr_model.")
            messages.append({"role": "user", "content": [
                _tool_result(u.get("id"), feedback, True) for u in uses
            ]})
    return best


async def _generate_ldr_with_claude(request: ClaudeToBricksRequest) -> str:
    if LDR_MODE == "direct":
        return await _generate_ldr_direct(request)
    try:
        return validate_ldr_content(await _generate_ldr_with_design(request))
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


async def process_claude_to_bricks_task(
    generation_id: str,
    request: ClaudeToBricksRequest,
    user_info: Dict[str, Any],
    auth_info: Dict[str, Any],
) -> None:
    heartbeat_task: Optional[asyncio.Task] = None

    async def heartbeat() -> None:
        while True:
            await asyncio.sleep(5)
            try:
                await generation_storage.update_status(generation_id, "processing")
            except Exception as exc:
                logger.warning("Claude generation heartbeat failed: %s", exc)

    try:
        await generation_storage.update_status(generation_id, "processing")
        heartbeat_task = asyncio.create_task(heartbeat())
        ldr_content = await _generate_ldr_with_claude(request)

        await deduct_credits(
            user_info=user_info,
            auth_info=auth_info,
            credits_to_deduct=1,
            operation_description="Anthropic LDraw generation",
        )

        with tempfile.TemporaryDirectory(prefix="claude-ldr-") as temp_dir:
            ldr_path = Path(temp_dir) / "model.ldr"
            ldr_path.write_text(ldr_content, encoding="utf-8")
            packer = LDrawPacker()
            mpd_path = await asyncio.get_running_loop().run_in_executor(
                None, packer.pack_ldraw_model, str(ldr_path)
            )
            mpd_content = Path(mpd_path).read_text(encoding="utf-8")

        if request.image_base64:
            image_data_url = (
                f"data:{request.image_media_type};base64,{request.image_base64}"
            )
            await generation_storage.store_images(
                generation_id=generation_id,
                original_image_url=image_data_url,
                processed_image_url=image_data_url,
            )

        await generation_storage.store_model_file(
            generation_id, ldr_content, "ldr", raise_on_error=True
        )
        await generation_storage.store_parts_list_csv(
            generation_id, ldr_content, raise_on_error=True
        )
        # The shared generations schema persists the LDR and parts list but
        # does not require an mpd_url column. The frontend follows the same
        # path as existing generations and converts the saved LDR through
        # /ldrToMpd when no MPD URL is present. Packing above still verifies
        # that Claude's LDraw output can be expanded successfully.
        await generation_storage.update_status(generation_id, "completed")

        track_image_conversion(
            user_id=user_info["user_email"],
            success=True,
            has_mpd=True,
            ldr_size=len(ldr_content),
            mpd_size=len(mpd_content),
            image_type="claude_direct_ldr" if LDR_MODE == "direct" else "claude_brick_design",
            is_developer=user_info["is_developer"],
        )
    except Exception as exc:
        logger.exception("Claude-to-bricks generation failed for %s", generation_id)
        await generation_storage.update_status(generation_id, "failed", str(exc))
        track_error(
            error_type=type(exc).__name__,
            error_message=str(exc),
            endpoint="/claudeToBricks",
            user_id=user_info.get("user_email", "anonymous"),
        )
    finally:
        if heartbeat_task:
            heartbeat_task.cancel()


async def claude_to_bricks(
    request: ClaudeToBricksRequest,
    auth_info: dict = Depends(get_user_with_optional_auth),
) -> ImageToBricksResponse:
    user_info = handle_auth_and_tracking(
        auth_info=auth_info,
        endpoint="/claudeToBricks",
        track_properties={
            "has_image": bool(request.image_base64),
            "has_prompt": bool(request.prompt),
            "model": DEFAULT_MODEL,
        },
        required_credits=1,
    )

    if user_info["is_anonymous"]:
        user_id = auth_info["user_id"]
        user_type = "anonymous"
    elif user_info["is_developer"]:
        user_id = user_info["user_email"]
        user_type = "authenticated"
    else:
        user_id = auth_info.get("user_id", user_info["user_email"])
        user_type = "authenticated"

    try:
        generation_id = await generation_storage.create_generation(
            user_id=user_id,
            user_type=user_type,
            prompt=request.prompt or "Image reference",
            detail_level=request.detail_level,
            endpoint="claudeToBricks",
            model_3d=DEFAULT_MODEL,
        )
        asyncio.create_task(
            process_claude_to_bricks_task(generation_id, request, user_info, auth_info)
        )
        return ImageToBricksResponse(
            generation_id=generation_id,
            message="Claude generation started. Poll /generation/{generation_id} for status.",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to start Claude-to-bricks generation")
        track_error(
            error_type=type(exc).__name__,
            error_message=str(exc),
            endpoint="/claudeToBricks",
            user_id=user_info.get("user_email", "anonymous"),
        )
        raise HTTPException(status_code=500, detail="Failed to start Claude generation") from exc
