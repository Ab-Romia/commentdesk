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


# Imported for the side effect of registering the built in handler. The import
# sits at the bottom because the module above defines the decorator it uses, and
# the name is unused on purpose.
from . import text  # noqa: E402, F401
