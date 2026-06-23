<h1 align="center">BrickBuilder</h1>

<p align="center">
  <b>Use AI to design LEGO models.</b><br/> Turn any image or text prompt into a buildable LEGO®-compatible brick model.</b><br/>
  Get a 3D preview, step-by-step building instructions, downloadable LDR/MPD files, and a parts list you can order.
</p>

<p align="center">
  <img width="768" height="520" alt="github-readme-video (1)" src="https://github.com/user-attachments/assets/63added8-2404-45ce-a87c-df40c801ddf4" />
</p>

## What it does

Upload a photo or type a prompt, and BrickBuilder turns it into a real brick build:

1. **Image or text in** — start from any picture, or describe what you want.
2. **3D reconstruction** — a Trellis or SAM-3D model converts the subject into a solid shape.
3. **Voxelization** - 3D model is voxelized if using Trellis, or gotten directly from SAM3D stream
3. **Brick optimization** — an optimizer packs the voxels into real LEGO-compatible parts.
4. **Build it** — explore the model in 3D, follow the instructions, download the LDR/MPD, or order the parts.

## Examples

<p align="center">
  <img src="frontend/public/assets/demo-images/Pokemon.png" width="180" />
  <img src="frontend/public/assets/demo-images/Link.png" width="180" />
  <img src="frontend/public/assets/demo-images/Octopus.png" width="180" />
  <img src="frontend/public/assets/demo-images/Nyan%20Cat.png" width="180" />
</p>

## Project layout

| Folder | What it is | Stack |
| --- | --- | --- |
| `frontend/` | Web app: upload, 3D viewer, instructions, checkout | React, Vite, TypeScript, Three.js, Tailwind, Supabase, Stripe |
| `backend/` | API that converts images/text into brick models | fal.ai Python, FastAPI, Open3D, Trimesh |
| `serverless/` | Image-to-3D voxel generation worker | SAM-3D, Docker, RunPod |

## Running locally

```bash
python install.py
python run.py
```
Voxelization with SAM3D works better than Trellis but you must host this docker image on runpod and provide RUNPOD_API_KEY and RUNPOD_ENDPOINT_ID backend/.env

## Attributes
- Voxelization: https://github.com/eisenwave/obj2voxel
- Legolization: https://github.com/AvaLovelace1/BrickGPT/
- image-to-3D streaming: https://github.com/rehan-remade/Manifold

## License

MIT. LEGO® is a trademark of the LEGO Group, which does not sponsor or endorse this project.
