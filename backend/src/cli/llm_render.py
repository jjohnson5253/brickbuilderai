"""Run a live llmRender request from the command line."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

import requests
from dotenv import load_dotenv


DEFAULT_API_URL = "http://127.0.0.1:8002"
DEFAULT_PROMPT = (
    "Recolor the voxel model to semantically match the reference image while "
    "preserving the model shape."
)

load_dotenv()


class LlmRenderCliError(RuntimeError):
    """A user-actionable failure while running the manual LLM render test."""


def _generation_id(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("generation_id must be a UUID") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Call the live /llmRender endpoint for an existing generation. Missing "
            "XYZRGB and reference URLs are read from the generation automatically."
        )
    )
    parser.add_argument("generation_id", type=_generation_id)
    parser.add_argument(
        "--api-url",
        default=os.getenv("BRICKBUILDER_API_URL", DEFAULT_API_URL),
        help="Backend base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("DEVELOPER_API_KEY"),
        help="Developer API key; defaults to DEVELOPER_API_KEY",
    )
    parser.add_argument("--xyzrgb-url", help="Override the generation's xyzrgb_url")
    parser.add_argument(
        "--reference-image-url",
        help="Override the generation's processed/external reference image URL",
    )
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--max-segments", type=int, default=16, choices=range(2, 25))
    parser.add_argument(
        "--include-preview",
        action="store_true",
        help="Include the base64-labelled voxel preview in the JSON response",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("llm_render_response.json"),
        help="JSON response path (default: %(default)s)",
    )
    parser.add_argument(
        "--xyzrgb-output",
        type=Path,
        default=Path("llm_render_output.xyzrgb"),
        help="Recolored XYZRGB path (default: %(default)s)",
    )
    return parser


def _headers(api_key: Optional[str]) -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    return headers


def _read_json_response(response: requests.Response, action: str) -> Dict[str, Any]:
    try:
        data = response.json()
    except ValueError as exc:
        raise LlmRenderCliError(
            f"{action} returned HTTP {response.status_code} with a non-JSON response"
        ) from exc

    if not response.ok:
        detail = data.get("detail") if isinstance(data, dict) else data
        raise LlmRenderCliError(f"{action} failed (HTTP {response.status_code}): {detail}")
    if not isinstance(data, dict):
        raise LlmRenderCliError(f"{action} returned an invalid JSON response")
    return data


def resolve_input_urls(
    session: Any,
    api_url: str,
    generation_id: str,
    headers: Dict[str, str],
    xyzrgb_url: Optional[str],
    reference_image_url: Optional[str],
) -> Tuple[str, str]:
    """Resolve omitted render inputs from the generation polling endpoint."""
    if xyzrgb_url and reference_image_url:
        return xyzrgb_url, reference_image_url

    response = session.get(
        f"{api_url}/generation/{generation_id}",
        headers=headers,
        timeout=30,
    )
    generation = _read_json_response(response, "Fetching generation")
    resolved_xyzrgb = xyzrgb_url or generation.get("xyzrgb_url")
    resolved_reference = (
        reference_image_url
        or generation.get("processed_image_url")
        or generation.get("external_image_url")
    )
    if not resolved_xyzrgb:
        raise LlmRenderCliError(
            "The generation has no xyzrgb_url; pass one with --xyzrgb-url."
        )
    if not resolved_reference:
        raise LlmRenderCliError(
            "The generation has no processed or external image; pass one with "
            "--reference-image-url."
        )
    return str(resolved_xyzrgb), str(resolved_reference)


def run(args: argparse.Namespace, session: Any = requests) -> Dict[str, Any]:
    api_url = args.api_url.rstrip("/")
    headers = _headers(args.api_key)
    xyzrgb_url, reference_image_url = resolve_input_urls(
        session=session,
        api_url=api_url,
        generation_id=args.generation_id,
        headers=headers,
        xyzrgb_url=args.xyzrgb_url,
        reference_image_url=args.reference_image_url,
    )
    payload = {
        "generation_id": args.generation_id,
        "xyzrgb_url": xyzrgb_url,
        "reference_image_url": reference_image_url,
        "prompt": args.prompt,
        "max_segments": args.max_segments,
        "include_preview": args.include_preview,
    }
    response = session.post(
        f"{api_url}/llmRender",
        headers=headers,
        json=payload,
        timeout=600,
    )
    result = _read_json_response(response, "LLM render")
    xyzrgb_content = result.get("xyzrgb_content")
    if not isinstance(xyzrgb_content, str) or not xyzrgb_content.strip():
        raise LlmRenderCliError("LLM render response did not include xyzrgb_content")

    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    args.xyzrgb_output.write_text(xyzrgb_content, encoding="utf-8")
    return result


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = run(args)
    except (LlmRenderCliError, requests.RequestException, OSError) as exc:
        print(f"llmRender test failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"{result.get('message', 'llmRender completed')}\n"
        f"JSON response: {args.output}\n"
        f"Recolored XYZRGB: {args.xyzrgb_output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
