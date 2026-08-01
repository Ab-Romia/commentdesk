# SPDX-License-Identifier: Apache-2.0
"""Behaviour of the reply level style rules."""

import re

import pytest

from commentdraft.config import ConfigError, load_config
from commentdraft.sanitize import sanitize_reply

SEP = ", "
# The three smiling faces the example config bans. Written as escapes so the file
# reads the same in any editor.
EMOJI = "\U0001f642\U0001f643\U0001f60a"
MARKERS = ["example.com/field-guide", "link in bio"]


def test_em_and_en_dashes_become_the_configured_separator():
    assert sanitize_reply("Glad it helped — enjoy it", SEP, EMOJI) == ("Glad it helped, enjoy it")
    assert sanitize_reply("Glad it helped – enjoy it", SEP, EMOJI) == (  # noqa: RUF001
        "Glad it helped, enjoy it"
    )
    # No surrounding spaces, and a separator that is not a comma at all. The
    # separator is the operator's choice, so nothing may assume its shape.
    assert sanitize_reply("yes—no", " / ", EMOJI) == "yes / no"


def test_the_separator_is_inserted_literally_and_not_as_a_template():
    # re.sub treats a replacement string as a template, so a backslash in an
    # operator supplied separator would be expanded as a group reference.
    assert sanitize_reply("yes—no", "\\1", EMOJI) == "yes\\1no"


def test_a_hyphen_inside_a_url_is_left_alone():
    text = "you can get it at https://example.com/field-guide — it ships free"
    out = sanitize_reply(text, SEP, EMOJI)
    assert "https://example.com/field-guide" in out
    assert out == "you can get it at https://example.com/field-guide, it ships free"


def test_a_reply_that_is_only_banned_emoji_sanitizes_to_empty():
    assert sanitize_reply("  \U0001f642  \U0001f60a ", SEP, EMOJI) == ""
    assert sanitize_reply("", SEP, EMOJI) == ""
    assert sanitize_reply("   ", SEP, EMOJI) == ""


def test_removing_an_emoji_does_not_leave_a_double_space_behind():
    assert sanitize_reply("thanks \U0001f642 a lot", SEP, EMOJI) == "thanks a lot"
    # A deliberate line break is the operator's formatting, not a style defect.
    assert sanitize_reply("line one\nline two", SEP, EMOJI) == "line one\nline two"


def test_no_punctuation_from_another_script_is_introduced():
    """A Cyrillic reply and a Japanese reply.

    The deleted sniff measured two scripts and sent everything else down one
    default branch, which put an unrelated script's comma into replies written in
    a third. The check below is script agnostic: nothing may appear in the output
    that was not already in the input or in the configured separator.
    """
    cyrillic = "Спасибо — рад помочь"
    japanese = "ありがとう — お役に立てて嬉しい"
    for text in (cyrillic, japanese):
        out = sanitize_reply(text, SEP, EMOJI)
        assert set(out) <= set(text) | set(SEP), out
        assert "—" not in out
        assert "," in out


def test_find_repetition_sees_past_trailing_punctuation():
    """The exact case the old hand written strip list missed.

    Three English replies that end on the same word with three different marks.
    The old code stripped the full stop and the exclamation mark but not the
    ASCII question mark, so these three became two keys and nothing was flagged.
    """
    from commentdraft.sanitize import find_repetition

    rows = [
        {"id": "1", "reply": "That helps a lot, thank you"},
        {"id": "2", "reply": "Glad it landed, thank you!"},
        {"id": "3", "reply": "Did that answer it, thank you?"},
        {"id": "4", "reply": "Hope the weekend treats you well"},
    ]
    flags = find_repetition(rows)
    assert any(f.startswith("closing") and "'you'" in f and "1, 2, 3" in f for f in flags), flags


def test_two_repeats_are_normal_variation():
    from commentdraft.sanitize import find_repetition

    rows = [
        {"id": "1", "reply": "Thank you kindly"},
        {"id": "2", "reply": "Thank you again"},
    ]
    assert find_repetition(rows) == []
    # ...and the threshold is a parameter, so a stricter run can ask for two.
    assert find_repetition(rows, min_repeats=2)


def test_repetition_is_found_across_non_ascii_punctuation():
    """An ideographic full stop, a fullwidth exclamation mark, and no mark at all
    must all normalise to the same closing word.

    This exercises punctuation category stripping across scripts, nothing more.
    The space before the closing word in each reply below is artificial: real
    Japanese carries no space between words, and it is inserted here only so the
    whitespace tokenizer sees two tokens instead of one. It is not a claim that
    find_repetition detects repetition in naturally written Japanese; it does
    not, see test_repetition_is_invisible_in_a_language_without_word_spaces.
    """
    from commentdraft.sanitize import find_repetition

    rows = [
        {"id": "1", "reply": "お役に立てて 嬉しい。"},
        {"id": "2", "reply": "読んでくれて 嬉しい！"},  # noqa: RUF001
        {"id": "3", "reply": "そう言ってもらえて 嬉しい"},
    ]
    flags = find_repetition(rows)
    assert any(f.startswith("closing") and "1, 2, 3" in f for f in flags), flags


