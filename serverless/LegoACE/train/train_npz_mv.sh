#!/usr/bin/env bash
# Example launch script for multi-view image-conditioned training.
# Edit OUTPUT_DIR, SPLIT, and WANDB_ID to match your setup.
set -euo pipefail

export PYTHONPATH="${PYTHONPATH:-$(pwd)}"

OUTPUT_DIR="${OUTPUT_DIR:-./outputs/image-condition}"
SPLIT="${SPLIT:-bricklink-unique-1280-5w}"
WANDB_ID="${WANDB_ID:-legoace-mv}"

accelerate launch --config_file ./accelerate_config/4-gpu.yaml \
    ./train/train_image_npz_mv.py \
    --output_dir "${OUTPUT_DIR}" \
    --split "${SPLIT}" \
    --train_batch_size 6 \
    --eval_batch_size 6 \
    --dataloader_num_workers 12 \
    --validate_epochs 1 \
    --save_model_epochs 5 \
    --num_epochs 500 \
    --learning_rate 1e-5 \
    --mixed_precision bf16 \
    --checkpointing_steps 10000 \
    --seed 1443 \
    --logger wandb \
    --wandb_id "${WANDB_ID}"
