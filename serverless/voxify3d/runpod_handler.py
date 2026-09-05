"""
Voxify3D voxelization handler for RunPod Serverless.

Runs the official Voxify3D pipeline (https://github.com/yichuanH/Voxify3D_official)
on a GLB file and returns the stylized, palette-constrained voxel grid as
`.xyzrgb` content (one "x y z r g b" line per voxel, RGB in 0-255), the same
format the BrickBuilder backend uses for its brick pipeline.

Pipeline stages (mirrors `Run_Voxify3D_glb.py` from the official repo):
    1. Blender renders ~100 orthographic views of the GLB (`glb2img.py`).
    2. `execute_gumbel_color_palette.py` runs the PixelArt stage, coarse DVGO
       ortho training, and the 6-view color-palette fine-tuning.
    3. The resulting `{scene}_6views.npz` (alpha grid + palette logits) and
       `color_palette.npz` are converted to xyzrgb voxels.

Input schema (job["input"]):
    {
        "glb_url": str | None,       # http(s) URL to a GLB file
        "glb_b64": str | None,       # alternative: base64-encoded GLB bytes
        "cell_size": int = 30,       # Voxify3D pixel-art cell size; the voxel
                                     #   grid resolution is ~(1200 / cell_size)
        "palette_mode": str = "kmeans_rare",  # kmeans|kmeans_rare|maxmin|mediancut|sa
        "color_num": int = 6,        # palette size
        "alpha_threshold": float = 0.78,      # occupancy threshold on the alpha grid
    }

Output: generator yielding dicts. Progress events look like
`{"stage": "render", "message": ...}`; the final event is
`{"stage": "complete", "xyzrgb_gz_b64": ..., "voxel_count": ..., "palette": ...}`
where `xyzrgb_gz_b64` is base64(gzip(xyzrgb text)). Errors are reported as
`{"stage": "error", "error": ...}`.

Model checkpoints: the four PixelArt checkpoints Voxify3D depends on are not
bundled in the image. At cold start they are downloaded from the Hugging Face
repo named by VOXIFY3D_HF_REPO (see README.md for the expected layout) into
VOXIFY3D_CACHE_DIR (mount a RunPod Network Volume at /runpod-volume so they
persist across cold starts) and copied into the PixelArt directories.
"""

from __future__ import annotations

import base64
import gzip
import os
import shutil
import subprocess
import time
import traceback
import uuid
from pathlib import Path

import numpy as np
import requests
import runpod

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_ROOT = Path(os.environ.get("VOXIFY3D_REPO_DIR", "/workspace/Voxify3D_official"))
CACHE_ROOT = Path(os.environ.get("VOXIFY3D_CACHE_DIR", "/runpod-volume/voxify3d"))
BLENDER_EXE = os.environ.get("VOXIFY3D_BLENDER_EXE", "blender")
HF_REPO_ID = os.environ.get("VOXIFY3D_HF_REPO", "")

DATA_ROOT = "GLB"
N_VIEWS = int(os.environ.get("VOXIFY3D_N_VIEWS", "100"))
RENDER_RES = int(os.environ.get("VOXIFY3D_RENDER_RES", "1200"))

# Checkpoints expected by the Voxify3D PixelArt stage, relative to PixelArt/.
# See https://github.com/yichuanH/Voxify3D_official#pretrained-models — the
# files come from WuZongWei6/Pixelization and carry a non-commercial license.
PIXELART_CHECKPOINTS = (
    "pixelart_vgg19.pth",
    "alias_net.pth",
    "checkpoints/pixel_model/160_net_G_A.pth",
    "checkpoints/pixel_model/160_net_G_B.pth",
)

_checkpoints_ready = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_checkpoints() -> None:
    """Download the PixelArt checkpoints (once) and place them in the repo."""
    global _checkpoints_ready
    if _checkpoints_ready:
        return

    pixelart_dir = REPO_ROOT / "PixelArt"
    if all((pixelart_dir / rel).exists() for rel in PIXELART_CHECKPOINTS):
        _checkpoints_ready = True
        return

    if not HF_REPO_ID:
        raise RuntimeError(
            "PixelArt checkpoints are missing and VOXIFY3D_HF_REPO is not set. "
            "Mirror the Voxify3D PixelArt checkpoints to a Hugging Face repo "
            "(see serverless/voxify3d/README.md) and set VOXIFY3D_HF_REPO."
        )

    from huggingface_hub import snapshot_download

    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    snapshot_dir = Path(
        snapshot_download(
            repo_id=HF_REPO_ID,
            local_dir=str(CACHE_ROOT / "pixelart_checkpoints"),
            token=os.environ.get("HF_TOKEN") or None,
        )
    )

    for rel in PIXELART_CHECKPOINTS:
        src = snapshot_dir / rel
        if not src.exists():
            # Also accept a flat layout (all files at the repo root).
            src = snapshot_dir / Path(rel).name
        if not src.exists():
            raise RuntimeError(
                f"Checkpoint '{rel}' not found in Hugging Face repo '{HF_REPO_ID}'."
            )
        dest = pixelart_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)

    _checkpoints_ready = True


def _fetch_glb(job_input: dict, dest: Path) -> None:
    """Write the input GLB (from URL or base64) to `dest`."""
    glb_url = job_input.get("glb_url")
    glb_b64 = job_input.get("glb_b64")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if glb_b64:
        dest.write_bytes(base64.b64decode(glb_b64))
    elif glb_url:
        response = requests.get(glb_url, timeout=120)
        response.raise_for_status()
        dest.write_bytes(response.content)
    else:
        raise ValueError("Provide 'glb_url' or 'glb_b64' in the job input.")