def test_repetition_is_invisible_in_a_language_without_word_spaces():
    """Known limit, not a bug: whitespace tokenizing cannot see into a script
    written without spaces between words.

    Naturally written Japanese carries no space between words, so the whole
    reply below is one token. find_repetition requires at least two tokens
    before a reply enters either bucket, so three identical replies, repeated
    on purpose to make the case as strong as possible, produce no flag at all.
    Seeing into this would need a word segmentation library, which this project
    does not take on as a dependency. The gap is documented in docs/limits.md
    rather than fixed here; this test pins the behavior so it stays visible
    instead of being mistaken for coverage the function does not have.
    """
    from commentdraft.sanitize import find_repetition

    rows = [
        {"id": "1", "reply": "お役に立てて嬉しいです"},
        {"id": "2", "reply": "お役に立てて嬉しいです"},
        {"id": "3", "reply": "お役に立てて嬉しいです"},
    ]
    assert find_repetition(rows) == []


def test_leading_punctuation_does_not_split_an_opening():
    from commentdraft.sanitize import find_repetition

    rows = [
        {"id": "1", "reply": '"Glad you asked, here it is'},
        {"id": "2", "reply": "Glad that helped, take care"},
        {"id": "3", "reply": "(Glad to hear it) all the best"},
    ]
    flags = find_repetition(rows)
    assert any(f.startswith("opening") and "'Glad'" in f and "1, 2, 3" in f for f in flags), flags


def test_one_word_replies_are_not_counted_at_both_ends():
    """A single word is its own opening and its own closing, and counting it twice
    would report the same fact as two separate flags."""
    from commentdraft.sanitize import find_repetition

    rows = [{"id": str(i), "reply": "Thanks"} for i in range(1, 6)]
    assert find_repetition(rows) == []


def test_find_repetition_tolerates_rows_without_a_reply():
    from commentdraft.sanitize import find_repetition

    rows = [{"id": "1"}, {"id": "2", "reply": None}, {"id": "3", "reply": ""}]
    assert find_repetition(rows) == []


def test_is_plug_matches_configured_markers_case_insensitively():
    from commentdraft.sanitize import is_plug

    assert is_plug("you can get it at https://example.com/field-guide", MARKERS)
    assert is_plug("Link In Bio", MARKERS)
    assert is_plug("LINK IN BIO if you want it", MARKERS)


def test_is_plug_is_false_when_no_configured_marker_appears():
    """A run reports clean only when it is clean.

    The count is approximate by design, so this test pins the direction that
    matters: markers that are absent must not be conjured, and an empty reply is
    never a plug.
    """
    from commentdraft.sanitize import is_plug

    assert not is_plug("Sleep on it and see how you feel tomorrow", MARKERS)
    assert not is_plug("", MARKERS)
    assert not is_plug("", [])


def test_empty_plug_markers_cannot_be_configured(tmp_path, repo_root):
    """The silently unmeasurable state is closed off by config, not by luck.

    In the source project the markers were hardcoded to one product's strings, so
    under any other configuration is_plug answered False on every reply, the report
    printed a clean zero, and plug_cap could never fire. A failure that looks like
    success is worse than a crash, so an empty marker list is a load error.

    This copies the real config.toml shipped with the field guide example rather
    than a stand-in fixture, so the shipped example is the thing under test. That
    config keeps plug_markers on one line and says so in a comment, for the same
    reason this test does: the substitution below depends on it, and asserting the
    match count is what turns a silent reformat into a loud test failure instead of
    a test that quietly stops testing anything.
    """
    from commentdraft.sanitize import is_plug

    real_config = repo_root / "examples" / "field-guide-book" / "config.toml"
    config_path = tmp_path / "config.toml"
    config_path.write_text(real_config.read_text(encoding="utf-8"), encoding="utf-8")

    # The shipped example is the control: it loads, and its markers are real.
    markers = load_config(config_path)["behavior"]["plug_markers"]
    assert markers
    assert any(is_plug(f"see {m} for more", markers) for m in markers)

    raw = config_path.read_text(encoding="utf-8")
    broken, count = re.subn(r"(?m)^plug_markers\s*=.*$", "plug_markers = []", raw)
    assert count == 1, (
        "substitution matched nothing, so this test would pass without testing "
        "anything. The shipped config keeps plug_markers on one line; if that "
        "changes, update this pattern."
    )
    config_path.write_text(broken, encoding="utf-8")

    with pytest.raises(ConfigError) as excinfo:
        load_config(config_path)
    assert "plug_markers" in str(excinfo.value)
