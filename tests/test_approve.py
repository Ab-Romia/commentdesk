# SPDX-License-Identifier: Apache-2.0
"""The approval gate, driven by scripted keystrokes against a connector that
records what it was asked to do and reaches nothing.

Every test here drives the real loop. Nothing is mocked away: the prompt is a
parameter with a real default, so a test can hand it a list of keys, and the
connector is a parameter, so a test can hand it something that counts calls. That
is the whole reason those two are parameters.

What is being pinned is the shape of the consent, not the shape of the output.
One keystroke, one reply, one call, in that order, and no route to a call that
does not start with a person pressing a key that is not the one under a resting
finger.
"""

import json
from pathlib import Path

import pytest

from commentdraft.approve import (
    EDIT_KEY,
    QUIT_KEY,
    SEND_KEY,
    SKIP_KEY,
    EditorError,
    approve_and_publish,
)


class Recorder:
    """A connector that records calls and reaches nothing.

    `fails` makes publish_reply raise, which is how the tests reach the branch a
    real rate limit or a rejected token takes.
    """

    def __init__(self, fails: bool = False) -> None:
        self.calls: list[tuple] = []
        self.fails = fails

    def fetch_comments(self, config: dict, since: str) -> list[dict]:
        self.calls.append(("fetch_comments", since))
        return []

    def publish_reply(self, config: dict, parent_id: str, text: str) -> str:
        self.calls.append(("publish_reply", parent_id, text))
        if self.fails:
            raise RuntimeError("the platform said no")
        return "published-" + parent_id

    @property
    def sends(self) -> list[tuple]:
        return [call for call in self.calls if call[0] == "publish_reply"]


class Keys:
    """A scripted reviewer. Raises EOFError once the script runs out, which is
    what a real terminal does at Ctrl+D and what stops a broken loop from
    hanging the suite instead of failing it."""

    def __init__(self, *pressed: str) -> None:
        self.pressed = list(pressed)
        self.reads = 0

    def __call__(self) -> str:
        self.reads += 1
        if not self.pressed:
            raise EOFError
        return self.pressed.pop(0)


def row(identifier: str, reply: str, decision: str = "reply", platform: str = "video-site"):
    return {
        "id": identifier,
        "platform": platform,
        "author": "sam",
        "comment": "how much is it",
        "post_title": "foraging clip",
        "decision": decision,
        "reason": "asks the price",
        "reply": reply,
    }


class Out:
    """A writable stream that keeps what was written."""

    def __init__(self) -> None:
        self.chunks: list[str] = []

    def write(self, text: str) -> int:
        self.chunks.append(text)
        return len(text)

    def flush(self) -> None:
        return None

    @property
    def text(self) -> str:
        return "".join(self.chunks)


def run(rows, keys, platform, tmp_path, **kwargs):
    out = Out()
    counts = approve_and_publish(
        rows,
        {"product": {"name": "the guide"}},
        platform,
        platform_name="video-site",
        config_label="config.toml",
        log_path=tmp_path / "out" / "published.jsonl",
        read_key=keys,
        out=out,
        now=lambda: "2026-08-01T12:00:00Z",
        **kwargs,
    )
    return counts, out


def log_lines(tmp_path) -> list[dict]:
    path = tmp_path / "out" / "published.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


# --- the send ---------------------------------------------------------------


def test_the_send_key_publishes_that_one_reply_and_nothing_else(tmp_path):
    platform = Recorder()
    rows = [row("c1", "eighteen dollars"), row("c2", "yes it does")]
    counts, _ = run(rows, Keys(SEND_KEY, SKIP_KEY), platform, tmp_path)

    assert platform.sends == [("publish_reply", "c1", "eighteen dollars")]
    assert counts["sent"] == 1
    assert counts["skipped"] == 1


def test_two_approvals_are_two_calls_in_the_order_they_were_approved(tmp_path):
    """Approval is per reply, not per run. YouTube III.E.3.d asks for express
    consent prior to each action, so two actions is two consents and two calls."""
    platform = Recorder()
    rows = [row("c1", "first"), row("c2", "second")]
    run(rows, Keys(SEND_KEY, SEND_KEY), platform, tmp_path)

    assert platform.sends == [
        ("publish_reply", "c1", "first"),
        ("publish_reply", "c2", "second"),
    ]


