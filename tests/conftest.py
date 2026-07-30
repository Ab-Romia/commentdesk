# SPDX-License-Identifier: Apache-2.0
"""Shared test paths and fixtures.

Paths are computed from this file, never from the working directory, so the suite
behaves the same under `pytest`, `pytest tests/some_test.py`, and an editor runner.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
PACKAGE_ROOT = SRC_ROOT / "commentdesk"


@pytest.fixture
def repo_root() -> Path:
    """The checkout root."""
    return REPO_ROOT


@pytest.fixture
def package_root() -> Path:
    """The directory holding the packaged modules."""
    return PACKAGE_ROOT
