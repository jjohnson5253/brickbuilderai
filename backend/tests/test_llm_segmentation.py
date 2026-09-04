import io
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils import llm_segmentation
from src.utils.llm_segmentation import (
    apply_llm_segmentation,
    build_check_sheet,
    get_llm_segmentation_mode,
    parse_llm_verdict,
    parse_llm_xyzrgb,
    render_voxel_projections,
)


def make_xyzrgb_lines(count: int) -> str:
    return "\n".join(f"{i % 8} {i // 8 % 8} {i // 64 % 8} 10 20 30" for i in range(count))


class TestGetLlmSegmentationMode:
    def test_defaults_to_off(self, monkeypatch):
        monkeypatch.delenv("LLM_SEGMENTATION_MODE", raising=False)
        assert get_llm_segmentation_mode() == "off"

    def test_reads_valid_modes(self, monkeypatch):
        for mode in ("off", "check", "llm"):
            monkeypatch.setenv("LLM_SEGMENTATION_MODE", mode.upper())
            assert get_llm_segmentation_mode() == mode

    def test_unknown_mode_falls_back_to_off(self, monkeypatch):
        monkeypatch.setenv("LLM_SEGMENTATION_MODE", "bogus")
        assert get_llm_segmentation_mode() == "off"


class TestParseLlmXyzrgb:
    def test_parses_noisy_output(self):
        body = make_xyzrgb_lines(30)
        text = f"Here is the voxel model:\n```\n{body}\n```\nDone!"
        result = parse_llm_xyzrgb(text, grid_resolution=8)
        assert result == body

    def test_filters_out_of_bounds_coords_and_colors(self):
        valid = make_xyzrgb_lines(25)
        text = valid + "\n99 0 0 10 20 30\n-1 0 0 10 20 30\n0 0 0 300 0 0"
        result = parse_llm_xyzrgb(text, grid_resolution=8)
        assert result == valid

    def test_deduplicates_positions(self):
        body = make_xyzrgb_lines(25)
        result = parse_llm_xyzrgb(body + "\n0 0 0 99 99 99", grid_resolution=8)
        assert result.splitlines().count("0 0 0 10 20 30") == 1
        assert "0 0 0 99 99 99" not in result

    def test_raises_when_too_few_voxels(self):
        with pytest.raises(ValueError):
            parse_llm_xyzrgb(make_xyzrgb_lines(5), grid_resolution=8)


class TestParseLlmVerdict:
    def test_parses_json_verdict(self):
        text = 'Sure! {"passes": true, "score": 0.9, "feedback": "Looks good"}'
        verdict = parse_llm_verdict(text)
        assert verdict == {"passes": True, "score": 0.9, "feedback": "Looks good"}

    def test_parses_failing_json_verdict(self):
        text = '{"passes": false, "score": 0.2, "feedback": "Silhouette mismatch"}'
        verdict = parse_llm_verdict(text)
        assert verdict["passes"] is False
        assert verdict["score"] == 0.2

    def test_keyword_fallback(self):
        assert parse_llm_verdict("The segmentation passes the check.")["passes"] is True
        assert parse_llm_verdict("This is a fail, colors are wrong.")["passes"] is False

    def test_unparseable_returns_none_verdict(self):
        verdict = parse_llm_verdict("no idea")
        assert verdict["passes"] is None
        assert verdict["feedback"] == "no idea"


class TestRenderVoxelProjections:
    def test_renders_three_decodable_views(self):
        xyzrgb = "0 0 0 255 0 0\n1 0 0 0 255 0\n0 1 0 0 0 255\n0 0 1 10 10 10"
        pngs = render_voxel_projections(xyzrgb, scale=4)
        assert len(pngs) == 3
        for png in pngs:
            image = Image.open(io.BytesIO(png))
            assert image.size == (8, 8)  # 2x2 grid upscaled by 4

    def test_front_view_shows_front_voxel_color(self):
        # Two voxels stacked along Y — front view must show the y=0 color
        xyzrgb = "0 0 0 255 0 0\n0 1 0 0 255 0\n" + make_xyzrgb_lines(0)
        front_png = render_voxel_projections(xyzrgb, scale=1)[0]
        image = Image.open(io.BytesIO(front_png)).convert("RGB")
        assert image.getpixel((0, 0)) == (255, 0, 0)


