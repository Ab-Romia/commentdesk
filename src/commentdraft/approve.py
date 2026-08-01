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

Three things that sound like details and are not, each of them a way a keystroke
was once counted as consent to something nobody had read:

1. The key is read from the terminal, after the terminal's own input queue has
   been discarded. A line read with input() comes out of a buffer that already
   holds whatever was typed or pasted while the reply was still being written to
   the screen, so a paste delivered before the first reply rendered was a send
   per line in it. See _from_the_terminal.
2. What is displayed is what is sent, as one string rather than two that happen
   to agree. Reply text is model output derived from a stranger's comment, and a
   terminal acts on some of the characters a stranger can type: an escape
   sequence can hide half a reply from the reviewer and leave the whole of it in
   the payload. See _plain.
3. The gate checks its own preconditions. A credential and a terminal are what
   make this a person approving a reply rather than a script answering a prompt,
   and a check that lives in the caller is a check the next caller skips. See
   _preconditions.

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
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from commentdraft.platforms import Platform, publish_target

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

# The fields of a row that a reviewer reads on the way to a decision. Every one of
# them is turned into printable text before it reaches either the screen or an
# Approval, because a row is untrusted from end to end: a comment that ends in an
# escape sequence can hide the reply printed under it just as easily as a reply
# can hide its own second half.
DISPLAY_FIELDS = ("id", "platform", "comment", "post_title", "reply")

# The Unicode general categories a terminal does not print as themselves. Cc is the
# control characters, ESC among them. Cf is the format characters, which includes
# the bidirectional overrides that reorder a line without changing a byte of it. Cs
# is the surrogates, which cannot be encoded at all and would fail at the moment of
# the send rather than here.
HIDDEN_CATEGORIES = frozenset({"Cc", "Cf", "Cs"})


class EditorError(Exception):
    """$EDITOR is unset, or it did not come back with anything usable."""


class GateError(Exception):
    """A precondition of the gate is not met, so nothing is offered at all.

    Raised rather than returned because there is no partial version of this: a run
    that cannot ask a person to approve anything has nothing useful to do with the
    queue, and a caller that ignored a return value would publish anyway.
    """


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


def at_a_keyboard() -> bool:
    """True when there is a person at the other end of this process's stdin.

    `yes | commentdraft publish` is the exact failure the four keys were chosen
    to prevent, and a pipe answers a prompt faster than any finger can. Nothing
    at the far end of a redirect can read a reply, so nothing there can approve
    one, and the refusal belongs before the first row rather than after the
    fortieth send.
    """
    return sys.stdin.isatty()


# The keystroke seam, and the seal on it.
#
# The suite has to drive this loop with a scripted reviewer, because the loop is
# the product and a gate whose only test replaces the prompt is a gate nobody has
# tested. What is not acceptable is the seam being reachable from installed code.
# It used to be a public keyword parameter, and approve_and_publish(...,
# read_key=lambda: "y") is one line in any script that imports this package and
# sends the entire queue with no terminal and no credential.
#
# So it is a private module attribute that is honoured only while a test runner is
# in the process. pytest is a development dependency: it is not installed beside
# the tool, and an installed caller cannot satisfy the second half of the
# condition without deliberately shipping one. tests/test_guarantees.py asserts
# that no module under src/ but this one so much as names it.
_scripted_keys: Callable[[], str] | None = None
_TEST_RUNNER = "pytest"


