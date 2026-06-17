"""
SAM-3D Objects Streaming Handler for RunPod Serverless.

This is a port of `app.py` (which targets fal.ai's `fal deploy`) to a
RunPod Serverless generator handler. The protocol of yielded events is kept
byte-for-byte compatible with the original fal SSE stream so the frontend
hook (`useSAM3DStream`) does not need to change.

Input schema (job["input"]):
    {
        "image_url": str,                 # http(s) URL OR a data: URL
        "image_b64": str | None,          # alternative to image_url (raw base64,
                                          #   no data: prefix; PNG/JPEG)
        "mask_urls": list[str] | None,
        "mask_b64": list[str] | None,
        "prompt": str | None,             # text label for auto-segmentation
        "seed": int | None,
        "stream_geometry_every": int = 1,
        "stream_colors_every": int = 1,
    }

Output: generator yielding dicts. Each yielded dict is one stream event;
the final `complete` event includes a base64-encoded GLB (under `glb_data`)
and, when small enough, the gaussian splat (`splat_data`). No external
object storage is used; everything is delivered inline over the stream.
"""

from __future__ import annotations

import base64
import io
import os
import queue
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Iterable

import runpod

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Persistent cache directory inside the container/worker. When using a RunPod
# Network Volume mounted at /runpod-volume, we get cross-invocation caching.
CACHE_ROOT = Path(os.environ.get("MANIFOLD_CACHE_DIR", "/runpod-volume/sam3d_objects"))
SAM3D_REPO_ID = os.environ.get("SAM3D_REPO_ID", "jetjodh/sam-3d-objects")

# If True, abort pipeline.run() right after the final appearance step — no
# mesh decoding, no GLB export, no splat PLY. Saves ~30s and avoids RunPod's
# per-job output cap entirely. Can be overridden per-request via
# job_input["voxels_only"] = False.
VOXELS_ONLY_DEFAULT = os.environ.get("VOXELS_ONLY", "1").lower() not in ("0", "false", "no")

# When the full pipeline does run, RunPod Serverless caps a job's aggregated
# output payload (~10 MB for /run, ~20 MB for /runsync). The splat PLY is
# typically 30–100 MB so it is dropped by default; the GLB is capped at 6 MB.
MAX_INLINE_SPLAT_BYTES = int(os.environ.get("MAX_INLINE_SPLAT_BYTES", 0))
MAX_INLINE_GLB_BYTES = int(os.environ.get("MAX_INLINE_GLB_BYTES", 6 * 1024 * 1024))


class _VoxelsOnlyAbort(Exception):
    """Raised inside the appearance callback to short-circuit pipeline.run()."""


# ---------------------------------------------------------------------------
# Lazy global pipeline (cold-start once per worker process)
# ---------------------------------------------------------------------------

_pipeline = None


def _patch_xformers_triton_compat() -> None:
    """Patch triton/xformers compat for PyTorch 2.8+. Lifted from app.py."""
    try:
        from triton.runtime import jit as triton_jit

        if not hasattr(triton_jit.JITFunction, "_unsafe_update_src"):
            return

        import xformers.triton.vararg_kernel as vararg_kernel
        import copy

        def patched_unroll_varargs(kernel, N):
            jitted_fn = copy.copy(kernel)
            annotations = {**kernel.__annotations__}
            src = kernel.src
            for i in range(N):
                old_arg = f"_args{i}"
                new_arg = f"_args_{i}"
                src = src.replace(old_arg, new_arg)
                if old_arg in annotations:
                    annotations[new_arg] = annotations.pop(old_arg)
            if hasattr(jitted_fn, "_unsafe_update_src"):
                jitted_fn._unsafe_update_src(src)
                if hasattr(jitted_fn, "hash"):
                    jitted_fn.hash = None
            else:
                jitted_fn.src = src
            jitted_fn.__annotations__ = annotations
            return jitted_fn

        vararg_kernel.unroll_varargs = patched_unroll_varargs
        print("[runpod-sam3d] Applied xformers/triton compatibility patch", flush=True)
    except ImportError:
        pass
    except Exception as e:  # noqa: BLE001
        print(f"[runpod-sam3d] xformers/triton patch skipped: {e}", flush=True)


def _create_pipeline(config_file: str):
    from hydra.utils import instantiate
    from omegaconf import OmegaConf

    config = OmegaConf.load(config_file)
    config.rendering_engine = "pytorch3d"
    config.compile_model = False
    config.workspace_dir = os.path.dirname(config_file)
    return instantiate(config)


