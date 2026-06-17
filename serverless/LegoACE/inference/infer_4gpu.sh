#!/usr/bin/env bash
# Example launch script for single-image inference.
set -euo pipefail

export PYTHONPATH="${PYTHONPATH:-$(pwd)}"

DATASET_NAME="${DATASET_NAME:-bricklink-unique-1280-5w}"
CKPT_DIR="${CKPT_DIR:-VAST-AI/LegoACE}"
SAVE_NAME="${SAVE_NAME:-image-run}"

python inference/inference_image_condition.py \
    --dataset_name "${DATASET_NAME}" \
    --ckpt_dir "${CKPT_DIR}" \
    --save_name "${SAVE_NAME}" \
    --infer_number 40 \
    --ckpt_iter 520000
