"""
SAM-3D Objects Streaming Demo

A minimal streaming endpoint for real-time 3D reconstruction visualization.
Streams voxel data during geometry and appearance diffusion stages.
"""
import base64
import json
import os
import queue
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

import fal
from fal.container import ContainerImage
from fal.exceptions import FieldException
from fal.toolkit import FAL_PERSISTENT_DIR, File, Image
from fastapi import Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, root_validator

# Simplified Dockerfile - only SAM-3D Objects dependencies
dockerfile_str = r"""
FROM nvidia/cuda:12.8.0-cudnn-devel-ubuntu22.04
ENV TZ=Etc/UTC DEBIAN_FRONTEND=noninteractive
ENV PYOPENGL_PLATFORM=osmesa

RUN apt-get update && apt-get install -y --no-install-recommends software-properties-common && \
    add-apt-repository -y ppa:deadsnakes/ppa && \
    apt-get update && apt-get install -y --fix-missing --no-install-recommends \
        python3.11 python3.11-dev python3.11-distutils python3.11-venv python3-pybind11 \
        build-essential cmake ninja-build curl git ca-certificates \
        libgl1 libglib2.0-0 libsm6 libxext6 libglew-dev libopenexr-dev libboost-all-dev \
        libegl1-mesa-dev libgl1-mesa-glx libgl1-mesa-dri libosmesa6 libosmesa6-dev mesa-utils && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 && \
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11

ENV CUDA_HOME=/usr/local/cuda PATH=$CUDA_HOME/bin:$PATH LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH
ENV TORCH_CUDA_ARCH_LIST="8.0 8.6 8.9 9.0 10.0+PTX"

RUN pip install --no-cache-dir numpy==1.26.4 scipy==1.14.1
RUN pip install --no-cache-dir --ignore-installed blinker==1.8.2
RUN pip install --no-cache-dir torch==2.8.0 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128

# Core dependencies
RUN pip install --no-cache-dir opencv-python setuptools==69.5.1 matplotlib einops \
    huggingface_hub fastapi pydantic gsplat==1.5.3 \
    hydra-core==1.3.2 omegaconf trimesh pyrootutils pytorch-lightning pyrender roma \
    timm dill rich networkx==3.2.1 joblib appdirs loguru optree fvcore jaxtyping

# Clone forked sam-3d-objects with streaming callback support
# Cache bust: change this value to force re-clone
ARG SAM3D_CACHE_BUST=v10
RUN git clone https://github.com/rehan-remade/sam-3d-objects.git && cd sam-3d-objects && \
    grep -Ev '^(torch|torchvision|torchaudio|pytorch3d|nvidia-|numpy|scipy|blinker)' requirements.txt > /tmp/reqs.txt && \
    pip install --no-cache-dir -r /tmp/reqs.txt && pip install -e . --no-deps

RUN pip install --no-cache-dir kaolin==0.18.0 -f https://nvidia-kaolin.s3.us-east-2.amazonaws.com/torch-2.8.0_cu128.html
RUN pip install --no-cache-dir git+https://github.com/microsoft/MoGe.git@a8c37341bc0325ca99b9d57981cc3bb2bd3e255b

# PyTorch3D, xformers, flash-attention
RUN pip install --no-cache-dir torch==2.8.0 torchvision torchaudio xformers==0.0.32.post1 --index-url https://download.pytorch.org/whl/cu128 && \
    pip install --no-cache-dir --force-reinstall numpy==1.26.4 scipy==1.14.1 && \
    pip install --no-cache-dir https://github.com/MiroPsota/torch_packages_builder/releases/download/pytorch3d-0.7.8%2B5043d15/pytorch3d-0.7.8+5043d15pt2.8.0cu128-cp311-cp311-linux_x86_64.whl && \
    pip install --no-cache-dir https://github.com/Dao-AILab/flash-attention/releases/download/v2.8.3/flash_attn-2.8.3+cu12torch2.8cxx11abiTRUE-cp311-cp311-linux_x86_64.whl && \
    python -c "from pytorch3d.renderer import look_at_view_transform; print('pytorch3d loaded successfully')"

RUN pip install --no-cache-dir --upgrade 'PyOpenGL>=3.1.7'
ENV LIDRA_SKIP_INIT=true
"""

