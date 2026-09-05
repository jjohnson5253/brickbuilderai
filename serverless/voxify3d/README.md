# Voxify3D voxelization worker

Experimental RunPod Serverless worker that runs
[Voxify3D](https://yichuanh.github.io/Voxify-3D/) (CVPR 2026, official code at
[yichuanH/Voxify3D_official](https://github.com/yichuanH/Voxify3D_official)) to
turn a GLB mesh into stylized, palette-constrained voxel art. The handler
returns the voxels as `.xyzrgb` content, so the BrickBuilder backend can feed
them straight into the existing brick-optimization pipeline by selecting the
`voxify3d` voxelizer (see `backend/src/utils/voxify3d_client.py`).

Unlike SAM-3D (which reconstructs 3D from an image), Voxify3D is a
mesh-to-voxel *stylizer*: it takes the GLB produced by Trellis and optimizes a
low-resolution voxel grid with a discrete color palette. Expect jobs to take
several minutes — each request runs Blender renders plus two DVGO optimization
stages on the GPU.

## Pipeline

1. **Blender render** — `glb2img.py` renders ~100 orthographic views of the GLB.
2. **Voxify3D optimization** — `execute_gumbel_color_palette.py` runs the
   PixelArt stage, coarse DVGO training, and 6-view color-palette fine-tuning.
3. **Voxel export** — the resulting `alpha`/`rgb` grids and `color_palette.npz`
   are converted to `x y z r g b` lines, gzipped, base64-encoded, and returned
   in the final stream event.

## Pretrained models (Hugging Face)

Voxify3D depends on four PixelArt checkpoints from
[WuZongWei6/Pixelization](https://github.com/WuZongWei6/Pixelization) that the
official repo distributes via Google Drive. This worker instead downloads them
from a Hugging Face repo at cold start (cached on the network volume), so you
must mirror them once:

1. Download the four checkpoints linked in the
   [Voxify3D README](https://github.com/yichuanH/Voxify3D_official#pretrained-models).
2. Upload them to a Hugging Face model repo (keep it **private** — the
   checkpoints are licensed for non-commercial use only) with this layout:

   ```text
   pixelart_vgg19.pth
   alias_net.pth
   checkpoints/pixel_model/160_net_G_A.pth
   checkpoints/pixel_model/160_net_G_B.pth
   ```

   A flat layout (all four files at the repo root) also works.
3. Set `VOXIFY3D_HF_REPO` (for example `your-user/voxify3d-pixelart`) and, if
   the repo is private, `HF_TOKEN` on the RunPod endpoint.

## Build & deploy

```bash
cd serverless/voxify3d
depot build --platform linux/amd64 --tag <your-dockerhub>/voxify3d:latest --push .
```

1. In the [RunPod Serverless console](https://www.runpod.io/console/serverless),
   create a new endpoint with the image you pushed.
2. Pick a GPU with at least 24 GB VRAM (DVGO training at the default settings
   fits comfortably; more VRAM shortens iteration time).
3. Attach a Network Volume mounted at `/runpod-volume` so the PixelArt
   checkpoints persist across cold starts.
4. Set the environment variables below, then deploy.
5. Copy the endpoint ID into `VOXIFY3D_ENDPOINT_ID` in `backend/.env` (the
   backend reuses `RUNPOD_API_KEY`).

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `VOXIFY3D_HF_REPO` | *(required)* | Hugging Face repo holding the PixelArt checkpoints |
| `HF_TOKEN` | — | Hugging Face token (needed for private repos) |
| `VOXIFY3D_CACHE_DIR` | `/runpod-volume/voxify3d` | Checkpoint cache location |
| `VOXIFY3D_N_VIEWS` | `100` | Number of Blender orthographic views |
| `VOXIFY3D_RENDER_RES` | `1200` | Render resolution (grid size ≈ res / cell_size) |

## Request / response

Job input:

```json
{
  "input": {
    "glb_url": "https://.../model.glb",
    "cell_size": 30,
    "palette_mode": "kmeans_rare",
    "color_num": 6,
    "alpha_threshold": 0.78
  }
}
```

`glb_b64` (base64-encoded GLB bytes) can be used instead of `glb_url`. The
handler streams progress events (`setup`, `render`, `optimize`, `convert`) and
finishes with:

```json
{
  "stage": "complete",
  "xyzrgb_gz_b64": "<base64(gzip(xyzrgb text))>",
  "voxel_count": 1234,
  "palette": [[255, 0, 0], "..."]
}
```

Failures are reported as `{"stage": "error", "error": "..."}`.

You can smoke-test a deployed endpoint with:

```bash
curl -s -X POST "https://api.runpod.ai/v2/$VOXIFY3D_ENDPOINT_ID/run" \
  -H "Authorization: ******" -H "Content-Type: application/json" \
  -d '{"input": {"glb_url": "https://example.com/model.glb"}}'
```

## Licensing

Voxify3D and the PixelArt checkpoints are licensed for **non-commercial
scientific research use only**. This worker is provided for experimentation;
do not enable it for commercial deployments.
