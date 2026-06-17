import torch
from transformers import AutoImageProcessor, AutoModel
from pathlib import Path

import os
from tqdm import tqdm
import tyro

from utils.render import render_glb_normal
from utils.infer_utils import make_compare_mv, make_compare_with_repeat_mv

from model.logitsprocessor import DynamicRangeMaskingProcessor
from utils.misc import get_obj_from_str
from configs.config import InferenceArgs

from PIL import Image, ImageOps

def pad_rgb_pil(image_path, pad_size=10, pad_color=(255, 255, 255)):
    img = Image.open(image_path).convert('RGB')
    padded_img = ImageOps.expand(img, border=pad_size, fill=pad_color)
    return padded_img


def generete_batch(condition_embeds, uncondition_embeds, model, logits_processor, cfg, eos):
    batch_size = condition_embeds.shape[0]
    input_ids = torch.zeros((batch_size, 1), dtype=torch.int32, device=model.device)
    attention_mask = torch.ones((batch_size, 1), dtype=torch.bool, device=model.device)
    
    kwargs = {
            'input_ids': input_ids,
            'use_cache': True,
            'condition_embeds': condition_embeds,
            'uncondition_embeds': uncondition_embeds,
            'pad_token_id': eos,
            'bos_token_id': 0,
            'eos_token_id': eos,
            'max_length': cfg.max_length + 2,
            'attention_mask': attention_mask,
            'logits_processor': [logits_processor],
        }
    if cfg.sample_type == "no_sample":
        kwargs['num_beams'] = 1
    elif cfg.sample_type == "top_k":
        kwargs['do_sample'] = True
        kwargs['top_k'] = cfg.top_k_number
    elif cfg.sample_type == "top_k_and_p":
        kwargs['do_sample'] = True
        kwargs['top_k'] = cfg.top_k_number
        kwargs['top_p'] = cfg.top_p_number
    out = model.generate(**kwargs)
    return out

