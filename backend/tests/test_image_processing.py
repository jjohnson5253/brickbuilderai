from io import BytesIO

from PIL import Image

from src.utils import image_processing


def _png_bytes(mode, color):
    buffer = BytesIO()
    Image.new(mode, (2, 2), color).save(buffer, format="PNG")
    return buffer.getvalue()


def test_remove_background_uses_fal_without_local_model(monkeypatch, tmp_path):
    input_bytes = _png_bytes("RGB", "white")
    output_bytes = _png_bytes("RGBA", (255, 0, 0, 255))

    class Response:
        def __init__(self, content):
            self.content = content

        def raise_for_status(self):
            pass

    monkeypatch.setattr(
        image_processing.requests,
        "get",
        lambda url, timeout: Response(
            output_bytes if url == "https://fal.test/output.png" else input_bytes
        ),
    )

    import fal_client

    monkeypatch.setattr(
        fal_client,
        "subscribe",
        lambda model, arguments: {"image": {"url": "https://fal.test/output.png"}},
    )
    monkeypatch.setattr(
        fal_client,
        "upload",
        lambda data, content_type: "https://fal.test/processed.png",
    )

    result = image_processing.remove_background_from_url(
        "https://example.test/input.png",
        str(tmp_path),
    )

    assert result == "https://fal.test/processed.png"
    assert not (tmp_path / "processed_image.png").exists()
