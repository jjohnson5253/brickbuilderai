"""
Trellis 2 Streaming Demo

A streaming endpoint for real-time 3D reconstruction with PBR materials.
Streams voxel data during sparse structure, shape, and texture diffusion stages.
"""
import base64
import json
import os
import queue
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal, Optional

import fal
from fal.container import ContainerImage
from fal.exceptions import FieldException
from fal.toolkit import FAL_PERSISTENT_DIR, File, Image
from fastapi import Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# Dockerfile for Trellis 2 dependencies
dockerfile_str = r"""
FROM nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04
ENV TZ=Etc/UTC DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common && \
    add-apt-repository -y ppa:deadsnakes/ppa && \
    apt-get update && apt-get install -y --fix-missing --no-install-recommends \
        python3.11 python3.11-dev python3.11-distutils python3.11-venv \
        build-essential cmake ninja-build curl git ca-certificates \
        libgl1 libglib2.0-0 libsm6 libxext6 libglew-dev \
        libegl1-mesa-dev libgl1-mesa-glx libgl1-mesa-dri libosmesa6 \
        libjpeg-dev zlib1g-dev && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 && \
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11

ENV CUDA_HOME=/usr/local/cuda PATH=$CUDA_HOME/bin:$PATH LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH
ENV TORCH_CUDA_ARCH_LIST="8.0 8.6 8.9 9.0+PTX"

# PyTorch 2.6.0 + CUDA 12.4
RUN pip install --no-cache-dir numpy==1.26.4 scipy==1.14.1
RUN pip install --no-cache-dir torch==2.6.0 torchvision==0.21.0 torchaudio --index-url https://download.pytorch.org/whl/cu124

# Core dependencies (pin transformers<5.0.0 to avoid meta tensor issue with BiRefNet)
RUN pip install --no-cache-dir \
    "transformers>=4.47.0,<5.0.0" accelerate safetensors \
    huggingface_hub fastapi pydantic \
    einops trimesh pillow imageio imageio-ffmpeg \
    tqdm rich loguru easydict opencv-python-headless \
    ninja kornia timm tensorboard pandas lpips zstandard

# pillow-simd for faster image processing
RUN pip install --no-cache-dir pillow-simd

# Flash attention for Trellis 2
RUN pip install --no-cache-dir flash-attn==2.7.3 --no-build-isolation

# utils3d
RUN pip install --no-cache-dir git+https://github.com/EasternJournalist/utils3d.git@9a4eb15e4021b67b12c460c7057d642626897ec8

# nvdiffrast (must have --no-build-isolation for CUDA extension)
RUN mkdir -p /tmp/extensions && \
    git clone -b v0.4.0 https://github.com/NVlabs/nvdiffrast.git /tmp/extensions/nvdiffrast && \
    pip install /tmp/extensions/nvdiffrast --no-build-isolation

# nvdiffrec from fork (must have --no-build-isolation for CUDA extension)
RUN git clone -b renderutils https://github.com/JeffreyXiang/nvdiffrec.git /tmp/extensions/nvdiffrec && \
    pip install /tmp/extensions/nvdiffrec --no-build-isolation

# Install CuMesh for CUDA mesh operations (needed by o-voxel)
RUN git clone --recursive https://github.com/JeffreyXiang/CuMesh.git /tmp/extensions/CuMesh && \
    pip install /tmp/extensions/CuMesh --no-build-isolation

# Install FlexGEMM for sparse convolution (needed by o-voxel)
RUN git clone --recursive https://github.com/JeffreyXiang/FlexGEMM.git /tmp/extensions/FlexGEMM && \
    pip install /tmp/extensions/FlexGEMM --no-build-isolation

# Clone forked Trellis 2 with streaming callback support
ARG TRELLIS2_CACHE_BUST=v3
RUN git clone --recursive https://github.com/rehan-remade/TRELLIS.2.git /trellis2

# Install o-voxel (depends on CuMesh and FlexGEMM)
RUN cd /trellis2/o-voxel && pip install -e . --no-build-isolation

# Add Trellis 2 to PYTHONPATH (no setup.py at root)
ENV PYTHONPATH="/trellis2:${PYTHONPATH}"
ENV ATTN_BACKEND=flash_attn
"""

TRELLIS2_CACHE_DIR = FAL_PERSISTENT_DIR / "trellis2"