def get_pipeline():
    """Initialise the SAM-3D pipeline on first call (per worker)."""
    global _pipeline
    if _pipeline is not None:
        return _pipeline

    import torch
    from huggingface_hub import snapshot_download

    _patch_xformers_triton_compat()

    if torch.cuda.is_available() and torch.cuda.get_device_properties(0).major >= 8:
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
    torch.set_float32_matmul_precision("high")

    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    config_path = CACHE_ROOT / "checkpoints" / "pipeline.yaml"
    # Skip the HF ETag re-validation (5–20s) when the checkpoint is already
    # present on the network volume. Set FORCE_SAM3D_REFRESH=1 to refresh.
    force_refresh = os.environ.get("FORCE_SAM3D_REFRESH", "0").lower() in ("1", "true", "yes")
    if force_refresh or not config_path.exists():
        t0 = time.time()
        snapshot_download(
            SAM3D_REPO_ID,
            revision="main",
            local_dir=str(CACHE_ROOT),
            local_dir_use_symlinks=False,
        )
        print(f"[runpod-sam3d] snapshot_download took {time.time() - t0:.1f}s", flush=True)
    else:
        print(f"[runpod-sam3d] Using cached checkpoint at {CACHE_ROOT}", flush=True)

    _pipeline = _create_pipeline(str(config_path))
    print("[runpod-sam3d] Pipeline loaded", flush=True)
    return _pipeline


# ---------------------------------------------------------------------------
# Image / mask loading helpers
# ---------------------------------------------------------------------------


def _load_pil_from_input(image_url: str | None, image_b64: str | None):
    """Load a PIL image from either a URL or a raw / data-url base64 string."""
    from PIL import Image as PILImage

    if image_b64:
        data = base64.b64decode(image_b64)
        return PILImage.open(io.BytesIO(data))

    if not image_url:
        raise ValueError("Either image_url or image_b64 must be provided")

    if image_url.startswith("data:"):
        # data:[<mediatype>][;base64],<data>
        try:
            header, payload = image_url.split(",", 1)
        except ValueError as e:
            raise ValueError("Malformed data URL") from e
        if ";base64" in header:
            return PILImage.open(io.BytesIO(base64.b64decode(payload)))
        # URL-encoded text payload; not expected here, but handle for safety.
        import urllib.parse
        return PILImage.open(io.BytesIO(urllib.parse.unquote_to_bytes(payload)))

    import requests

    r = requests.get(image_url, timeout=60)
    r.raise_for_status()
    return PILImage.open(io.BytesIO(r.content))


def _load_mask_array(mask_url: str | None, mask_b64: str | None):
    import numpy as np

    pil = _load_pil_from_input(mask_url, mask_b64)
    if pil.mode != "L":
        pil = pil.convert("L")
    return (np.array(pil) > 127).astype(np.uint8)


# ---------------------------------------------------------------------------
# Binary encoders (kept identical to app.py for frontend compatibility)
# ---------------------------------------------------------------------------


def _encode_voxels_binary(coords_np, colors_list):
    import numpy as np

    if coords_np is None or len(coords_np) == 0:
        return "", None, None

    if coords_np.ndim == 2 and coords_np.shape[1] >= 4:
        coords_np = coords_np[:, 1:4]

    coords_min = coords_np.min(axis=0)
    coords_max = coords_np.max(axis=0)
    coords_range = coords_max - coords_min
    coords_range[coords_range == 0] = 1

    coords_normalized = ((coords_np - coords_min) / coords_range * 255).astype(np.uint8)

    if colors_list and len(colors_list) > 0:
        colors_arr = np.array(colors_list, dtype=np.uint8)
        if colors_arr.ndim == 2 and colors_arr.shape[1] == 4:
            colors_arr = colors_arr[:, :3]
        elif colors_arr.ndim == 2 and colors_arr.shape[1] != 3:
            colors_arr = np.full((len(coords_np), 3), 128, dtype=np.uint8)
    else:
        colors_arr = np.full((len(coords_np), 3), 128, dtype=np.uint8)

    if len(colors_arr) < len(coords_np):
        padding = np.full((len(coords_np) - len(colors_arr), 3), 128, dtype=np.uint8)
        colors_arr = np.vstack([colors_arr, padding])

    packed = np.empty((len(coords_np), 6), dtype=np.uint8)
    packed[:, :3] = coords_normalized
    packed[:, 3:] = colors_arr[: len(coords_np), :3]

    return (
        base64.b64encode(packed.tobytes()).decode("ascii"),
        coords_min.tolist(),
        coords_max.tolist(),
    )


