"""Experiment: can top LLMs generate a voxel structure resembling a picture?

Instead of the image -> 3D (Trellis / SAM3D) -> voxel pipeline, ask vision
LLMs (GPT-5, Gemini, or any OpenAI-compatible model) to look at an image and
emit a voxel model directly, algorithmically fill the gaps they leave, and
score each model against a pipeline-produced xyzrgb baseline.

Run from the backend directory:
    uv run python scripts/llm_voxel_experiment.py \
        --image test-files/png/pikachu.png \
        --models gpt-5,gemini-2.5-pro \
        --baseline pikachu_pipeline.xyzrgb

Set OPENAI_API_KEY for gpt-* models and GEMINI_API_KEY for gemini-* models.
Any other OpenAI-compatible endpoint can be used with --base-url and
--api-key-env. The baseline xyzrgb comes from the existing pipeline (the
``xyzrgb_content`` of an /imageToBricks generation). Results (raw and
gap-filled xyzrgb files plus report.json) are written to --output-dir; the
xyzrgb files can be loaded back through the normal pipeline tooling.
"""

import argparse
import base64
import json
import mimetypes
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.llm_voxel_generation import (
    DEFAULT_GRID_SIZE,
    MAX_GRID_SIZE,
    build_voxel_generation_messages,
    compare_voxel_models,
    describe_voxels,
    fill_gaps,
    parse_llm_voxel_output,
    parse_xyzrgb,
    serialize_xyzrgb,
)

REQUEST_TIMEOUT_SECONDS = 600.0

PROVIDERS = {
    "gpt": ("https://api.openai.com/v1", "OPENAI_API_KEY"),
    "o": ("https://api.openai.com/v1", "OPENAI_API_KEY"),
    "gemini": (
        "https://generativelanguage.googleapis.com/v1beta/openai",
        "GEMINI_API_KEY",
    ),
}


def resolve_provider(model: str, base_url: str | None, api_key_env: str | None) -> tuple[str, str]:
    """Map a model name to an OpenAI-compatible base URL and API key."""
    prefix = model.split("-", 1)[0].lower()
    default_base_url, default_key_env = PROVIDERS.get(prefix, (None, None))
    base_url = base_url or default_base_url
    key_env = api_key_env or default_key_env
    if not base_url or not key_env:
        raise SystemExit(
            f"Unknown provider for model '{model}'. Pass --base-url and --api-key-env."
        )
    api_key = os.getenv(key_env)
    if not api_key:
        raise SystemExit(f"{key_env} is not set. Add it to backend/.env or the environment.")
    return base_url.rstrip("/"), api_key


def load_image_url(image: str) -> str:
    """Return the image as an https URL or a base64 data URL."""
    if image.startswith(("http://", "https://")):
        return image
    path = Path(image)
    if not path.is_file():
        raise SystemExit(f"Image not found: {image}")
    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def load_baseline(baseline: str) -> list[dict]:
    if baseline.startswith(("http://", "https://")):
        response = httpx.get(baseline, timeout=60.0, follow_redirects=True)
        response.raise_for_status()
        content = response.text
    else:
        content = Path(baseline).read_text()
    return parse_xyzrgb(content)


def call_llm(model: str, messages: list, base_url: str, api_key: str) -> str:
    response = httpx.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": "Bearer " + api_key},
        json={"model": model, "messages": messages},
        timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS, connect=15.0),
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def run_model(
    model: str,
    image_url: str,
    args: argparse.Namespace,
    baseline: list | None,
    output_dir: Path,
) -> dict:
    base_url, api_key = resolve_provider(model, args.base_url, args.api_key_env)
    messages = build_voxel_generation_messages(image_url, args.grid_size, args.prompt)

    print(f"[{model}] requesting voxel model...")
    start = time.time()
    raw_text = call_llm(model, messages, base_url, api_key)
    elapsed = time.time() - start
    voxels = parse_llm_voxel_output(raw_text, args.grid_size)
    print(f"[{model}] {len(voxels)} voxels in {elapsed:.1f}s")

    safe_name = model.replace("/", "_")
    (output_dir / f"{safe_name}.xyzrgb").write_text(serialize_xyzrgb(voxels))

    result = {
        "model": model,
        "generation_seconds": round(elapsed, 1),
        "raw": describe_voxels(voxels),
    }

    if not args.no_fill_gaps:
        filled = fill_gaps(voxels)
        (output_dir / f"{safe_name}_filled.xyzrgb").write_text(serialize_xyzrgb(filled))
        result["filled"] = describe_voxels(filled)
        result["gap_voxels_added"] = len(filled) - len(voxels)
        voxels = filled

    if baseline is not None:
        result["vs_pipeline"] = compare_voxel_models(voxels, baseline, args.grid_size)

    return result


def print_summary(results: list[dict], baseline: list | None) -> None:
    print("\n=== LLM voxel generation results ===")
    if baseline is not None:
        stats = describe_voxels(baseline)
        print(
            f"pipeline baseline: {stats['voxel_count']} voxels, "
            f"bbox {stats['bounding_box']}, {stats['connected_components']} component(s)"
        )
    for result in results:
        if "error" in result:
            print(f"{result['model']}: FAILED ({result['error']})")
            continue
        line = (
            f"{result['model']}: {result['raw']['voxel_count']} voxels "
            f"({result['raw']['connected_components']} component(s)) "
            f"in {result['generation_seconds']}s"
        )
        if "gap_voxels_added" in result:
            line += f", +{result['gap_voxels_added']} gap-filled"
        comparison = result.get("vs_pipeline")
        if comparison:
            silhouette = comparison["silhouette_iou"]
            line += (
                f", IoU vs pipeline {comparison['occupancy_iou']:.2f} "
                f"(front {silhouette['front']:.2f}, side {silhouette['side']:.2f}, "
                f"top {silhouette['top']:.2f})"
            )
        print(line)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--image", required=True, help="Image path or URL")
    parser.add_argument(
        "--models",
        default="gpt-5,gemini-2.5-pro",
        help="Comma-separated model names (default: gpt-5,gemini-2.5-pro)",
    )
    parser.add_argument(
        "--baseline",
        help="Pipeline xyzrgb path or URL to compare against (from /imageToBricks)",
    )
    parser.add_argument("--grid-size", type=int, default=DEFAULT_GRID_SIZE)
    parser.add_argument("--prompt", help="Extra instructions for the LLM")
    parser.add_argument("--output-dir", default="llm_voxel_results")
    parser.add_argument("--base-url", help="OpenAI-compatible base URL override")
    parser.add_argument("--api-key-env", help="Env var holding the API key for --base-url")
    parser.add_argument(
        "--no-fill-gaps",
        action="store_true",
        help="Skip the algorithmic gap-filling pass",
    )
    args = parser.parse_args()

    if not 8 <= args.grid_size <= MAX_GRID_SIZE:
        raise SystemExit(f"--grid-size must be between 8 and {MAX_GRID_SIZE}")

    image_url = load_image_url(args.image)
    baseline = load_baseline(args.baseline) if args.baseline else None
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for model in [m.strip() for m in args.models.split(",") if m.strip()]:
        try:
            results.append(run_model(model, image_url, args, baseline, output_dir))
        except (httpx.HTTPError, ValueError, KeyError) as e:
            print(f"[{model}] failed: {e}", file=sys.stderr)
            results.append({"model": model, "error": str(e)})

    report_path = output_dir / "report.json"
    report_path.write_text(json.dumps({"image": args.image, "results": results}, indent=2))
    print_summary(results, baseline)
    print(f"\nReport written to {report_path}")


if __name__ == "__main__":
    main()
