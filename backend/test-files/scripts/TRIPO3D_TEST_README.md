# Tripo3D API Test Script

Test script for generating 3D models from images using the Tripo3D API.

## Setup

1. Set your Tripo3D API key as an environment variable:
```bash
export TRIPO3D_API_KEY="tsk_your_api_key_here"
```

2. Make sure the batman.png image exists:
```bash
ls -lh test-files/png/batman.png
```

## Usage

Run the test script:
```bash
uv run python test_tripo3d.py
```

Or with the API key inline:
```bash
TRIPO3D_API_KEY="tsk_your_key" uv run python test_tripo3d.py
```

## What it does

1. **Uploads** `test-files/png/batman.png` to Tripo3D
2. **Creates** an image-to-model generation task using the `Turbo-v1.0-20250506` model
3. **Polls** the task status until completion
4. **Downloads** the generated GLB model and rendered image to `./output/`

## Output

If successful, you'll get:
- `output/batman_tripo3d.glb` - The generated 3D model
- `output/batman_tripo3d_render.png` - A rendered view of the model

## Model Parameters

The script uses:
- `model_version`: `Turbo-v1.0-20250506` (fastest model)
- `type`: `image_to_model`
- Default settings for all other parameters (texture, PBR, etc.)

You can modify the `create_image_to_model_task()` function to add additional parameters like:
- `face_limit`: Limit polygon count
- `texture_quality`: "standard" or "detailed"
- `pbr`: Enable/disable PBR materials
- `auto_size`: Scale to real-world dimensions

## Example Output

```
============================================================
Tripo3D API Test - Image to Model
============================================================
📤 Uploading image: ./test-files/png/batman.png
✅ Upload successful! File token: abc123...

🚀 Creating image-to-model task...
✅ Task created! Task ID: 1ec04ced-4b87-44f6-a296-beee80777941

⏳ Waiting for task completion...
   Status: running
✅ Task completed successfully!

📥 Downloading model...
✅ Model saved to: output/batman_tripo3d.glb

📥 Downloading rendered image...
✅ Rendered image saved to: output/batman_tripo3d_render.png

============================================================
✅ SUCCESS - Model generated and downloaded!
============================================================
```
