import json
import os
import random

import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset

os.environ.setdefault("PYOPENGL_PLATFORM", "osmesa")
import pyrender  # noqa: E402
import trimesh  # noqa: E402

from model.tokenizer import LdrTokenizer, _data_root  # noqa: E402
from utils.utils import look_at, normalize_mesh, rotation_matrices_y, sample_sphere_mv  # noqa: E402

class MVNpzDataset(Dataset):
    """Multi-view NPZ dataset for image-conditioned training and evaluation.

    Each item in the dataset JSON must provide ``ldr`` (path to the .ldr file) and
    ``npz`` (path to a per-brick NPZ archive with ``vertices``/``faces``/``vertex_normals``).

    For non-training splits, ``eval_image_dir`` may be set so that pre-rendered
    multi-view normal maps are loaded from disk instead of being rendered on the fly.
    The expected naming convention is ``{npz_stem}_{view_index}.png``.
    """

    def __init__(self, dataset_name, split, pos_range=2048, augment=False, debug=False, cfg=False,
                 eval_image_dir: str | None = None):
        super().__init__()
        data_root = _data_root()
        with open(os.path.join(data_root, dataset_name, f"{split}_dataset.json"), "r") as f:
            self.dataset = json.load(f)

        self.split = split
        self.tokenizer = LdrTokenizer(dataset_name)
        self.position_range = pos_range
        self.num_rotations = self.tokenizer.num_rotations()
        self.num_classes = self.tokenizer.num_classes()
        self.augment = augment and self.split == "train"
        self.keys = list(self.dataset.keys())
        self.eval_image_dir = eval_image_dir

        if self.augment:
            self.augment_rotations = rotation_matrices_y()

        self.augment_threshold = 0.2
        self.debug = debug
        self.cfg = cfg
    
    def get_vocab_size(self):
        return self.position_range + self.num_rotations + self.num_classes + 2

    def __len__(self):
        return len(self.keys)
    
    def __getitem__(self, index):
        key = self.keys[index]
        ldr_path = self.dataset[key]['ldr']
        npz_path = self.dataset[key]['npz']

        lego_seq_length = self.tokenizer.get_length(ldr_path)
        start = 0
        end = lego_seq_length
        if self.augment:
            if np.random.random() > self.augment_threshold:
                start = np.random.randint(0, lego_seq_length)
                end = np.random.randint(start + 1, lego_seq_length+1)
        
        rotation = np.eye(4)
        camera_positions = [np.array([1.0, 1.0, 1.0]),
                           np.array([-1.0, 1.0, 1.0]),
                           np.array([-1.0, 1.0, -1.0]),
                           np.array([1.0, 1.0, -1.0])]
        if self.augment:
            rotation = random.choice(self.augment_rotations)

            elev_min = np.radians(-15)
            elev_max = np.radians(45)
            elev = np.random.uniform(elev_min, elev_max)
            azim_min = np.radians(15)
            azim_max = np.radians(75)
            azim = np.random.uniform(azim_min, azim_max)
            camera_positions = sample_sphere_mv(elev, azim, radius=np.sqrt(3))

        # tokenize ldr, sort and move origin to (1, 1, 1)
        lego_seq = self.tokenizer.tokenize_file_with_start_and_end(ldr_path, start, end, pose=rotation)

        if self.split == "train" or self.eval_image_dir is None:
            normal_images = self.render_npz_mv(
                npz_path, camera_positions=camera_positions, rotation=rotation, start=start, end=end
            )
        else:
            normal_images = []
            for i in range(len(camera_positions)):
                image_name = os.path.basename(npz_path).replace(".npz", f"_{i}.png")
                normal_images.append(Image.open(os.path.join(self.eval_image_dir, image_name)))
        
        pos = lego_seq[: , :3]
        rotation_id = lego_seq[:, -2] + self.position_range + 1
        type_id = lego_seq[:, -1] + self.position_range + self.num_rotations + 1
        seq = np.concatenate([pos, rotation_id.reshape(-1, 1), type_id.reshape(-1, 1)], axis=1).reshape(-1)
        seq = np.concatenate([np.array([0], dtype=seq.dtype), seq, np.array([self.get_vocab_size() - 1], dtype=seq.dtype)])

        attenion_mask = np.ones(len(seq), dtype=bool)
        attenion_mask[-1] = False
        return seq, attenion_mask, normal_images
    
    
    def render_npz_mv(self, npz_path, start, end, camera_positions, rotation=None):
        loaded_data = np.load(npz_path, allow_pickle=True)
        meshes = []
        for geom_name in loaded_data.files[start:end]:
            
            vertices = loaded_data[geom_name].item()['vertices']
            faces = loaded_data[geom_name].item()['faces']
            vertex_normals = loaded_data[geom_name].item()['vertex_normals']
            mesh = trimesh.Trimesh(vertices=vertices, faces=faces, vertex_normals=vertex_normals, process=False)
            meshes.append(mesh)


        combined_mesh = trimesh.util.concatenate(meshes)
        combined_mesh = normalize_mesh(combined_mesh)
        normal_images = self.render_mesh_mv(combined_mesh, camera_positions=camera_positions, rotation=rotation)
        return normal_images

    def render_mesh_mv(self, mesh, camera_positions, rotation=None, yfov=np.pi/3.0):
        scene = pyrender.Scene()
        mesh_node = pyrender.Mesh.from_trimesh(mesh, smooth=True, poses=rotation)
        scene.add(mesh_node)
        camera = pyrender.PerspectiveCamera(yfov=yfov)
        renderer = pyrender.OffscreenRenderer(viewport_width=224, viewport_height=224)
        renderer._renderer._program_cache = pyrender.shader_program.ShaderProgramCache(shader_dir="./utils/shader")

        mv_images = []
        for camera_position in camera_positions:
            look_at_mat = look_at(camera_position, np.array([0.0, 0.0, 0.0]))
            camera_pose = np.linalg.inv(look_at_mat)

            camera_node = scene.add(camera, pose=camera_pose)

            # Set up the renderer
            normal, _ = renderer.render(scene)
            scene.remove_node(camera_node)
            mv_images.append(Image.fromarray(normal))
    
        return mv_images
    
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
    seq, attenion_mask, images = zip(*batch)
    max_len = max([s.shape[0] for s in seq])
    def id_padding(length):
        return (0, max_len - length)
    seq = np.stack([pad_to_max_length(s, id_padding(len(s))) for s in seq])
    attenion_mask = np.stack([pad_to_max_length(a, id_padding(len(a))) for a in attenion_mask])


    return torch.tensor(seq), torch.tensor(attenion_mask), images

