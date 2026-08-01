# SPDX-License-Identifier: Apache-2.0
"""Style rules that can be decided from a reply string alone.

Anything that needs the comment being answered, or the rest of the run, does not
belong here. Plug frequency is the example: it is a property of a whole run and
is reported by report.py rather than fixed one reply at a time.
"""

from __future__ import annotations

import re
import unicodedata

# The em dash and the en dash, with any whitespace on either side. Written as
# escapes so that no string literal in this package holds a non-ASCII character.
# The regex engine expands them, so the pattern still matches the real marks.
DASHES = re.compile(r"\s*[\u2014\u2013]\s*")

# Runs of spaces only. A reply may be deliberately written on two lines, and the
# line break is the operator's formatting rather than a style defect.
SPACE_RUN = re.compile(r" {2,}")


def sanitize_reply(text: str, separator: str, banned_emoji: str) -> str:
    """Apply the style bans that need no context beyond the reply itself.

    The separator comes from config. It is not inferred from the reply. An
    earlier version of this code counted characters to guess which script the
    reply was written in and sent every script it did not measure down the same
    default branch, so a reply in a third script received punctuation belonging
    to none of them. That is the exact failure this function exists to prevent,
    so the guess is gone and the value is configured.

    banned_emoji is read as a set of single characters, which is what the config
    field holds.
    """
    if not text:
        return ""
    # A lambda, not the separator itself: re.sub reads a replacement string as a
    # template, so a backslash in an operator supplied value would be expanded as
    # a group reference instead of inserted.
    out = DASHES.sub(lambda _match: separator, text)
    # Emoji removal runs before the space collapse on purpose. Dropping an emoji
    # that had a space on each side leaves two spaces behind.
    for emoji in banned_emoji:
        out = out.replace(emoji, "")
    return SPACE_RUN.sub(" ", out).strip()


def _core(word: str) -> str:
    """Strip punctuation from both ends of a word, by Unicode category.

    An earlier version stripped a hand written list of punctuation marks, which
    made the list correct for one script and incomplete for every other, and it
    was missing the ASCII question mark besides. Unicode category P covers every
    punctuation mark in every script, so a closing word normalises the same way
    whatever the reply is written in. That claim carries one overreach: category
    P also covers the ASCII apostrophe and the typographic right single quote,
    and in languages that write a word final glottal stop with one of those
    marks as a stand in, the letter is stripped along with it. The correct
    letter for that sound, U+02BB, is category Lm and is not touched. In
    find_repetition's use this only pushes two different words toward sharing a
    key, which biases toward false positive clustering rather than a missed
    repeat, so it does not weaken the guarantee the function exists for.
    """
    start, end = 0, len(word)
    while start < end and unicodedata.category(word[start]).startswith("P"):
        start += 1
    while end > start and unicodedata.category(word[end - 1]).startswith("P"):
        end -= 1
    return word[start:end]


def find_repetition(rows: list[dict], min_repeats: int = 3) -> list[str]:
    """Flag opening and closing words reused across a run.

    This is the one style rule a prompt structurally cannot enforce. "Do not end
    three replies the same way" is a claim about the whole set, and the model
    answers one comment at a time with no memory of the others, so nothing
    upstream can see it. That makes this function the only backstop for the rule
    in a script written with spaces between words: a false negative here has no
    safety net and the run ships with the repetition in it. It reports for a
    person to break up. It never rewrites anything.

    The backstop does not reach a script written without spaces between words,
    such as Japanese, Chinese or Thai. Tokenizing is whitespace only, so a reply
    in one of those scripts is a single token regardless of how many words it
    holds, falls under the two word minimum below, and never enters either
    bucket, however many replies in the run share the same ending. Seeing into
    that would need a word segmentation library, which this project does not
    take on as a dependency; the gap is a known and documented limit rather than
    a defect this function is meant to close. See docs/limits.md.
    """
    openings: dict[str, list[str]] = {}
    closings: dict[str, list[str]] = {}
    for row in rows:
        words = (row.get("reply") or "").split()
        # A one word reply is its own opening and its own closing, and counting it
        # in both buckets reports the same fact twice. This is also the branch a
        # spaceless script always takes: see the docstring above.
        if len(words) < 2:
            continue
        row_id = str(row.get("id", ""))
        first, last = _core(words[0]), _core(words[-1])
        # A word that was nothing but punctuation normalises to empty and is not a
        # word anyone can be asked to vary.
        if first:
            openings.setdefault(first, []).append(row_id)
        if last:
            closings.setdefault(last, []).append(row_id)
    flags: list[str] = []
    for label, groups in (("opening", openings), ("closing", closings)):
        for word, ids in sorted(groups.items()):
            if len(ids) >= min_repeats:
                flags.append(f"{label} {word!r} repeats in rows {', '.join(ids)}")
    return flags


def is_plug(reply: str, markers: list[str]) -> bool:
    """Does this reply point at the thing being sold?

    Approximate by design. It is a case insensitive substring test, so a reply
    that happens to contain a marker for an unrelated reason is counted. That is
    accurate enough to notice a run drifting into advertising and it is not
    accurate enough to quote as a figure, so the report says how many replies
    matched and claims nothing more.

    The markers come from config. Hardcoding them made this answer False for
    every reply under any other configuration, which reported a clean run instead
    of an unmeasured one. Config validation now refuses an empty list, so the
    silent version of this function cannot be configured into existence.
    """
    if not reply:
        return False
    lowered = reply.lower()
    return any(marker.lower() in lowered for marker in markers if marker)
