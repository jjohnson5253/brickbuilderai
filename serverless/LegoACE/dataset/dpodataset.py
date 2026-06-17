import json
import os
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset

os.environ.setdefault("PYOPENGL_PLATFORM", "egl")

from model.tokenizer import LdrTokenizer  # noqa: E402



class DPODataset(Dataset):
    """DPO preference dataset for image-conditioned refinement.

    Args:
        dataset_name: Dataset name used to load the LDR tokenizer.
        dataset_file: JSON file with preference pairs, each entry of the form
            ``{"prompt_id": str, "chosen": str, "rejected": str}``.
        ldr_dir: Directory containing per-sample LDR files named
            ``{prompt_id}-{sample_id}.ldr``.
        ref_image_dir: Directory containing 4-view reference images named
            ``{prompt_id}-{0..3}.png``.
        pos_range: Position vocabulary size.
    """

    def __init__(self, dataset_name, dataset_file, ldr_dir, ref_image_dir, pos_range=1280):
        super().__init__()
        with open(dataset_file, "r") as f:
            self.dataset = json.load(f)

        self.tokenizer = LdrTokenizer(dataset_name)
        self.position_range = pos_range
        self.num_rotations = self.tokenizer.num_rotations()
        self.num_classes = self.tokenizer.num_classes()

        self.ldr_dir = Path(ldr_dir)
        self.ref_path = Path(ref_image_dir)

    def get_vocab_size(self):
        return self.position_range + self.num_rotations + self.num_classes + 2

    def __len__(self):
        return len(self.dataset)

    def get_ldr_path(self, index, id):
        ldr_path = self.ldr_dir / f"{id}-{index}.ldr"
        if not ldr_path.exists():
            raise FileNotFoundError(f"Ldr file not found: {ldr_path}")
        return ldr_path

    def get_ref_image(self, id):
        ref_image_paths = [self.ref_path / f"{id}-{i}.png" for i in range(4)]
        for ref_image_path in ref_image_paths:
            if not ref_image_path.exists():
                raise FileNotFoundError(f"Reference image not found: {ref_image_path}")
        return ref_image_paths
    
    
    def __getitem__(self, index):
        data = self.dataset[index]
        id = data['prompt_id']
        chosen = data['chosen']
        rejected = data['rejected']
        ldr_chosen = self.get_ldr_path(chosen, id)
        ldr_rejected = self.get_ldr_path(rejected, id)
        ldr_image = self.get_ref_image(id)
        chosen_id = self.tokenizer.tokenize_file(ldr_chosen)
        rejected_id = self.tokenizer.tokenize_file(ldr_rejected)

        chosen_id = self.post_idprocess(chosen_id)
        rejected_id = self.post_idprocess(rejected_id)

        images = [Image.open(image) for image in ldr_image]
        return chosen_id, rejected_id, images

    def post_idprocess(self, id):
        pos = id[: , :3]
        rotation_id = id[:, -2] + self.position_range + 1
        type_id = id[:, -1] + self.position_range + self.num_rotations + 1
        seq = np.concatenate([pos, rotation_id.reshape(-1, 1), type_id.reshape(-1, 1)], axis=1).reshape(-1)
        seq = np.concatenate([np.array([0], dtype=seq.dtype), seq, np.array([self.get_vocab_size() - 1], dtype=seq.dtype)])
        return seq
    
    def convert_npy_to_ldr(self, npy_data):
        npy_data = npy_data.astype(int)
        eos = self.get_vocab_size() - 1
        last_non_x_index = (npy_data == eos).argmax()
        npy_data = npy_data[1:last_non_x_index]

        npy_data = npy_data.reshape(-1, 5)
        npy_data[:, 3] = npy_data[:, 3] - self.position_range - 1
        npy_data[:, 4] = npy_data[:, 4] - self.position_range - self.num_rotations - 1
        
        ldr = self.tokenizer.detokenize(npy_data)
        return ldr
    
    

def pad_to_max_length(array, padding):
    return np.pad(array, padding, mode='constant', constant_values=0)


def collate_fn(batch):
    # pad each sequence to the max length, add a bos token at the beginning and an eos token at the end
    chosens, rejects, images = zip(*batch)
    chosens_mask = []
    for chosen in chosens:
        chosen_mask = np.ones(len(chosen), dtype=bool)
        chosen_mask[-1] = False
        chosens_mask.append(chosen_mask)
    
    rejects_mask = []
    for reject in rejects:
        reject_mask = np.ones(len(reject), dtype=bool)
        reject_mask[-1] = False
        rejects_mask.append(reject_mask)

    def id_padding(length, max_len):
        return (0, max_len - length)
    
    max_len_chosen = max([s.shape[0] for s in chosens])
    chosens = np.stack([pad_to_max_length(s, id_padding(len(s), max_len_chosen)) for s in chosens])
    chosens_mask = np.stack([pad_to_max_length(a, id_padding(len(a), max_len_chosen)) for a in chosens_mask])

    max_len_reject = max([s.shape[0] for s in rejects])
    rejects = np.stack([pad_to_max_length(s, id_padding(len(s), max_len_reject)) for s in rejects])
    rejects_mask = np.stack([pad_to_max_length(a, id_padding(len(a), max_len_reject)) for a in rejects_mask])

    return {
        "chosens": torch.as_tensor(chosens),
        "chosens_mask": torch.as_tensor(chosens_mask),
        "rejects": torch.as_tensor(rejects),
        "rejects_mask": torch.as_tensor(rejects_mask),
        "images": images,
    }
