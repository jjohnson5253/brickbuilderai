from dataclasses import dataclass


@dataclass
class InferenceArgs:
    """Command-line arguments for the image / multi-view inference scripts."""

    dataset_name: str = "your-dataset-name"
    """Dataset name (must match a directory under ``data/``)."""

    dataset_class: str = "dataset.MVNpzDataset.MVNpzDataset"
    """Fully-qualified dataset class to instantiate."""

    model_class: str = "model.llama_image_condition.ImageConditionModel"
    """Fully-qualified model class to instantiate."""

    ckpt_dir: str = "VAST-AI/LegoACE"
    """Local checkpoint directory or HuggingFace repo id."""

    ckpt_iter: int = 0
    """Checkpoint iteration (only used when ``ckpt_dir`` is a local training output)."""

    pos_range: int = 1280
    dataset_split: str = "test"

    batch_size: int = 4
    infer_number: int = 10
    max_length: int = 5000

    save_dir: str = "output/inference"
    save_name: str = "run"

    cfg_number: float = 0.0
    """Classifier-free guidance scale (0.0 disables CFG)."""

    sample_type: str = "top_k_and_p"
    """One of ``"top_k_and_p"``, ``"top_k"``, ``"no_sample"``."""

    top_k_number: int = 10
    top_p_number: float = 0.95

    repeat: int = 4
    """Number of samples per input. ``batch_size`` must be divisible by ``repeat``."""

    use_0_dot_1: bool = False
    """Use the alternative ``convert_npy_to_ldr_10`` decoder if the dataset provides it."""
