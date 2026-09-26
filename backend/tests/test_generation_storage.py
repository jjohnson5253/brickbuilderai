import asyncio
import sys
from pathlib import Path
from types import ModuleType

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

fake_auth = ModuleType("src.utils.auth")
fake_auth.supabase_client = None
sys.modules.setdefault("src.utils.auth", fake_auth)
sys.modules["src.utils.auth"].supabase_client = None

fake_image_processing = ModuleType("src.utils.image_processing")
fake_image_processing.convert_base64_to_png = lambda *_args, **_kwargs: None
sys.modules.setdefault("src.utils.image_processing", fake_image_processing)
sys.modules["src.utils.image_processing"].convert_base64_to_png = (
    lambda *_args, **_kwargs: None
)

fake_brickowl_utils = ModuleType("src.utils.brickowl_utils")
fake_brickowl_utils.parse_ldr_file = lambda *_args, **_kwargs: None
fake_brickowl_utils.generate_parts_list_csv = lambda *_args, **_kwargs: ""
sys.modules.setdefault("src.utils.brickowl_utils", fake_brickowl_utils)
sys.modules["src.utils.brickowl_utils"].parse_ldr_file = lambda *_args, **_kwargs: None
sys.modules["src.utils.brickowl_utils"].generate_parts_list_csv = (
    lambda *_args, **_kwargs: ""
)

fake_supabase = ModuleType("supabase")
fake_supabase.Client = object
sys.modules.setdefault("supabase", fake_supabase)

sys.modules.pop("src.utils.generation_storage", None)

from src.utils.generation_storage import GenerationStorage


class FakeCommunityQuery:
    def __init__(self, client):
        self.client = client
        self.filters = []
        self.ordering = []
        self.range_values = None

    def select(self, _fields):
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def in_(self, key, values):
        self.filters.append((key, tuple(values)))
        return self

    def order(self, key, desc=False):
        self.ordering.append((key, desc))
        return self

    def range(self, start, end):
        self.range_values = (start, end)
        return self

    def execute(self):
        if any(key == "like_count" for key, _desc in self.ordering):
            raise Exception('column "like_count" does not exist')

        return type("Result", (), {
            "data": [
                {"id": "generation-2", "created_at": "2026-09-26T00:00:00Z"},
                {"id": "generation-1", "created_at": "2026-09-25T00:00:00Z"},
            ]
        })()


class FakeCommunityClient:
    def __init__(self):
        self.queries = []

    def table(self, table_name):
        assert table_name == "generations"
        query = FakeCommunityQuery(self)
        self.queries.append(query)
        return query


def test_get_community_generations_falls_back_to_recent_when_like_count_is_missing():
    client = FakeCommunityClient()
    storage = GenerationStorage.__new__(GenerationStorage)
    storage.client = client

    result = asyncio.run(storage.get_community_generations(limit=2, offset=0, sort="top"))

    assert [row["id"] for row in result] == ["generation-2", "generation-1"]
    assert len(client.queries) == 2
    assert ("like_count", True) in client.queries[0].ordering
    assert client.queries[1].ordering == [("created_at", True)]
