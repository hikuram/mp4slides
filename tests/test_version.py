from pathlib import Path

import tomllib

import mp4slides


def test_package_version_matches_pyproject() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    metadata = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    assert mp4slides.__version__ == metadata["project"]["version"]
