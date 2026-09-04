from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "agent_config.py"
SPEC = importlib.util.spec_from_file_location("agent_config", MODULE_PATH)
assert SPEC and SPEC.loader
agent_config = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(agent_config)


class AgentConfigTests(unittest.TestCase):
    def test_defaults_to_implementer(self) -> None:
        self.assertEqual(agent_config.select_agent("[]"), "implementer")

    def test_selects_labeled_agent_from_event_objects(self) -> None:
        labels = json.dumps([{"name": "bug"}, {"name": "agent:outcome-reviewer"}])
        self.assertEqual(agent_config.select_agent(labels), "outcome-reviewer")

    def test_rejects_conflicting_agent_labels(self) -> None:
        labels = json.dumps(["agent:implementer", "agent:outcome-reviewer"])
        with self.assertRaisesRegex(ValueError, "conflicting"):
            agent_config.select_agent(labels)

    def test_resolves_model_from_profile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profiles = root / ".github" / "agents"
            profiles.mkdir(parents=True)
            (profiles / "implementer.agent.md").write_text(
                "---\ntarget: github-copilot\nmodel: gpt-5.6-terra\n---\n",
                encoding="utf-8",
            )
            self.assertEqual(
                agent_config.resolve("implementer", root),
                {"agent": "implementer", "model": "gpt-5.6-terra"},
            )

    def test_repository_reviewer_profile_has_a_pinned_model(self) -> None:
        repository_root = Path(__file__).parents[3]
        resolved = agent_config.resolve("outcome-reviewer", repository_root)
        self.assertEqual(resolved["agent"], "outcome-reviewer")
        self.assertTrue(resolved["model"])

    def test_rejects_unknown_agent(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported"):
            agent_config.resolve("../../other", Path.cwd())


if __name__ == "__main__":
    unittest.main()
