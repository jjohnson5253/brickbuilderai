import asyncio
import base64
import importlib
import json
import sys
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.requests.llmRender import (
    SEGMENT_PALETTE,
    VIEWS,
    _apply_assignments,
    _assignment_schema,
    _build_scene_summary,
    _build_voxel_preview_data_url,
    _extract_thinking_delta,
    _geometric_regions,
    _load_font,
    LlmRenderResponse,
    llm_render_stream,
    _perceptual_colors,
    _project_segments,
    _quantize_colors,
    _render_view_tile,
    _rgb_to_lab,
    _segment_voxels,
    _voxel_arrays,
)


def _block(x_range, y_range, z_range, color):
    return [
        {"x": x, "y": y, "z": z, "r": color[0], "g": color[1], "b": color[2]}
        for x in range(*x_range)
        for y in range(*y_range)
        for z in range(*z_range)
    ]


def _sphere(center, radius, color):
    cx, cy, cz = center
    return [
        {"x": x, "y": y, "z": z, "r": color[0], "g": color[1], "b": color[2]}
        for x in range(cx - radius, cx + radius + 1)
        for y in range(cy - radius, cy + radius + 1)
        for z in range(cz - radius, cz + radius + 1)
        if (x - cx) ** 2 + (y - cy) ** 2 + (z - cz) ** 2 <= radius * radius
    ]


YELLOW = (245, 205, 47)


def _same_color_figure(color=YELLOW):
    """Body, thin neck, head and a thin arm, all one colour, so only geometry can
    tell the parts apart."""
    body = _block((0, 10), (0, 10), (0, 12), color)
    neck = _block((3, 7), (3, 7), (12, 14), color)
    head = _block((1, 9), (1, 9), (14, 22), color)
    arm = _block((10, 18), (3, 6), (6, 9), color)
    return body + neck + head + arm


def _segments_of(voxels, segment_ids, predicate):
    coords, _ = _voxel_arrays(voxels)
    mask = np.array([predicate(x, y, z) for x, y, z in coords.tolist()])
    return set(segment_ids[mask].tolist())


def _segments_with_color(voxels, segment_ids, color):
    _, colors = _voxel_arrays(voxels)
    return set(segment_ids[np.all(colors == color, axis=1)].tolist())


BLACK = (20, 20, 20)
MOUTH = (120, 20, 30)
BLUE = (30, 90, 200)
WHITE = (240, 240, 240)
RED = (200, 30, 30)


def _detailed_shell_figure():
    """Hollow figure in the style of generated models: a yellow head sphere on a
    red body, both with smooth baked shading, plus two black 2x2 eyes, a 4-voxel
    mouth, three 2-voxel blue buttons and a 3x3 white logo. Details are 4-9 voxels
    in a ~1000-voxel model, i.e. well below the 0.5% speckle threshold."""
    voxels = {}

    def shade(color, x, z):
        factor = 0.7 + 0.3 * ((x + 1) / 14.0 * 0.5 + (z + 3) / 30.0 * 0.5)
        return tuple(int(round(channel * factor)) for channel in color)

    for x in range(12):
        for y in range(8):
            for z in range(14):
                if x in (0, 11) or y in (0, 7) or z in (0, 13):
                    voxels[(x, y, z)] = shade(RED, x, z)
    cx, cy, cz, radius = 5.5, 3.5, 20, 6
    for x in range(-1, 13):
        for y in range(-3, 11):
            for z in range(14, 27):
                distance = ((x - cx) ** 2 + (y - cy) ** 2 + (z - cz) ** 2) ** 0.5
                if radius - 1.2 <= distance <= radius:
                    voxels[(x, y, z)] = shade(YELLOW, x, z)

    def paint_front(x, z, color):
        for y in range(-3, 11):
            if (x, y, z) in voxels:
                voxels[(x, y, z)] = color
                return

    for x, z in [(3, 21), (4, 21), (3, 22), (4, 22), (7, 21), (8, 21), (7, 22), (8, 22)]:
        paint_front(x, z, BLACK)
    for x in range(4, 8):
        paint_front(x, 18, MOUTH)
    for z in (4, 7, 10):
        voxels[(5, 0, z)] = BLUE
        voxels[(6, 0, z)] = BLUE
    for x in range(7, 10):
        for z in range(8, 11):
            voxels[(x, 0, z)] = WHITE
    return [{"x": x, "y": y, "z": z, "r": c[0], "g": c[1], "b": c[2]} for (x, y, z), c in voxels.items()]