class TestBuildCheckSheet:
    def test_composes_labeled_panels(self):
        panels = [
            ("SOURCE", Image.new("RGB", (64, 64), (255, 0, 0))),
            ("VOXELS (front)", Image.new("RGB", (32, 32), (0, 255, 0))),
            ("REFERENCE 1", Image.new("RGB", (128, 128), (0, 0, 255))),
            ("REFERENCE 2", Image.new("RGB", (128, 64), (255, 255, 0))),
        ]
        sheet = Image.open(io.BytesIO(build_check_sheet(panels)))
        # 4 panels in up to 3 columns -> 3 wide, 2 rows
        assert sheet.size[0] == 3 * 256
        assert sheet.size[1] == 2 * (256 + 24)

    def test_raises_without_panels(self):
        with pytest.raises(ValueError):
            build_check_sheet([])


class TestApplyLlmSegmentation:
    def test_off_mode_returns_content_unchanged(self):
        content = make_xyzrgb_lines(25)
        result, info = apply_llm_segmentation(
            content, source_image_url="http://example.com/img.png",
            grid_resolution=8, mode="off",
        )
        assert result == content
        assert info["mode"] == "off"
        assert info["used_llm_segmentation"] is False

    def test_llm_mode_uses_llm_content(self, monkeypatch):
        llm_content = make_xyzrgb_lines(30)
        monkeypatch.setattr(
            llm_segmentation, "segment_voxels_with_llm",
            lambda url, res: llm_content,
        )
        monkeypatch.setattr(
            llm_segmentation, "check_segmentation_with_llm",
            lambda content, source_image_url=None: {"passes": True, "score": 1.0, "feedback": "ok"},
        )
        result, info = apply_llm_segmentation(
            "0 0 0 1 2 3", source_image_url="http://example.com/img.png",
            grid_resolution=8, mode="llm",
        )
        assert result == llm_content
        assert info["used_llm_segmentation"] is True
        assert info["verdict"]["passes"] is True

    def test_llm_mode_falls_back_on_failure(self, monkeypatch):
        def boom(url, res):
            raise ValueError("LLM produced garbage")

        monkeypatch.setattr(llm_segmentation, "segment_voxels_with_llm", boom)
        content = make_xyzrgb_lines(25)
        result, info = apply_llm_segmentation(
            content, source_image_url="http://example.com/img.png",
            grid_resolution=8, mode="llm",
        )
        assert result == content
        assert info["used_llm_segmentation"] is False
        assert "garbage" in info["error"]

    def test_llm_mode_without_source_image_falls_back(self):
        content = make_xyzrgb_lines(25)
        result, info = apply_llm_segmentation(
            content, source_image_url=None, grid_resolution=8, mode="llm",
        )
        assert result == content
        assert info["error"] is not None

    def test_check_mode_keeps_content_and_reports_verdict(self, monkeypatch):
        verdict = {"passes": False, "score": 0.3, "feedback": "proportions off"}
        monkeypatch.setattr(
            llm_segmentation, "check_segmentation_with_llm",
            lambda content, source_image_url=None: verdict,
        )
        content = make_xyzrgb_lines(25)
        result, info = apply_llm_segmentation(
            content, source_image_url="http://example.com/img.png",
            grid_resolution=8, mode="check",
        )
        assert result == content
        assert info["verdict"] == verdict
        assert info["used_llm_segmentation"] is False

    def test_check_mode_failure_falls_back(self, monkeypatch):
        def boom(content, source_image_url=None):
            raise Exception("network down")

        monkeypatch.setattr(llm_segmentation, "check_segmentation_with_llm", boom)
        content = make_xyzrgb_lines(25)
        result, info = apply_llm_segmentation(
            content, source_image_url="http://example.com/img.png",
            grid_resolution=8, mode="check",
        )
        assert result == content
        assert info["error"] == "network down"
