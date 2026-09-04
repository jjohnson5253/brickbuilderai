import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from src import api


AUTH = {"user_id": "user"}


def test_staging_vercel_deployment_is_allowed_by_cors():
    assert "https://brickbuilderai-git-staging-jjohnson3700team.vercel.app" in api.ALLOWED_ORIGINS


@pytest.mark.parametrize(
    ("endpoint_name", "handler_name", "call_args", "forwarded_args"),
    [
        ("glbToBricks_endpoint", "glb_to_bricks", ("file", "trimesh", 40, AUTH), ("file", "trimesh", 40, AUTH)),
        ("ldr_to_mpd_endpoint", "ldr_to_mpd", ("request", AUTH), ("request", AUTH)),
        ("part_to_mpd_endpoint", "part_to_mpd", ("request", AUTH), ("request", AUTH)),
        ("ldr_to_brickowl_endpoint", "ldr_to_brickowl", ("request", AUTH), ("request", AUTH)),
        ("estimate_price_endpoint", "estimate_price", ("request", AUTH), ("request", AUTH)),
        ("get_price_endpoint", "get_price", ("request", AUTH), ("request", AUTH)),
        ("resize_model_endpoint", "resize_model", ("request", AUTH), ("request", AUTH)),
        ("prompt_edit_model_endpoint", "prompt_edit_model", ("request", AUTH, None), ("request", AUTH)),
        ("llm_render_endpoint", "llm_render", ("request", AUTH), ("request", AUTH)),
        ("create_checkout_session_endpoint", "create_checkout_session", ("request", AUTH), ("request", AUTH)),
        ("get_user_generations_endpoint", "get_user_generations", ("body", "http-request", AUTH), ("body", AUTH, "http-request")),
        ("get_generations_by_image_endpoint", "get_generations_by_image", ("body", AUTH), ("body", AUTH)),
        ("get_community_generations_endpoint", "get_community_generations", ("body", AUTH), ("body", AUTH)),
        ("update_model_endpoint", "update_model", ("request", AUTH), ("request", AUTH)),
        ("update_ldr_and_parts_list_endpoint", "update_ldr_and_parts_list", ("request", AUTH), ("request", AUTH)),
        ("toggle_is_community_endpoint", "toggle_is_community", ("request", AUTH), ("request", AUTH)),
        ("claim_generation_endpoint", "claim_generation", ("request", AUTH), ("request", AUTH)),
        ("update_generation_name_endpoint", "update_generation_name", ("request", AUTH), ("request", AUTH)),
        ("update_image_preview_endpoint", "update_image_preview", ("request", AUTH), ("request", AUTH)),
        ("update_username_endpoint", "update_username", ("request", AUTH), ("request", AUTH)),
    ],
)
def test_api_endpoints_delegate_to_request_handlers(monkeypatch, endpoint_name, handler_name, call_args, forwarded_args):
    handler = AsyncMock(return_value={"ok": True})
    monkeypatch.setattr(api, handler_name, handler)
    result = asyncio.run(getattr(api, endpoint_name)(*call_args))
    assert result == {"ok": True}
    handler.assert_awaited_once_with(*forwarded_args)


def test_generation_endpoints_delegate(monkeypatch):
    handler = AsyncMock(return_value={"status": "completed"})
    monkeypatch.setattr(api, "get_generation", handler)
    request = object()
    assert asyncio.run(api.get_generation_endpoint(request)) == {"status": "completed"}
    handler.assert_awaited_once_with(request)

    handler.reset_mock()
    asyncio.run(api.get_generation_by_id_endpoint("generation-1"))
    assert handler.await_args.args[0].generation_id == "generation-1"


def test_image_and_text_endpoints_choose_streaming_handler(monkeypatch):
    for endpoint, normal_name, stream_name in [
        (api.imageToBricks_endpoint, "image_to_bricks", "image_to_bricks_stream"),
        (api.textToBricks_endpoint, "text_to_bricks", "text_to_bricks_stream"),
    ]:
        normal = AsyncMock(return_value="normal")
        stream = AsyncMock(return_value="stream")
        monkeypatch.setattr(api, normal_name, normal)
        monkeypatch.setattr(api, stream_name, stream)
        request = type("Request", (), {"stream": False})()
        assert asyncio.run(endpoint(request, AUTH, None)) == "normal"
        request.stream = True
        assert asyncio.run(endpoint(request, AUTH, None)) == "stream"


def test_unprotected_one_argument_endpoints(monkeypatch):
    email_handler = AsyncMock(return_value="sent")
    webhook_handler = AsyncMock(return_value="accepted")
    monkeypatch.setattr(api, "send_waitlist_email", email_handler)
    monkeypatch.setattr(api, "stripe_webhook", webhook_handler)
    assert asyncio.run(api.send_waitlist_email_endpoint("request")) == "sent"
    assert asyncio.run(api.stripe_webhook_endpoint("request")) == "accepted"
    webhook_handler.assert_awaited_once_with("request", {})


def test_health_and_fal_key_dependency(monkeypatch):
    monkeypatch.setattr(api, "track_api_call", lambda **_kwargs: None)
    assert asyncio.run(api.health_check()) == {"message": "brickai API is running"}
    monkeypatch.setattr(api, "FAL_KEY", None)
    with pytest.raises(HTTPException) as exc_info:
        api.require_fal_key()
    assert exc_info.value.status_code == 503
    monkeypatch.setattr(api, "FAL_KEY", "configured")
    assert api.require_fal_key() is None
