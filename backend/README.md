# BrickBuilder Backend

## Running locally
 - Create .env file and populate
 - Make sure `uv` is installed on cmd line
 - Then run:
```bash
uv sync
```
```bash
uv run local_run.py
```
## Endpoints
Developer API keys are for local curl and server-side callers only. Browser clients should authenticate with Supabase JWT bearer tokens instead of sending `X-API-Key`.

### Brick Generation
#### /imageToBricks
```bash
image_base64=$(base64 -i test-files/png/pikachu.png) && 
curl -X POST http://localhost:8002/imageToBricks \
-H "Content-Type: application/json" \
-H "X-API-Key: <your DEVELOPER_API_KEY>" \
-d "{\"image_base64\": \"$image_base64\", \"detail_level\": 32}" \
-o pikachu_response.json
```
#### /textToBricks
```bash
curl -X POST http://localhost:8002/textToBricks \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your DEVELOPER_API_KEY>" \
  -d '{"prompt": "a cute pikachu", "model_option": "a", "detail_level": "32"}' \
  -o pikachu_response.json
```
Response with .ldr and .mpd will be in pikachu_response.json. Extract them like this:
```bash
jq -r '.ldr_content' pikachu_response.json > pikachu.ldr
```
```bash
jq -r '.mpd_content' pikachu_response.json > pikachu.mpd
```
### Brick Owl Wishlist Creation
#### /ldrToBrickOwl
```bash
curl -X POST http://localhost:8002/ldrToBrickOwl \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your DEVELOPER_API_KEY>" \
  -d '{
    "ldr_content": "<your LDR file content here>",
    "brickowl_api_key": "your_brickowl_api_key",
    "user_email": "your_email@example.com"
  }' \
  -o brickowl_response.json
```
### LDR and MPD functions
#### /partToMpd
```bash
curl -X POST "http://localhost:8002/partToMpd" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your DEVELOPER_API_KEY>" \
  -d '{"part_number": "3006", "color": 147}' \
  -o part_output.json
```
#### /ldrToMpd
```bash
curl -X POST "http://localhost:8002/ldrToMpd" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your DEVELOPER_API_KEY>" \
  -d "$(jq -n --arg ldr_content "$(cat test-files/ldr/pikachu.ldr)" '{ldr_content: $ldr_content}')" \
  -o mpd_output.json
```
#### /resizeModel  
```bash
curl -X POST "http://localhost:8002/resizeModel" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your DEVELOPER_API_KEY>" \
  -d '{"generation_id": "your_generation_id", "detail_level": 16}' \
  -o resize_output.json
```
#### /promptEditModel
```bash
curl -X POST http://localhost:8002/promptEditModel \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your DEVELOPER_API_KEY>" \
  -d '{"generation_id": "your_generation_id_here", "edit_prompt": "make it red and add a hat"}' \
  -o edited_model_response.json
```
#### /llmRender
Recolor an existing xyzrgb file to better match one or more reference images. Requires `OPENAI_API_KEY`.

The model is first split server-side into up to `max_segments` (default 16) contiguous
segments. Splitting combines colour structure (clustered in CIELAB with lightness
down-weighted, so shading does not split a part) with geometry (a distance-transform
watershed that separates thick cores joined by thin necks, so same-coloured parts such as
a head and torso still split). Small high-contrast features (eyes, mouth, buttons, logos,
jewelry, shirt patterns) are protected from speckle removal, and same-coloured pieces of
one feature (both eyes, all buttons) share a single segment; the scene summary flags these
with `is_detail` and `island_count`. Unless `check_segmentation` is false, the LLM then
reviews the labelled preview against the reference image(s) and may merge segments that
are fragments of one part or ask for a segment spanning several parts to be re-split
deterministically; applied changes are reported in `segmentation_adjustments` (segment ids
there refer to the segmentation the LLM reviewed). A labelled multi-view preview of the
final segments plus every reference image is sent to OpenAI, which returns one colour per
segment. `applied_rules` in the response lists each segment's inferred part name, reason
and colour. Reference images can be given as `reference_image_url`, `reference_image_urls`
(max 4 combined), or both.

Optional env vars: `OPENAI_LLM_RENDER_MODEL`, `OPENAI_LLM_RENDER_REASONING_EFFORT`
(default `medium`), `OPENAI_LLM_RENDER_TIMEOUT_SECONDS` (default `240`).
```bash
curl -X POST http://localhost:8002/llmRender \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your DEVELOPER_API_KEY>" \
  -d '{
    "xyzrgb_url": "https://example.com/model.xyzrgb",
    "reference_image_urls": ["https://example.com/reference.png", "https://example.com/reference-side.png"],
    "prompt": "match the character colors, preserving the model shape",
    "max_segments": 16,
    "check_segmentation": true,
    "include_preview": false
  }' \
  -o llm_render_response.json
```
#### /estimatePrice
```bash
curl -X POST http://localhost:8002/estimatePrice \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your DEVELOPER_API_KEY>" \
  -d @test-files/json/estimate_price_test_request.json \
  -o price_estimate_response.json
```

## Testing
### Run glb2brick from cmd line to bypass .glb generation
```bash
uv run python -m src.utils.conversions.glb2brick ./test-files/glb/pikachu.glb --voxel-size 30
```
### Run glb2brick with xyzrgb file (bypassing glb voxelization)
```bash
uv run python -m src.utils.conversions.glb2brick ./test-files/glb/pikachu.glb --voxel-size 36 --xy
zrgb ./lambo-no-bottom.xyzrgb 
```
### Stripe Webhook testing
```bash
stripe login
```
```bash
stripe listen --forward-to localhost:8002/stripeWebhook
```
Read output and make sure STRIPE_WEBHOOK_SECRET is correct in `.env`. Restart local server if necessary
```bash
uv run local_run.py
```
```bash
stripe trigger checkout.session.completed
```
can view events at `https://dashboard.stripe.com/acct_1SRdqKBSm75IitZv/test/workbench/events`

## Parts Used
### Colors
Colors used are in `gobrick_colors.csv`
### Part Types
Part types used are in `brick_library.json`