def _two_part_model():
    """A 'body' block with a differently coloured 'head' block stacked on top,
    plus a few noisy voxels inside the body that should be absorbed."""
    body = _block((0, 6), (0, 6), (0, 6), (120, 60, 20))
    head = _block((1, 5), (1, 5), (6, 10), (140, 200, 90))
    for index, voxel in enumerate(body):
        if index % 40 == 0:
            voxel["r"], voxel["g"], voxel["b"] = 90, 90, 90
    return body + head


def test_segment_voxels_splits_by_color_region_and_absorbs_noise():
    voxels = _two_part_model()
    segment_ids = _segment_voxels(voxels, max_segments=16)

    assert segment_ids.min() == 1
    assert segment_ids.max() == 2
    coords, _ = _voxel_arrays(voxels)
    body_segment = segment_ids[coords[:, 2] < 6]
    head_segment = segment_ids[coords[:, 2] >= 6]
    assert len(set(body_segment.tolist())) == 1
    assert len(set(head_segment.tolist())) == 1
    assert body_segment[0] != head_segment[0]
    # Segment 1 is always the largest.
    assert body_segment[0] == 1


def test_segment_voxels_respects_max_segments():
    voxels = []
    for index in range(8):
        voxels += _block((index * 3, index * 3 + 3), (0, 3), (0, 3), (index * 30, 255 - index * 30, 40))
    segment_ids = _segment_voxels(voxels, max_segments=3)
    assert segment_ids.max() == 3
    assert set(np.unique(segment_ids).tolist()) == {1, 2, 3}


def test_segment_voxels_single_color_model_is_one_segment():
    voxels = _block((0, 4), (0, 4), (0, 4), (10, 20, 30))
    segment_ids = _segment_voxels(voxels, max_segments=16)
    assert segment_ids.max() == 1


def test_rgb_to_lab_matches_reference_values():
    lab = _rgb_to_lab(np.array([(255, 255, 255), (0, 0, 0), (255, 0, 0)], dtype=np.float64))
    assert np.allclose(lab[0], (100.0, 0.0, 0.0), atol=1e-3)
    assert np.allclose(lab[1], (0.0, 0.0, 0.0), atol=1e-6)
    assert np.allclose(lab[2], (53.24, 80.09, 67.20), atol=0.05)


def test_geometric_regions_split_at_necks_and_thickness_changes():
    voxels = _same_color_figure()
    coords, _ = _voxel_arrays(voxels)
    regions = _geometric_regions(coords)

    assert len(np.unique(regions)) == 3
    head = set(regions[coords[:, 2] >= 14].tolist())
    body_core = set(regions[(coords[:, 2] < 12) & (coords[:, 0] < 8)].tolist())
    arm_tip = set(regions[coords[:, 0] >= 14].tolist())
    assert len(head) == 1 and len(body_core) == 1 and len(arm_tip) == 1
    assert head != body_core and arm_tip != body_core


def test_geometric_regions_do_not_split_on_bumps_or_steps():
    bumpy_sphere = _sphere((0, 0, 0), 8, YELLOW) + _block((-1, 2), (-1, 2), (8, 10), YELLOW)
    slab_with_step = _block((0, 20), (0, 20), (0, 6), YELLOW) + _block((0, 20), (0, 10), (6, 8), YELLOW)
    l_shape = _block((0, 20), (0, 6), (0, 6), YELLOW) + _block((0, 6), (6, 20), (0, 6), YELLOW)

    for voxels in (bumpy_sphere, slab_with_step, l_shape):
        coords, _ = _voxel_arrays(voxels)
        assert len(np.unique(_geometric_regions(coords))) == 1


def test_geometric_regions_split_touching_spheres():
    coords, _ = _voxel_arrays(_sphere((0, 0, 0), 6, YELLOW) + _sphere((0, 0, 9), 4, YELLOW))
    regions = _geometric_regions(coords)
    assert len(np.unique(regions)) == 2
    assert set(regions[coords[:, 2] <= 4].tolist()) != set(regions[coords[:, 2] >= 7].tolist())


