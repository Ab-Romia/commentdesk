# SPDX-License-Identifier: Apache-2.0
"""Docs lint, plus one content test per document.

The walker catches the two things that reliably rot: a non-ASCII character pasted in
from somewhere else, and dash typography the sanitizer strips from replies but nobody
strips from prose. The content tests catch a document quietly losing the sentence it
was written for.
"""

import ast
import re
from pathlib import Path

import pytest

from conftest import PACKAGE_ROOT

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


def test_bakeoff_doc_publishes_measured_figures_that_carry_their_date():
    """This test used to assert the opposite, and was right to.

    Until a bake-off had actually been run against the example products in this
    repository, the method was publishable and no specific figure was, so this
    asserted that the page held no table and no dollar amount. A run against
    examples/field-guide-book on 2026-08-01 changed the fact, so the test pins the
    new one rather than being deleted: the figures are on the page, the command that
    reproduces them is on the page, and so is the date they were true on.
    """
    text = read_doc("bakeoff.md")
    table_lines = [line for line in text.splitlines() if line.strip().startswith("|")]
    assert table_lines, "bakeoff.md carries a measured run; it needs its results table"
    assert re.search(r"\$\s*\d", text), "the measured costs are the point of the section"
    # A figure with no date next to it is what this page has always refused to print.
    assert "2026-08-01" in text, "a published figure has to carry the date it was true on"
    assert "re-verify" in text
    assert "Re-run the command before you rely on any of it." in text
    # Reproducible means a reader can run it, which means the command stays on the page.
    assert "commentdesk bakeoff --config examples/field-guide-book/config.toml" in text
    assert "data_collection" in text
    assert "blind" in text


def test_bakeoff_doc_reports_the_results_that_did_not_flatter():
    """A results section holding only the good news is marketing, not evidence.

    The run measured three things worth publishing and only one of them is a
    compliment: the cached prefix made the default route far cheaper per comment,
    the plug rate went over the config's own alarm threshold on two of three models,
    and the default closed most of its replies on the identical pointer. The second
    and third are the ones an author is tempted to quietly drop on the next edit, so
    they are the ones pinned here.
    """
    text = read_doc("bakeoff.md")
    assert "OVER plug_cap 0.75" in text, "the run that exceeded its own alarm threshold"
    assert "repetition: closing" in text, "the repetition find_repetition reported"
    # Both are already documented as known limits. The write-up has to say so rather
    # than presenting either as a surprise, because a reader who checks will find them.
    assert "docs/limits.md" in text


def test_bakeoff_doc_records_the_scoring_pass_including_how_first_place_was_decided():
    """The page prescribes blind scoring, so the page has to report its own.

    Three parts of that write-up are the ones that would quietly improve on a later
    edit, so they are pinned here. The finding against `small` is a specific row and
    a specific decision rather than an impression. First place went to `primary` on
    cost after two sources tied on quality, which is not a quality ranking and must
    not start reading like one. And the pass is thinner than the method section a
    few screens up asks of a reader, which is a thing to say out loud in the results
    rather than to leave for a reader to work out.
    """
    # Line breaks are wrapping, not content, so the assertions read the prose flat.
    flat = " ".join(read_doc("bakeoff.md").split())
    assert "One scorer, one pass." in flat
    assert "`primary` first, `cheap` second, `small` third" in flat
    assert "Do you ship to Canada and how long does it take?" in flat
    assert "First place was decided on cost, not on quality." in flat
    assert "two tied and one below them" in flat
    assert "asks more of you than it demonstrates itself" in flat


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
    ("commentdesk.ui", "_PAGE"),
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


def _module_dotted_name(path: Path) -> str:
    """The import path for a module under src/, e.g. commentdesk.render.review_html."""
    rel = path.relative_to(PACKAGE_ROOT.parent).with_suffix("")
    parts = [part for part in rel.parts if part != "__init__"]
    return ".".join(parts)