def _encode_mesh_binary(vertices, faces, vertex_colors):
    import numpy as np

    if vertices is None or len(vertices) == 0:
        return None, None, None, None, None

    vertices_np = vertices if isinstance(vertices, np.ndarray) else np.array(vertices)
    faces_np = faces if isinstance(faces, np.ndarray) else np.array(faces)

    v_min = vertices_np.min(axis=0)
    v_max = vertices_np.max(axis=0)

    vertices_b64 = base64.b64encode(vertices_np.astype(np.float32).tobytes()).decode("ascii")
    faces_b64 = base64.b64encode(faces_np.astype(np.uint32).tobytes()).decode("ascii")

    colors_b64 = None
    if vertex_colors is not None and len(vertex_colors) > 0:
        colors_np = (
            vertex_colors if isinstance(vertex_colors, np.ndarray) else np.array(vertex_colors)
        )
        if colors_np.max() <= 1.0:
            colors_np = (colors_np * 255).astype(np.uint8)
        else:
            colors_np = colors_np.astype(np.uint8)
        colors_b64 = base64.b64encode(colors_np.tobytes()).decode("ascii")

    return vertices_b64, faces_b64, colors_b64, v_min.tolist(), v_max.tolist()


# ---------------------------------------------------------------------------
# Pipeline runner (executed in a worker thread; pushes events into a queue)
# ---------------------------------------------------------------------------


