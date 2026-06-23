<p align="center">
  <img src="https://brickbuilder.ai/brickbuilder-logo.PNG" alt="BrickBuilder.AI" width="320" />
</p>

<h1 align="center">BrickBuilder.AI</h1>

<p align="center">
  <b>Turn any image or text prompt into a buildable LEGO®-compatible brick model.</b><br/>
  Get a 3D preview, step-by-step building instructions, downloadable LDR/MPD files, and a parts list you can order.
</p>

<p align="center">
  <a href="https://brickbuilder.ai">🌐 brickbuilder.ai</a>
</p>

<p align="center">
  <img src="https://brickbuilder.ai/twitter-preview.png" alt="BrickBuilder.AI preview" width="720" />
</p>

## What it does

Upload a photo or type a prompt, and BrickBuilder turns it into a real brick build:

1. **Image or text in** — start from any picture, or describe what you want.
2. **3D reconstruction** — a SAM-3D model voxelizes the subject into a solid shape.
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
| `backend/` | API that converts images/text into brick models | Python, FastAPI, Gurobi, Open3D, Trimesh, fal.ai |
| `serverless/` | Image-to-3D voxel generation worker | SAM-3D, Docker, RunPod |

## Running locally

### Frontend

```bash
python install.py
python run.py
```

The API runs on `http://localhost:8002`. Generate a model from an image:

## Deployment

- **Frontend** → Vercel
- **Backend** → Railway
- **Serverless worker** → RunPod (Docker image)

## Attributes
- Voxelization: https://github.com/eisenwave/obj2voxel
- Legolization: https://github.com/AvaLovelace1/BrickGPT/
- image-to-3D streaming: https://github.com/rehan-remade/Manifold

## License

Apache 2.0. LEGO® is a trademark of the LEGO Group, which does not sponsor or endorse this project.
