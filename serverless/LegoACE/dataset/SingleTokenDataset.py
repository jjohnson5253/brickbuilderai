import os
import torch
import numpy as np

from torch.utils.data import Dataset
from utils.brick_ids import class_id_to_brick_id, non_reduced_class_id_to_brick_id



def get_id2label():
    """Mapping from class index to human-readable label."""
    return class_id_to_brick_id

class SingleTokenDataset(Dataset):
    def __init__(self, dataset_dir, postion_range, num_rotations, num_classes):
        # self.num_classes = num_classes
        self.num_rotations = num_rotations
        self.num_classes = num_classes
        self.position_range = postion_range
        self.seq_file_paths = []
        for root, dirs, files in os.walk(dataset_dir):
            for file in files:
                if file.endswith("moved.npy"):
                    self.seq_file_paths.append(os.path.join(root, file))
    
    def get_vocab_size(self):
        return self.position_range + self.num_rotations + self.num_classes + 2
    def __len__(self):
        return len(self.seq_file_paths)
    
    def __getitem__(self, idx):
        seq_file = self.seq_file_paths[idx]
        lego_seq = np.load(seq_file)

        pos = lego_seq[: , :3]
        # LEGO -y, alreay done in the data_process.py
        # pos[:, 1] = -pos[:, 1]
        rotation_id = lego_seq[:, -2] + self.position_range
        type_id = lego_seq[:, -1] + self.position_range + self.num_rotations

        seq = np.concatenate([pos, rotation_id.reshape(-1, 1), type_id.reshape(-1, 1)], axis=1).reshape(-1)
        seq = np.concatenate([np.array([0], dtype=seq.dtype), seq, np.array([self.get_vocab_size() - 1], dtype=seq.dtype)])

        attenion_mask = np.ones(len(seq), dtype=np.bool_)
        attenion_mask[-1] = False
        return seq, attenion_mask

def pad_to_max_length(array, padding):
    return np.pad(array, padding, mode='constant', constant_values=0)


def Single_collate_fn(batch):
    # pad each sequence to the max length, add a bos token at the beginning and an eos token at the end
    seq, attenion_mask = zip(*batch)

    max_len = max([s.shape[0] for s in seq])
    def pos_padding(length):
        return ((0, max_len -length), (0, 0))
    
    def id_padding(length):
        return (0, max_len - length)
    
    seq = np.stack([pad_to_max_length(s, id_padding(len(s))) for s in seq])

    attenion_mask = np.stack([pad_to_max_length(a, id_padding(len(a))) for a in attenion_mask])

    return torch.tensor(seq), torch.tensor(attenion_mask)
