# SPDX-License-Identifier: Apache-2.0
"""Docs lint, plus one content test per document.

The walker catches the two things that reliably rot: a non-ASCII character pasted in
from somewhere else, and dash typography the sanitizer strips from replies but nobody
strips from prose. The content tests catch a document quietly losing the sentence it
was written for.
"""

import re
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


def test_voice_doc_covers_every_placeholder():
    """The doc is the only place an operator learns the placeholder names.

    Adding a placeholder to build_mapping and forgetting this file leaves an operator
    with a feature they cannot discover, so the test binds the two together.
    """
    from commentdesk.prompt import KNOWLEDGE_TAG

    text = read_doc("writing-a-voice.md")
    for name in (
        "product_name",
        "product_kind",
        "price_text",
        "purchase_link",
        "escalation_contact",
        "max_reply_sentences",
        "bot_disclosure_text",
        "knowledge_tag",
        "cta_instruction",
        "cta_phrases",
        "cta_phrase_1",
    ):
        assert "{{" + name + "}}" in text, f"{name} is undocumented"
    assert f"<{KNOWLEDGE_TAG}>" in text
    assert "two passes" in text
    assert "hard error" in text


def test_sources_doc_documents_every_registered_source():
    """A source nobody documented is a source nobody can configure."""
    import commentdesk.sources.text  # noqa: F401  (registers "text")
    from commentdesk import sources

    text = read_doc("sources.md")
    for name in sources.SOURCES:
        assert f'source = "{name}"' in text, f"source {name!r} is undocumented"
    assert "@register(" in text
    assert "def load_" in text
    assert "refuses to overwrite" in text


def test_bakeoff_doc_carries_no_unmeasured_figures():
    """No table and no quoted numbers until they are re-measured.

    The method is publishable now. Any specific figure is not, because none has been
    measured against the example products in this repository.
    """
    text = read_doc("bakeoff.md")
    table_lines = [line for line in text.splitlines() if line.strip().startswith("|")]
    assert table_lines == [], "bakeoff.md must not carry a results table yet"
    assert "re-verify" in text
    assert "data_collection" in text
    assert "blind" in text
    # Prices and token counts are the figures that must not appear before measurement.
    assert not re.search(r"\$\s*\d", text), "a dollar figure appears before measurement"
    assert not re.search(r"\b\d[\d,]*\s*(tokens|ms|seconds)\b", text), (
        "a measured quantity appears before measurement"
    )


def test_comments_csv_doc_names_every_column_the_engine_reads():
    """The input CSV was documented nowhere. config.toml, the voice files and the
    knowledge document each had a complete reference page; the one file an operator
    builds by hand in a spreadsheet had four command lines and a mermaid node. A
    column added to IN_FIELDS and left out of this page is a column nobody can find,
    so the two are bound together."""
    from commentdesk.engine import IN_FIELDS, TITLE_ALIAS

    text = read_doc("comments-csv.md")
    for field in IN_FIELDS:
        assert f"`{field}`" in text, f"comments-csv.md does not document {field}"
    # The alias is the part an operator with an older export needs to read.
    assert f"`{TITLE_ALIAS}`" in text
    # And the two behaviours nobody discovers on their own.
    assert "utf-8-sig" in text
    assert "refused" in text


def test_the_readme_documentation_table_lists_every_doc():
    """A page nobody links to is a page nobody reads. The table is the only index."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for path in sorted(DOCS.glob("*.md")):
        assert f"`docs/{path.name}`" in readme, f"README does not link docs/{path.name}"


def test_platform_policy_maps_features_to_clauses():
    text = read_doc("platform-policy.md")
    for clause in (
        "III.I.2",
        "III.E.3.d",
        "III.I.11",
        "1.7",
        "Article 50(1)",
        "Article 50(4)",
    ):
        assert clause in text, f"{clause} is not mapped to a feature"
    assert "not legal advice" in text
    assert "data_collection" in text


def test_limits_doc_states_every_known_limit():
    text = read_doc("limits.md")
    for phrase in (
        "One call to action style per run",
        "breaks the cache",
        "alarm threshold",
        "shape and never content",
        "cannot be prevented",
        "context window",
        "The engine's own English",
    ):
        assert phrase in text, f"limits.md no longer states: {phrase!r}"


# Every English string the engine owns, as (module, attribute). The ASCII-only guard
# in test_guarantees.py cannot see these, because English is ASCII: it proves no copy
# in another script reached a module and nothing more. This list is the other half of
# that guarantee, and the test below binds it to the document that publishes it.
ENGINE_OWNED_ENGLISH = [
    ("commentdesk.prompt", "OUTPUT_CONTRACT"),
    ("commentdesk.engine", "RETRY_NUDGE"),
    ("commentdesk.engine", "EMPTY_COMMENT_REASON"),
    ("commentdesk.sources.pdf_vision", "TRANSCRIBE_PROMPT"),
    ("commentdesk.render.review_html", "DRAFT_BANNER"),
    ("commentdesk.render.review_html", "DEFAULT_CURRENCY_NOTE"),
    ("commentdesk.render.review_html", "NEVER_POSTED_NOTE"),
    ("commentdesk.render.review_html", "COLUMNS"),
]


@pytest.mark.parametrize(("module_name", "attribute"), ENGINE_OWNED_ENGLISH)
def test_limits_doc_names_every_english_string_the_engine_owns(module_name, attribute):
    """The engine's own English is enumerable, so limits.md enumerates it.

    A constant renamed or a new one added without touching the document leaves the
    published list quietly incomplete, which is the exact failure the wide claim
    ("nothing in the engine holds human-language copy") used to hide. Both halves are
    checked: the attribute must still exist, and the document must still name it.
    """
    import importlib

    module = importlib.import_module(module_name)
    assert hasattr(module, attribute), f"{module_name}.{attribute} no longer exists"
    assert attribute in read_doc("limits.md"), f"limits.md does not name {attribute}"


def test_community_files_exist_and_state_the_hard_rules():
    contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    # These four are the rules a well-meaning pull request breaks by accident.
    for rule in ("non-ascii", "no posting path", "data_collection", "em dash"):
        assert rule in contributing.lower(), f"CONTRIBUTING.md omits: {rule}"
    assert "make check" in contributing

    security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    assert "Security Advisories" in security
    assert "@" in security, "SECURITY.md needs a fallback contact"

    conduct = (ROOT / "CODE_OF_CONDUCT.md").read_text(encoding="utf-8")
    assert "Contributor Covenant" in conduct
    assert "@" in conduct, "CODE_OF_CONDUCT.md needs an enforcement contact"
