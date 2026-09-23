import asyncio
import base64
import copy

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


GOOD_DESIGN = {
    "title": "Tower",
    "base_color": 2,
    "grid": {"width": 8, "depth": 8, "layers": 6},
    "shapes": [{"shape": "cylinder", "axis": "y", "center": [3.5, 3.5], "radius": 3, "range": [0, 5], "color": 71}],
}
FLOATING_DESIGN = {
    "grid": {"width": 8, "depth": 8, "layers": 8},
    "shapes": [
        {"shape": "box", "x": [0, 7], "y": [0, 0], "z": [0, 7], "color": 71},
        {"shape": "box", "x": [2, 4], "y": [4, 5], "z": [2, 4], "color": 4},
    ],
}


def _tool_response(name, tool_input, tool_id):
    return {"stop_reason": "tool_use",
            "content": [{"type": "tool_use", "id": tool_id, "name": name, "input": tool_input}]}


def _scripted_claude(monkeypatch, responses):
    sent = []

    async def fake_post(_client, _headers, payload):
        sent.append(copy.deepcopy(payload))  # the loop keeps appending to the same message list
        return responses[len(sent) - 1]

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(module, "_post_messages", fake_post)
    return sent


def test_design_mode_feeds_build_errors_back_then_reviews_then_accepts(monkeypatch):
    sent = _scripted_claude(monkeypatch, [
        _tool_response("submit_brick_design", FLOATING_DESIGN, "t1"),
        _tool_response("submit_brick_design", GOOD_DESIGN, "t2"),
        _tool_response("accept_design", {}, "t3"),
    ])
    monkeypatch.setattr(module, "DESIGN_REVIEW_ROUNDS", 1)
    monkeypatch.setattr(module, "DESIGN_MAX_ATTEMPTS", 3)

    ldr = asyncio.run(module._generate_ldr_with_design(ClaudeToBricksRequest(prompt="a tower")))

    assert len(sent) == 3
    assert sent[0]["tools"][0]["name"] == "submit_brick_design"
    assert "COLORS" in sent[0]["system"] and "71 Light Bluish Gray" in sent[0]["system"]
    error_result = sent[1]["messages"][-1]["content"][0]
    assert error_result["is_error"] and "float" in error_result["content"]
    review_result = sent[2]["messages"][-1]["content"][0]
    assert review_result["content"][1]["type"] == "image"
    assert "Built" in review_result["content"][0]["text"]
    validated = validate_ldr_content(ldr)
    assert module.audit_ldraw(validated).ok
    assert "0 STEP" in validated


def test_design_mode_repairs_on_last_attempt_instead_of_failing(monkeypatch):
    _scripted_claude(monkeypatch, [_tool_response("submit_brick_design", FLOATING_DESIGN, "t1")])
    monkeypatch.setattr(module, "DESIGN_MAX_ATTEMPTS", 1)
    monkeypatch.setattr(module, "DESIGN_REVIEW_ROUNDS", 0)
    ldr = asyncio.run(module._generate_ldr_with_design(ClaudeToBricksRequest(prompt="a slab")))
    assert "3001.dat" in ldr or "3007.dat" in ldr


def test_direct_mode_sends_audit_feedback_and_uses_the_corrected_model(monkeypatch):
    overlapping = f"{VALID_PART}\n{VALID_PART}"
    sent = _scripted_claude(monkeypatch, [
        _tool_response("submit_ldr_model", {"ldr_content": overlapping}, "d1"),
        _tool_response("submit_ldr_model", {"ldr_content": VALID_PART}, "d2"),
    ])
    monkeypatch.setattr(module, "DIRECT_FIX_ROUNDS", 1)
    ldr = asyncio.run(module._generate_ldr_direct(ClaudeToBricksRequest(prompt="brick")))
    assert len(sent) == 2
    feedback = sent[1]["messages"][-1]["content"][0]
    assert feedback["is_error"] and "overlap" in feedback["content"]
    assert ldr.count("3001.dat") == 1
