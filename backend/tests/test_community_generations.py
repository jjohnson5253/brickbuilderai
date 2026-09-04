import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.requests import getCommunityGenerations
from src.requests.getCommunityGenerations import (
    GetCommunityGenerationsRequest,
    get_community_generations,
)

AUTH = {"user_id": "anonymous", "user_email": "anonymous"}


def make_generation(**overrides):
    generation = {
        "id": "gen-1",
        "user_id": "anon-1",
        "user_type": "anonymous",
        "prompt": "a castle",
        "name": "Castle",
        "detail_level": 40,
        "endpoint": "/textToBricks",
        "created_at": "2026-01-01T00:00:00Z",
        "status": "completed",
        "preview_image_url": "https://example.com/preview.png",
        "is_community": True,
        "is_highlighted": True,
        "brick_count": 231,
    }
    generation.update(overrides)
    return generation


class FakeGenerationStorage:
    def __init__(self, generations):
        self.generations = generations
        self.calls = []

    async def get_community_generations(
        self, limit=10, status_filter=None, offset=0, highlighted_only=False
    ):
        self.calls.append(
            {
                "limit": limit,
                "status_filter": status_filter,
                "offset": offset,
                "highlighted_only": highlighted_only,
            }
        )
        if highlighted_only:
            return [g for g in self.generations if g.get("is_highlighted")]
        return list(self.generations)


def test_highlighted_filter_passed_to_storage(monkeypatch):
    storage = FakeGenerationStorage(
        [make_generation(), make_generation(id="gen-2", is_highlighted=False)]
    )
    monkeypatch.setattr(getCommunityGenerations, "generation_storage", storage)

    response = asyncio.run(
        get_community_generations(
            GetCommunityGenerationsRequest(limit=10, highlighted=True), AUTH
        )
    )

    assert storage.calls == [
        {"limit": 11, "status_filter": None, "offset": 0, "highlighted_only": True}
    ]
    assert [g.id for g in response.generations] == ["gen-1"]
    assert response.generations[0].is_highlighted is True
    assert response.generations[0].brick_count == 231
    assert response.has_more is False


def test_highlighted_defaults_to_all_community_generations(monkeypatch):
    storage = FakeGenerationStorage(
        [make_generation(), make_generation(id="gen-2", is_highlighted=False)]
    )
    monkeypatch.setattr(getCommunityGenerations, "generation_storage", storage)

    response = asyncio.run(
        get_community_generations(GetCommunityGenerationsRequest(limit=10), AUTH)
    )

    assert storage.calls[0]["highlighted_only"] is False
    assert [g.id for g in response.generations] == ["gen-1", "gen-2"]
    assert response.generations[1].is_highlighted is False
