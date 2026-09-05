# LegoACE pre-trained weights: availability and usability

Research findings for the issue "see if LEGO ACE weights are out and if we can use
yet". Last verified: 2026-09-04.

## TL;DR

- **Yes, the weights are out.** The upstream LegoACE README states the pre-trained
  models are "Released on the HuggingFace Hub" at
  [`VAST-AI/LegoACE`](https://huggingface.co/VAST-AI/LegoACE), and the inference
  scripts vendored in this repo already default to that repo id.
- **Yes, we can use them.** Both the code and the weights are MIT licensed, which is
  compatible with this project's MIT license.
- **One practical caveat:** running inference also needs the per-dataset tokenizer
  vocabulary files (`*_dat_dict.json` / `*_rot_dict.json`), not just the transformer
  weights. Whether those ship inside the HuggingFace repo still needs to be confirmed
  by downloading it (see [Open questions](#open-questions)).

## What LegoACE is

LegoACE (SIGGRAPH Asia 2025, [DOI 10.1145/3757377.3763881](https://doi.org/10.1145/3757377.3763881))
is an autoregressive next-token-prediction transformer that generates LEGO®
assemblies directly as LDR brick sequences. Two conditioned variants were released:

| Model | Conditioning | HF subfolder |
| --- | --- | --- |
| LegoACE-MV | Multi-view images (DINOv2 encoder) | `mv/` |
| LegoACE-Text | Text prompts (CLIP encoder) | `text/` |

Links: [HuggingFace](https://huggingface.co/VAST-AI/LegoACE) ·
[GitHub](https://github.com/VAST-AI-Research/LegoACE) ·
[Paper](https://dl.acm.org/doi/10.1145/3757377.3763881)

## Evidence that the weights are released

1. The upstream `README.md` on `VAST-AI-Research/LegoACE` `main` (fetched
   2026-09-04) has a "Pre-trained models" section: *"Released on the HuggingFace
   Hub: [VAST-AI/LegoACE](https://huggingface.co/VAST-AI/LegoACE)"*, with loading
   examples:

   ```python
   mv_model   = ImageConditionModel.from_pretrained("VAST-AI/LegoACE", subfolder="mv").to("cuda")
   text_model = TextConditionModel.from_pretrained("VAST-AI/LegoACE", subfolder="text").to("cuda")
   ```

2. The LegoACE source vendored in this repo at `serverless/LegoACE/` already
   defaults to the hub weights:
   - `serverless/LegoACE/configs/config.py` — `ckpt_dir: str = "VAST-AI/LegoACE"`
   - `serverless/LegoACE/inference/inference_text_condition.py` — same default
   - `serverless/LegoACE/inference/infer_4gpu.sh` and `infer_multi_view.sh` —
     `CKPT_DIR="${CKPT_DIR:-VAST-AI/LegoACE}"`
   - `serverless/LegoACE/inference/inference_multi_view.py` resolves any
     `VAST-AI/…` checkpoint path to the `mv` subfolder before calling
     `from_pretrained`.

Note: direct access to `huggingface.co` was blocked from the environment used for
this research, so the hub repo contents were confirmed via the upstream GitHub
README and code defaults rather than by downloading the weights.

## Licensing

- Code and released models: **MIT** (`serverless/LegoACE/LICENSE`, upstream
  `pyproject.toml` classifier `License :: OSI Approved :: MIT License`).
- Compatible with BrickBuilder's MIT license. The usual LEGO® trademark disclaimer
  applies (already present in both projects' READMEs).

## What using the weights requires

From `serverless/LegoACE/pyproject.toml` and the inference scripts:

- Python 3.10+, PyTorch 2.0+ with CUDA (GPU required), `transformers>=4.45`.
- Encoder downloads at runtime: `facebook/dinov2-base` (multi-view) or CLIP (text).
- Blender 4.2+ with the ImportLDraw add-on — **only** for LDR → GLB conversion.
  BrickBuilder does not need this step (see below).
- Tokenizer vocabularies: `model/tokenizer.py` loads
  `<dataset>_dat_dict.json` (brick type → token id) and `<dataset>_rot_dict.json`
  (rotation → token id) from `$LEGOACE_DATA_ROOT/<dataset>/`. These define how
  generated tokens decode back into LDR lines, so they are required at inference
  time alongside the weights.

## How this fits BrickBuilder

LegoACE outputs LDR files directly, so it would bypass the current
3D-reconstruction → voxelization → brick-optimization pipeline entirely for both
image and text inputs. A plausible integration mirrors the existing SAM-3D setup:

1. Package `serverless/LegoACE` inference into a Docker image (like
   `serverless/` does for SAM-3D) and deploy it as a RunPod serverless endpoint.
   The weights can be cached on a network volume, same as the SAM-3D weights.
2. Have the backend call the endpoint (as `backend/src/utils/sam3d_stream.py` does
   today) and feed the returned LDR into the existing instructions/parts pipeline.
3. Compare output quality, part availability (LegoACE's brick vocabulary comes from
   its training set and may include parts outside `backend/big-parts-list.csv`), and
   generation latency against the current SAM-3D + optimizer path before switching.

## Open questions

- Confirm (from a machine with HuggingFace access) that the `VAST-AI/LegoACE` repo
  contains the tokenizer dictionaries or that upstream publishes them elsewhere;
  without them the generated token sequences cannot be decoded to LDR.
- Measure VRAM needs and end-to-end latency to pick a RunPod GPU tier.
- Evaluate whether LegoACE's brick/color vocabulary maps cleanly onto the parts and
  colors BrickBuilder can order.
