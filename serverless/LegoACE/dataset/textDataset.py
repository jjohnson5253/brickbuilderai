import json
import os

import numpy as np
import torch
from torch.utils.data import Dataset

from model.tokenizer import LdrTokenizer, _data_root


class TextDataset(Dataset):
    def __init__(self, dataset_name, split, pos_range=2048):
        super().__init__()
        data_root = _data_root()
        with open(os.path.join(data_root, dataset_name, f"{split}_dataset.json"), "r") as f:
            self.dataset = json.load(f)
        
        self.split = split
        self.tokenizer = LdrTokenizer(dataset_name)
        self.position_range = pos_range
        self.num_rotations = self.tokenizer.num_rotations()
        self.num_classes = self.tokenizer.num_classes()
        self.keys = list(self.dataset.keys())

        self.text_count = 4        
        self.augment_threshold = 0.2
    
    def get_vocab_size(self):
        return self.position_range + self.num_rotations + self.num_classes + 2

    def __len__(self):
        return len(self.keys) * self.text_count
    
    def __getitem__(self, index):
        text_index = index % self.text_count
        data_index = index % len(self.keys)
        key = self.keys[data_index]
        ldr_path = self.dataset[key]['ldr']

        text = self.dataset[key]['text'][text_index]

        lego_seq = self.tokenizer.tokenize_file(ldr_path)

        pos = lego_seq[: , :3]
        rotation_id = lego_seq[:, -2] + self.position_range + 1
        type_id = lego_seq[:, -1] + self.position_range + self.num_rotations + 1
        seq = np.concatenate([pos, rotation_id.reshape(-1, 1), type_id.reshape(-1, 1)], axis=1).reshape(-1)
        seq = np.concatenate([np.array([0], dtype=seq.dtype), seq, np.array([self.get_vocab_size() - 1], dtype=seq.dtype)])

        attenion_mask = np.ones(len(seq), dtype=bool)
        attenion_mask[-1] = False
        return seq, attenion_mask, text

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
    seq, attenion_mask, text = zip(*batch)
    max_len = max([s.shape[0] for s in seq])
    def id_padding(length):
        return (0, max_len - length)
    seq = np.stack([pad_to_max_length(s, id_padding(len(s))) for s in seq])
    attenion_mask = np.stack([pad_to_max_length(a, id_padding(len(a))) for a in attenion_mask])


    return torch.tensor(seq), torch.tensor(attenion_mask), text

