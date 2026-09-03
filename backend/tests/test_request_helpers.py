import base64

import pytest
from pydantic import ValidationError

from src.requests.estimatePrice import EstimatePriceRequest
from src.requests.getPrice import calculate_price, parse_parts_list_csv
from src.requests.getUserGenerations import _filter_duplicate_glb_generations
from src.requests.ldrToMpd import LdrToMpdRequest, extract_last_step_from_ldr
from src.requests.textToBricks import TextToBricksRequest
from src.requests.updateImagePreview import UpdateImagePreviewRequest
from src.requests.updateUsername import UpdateUsernameRequest


def test_parts_csv_aggregates_quantities_weight_and_invalid_rows():
    csv_text = "LdrawId,Qty,Weight\n3001.dat,2,1.5\n3001.dat,3,1.5\n3003.dat,nope,nope\n,8,2\n"
    parts, weight = parse_parts_list_csv(csv_text)
    assert parts == {"3001.dat": 5}
    assert weight == 7.5


def test_calculate_price_uses_known_and_default_prices_and_sorts():
    total, details = calculate_price({"unknown.dat": 2, "3001.dat": 4})
    assert total == 0.8
    assert [detail.part_id for detail in details] == ["3001.dat", "unknown.dat"]
    assert details[0].total_price == 0.6
    assert details[1].unit_price == 0.1


def test_extract_last_step_handles_explicit_implicit_and_no_steps():
    first = "1 4 0 0 0 1 0 0 0 1 0 0 0 1 a.dat"
    last = "1 4 1 0 0 1 0 0 0 1 0 0 0 1 b.dat"
    assert extract_last_step_from_ldr(f"{first}\n0 STEP\n{last}") == last + "\n"
    assert extract_last_step_from_ldr(f"{first}\n{last}") == first + "\n" + last + "\n"
    assert extract_last_step_from_ldr(f"{first}\n0 STEP") == first + "\n"


def test_duplicate_generation_filter_keeps_newest_and_unkeyed_rows():
    rows = [
        {"id": "old", "processed_image_url": "same", "created_at": "2025-01-01T00:00:00"},
        {"id": "new", "processed_image_url": "same", "created_at": "2025-02-01T00:00:00"},
        {"id": "other", "processed_image_url": None, "created_at": "2024-01-01T00:00:00"},
    ]
    assert {row["id"] for row in _filter_duplicate_glb_generations(rows)} == {"new", "other"}
    malformed = [{"id": "a", "processed_image_url": "x", "created_at": "bad"}, {"id": "b", "processed_image_url": "x"}]
    assert _filter_duplicate_glb_generations(malformed) == [malformed[0]]
    assert _filter_duplicate_glb_generations([]) == []


@pytest.mark.parametrize("bad", ["", "   "])
def test_ldr_request_rejects_empty_content(bad):
    with pytest.raises(ValidationError):
        LdrToMpdRequest(ldr_content=bad)


def test_estimate_price_request_validates_fields():
    valid = EstimatePriceRequest(ldr_content="1 brick", user_email="a@b.com")
    assert valid.condition == "usedg"
    for kwargs in ({"ldr_content": "", "user_email": "a@b.com"}, {"ldr_content": "x", "user_email": "bad"}, {"ldr_content": "x", "user_email": "a@b.com", "condition": "mint"}):
        with pytest.raises(ValidationError):
            EstimatePriceRequest(**kwargs)


def test_generation_request_models_normalize_and_validate():
    request = TextToBricksRequest(prompt="  a castle  ", model_option="c", prompt_option="b", voxelizer="obj2voxel")
    assert request.prompt == "a castle"
    for kwargs in ({"prompt": ""}, {"prompt": "x" * 1001}, {"prompt": "x", "model_option": "z"}, {"prompt": "x", "prompt_option": "z"}, {"prompt": "x", "voxelizer": "bad"}):
        with pytest.raises(ValidationError):
            TextToBricksRequest(**kwargs)


def test_image_preview_and_username_validators():
    encoded = base64.b64encode(b"png").decode()
    assert UpdateImagePreviewRequest(generation_id="g", image_base64=f"data:image/png;base64,{encoded}").image_base64 == encoded
    for value in ("not base64!", "data:broken"):
        with pytest.raises(ValidationError):
            UpdateImagePreviewRequest(generation_id="g", image_base64=value)
    assert UpdateUsernameRequest(username="  brick.builder-1 ").username == "brick.builder-1"
    for username in ("ab", "bad name", "x" * 31):
        with pytest.raises(ValidationError):
            UpdateUsernameRequest(username=username)
