# SPDX-License-Identifier: Apache-2.0
"""The approval gate. One reply, one keystroke, one call, in that order.

This module is the whole of the promise the project makes about publishing:
nothing reaches a platform that a person did not read and approve first. It is
the only module in the package that calls publish_reply, and every call it makes
sits lexically inside the branch of the prompt loop that an explicit keystroke
reaches. tests/test_guarantees.py walks the AST of every module and fails the
build on any other arrangement.

Why it is built this way rather than more conveniently:

YouTube API Services Developer Policies III.E.3.d requires that a client
"clearly identify any actions that they take to insert, share, update, or delete
data or content on the authorizing user's behalf", and that "the user must
expressly consent to those actions prior to their actual execution." Meta's
Developer Policies say the same in section 1.7. Read literally, consent has to be
express, so it cannot be inferred from a setting; prior to execution, so it
cannot be a report afterwards; and attached to those actions, enumerated, so one
grant cannot cover a batch. A person seeing one specific reply and acting is the
only thing that satisfies all three.

So there is no way to say yes to more than one reply at a time. There is no flag,
no config key, and no default that changes that. Not defaulted off. Absent. A
flag that exists is a flag somebody sets once and forgets, and the whole claim
collapses the first time it is set on a machine nobody is watching.

Publishing thirty replies costs thirty keystrokes. That is the design.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import tempfile
import textwrap
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from commentdraft.platforms import Platform

# The four keys, and nothing else. `y` is not under a resting finger and Enter is
# not one of them, which together are what stop a held key from walking the queue.
SEND_KEY = "y"
EDIT_KEY = "e"
SKIP_KEY = "s"
QUIT_KEY = "q"

# Only rows the engine decided this way are ever offered. A row decided skip or
# escalate carries no draft, and a row decided error carries a failure.
REPLY_DECISION = "reply"

# Built from the constants above rather than typed out, so a key renamed in one
# place cannot leave the line a reviewer reads describing the old one.
PROMPT = f"  ({SEND_KEY}) send   ({EDIT_KEY}) edit   ({SKIP_KEY}) skip   ({QUIT_KEY}) quit"

WIDTH = 78


class EditorError(Exception):
    """$EDITOR is unset, or it did not come back with anything usable."""


class Writer(Protocol):
    """Just enough of a stream for print(file=...).

    Narrower than TextIO on purpose: the output stream is a parameter so a test
    can hand this loop something that records what a reviewer would have seen,
    and demanding a whole file object of a test double buys nothing.
    """

    def write(self, text: str, /) -> int: ...


@dataclass(frozen=True)
class Approval:
    """One person's express consent to send one specific reply.

    Frozen, and carrying the text rather than pointing at the row, because the
    text that was approved is the text that must be sent. A row re-read from disk
    between the keystroke and the call would be a different thing than the one
    the reviewer looked at.

    It is built at exactly two places in this package, both inside the branch of
    the prompt loop reached by an explicit keystroke, and tests/test_guarantees.py
    asserts that by walking the AST. Nothing stops a future caller constructing
    one out of thin air; what stops it is that test failing when they do.
    """

    parent_id: str
    text: str
    edited: bool


@dataclass(frozen=True)
class _Ledger:
    """The parts of a send that are the same for every row in one run."""

    log_path: Path
    platform_name: str
    config_label: str
    now: Callable[[], str]
    stream: Writer


def _utc_now() -> str:
    """The moment of the send, to the second, in UTC.

    An audit line answering "when did my account post this" is read next to a
    complaint that arrived in some other timezone, so it carries an offset that
    needs no interpretation.
    """
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def edit_in_editor(text: str) -> str:
    """Open the draft in $EDITOR and hand back whatever comes out.

    This matters more than it looks. A tool that makes editing harder than
    sending teaches people to send, so the edit path is one keystroke, exactly
    like the send path, and what comes back is what goes out.

    Every failure becomes an EditorError so the caller can say so and ask again,
    rather than losing the queue to a traceback because a variable was unset.
    """
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
    if not editor:
        raise EditorError("no $EDITOR is set, so there is nothing to open the draft in")
    descriptor, name = tempfile.mkstemp(suffix=".txt")
    path = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        subprocess.run([*shlex.split(editor), str(path)], check=True)
        return path.read_text(encoding="utf-8")
    except (OSError, subprocess.SubprocessError) as exc:
        raise EditorError(f"$EDITOR ({editor}) did not return a draft: {exc}") from exc
    finally:
        path.unlink(missing_ok=True)


def approve_and_publish(
    rows: Iterable[dict],
    cfg: dict,
    platform: Platform,
    *,
    platform_name: str,
    config_label: str,
    log_path: str | Path,
    dry_run: bool = False,
    read_key: Callable[[], str] = input,
    out: Writer | None = None,
    edit: Callable[[str], str] = edit_in_editor,
    now: Callable[[], str] = _utc_now,
) -> dict[str, int]:
    """Walk the drafted replies one at a time and send only what is approved.

    read_key, out, edit and now are parameters with real defaults so that a test
    can drive this entire loop with a scripted sequence of keystrokes against a
    connector that records calls, without mocking the prompt away. A gate whose
    only test replaces the prompt is a gate nobody has tested.

    `out` defaults to None rather than to sys.stdout in the signature: a default
    evaluated at import time captures whichever stream was installed then, which
    is not the one a caller under test capture is writing to.
    """
    stream: Writer = sys.stdout if out is None else out
    counts = {"offered": 0, "sent": 0, "skipped": 0, "failed": 0, "held": 0}
    queue = _queue(rows, platform_name, stream, counts)
    counts["offered"] = len(queue)
    if not queue:
        _line(stream, f"  nothing to publish: no row here is a drafted reply for {platform_name}")
        return counts

    if dry_run:
        # No keystroke and no credential. The point of a dry run is that a person
        # can read what a platform would receive before granting any write scope
        # at all, which means it has to run on a setup that could not send.
        for index, item in enumerate(queue, start=1):
            _show(stream, index, len(queue), platform_name, item)
            _preview(stream, platform_name, item)
        _summary(stream, counts)
        return counts

    ledger = _Ledger(Path(log_path), platform_name, config_label, now, stream)
    for index, item in enumerate(queue, start=1):
        _show(stream, index, len(queue), platform_name, item)
        parent_id = (item.get("id") or "").strip()
        drafted = (item.get("reply") or "").strip()
        while True:
            pressed = _press(stream, read_key)
            if pressed == QUIT_KEY:
                # Everything already sent stays sent. Everything else is untouched.
                _summary(stream, counts)
                return counts
            if pressed == SKIP_KEY:
                counts["skipped"] += 1
                break
            if pressed == SEND_KEY:
                _send_approved(platform, cfg, Approval(parent_id, drafted, False), ledger, counts)
                break
            if pressed == EDIT_KEY:
                try:
                    revised = edit(drafted).strip()
                except EditorError as exc:
                    _line(stream, f"  {exc}")
                    continue
                if not revised:
                    # Emptying the buffer is how every editor anyone uses says
                    # "forget it". It cannot mean "send whatever is left".
                    _line(stream, "  the draft came back empty, so nothing was sent")
                    continue
                _send_approved(
                    platform, cfg, Approval(parent_id, revised, revised != drafted), ledger, counts
                )
                break
            # No else, and nothing after this line inside the loop. There is no
            # default action: an unrecognised key, Enter included, falls off the
            # bottom of the chain and asks again without moving the queue.
    _summary(stream, counts)
    return counts


def _send_approved(
    platform: Platform,
    cfg: dict,
    approval: Approval,
    ledger: _Ledger,
    counts: dict[str, int],
) -> None:
    """The one place in this package that reaches a platform.

    It takes an Approval rather than a string. That is not decoration: it is what
    makes the two call sites above readable as what they are, one send per
    keystroke, and it is what tests/test_guarantees.py anchors on when it asserts
    that no route reaches a send without a value the prompt loop produced.

    The record is written after the platform confirms and carries the id the
    platform returned. A line written before the call would claim a post that may
    never have happened, which is worse than no record at all.
    """
    try:
        published_id = platform.publish_reply(cfg, approval.parent_id, approval.text)
    except Exception as exc:  # noqa: BLE001 - a connector may raise anything; one row must not lose the queue
        counts["failed"] += 1
        _line(ledger.stream, f"  not sent: {type(exc).__name__}: {exc}")
        return
    _record(ledger, approval, published_id)
    counts["sent"] += 1
    _line(ledger.stream, f"  sent, and the platform called it {published_id}")


def _record(ledger: _Ledger, approval: Approval, published_id: str) -> None:
    """Append one line to the audit file, after the fact, never before.

    Append only, and never read back by this tool. Without it an operator cannot
    answer a complaint about something their own account posted, which is a
    normal thing to be asked and an embarrassing thing to be unable to answer.
    """
    entry = {
        "at": ledger.now(),
        "platform": ledger.platform_name,
        "parent_id": approval.parent_id,
        "published_id": published_id,
        "text": approval.text,
        "edited": approval.edited,
        "config": ledger.config_label,
    }
    ledger.log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(ledger.log_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _queue(
    rows: Iterable[dict], platform_name: str, stream: Writer, counts: dict[str, int]
) -> list[dict]:
    """The rows this run will offer, and a line about each one it will not.

    A row for another platform is held back rather than sent through whichever
    connector happens to be configured. Saying so out loud is the point: a
    reviewer who approved twelve replies out of sixteen rows has to be told why
    the other four never appeared, or they will assume those went out too.
    """
    wanted = platform_name.strip().casefold()
    queue = []
    for item in rows:
        if (item.get("decision") or "").strip() != REPLY_DECISION:
            continue
        row_platform = (item.get("platform") or "").strip()
        if row_platform and row_platform.casefold() != wanted:
            counts["held"] += 1
            _line(
                stream,
                f"  not offered: {(item.get('id') or '').strip()} came from {row_platform}, "
                f"and this config publishes to {platform_name}",
            )
            continue
        queue.append(item)
    return queue


def _press(stream: Writer, read_key: Callable[[], str]) -> str:
    """Show the four keys and return whichever one was pressed.

    End of input is read as quit rather than as anything else: a caller whose
    stdin ran out has not consented to the rest of the queue, and a loop that
    kept asking would spin forever against a closed pipe.
    """
    _line(stream, PROMPT)
    try:
        return read_key().strip().casefold()
    except EOFError:
        return QUIT_KEY


def _show(stream: Writer, index: int, total: int, platform_name: str, item: dict) -> None:
    """The original comment, the drafted reply, and where it would go."""
    title = (item.get("post_title") or "").strip()
    context = f' on "{title}"' if title else ""
    _line(stream, "")
    _line(
        stream,
        f"  [ {index} / {total} ]  {platform_name}  {(item.get('id') or '').strip()}{context}",
    )
    _line(stream, "")
    _field(stream, "comment", item.get("comment") or "")
    _field(stream, "reply", item.get("reply") or "")
    _line(stream, "")


def _preview(stream: Writer, platform_name: str, item: dict) -> None:
    """What the send would hand the connector, and the fact that it did not."""
    _line(stream, f"  would call {platform_name}")
    _line(stream, f"    parent_id   {(item.get('id') or '').strip()}")
    _line(stream, f"    text        {(item.get('reply') or '').strip()}")
    _line(stream, "  dry run, so nothing was sent")


def _field(stream: Writer, label: str, value: str) -> None:
    head = f"  {label:<10}"
    flat = " ".join(value.split())
    body = textwrap.fill(flat, width=WIDTH, initial_indent=head, subsequent_indent=" " * len(head))
    _line(stream, body or head)


def _summary(stream: Writer, counts: dict[str, int]) -> None:
    _line(stream, "")
    _line(
        stream,
        f"  sent {counts['sent']}, skipped {counts['skipped']}, "
        f"failed {counts['failed']}, not offered {counts['held']}",
    )


def _line(stream: Writer, text: str) -> None:
    print(text, file=stream)