def test_segment_voxels_splits_same_colored_parts_by_geometry():
    voxels = _same_color_figure()
    segment_ids = _segment_voxels(voxels, max_segments=16)

    head = _segments_of(voxels, segment_ids, lambda x, y, z: z >= 14)
    body = _segments_of(voxels, segment_ids, lambda x, y, z: z < 12 and x < 8)
    assert len(head) == 1 and len(body) == 1
    assert head != body


def test_segment_voxels_merges_shading_before_distinct_dark_colors():
    """Under budget pressure, the lit/shaded halves of a grey bar must merge with
    each other rather than black merging with dark brown, which is what a plain
    RGB distance would pick."""
    grey, shaded_grey, black, brown = (150, 150, 150), (112, 112, 112), (30, 30, 30), (70, 45, 25)
    voxels = (
        _block((0, 6), (0, 4), (0, 4), grey)
        + _block((6, 12), (0, 4), (0, 4), shaded_grey)
        + _block((12, 18), (0, 4), (0, 4), black)
        + _block((18, 24), (0, 4), (0, 4), brown)
    )
    segment_ids = _segment_voxels(voxels, max_segments=3)

    grey_segment = _segments_of(voxels, segment_ids, lambda x, y, z: x < 6)
    shaded_segment = _segments_of(voxels, segment_ids, lambda x, y, z: 6 <= x < 12)
    black_segment = _segments_of(voxels, segment_ids, lambda x, y, z: 12 <= x < 18)
    brown_segment = _segments_of(voxels, segment_ids, lambda x, y, z: x >= 18)
    assert grey_segment == shaded_segment
    assert black_segment != brown_segment
    assert black_segment != grey_segment


def test_segment_voxels_prefers_merging_shading_over_crossing_a_neck():
    """Same-coloured head and body separated by a neck, with a shaded patch on
    the body. With room for only two segments, the shaded patch should rejoin
    the body and the head should stay its own segment."""
    shaded = (184, 154, 35)
    body = _block((0, 10), (0, 10), (0, 10), YELLOW)
    for voxel in body:
        if voxel["x"] >= 7:
            voxel["r"], voxel["g"], voxel["b"] = shaded
    neck = _block((4, 6), (4, 6), (10, 11), YELLOW)
    head = _block((2, 8), (2, 8), (11, 17), YELLOW)
    voxels = body + neck + head

    unbudgeted = _segment_voxels(voxels, max_segments=16)
    assert unbudgeted.max() == 3

    segment_ids = _segment_voxels(voxels, max_segments=2)
    assert segment_ids.max() == 2
    assert len(_segments_of(voxels, segment_ids, lambda x, y, z: z < 10)) == 1
    assert _segments_of(voxels, segment_ids, lambda x, y, z: z >= 11) != _segments_of(
        voxels, segment_ids, lambda x, y, z: z < 10
    )


def test_quantize_colors_gives_small_distinct_colors_their_own_cluster():
    """A handful of black voxels among a thousand shaded-yellow ones carry almost
    no weight, but must still end up in a cluster of their own."""
    shades = np.array([(245 - i % 40, 205 - i % 40, 47) for i in range(1000)], dtype=np.float64)
    black = np.array([BLACK] * 8, dtype=np.float64)
    labels = _quantize_colors(_perceptual_colors(np.vstack([shades, black])), clusters=10)

    black_labels = set(labels[1000:].tolist())
    assert len(black_labels) == 1
    assert not black_labels & set(labels[:1000].tolist())


def test_segment_voxels_keeps_small_high_contrast_details():
    voxels = _detailed_shell_figure()
    segment_ids = _segment_voxels(voxels, max_segments=16)

    eyes = _segments_with_color(voxels, segment_ids, BLACK)
    mouth = _segments_with_color(voxels, segment_ids, MOUTH)
    buttons = _segments_with_color(voxels, segment_ids, BLUE)
    logo = _segments_with_color(voxels, segment_ids, WHITE)
    # Each detail is exactly one segment, disconnected pieces grouped by colour.
    assert len(eyes) == len(mouth) == len(buttons) == len(logo) == 1
    assert len(eyes | mouth | buttons | logo) == 4
    # ...and that segment contains nothing but the detail.
    for detail, color in ((eyes, BLACK), (mouth, MOUTH), (buttons, BLUE), (logo, WHITE)):
        _, colors = _voxel_arrays(voxels)
        members = colors[segment_ids == next(iter(detail))]
        assert np.all(members == color)


