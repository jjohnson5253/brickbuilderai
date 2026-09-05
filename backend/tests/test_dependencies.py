import tomllib
from pathlib import Path


def test_unused_heavyweight_dependencies_are_not_installed():
    pyproject = tomllib.loads(
        (Path(__file__).parents[1] / "pyproject.toml").read_text()
    )
    dependencies = {
        dependency.split("[", 1)[0].split(">", 1)[0].split("=", 1)[0]
        for dependency in pyproject["project"]["dependencies"]
    }

    assert dependencies.isdisjoint({"matplotlib", "onnxruntime", "open3d", "rembg"})