class Trellis2StreamInput(BaseModel):
    """Input for streaming 3D reconstruction endpoint."""

    image_url: str = Field(
        description="URL of the image to reconstruct in 3D",
        examples=["https://example.com/image.png"],
    )
    mode: Literal["512", "1024", "1024_cascade", "1536_cascade"] = Field(
        default="1536_cascade",
        description="Resolution mode for generation (1536_cascade is highest quality)",
    )
    seed: Optional[int] = Field(
        default=None,
        description="Random seed for reproducibility",
    )
    stream_sparse_structure_every: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Emit sparse structure updates every N steps (1=smoothest)",
    )
    stream_shape_every: int = Field(
        default=2,
        ge=1,
        le=10,
        description="Emit shape updates every N steps",
    )
    stream_texture_every: int = Field(
        default=2,
        ge=1,
        le=10,
        description="Emit texture updates every N steps",
    )
    preprocess_image: bool = Field(
        default=True,
        description="Whether to preprocess image (remove background, crop)",
    )


class Trellis2StreamApp(
    fal.App,
    keep_alive=600,
    kind="container",
    image=ContainerImage.from_dockerfile_str(dockerfile_str, builder="depot"),
    name="trellis-2-stream",
    request_timeout=600,
    max_concurrency=1,
    min_concurrency=1,
):
    machine_type = "GPU-H100"

    def setup(self):
        import torch
        from huggingface_hub import snapshot_download

        hf_token = os.getenv("HF_TOKEN")
        if not hf_token:
            print("[trellis2-stream] WARNING: No HF_TOKEN found, gated models may fail")

        if torch.cuda.is_available() and torch.cuda.get_device_properties(0).major >= 8:
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
        torch.set_float32_matmul_precision("high")

        # Download Trellis 2 checkpoint
        snapshot_download(
            "microsoft/TRELLIS.2-4B",
            revision="main",
            local_dir=str(TRELLIS2_CACHE_DIR),
            local_dir_use_symlinks=False,
        )

        # Create pipeline
        from trellis2.pipelines import Trellis2ImageTo3DPipeline

        self.pipeline = Trellis2ImageTo3DPipeline.from_pretrained(
            str(TRELLIS2_CACHE_DIR)
        )
        self.pipeline.to("cuda")
        print("[trellis2-stream] Pipeline loaded successfully!")

    def _load_image(self, image_url: str):
        try:
            image = Image(url=image_url)
            return image.to_pil()
        except Exception as exc:
            raise FieldException(
                "image_url", "Failed to read or process the image."
            ) from exc

    @fal.endpoint("/stream")
    def stream_3d_reconstruction(
        self, input: Trellis2StreamInput, request: Request, response: Response
    ):
        """
        Stream 3D reconstruction with real-time voxel and PBR visualization.

        SSE Events:
        - loading: Initial setup
        - sparse_structure: Voxel coords (Stage 1 diffusion)
        - shape_lr/shape_hr/shape: Shape latent (Stage 2 diffusion)
        - texture: PBR attributes preview (Stage 3 diffusion)
        - mesh_preview: Vertex-colored mesh preview
        - glb_ready: Final PBR GLB
        - complete: Final URLs
        """
        import numpy as np
        import torch

        progress_queue = queue.Queue(maxsize=100)

        def encode_voxels_binary(coords_np, colors_list=None):
            """Pack voxels as uint8: [x,y,z,r,g,b] per voxel."""
            if coords_np is None or len(coords_np) == 0:
                return "", None, None

            # Handle 4D coords [batch_idx, x, y, z] -> take only xyz
            if coords_np.ndim == 2 and coords_np.shape[1] >= 4:
                coords_np = coords_np[:, 1:4]

            coords_min = coords_np.min(axis=0)
            coords_max = coords_np.max(axis=0)
            coords_range = coords_max - coords_min
            coords_range[coords_range == 0] = 1

            coords_normalized = ((coords_np - coords_min) / coords_range * 255).astype(
                np.uint8
            )

            if colors_list is not None and len(colors_list) > 0:
                colors_arr = np.array(colors_list, dtype=np.uint8)
                if colors_arr.ndim == 2 and colors_arr.shape[1] == 4:
                    colors_arr = colors_arr[:, :3]
                elif colors_arr.ndim == 2 and colors_arr.shape[1] != 3:
                    colors_arr = np.full((len(coords_np), 3), 128, dtype=np.uint8)
            else:
                colors_arr = np.full((len(coords_np), 3), 128, dtype=np.uint8)

            if len(colors_arr) < len(coords_np):
                padding = np.full(
                    (len(coords_np) - len(colors_arr), 3), 128, dtype=np.uint8
                )
                colors_arr = np.vstack([colors_arr, padding])

            packed = np.empty((len(coords_np), 6), dtype=np.uint8)
            packed[:, :3] = coords_normalized
            packed[:, 3:] = colors_arr[: len(coords_np), :3]

            return (
                base64.b64encode(packed.tobytes()).decode("ascii"),
                coords_min.tolist(),
                coords_max.tolist(),
            )

        def encode_mesh_binary(vertices, faces, vertex_colors=None):
            """Encode mesh as binary for streaming."""
            if vertices is None or len(vertices) == 0:
                return None, None, None, None, None

            vertices_np = (
                vertices if isinstance(vertices, np.ndarray) else np.array(vertices)
            )
            faces_np = faces if isinstance(faces, np.ndarray) else np.array(faces)

            v_min = vertices_np.min(axis=0)
            v_max = vertices_np.max(axis=0)

            vertices_b64 = base64.b64encode(
                vertices_np.astype(np.float32).tobytes()
            ).decode("ascii")
            faces_b64 = base64.b64encode(faces_np.astype(np.uint32).tobytes()).decode(
                "ascii"
            )

            colors_b64 = None
            if vertex_colors is not None and len(vertex_colors) > 0:
                colors_np = (
                    vertex_colors
                    if isinstance(vertex_colors, np.ndarray)
                    else np.array(vertex_colors)
                )
                if colors_np.max() <= 1.0:
                    colors_np = (colors_np * 255).astype(np.uint8)
                else:
                    colors_np = colors_np.astype(np.uint8)
                colors_b64 = base64.b64encode(colors_np.tobytes()).decode("ascii")

            return vertices_b64, faces_b64, colors_b64, v_min.tolist(), v_max.tolist()

        def run_streaming():
            try:
                progress_queue.put(
                    {"stage": "loading", "progress": 0.01, "message": "Loading image..."}
                )

                image_pil = self._load_image(input.image_url)

                progress_queue.put(
                    {
                        "stage": "preprocessing",
                        "progress": 0.03,
                        "message": "Preparing pipeline...",
                    }
                )

                seed = input.seed if input.seed is not None else 42

                # Step counters for throttling
                ss_step_counter = [0]
                shape_step_counter = [0]
                tex_step_counter = [0]

                # Stage 1: Sparse Structure callback (5-25% progress)
                def sparse_structure_callback(stage, step, total_steps, coords, latent):
                    ss_step_counter[0] += 1
                    if ss_step_counter[0] % input.stream_sparse_structure_every != 0:
                        if step != total_steps - 1:
                            return

                    coords_np = (
                        coords.cpu().numpy()
                        if hasattr(coords, "cpu")
                        else np.array(coords)
                    )
                    progress = 0.05 + (step / max(total_steps - 1, 1)) * 0.20
                    voxel_data, bounds_min, bounds_max = encode_voxels_binary(
                        coords_np, None
                    )

                    progress_queue.put(
                        {
                            "stage": "sparse_structure",
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

                # Stage 2: Shape callback (25-55% progress)
                def shape_callback(stage, step, total_steps, coords, shape_slat):
                    shape_step_counter[0] += 1
                    if shape_step_counter[0] % input.stream_shape_every != 0:
                        if step != total_steps - 1:
                            return

                    coords_np = (
                        coords.cpu().numpy()
                        if hasattr(coords, "cpu")
                        else np.array(coords)
                    )

                    # Calculate progress based on stage (LR vs HR for cascade)
                    if stage == "shape_lr":
                        progress = 0.25 + (step / max(total_steps - 1, 1)) * 0.15
                    elif stage == "shape_hr":
                        progress = 0.40 + (step / max(total_steps - 1, 1)) * 0.15
                    else:
                        progress = 0.25 + (step / max(total_steps - 1, 1)) * 0.30

                    voxel_data, bounds_min, bounds_max = encode_voxels_binary(
                        coords_np, None
                    )

                    progress_queue.put(
                        {
                            "stage": stage,
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

                # Stage 3: Texture callback (55-90% progress)
                def texture_callback(
                    stage, step, total_steps, coords, tex_slat, pbr_attrs
                ):
                    tex_step_counter[0] += 1
                    if tex_step_counter[0] % input.stream_texture_every != 0:
                        if step != total_steps - 1:
                            return

                    coords_np = (
                        coords.cpu().numpy()
                        if hasattr(coords, "cpu")
                        else np.array(coords)
                    )

                    progress = 0.55 + (step / max(total_steps - 1, 1)) * 0.35

                    # Extract base colors from PBR attributes
                    colors = None
                    if pbr_attrs is not None:
                        base_color = pbr_attrs.get("base_color")
                        if base_color is not None:
                            bc_np = (
                                base_color.cpu().numpy()
                                if hasattr(base_color, "cpu")
                                else np.array(base_color)
                            )
                            if bc_np.max() <= 1.0:
                                colors = (bc_np * 255).astype(np.uint8).tolist()
                            else:
                                colors = bc_np.astype(np.uint8).tolist()

                    voxel_data, bounds_min, bounds_max = encode_voxels_binary(
                        coords_np, colors
                    )

                    progress_queue.put(
                        {
                            "stage": "texture",
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

                # Decode callback
                def decode_callback(stage, vertices=None, faces=None, pbr_attrs=None):
                    if stage == "mesh_ready":
                        vertices_np = (
                            vertices.cpu().numpy()
                            if hasattr(vertices, "cpu")
                            else np.array(vertices)
                        )
                        faces_np = (
                            faces.cpu().numpy()
                            if hasattr(faces, "cpu")
                            else np.array(faces)
                        )

                        # Extract base_color for vertex colors
                        vertex_colors = None
                        if pbr_attrs and "base_color" in pbr_attrs:
                            vc = pbr_attrs["base_color"]
                            if vc is not None:
                                vertex_colors = (
                                    vc.cpu().numpy() if hasattr(vc, "cpu") else np.array(vc)
                                )

                        vertices_b64, faces_b64, colors_b64, v_min, v_max = (
                            encode_mesh_binary(vertices_np, faces_np, vertex_colors)
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
                                "vertex_count": len(vertices_np),
                                "face_count": len(faces_np),
                            }
                        )

                # Run pipeline
                progress_queue.put(
                    {
                        "stage": "sparse_structure_start",
                        "progress": 0.05,
                        "message": "Starting sparse structure diffusion...",
                    }
                )

                meshes = self.pipeline.run_with_callbacks(
                    image_pil,
                    num_samples=1,
                    seed=seed,
                    preprocess_image=input.preprocess_image,
                    pipeline_type=input.mode,
                    sparse_structure_callback=sparse_structure_callback,
                    shape_callback=shape_callback,
                    texture_callback=texture_callback,
                    decode_callback=decode_callback,
                )

                # Finalize - export GLB
                progress_queue.put(
                    {
                        "stage": "finalizing",
                        "progress": 0.95,
                        "message": "Generating final GLB with PBR materials...",
                    }
                )

                with TemporaryDirectory() as temp_dir:
                    if meshes and len(meshes) > 0:
                        mesh = meshes[0]

                        # Simplify mesh for nvdiffrast limits
                        mesh = mesh.simplify(max_faces=500000)

                        # Export GLB with PBR textures
                        from o_voxel import postprocess

                        glb = postprocess.to_glb(
                            mesh,
                            decimation_target=1000000,
                            texture_size=4096,
                            remesh=True,
                        )

                        glb_path = os.path.join(temp_dir, "model.glb")
                        glb.export(glb_path, extension_webp=True)

                        glb_file = File.from_path(
                            path=glb_path,
                            content_type="model/gltf-binary",
                            multipart=True,
                            request=request,
                        )

                        progress_queue.put(
                            {
                                "stage": "complete",
                                "progress": 1.0,
                                "message": "Complete!",
                                "model_glb_url": glb_file.url,
                            }
                        )
                    else:
                        progress_queue.put(
                            {
                                "stage": "error",
                                "error": "No mesh generated",
                            }
                        )

                progress_queue.put(None)

            except Exception as e:
                import traceback

                progress_queue.put(
                    {
                        "stage": "error",
                        "error": str(e),
                        "traceback": traceback.format_exc(),
                    }
                )
                progress_queue.put(None)

        def event_stream():
            executor = ThreadPoolExecutor(max_workers=1)
            future = executor.submit(run_streaming)

            while True:
                try:
                    update = progress_queue.get(timeout=300)
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
    app = fal.wrap_app(Trellis2StreamApp)
    app()
