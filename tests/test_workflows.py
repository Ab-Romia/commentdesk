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


def test_publish_uses_trusted_publishing_in_a_protected_environment():
    """No long-lived token in a repository secret, ever.

    Trusted publishing exchanges a short-lived OIDC token for an upload. The protected
    environment is what forces a human approval step in front of it.
    """
    text = (WORKFLOWS / "publish.yml").read_text(encoding="utf-8")
    assert "id-token: write" in text
    assert re.search(r"environment:\n\s+name: release", text)
    assert "password:" not in text, "trusted publishing needs no password"
    assert "PYPI_API_TOKEN" not in text
    assert "secrets." not in text, "no repository secret should be needed to publish"
    # id-token: write must be scoped to the publishing job, not granted file-wide.
    top, _, _jobs = text.partition("\njobs:")
    assert "id-token" not in top


def test_publish_only_runs_on_a_published_release():
    text = (WORKFLOWS / "publish.yml").read_text(encoding="utf-8")
    assert re.search(r"on:\n  release:\n    types: \[published\]", text)
    assert "on: push" not in text


def test_dependabot_is_monthly_grouped_and_cooled_down():
    """Ungrouped weekly bumps are noise, and a same-day bump is a supply chain risk."""
    text = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    assert text.count("interval: monthly") >= 2
    assert "groups:" in text
    assert "default-days: 14" in text
    for ecosystem in ("github-actions", "uv"):
        assert f"package-ecosystem: {ecosystem}" in text


def test_local_hooks_call_the_same_make_targets_as_ci():
    """Hooks that reimplement CI drift from it, and the drift is discovered in CI.

    Calling the same make targets means there is exactly one definition of each check.
    """
    config = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    hook_targets = set(re.findall(r"entry:\s*make\s+(\w+)", config))
    ci = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    ci_targets = set(re.findall(r"run:\s*make\s+(\w+)", ci))
    assert ci_targets, "ci.yml calls no make targets"
    assert ci_targets <= hook_targets, (
        f"CI runs targets no hook runs: {sorted(ci_targets - hook_targets)}"
    )


def test_remote_hooks_are_present_and_revision_pinned():
    config = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    for hook in ("codespell", "validate-pyproject", "end-of-file-fixer"):
        assert f"id: {hook}" in config, f"missing hook: {hook}"
    revs = re.findall(r"(?m)^\s+rev:\s*(\S+)$", config)
    assert revs, "no pinned revisions"
    assert all(rev not in ("HEAD", "master", "main") for rev in revs), revs


TEMPLATES = ROOT / ".github" / "ISSUE_TEMPLATE"


def test_issue_templates_exist_and_disable_blank_issues():
    assert (TEMPLATES / "bug_report.yml").exists()
    assert (TEMPLATES / "feature_request.yml").exists()
    config = (TEMPLATES / "config.yml").read_text(encoding="utf-8")
    assert "blank_issues_enabled: false" in config
    assert "SECURITY.md" in config, "security reports must be routed away from issues"


def test_issue_templates_never_ask_for_a_secret():
    """A form field is where a key gets pasted into a public issue."""
    for path in sorted(TEMPLATES.glob("*.yml")):
        text = path.read_text(encoding="utf-8").lower()
        for word in ("api key", "api_key", "token", "credential", "password"):
            if word in text:
                assert "never" in text or "do not" in text, (
                    f"{path.name} mentions {word!r} without warning against it"
                )


def test_pull_request_template_lists_the_hard_rules():
    text = (ROOT / ".github" / "pull_request_template.md").read_text(encoding="utf-8")
    for rule in ("ascii", "posting", "em dash", "make check"):
        assert rule in text.lower(), f"pull request template omits: {rule}"