SAM3D_OBJECTS_CACHE_DIR = FAL_PERSISTENT_DIR / "sam3d_objects"


# ─────────────────────────────────────────────────────────────────────────────
# Input Models
# ─────────────────────────────────────────────────────────────────────────────


class PointPromptBase(BaseModel):
    x: int | None = Field(default=None, description="X Coordinate of the prompt")
    y: int | None = Field(default=None, description="Y Coordinate of the prompt")
    label: Literal[0, 1] | None = Field(
        default=None, description="1 for foreground, 0 for background"
    )


class BoxPromptBase(BaseModel):
    x_min: int | None = Field(default=None, description="X Min Coordinate of the box")
    y_min: int | None = Field(default=None, description="Y Min Coordinate of the box")
    x_max: int | None = Field(default=None, description="X Max Coordinate of the box")
    y_max: int | None = Field(default=None, description="Y Max Coordinate of the box")


class SAM3DStreamInput(BaseModel):
    """Input for streaming 3D reconstruction endpoint."""

    image_url: str = Field(
        description="URL of the image to reconstruct in 3D",
        examples=[
            "https://v3b.fal.media/files/b/0a8439e5/TyAmfW5w_sqRXRzWVBGsW_car.jpeg"
        ],
    )
    mask_urls: list[str] = Field(
        default_factory=list,
        description="Optional list of mask URLs. If not provided, uses prompt for auto-segmentation.",
    )
    prompt: str | None = Field(
        default="car",
        description="Text prompt for auto-segmentation (e.g., 'chair', 'lamp')",
        ui={"important": True},
    )
    point_prompts: list[PointPromptBase] | None = Field(
        default=[],
        description="Point prompts for auto-segmentation",
    )
    box_prompts: list[BoxPromptBase] = Field(
        default=[],
        description="Box prompts for auto-segmentation",
    )
    seed: int | None = Field(
        default=None,
        description="Random seed for reproducibility",
    )
    stream_geometry_every: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Emit geometry updates every N steps (1=smoothest, 10=fastest)",
    )
    stream_colors_every: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Emit color updates every N steps",
    )

    @root_validator(pre=True)
    def backward_compat(cls, values):
        if isinstance(values.get("box_prompts"), dict):
            values["box_prompts"] = [values["box_prompts"]]
        if values.get("box_prompts") is None:
            values["box_prompts"] = []
        return values


# ─────────────────────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────────────────────


