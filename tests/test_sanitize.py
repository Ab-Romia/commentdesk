# SPDX-License-Identifier: Apache-2.0
"""Behaviour of the reply level style rules."""

from commentdesk.sanitize import sanitize_reply

SEP = ", "
# The three smiling faces the example config bans. Written as escapes so the file
# reads the same in any editor.
EMOJI = "\U0001f642\U0001f643\U0001f60a"


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
