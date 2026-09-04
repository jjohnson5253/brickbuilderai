import base64

import numpy as np
import pytest

from src.stability_analysis.utils import construct_world_grid, gen_key, out_boundary
from src.utils.color_conversions import _precompute_lab_color_map, _srgb_to_lab, rgb_to_ldr_color
from src.utils.conversions.voxel2brick import first_nonzero_idx, first_zero_idx, get_merged_brick, k_ring_neighbors, valid_brick
from src.utils.sam3d_stream import _sse, decode_sam3d_voxels_to_xyzrgb, parse_fal_stream_results
from src.data.brick_structure import Brick


def test_stability_grid_and_coordinate_helpers():
    library = {"1": {"height": 1, "width": 2}}
    grid = construct_world_grid({"1": {"brick_id": 1, "ori": 0, "x": 1, "y": 2, "z": 0}}, (4, 5, 2), library)
    assert grid[:, :, 0].sum() == 2
    assert gen_key(1, 2, 3) == "X: 1, Y: 2, Z: 3"
    assert out_boundary((0, 2), 1, 2, 1, 2)
    assert not out_boundary((1, 3), 1, 2, 1, 2)


def test_color_conversion_matches_exact_colors_and_defaults():
    colors = {4: (1.0, 0.0, 0.0), 1: (0.0, 0.0, 1.0), 16: (0.5, 0.5, 0.5)}
    cache = _precompute_lab_color_map(colors)
    assert {item[0] for item in cache} == {1, 4}
    code, rgb = rgb_to_ldr_color(np.array([1.0, 0.0, 0.0]), colors, cache)
    assert code == 4
    assert np.array_equal(rgb, [1.0, 0.0, 0.0])
    assert rgb_to_ldr_color(np.array([1.0, 2.0]), colors)[0] == 7
    assert np.allclose(_srgb_to_lab(np.array([1.0, 1.0, 1.0])), [100, 0, 0], atol=0.01)


def test_voxel_array_helpers_and_brick_merging():
    values = np.array([[1, 1, 0], [0, 1, 1]])
    assert first_zero_idx(values).tolist() == [2, 0]
    assert first_nonzero_idx(values).tolist() == [0, 1]
    assert valid_brick(1, 2)
    assert not valid_brick(3, 3)
    merged = get_merged_brick(Brick(h=1, w=1, x=0, y=0, z=0), Brick(h=1, w=1, x=1, y=0, z=0))
    assert merged == Brick(h=2, w=1, x=0, y=0, z=0)
    assert get_merged_brick(Brick(h=1, w=1, x=0, y=0, z=0), Brick(h=1, w=1, x=3, y=0, z=0)) is None


def test_sam3d_sse_decode_deduplicates_positions_and_averages_colors():
    packed = bytes([0, 0, 0, 10, 20, 30, 0, 0, 0, 30, 40, 50, 255, 128, 0, 100, 110, 120])
    text = decode_sam3d_voxels_to_xyzrgb(base64.b64encode(packed).decode(), [0, 0, 0], [1, 1, 1], 18)
    assert text.splitlines() == ["0 0 0 20 30 40", "1 1 0 100 110 120"]
    assert _sse({"ok": True}) == b'data: {"ok": true}\n\n'


def test_parse_fal_stream_results_keeps_latest_appearance_and_glb():
    glb = base64.b64encode(b"glb").decode()
    raw = "\n\n".join([
        'data: {"type":"appearance","voxel_data":"old","bounds_min":[0],"bounds_max":[1]}',
        'data: {"type":"appearance","voxel_data":"new","bounds_min":[0],"bounds_max":[1]}',
        f'data: {{"type":"glb_ready","glb_data":"{glb}"}}',
        'data: {"type":"complete","model_glb_url":"https://model"}',
        'data: not-json "complete"',
    ])
    result = parse_fal_stream_results(raw)
    assert result["last_appearance"]["voxel_data"] == "new"
    assert result["model_glb_url"] == "https://model"
    assert result["glb_bytes"] == b"glb"
    with pytest.raises(Exception, match="failed"):
        parse_fal_stream_results('data: {"type":"error","message":"failed"}')
