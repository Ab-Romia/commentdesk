# SPDX-License-Identifier: Apache-2.0
"""Workflow files are checked as text on purpose.

Every property below is textual: a forty character SHA, a literal flag, a version
comment. Parsing the YAML would require a dependency the project does not have and
would not check the comment that makes a pin auditable.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

# uses: owner/repo@<40 hex> # v1.2.3
PINNED = re.compile(
    r"uses:\s+(?P<action>[\w.-]+/[\w./-]+)@(?P<sha>[0-9a-f]{40})\s+#\s*v?\d[\w.-]*\s*$"
)
ANY_USES = re.compile(r"^\s*-?\s*uses:\s+\S+.*$", re.MULTILINE)


def workflow_files():
    return sorted(WORKFLOWS.glob("*.yml"))


def uses_lines(path):
    return [m.group(0).strip() for m in ANY_USES.finditer(path.read_text(encoding="utf-8"))]


@pytest.mark.parametrize("path", workflow_files(), ids=lambda p: p.name)
def test_every_action_is_sha_pinned_with_a_version_comment(path):
    """A tag is mutable. A SHA is not, and the comment is what keeps it readable."""
    unpinned = [line for line in uses_lines(path) if not PINNED.search(line)]
    assert unpinned == [], f"{path.name} has unpinned actions: {unpinned}"


@pytest.mark.parametrize("path", workflow_files(), ids=lambda p: p.name)
def test_top_level_permissions_are_read_only(path):
    text = path.read_text(encoding="utf-8")
    assert re.search(r"(?m)^permissions:\n  contents: read\n", text), (
        f"{path.name} must declare read-only permissions at the top level"
    )


@pytest.mark.parametrize("path", workflow_files(), ids=lambda p: p.name)
def test_checkout_never_persists_credentials(path):
    text = path.read_text(encoding="utf-8")
    checkouts = text.count("actions/checkout@")
    assert checkouts == text.count("persist-credentials: false"), (
        f"{path.name} has a checkout that leaves a credential in the runner"
    )


def test_ci_matrix_covers_every_supported_python():
    text = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    m = re.search(r"python-version:\s*\[(?P<versions>[^\]]+)\]", text)
    assert m, "ci.yml declares no python matrix"
    found = {v.strip().strip('"').strip("'") for v in m.group("versions").split(",")}
    assert {"3.11", "3.12", "3.13", "3.14"} <= found, f"matrix misses versions: {found}"


def test_ci_does_not_fail_fast():
    """One version failing must not hide the result for the other three."""
    text = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    assert "fail-fast: false" in text


def test_ci_cancels_superseded_runs():
    text = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    assert re.search(r"(?m)^concurrency:\n", text)
    assert "cancel-in-progress: true" in text


def test_lint_runs_once_outside_the_matrix():
    """Lint and typecheck are version independent. Running them four times is waste."""
    text = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    lint = text.split("  lint:", 1)[1].split("\n  test:", 1)[0]
    assert "matrix" not in lint
    assert "make lint" in lint
    assert "make typecheck" in lint
