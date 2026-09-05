# Voxify3D voxelization worker for RunPod Serverless.
#
# Packages the official Voxify3D pipeline (https://github.com/yichuanH/Voxify3D_official)
# behind a RunPod generator handler that takes a GLB and returns stylized,
# palette-constrained voxels as xyzrgb content. See README.md in this folder
# for deployment instructions and checkpoint setup.
#
# Build & push (mirrors the sam3d worker workflow):
#   cd serverless/voxify3d
#   depot build --platform linux/amd64 --tag <your-dockerhub>/voxify3d:latest --push .

# Voxify3D targets CUDA 11.8 + PyTorch 2.5 (torch_scatter and mmcv wheels are
# tightly coupled to these versions).
FROM nvidia/cuda:11.8.0-cudnn8-devel-ubuntu22.04
ENV TZ=Etc/UTC DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.10 python3.10-dev python3.10-venv python3-pip \
        build-essential git curl ca-certificates xz-utils \
        # Headless Blender runtime dependencies
        libgl1 libglu1-mesa libegl1 libglib2.0-0 libsm6 libice6 libxext6 \
        libxrender1 libxi6 libxfixes3 libxkbcommon0 libxxf86vm1 libtbb12 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1 && \
    python -m pip install --no-cache-dir --upgrade pip

ENV CUDA_HOME=/usr/local/cuda PATH=$CUDA_HOME/bin:$PATH LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH
ENV TORCH_CUDA_ARCH_LIST="7.5 8.0 8.6 8.9 9.0+PTX"

# Torch stack pinned to the versions Voxify3D was tested with (cu118).
RUN pip install --no-cache-dir torch==2.5.0 torchvision==0.20.0 torchaudio==2.5.0 \
        --index-url https://download.pytorch.org/whl/cu118
RUN pip install --no-cache-dir torch_scatter -f https://data.pyg.org/whl/torch-2.5.0+cu118.html
RUN pip install --no-cache-dir mmcv==2.2.0 -f https://download.openmmlab.com/mmcv/dist/cu118/torch2.5/index.html
RUN pip install --no-cache-dir torch-efficient-distloss

# Headless Blender for the orthographic renders in glb2img.py.
RUN curl -fsSL https://download.blender.org/release/Blender4.0/blender-4.0.2-linux-x64.tar.xz \
        | tar -xJ -C /opt && \
    ln -s /opt/blender-4.0.2-linux-x64/blender /usr/local/bin/blender
ENV VOXIFY3D_BLENDER_EXE=/opt/blender-4.0.2-linux-x64/blender

# Clone the official Voxify3D implementation.
# Bump this when you need to force a re-clone (rebuild this layer).
ARG VOXIFY3D_CACHE_BUST=v1
RUN git clone https://github.com/yichuanH/Voxify3D_official.git /workspace/Voxify3D_official && \
    cd /workspace/Voxify3D_official && \
    grep -Ev '^(torch|torchvision|torchaudio|torch-scatter|torch_scatter|torch-efficient-distloss|mmcv|nvidia-|triton)' requirements.txt > /tmp/reqs.txt && \
    pip install --no-cache-dir -r /tmp/reqs.txt
ENV VOXIFY3D_REPO_DIR=/workspace/Voxify3D_official

# ---------------------------------------------------------------------------
# RunPod worker bits
# ---------------------------------------------------------------------------
RUN pip install --no-cache-dir "runpod>=1.7.0" requests huggingface_hub

# Default cache location. If you attach a RunPod Network Volume mounted at
# /runpod-volume, the PixelArt checkpoints persist across cold starts.
ENV VOXIFY3D_CACHE_DIR=/runpod-volume/voxify3d

WORKDIR /app
COPY runpod_handler.py /app/runpod_handler.py

CMD ["python", "-u", "/app/runpod_handler.py"]
