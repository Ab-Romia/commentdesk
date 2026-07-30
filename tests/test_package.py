# SPDX-License-Identifier: Apache-2.0
"""The package imports, and it agrees with its own metadata about its version."""

import tomllib
from pathlib import Path

import commentdesk


def test_version_matches_pyproject(repo_root: Path) -> None:
    """__version__ and the pyproject version drift the moment one is bumped alone.

    Everything downstream reads one or the other: the wheel carries the pyproject
    value, the run report stamps __version__ onto every row it writes. A row that
    claims a version no release ever had is worse than an unversioned row.
    """
    with open(repo_root / "pyproject.toml", "rb") as handle:
        pyproject = tomllib.load(handle)
    assert commentdesk.__version__ == pyproject["project"]["version"]


def test_package_declares_no_runtime_surface_yet() -> None:
    """__init__ exports the version and nothing else.

    Submodules are imported by path, not re-exported here. Keeping __init__ empty
    of imports keeps `import commentdesk` free of the optional pdf dependency.
    """
    assert commentdesk.__all__ == ["__version__"]
