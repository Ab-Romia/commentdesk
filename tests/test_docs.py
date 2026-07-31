# SPDX-License-Identifier: Apache-2.0
"""Docs lint, plus one content test per document.

The walker catches the two things that reliably rot: a non-ASCII character pasted in
from somewhere else, and dash typography the sanitizer strips from replies but nobody
strips from prose. The content tests catch a document quietly losing the sentence it
was written for.
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def markdown_files():
    # fixtures is excluded on purpose, not by oversight: tests/fixtures/nazzef-kit-ar
    # is a fictional product written entirely in Arabic, and its .md files are the
    # acceptance evidence that nothing in this project assumes Latin script or ASCII.
    # Holding fixture content to an ASCII-only prose lint would be testing the wrong
    # thing in the one place non-ASCII content is not a defect but the point.
    skip = {".venv", "node_modules", ".git", "fixtures"}
    return sorted(
        p
        for p in ROOT.rglob("*.md")
        if not any(part in skip for part in p.parts) and "notes" not in p.parts
    )


def read_doc(name):
    return (DOCS / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("path", markdown_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_markdown_is_ascii_and_free_of_dash_typography(path):
    text = path.read_text(encoding="utf-8")
    assert text.isascii(), f"{path} contains a non-ascii character"
    assert "—" not in text, f"{path} contains an em dash"
    assert "–" not in text, f"{path} contains an en dash"  # noqa: RUF001


def test_architecture_explains_the_cached_prefix_and_its_limit():
    text = read_doc("architecture.md")
    assert "byte-identical" in text
    assert "```mermaid" in text
    assert "context window" in text
    # The no-retrieval decision is only defensible next to the condition that makes it
    # true. If the condition ever disappears from this file, the claim is unsupported.
    assert "one document" in text
    assert "nothing that varies per row may enter the prefix" in text