def test_skip_sends_nothing_and_records_nothing(tmp_path):
    platform = Recorder()
    counts, _ = run([row("c1", "eighteen dollars")], Keys(SKIP_KEY), platform, tmp_path)

    assert platform.calls == []
    assert log_lines(tmp_path) == []
    assert counts["skipped"] == 1


def test_quit_stops_and_leaves_everything_after_it_untouched(tmp_path):
    """Everything already sent stays sent. Everything else is not offered again
    and is not marked as anything, because the reviewer made no decision on it."""
    platform = Recorder()
    rows = [row("c1", "first"), row("c2", "second"), row("c3", "third")]
    counts, _ = run(rows, Keys(SEND_KEY, QUIT_KEY), platform, tmp_path)

    assert platform.sends == [("publish_reply", "c1", "first")]
    assert counts["sent"] == 1
    assert len(log_lines(tmp_path)) == 1


def test_end_of_input_stops_the_same_way_quit_does(tmp_path):
    """A terminal at Ctrl+D, and a caller whose stdin ran out. Neither is consent
    to send the rest, and neither may loop forever asking."""
    platform = Recorder()
    rows = [row("c1", "first"), row("c2", "second")]
    counts, _ = run(rows, Keys(), platform, tmp_path)

    assert platform.calls == []
    assert counts["sent"] == 0


# --- the key that does nothing ----------------------------------------------


def test_enter_alone_advances_nothing_and_sends_nothing(tmp_path):
    """The one that matters. There is no default action, so a reviewer holding a
    key cannot walk the queue: the queue does not move until one of four named
    keys arrives, and the key that sends is not the one under a resting finger."""
    platform = Recorder()
    rows = [row("c1", "first"), row("c2", "second")]
    keys = Keys("", "", "", QUIT_KEY)
    counts, out = run(rows, keys, platform, tmp_path)

    assert platform.calls == []
    assert counts["sent"] == 0
    # Still on the first reply after three presses of Enter.
    assert out.text.count("[ 1 / 2 ]") == 1
    assert "[ 2 / 2 ]" not in out.text
    assert keys.reads == 4


@pytest.mark.parametrize("pressed", ["\n", " ", "Y ES", "n", "1", "yes please", "\t"])
def test_a_key_that_is_not_one_of_the_four_does_nothing(tmp_path, pressed):
    platform = Recorder()
    counts, out = run([row("c1", "first")], Keys(pressed, QUIT_KEY), platform, tmp_path)

    assert platform.calls == []
    assert counts["sent"] == 0
    assert out.text.count("[ 1 / 1 ]") == 1


@pytest.mark.parametrize("pressed", ["Y", " y ", "y\n"])
def test_the_send_key_is_read_past_the_whitespace_and_the_shift_key(tmp_path, pressed):
    """A reviewer who typed it is a reviewer who meant it. Caps lock is not a
    different intention, and neither is a trailing space."""
    platform = Recorder()
    run([row("c1", "first")], Keys(pressed), platform, tmp_path)

    assert platform.sends == [("publish_reply", "c1", "first")]


# --- the edit ---------------------------------------------------------------


def test_edit_sends_what_came_back_and_records_that_it_was_edited(tmp_path):
    platform = Recorder()
    counts, _ = run(
        [row("c1", "eighteen dollars")],
        Keys(EDIT_KEY),
        platform,
        tmp_path,
        edit=lambda text: "it is eighteen dollars, link in the description",
    )

    assert platform.sends == [
        ("publish_reply", "c1", "it is eighteen dollars, link in the description")
    ]
    assert counts["sent"] == 1
    assert log_lines(tmp_path)[0]["edited"] is True


def test_an_edit_that_changed_nothing_is_recorded_as_unedited(tmp_path):
    """The record answers "did a person change this before it went out". An
    editor opened and closed is a person who read it and let it stand."""
    platform = Recorder()
    run(
        [row("c1", "eighteen dollars")],
        Keys(EDIT_KEY),
        platform,
        tmp_path,
        edit=lambda text: text + "\n",
    )

    assert log_lines(tmp_path)[0]["edited"] is False


