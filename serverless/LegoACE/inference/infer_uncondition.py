import os
from dataclasses import dataclass
from pathlib import Path

import torch
import tyro
from tqdm import tqdm

from dataset.SingleTokenDataset import SingleTokenDataset
from model.gpt2 import SingleTokenModel
from model.tokenizer import LdrTokenizer
from utils.brick_ids import brick_id_to_non_reduced_class_id
from utils.data_utils import convert_unconditional_npy_to_ldr
from utils.render import render_glb_normal


@dataclass
class UncondInferenceArgs:
    ckpt_dir: str
    """Path to the trained unconditional checkpoint (with ``config.json`` + weights)."""

    dataset_name: str
    """Dataset name (used to load ``data/<name>/<name>_dat_dict.json`` etc.)."""

    dataset_dir: str
    """Directory containing ``*moved.npy`` files for the unconditional dataset."""

    save_dir: str = "output/unconditional"
    save_name: str = "run"

    num_samples: int = 400
    batch_size: int = 1

    pos_range: int = 256
    num_rotations: int = 20

    top_k: int = 10
    top_p: float = 0.95


def generate_batch(model, eos, batch_size, top_k, top_p):
    input_ids = torch.zeros((batch_size, 1), dtype=torch.int32, device=model.device)
    attention_mask = torch.ones((batch_size, 1), dtype=torch.bool, device=model.device)
    return model.generate(
        input_ids=input_ids,
        use_cache=True,
        pad_token_id=eos,
        bos_token_id=0,
        eos_token_id=eos,
        max_length=256,
        attention_mask=attention_mask,
        do_sample=True,
        top_k=top_k,
        top_p=top_p,
    )


def main(cfg: UncondInferenceArgs):
    dataset = SingleTokenDataset(
        cfg.dataset_dir,
        cfg.pos_range,
        cfg.num_rotations,
        len(brick_id_to_non_reduced_class_id),
    )
    eos = dataset.get_vocab_size() - 1

    # Reuse the LDR tokenizer's rotation mapping to convert rotation ids back to matrices.
    tokenizer = LdrTokenizer(cfg.dataset_name)
    rotation_id_to_array = {
        rid: [int(v) for v in rot_str.split(" ")]
        for rid, rot_str in tokenizer.id_to_rotation.items()
    }

    model = SingleTokenModel.from_pretrained(cfg.ckpt_dir).to("cuda")
    params = sum(p.numel() for p in model.parameters())
    print(f"Total number of parameters in the model: {params / 1e6:.2f}M")

    save_dir = Path(cfg.save_dir) / cfg.save_name
    ldr_save_dir = save_dir / "ldr"
    glb_save_dir = save_dir / "glb"
    render_save_dir = save_dir / "render"
    pt_save_dir = save_dir / "pt"
    for d in (save_dir, ldr_save_dir, glb_save_dir, render_save_dir, pt_save_dir):
        d.mkdir(parents=True, exist_ok=True)

    index = 0
    with tqdm(total=cfg.num_samples, desc="Inferencing") as pbar:
        while index < cfg.num_samples // cfg.batch_size:
            with torch.no_grad():
                out = generate_batch(model, eos, cfg.batch_size, cfg.top_k, cfg.top_p)
                out[:, -1] = eos
                out = out[:, 1:-1]
                if out.shape[1] % 5 != 0:
                    continue
                out_np = out.reshape([-1, 5]).cpu().numpy()
                out_np[:, 3] = out_np[:, 3] - cfg.pos_range
                out_np[:, 4] = out_np[:, 4] - cfg.num_rotations - cfg.pos_range
                convert_unconditional_npy_to_ldr(
                    out_np,
                    ldr_save_dir / f"sample-{index}.ldr",
                    color=15,
                    num_rotations=cfg.num_rotations,
                    rotation_id_to_array=rotation_id_to_array,
                )
                torch.save(out, pt_save_dir / f"sample-{index}.pt")
            index += 1
            pbar.update(cfg.batch_size)

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
    main(tyro.cli(UncondInferenceArgs))
