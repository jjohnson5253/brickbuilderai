import pytest

from src.utils import generate_image


def test_generate_reference_view_images_requests_four_ordered_views(monkeypatch):
    captured = {}
    expected_urls = [
        "https://example.com/front.png",
        "https://example.com/top.png",
        "https://example.com/side.png",
        "https://example.com/isometric.png",
    ]

    def subscribe(endpoint, arguments, with_logs, on_queue_update):
        captured.update(
            endpoint=endpoint,
            arguments=arguments,
            with_logs=with_logs,
            on_queue_update=on_queue_update,
        )
        return {"images": [{"url": url} for url in expected_urls]}

    monkeypatch.setattr(generate_image.fal_client, "subscribe", subscribe)

    result = generate_image.generate_reference_view_images("https://example.com/source.png")

    assert result == expected_urls
    assert captured["endpoint"] == "fal-ai/nano-banana/edit"
    assert captured["arguments"] == {
        "prompt": generate_image.REFERENCE_VIEW_PROMPT,
        "image_urls": ["https://example.com/source.png"],
        "num_images": 4,
    }
    assert captured["with_logs"] is True


def test_generate_reference_view_images_requires_all_four_outputs(monkeypatch):
    monkeypatch.setattr(
        generate_image.fal_client,
        "subscribe",
        lambda *args, **kwargs: {
            "images": [{"url": "https://example.com/front.png"}],
        },
    )

    with pytest.raises(RuntimeError, match="fewer than 4"):
        generate_image.generate_reference_view_images("https://example.com/source.png")
