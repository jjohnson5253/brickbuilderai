# LegoACE: Autoregressive Construction Engine for Expressive LEGO® Assemblies

Official implementation of **LegoACE**, published at SIGGRAPH Asia 2025.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Paper](https://img.shields.io/badge/Paper-DOI-blue)](https://doi.org/10.1145/3757377.3763881)
[![HuggingFace](https://img.shields.io/badge/%F0%9F%A4%97%20HuggingFace-VAST--AI%2FLegoACE-orange)](https://huggingface.co/VAST-AI/LegoACE)

LegoACE is an autoregressive transformer that generates LEGO® assemblies. The repository
supports four generation modes:

- **Unconditional** generation (GPT-2 backbone)
- **Text-conditioned** generation (CLIP text encoder)
- **Image-conditioned** generation (DINOv2; single-view and multi-view)
- **DPO refinement** for image-conditioned models

---

## Table of contents
- [Installation](#installation)
- [Data preparation](#data-preparation)
- [Training](#training)
- [Inference](#inference)
- [Pre-trained models](#pre-trained-models)
- [Project structure](#project-structure)
- [Citation](#citation)
- [Acknowledgments](#acknowledgments)
- [License](#license)

---

## Installation

### Requirements
- Python 3.10+
- PyTorch 2.0+ with CUDA support
- Blender 4.2+ (only required to convert generated LDR files to GLB meshes)

### Setup

Clone the repository:
```bash
git clone https://github.com/VAST-AI-Research/LegoACE.git
cd LegoACE
```

Install Python dependencies using [uv](https://docs.astral.sh/uv/) (recommended):
```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install the project + dependencies
uv sync

# Install PyTorch with the CUDA wheel that matches your driver
uv pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

Or with plain pip:
```bash
pip install -e .
# Optional metrics deps (Chamfer / EMD evaluation):
pip install -e ".[metrics]"
```

Install Blender 4.2.x with the [ImportLDraw](https://github.com/TobyLobster/ImportLDraw) add-on:
```bash
wget https://download.blender.org/release/Blender4.2/blender-4.2.3-linux-x64.tar.xz
tar -xf blender-4.2.3-linux-x64.tar.xz
# Then in Blender: Edit > Preferences > Add-ons > Install... and select the ImportLDraw .zip
```

Export the binary path so the inference scripts can find it:
```bash
export BLENDER_BIN=/absolute/path/to/blender-4.2.3-linux-x64/blender
```

Make sure the project root is on `PYTHONPATH` whenever you run a script directly:
```bash
export PYTHONPATH="$(pwd)"
```

---

## Data preparation

### Dataset directory layout

All datasets live under a single root directory. The default root is `./data`; override
with the `LEGOACE_DATA_ROOT` environment variable:

```bash
export LEGOACE_DATA_ROOT=/path/to/datasets
```

Each dataset is a sub-directory:

```
$LEGOACE_DATA_ROOT/
└── <dataset_name>/
    ├── train_dataset.json
    ├── val_dataset.json
    ├── test_dataset.json
    ├── <dataset_name>_dat_dict.json   # brick type -> token id
    ├── <dataset_name>_rot_dict.json   # rotation matrix string -> token id
    └── models/
        ├── <model_id>.ldr             # LEGO instruction file
        ├── <model_id>.npz             # mesh data (vertices/faces/normals per brick)
        └── <model_id>_normal_*.png    # optional: pre-rendered multi-view images
```

### Dataset JSON formats

**Image-conditioned** (`train_dataset.json`):
```json
{
  "model_001": {
    "ldr": "/abs/path/to/model_001.ldr",
    "npz": "/abs/path/to/model_001.npz"
  }
}
```

**Text-conditioned**:
```json
{
  "model_001": {
    "ldr": "/abs/path/to/model_001.ldr",
    "text": [
      "A red sports car",
      "Racing vehicle with spoiler",
      "Small car model",
      "Automotive build"
    ]
  }
}
```

### LDR line format

```
1 <color> x y z r00 r01 r02 r10 r11 r12 r20 r21 r22 <brick_type>.dat
```

---

## Training

Multi-GPU launch uses [🤗 Accelerate](https://github.com/huggingface/accelerate)
config files under `accelerate_config/` (2/4/6/8 GPU variants are provided).

### Image-conditioned (multi-view)

```bash
accelerate launch --config_file ./accelerate_config/4-gpu.yaml \
    ./train/train_image_npz_mv.py \
    --output_dir ./outputs/image-condition \
    --split <dataset_name> \
    --train_batch_size 6 \
    --eval_batch_size 6 \
    --dataloader_num_workers 12 \
    --num_epochs 200 \
    --learning_rate 1e-5 \
    --mixed_precision bf16 \
    --checkpointing_steps 10000 \
    --logger wandb \
    --wandb_id my-experiment
```

Or use the example shell script:
```bash
OUTPUT_DIR=./outputs/image-condition SPLIT=<dataset_name> bash train/train_npz_mv.sh
```

### Text-conditioned

```bash
accelerate launch --config_file ./accelerate_config/8-gpu.yaml \
    ./train/train_text_condition.py \
    --output_dir ./outputs/text-condition \
    --split <dataset_name> \
    --train_batch_size 8 \
    --num_epochs 100 \
    --learning_rate 1e-4 \
    --mixed_precision bf16 \
    --checkpointing_steps 15000 \
    --logger wandb
```

### Unconditional

```bash
accelerate launch --config_file ./accelerate_config/4-gpu.yaml \
    ./train/train_unconditional.py \
    --train_data_dir /path/to/unconditional/data \
    --output_dir ./outputs/unconditional \
    --train_batch_size 16 \
    --num_epochs 200 \
    --learning_rate 1e-4 \
    --mixed_precision bf16
```

### DPO refinement

Build a preference dataset from per-sample Chamfer distance scores, then run DPO:

```bash
# Step 1: build preference pairs
python dpo/dpo_dataset/build_cd_dataset.py \
    --cd_file /path/to/cd_scores.json \
    --output  /path/to/preferences.json

# Step 2: DPO training
accelerate launch --config_file ./accelerate_config/8-gpu.yaml \
    dpo/train_dpo_acce.py \
    --dataset_name <dataset_name> \
    --dataset_path /path/to/preferences.json \
    --ldr_dir       /path/to/per_sample_ldrs \
    --ref_image_dir /path/to/reference_4view_images \
    --model_path    ./outputs/image-condition/checkpoint-260000/transformer \
    --save_dir      ./outputs/dpo \
    --epochs 3 --beta 0.1 --batch_size 2 --lr 1e-6
```

---

## Inference

All inference scripts accept arguments via [`tyro`](https://github.com/brentyi/tyro);
run any of them with `--help` to see every option.

### Multi-view image-conditioned

```bash
python inference/inference_multi_view.py \
    --dataset_name <dataset_name> \
    --ckpt_dir ./outputs/image-condition \
    --ckpt_iter 260000 \
    --dataset_class dataset.MVNpzDataset.MVNpzDataset \
    --save_dir ./outputs/inference \
    --save_name my-mv-run \
    --infer_number 100 \
    --batch_size 4 \
    --repeat 4 \
    --dataset_split val
```

### Single-image conditioned

```bash
python inference/inference_image_condition.py \
    --dataset_name <dataset_name> \
    --ckpt_dir ./outputs/image-condition \
    --ckpt_iter 260000 \
    --save_dir ./outputs/inference \
    --save_name my-image-run \
    --infer_number 100
```

### Text-conditioned

```bash
python inference/inference_text_condition.py \
    --ckpt_dir VAST-AI/LegoACE \
    --dataset_name <dataset_name> \
    --save_dir ./outputs/inference \
    --save_name my-text-run \
    --prompts "A red sports car" "A modern brick bed" "A bridge over a river"
```

### Unconditional

```bash
python inference/infer_uncondition.py \
    --ckpt_dir ./outputs/unconditional/checkpoint-200000/transformer \
    --dataset_name <dataset_name> \
    --dataset_dir /path/to/unconditional/data \
    --save_dir ./outputs/inference \
    --save_name my-uncond-run \
    --num_samples 400
```

### Output layout

Every inference script writes its results into `<save_dir>/<save_name>/...`:

| Sub-directory | Contents |
| --- | --- |
| `ldr/` | Generated LDR files |
| `glb/` | Converted GLB meshes (requires Blender) |
| `render/` | Normal-map renderings of each GLB |
| `input_image/` | Conditioning images (image-conditioned modes only) |

### Sampling parameters

Defaults are defined in `configs/config.py` and can be overridden on the command line:

| Argument | Default | Description |
| --- | --- | --- |
| `--sample_type` | `top_k_and_p` | one of `top_k_and_p`, `top_k`, `no_sample` |
| `--top_k_number` | `10` | top-k sampling cutoff |
| `--top_p_number` | `0.95` | nucleus sampling threshold |
| `--cfg_number` | `0.0` | classifier-free guidance scale |
| `--max_length` | `5000` | maximum sequence length |

---

## Pre-trained models

Released on the HuggingFace Hub: [VAST-AI/LegoACE](https://huggingface.co/VAST-AI/LegoACE).

| Model | Conditioning | Subfolder |
| --- | --- | --- |
| **LegoACE-MV** | Multi-view images (DINOv2) | `mv/` |
| **LegoACE-Text** | Text descriptions (CLIP) | `text/` |

Loading from Python:
```python
from model.llama_image_condition import ImageConditionModel
from model.llama_text_condition import TextConditionModel

mv_model   = ImageConditionModel.from_pretrained("VAST-AI/LegoACE", subfolder="mv").to("cuda")
text_model = TextConditionModel.from_pretrained("VAST-AI/LegoACE", subfolder="text").to("cuda")
```

---

## Project structure

```
LegoACE/
├── accelerate_config/        # multi-GPU configs (2/4/6/8-gpu, debug)
├── configs/
│   └── config.py             # InferenceArgs dataclass
├── dataset/
│   ├── MVNpzDataset.py       # multi-view image dataset
│   ├── SingleTokenDataset.py # unconditional dataset
│   ├── dpodataset.py         # DPO preference dataset
│   └── textDataset.py        # text-conditioned dataset
├── dpo/
│   ├── dpo_dataset/
│   │   └── build_cd_dataset.py  # build preference pairs from CD scores
│   ├── train_dpo_acce.py        # DPO training
│   └── train_dpo_multi_gpu.sh
├── inference/
│   ├── inference_image_condition.py
│   ├── inference_multi_view.py
│   ├── inference_text_condition.py
│   └── infer_uncondition.py
├── model/
│   ├── gpt2.py                  # GPT2 baseline (unconditional)
│   ├── llama_image_condition.py # image-conditioned Llama
│   ├── llama_text_condition.py  # text-conditioned Llama
│   ├── logitsprocessor.py       # brick-format-valid logits masking
│   └── tokenizer.py             # LDR tokenizer
├── train/
│   ├── train_image_npz_mv.py    # multi-view image training
│   ├── train_text_condition.py  # text-conditioned training
│   └── train_unconditional.py   # unconditional training
├── utils/
│   ├── brick_ids.py             # brick id <-> class id mappings
│   ├── data_utils.py            # LDR I/O helpers
│   ├── infer_utils.py           # inference-time image grid helpers
│   ├── ldr_export_dir.py        # Blender script: LDR directory -> GLBs
│   ├── log_utils.py             # code-snapshot logger
│   ├── metric.py                # CD/EMD evaluation (optional deps)
│   ├── misc.py                  # config-string instantiation
│   ├── render.py                # pyrender normal-map renderer
│   ├── utils.py                 # math / geometry helpers
│   └── shader/                  # pyrender GLSL shaders
├── LICENSE
├── pyproject.toml
└── README.md
```

---

## Citation

If you find this work useful, please cite:

```bibtex
@inproceedings{xu2025legoace,
  author    = {Hao Xu and Yuqing Zhang and Yiqian Wu and Xinyang Zheng and
               Yutao Liu and Xiangjun Tang and Yunhan Yang and Ding Liang and
               Yingtian Liu and Yuanchen Guo and Yanpei Cao and Xiaogang Jin},
  title     = {LegoACE: Autoregressive Construction Engine for Expressive LEGO{\textregistered}
               Assemblies},
  booktitle = {Proceedings of the {SIGGRAPH} Asia 2025 Conference Papers},
  publisher = {{ACM}},
  year      = {2025},
  pages     = {40:1--40:11},
  doi       = {10.1145/3757377.3763881},
  url       = {https://doi.org/10.1145/3757377.3763881}
}
```

---

## Acknowledgments

This project builds on several excellent open-source projects:

- [DINOv2](https://github.com/facebookresearch/dinov2) (Meta AI) — image feature extraction
- [CLIP](https://github.com/openai/CLIP) (OpenAI) — text encoding
- [Transformers](https://github.com/huggingface/transformers) — model implementations
- [Accelerate](https://github.com/huggingface/accelerate) — distributed training
- [Diffusers](https://github.com/huggingface/diffusers) — LR schedulers / utilities
- [PyRender](https://github.com/mmatl/pyrender) — mesh rendering
- [Trimesh](https://github.com/mikedh/trimesh) — mesh processing
- [Blender](https://www.blender.org/) + [ImportLDraw](https://github.com/TobyLobster/ImportLDraw) — LDR → GLB conversion

---

## License

This project is released under the [MIT License](LICENSE).

LEGO® is a trademark of the LEGO Group, which does not sponsor, authorize, or endorse this project.
