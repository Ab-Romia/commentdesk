# SPDX-License-Identifier: Apache-2.0
"""A structural rule that holds for every connector, present and future.

tests/test_guarantees.py proves one half of the publishing promise: the send is
reached from the approval loop and from nowhere else. This file is the other
half, and it was named as the missing test in notes/platforms/gate-ruling.md
and had no successor until now.

A connector is the only part of this package that can change something on
somebody else's platform. The gate tests watch the one method the gate calls.
Nothing watched the rest of the connector, so a refresh helper, a retry path or
a read that quietly marks a comment as seen could issue a write from a code
path no keystroke reaches, and every AST test in this repository would report
nothing, because no send happened.
"""

from __future__ import annotations

import ast
from pathlib import Path

from conftest import PACKAGE_ROOT

CONNECTORS = PACKAGE_ROOT / "platforms"

# Anything that is not a read. GET and HEAD are absent on purpose: reading is
# what fetch_comments does for a living, and the check that matters here is
# about changing somebody else's data rather than about touching the network.
WRITING_VERBS = {"POST", "PUT", "PATCH", "DELETE"}
PUBLISH_METHOD = "publish_reply"


def _enclosing(tree: ast.Module, node: ast.AST) -> str:
    parents: dict[int, ast.AST] = {}
    for outer in ast.walk(tree):
        for child in ast.iter_child_nodes(outer):
            parents[id(child)] = outer
    current: ast.AST | None = node
    while current is not None and id(current) in parents:
        current = parents[id(current)]
        if isinstance(current, ast.FunctionDef):
            return current.name
    return ""


def test_no_connector_names_a_writing_verb_outside_the_publish_path() -> None:
    offenders = []
    for path in sorted(CONNECTORS.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or node.value not in WRITING_VERBS:
                continue
            if _enclosing(tree, node) != PUBLISH_METHOD:
                offenders.append(f"{path.name}:{node.lineno}: {node.value}")
    assert offenders == [], (
        "a connector names a verb that changes something on a platform, outside the "
        f"one method the approval gate can reach: {offenders}"
    )


def test_the_verb_rule_catches_a_write_moved_into_a_helper(tmp_path: Path) -> None:
    """The rule is only worth having if it fires on the shape it was written for:
    a write tucked into a private helper that a read path could also call."""
    source = 'def _refresh(url):\n    return _call("POST", url, None)\n'
    module = tmp_path / "helper.py"
    module.write_text(source, encoding="utf-8")
    tree = ast.parse(source, filename=str(module))
    found = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and node.value in WRITING_VERBS
        and _enclosing(tree, node) != PUBLISH_METHOD
    ]
    assert found == ["POST"]