def test_an_edit_that_comes_back_empty_sends_nothing_and_asks_again(tmp_path):
    """Emptying the buffer is the ordinary way to abandon an edit in every editor
    anyone uses. It has to mean "not this one", never "send whatever is left"."""
    platform = Recorder()
    counts, out = run(
        [row("c1", "eighteen dollars")],
        Keys(EDIT_KEY, SKIP_KEY),
        platform,
        tmp_path,
        edit=lambda text: "   \n",
    )

    assert platform.calls == []
    assert counts["skipped"] == 1
    assert "empty" in out.text.lower()


def test_an_editor_that_will_not_start_reports_it_and_asks_again(tmp_path):
    def broken(text: str) -> str:
        raise EditorError("no $EDITOR is set")

    platform = Recorder()
    counts, out = run(
        [row("c1", "eighteen dollars")], Keys(EDIT_KEY, SKIP_KEY), platform, tmp_path, edit=broken
    )

    assert platform.calls == []
    assert counts["skipped"] == 1
    assert "EDITOR" in out.text


# --- the record -------------------------------------------------------------


def test_every_send_appends_one_line_carrying_the_id_the_platform_returned(tmp_path):
    """Without this an operator cannot answer a complaint about something their
    own account posted, which is a normal thing to be asked."""
    platform = Recorder()
    run([row("c1", "eighteen dollars")], Keys(SEND_KEY), platform, tmp_path)

    (entry,) = log_lines(tmp_path)
    assert entry == {
        "at": "2026-08-01T12:00:00Z",
        "platform": "video-site",
        "parent_id": "c1",
        "published_id": "published-c1",
        "text": "eighteen dollars",
        "edited": False,
        "config": "config.toml",
    }


def test_the_record_is_append_only_across_runs(tmp_path):
    platform = Recorder()
    run([row("c1", "first")], Keys(SEND_KEY), platform, tmp_path)
    run([row("c2", "second")], Keys(SEND_KEY), platform, tmp_path)

    assert [entry["parent_id"] for entry in log_lines(tmp_path)] == ["c1", "c2"]


def test_nothing_is_recorded_when_the_platform_refused(tmp_path):
    """The line is written after the platform confirms, carrying the id it
    returned. A line written before the call would claim a post that never
    happened, which is worse than no record at all."""
    platform = Recorder(fails=True)
    counts, out = run([row("c1", "first")], Keys(SEND_KEY, QUIT_KEY), platform, tmp_path)

    assert len(platform.sends) == 1
    assert log_lines(tmp_path) == []
    assert counts["failed"] == 1
    assert counts["sent"] == 0
    assert "the platform said no" in out.text


def test_a_failed_send_does_not_lose_the_rest_of_the_queue(tmp_path):
    platform = Recorder(fails=True)
    rows = [row("c1", "first"), row("c2", "second")]
    counts, _ = run(rows, Keys(SEND_KEY, SKIP_KEY), platform, tmp_path)

    assert counts["failed"] == 1
    assert counts["skipped"] == 1


# --- what is offered --------------------------------------------------------


@pytest.mark.parametrize("decision", ["skip", "escalate", "error", ""])
def test_only_rows_decided_reply_are_ever_offered(tmp_path, decision):
    platform = Recorder()
    rows = [row("c1", "", decision=decision)]
    counts, out = run(rows, Keys(), platform, tmp_path)

    assert counts["offered"] == 0
    assert platform.calls == []
    assert "c1" not in out.text


def test_a_row_for_another_platform_is_held_back_and_said_out_loud(tmp_path):
    """Silently dropping it is the failure mode that matters here: a reviewer who
    approved twelve replies and saw sixteen on the review page has to be told why,
    or they will assume the other four went out."""
    platform = Recorder()
    rows = [row("c1", "first"), row("c2", "second", platform="photo-site")]
    counts, out = run(rows, Keys(SEND_KEY), platform, tmp_path)

    assert counts["offered"] == 1
    assert counts["held"] == 1
    assert platform.sends == [("publish_reply", "c1", "first")]
    assert "photo-site" in out.text


