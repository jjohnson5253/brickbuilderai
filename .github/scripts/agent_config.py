#!/usr/bin/env python3
"""Resolve a trusted custom-agent profile for GitHub workflows."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


AGENT_BY_LABEL = {
    "agent:implementer": "implementer",
    "agent:outcome-reviewer": "outcome-reviewer",
}
DEFAULT_AGENT = "implementer"
SAFE_VALUE = re.compile(r"^[A-Za-z0-9._-]+$")


def parse_frontmatter(profile: Path) -> dict[str, str]:
    lines = profile.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{profile} has no YAML frontmatter")

    values: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith((" ", "\t")) or ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip().strip("'\"")
        if value:
            values[key.strip()] = value
    else:
        raise ValueError(f"{profile} has unterminated YAML frontmatter")

    return values


def label_names(raw_labels: str) -> set[str]:
    labels: Any = json.loads(raw_labels)
    if not isinstance(labels, list):
        raise ValueError("labels JSON must be a list")

    names: set[str] = set()
    for label in labels:
        if isinstance(label, str):
            names.add(label)
        elif isinstance(label, dict) and isinstance(label.get("name"), str):
            names.add(label["name"])
        else:
            raise ValueError("each label must be a string or an object with a name")
    return names


def select_agent(raw_labels: str) -> str:
    requested = {AGENT_BY_LABEL[name] for name in label_names(raw_labels) if name in AGENT_BY_LABEL}
    if len(requested) > 1:
        raise ValueError("issue has conflicting agent labels")
    return next(iter(requested), DEFAULT_AGENT)


def resolve(agent: str, repository_root: Path) -> dict[str, str]:
    if agent not in set(AGENT_BY_LABEL.values()):
        raise ValueError(f"unsupported agent: {agent}")

    profile = repository_root / ".github" / "agents" / f"{agent}.agent.md"
    values = parse_frontmatter(profile)
    model = values.get("model", "")
    if model and not SAFE_VALUE.fullmatch(model):
        raise ValueError(f"{profile} has an invalid model")
    if values.get("target") != "github-copilot":
        raise ValueError(f"{profile} must target github-copilot")
    return {"agent": agent, "model": model}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--agent")
    group.add_argument("--labels-json")
    args = parser.parse_args()

    agent = args.agent or select_agent(args.labels_json)
    print(json.dumps(resolve(agent, args.repository_root.resolve())))


if __name__ == "__main__":
    main()
