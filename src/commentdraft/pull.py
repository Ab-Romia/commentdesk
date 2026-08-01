# SPDX-License-Identifier: Apache-2.0
"""What a pull remembers, so that pulling twice does not draft twice.

A pull is a read, and a read is safe to repeat. Drafting is not: every comment
that reaches `commentdraft run` costs a model call, and every draft that reaches
`commentdraft publish` costs a person a keystroke and offers somebody the same
reply twice. So the expensive half of the loop has to be able to tell a comment
it has already seen from one it has not, and an operator running this on a
schedule must not have to do that with a notebook.

The memory is a small JSON file the operator points at with --state, holding the
platform it was written for, the marker the last pull was given, and the id of
every comment the platform has handed over while that file has existed. A row
whose id is in that set is left out of the CSV. That is the whole mechanism, and
it is deliberately by id rather than by time:

  - it is exact. A time marker is inclusive at its own boundary, so resuming from
    the newest timestamp seen hands back the comment that set it, every run,
    forever. Nothing here has that problem.
  - it needs nothing from the row but its id. A connector returns exactly the
    five columns the engine reads, and a sixth carrying a timestamp would be a
    column every consumer downstream would have to learn to ignore.
  - it is the same mechanism for every platform, including the ones whose ids
    sort in no useful order and whose cursors are opaque.

What it costs is one line per comment ever pulled. Twenty thousand comments is a
few hundred kilobytes of ids, which is a file, not a database, and it prunes
itself only in the sense that an operator can delete it and start again.

The time marker is still carried, because it is what keeps the platform side
cheap: --since narrows what the connector asks the platform for at all, and the
state file remembers the last one so it does not have to be retyped. It is
opaque here. Only the connector knows what one means.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# The three keys the state file holds. Named rather than spelled inline so that
# reading one and writing one cannot drift apart.
PLATFORM_FIELD = "platform"
SINCE_FIELD = "since"
SEEN_FIELD = "seen"

ID_FIELD = "id"


class PullError(Exception):
    """A state file that cannot be read, or that was written for another platform."""


@dataclass
class State:
    """What one state file says. Empty is what a first run gets."""

    platform: str = ""
    since: str = ""
    seen: set[str] = field(default_factory=set)


def load_state(path: str | Path | None, platform_name: str) -> State:
    """Read the state file, or hand back an empty state, or refuse to guess.

    No path at all, and a missing file, are both a first run rather than an
    error: an operator who names a file that does not exist yet is asking for one
    to be written, not reporting a problem. Anything else that cannot be read is
    refused rather than treated as a first run, because a state file quietly read
    as empty is a state file that silently re-pulls everything it was there to
    prevent.
    """
    if not path:
        return State()
    state_path = Path(path)
    if not state_path.exists():
        return State()
    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PullError(f"{state_path} is not readable as JSON: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise PullError(f"{state_path} is not valid UTF-8: {exc.reason}") from exc
    if not isinstance(raw, dict):
        raise PullError(f"{state_path} does not hold a JSON object")

    written_for = raw.get(PLATFORM_FIELD)
    if not isinstance(written_for, str) or not written_for:
        raise PullError(f"{state_path} does not say which platform it was written for")
    if written_for != platform_name:
        raise PullError(
            f"{state_path} remembers a pull from {written_for} and this config pulls "
            f"from {platform_name}. One state file per platform: point --state at a "
            "different one, or delete this file to start that platform over."
        )

    since = raw.get(SINCE_FIELD, "")
    if not isinstance(since, str):
        raise PullError(f"{state_path} holds a {SINCE_FIELD} that is not a string")
    seen = raw.get(SEEN_FIELD, [])
    if not isinstance(seen, list) or any(not isinstance(item, str) for item in seen):
        raise PullError(f"{state_path} holds a {SEEN_FIELD} that is not a list of ids")
    return State(platform=written_for, since=since, seen=set(seen))


def unseen(rows: list[dict], state: State) -> list[dict]:
    """The rows this state file has not seen before, in the order they arrived.

    A repeat inside one batch is dropped too. A platform that lists the same
    comment under two posts is not a shape this connector produces today, and it
    is not worth drafting twice if one ever does.

    A row with no id is kept every time. There is nothing to remember it by, so
    the choice is between a duplicate and a comment nobody ever answers, and the
    second one is worse. docs/configuration.md says so where an operator reads it.
    """
    fresh: list[dict] = []
    within: set[str] = set()
    for row in rows:
        identifier = str(row.get(ID_FIELD, "") or "")
        if identifier and (identifier in state.seen or identifier in within):
            continue
        if identifier:
            within.add(identifier)
        fresh.append(row)
    return fresh


def remember(state: State, platform_name: str, since: str, rows: list[dict]) -> State:
    """The state after a pull: every id the platform handed back, kept or dropped.

    Kept or dropped is the load bearing half. Recording only what was written to
    the CSV would forget a row the moment it was suppressed once, and the run
    after that would write it again.
    """
    seen = set(state.seen)
    for row in rows:
        identifier = str(row.get(ID_FIELD, "") or "")
        if identifier:
            seen.add(identifier)
    return State(platform=platform_name, since=since, seen=seen)


def save_state(path: str | Path, state: State) -> None:
    """Write the state file, creating the directory it sits in if it is missing.

    Sorted, so that two runs that saw the same comments produce the same file and
    a diff of it is readable. Written whole rather than appended to: it is a
    picture of what has been pulled, not a log of pulls.
    """
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    body = {
        PLATFORM_FIELD: state.platform,
        SINCE_FIELD: state.since,
        SEEN_FIELD: sorted(state.seen),
    }
    state_path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
