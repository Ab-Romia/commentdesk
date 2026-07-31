# SPDX-License-Identifier: Apache-2.0
"""Style rules that can be decided from a reply string alone.

Anything that needs the comment being answered, or the rest of the run, does not
belong here. Plug frequency is the example: it is a property of a whole run and
is reported by report.py rather than fixed one reply at a time.
"""

from __future__ import annotations

import re

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
