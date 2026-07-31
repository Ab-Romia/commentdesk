# SPDX-License-Identifier: Apache-2.0
"""Knowledge intake registry.

A knowledge source turns one configured path into one string. That string is the
whole grounding for a run: it is the only thing the model may state as fact, and
it lives in the cached prefix, so it is read exactly once per run and never
varies between rows.

Adding a source is one module and one register call. Nothing else in the package
needs to learn the new name.
"""

from collections.abc import Callable
from pathlib import Path

from commentdesk.config import resolve_path


class SourceError(Exception):
    pass


SOURCES: dict[str, Callable[[Path, dict], str]] = {}


def read_utf8(path: Path) -> str:
    """The file's text, or a SourceError naming the file and what to do about it.

    Lives here rather than in one handler because docs/sources.md makes it a rule for
    every handler: raise SourceError, with the path in the message. A document
    exported from a desktop word processor on a Windows machine arrives in a legacy
    single byte encoding, and that is the likeliest mistake anyone makes with this
    tool. It is the operator's own document, it is hit before a single token is
    spent, and it is hit again on every retry while they are setting up. Read as
    utf-8 it raises UnicodeDecodeError, which is a ValueError rather than an
    OSError, so it passed straight through the caller's handler and printed a
    traceback that cli.py's own module docstring promises never to print. The
    comments CSV four lines away already answered this properly; this is the same
    answer for everything the knowledge registry reads.

    utf-8-sig so a byte order mark left by a desktop editor is dropped instead of
    becoming the first character of the prompt.
    """
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SourceError(
            f"{path} is not valid UTF-8 ({exc.reason} at byte {exc.start}). "
            "Save it as UTF-8 and try again."
        ) from exc


def register(name: str) -> Callable[[Callable], Callable]:
    """Bind a handler to the name operators write in [knowledge].source."""

    def decorator(handler: Callable) -> Callable:
        if name in SOURCES:
            # Two handlers under one name means the operator gets whichever
            # module happened to import last. That depends on import order
            # rather than on anything they wrote, so refuse instead.
            raise SourceError(f"knowledge source already registered: {name}")
        SOURCES[name] = handler
        return handler

    return decorator


def load_knowledge(cfg: dict, config_dir: Path) -> str:
    """Read the configured knowledge document and hand back its full text.

    The whole document goes into the prompt. There is no chunking and no vector
    store, which is the right answer while the source fits the context window
    and is documented as a limit rather than hidden.
    """
    knowledge = cfg.get("knowledge") or {}
    name = knowledge.get("source", "text")
    handler = SOURCES.get(name)
    if handler is None:
        raise SourceError(
            f"unknown knowledge source: {name}. registered: " + ", ".join(sorted(SOURCES))
        )
    rel = knowledge.get("path")
    if not rel:
        raise SourceError("knowledge.path is not set")
    path = resolve_path(config_dir, rel)
    if not path.exists():
        raise SourceError(f"knowledge path not found: {path}")
    # A copy, so a handler cannot reach back into the loaded config.
    document = handler(path, dict(knowledge))
    if not document.strip():
        # An empty knowledge document produces a run in which every factual
        # claim is ungrounded, and no later stage can detect that. Stop here,
        # before the first token is spent.
        raise SourceError(f"knowledge source returned empty text: {path}")
    return document


# Imported for the side effect of registering the built in handlers. The import
# sits at the bottom because the module above defines the decorator they use, and
# the names are unused on purpose.
from . import pdf_vision, text  # noqa: E402,F401  imported for the side effect of registering