def _key_source() -> Callable[[], str] | None:
    """The suite's scripted reviewer, when the suite is what is running."""
    if _TEST_RUNNER not in sys.modules:
        return None
    return _scripted_keys


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
    platform: Platform | None,
    *,
    platform_name: str,
    config_label: str,
    log_path: str | Path,
    dry_run: bool = False,
    out: Writer | None = None,
    edit: Callable[[str], str] = edit_in_editor,
    now: Callable[[], str] = _utc_now,
) -> dict[str, int]:
    """Walk the drafted replies one at a time and send only what is approved.

    Raises GateError before anything is offered when the two things that make a
    keystroke mean anything are missing: a publish credential in the environment,
    and a person at the terminal. Both are checked here rather than only in the
    command that calls this, because a check in the caller is a check the next
    caller skips, and this function is importable by anyone.

    `platform` may be None for a dry run and only for one. A dry run reaches no
    connector, so it should not need one to exist, and building one in order to
    print what would be sent runs a connector's constructor during the one command
    documented as asking for no credential and no keystroke.

    out, edit and now are parameters with real defaults so that a test can drive
    this entire loop against a connector that records calls. The keystroke is not
    among them any more: it comes from the terminal, or from the seam above, which
    only the suite that owns this repository can reach.

    `out` defaults to None rather than to sys.stdout in the signature: a default
    evaluated at import time captures whichever stream was installed then, which
    is not the one a caller under test capture is writing to.
    """
    stream = _stream(out)
    counts = {"offered": 0, "sent": 0, "skipped": 0, "failed": 0, "held": 0, "unrecorded": 0}
    scripted = _key_source()
    _preconditions(cfg, config_label, dry_run=dry_run, scripted=scripted)
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

    connector = _connector(platform)
    ledger = _Ledger(Path(log_path), platform_name, config_label, now, stream)
    for index, item in enumerate(queue, start=1):
        _show(stream, index, len(queue), platform_name, item)
        # Both come out of the queue already reduced to printable text, which is
        # the form they were shown in. The reviewer approves a string, not a row.
        parent_id = item["id"]
        drafted = item["reply"]
        while True:
            pressed = _press(stream, scripted)
            if pressed == QUIT_KEY:
                # Everything already sent stays sent. Everything else is untouched.
                _summary(stream, counts)
                return counts
            if pressed == SKIP_KEY:
                counts["skipped"] += 1
                break
            if pressed == SEND_KEY:
                _send_approved(connector, cfg, Approval(parent_id, drafted, False), ledger, counts)
                break
            if pressed == EDIT_KEY:
                try:
                    # Reduced the same way the draft was. What comes back out of an
                    # editor is a stranger's text a reviewer has been looking at,
                    # and the record and the payload have to be the string that was
                    # read rather than whatever bytes were in the buffer.
                    revised = _plain(edit(drafted))
                except EditorError as exc:
                    _line(stream, f"  {exc}")
                    continue
                if not revised:
                    # Emptying the buffer is how every editor anyone uses says
                    # "forget it". It cannot mean "send whatever is left".
                    _line(stream, "  the draft came back empty, so nothing was sent")
                    continue
                _send_approved(
                    connector,
                    cfg,
                    Approval(parent_id, revised, revised != drafted),
                    ledger,
                    counts,
                )
                break
            # No else, and nothing after this line inside the loop. There is no
            # default action: an unrecognised key, Enter included, falls off the
            # bottom of the chain and asks again without moving the queue.
    _summary(stream, counts)
    return counts


def _stream(out: Writer | None) -> Writer:
    """The stream the reviewer reads, resolved when the run starts.

    A separate function because the loop above may not carry a conditional
    expression: `a if b else c` is an else by another spelling, and the test that
    bans an else in the prompt loop bans this too rather than leaving a hole the
    exact width of one line.
    """
    if out is None:
        return sys.stdout
    return out


def _connector(platform: Platform | None) -> Platform:
    """The connector the send will reach, or a refusal before the first prompt.

    Reached only past the dry run return above, so None here is a caller that
    asked for real sends without providing anything to send with. Refusing at the
    top of the run rather than at the first keystroke keeps the failure away from
    the moment a person has just approved something.
    """
    if platform is None:
        raise GateError("publish has no connector to send with, so nothing can be approved")
    return platform


def _preconditions(
    cfg: dict, config_label: str, *, dry_run: bool, scripted: Callable[[], str] | None
) -> None:
    """The two facts the gate does not take a caller's word for.

    Both of these used to live in cmd_publish, which meant the promise was a
    property of one command rather than of this function. Any script that imports
    this package calls it directly, and with the checks upstream it published a
    whole queue with stdin at /dev/null and no credential in the environment.

    A dry run is exempt because it reaches no platform and is documented as
    needing neither. The scripted seam is exempt because it is the suite driving
    the loop, and the checks it skips have tests of their own that do not use it.
    """
    if dry_run or scripted is not None:
        return
    _, credential_env = publish_target(cfg)
    if not os.environ.get(credential_env):
        raise GateError(
            f"missing env var(s): {credential_env} (put them in .env next to {config_label})"
        )
    if not at_a_keyboard():
        raise GateError(
            "publish needs a terminal: every reply is approved one keystroke at a time, "
            "and a pipe or a redirect cannot read a reply. Run it from a terminal, or "
            "use --dry-run to see what would be sent."
        )


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
    counts["sent"] += 1
    line = _entry(ledger, approval, published_id)
    try:
        _record(ledger, line)
    except OSError as exc:
        # The reply is already on the platform, so raising here would end the run
        # with a traceback over a send that did happen, and take the rest of the
        # queue with it. The line is printed instead, in the form it would have
        # taken on disk, so the operator can keep it by hand.
        counts["unrecorded"] += 1
        _line(ledger.stream, f"  sent, but {ledger.log_path} could not be written: {exc}")
        _line(ledger.stream, f"  keep this line: {line}")
        return
    _line(ledger.stream, f"  sent, and the platform called it {published_id}")


