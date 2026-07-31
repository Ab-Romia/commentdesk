# SPDX-License-Identifier: Apache-2.0
"""The shipped example products are part of the contract, so they are tested."""

import tomllib
from pathlib import Path

import pytest

from commentdesk.config import load_config
from commentdesk.engine import IN_FIELDS, read_comments
from commentdesk.prompt import KNOWLEDGE_TAG, render_system_text
from commentdesk.sources import load_knowledge

ROOT = Path(__file__).resolve().parents[1]
FIELD_GUIDE = ROOT / "examples" / "field-guide-book"
SOURDOUGH = ROOT / "examples" / "sourdough-course"
EXAMPLES = {"field-guide-book": FIELD_GUIDE, "sourdough-course": SOURDOUGH}


def non_blank_lines(path):
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


REQUIRED_CATEGORIES = {
    "content_question",
    "purchase_intent",
    "price_objection",
    "praise",
    "provocation",
    "non_english",
    "no_author",
    "empty_comment",
    "bot_question",
    "escalation_unhappy_buyer",
    "escalation_piracy",
}


def read_categories(directory):
    with open(directory / "categories.toml", "rb") as handle:
        return tomllib.load(handle)["categories"]


def test_field_guide_ships_all_six_files():
    for relative in (
        "config.toml",
        "knowledge.md",
        "prompts/voice.md",
        "prompts/examples.md",
        "comments.csv",
        "categories.toml",
    ):
        assert (FIELD_GUIDE / relative).is_file(), f"missing {relative}"


def test_field_guide_config_loads_and_names_its_own_files():
    cfg = load_config(FIELD_GUIDE / "config.toml")
    assert cfg["product"]["name"]
    assert cfg["product"]["kind"]
    assert cfg["behavior"]["max_reply_sentences"] >= 1
    assert cfg["behavior"]["bot_disclosure_text"].strip()
    assert cfg["behavior"]["plug_markers"]
    # cta_mode must name a table that exists in this very file
    assert cfg["behavior"]["cta_mode"] in cfg["cta"]
    for relative in (cfg["knowledge"]["path"], cfg["voice"]["rules"], cfg["voice"]["examples"]):
        assert (FIELD_GUIDE / relative).is_file(), f"config points at missing {relative}"


def test_field_guide_comments_read_with_the_expected_columns():
    rows = read_comments(FIELD_GUIDE / "comments.csv")
    assert 24 <= len(rows) <= 32
    for row in rows:
        assert set(IN_FIELDS) <= set(row)
    ids = [row["id"] for row in rows]
    assert len(set(ids)) == len(ids), "duplicate row ids"


def test_field_guide_categories_cover_every_row_and_every_intent():
    """Coverage is asserted by intent, never by literal comment text.

    A category that names a row id which is not in the CSV, or a row that no
    category claims, is the failure this catches: both mean the manifest and the
    data have drifted and the coverage claim is no longer true.
    """
    categories = read_categories(FIELD_GUIDE)
    rows = read_comments(FIELD_GUIDE / "comments.csv")
    row_ids = {row["id"] for row in rows}

    missing = REQUIRED_CATEGORIES - set(categories)
    assert not missing, f"categories.toml is missing {sorted(missing)}"

    claimed = set()
    for name, ids in categories.items():
        assert ids, f"category {name} is empty"
        as_text = {str(i) for i in ids}
        unknown = as_text - row_ids
        assert not unknown, f"category {name} names rows not in the CSV: {sorted(unknown)}"
        claimed |= as_text
    unclaimed = row_ids - claimed
    assert not unclaimed, f"rows in no category: {sorted(unclaimed)}"


def test_field_guide_covers_both_an_english_and_a_non_english_comment():
    categories = read_categories(FIELD_GUIDE)
    rows = read_comments(FIELD_GUIDE / "comments.csv")
    other_language = {str(i) for i in categories["non_english"]}
    assert other_language, "no comment in another language"
    assert {row["id"] for row in rows} - other_language, "no comment in the product language"