def _run_pipeline(job_input: dict[str, Any], progress_queue: "queue.Queue[dict | None]") -> None:
    import numpy as np
    import torch

    try:
        progress_queue.put({"stage": "loading", "progress": 0.01, "message": "Loading image..."})

        image_pil = _load_pil_from_input(
            job_input.get("image_url"), job_input.get("image_b64")
        )
        image_rgb = np.array(image_pil.convert("RGB"))

        mask_urls = job_input.get("mask_urls") or []
        mask_b64_list = job_input.get("mask_b64") or []
        if mask_urls or mask_b64_list:
            mask = _load_mask_array(
                mask_urls[0] if mask_urls else None,
                mask_b64_list[0] if mask_b64_list else None,
            )
        else:
            mask = np.ones(image_rgb.shape[:2], dtype=np.uint8)

        progress_queue.put(
            {"stage": "preprocessing", "progress": 0.03, "message": "Preparing pipeline..."}
        )

        mask_uint8 = mask.astype(np.uint8) * 255
        merged = np.concatenate([image_rgb[..., :3], mask_uint8[..., None]], axis=-1)

        seed = job_input.get("seed")
        if seed is not None:
            torch.manual_seed(int(seed))

        stream_geom_every = int(job_input.get("stream_geometry_every", 1))
        stream_colors_every = int(job_input.get("stream_colors_every", 1))

        # Per-request override for the VOXELS_ONLY env default. When true,
        # we abort pipeline.run() right after the final appearance step.
        voxels_only_in = job_input.get("voxels_only")
        if voxels_only_in is None:
            voxels_only = VOXELS_ONLY_DEFAULT
        else:
            voxels_only = bool(voxels_only_in)

        geometry_step_counter = [0]
        appearance_step_counter = [0]

        # The sam-3d-objects callbacks are inconsistent across stages about
        # whether `step` is 0-indexed (last call has step == total_steps - 1)
        # or 1-indexed (last call has step == total_steps). Treat either as
        # "final" so:
        #   1. the decimation filter never swallows the last fully-refined event,
        #   2. the voxels_only abort actually fires once per stage.
        def _is_final(step: int, total_steps: int) -> bool:
            if total_steps <= 0:
                return True
            return step >= total_steps - 1

        def geometry_callback(stage, step, total_steps, coords, latent, colors=None, **kwargs):
            geometry_step_counter[0] += 1
            is_final = _is_final(step, total_steps)
            if geometry_step_counter[0] % stream_geom_every != 0 and not is_final:
                return

            coords_np = None
            if coords is not None and len(coords) > 0:
                coords_np = coords.cpu().numpy() if hasattr(coords, "cpu") else np.array(coords)

            progress = 0.05 + (step / max(total_steps, 1)) * 0.45
            voxel_data, bounds_min, bounds_max = _encode_voxels_binary(coords_np, None)

            progress_queue.put(
                {
                    "stage": "geometry",
                    "step": step,
                    "total_steps": total_steps,
                    "progress": progress,
                    "voxel_data": voxel_data,
                    "bounds_min": bounds_min,
                    "bounds_max": bounds_max,
                    "voxel_count": len(coords_np) if coords_np is not None else 0,
                    "encoding": "binary_uint8_xyzrgb",
                }
            )

        def appearance_callback(stage, step, total_steps, coords, colors=None, latent=None, **kwargs):
            appearance_step_counter[0] += 1
            is_final = _is_final(step, total_steps)
            if appearance_step_counter[0] % stream_colors_every != 0 and not is_final:
                return

            progress = 0.5 + (step / max(total_steps, 1)) * 0.45
            coords_np = coords.cpu().numpy() if hasattr(coords, "cpu") else np.array(coords)
            colors_list = None
            if colors is not None:
                colors_list = (
                    colors.cpu().numpy().tolist() if hasattr(colors, "cpu") else colors.tolist()
                )

            voxel_data, bounds_min, bounds_max = _encode_voxels_binary(coords_np, colors_list)

            progress_queue.put(
                {
                    "stage": "appearance",
                    "step": step,
                    "total_steps": total_steps,
                    "progress": progress,
                    "voxel_data": voxel_data,
                    "bounds_min": bounds_min,
                    "bounds_max": bounds_max,
                    "voxel_count": len(coords_np),
                    "encoding": "binary_uint8_xyzrgb",
                }
            )

            # Short-circuit: once the final appearance step has been emitted,
            # abort pipeline.run() so we don't spend ~30s on mesh decoding +
            # GLB export. The exception is caught around pipeline.run() below.
            if voxels_only and is_final:
                raise _VoxelsOnlyAbort()

        def decode_callback(stage, **kwargs):
            if stage == "mesh_preview":
                vertices = kwargs.get("vertices")
                faces = kwargs.get("faces")
                vertex_colors = kwargs.get("vertex_colors")
                vertices_b64, faces_b64, colors_b64, v_min, v_max = _encode_mesh_binary(
                    vertices, faces, vertex_colors
                )
                progress_queue.put(
                    {
                        "stage": "mesh_preview",
                        "progress": 0.92,
                        "message": "Mesh decoded - preview available!",
                        "vertices_data": vertices_b64,
                        "faces_data": faces_b64,
                        "vertex_colors_data": colors_b64,
                        "bounds_min": v_min,
                        "bounds_max": v_max,
                        "vertex_count": len(vertices) if vertices is not None else 0,
                        "face_count": len(faces) if faces is not None else 0,
                    }
                )
            elif stage == "glb_ready":
                glb_bytes = kwargs.get("glb_bytes")
                if glb_bytes:
                    progress_queue.put(
                        {
                            "stage": "glb_ready",
                            "progress": 0.98,
                            "message": "Final GLB ready!",
                            "glb_data": base64.b64encode(glb_bytes).decode("ascii"),
                            "glb_size_bytes": len(glb_bytes),
                        }
                    )

        progress_queue.put(
            {
                "stage": "geometry_start",
                "progress": 0.05,
                "message": "Starting geometry diffusion...",
            }
        )

        pipeline = get_pipeline()
        try:
            outputs = pipeline.run(
                merged,
                None,
                seed,
                stage1_only=False,
                with_mesh_postprocess=False,
                with_texture_baking=False,
                with_layout_postprocess=True,
                use_vertex_color=True,
                geometry_callback=geometry_callback,
                appearance_callback=appearance_callback,
                decode_callback=decode_callback,
            )
        except _VoxelsOnlyAbort:
            # Voxels are already streamed; skip mesh/GLB/splat entirely.
            progress_queue.put(
                {
                    "stage": "complete",
                    "progress": 1.0,
                    "message": "Voxels complete (mesh/GLB skipped)",
                    "voxels_only": True,
                }
            )
            progress_queue.put(None)
            return

        progress_queue.put(
            {
                "stage": "finalizing",
                "progress": 0.95,
                "message": "Generating final assets...",
            }
        )

        with TemporaryDirectory() as temp_dir:
            complete_event: dict[str, Any] = {
                "stage": "complete",
                "progress": 1.0,
                "message": "Complete!",
            }

            # Gaussian splat: typically 30–100 MB. Disabled by default to stay
            # under RunPod's aggregate output cap; opt in via MAX_INLINE_SPLAT_BYTES.
            gs = outputs.get("gs") if isinstance(outputs, dict) else None
            if gs is not None and MAX_INLINE_SPLAT_BYTES > 0:
                splat_path = os.path.join(temp_dir, "splat.ply")
                gs.save_ply(splat_path)
                splat_bytes = Path(splat_path).read_bytes()
                if len(splat_bytes) <= MAX_INLINE_SPLAT_BYTES:
                    splat_b64 = base64.b64encode(splat_bytes).decode("ascii")
                    complete_event["gaussian_splat_url"] = (
                        f"data:application/octet-stream;base64,{splat_b64}"
                    )
                    complete_event["splat_size_bytes"] = len(splat_bytes)
                else:
                    complete_event["splat_skipped_reason"] = (
                        f"splat {len(splat_bytes)} bytes exceeds MAX_INLINE_SPLAT_BYTES"
                        f" ({MAX_INLINE_SPLAT_BYTES})"
                    )
            elif gs is not None:
                complete_event["splat_skipped_reason"] = (
                    "splat inlining disabled (set MAX_INLINE_SPLAT_BYTES > 0 to enable)"
                )

            # GLB (inline as data URL — the frontend uses it for the download
            # button). Skipped if it would push the response over the cap.
            glb_obj = outputs.get("glb") if isinstance(outputs, dict) else None
            if glb_obj is not None:
                glb_path = os.path.join(temp_dir, "model.glb")
                glb_obj.export(glb_path)
                glb_bytes = Path(glb_path).read_bytes()
                if len(glb_bytes) <= MAX_INLINE_GLB_BYTES:
                    glb_b64 = base64.b64encode(glb_bytes).decode("ascii")
                    complete_event["model_glb_url"] = (
                        f"data:model/gltf-binary;base64,{glb_b64}"
                    )
                    complete_event["glb_size_bytes"] = len(glb_bytes)
                else:
                    complete_event["glb_skipped_reason"] = (
                        f"glb {len(glb_bytes)} bytes exceeds MAX_INLINE_GLB_BYTES"
                        f" ({MAX_INLINE_GLB_BYTES})"
                    )
                    complete_event["glb_size_bytes"] = len(glb_bytes)

            progress_queue.put(complete_event)

        progress_queue.put(None)

    except Exception as e:  # noqa: BLE001
        progress_queue.put(
            {
                "stage": "error",
                "error": str(e),
                "traceback": traceback.format_exc(),
            }
        )
        progress_queue.put(None)