def _module_level_string_constants(path: Path) -> list[tuple[str, str]]:
    """(name, value) for every bare `NAME = "..."` at the top of `path`'s module body.

    Deliberately narrow. Every constant this project has ever used for
    operator-visible copy (`_PAGE`, `OUTPUT_CONTRACT`, `DRAFT_BANNER`, and the rest
    of ENGINE_OWNED_ENGLISH above) is exactly this shape: a plain string literal
    assigned to a single name at module level. An assignment nested inside a
    function or a class, a tuple or list of strings (the shape `COLUMNS` and
    `IN_FIELDS` use), and an f-string all fall outside this scan on purpose. See
    the docstring on the test below for what that leaves uncovered.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = []
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if (
            isinstance(target, ast.Name)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            found.append((target.id, node.value.value))
    return found


# Common English function words. Their presence, alongside four or more alphabetic
# words, is what separates a sentence or two of prose from a machine token: every
# constant already on ENGINE_OWNED_ENGLISH contains at least one, and every short
# token this project actually uses (`"knowledge"`, `"video_title"`, `", "`)
# contains none, simply for lack of the word count to hold one.
_ENGLISH_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "to",
        "of",
        "in",
        "on",
        "for",
        "with",
        "by",
        "that",
        "this",
        "it",
        "as",
        "or",
        "be",
        "has",
        "have",
        "not",
        "no",
        "your",
        "you",
    }
)


def _reads_like_operator_prose(text: str) -> bool:
    """A cheap, deliberately approximate stand-in for "a human reads this".

    Not a parser and not proof, in either direction: it can be fooled by a long
    enough run of technical words with no stopword among them, and it cannot tell
    rendered text from a comment that never leaves the source file, which is
    exactly why EXCUSED_STRING_CONSTANTS below exists and has to be read by a
    person rather than generated.
    """
    words = [word for word in re.findall(r"[A-Za-z]+", text) if len(word) >= 2]
    if len(words) < 4:
        return False
    return any(word.lower() in _ENGLISH_STOPWORDS for word in words)


# Constants the heuristic above flags as prose-shaped but that are not operator
# visible English in the sense the limits table promises to enumerate. Every entry
# here needs its own comment saying why: an entry added with no comment is not a
# fix, it is the hole this test exists to close reopening under a different name.
EXCUSED_STRING_CONSTANTS = {
    # CSS. Its two English sentences are comments for whoever reads
    # review_html.py next, never text a browser renders, so no operator ever sees
    # them; docs/limits.md documents what a reader of the review page sees, and
    # this string does not reach that page as text.
    ("commentdesk.render.review_html", "STYLE"),
}


def test_a_new_operator_visible_string_constant_cannot_hide_from_the_limits_list():
    """The parametrized test above only ever checks the names someone remembered
    to put in ENGINE_OWNED_ENGLISH, so it is structurally incapable of noticing a
    ninth constant nobody listed. This test does not start from that list: it
    walks every module under src/ itself and applies the same two checks to
    whatever it finds there.

    What this catches: a new module-level `NAME = "a sentence or two"` added
    anywhere under src/commentdesk, in the specific shape every current entry on
    the limits table already has, that is neither named in ENGINE_OWNED_ENGLISH
    (and therefore in docs/limits.md, which the test above enforces) nor listed in
    EXCUSED_STRING_CONSTANTS with a reason.

    What this does NOT catch, and cannot without becoming a much larger project:
    English assembled at runtime rather than held as one literal (f-strings,
    str.join, concatenation, argparse help text built inline in cli.py); English
    held in a list or tuple of strings instead of a bare string constant (the
    shape COLUMNS and IN_FIELDS use); English nested inside a function or class
    body rather than sitting at module level; and prose short enough, or plain
    enough of stopwords, to slip past _reads_like_operator_prose. Anything that
    slips through by one of those routes still needs a human reader to catch it,
    the same way this project's own gap around ui.py's _PAGE was caught: by
    someone reading the code next to the claim, not by this test.
    """
    offenders = []
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        module_name = _module_dotted_name(path)
        for name, value in _module_level_string_constants(path):
            if not _reads_like_operator_prose(value):
                continue
            key = (module_name, name)
            if key in ENGINE_OWNED_ENGLISH or key in EXCUSED_STRING_CONSTANTS:
                continue
            offenders.append(key)
    assert offenders == [], (
        "a module-level string constant reads like operator-visible English but is "
        f"neither on the limits.md table nor excused with a reason: {offenders}. "
        "Add it to docs/limits.md and ENGINE_OWNED_ENGLISH above, or, if it truly "
        "never reaches an operator as text, to EXCUSED_STRING_CONSTANTS with a "
        "comment saying why."
    )


def test_community_files_exist_and_state_the_hard_rules():
    contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    # These four are the rules a well-meaning pull request breaks by accident.
    for rule in ("non-ascii", "no posting path", "data_collection", "em dash"):
        assert rule in contributing.lower(), f"CONTRIBUTING.md omits: {rule}"
    assert "make check" in contributing

    # A bare `"@" in text` passed on any at-sign anywhere in the file, including one
    # inside a decorator in a fenced code block. The point of both assertions is that
    # somebody reachable is named, so the handle is what is checked.
    contact = "@Ab-Romia"

    security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    assert "Security Advisories" in security
    assert contact in security, "SECURITY.md needs a fallback contact"
    assert "loopback" in security, "SECURITY.md must describe what keeps the ui local"

    conduct = (ROOT / "CODE_OF_CONDUCT.md").read_text(encoding="utf-8")
    assert "Contributor Covenant" in conduct
    assert contact in conduct, "CODE_OF_CONDUCT.md needs an enforcement contact"


# The claims the README is not allowed to make, kept in one place and enforced over
# the docs as well as over the README. test_readme.py enforced them against README.md
# only: the eight documents were clean by care, and nothing kept them so.
#
# `bot_disclosure_text` survives the `\bbots?\b` pattern because `_` is a word
# character, so `\b` does not match between `bot` and `_disclosure`. That is correct
# and deliberate: the setting name is an identifier, not a claim. Do not "fix" the
# pattern to catch it.
FORBIDDEN_CLAIMS = [
    r"\bbots?\b",
    r"\bauto-?repl(y|ies)\b",
    r"\bengagement\b",
    r"\bgrowth\b",
    r"\bautonomous(ly)?\b",
    r"\bguardrails?\b",
    r"\bcheapest\b",
    r"integrat",
]


@pytest.mark.parametrize("path", sorted(DOCS.glob("*.md")), ids=lambda p: p.name)
def test_a_doc_makes_no_claim_the_project_cannot_support(path):
    lower = path.read_text(encoding="utf-8").lower()
    hits = [pattern for pattern in FORBIDDEN_CLAIMS if re.search(pattern, lower)]
    assert hits == [], f"{path.name} uses forbidden claim language: {hits}"