def test_segment_voxels_sacrifices_shading_before_details_under_budget():
    voxels = _detailed_shell_figure()
    segment_ids = _segment_voxels(voxels, max_segments=6)

    assert segment_ids.max() == 6
    details = [
        _segments_with_color(voxels, segment_ids, color) for color in (BLACK, MOUTH, BLUE, WHITE)
    ]
    assert all(len(detail) == 1 for detail in details)
    assert len(set().union(*details)) == 4
    head = _segments_of(voxels, segment_ids, lambda x, y, z: z >= 14)
    body = _segments_of(voxels, segment_ids, lambda x, y, z: z < 14)
    assert len(head - set().union(*details)) == 1
    assert len(body - set().union(*details)) == 1


def test_segment_voxels_absorbs_isolated_noise_voxels():
    """Lone off-colour voxels are texture noise, not details, even when several
    of them share a colour."""
    voxels = _block((0, 8), (0, 8), (0, 8), YELLOW)
    for index in (0, 77, 155, 233, 311):
        voxels[index]["r"], voxels[index]["g"], voxels[index]["b"] = BLACK
    segment_ids = _segment_voxels(voxels, max_segments=16)
    assert segment_ids.max() == 1


def test_build_scene_summary_flags_details_and_island_counts():
    voxels = _detailed_shell_figure()
    segment_ids = _segment_voxels(voxels, max_segments=16)
    summary = _build_scene_summary(voxels, segment_ids)
    by_id = {segment["id"]: segment for segment in summary["segments"]}

    eyes = by_id[next(iter(_segments_with_color(voxels, segment_ids, BLACK)))]
    buttons = by_id[next(iter(_segments_with_color(voxels, segment_ids, BLUE)))]
    logo = by_id[next(iter(_segments_with_color(voxels, segment_ids, WHITE)))]
    assert eyes["is_detail"] and eyes["island_count"] == 2
    assert buttons["is_detail"] and buttons["island_count"] == 3
    assert logo["is_detail"] and logo["island_count"] == 1
    assert "details" in summary
    big = max(summary["segments"], key=lambda s: s["voxel_count"])
    assert not big["is_detail"]


