from pathlib import Path

import pytest

from src.cli import llm_render


GENERATION_ID = "d7f8fdb4-b010-4ef5-bd68-069aa20f96a4"


class FakeResponse:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code
        self.ok = 200 <= status_code < 300

    def json(self):
        return self._data


class FakeSession:
    def __init__(self, generation=None, render=None):
        self.generation = generation or {}
        self.render = render or {}
        self.get_calls = []
        self.post_calls = []

    def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        return FakeResponse(self.generation)

    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return FakeResponse(self.render)


def _args(tmp_path: Path, *extra: str):
    return llm_render.build_parser().parse_args(
        [
            GENERATION_ID,
            "--output",
            str(tmp_path / "response.json"),
            "--xyzrgb-output",
            str(tmp_path / "output.xyzrgb"),
            *extra,
        ]
    )


def test_run_resolves_generation_urls_and_writes_outputs(tmp_path):
    session = FakeSession(
        generation={
            "xyzrgb_url": "https://example.com/model.xyzrgb",
            "processed_image_url": "https://example.com/reference.png",
        },
        render={
            "xyzrgb_content": "0 0 0 1 2 3\n",
            "message": "Recolored one segment",
        },
    )
    args = _args(tmp_path, "--api-key", "secret", "--include-preview")

    result = llm_render.run(args, session=session)

    assert result["message"] == "Recolored one segment"
    assert len(session.get_calls) == 1
    render_url, render_request = session.post_calls[0]
    assert render_url == "http://127.0.0.1:8002/llmRender"
    assert render_request["headers"]["X-API-Key"] == "secret"
    assert render_request["json"] == {
        "generation_id": GENERATION_ID,
        "xyzrgb_url": "https://example.com/model.xyzrgb",
        "reference_image_url": "https://example.com/reference.png",
        "prompt": llm_render.DEFAULT_PROMPT,
        "max_segments": 16,
        "include_preview": True,
    }
    assert args.xyzrgb_output.read_text() == "0 0 0 1 2 3\n"
    assert '"message": "Recolored one segment"' in args.output.read_text()


def test_run_skips_generation_lookup_when_both_urls_are_overridden(tmp_path):
    session = FakeSession(render={"xyzrgb_content": "0 0 0 1 2 3\n"})
    args = _args(
        tmp_path,
        "--xyzrgb-url",
        "https://example.com/override.xyzrgb",
        "--reference-image-url",
        "https://example.com/override.png",
    )

    llm_render.run(args, session=session)

    assert session.get_calls == []
    assert session.post_calls[0][1]["json"]["xyzrgb_url"].endswith("override.xyzrgb")


def test_resolve_input_urls_reports_missing_generation_data():
    session = FakeSession(generation={"status": "completed"})

    with pytest.raises(llm_render.LlmRenderCliError, match="no xyzrgb_url"):
        llm_render.resolve_input_urls(
            session,
            "http://127.0.0.1:8002",
            GENERATION_ID,
            {},
            None,
            None,
        )
