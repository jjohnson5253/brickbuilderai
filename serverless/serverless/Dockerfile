# SAM-3D Objects streaming worker for RunPod Serverless.
#
# This Dockerfile is a direct port of the inline `dockerfile_str` from
# `app.py` (the fal version), with two changes at the end:
#   1. Install `runpod` and `requests`.
#   2. Copy in `runpod_handler.py` and use it as the container entrypoint.
#
# Build & push:
#   docker build -t <your-dockerhub>/manifold-sam3d:latest .
#   docker push <your-dockerhub>/manifold-sam3d:latest

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

# Clone forked sam-3d-objects with streaming callback support.
# Bump this when you need to force a re-clone (rebuild this layer).
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

# ---------------------------------------------------------------------------
# RunPod worker bits
# ---------------------------------------------------------------------------
RUN pip install --no-cache-dir runpod>=1.7.0 requests pillow

# Default cache location. If you attach a RunPod Network Volume mounted at
# /runpod-volume, the SAM-3D checkpoint will persist across cold starts.
ENV MANIFOLD_CACHE_DIR=/runpod-volume/sam3d_objects

WORKDIR /app
COPY runpod_handler.py /app/runpod_handler.py

CMD ["python", "-u", "/app/runpod_handler.py"]
