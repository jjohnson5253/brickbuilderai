import asyncio
import base64

import pytest
from pydantic import ValidationError

from src.requests import claudeToBricks as module
from src.requests.claudeToBricks import (
    ClaudeToBricksRequest,
    _anthropic_payload,
    _extract_ldr_content,
    process_claude_to_bricks_task,
    validate_ldr_content,
)


VALID_PART = "1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat"


def test_request_accepts_text_or_supported_image_and_rejects_invalid_input():
    assert ClaudeToBricksRequest(prompt="  red castle  ").prompt == "red castle"

    encoded = base64.b64encode(b"image bytes").decode()
    image_request = ClaudeToBricksRequest(
        image_base64=encoded,
        image_media_type="image/jpeg",
    )
    assert image_request.image_base64 == encoded

    for kwargs in (
        {},
        {"prompt": " "},
        {"image_base64": "not base64"},
        {"image_base64": encoded, "image_media_type": "image/svg+xml"},
        {"prompt": "model", "detail_level": 0},
    ):
        with pytest.raises(ValidationError):
            ClaudeToBricksRequest(**kwargs)


def test_anthropic_payload_uses_opus_5_5_auto_tool_output_and_optional_image():
    encoded = base64.b64encode(b"png").decode()
    request = ClaudeToBricksRequest(
        prompt="a lighthouse",
        image_base64=encoded,
        image_media_type="image/png",
    )
    payload = _anthropic_payload(request)

    assert payload["model"] == "claude-opus-5-5"
    assert payload["tool_choice"] == {"type": "auto"}
    content = payload["messages"][0]["content"]
    assert content[0]["source"]["data"] == encoded
    assert content[1]["text"] == "a lighthouse"


def test_extract_and_validate_ldr_content():
    response = {
        "content": [
            {
                "type": "tool_use",
                "name": "submit_ldr_model",
                "input": {"ldr_content": f"0 FILE model.ldr\n0 My model\n{VALID_PART}"},
            }
        ]
    }
    validated = validate_ldr_content(_extract_ldr_content(response))
    assert "0 Name: claude-model.ldr" in validated
    assert "0 Author: BrickBuilder AI with Claude" in validated
    assert validated.endswith(VALID_PART + "\n")

    with pytest.raises(ValueError, match="Unsafe"):
        validate_ldr_content(VALID_PART.replace("3001.dat", "../3001.dat"))
    with pytest.raises(ValueError, match="Invalid LDraw command"):
        validate_ldr_content("2 4 0 0 0 1 1 1")
    with pytest.raises(ValueError, match="embedded FILE"):
        validate_ldr_content(f"{VALID_PART}\n0 FILE another.ldr\n{VALID_PART}")
    with pytest.raises(ValueError, match="truncated"):
        _extract_ldr_content({"stop_reason": "max_tokens", "content": []})


def test_extract_ldr_content_accepts_text_fallback_for_auto_tool_choice():
    response = {"content": [{"type": "text", "text": VALID_PART}]}
    assert validate_ldr_content(_extract_ldr_content(response)).endswith(VALID_PART + "\n")

    json_response = {
        "content": [
            {"type": "text", "text": '{"ldr_content": "' + VALID_PART + '"}'}
        ]
    }
    assert _extract_ldr_content(json_response) == VALID_PART


def test_background_task_stores_standard_generation_artifacts(monkeypatch, tmp_path):
    calls = []

    class FakeStorage:
        async def update_status(self, generation_id, status, error_message=None):
            calls.append(("status", generation_id, status, error_message))

        async def store_images(self, **kwargs):
            calls.append(("images", kwargs))

        async def store_model_file(self, generation_id, content, file_type, **kwargs):
            calls.append(("model", generation_id, file_type, content, kwargs))
            return f"https://example.com/{file_type}"

        async def store_parts_list_csv(self, generation_id, content, **kwargs):
            calls.append(("parts", generation_id, content, kwargs))
            return "https://example.com/parts.csv"

    class FakePacker:
        def pack_ldraw_model(self, ldr_path):
            mpd_path = tmp_path / "model.mpd"
            mpd_path.write_text("0 FILE model.ldr\n", encoding="utf-8")
            return str(mpd_path)

    async def fake_generate(_request):
        return validate_ldr_content(VALID_PART)

    async def fake_deduct(**_kwargs):
        return {}

    monkeypatch.setattr(module, "generation_storage", FakeStorage())
    monkeypatch.setattr(module, "LDrawPacker", FakePacker)
    monkeypatch.setattr(module, "_generate_ldr_with_claude", fake_generate)
    monkeypatch.setattr(module, "deduct_credits", fake_deduct)
    monkeypatch.setattr(module, "track_image_conversion", lambda **_kwargs: None)
    monkeypatch.setattr(module, "track_error", lambda **_kwargs: None)

    encoded = base64.b64encode(b"png").decode()
    request = ClaudeToBricksRequest(prompt="castle", image_base64=encoded)
    asyncio.run(
        process_claude_to_bricks_task(
            "generation-1",
            request,
            {
                "user_email": "builder@example.com",
                "is_developer": False,
                "is_anonymous": False,
            },
            {"user_id": "user-1"},
        )
    )

    assert ("status", "generation-1", "completed", None) in calls
    assert any(call[:3] == ("model", "generation-1", "ldr") for call in calls)
    assert not any(call[:3] == ("model", "generation-1", "mpd") for call in calls)
    assert any(call[0] == "parts" for call in calls)
    assert any(call[0] == "images" for call in calls)