def test_a_row_with_no_platform_column_is_offered(tmp_path):
    """A comments CSV assembled by hand may carry no platform at all, and the
    operator running publish has already named the one platform in their config."""
    platform = Recorder()
    counts, _ = run([row("c1", "first", platform="")], Keys(SEND_KEY), platform, tmp_path)

    assert counts["offered"] == 1


def test_an_empty_queue_says_so_and_asks_for_nothing(tmp_path):
    platform = Recorder()
    keys = Keys()
    counts, out = run([row("c1", "", decision="skip")], keys, platform, tmp_path)

    assert counts["offered"] == 0
    assert keys.reads == 0
    assert "nothing" in out.text.lower()


# --- the dry run ------------------------------------------------------------


def test_dry_run_issues_no_call_and_asks_for_no_key(tmp_path):
    """The point is that a person can read what a platform is about to receive
    before granting any write scope at all, so it must need neither a keystroke
    nor a credential to run."""
    platform = Recorder()
    # Holding the send key down. A dry run that read it would be a dry run that
    # sends the first time somebody pipes anything into this subcommand.
    keys = Keys(SEND_KEY, SEND_KEY)
    rows = [row("c1", "first"), row("c2", "second")]
    counts, out = run(rows, keys, platform, tmp_path, dry_run=True)

    assert platform.calls == []
    assert keys.reads == 0
    assert counts["sent"] == 0
    assert "first" in out.text
    assert "second" in out.text
    assert "c1" in out.text


def test_dry_run_writes_no_record(tmp_path):
    platform = Recorder()
    run([row("c1", "first")], Keys(), platform, tmp_path, dry_run=True)

    assert not (tmp_path / "out" / "published.jsonl").exists()


def test_dry_run_names_the_platform_it_would_reach(tmp_path):
    platform = Recorder()
    _, out = run([row("c1", "first")], Keys(), platform, tmp_path, dry_run=True)

    assert "video-site" in out.text


# --- what the reviewer is shown ---------------------------------------------


def test_the_reviewer_sees_the_comment_the_draft_and_where_it_would_go(tmp_path):
    platform = Recorder()
    _, out = run([row("c1", "eighteen dollars")], Keys(QUIT_KEY), platform, tmp_path)
    text = out.text

    assert "how much is it" in text
    assert "eighteen dollars" in text
    assert "video-site" in text
    assert "c1" in text
    assert "foraging clip" in text
    for key in (SEND_KEY, EDIT_KEY, SKIP_KEY, QUIT_KEY):
        assert f"({key})" in text


def test_the_log_directory_is_created_when_it_is_missing(tmp_path):
    platform = Recorder()
    target = tmp_path / "deep" / "deeper" / "published.jsonl"
    approve_and_publish(
        [row("c1", "first")],
        {},
        platform,
        platform_name="video-site",
        config_label="config.toml",
        log_path=target,
        read_key=Keys(SEND_KEY),
        out=Out(),
    )
    assert Path(target).exists()


def test_a_send_that_cannot_be_written_down_is_said_out_loud_rather_than_raised(tmp_path):
    """The reply is already on the platform by the time the record is written.

    Raising here would end the run with a traceback over a send that did happen,
    take the rest of the queue with it, and leave the operator unable to say
    which of the earlier sends were written either. The line is printed in the
    form it would have taken on disk instead, so it can be kept by hand.
    """
    platform = Recorder()
    blocked = tmp_path / "out"
    blocked.write_text("this is a file, not a directory", encoding="utf-8")

    out = Out()
    counts = approve_and_publish(
        [row("c1", "eighteen dollars")],
        {},
        platform,
        platform_name="video-site",
        config_label="config.toml",
        log_path=blocked / "published.jsonl",
        read_key=Keys(SEND_KEY),
        out=out,
        now=lambda: "2026-08-01T12:00:00Z",
    )

    assert platform.sends == [("publish_reply", "c1", "eighteen dollars")]
    assert counts["sent"] == 1
    assert counts["unrecorded"] == 1
    assert '"published_id": "published-c1"' in out.text
