#!/usr/bin/env bash
# Example launch script for text-conditioned training.
# Edit OUTPUT_DIR, SPLIT, and WANDB_ID to match your setup.
set -euo pipefail

export PYTHONPATH="${PYTHONPATH:-$(pwd)}"

OUTPUT_DIR="${OUTPUT_DIR:-./outputs/text-condition}"
SPLIT="${SPLIT:-bricklink-text}"
WANDB_ID="${WANDB_ID:-legoace-text}"

accelerate launch --config_file ./accelerate_config/8-gpu.yaml \
    ./train/train_text_condition.py \
    --output_dir "${OUTPUT_DIR}" \
    --split "${SPLIT}" \
    --train_batch_size 8 \
    --eval_batch_size 8 \
    --dataloader_num_workers 10 \
    --validate_epochs 1 \
    --save_model_epochs 5 \
    --num_epochs 100 \
    --learning_rate 1e-4 \
    --mixed_precision bf16 \
    --checkpointing_steps 15000 \
    --seed 1443 \
    --logger wandb \
    --wandb_id "${WANDB_ID}"
