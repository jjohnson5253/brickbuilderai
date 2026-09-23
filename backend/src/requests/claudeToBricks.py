import asyncio
import base64
import json
import logging
import math
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from fastapi import Depends, HTTPException
from pydantic import BaseModel, field_validator, model_validator

from ..utils.auth import deduct_credits, get_user_with_optional_auth, handle_auth_and_tracking
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


def _anthropic_payload(request: ClaudeToBricksRequest, model: str = DEFAULT_MODEL) -> Dict[str, Any]:
    user_content = []
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
        "messages": [{"role": "user", "content": user_content}],
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


async def _generate_ldr_with_claude(request: ClaudeToBricksRequest) -> str:
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

    try:
        async with httpx.AsyncClient(timeout=ANTHROPIC_TIMEOUT_SECONDS) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=_anthropic_payload(request),
            )
            response.raise_for_status()
            response_json = response.json()
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

    try:
        return validate_ldr_content(_extract_ldr_content(response_json))
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
        await generation_storage.store_model_file(
            generation_id, mpd_content, "mpd", raise_on_error=True
        )
        await generation_storage.update_status(generation_id, "completed")

        track_image_conversion(
            user_id=user_info["user_email"],
            success=True,
            has_mpd=True,
            ldr_size=len(ldr_content),
            mpd_size=len(mpd_content),
            image_type="claude_direct_ldr",
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