def test_render_view_tile_keeps_small_segments_visible_under_their_labels():
    voxels = _detailed_shell_figure()
    segment_ids = _segment_voxels(voxels, max_segments=16)
    coords, _ = _voxel_arrays(voxels)
    front = next(view for view in VIEWS if view["name"] == "front")
    tile = _render_view_tile(coords, segment_ids, front, 320, _load_font(15))
    pixels = np.array(tile)
    projection = _project_segments(coords, segment_ids, front)
    scale = min(320 // projection.shape[1], 320 // projection.shape[0])

    for detail_color in (BLACK, MOUTH, BLUE, WHITE):
        segment_id = next(iter(_segments_with_color(voxels, segment_ids, detail_color)))
        palette_color = np.array(SEGMENT_PALETTE[segment_id - 1])
        visible = int(np.all(pixels == palette_color, axis=2).sum())
        projected = int((projection == segment_id).sum())
        # The label must sit beside the detail, leaving most of it uncovered.
        assert visible >= projected * scale * scale * 0.75


def test_build_scene_summary_describes_segments_without_colors():
    voxels = _two_part_model()
    segment_ids = _segment_voxels(voxels, max_segments=16)
    summary = _build_scene_summary(voxels, segment_ids)

    assert summary["segment_count"] == 2
    assert summary["voxel_count"] == len(voxels)
    head = next(s for s in summary["segments"] if s["id"] == 2)
    assert head["center"]["z"] > 0.6
    assert head["extent"]["z"][0] > 0.5
    for segment in summary["segments"]:
        assert "rgb" not in segment
        assert "color" not in segment


def test_project_segments_front_view_shows_head_above_body():
    voxels = _two_part_model()
    segment_ids = _segment_voxels(voxels, max_segments=16)
    coords, _ = _voxel_arrays(voxels)
    front = {"h": "x", "flip_h": False, "v": "z", "d": "y", "d_sign": -1}
    projection = _project_segments(coords, segment_ids, front)

    assert projection.shape == (10, 6)
    assert set(np.unique(projection[:4]).tolist()) <= {0, 2}
    assert set(np.unique(projection[4:]).tolist()) == {1}


def test_build_voxel_preview_data_url_returns_labelled_png():
    voxels = _two_part_model()
    segment_ids = _segment_voxels(voxels, max_segments=16)

    data_url = _build_voxel_preview_data_url(voxels, segment_ids)

    assert data_url.startswith("data:image/png;base64,")
    image = Image.open(BytesIO(base64.b64decode(data_url.split(",", 1)[1])))
    assert image.format == "PNG"
    colors = {color for _, color in image.getcolors(maxcolors=image.width * image.height)}
    # Segment ID colours are present; the model's real colours are not.
    assert SEGMENT_PALETTE[0] in colors
    assert SEGMENT_PALETTE[1] in colors
    assert (120, 60, 20) not in colors
    assert (140, 200, 90) not in colors


def test_assignment_schema_requires_every_segment():
    schema = _assignment_schema([1, 2, 3])
    assignments = schema["properties"]["assignments"]
    assert assignments["minItems"] == 3
    assert assignments["maxItems"] == 3
    assert assignments["items"]["properties"]["segment_id"]["enum"] == [1, 2, 3]


def test_extract_thinking_delta_only_returns_reasoning_summaries():
    assert _extract_thinking_delta(
        {
            "type": "response.reasoning_summary_text.delta",
            "delta": "I notice the torso should use red bricks.",
        }
    ) == "I notice the torso should use red bricks."
    assert _extract_thinking_delta({"type": "response.output_text.delta", "delta": "private output"}) is None
    assert _extract_thinking_delta({"type": "response.reasoning_summary_text.delta", "delta": 3}) is None


def test_llm_render_stream_relays_thinking_and_result(monkeypatch):
    async def fake_llm_render(_request, _auth_info, on_thinking):
        await on_thinking("I see separate arms and a torso.")
        return LlmRenderResponse(
            xyzrgb_content="0 0 0 255 0 0\n",
            voxel_count=1,
            segment_count=1,
            model="test-model",
            applied_rules=[],
        )

    module = importlib.import_module("src.requests.llmRender")
    monkeypatch.setattr(module, "llm_render", fake_llm_render)

    async def collect_events():
        return [event async for event in llm_render_stream(object(), {})]

    events = [
        json.loads(event.removeprefix("data: "))
        for event in asyncio.run(collect_events())
    ]
    assert events[0] == {"type": "thinking", "delta": "I see separate arms and a torso."}
    assert events[1]["type"] == "result"
    assert events[1]["data"]["xyzrgb_content"] == "0 0 0 255 0 0\n"


def test_apply_assignments_recolors_segments_and_ignores_invalid_entries():
    voxels = _two_part_model()
    segment_ids = _segment_voxels(voxels, max_segments=16)
    assignments = [
        {"segment_id": 1, "part": "robe", "reason": "large lower block", "color": [200, 150, 100]},
        {"segment_id": 2, "part": "head", "reason": "top block", "color": [300, -5, 50]},
        {"segment_id": 2, "part": "dup", "reason": "duplicate", "color": [0, 0, 0]},
        {"segment_id": 99, "part": "ghost", "reason": "missing", "color": [1, 2, 3]},
        "not a dict",
    ]

    recolored, applied = _apply_assignments(voxels, segment_ids, assignments)

    assert [rule["segment_id"] for rule in applied] == [1, 2, 99]
    assert applied[0]["changed_voxels"] == int((segment_ids == 1).sum())
    assert applied[1]["color"] == [255, 0, 50]
    assert applied[2]["changed_voxels"] == 0
    body = [v for v in recolored if v["z"] < 6]
    head = [v for v in recolored if v["z"] >= 6]
    assert all((v["r"], v["g"], v["b"]) == (200, 150, 100) for v in body)
    assert all((v["r"], v["g"], v["b"]) == (255, 0, 50) for v in head)
    # Geometry untouched.
    assert [(v["x"], v["y"], v["z"]) for v in recolored] == [(v["x"], v["y"], v["z"]) for v in voxels]
