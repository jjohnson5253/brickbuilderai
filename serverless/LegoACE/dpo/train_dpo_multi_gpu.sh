#!/usr/bin/env bash
# Example launch script for DPO refinement.
# Required env vars: DATASET_NAME, DATASET_PATH, LDR_DIR, REF_IMAGE_DIR, MODEL_PATH.
set -euo pipefail

export PYTHONPATH="${PYTHONPATH:-$(pwd)}"

: "${DATASET_NAME:?Set DATASET_NAME to your dataset name (matches data/<name>/)}"
: "${DATASET_PATH:?Set DATASET_PATH to the preference JSON built by build_cd_dataset.py}"
: "${LDR_DIR:?Set LDR_DIR to the directory of per-sample LDR files}"
: "${REF_IMAGE_DIR:?Set REF_IMAGE_DIR to the directory of 4-view reference images}"
: "${MODEL_PATH:?Set MODEL_PATH to the pretrained checkpoint to refine}"
SAVE_DIR="${SAVE_DIR:-./outputs/dpo}"

accelerate launch --config_file ./accelerate_config/8-gpu.yaml \
    dpo/train_dpo_acce.py \
    --dataset_name "${DATASET_NAME}" \
    --dataset_path "${DATASET_PATH}" \
    --ldr_dir "${LDR_DIR}" \
    --ref_image_dir "${REF_IMAGE_DIR}" \
    --model_path "${MODEL_PATH}" \
    --save_dir "${SAVE_DIR}" \
    --epochs 3 \
    --beta 0.1 \
    --batch_size 2 \
    --lr 1e-6
