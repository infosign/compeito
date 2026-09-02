"""The version is declared twice — keep the two declarations from drifting.

`src/__init__.__version__` is what the API advertises; `pyproject.toml` is what
packaging and the release tag use. Nothing enforces the two at runtime, so a
release that bumps one and forgets the other would ship an OpenAPI document
claiming the previous version.
"""

import tomllib
from pathlib import Path

from src import __version__


def test_pyproject_version_matches_package_version():
    pyproject = tomllib.loads((Path(__file__).parents[2] / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == __version__
