import threading
from io import BytesIO

import pytest
from PIL import Image

from src.utils import generate_image


def test_generate_reference_view_images_makes_four_parallel_view_requests(monkeypatch):
    calls = []
    barrier = threading.Barrier(4)

    def subscribe(endpoint, arguments, with_logs, on_queue_update):
        calls.append((endpoint, arguments, with_logs, on_queue_update))
        barrier.wait(timeout=1)
        view_name = next(
            name
            for name, instruction in generate_image.REFERENCE_VIEWS
            if instruction in arguments["prompt"]
        )
        return {"images": [{"url": f"https://example.com/{view_name}.png"}]}

    monkeypatch.setattr(generate_image.fal_client, "subscribe", subscribe)

    result = generate_image.generate_reference_view_images(
        "https://example.com/source.png",
        base_prompt="Render as a voxel toy. Isometric view.",
    )

    assert result == [
        "https://example.com/front.png",
        "https://example.com/top.png",
        "https://example.com/side.png",
        "https://example.com/isometric.png",
    ]
    assert len(calls) == 4
    assert {call[0] for call in calls} == {"google/nano-banana-lite/edit"}
    assert all(call[1]["image_urls"] == ["https://example.com/source.png"] for call in calls)
    assert all(call[1]["num_images"] == 1 for call in calls)
    assert all(call[1]["output_format"] == "png" for call in calls)
    assert all(call[2] is True for call in calls)
    assert all("Render as a voxel toy." in call[1]["prompt"] for call in calls)
    prompts_by_view = {
        name: next(call[1]["prompt"] for call in calls if instruction in call[1]["prompt"])
        for name, instruction in generate_image.REFERENCE_VIEWS
    }
    assert "isometric view" not in prompts_by_view["front"].lower()
    assert "isometric view" not in prompts_by_view["top"].lower()
    assert "isometric view" not in prompts_by_view["side"].lower()


def test_generate_reference_view_images_requires_each_view_output(monkeypatch):
    monkeypatch.setattr(
        generate_image.fal_client,
        "subscribe",
        lambda *args, **kwargs: {"images": []},
    )

    with pytest.raises(RuntimeError, match="returned no"):
        generate_image.generate_reference_view_images("https://example.com/source.png")


def test_generate_image_from_image_returns_isometric_for_3d(monkeypatch):
    image_buffer = BytesIO()
    Image.new("RGB", (4, 4), "red").save(image_buffer, format="PNG")

    class Response:
        content = image_buffer.getvalue()

        @staticmethod
        def raise_for_status():
            return None

    reference_urls = [
        "https://example.com/front.png",
        "https://example.com/top.png",
        "https://example.com/side.png",
        "https://example.com/isometric.png",
    ]
    captured = {}

    monkeypatch.setattr(generate_image.requests, "get", lambda *args, **kwargs: Response())
    monkeypatch.setattr(
        generate_image.fal_client,
        "upload",
        lambda *args, **kwargs: "https://example.com/resized.png",
    )

    def generate_views(image_url, base_prompt=None, status_callback=None):
        captured.update(image_url=image_url, base_prompt=base_prompt)
        return reference_urls

    monkeypatch.setattr(generate_image, "generate_reference_view_images", generate_views)

    resized_url, image_3d_url, prompt, result_urls = generate_image.generate_image_from_image(
        "https://example.com/source.png",
        edit_prompt="Make it blue.",
    )

    assert resized_url == "https://example.com/resized.png"
    assert image_3d_url == reference_urls[-1]
    assert result_urls == reference_urls
    assert captured["image_url"] == resized_url
    assert prompt == captured["base_prompt"]
