# SPDX-License-Identifier: Apache-2.0
"""The default knowledge source: plain text files on disk, no dependencies."""

from pathlib import Path

from . import register

SUFFIXES = (".md", ".txt")


@register("text")
def load_text(path: Path, options: dict) -> str:
    """A file gives its contents. A directory gives its .md and .txt children,
    sorted by name, each under a heading made from its filename.

    Sorted by name rather than by whatever order the filesystem returns: the
    concatenation lands in the cached prefix, so a run whose sections arrive in
    a different order than yesterday pays full uncached input price on every
    call of the run.

    Read as utf-8-sig so a byte order mark left by a desktop editor is dropped
    instead of becoming the first character of the prompt.

    options is the whole [knowledge] table. This handler needs nothing from it,
    but the registry passes it so that a handler with settings of its own can
    read them without a second config section.
    """
    if path.is_dir():
        parts: list[str] = []
        for child in sorted(path.iterdir(), key=lambda item: item.name):
            if child.is_file() and child.suffix.lower() in SUFFIXES:
                parts.append(f"\n\n## {child.stem}\n\n")
                parts.append(child.read_text(encoding="utf-8-sig"))
        return "".join(parts)
    return path.read_text(encoding="utf-8-sig")
