# SPDX-License-Identifier: Apache-2.0
"""The default knowledge source: plain text files on disk, no dependencies."""

from pathlib import Path

from . import read_utf8, register

SUFFIXES = (".md", ".txt")


@register("text")
def load_text(path: Path, options: dict) -> str:
    """A file gives its contents. A directory gives its .md and .txt children,
    sorted by name, each under a heading made from its filename.

    Sorted by name rather than by whatever order the filesystem returns: the
    concatenation lands in the cached prefix, so a run whose sections arrive in
    a different order than yesterday pays full uncached input price on every
    call of the run.

    Read through read_utf8 so a file in a legacy encoding is named in a SourceError
    rather than raising a UnicodeDecodeError past every handler in the CLI, which is
    the rule docs/sources.md gives handler authors and this handler has to keep too.

    options is the whole [knowledge] table. This handler needs nothing from it,
    but the registry passes it so that a handler with settings of its own can
    read them without a second config section.
    """
    if path.is_dir():
        parts: list[str] = []
        for child in sorted(path.iterdir(), key=lambda item: item.name):
            if child.is_file() and child.suffix.lower() in SUFFIXES:
                parts.append(f"\n\n## {child.stem}\n\n")
                parts.append(read_utf8(child))
        return "".join(parts)
    return read_utf8(path)