def test_field_guide_empty_comment_row_is_actually_empty():
    categories = read_categories(FIELD_GUIDE)
    rows = {row["id"]: row for row in read_comments(FIELD_GUIDE / "comments.csv")}
    for row_id in categories["empty_comment"]:
        assert rows[str(row_id)]["comment"] == ""
    for row_id in categories["no_author"]:
        assert rows[str(row_id)]["author"] == ""
        assert rows[str(row_id)]["comment"] != ""


@pytest.mark.parametrize("name", sorted(EXAMPLES))
@pytest.mark.parametrize("relative", ["prompts/voice.md", "prompts/examples.md", "knowledge.md"])
def test_example_operator_files_carry_no_em_dash(relative, name):
    """The tool strips em dashes out of replies, so the files that teach it how to
    write must not contain any either. Written as an escape so that this test file
    is itself free of the character it is looking for.

    Parametrized over every shipped example, not only the field guide, so a third
    product added later is covered automatically without anyone remembering to
    extend this test by hand.
    """
    directory = EXAMPLES[name]
    text = (directory / relative).read_text(encoding="utf-8")
    assert "\u2014" not in text, "em dash"
    assert "\u2013" not in text, "en dash"


@pytest.mark.parametrize("name", sorted(EXAMPLES))
def test_example_renders_a_prompt_with_no_unresolved_placeholders(name):
    directory = EXAMPLES[name]
    cfg = load_config(directory / "config.toml")
    text = render_system_text(cfg, directory)
    assert "{{" not in text and "}}" not in text, "a placeholder survived substitution"
    assert cfg["product"]["name"] in text
    assert cfg["product"]["price_text"] in text
    assert cfg["behavior"]["bot_disclosure_text"] in text
    assert str(cfg["behavior"]["max_reply_sentences"]) in text
    # the grounding rule in the voice file must point at the tag the engine emits
    assert f"<{KNOWLEDGE_TAG}>" in text


@pytest.mark.parametrize("name", sorted(EXAMPLES))
def test_example_knowledge_loads_and_is_substantial(name):
    directory = EXAMPLES[name]
    cfg = load_config(directory / "config.toml")
    knowledge = load_knowledge(cfg, directory)
    assert len(knowledge.split()) > 200


def test_the_two_examples_do_not_bleed_into_each_other():
    book = load_config(FIELD_GUIDE / "config.toml")
    course = load_config(SOURDOUGH / "config.toml")
    assert book["product"]["kind"] != course["product"]["kind"]
    assert book["behavior"]["cta_mode"] != course["behavior"]["cta_mode"]
    assert book["product"]["price_text"] != course["product"]["price_text"]
    assert book["behavior"]["max_reply_sentences"] != course["behavior"]["max_reply_sentences"]
    course_text = render_system_text(course, SOURDOUGH)
    assert book["product"]["name"] not in course_text


def test_the_course_voice_file_is_visibly_shorter():
    """The long rule set is a choice, not a requirement, and this is the proof.

    If the second example ever grows to match the first, the claim that an operator
    can start small stops being demonstrated anywhere in the repo.
    """
    book = non_blank_lines(FIELD_GUIDE / "prompts" / "voice.md")
    course = non_blank_lines(SOURDOUGH / "prompts" / "voice.md")
    assert len(course) * 2 < len(book)


def test_sourdough_categories_cover_every_row():
    categories = read_categories(SOURDOUGH)
    row_ids = {row["id"] for row in read_comments(SOURDOUGH / "comments.csv")}
    claimed = set()
    for name, ids in categories.items():
        assert ids, f"category {name} is empty"
        as_text = {str(i) for i in ids}
        assert not as_text - row_ids, f"category {name} names rows not in the CSV"
        claimed |= as_text
    assert not row_ids - claimed, "rows in no category"