if __name__ == "__main__":
    cfg = tyro.cli(InferenceArgs)
    assert cfg.batch_size % cfg.repeat == 0
    dataset_cls = get_obj_from_str(cfg.dataset_class)
    model_cls = get_obj_from_str(cfg.model_class)

    dataset = dataset_cls(cfg.dataset_name, cfg.dataset_split, pos_range=cfg.pos_range)
    num_rot = dataset.num_rotations
    num_dat = dataset.num_classes
    pos_range = dataset.position_range
    logits_processor = DynamicRangeMaskingProcessor(pos_range, num_rot, num_dat)

    eos = dataset.get_vocab_size() - 1

    print("preparing input images")
    test_images = []
    input_ids = []
    gt_length = []
    with tqdm(total=cfg.infer_number) as pbar:
        for i in range(cfg.infer_number):
            data = dataset[i]
            test_images.append(data[2])

            pbar.update(1)
    
    ckpt_path = cfg.ckpt_dir
    if ckpt_path.startswith("VAST-AI/") or ckpt_path.startswith("hf://"):
        subfolder = "mv"
    elif cfg.ckpt_iter > 0 and not Path(ckpt_path, "config.json").exists():
        ckpt_path = str(Path(ckpt_path) / f"checkpoint-{cfg.ckpt_iter}/transformer")
        subfolder = None
    else:
        subfolder = None
    model = model_cls.from_pretrained(ckpt_path, subfolder=subfolder).to("cuda")
    model.register_inference_cfg(cfg.cfg_number)
    params = sum(p.numel() for p in model.parameters())
    print(f"Total number of parameters in the model: {params / 1e6:.2f}M")

    dino_processor = AutoImageProcessor.from_pretrained('facebook/dinov2-base', use_fast=False)
    dino_model = AutoModel.from_pretrained('facebook/dinov2-base').to("cuda")
    save_dir = (
        Path(cfg.save_dir)
        / cfg.save_name
        / cfg.dataset_split
        / f"ckpt-{cfg.ckpt_iter}_samples-{cfg.repeat}_cfg-{cfg.cfg_number}"
        / f"{cfg.sample_type}_k{cfg.top_k_number}_p{cfg.top_p_number}"
    )
    
    
    ldr_save_dir = save_dir / "ldr"
    glb_save_dir = save_dir / "glb"
    render_save_dir = save_dir / "render"
    image_save_dir = save_dir / "input_image"

    save_dir.mkdir(parents=True, exist_ok=True)
    ldr_save_dir.mkdir(parents=True, exist_ok=True)
    glb_save_dir.mkdir(parents=True, exist_ok=True)
    render_save_dir.mkdir(parents=True, exist_ok=True)
    image_save_dir.mkdir(parents=True, exist_ok=True)

    img_count = 0
    condition_images = []
    uncondition_images = []
    save_path = []
    empty_image = Image.new("RGB", (512, 512), (255, 255, 255))
    with tqdm(total=len(test_images) * cfg.repeat) as pbar:
        pbar.set_description("Inferencing")
        for index, images in enumerate(test_images):
            file_name = f"{index:04d}"
            for i, image in enumerate(images):
                image.save(image_save_dir / f"{file_name}_{i}.png")

            if cfg.repeat == 1:
                save_path.append(ldr_save_dir / f"{file_name}.ldr")
                condition_images.append(images)
                uncondition_images.append(empty_image)
            else:
                repeat_images = [images] * cfg.repeat
                repeat_path = [ldr_save_dir / f"{index:04d}-{i}.ldr" for i in range(cfg.repeat)]
                repeat_uncondition_images = [empty_image] * cfg.repeat
                condition_images.extend(repeat_images)
                uncondition_images.extend(repeat_uncondition_images)
                save_path.extend(repeat_path)
            img_count += cfg.repeat
            if img_count % cfg.batch_size == 0:
                condition_images = [item for sublist in condition_images for item in sublist]
                input_dino = dino_processor(condition_images, return_tensors="pt")
                input_dino_uncondition = dino_processor(uncondition_images, return_tensors='pt')
                for k, v in input_dino.items():
                    input_dino[k] = v.to("cuda")
                for k, v in input_dino_uncondition.items():
                    input_dino_uncondition[k] = v.to("cuda")
                with torch.no_grad():
                    condition_embeds = dino_model(**input_dino)['last_hidden_state']
                    condition_embeds = condition_embeds.reshape(condition_embeds.shape[0] // 4, condition_embeds.shape[1] * 4, -1)
                    unconition_embdes = dino_model(**input_dino_uncondition)['last_hidden_state']
                    out = generete_batch(condition_embeds, unconition_embdes, model, logits_processor, cfg, eos)
                    out[:, -1] = eos
                for i, data in enumerate(out):
                    lego_model = data.cpu().numpy()
                    try:
                        if cfg.use_0_dot_1:
                            ldr = dataset.convert_npy_to_ldr_10(lego_model)
                        else:
                            ldr = dataset.convert_npy_to_ldr(lego_model)
                        with open(save_path[i], "w") as f:
                            f.writelines(ldr)
                    except Exception as e:
                        print(save_path[i])
                        print(e)
                condition_images = []
                save_path = []
                uncondition_images = []
                pbar.update(cfg.batch_size)


    blender_bin = os.environ.get("BLENDER_BIN", "blender")
    command = (f"{blender_bin} "
            "--background --python "
            "utils/ldr_export_dir.py -- "
            f"{str(ldr_save_dir)} {str(glb_save_dir)} "
            "> /dev/null 2>&1")
    os.system(command)

    
    print("Render results")
    for glb in tqdm(glb_save_dir.glob("*.glb")):
        normal_path = render_save_dir / (glb.stem + ".png")
        normal_image = render_glb_normal(str(glb))
        normal_image.save(normal_path)

    if cfg.repeat == 1:
        images_per_row = 4
        new_image = make_compare_mv(image_save_dir, render_save_dir, images_per_row=images_per_row)
        new_image.save(save_dir / f"compare_{images_per_row}.png")
    else:
        compare_image = make_compare_with_repeat_mv(image_save_dir, render_save_dir, repeat=cfg.repeat, samples_per_row=1)
        compare_image.save(save_dir / f"compare-repeat-{cfg.repeat}.png")