# ---------------------------------------------------------------------------
# RunPod handler (generator → emits one dict per stream chunk)
# ---------------------------------------------------------------------------


def handler(job: dict[str, Any]) -> Iterable[dict[str, Any]]:
    """RunPod generator handler. Yields one event per progress update."""
    job_input = job.get("input") or {}
    if not isinstance(job_input, dict):
        yield {"stage": "error", "error": "Job input must be an object"}
        return

    # Pre-warm pipeline before signalling readiness so first event from the
    # worker thread isn't blocked on a multi-GB checkpoint download.
    try:
        get_pipeline()
    except Exception as e:  # noqa: BLE001
        yield {
            "stage": "error",
            "error": f"Pipeline initialisation failed: {e}",
            "traceback": traceback.format_exc(),
        }
        return

    progress_queue: queue.Queue[dict | None] = queue.Queue(maxsize=64)

    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(_run_pipeline, job_input, progress_queue)

    try:
        while True:
            try:
                update = progress_queue.get(timeout=180)
            except queue.Empty:
                if future.done():
                    break
                # Heartbeat so client/proxy connections stay open
                yield {"heartbeat": True}
                continue

            if update is None:
                break
            yield update
    finally:
        executor.shutdown(wait=False)


if __name__ == "__main__":
    # Pre-load the pipeline at startup so the first job doesn't pay the
    # ~30–60s model-load cost. With this in place, RunPod will only mark
    # the worker "ready" once weights are on GPU.
    if os.environ.get("PRELOAD_PIPELINE", "1").lower() not in ("0", "false", "no"):
        t0 = time.time()
        try:
            get_pipeline()
            print(f"[runpod-sam3d] Preload complete in {time.time() - t0:.1f}s", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"[runpod-sam3d] Preload failed (will retry per-job): {e}", flush=True)

    runpod.serverless.start(
        {
            "handler": handler,
            "return_aggregate_stream": True,
        }
    )
