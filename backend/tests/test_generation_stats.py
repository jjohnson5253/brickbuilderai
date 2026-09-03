import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.requests import getGenerationStats
from src.utils.generation_storage import GenerationStorage


class FakeGenerationStorage:
    async def get_generation_stats(self):
        return {"generation_count": 12, "brick_count": 3456}


def test_get_generation_stats(monkeypatch):
    monkeypatch.setattr(
        getGenerationStats, "generation_storage", FakeGenerationStorage()
    )

    response = asyncio.run(getGenerationStats.get_generation_stats())

    assert response.generation_count == 12
    assert response.brick_count == 3456


def test_get_generation_stats_without_storage(monkeypatch):
    monkeypatch.setattr(getGenerationStats, "generation_storage", None)

    response = asyncio.run(getGenerationStats.get_generation_stats())

    assert response.generation_count == 0
    assert response.brick_count == 0


class FakeGenerationTable:
    def __init__(self):
        self.updated = None

    def update(self, values):
        self.updated = values
        return self

    def eq(self, _column, _value):
        return self

    def execute(self):
        return type("Result", (), {"data": [self.updated]})()


class FakeClient:
    def __init__(self):
        self.generations = FakeGenerationTable()

    def table(self, name):
        assert name == "generations"
        return self.generations


def test_store_parts_list_persists_brick_count():
    storage = GenerationStorage.__new__(GenerationStorage)
    storage.client = FakeClient()

    async def fake_upload(**_kwargs):
        return "https://example.com/parts.csv"

    storage._upload_file_to_storage = fake_upload
    ldr_content = "\n".join(
        [
            "1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat",
            "1 4 1 0 0 1 0 0 0 1 0 0 0 1 3001.dat",
            "1 1 2 0 0 1 0 0 0 1 0 0 0 1 3002.dat",
        ]
    )

    result = asyncio.run(storage.store_parts_list_csv("generation-1", ldr_content))

    assert result == "https://example.com/parts.csv"
    assert storage.client.generations.updated == {
        "parts_list_csv_url": "https://example.com/parts.csv",
        "brick_count": 3,
    }
