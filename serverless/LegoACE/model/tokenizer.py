import json
import os

import numpy as np


def _data_root() -> str:
    """Return the dataset root directory.

    By default uses ``./data`` relative to the current working directory; override with
    the ``LEGOACE_DATA_ROOT`` environment variable to point elsewhere without editing code.
    """
    return os.environ.get("LEGOACE_DATA_ROOT", "data")


class LdrTokenizer:
    """Tokenize / detokenize LDR brick sequences against per-dataset vocabulary files.

    Loads two JSON files from ``<data_root>/<dataset_name>/``:
      * ``<dataset_name>_dat_dict.json``: brick type -> id
      * ``<dataset_name>_rot_dict.json``: rotation matrix string -> id
    """

    def __init__(self, dataset_name, data_root: str | None = None):
        root = data_root if data_root is not None else _data_root()
        with open(os.path.join(root, dataset_name, f"{dataset_name}_dat_dict.json"), "r") as f:
            self.dat_dict = json.load(f)

        with open(os.path.join(root, dataset_name, f"{dataset_name}_rot_dict.json"), "r") as f:
            self.rot_dict = json.load(f)

        self.id_to_dat = {v: k for k, v in self.dat_dict.items()}
        self.id_to_rotation = {v: k for k, v in self.rot_dict.items()}

    def num_rotations(self):
        return len(self.rot_dict)

    def num_classes(self):
        return len(self.dat_dict)

    def tokenize(self, lines, pose=None):
        tokens = []
        if pose is not None and pose[0, 0] == 0:
            # same as transpose
            pose = np.dot(pose, np.array([[-1, 0, 0, 0], [0, 1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]]))
        for line in lines:
            line_data = []
            line = line.strip().split(" ")
            assert len(line) == 15, line
            if pose is None:
                pos_str = line[2:5]
                pos = list(map(float, pos_str))
                line_data.extend([round(pos[0]), -round(pos[1]), round(pos[2])])

                rot_str = line[5:14]
                rot_str = [str(round(float(x))) for x in rot_str]
                rot_str = " ".join(rot_str)
                assert rot_str in self.rot_dict
                rot_id = self.rot_dict[rot_str]
                line_data.append(rot_id)
            else:
                pos = np.array(list(map(float, line[2:5])))
                pos = np.dot(pose[:3, :3], pos) + pose[:3, 3]
                line_data.extend([round(pos[0]), -round(pos[1]), round(pos[2])])

                rot_str = line[5:14]
                rot_mat = np.array(list(map(float, rot_str))).reshape(3, 3)
                rot_mat = np.dot(pose[:3, :3], rot_mat)
                rot_str = " ".join([str(round(x)) for x in rot_mat.flatten()])
                assert rot_str in self.rot_dict
                rot_id = self.rot_dict[rot_str]
                line_data.append(rot_id)

            type_str = line[14]
            assert type_str in self.dat_dict.keys()
            type_id = self.dat_dict[type_str]
            line_data.append(type_id)
            tokens.append(line_data)
        tokens = np.array(tokens, dtype=np.int32)
        tokens = tokens[np.lexsort((tokens[:, 2], tokens[:, 0], tokens[:, 1]))]
        tokens_min = tokens[:, :3].min(axis=0)
        tokens[:, :3] = tokens[:, :3] - tokens_min + 1
        return tokens
    
    def tokenize_file(self, ldr_file, pose=None):
        with open(ldr_file, "r") as f:
            lines = f.readlines()
        lines = [line for line in lines if line.startswith("1")]
        tokens = self.tokenize(lines, pose=pose)
        return tokens
    
    def get_length(self, ldr_file):
        with open(ldr_file, "r") as f:
            lines = f.readlines()
        lines = [line for line in lines if line.startswith("1")]
        return len(lines)
    
    def tokenize_file_with_start_and_end(self, ldr_file, start, end, pose=None):
        with open(ldr_file, "r") as f:
            lines = f.readlines()
        lines = [line for line in lines if line.startswith("1")]
        lines = lines[start:end]
        tokens = self.tokenize(lines, pose=pose)
        return tokens
    
    def detokenize(self, tokens):
        # tokens = tokens.reshape(-1, 5)
        ldr = []
        for data in tokens:
            pos = data[:3]
            rot_id = data[3]
            type_id = data[4]
            rot_str = self.id_to_rotation[rot_id]
            type_str = self.id_to_dat[type_id]
            
            ldr.append(f"1 15 {pos[0]} {-pos[1]} {pos[2]} {rot_str} {type_str}\n")
        return ldr