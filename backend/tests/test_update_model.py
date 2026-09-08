import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import src.requests.updateModel as module


def test_process_update_model_stores_recolored_and_segment_ldrs(monkeypatch):
    storage = SimpleNamespace(
        client=MagicMock(),
        store_model_file=AsyncMock(),
        store_parts_list_csv=AsyncMock(),
        update_status=AsyncMock(),
    )

    def fake_glb2brick(*, glb_path, xyzrgb_path, auto_adjust_brick_count):
        assert auto_adjust_brick_count is False
        source = Path(xyzrgb_path).read_text()
        ldr_path = Path(glb_path).with_suffix(".ldr")
        ldr_path.write_text(f"0 {Path(glb_path).stem}\n{source}")
        return {
            "ldr_file": str(ldr_path),
            "problematic_xyzrgb_file": None,
        }

    class FakePacker:
        def pack_ldraw_model(self, ldr_path):
            mpd_path = Path(ldr_path).with_suffix(".mpd")
            mpd_path.write_text("0 packed")
            return str(mpd_path)

    monkeypatch.setattr(module, "generation_storage", storage)
    monkeypatch.setattr(module, "glb2brick", fake_glb2brick)
    monkeypatch.setattr(module, "LDrawPacker", FakePacker)
    monkeypatch.setattr(module, "track_api_call", lambda **_kwargs: None)

    asyncio.run(
        module.process_update_model_task(
            generation_id="new-generation",
            original_generation_id="original-generation",
            xyzrgb_content="0 0 0 12 34 56\n",
            segment_xyzrgb_content="0 0 0 201 26 9\n",
            generation={},
            user_email="builder@example.com",
            is_developer=False,
        )
    )

    stored = {
        call.kwargs["file_type"]: call.kwargs["file_content"]
        for call in storage.store_model_file.await_args_list
    }
    assert "0 recolored" in stored["ldr"]
    assert "12 34 56" in stored["ldr"]
    assert "0 segments" in stored["segment_ldr"]
    assert "201 26 9" in stored["segment_ldr"]
    assert stored["mpd"] == "0 packed"
    storage.update_status.assert_awaited_with("new-generation", "completed")
