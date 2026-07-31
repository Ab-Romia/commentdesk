# SPDX-License-Identifier: Apache-2.0
"""The shipped example products are part of the contract, so they are tested."""

import tomllib
from pathlib import Path

import pytest

from commentdesk.config import load_config
from commentdesk.engine import IN_FIELDS, read_comments

ROOT = Path(__file__).resolve().parents[1]
FIELD_GUIDE = ROOT / "examples" / "field-guide-book"

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


@pytest.mark.parametrize("relative", ["prompts/voice.md", "prompts/examples.md", "knowledge.md"])
def test_field_guide_operator_files_carry_no_em_dash(relative):
    """The tool strips em dashes out of replies, so the files that teach it how to
    write must not contain any either. Written as an escape so that this test file
    is itself free of the character it is looking for."""
    text = (FIELD_GUIDE / relative).read_text(encoding="utf-8")
    assert "\u2014" not in text, "em dash"
    assert "\u2013" not in text, "en dash"
