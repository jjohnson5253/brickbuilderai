# SAM-3D on RunPod Serverless

This folder contains a RunPod-Serverless port of the SAM-3D streaming endpoint
that lives in `app.py` (which targets fal's `fal deploy`). It exists because
deploying custom apps to fal requires an enterprise license, while RunPod
Serverless lets anyone push a custom container.

The original `app.py` and `trellis2_app.py` are left in place untouched — only
the SAM-3D path has been ported. The Next.js frontend has been updated so
`/api/stream-3d` talks to RunPod instead of fal; nothing else changed there.

## Files

| File | Purpose |
| --- | --- |
| `runpod_handler.py` | RunPod generator handler. Wraps the SAM-3D pipeline and yields the same SSE-style events the fal version produced. |
| `Dockerfile` | Container image used by the RunPod worker. Verbatim port of the inline `dockerfile_str` from `app.py`, plus the RunPod entrypoint at the bottom. |
| `app.py` / `trellis2_app.py` | Original fal apps. Untouched. |

## 1. Build & push the image

You need a container registry (Docker Hub, GHCR, ECR, …) that RunPod can pull
from. Replace `YOUR_REGISTRY/manifold-sam3d:latest` with your own tag.

```bash
cd serverless

# Use buildx for x86_64 if you're on an Apple Silicon Mac.
docker buildx build \
  --platform linux/amd64 \
  -t YOUR_REGISTRY/manifold-sam3d:latest \
  --push \
  .
```

Heads up: the build is large (PyTorch + CUDA + flash-attn + pytorch3d + kaolin)
and slow on the first run. Expect ~30–60 minutes and several GB of layers.

## 2. Create the RunPod Serverless endpoint

1. Go to <https://www.runpod.io/console/serverless> → **New Endpoint**.
2. **Container image**: the tag you pushed above.
3. **GPU type**: H100 80GB (or A100 80GB). Smaller cards will OOM on the
   appearance stage for 1024-mode runs.
4. **Container disk**: at least 60 GB.
5. **Worker config**: `Max workers ≥ 1`, `Active workers = 0` is fine; set
   `Idle timeout` to ~300s so you don't pay between requests.
6. (Recommended) Attach a **Network Volume** mounted at `/runpod-volume`. The
   handler caches the ~10 GB SAM-3D checkpoint there, so subsequent cold starts
   skip the Hugging Face download. If you do this, set the env var
   `MANIFOLD_CACHE_DIR=/runpod-volume/sam3d_objects` (already the default in
   the Dockerfile).
7. Optional env vars:
   - `HF_TOKEN` – only if you swap to a gated checkpoint.
   - `SAM3D_REPO_ID` – override the HF repo (defaults to `jetjodh/sam-3d-objects`).
   - `MAX_INLINE_SPLAT_BYTES` – cap on splat inlined into the final SSE event
     (default 25 MB).

Copy the resulting **Endpoint ID** (e.g. `abcd1234efgh5678`) and create an
**API key** under <https://www.runpod.io/console/user/settings>.

## 3. Wire up the frontend

In `frontend/.env.local`, replace the fal SAM-3D variables with:

```env
RUNPOD_API_KEY=rpa_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
RUNPOD_ENDPOINT_ID=abcd1234efgh5678

# Optional tuning
# RUNPOD_API_BASE=https://api.runpod.ai/v2
# RUNPOD_POLL_INTERVAL_MS=500
```

The other fal-related env vars (`FAL_KEY`) are still used for the
text-to-image step (`fal-ai/z-image/turbo`) and image uploads — those are
public pay-per-call endpoints on fal.run and do **not** require an enterprise
license, so they are left in place. If you'd rather replace them too, swap
`frontend/app/components/BottomToolbar.tsx` (image generation) and
`frontend/app/api/fal/upload/route.ts` (storage) for the providers of your
choice.

## 4. How streaming works under the hood

```
Browser ──SSE──▶ /api/stream-3d ──POST /run──▶ RunPod
                       │
                       └─ poll /stream/{id} every 500 ms,
                          re-emit each yielded dict as `data: {...}\n\n`
```

Each `yield` from `runpod_handler.handler` becomes one SSE event in the
browser. The hook (`useSAM3DStream`) decodes them exactly as before:

- `geometry` / `appearance` → voxel updates (base64 packed `xyzrgb` uint8)
- `mesh_preview` → vertex-colored mesh
- `glb_ready` → base64 GLB bytes
- `complete` → final summary; includes the GLB as a `data:` URL so the
  download button in `BottomToolbar` still works without any object storage.

## 5. Local smoke test (without RunPod)

If you want to sanity-check the handler before pushing:

```bash
docker build -t manifold-sam3d:dev .
docker run --rm --gpus all \
  -v $PWD/cache:/runpod-volume \
  -e RUNPOD_DEBUG_LEVEL=DEBUG \
  manifold-sam3d:dev \
  python -u /app/runpod_handler.py --test_input '{"input": {
      "image_url": "https://v3b.fal.media/files/b/0a8439e5/TyAmfW5w_sqRXRzWVBGsW_car.jpeg",
      "prompt": "car"
  }}'
```

`runpod.serverless.start` understands `--test_input`; it will run the handler
locally and print each yielded chunk.
