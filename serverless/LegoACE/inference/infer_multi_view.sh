#!/usr/bin/env bash
# Example launch script for multi-view inference.
set -euo pipefail

export PYTHONPATH="${PYTHONPATH:-$(pwd)}"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"

DATASET_NAME="${DATASET_NAME:-bricklink-unique-1280-5w}"
CKPT_DIR="${CKPT_DIR:-VAST-AI/LegoACE}"
SAVE_NAME="${SAVE_NAME:-mv-run}"

python inference/inference_multi_view.py \
    --dataset_name "${DATASET_NAME}" \
    --ckpt_dir "${CKPT_DIR}" \
    --dataset_class dataset.MVNpzDataset.MVNpzDataset \
    --save_name "${SAVE_NAME}" \
    --infer_number 100 \
    --batch_size 4 \
    --repeat 4 \
    --dataset_split val \
    --ckpt_iter 260000
