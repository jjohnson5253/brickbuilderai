import base64
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.requests.llmRender import _apply_rules, _build_voxel_preview_data_url


def test_build_voxel_preview_data_url_returns_multiview_png():
    voxels = [
        {"x": 0, "y": 0, "z": 0, "r": 255, "g": 0, "b": 0},
        {"x": 1, "y": 0, "z": 0, "r": 0, "g": 255, "b": 0},
        {"x": 0, "y": 1, "z": 1, "r": 0, "g": 0, "b": 255},
    ]

    data_url = _build_voxel_preview_data_url(voxels)

    assert data_url.startswith("data:image/png;base64,")
    image_bytes = base64.b64decode(data_url.split(",", 1)[1])
    image = Image.open(BytesIO(image_bytes))
    assert image.format == "PNG"
    assert image.size == (792, 284)


def test_apply_rules_preserves_reason_and_caps_rule_count():
    voxels = [
        {"x": 0, "y": 0, "z": 0, "r": 0, "g": 0, "b": 0},
    ]
    rules = [
        {
            "name": f"rule-{index}",
            "reason": f"reason-{index}",
            "selector": {
                "x": [0, 1],
                "y": [0, 1],
                "z": [0, 1],
                "source_colors": [],
                "color_tolerance": 60,
            },
            "color": [index, 0, 0],
            "strength": 1,
        }
        for index in range(20)
    ]

    recolored, applied_rules = _apply_rules(voxels, rules)

    assert len(applied_rules) == 16
    assert applied_rules[0]["reason"] == "reason-0"
    assert applied_rules[-1]["name"] == "rule-15"
    assert recolored[0]["r"] == 15