class SAM3DStreamApp(
    fal.App,
    keep_alive=600,
    kind="container",
    image=ContainerImage.from_dockerfile_str(dockerfile_str, builder="depot"),
    name="sam-3d-stream",
    request_timeout=300,
    max_concurrency=1,
    min_concurrency=0,
):
    machine_type = "GPU-H100"

    @staticmethod
    def _patch_xformers_triton_compat():
        """Patch triton/xformers compatibility for PyTorch 2.8+."""
        try:
            from triton.runtime import jit as triton_jit

            if not hasattr(triton_jit.JITFunction, "_unsafe_update_src"):
                return

            import xformers.triton.vararg_kernel as vararg_kernel

            def patched_unroll_varargs(kernel, N):
                import copy

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
            print("[sam3d-stream] Applied xformers/triton compatibility patch")
        except ImportError:
            pass
        except Exception as e:
            print(f"[sam3d-stream] Warning: Could not apply xformers/triton patch: {e}")

    def setup(self):
        import torch
        from huggingface_hub import snapshot_download

        self._patch_xformers_triton_compat()

        if torch.cuda.is_available() and torch.cuda.get_device_properties(0).major >= 8:
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
        torch.set_float32_matmul_precision("high")

        # Download SAM-3D Objects checkpoint
        snapshot_download(
            "jetjodh/sam-3d-objects",
            revision="main",
            local_dir=str(SAM3D_OBJECTS_CACHE_DIR),
            local_dir_use_symlinks=False,
        )

        # Create pipeline
        config_path = Path(SAM3D_OBJECTS_CACHE_DIR) / "checkpoints" / "pipeline.yaml"
        self.pipeline = self._create_pipeline(str(config_path))
        print("[sam3d-stream] Pipeline loaded successfully!")

    @staticmethod
    def _create_pipeline(config_file: str):
        """Create SAM-3D Objects inference pipeline."""
        from hydra.utils import instantiate
        from omegaconf import OmegaConf

        config = OmegaConf.load(config_file)
        config.rendering_engine = "pytorch3d"
        config.compile_model = False
        config.workspace_dir = os.path.dirname(config_file)
        return instantiate(config)

    def _load_image(self, image_url: str):
        try:
            image = Image(url=image_url)
            return image.to_pil()
        except Exception as exc:
            raise FieldException(
                "image_url", "Failed to read or process the image."
            ) from exc

    def _load_mask_from_url(self, mask_url: str):
        """Load mask from URL and convert to binary numpy array."""
        import numpy as np

        try:
            mask_image = Image(url=mask_url)
            mask_pil = mask_image.to_pil()
            if mask_pil.mode != "L":
                mask_pil = mask_pil.convert("L")
            mask_array = np.array(mask_pil)
            return (mask_array > 127).astype(np.uint8)
        except Exception as exc:
            raise FieldException("mask_url", f"Failed to load mask: {str(exc)[:200]}") from exc

    @fal.endpoint("/stream")
    def stream_3d_reconstruction(
        self, input: SAM3DStreamInput, request: Request, response: Response
    ):
        """
        🎬 Stream 3D reconstruction with real-time voxel visualization!

        SSE Events:
        - loading: Initial setup
        - geometry: Voxel coords + colors (Stage 1 diffusion)
        - appearance: Voxel coords + refined colors (Stage 2 diffusion)
        - mesh_preview: Vertex-colored mesh (instant preview)
        - glb_ready: Final textured GLB
        - complete: Final URLs
        """
        import numpy as np
        import torch

        progress_queue = queue.Queue(maxsize=50)

        def encode_voxels_binary(coords_np, colors_list):
            """Pack voxels as uint8: [x,y,z,r,g,b] per voxel. Returns base64 string."""
            if coords_np is None or len(coords_np) == 0:
                return "", None, None

            # Handle 4D coords [batch_idx, x, y, z] -> take only xyz
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

        def encode_mesh_binary(vertices, faces, vertex_colors):
            """Encode mesh as binary for streaming."""
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
                colors_np = vertex_colors if isinstance(vertex_colors, np.ndarray) else np.array(vertex_colors)
                if colors_np.max() <= 1.0:
                    colors_np = (colors_np * 255).astype(np.uint8)
                else:
                    colors_np = colors_np.astype(np.uint8)
                colors_b64 = base64.b64encode(colors_np.tobytes()).decode("ascii")

            return vertices_b64, faces_b64, colors_b64, v_min.tolist(), v_max.tolist()

        def run_streaming():
            try:
                progress_queue.put({"stage": "loading", "progress": 0.01, "message": "Loading image..."})

                image_pil = self._load_image(input.image_url)
                image_rgb = np.array(image_pil.convert("RGB"))

                # Get mask
                if input.mask_urls:
                    mask = self._load_mask_from_url(input.mask_urls[0])
                else:
                    mask = np.ones(image_rgb.shape[:2], dtype=np.uint8)

                progress_queue.put({"stage": "preprocessing", "progress": 0.03, "message": "Preparing pipeline..."})

                # Merge image + mask to RGBA
                mask_uint8 = mask.astype(np.uint8) * 255
                merged = np.concatenate([image_rgb[..., :3], mask_uint8[..., None]], axis=-1)

                if input.seed is not None:
                    torch.manual_seed(input.seed)

                # Callbacks
                geometry_step_counter = [0]
                appearance_step_counter = [0]

                def geometry_callback(stage, step, total_steps, coords, latent, colors=None, **kwargs):
                    geometry_step_counter[0] += 1
                    if geometry_step_counter[0] % input.stream_geometry_every != 0:
                        if step != total_steps:
                            return

                    coords_np = None
                    if coords is not None and len(coords) > 0:
                        coords_np = coords.cpu().numpy() if hasattr(coords, "cpu") else np.array(coords)

                    progress = 0.05 + (step / total_steps) * 0.45
                    voxel_data, bounds_min, bounds_max = encode_voxels_binary(coords_np, None)

                    progress_queue.put({
                        "stage": "geometry",
                        "step": step,
                        "total_steps": total_steps,
                        "progress": progress,
                        "voxel_data": voxel_data,
                        "bounds_min": bounds_min,
                        "bounds_max": bounds_max,
                        "voxel_count": len(coords_np) if coords_np is not None else 0,
                        "encoding": "binary_uint8_xyzrgb",
                    })

                def appearance_callback(stage, step, total_steps, coords, colors=None, latent=None, **kwargs):
                    appearance_step_counter[0] += 1
                    if appearance_step_counter[0] % input.stream_colors_every != 0:
                        if step != total_steps:
                            return

                    progress = 0.5 + (step / total_steps) * 0.45
                    coords_np = coords.cpu().numpy() if hasattr(coords, "cpu") else np.array(coords)
                    colors_list = None
                    if colors is not None:
                        colors_list = colors.cpu().numpy().tolist() if hasattr(colors, "cpu") else colors.tolist()

                    voxel_data, bounds_min, bounds_max = encode_voxels_binary(coords_np, colors_list)

                    progress_queue.put({
                        "stage": "appearance",
                        "step": step,
                        "total_steps": total_steps,
                        "progress": progress,
                        "voxel_data": voxel_data,
                        "bounds_min": bounds_min,
                        "bounds_max": bounds_max,
                        "voxel_count": len(coords_np),
                        "encoding": "binary_uint8_xyzrgb",
                    })

                def decode_callback(stage, **kwargs):
                    if stage == "mesh_preview":
                        vertices = kwargs.get("vertices")
                        faces = kwargs.get("faces")
                        vertex_colors = kwargs.get("vertex_colors")
                        vertices_b64, faces_b64, colors_b64, v_min, v_max = encode_mesh_binary(vertices, faces, vertex_colors)
                        progress_queue.put({
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
                        })
                    elif stage == "glb_ready":
                        glb_bytes = kwargs.get("glb_bytes")
                        if glb_bytes:
                            progress_queue.put({
                                "stage": "glb_ready",
                                "progress": 0.98,
                                "message": "Final GLB ready!",
                                "glb_data": base64.b64encode(glb_bytes).decode("ascii"),
                                "glb_size_bytes": len(glb_bytes),
                            })

                # Run pipeline
                progress_queue.put({"stage": "geometry_start", "progress": 0.05, "message": "Starting geometry diffusion..."})

                outputs = self.pipeline.run(
                    merged,
                    None,
                    input.seed,
                    stage1_only=False,
                    with_mesh_postprocess=False,
                    with_texture_baking=False,
                    with_layout_postprocess=True,
                    use_vertex_color=True,
                    geometry_callback=geometry_callback,
                    appearance_callback=appearance_callback,
                    decode_callback=decode_callback,
                )

                # Finalize
                progress_queue.put({"stage": "finalizing", "progress": 0.95, "message": "Generating final assets..."})

                with TemporaryDirectory() as temp_dir:
                    gs = outputs["gs"]
                    splat_path = os.path.join(temp_dir, "splat.ply")
                    gs.save_ply(splat_path)
                    splat_file = File.from_path(
                        path=splat_path,
                        multipart=True,
                        request=request,
                    )

                    glb_url = None
                    if outputs.get("glb"):
                        glb_path = os.path.join(temp_dir, "model.glb")
                        outputs["glb"].export(glb_path)
                        glb_file = File.from_path(
                            path=glb_path,
                            content_type="model/gltf-binary",
                            multipart=True,
                            request=request,
                        )
                        glb_url = glb_file.url

                    progress_queue.put({
                        "stage": "complete",
                        "progress": 1.0,
                        "message": "Complete!",
                        "gaussian_splat_url": splat_file.url,
                        "model_glb_url": glb_url,
                    })

                progress_queue.put(None)

            except Exception as e:
                import traceback
                progress_queue.put({
                    "stage": "error",
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                })
                progress_queue.put(None)

        def event_stream():
            executor = ThreadPoolExecutor(max_workers=1)
            future = executor.submit(run_streaming)

            while True:
                try:
                    update = progress_queue.get(timeout=180)
                    if update is None:
                        break
                    yield f"data: {json.dumps(update)}\n\n"
                except queue.Empty:
                    if future.done():
                        break
                    yield f"data: {json.dumps({'heartbeat': True})}\n\n"

            executor.shutdown(wait=False)

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "x-fal-sse-last-event-as-body": "1",
                "Cache-Control": "no-cache",
            },
        )


if __name__ == "__main__":
    app = fal.wrap_app(SAM3DStreamApp)
    app()