def _entry(ledger: _Ledger, approval: Approval, published_id: str) -> str:
    """One audit line, built once so its timestamp is read once."""
    return json.dumps(
        {
            "at": ledger.now(),
            "platform": ledger.platform_name,
            "parent_id": approval.parent_id,
            "published_id": published_id,
            "text": approval.text,
            "edited": approval.edited,
            "config": ledger.config_label,
        },
        ensure_ascii=False,
    )


def _record(ledger: _Ledger, line: str) -> None:
    """Append one line to the audit file, after the fact, never before.

    Append only, and never read back by this tool. Without it an operator cannot
    answer a complaint about something their own account posted, which is a
    normal thing to be asked and an embarrassing thing to be unable to answer.
    """
    ledger.log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(ledger.log_path, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")


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
    for row in rows:
        if (row.get("decision") or "").strip() != REPLY_DECISION:
            continue
        # Reduced here, once, rather than at each place a field is printed. The
        # queue is what the loop reads, what _show prints and what an Approval
        # carries, so reducing it at the door is what makes those three the same
        # text instead of three readings of the same row.
        item = _readable(row)
        row_platform = item["platform"]
        if row_platform and row_platform.casefold() != wanted:
            counts["held"] += 1
            _line(
                stream,
                f"  not offered: {item['id']} came from {row_platform}, "
                f"and this config publishes to {platform_name}",
            )
            continue
        queue.append(item)
    return queue


def _readable(row: dict) -> dict:
    """A copy of the row whose displayed fields are exactly what a terminal shows."""
    return {**row, **{field: _plain(row.get(field) or "") for field in DISPLAY_FIELDS}}


def _plain(value: str) -> str:
    """One line of printable text, which is the only form this module handles.

    A reply is model output derived from a stranger's comment, so it can carry
    anything a stranger can type, and a terminal acts on some of that rather than
    printing it. `ESC [ 8 m` stops a terminal showing what follows until it is
    turned off again, so a reply whose visible half is a sentence about chapter
    three can carry an invisible second half that goes out with it: the reviewer
    reads one thing and the platform receives another, and every word of the
    consent claim above is false for that reply.

    Escaping it at the display layer alone would not fix that, because then the
    displayed string and the sent string are two strings that agree until somebody
    edits one of them. So the text is reduced once, on the way into the queue, and
    the same string is what is printed, what an Approval carries, what the
    connector is handed and what the audit line records.

    Whitespace is collapsed for the same reason: the display has always folded a
    reply onto one line, and showing a flat version of something while sending a
    version with line breaks in it is the same divergence in a milder form.
    """
    return "".join(_printable(char) for char in " ".join(value.split()))


def _printable(char: str) -> str:
    """One character as itself, or as the escape a person can read."""
    if unicodedata.category(char) not in HIDDEN_CATEGORIES:
        return char
    if ord(char) < 0x100:
        return f"\\x{ord(char):02x}"
    if ord(char) < 0x10000:
        return f"\\u{ord(char):04x}"
    return f"\\U{ord(char):08x}"


def _press(stream: Writer, scripted: Callable[[], str] | None) -> str:
    """Show the four keys and return whichever one was pressed.

    End of input is read as quit rather than as anything else: a caller whose
    stdin ran out has not consented to the rest of the queue, and a loop that
    kept asking would spin forever against a closed pipe.
    """
    try:
        return _read_one(stream, scripted).strip().casefold()
    except EOFError:
        return QUIT_KEY


def _read_one(stream: Writer, scripted: Callable[[], str] | None) -> str:
    if scripted is None:
        return _from_the_terminal(stream)
    _line(stream, PROMPT)
    return scripted()


def _from_the_terminal(stream: Writer) -> str:
    """Print the prompt, discard what was typed before it, and read one key.

    The order is the whole of it. A line read with input() is popped off the
    terminal's own input queue, and that queue already holds everything typed or
    pasted while the reply was still being written to the screen. Five approvals
    delivered a second before the first reply rendered were five sends, none of
    them on screen when the key that approved it arrived, and no pipe, no flag and
    no source edit anywhere in it. The keystroke proved a key was pressed; it
    never proved the reply had been readable when it was.

    So the queue is discarded at the moment the prompt becomes readable, and
    exactly one byte is read after that, in cbreak mode, where a key needs no
    Enter behind it and cannot be joined to the key behind it either.

    The flush is not decoration. CPython's input() flushes stdout before it reads,
    and a replacement that does not would leave the prompt sitting in a buffer
    whenever output is piped, which is a reviewer approving a blank screen.

    The terminal is restored in a finally, so a connector that raises, a Ctrl-C,
    or a traceback from anywhere below cannot hand the operator back a shell with
    no echo and no line editing.
    """
    try:
        import termios
        import tty
    except ImportError as exc:  # pragma: no cover - POSIX only
        raise GateError(
            "publish needs a POSIX terminal: the approval keystroke is read from the "
            "terminal itself, and this platform has no termios. Use --dry-run to see "
            "what would be sent."
        ) from exc

    _line(stream, PROMPT)
    _flush(stream)
    try:
        descriptor = sys.stdin.fileno()
        saved = termios.tcgetattr(descriptor)
    except (OSError, ValueError, termios.error) as exc:
        raise GateError(
            "publish needs a terminal: every reply is approved one keystroke at a time, "
            "and this process's stdin is not one."
        ) from exc
    try:
        termios.tcflush(descriptor, termios.TCIFLUSH)
        tty.setcbreak(descriptor)
        pressed = os.read(descriptor, 1)
    finally:
        termios.tcsetattr(descriptor, termios.TCSADRAIN, saved)
    if not pressed:
        raise EOFError
    return pressed.decode("utf-8", "replace")


def _flush(stream: Writer) -> None:
    """Push the prompt out before anything waits on a key.

    Writer is deliberately narrower than a file object, so this asks rather than
    assumes. A stream with nothing to flush is a test double, and a test double
    that never buffered anything has nothing to lose here.
    """
    flush = getattr(stream, "flush", None)
    if callable(flush):
        flush()


def _show(stream: Writer, index: int, total: int, platform_name: str, item: dict) -> None:
    """The original comment, the drafted reply, and where it would go.

    Every value printed here came through _readable, so nothing on this screen can
    turn the rest of it off.
    """
    title = item["post_title"]
    context = f' on "{title}"' if title else ""
    _line(stream, "")
    _line(stream, f"  [ {index} / {total} ]  {platform_name}  {item['id']}{context}")
    _line(stream, "")
    _field(stream, "comment", item["comment"])
    _field(stream, "reply", item["reply"])
    _line(stream, "")


def _preview(stream: Writer, platform_name: str, item: dict) -> None:
    """What the send would hand the connector, and the fact that it did not."""
    _line(stream, f"  would call {platform_name}")
    _line(stream, f"    parent_id   {item['id']}")
    _line(stream, f"    text        {item['reply']}")
    _line(stream, "  dry run, so nothing was sent")


def _field(stream: Writer, label: str, value: str) -> None:
    """One labelled field, wrapped to the width, and nothing else done to it.

    The whitespace collapsing that used to live here has moved into _plain, which
    runs before the value reaches either this function or an Approval. Reducing
    the text for display only was the divergence: it left the escape characters in
    both copies and folded the whitespace in one of them.
    """
    head = f"  {label:<10}"
    body = textwrap.fill(value, width=WIDTH, initial_indent=head, subsequent_indent=" " * len(head))
    _line(stream, body or head)


def _summary(stream: Writer, counts: dict[str, int]) -> None:
    _line(stream, "")
    _line(
        stream,
        f"  sent {counts['sent']}, skipped {counts['skipped']}, "
        f"failed {counts['failed']}, not offered {counts['held']}, "
        f"unrecorded {counts['unrecorded']}",
    )


def _line(stream: Writer, text: str) -> None:
    print(text, file=stream)
