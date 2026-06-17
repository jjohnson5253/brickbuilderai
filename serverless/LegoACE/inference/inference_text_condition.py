import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import torch
import tyro
from tqdm import tqdm
from transformers import CLIPTextModel, CLIPTokenizer

from dataset.textDataset import TextDataset
from model.llama_text_condition import TextConditionModel
from model.logitsprocessor import DynamicRangeMaskingProcessor
from utils.render import render_glb_normal


@dataclass
class TextInferenceArgs:
    ckpt_dir: str = "VAST-AI/LegoACE"
    """Local checkpoint directory or HuggingFace repo id."""

    dataset_name: str = "bricklink-text"
    """Dataset name (used only to load the LDR tokenizer)."""

    dataset_split: str = "val"
    save_dir: str = "output/text"
    save_name: str = "run"

    pos_range: int = 1280
    max_length: int = 5000

    top_k: int = 10
    top_p: float = 0.95

    repeat: int = 4
    """Number of samples to generate per text prompt."""

    batch_size: int = 4
    """Generation batch size. Must be divisible by ``repeat``."""

    prompts: List[str] = field(default_factory=list)
    """Optional list of text prompts. If empty, prompts are taken from the dataset."""

    infer_number: int = 10
    """Number of prompts to take from the dataset when ``prompts`` is empty."""


def generate_batch(condition_embeds, model, logits_processor, eos, max_length, top_k, top_p):
    batch_size = condition_embeds.shape[0]
    input_ids = torch.zeros((batch_size, 1), dtype=torch.int32, device=model.device)
    attention_mask = torch.ones((batch_size, 1), dtype=torch.bool, device=model.device)

    return model.generate(
        input_ids=input_ids,
        use_cache=True,
        condition_embeds=condition_embeds,
        pad_token_id=eos,
        bos_token_id=0,
        eos_token_id=eos,
        max_length=max_length + 2,
        attention_mask=attention_mask,
        logits_processor=[logits_processor],
        do_sample=True,
        top_k=top_k,
        top_p=top_p,
    )


def resolve_ckpt(ckpt_dir: str) -> tuple[str, Optional[str]]:
    """Resolve a checkpoint path. Returns ``(path, subfolder)``."""
    if ckpt_dir.startswith("VAST-AI/") or ckpt_dir.startswith("hf://"):
        return ckpt_dir, "text"
    return ckpt_dir, None


def main(cfg: TextInferenceArgs):
    assert cfg.batch_size % cfg.repeat == 0, "batch_size must be divisible by repeat"

    dataset = TextDataset(cfg.dataset_name, cfg.dataset_split, pos_range=cfg.pos_range)
    logits_processor = DynamicRangeMaskingProcessor(dataset.position_range, dataset.num_rotations, dataset.num_classes)
    eos = dataset.get_vocab_size() - 1

    clip_tokenizer = CLIPTokenizer.from_pretrained("openai/clip-vit-base-patch32")
    clip_model = CLIPTextModel.from_pretrained("openai/clip-vit-base-patch32").to("cuda")

    ckpt_path, subfolder = resolve_ckpt(cfg.ckpt_dir)
    model = TextConditionModel.from_pretrained(ckpt_path, subfolder=subfolder).to("cuda")
    params = sum(p.numel() for p in model.parameters())
    print(f"Total number of parameters in the model: {params / 1e6:.2f}M")

    save_dir = Path(cfg.save_dir) / cfg.save_name
    ldr_save_dir = save_dir / "ldr"
    glb_save_dir = save_dir / "glb"
    render_save_dir = save_dir / "render"
    for d in (save_dir, ldr_save_dir, glb_save_dir, render_save_dir):
        d.mkdir(parents=True, exist_ok=True)

    if cfg.prompts:
        test_text = list(cfg.prompts)
    else:
        test_text = [dataset[i][2] for i in range(cfg.infer_number)]

    condition_texts: list[str] = []
    save_path: list[Path] = []
    text_to_out: dict[str, str] = {}
    text_count = 0

    with tqdm(total=len(test_text) * cfg.repeat, desc="Inferencing") as pbar:
        for index, text in enumerate(test_text):
            file_name = f"{index:04d}"
            text_to_out[file_name] = text
            condition_texts.extend([text] * cfg.repeat)
            save_path.extend(ldr_save_dir / f"{file_name}-{i}.ldr" for i in range(cfg.repeat))
            text_count += cfg.repeat

            if text_count % cfg.batch_size == 0:
                input_clip = clip_tokenizer(
                    condition_texts,
                    padding="max_length",
                    max_length=clip_tokenizer.model_max_length,
                    return_tensors="pt",
                )
                input_clip = {k: v.to("cuda") for k, v in input_clip.items()}

                with torch.no_grad():
                    condition_embeds = clip_model(**input_clip)[0]
                    out = generate_batch(
                        condition_embeds, model, logits_processor, eos,
                        cfg.max_length, cfg.top_k, cfg.top_p,
                    )
                    out[:, -1] = eos

                for i, data in enumerate(out):
                    ldr = dataset.convert_npy_to_ldr(data.cpu().numpy())
                    with open(save_path[i], "w") as f:
                        f.writelines(ldr)

                condition_texts = []
                save_path = []
                pbar.update(cfg.batch_size)

    with open(save_dir / "input.json", "w") as f:
        json.dump(text_to_out, f, indent=4)

    blender_bin = os.environ.get("BLENDER_BIN", "blender")
    command = (
        f"{blender_bin} --background --python utils/ldr_export_dir.py -- "
        f"{ldr_save_dir} {glb_save_dir} > /dev/null 2>&1"
    )
    os.system(command)

    print("Render results")
    for glb in tqdm(glb_save_dir.glob("*.glb")):
        normal_path = render_save_dir / (glb.stem + ".png")
        normal_image = render_glb_normal(str(glb))
        normal_image.save(normal_path)


if __name__ == "__main__":
    main(tyro.cli(TextInferenceArgs))