def _run(command: list[str], cwd: Path) -> None:
    print(f"[voxify3d] Running: {' '.join(command)} (cwd={cwd})")
    subprocess.run(command, cwd=str(cwd), check=True)


def _npz_to_xyzrgb(npz_path: Path, palette_path: Path, alpha_threshold: float) -> tuple[str, int, list]:
    """Convert Voxify3D's output npz files to xyzrgb text.

    Matches `Voxify3D/rgb_coarse_result/save_obj.py`: `alpha` is the occupancy
    grid, `rgb` holds per-voxel palette logits, and `color_palette.npz` stores
    the palette as floats in [0, 1].
    """
    data = np.load(str(npz_path))
    alpha = data["alpha"]
    logits = data["rgb"]
    palette = np.load(str(palette_path))["color_palette"]

    occupied = alpha >= alpha_threshold
    coords = np.argwhere(occupied)
    if len(coords) == 0:
        raise RuntimeError(
            f"No voxels above alpha threshold {alpha_threshold}; try lowering it."
        )

    class_indices = np.argmax(logits[occupied], axis=-1)
    colors = np.clip(np.rint(palette[class_indices] * 255.0), 0, 255).astype(int)

    lines = [
        f"{x} {y} {z} {r} {g} {b}"
        for (x, y, z), (r, g, b) in zip(coords, colors)
    ]
    palette_255 = np.clip(np.rint(palette * 255.0), 0, 255).astype(int).tolist()
    return "\n".join(lines) + "\n", len(coords), palette_255


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

def handler(job):
    job_input = job.get("input") or {}
    scene = f"job{uuid.uuid4().hex[:10]}"
    scene_dir = REPO_ROOT / "Voxify3D" / "data" / DATA_ROOT / scene

    cell_size = int(job_input.get("cell_size", 30))
    palette_mode = str(job_input.get("palette_mode", "kmeans_rare"))
    color_num = int(job_input.get("color_num", 6))
    alpha_threshold = float(job_input.get("alpha_threshold", 0.78))

    if palette_mode not in ("kmeans", "kmeans_rare", "maxmin", "mediancut", "sa"):
        yield {"stage": "error", "error": f"Unknown palette_mode '{palette_mode}'"}
        return

    started = time.time()
    try:
        yield {"stage": "setup", "message": "Preparing checkpoints and input GLB"}
        _ensure_checkpoints()
        _fetch_glb(job_input, scene_dir / f"{scene}.glb")

        # Stage 1: Blender orthographic renders (ortho/ + 6views/).
        yield {"stage": "render", "message": f"Rendering {N_VIEWS} orthographic views"}
        _run(
            [
                BLENDER_EXE, "-b", "-P", "glb2img.py", "--",
                "--input_dir", f"data/{DATA_ROOT}/{scene}",
                "--n_views", str(N_VIEWS),
                "--res", str(RENDER_RES),
            ],
            cwd=REPO_ROOT / "Voxify3D",
        )

        # Stage 2: PixelArt + DVGO ortho training + 6-view palette fine-tuning.
        yield {
            "stage": "optimize",
            "message": (
                f"Running Voxify3D optimization (cell_size={cell_size}, "
                f"palette_mode={palette_mode}, color_num={color_num})"
            ),
        }
        _run(
            [
                "python", "execute_gumbel_color_palette.py",
                "--scene", scene,
                "--cell_size", str(cell_size),
                "--data_root", DATA_ROOT,
                "--gpu", "0",
                "--color_num", str(color_num),
                "--palette_mode", palette_mode,
            ],
            cwd=REPO_ROOT,
        )

        # Stage 3: Convert the exported voxel grid to xyzrgb.
        yield {"stage": "convert", "message": "Converting voxel grid to xyzrgb"}
        result_dir = REPO_ROOT / "Voxify3D" / "rgb_coarse_result" / DATA_ROOT / scene / f"{scene}_6views"
        xyzrgb_content, voxel_count, palette = _npz_to_xyzrgb(
            result_dir / f"{scene}_6views.npz",
            result_dir / "color_palette.npz",
            alpha_threshold,
        )

        yield {
            "stage": "complete",
            "xyzrgb_gz_b64": base64.b64encode(
                gzip.compress(xyzrgb_content.encode("utf-8"))
            ).decode("ascii"),
            "voxel_count": voxel_count,
            "palette": palette,
            "cell_size": cell_size,
            "palette_mode": palette_mode,
            "color_num": color_num,
            "elapsed_s": round(time.time() - started, 2),
        }
    except Exception as exc:  # noqa: BLE001 - report any failure to the caller
        traceback.print_exc()
        yield {"stage": "error", "error": str(exc)}
    finally:
        # Per-job artifacts live in the container-local repo checkout; clean
        # them up so long-lived workers do not fill the disk.
        for path in (
            scene_dir,
            REPO_ROOT / "Voxify3D" / "logs" / DATA_ROOT / scene,
            REPO_ROOT / "Voxify3D" / "rgb_coarse_result" / DATA_ROOT / scene,
            REPO_ROOT / "Voxify3D" / "voxel_result" / DATA_ROOT / scene,
            REPO_ROOT / "Voxify3D" / "configs" / DATA_ROOT / scene,
        ):
            shutil.rmtree(path, ignore_errors=True)


if __name__ == "__main__":
    runpod.serverless.start({
        "handler": handler,
        "return_aggregate_stream": True,
    })
