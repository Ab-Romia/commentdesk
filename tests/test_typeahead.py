# SPDX-License-Identifier: Apache-2.0
"""Typeahead is not consent.

This is the only test in the suite that puts the gate in front of a real
terminal, because it is the only way to test the thing that was wrong. Under
pty.fork(), five approvals were written into the terminal a second and a half
before the child rendered its first row, and five replies were published. Not one
of them was on the screen when the key that approved it arrived. No pipe, no flag,
no config key, no monkeypatch and no source edit: on a real terminal the same
gesture is one paste.

The cause was that a line read with input() is popped off the terminal's own input
queue, and that queue holds everything typed while the reply was still being
written to the screen. The gate now discards that queue at the moment the prompt
becomes readable, and reads exactly one byte after it. What this test pins:

- keys delivered before the row was rendered approve nothing, and
- the row and the prompt are on the screen before anything waits for a key.

The second half is not decoration. The child's stdout is block buffered here on
purpose, which is what a piped run looks like. input() flushed stdout for free and
a replacement does not, so without an explicit flush the prompt would still be
sitting in a buffer while the gate waited, and the reviewer would be approving a
blank screen.

The child is a fresh interpreter rather than a forked copy of this process. It has
to be: pytest imports readline, and a forked child inherits the hook that puts
under input(), which handles the terminal itself and hides the very behaviour
being tested. A separate process is also the honest shape of the reproduction,
since it is what an operator's own process looks like.

Offline, keyless and self contained: the connector writes one line to a file in
tmp_path and reaches nothing.
"""

import contextlib
import os
import pty
import select
import sys
import time
from pathlib import Path

import pytest

import commentdraft

# How long the child waits before it renders anything. The approvals are written
# inside this window, so every one of them is in the terminal's queue before the
# first reply exists on the screen.
LEAD = 1.0
PAYLOAD = b"y\ny\ny\ny\ny\n"
ROWS = 5
PATIENCE = 20.0

pytestmark = pytest.mark.skipif(
    not hasattr(os, "fork") or not hasattr(pty, "fork"), reason="needs a POSIX pty"
)

# The whole of the child. It drives the real gate against the real terminal, with
# nothing in front of the prompt: no scripted keys, no patched predicate, no flag.
DRIVER = """\
import os
import sys
import time

sys.stdin = open(0, encoding="utf-8")
# Block buffered, which is what output through a pipe looks like. The prompt only
# reaches the screen if the gate flushes it before it waits for a key.
sys.stdout = open(1, "w", buffering=8192, encoding="utf-8")

record, log_path = sys.argv[1], sys.argv[2]
os.environ["CD_PUBLISH_TOKEN"] = "not-a-real-token"

from commentdraft.approve import approve_and_publish


class Connector:
    def fetch_comments(self, config, since):
        return []

    def publish_reply(self, config, parent_id, text):
        with open(record, "a", encoding="utf-8") as handle:
            handle.write(parent_id + "\\n")
        return "published-" + parent_id


rows = [
    {
        "id": "r" + str(index),
        "platform": "video-site",
        "comment": "how much is it",
        "post_title": "a clip",
        "decision": "reply",
        "reply": "draft " + str(index),
    }
    for index in range(1, __ROWS__ + 1)
]
cfg = {"publish": {"platform": "video-site", "credential_env": "CD_PUBLISH_TOKEN"}}

time.sleep(__LEAD__)
approve_and_publish(
    rows,
    cfg,
    Connector(),
    platform_name="video-site",
    config_label="config.toml",
    log_path=log_path,
)
sys.stdout.flush()
"""


def _read_until(master: int, marker: str, seen: str, deadline: float) -> str:
    """Everything the terminal has shown so far, once `marker` is among it."""
    while marker not in seen and time.time() < deadline:
        ready, _, _ = select.select([master], [], [], 0.2)
        if not ready:
            continue
        try:
            chunk = os.read(master, 4096)
        except OSError:  # the child exited and closed its end of the pty
            break
        if not chunk:
            break
        seen += chunk.decode("utf-8", "replace")
    return seen


def _published(record: Path) -> list[str]:
    return record.read_text(encoding="utf-8").split()


def test_keys_delivered_before_the_reply_was_on_screen_approve_nothing(tmp_path):
    record = tmp_path / "sends.txt"
    record.write_text("", encoding="utf-8")
    driver = tmp_path / "driver.py"
    driver.write_text(
        DRIVER.replace("__ROWS__", str(ROWS)).replace("__LEAD__", str(LEAD)),
        encoding="utf-8",
    )
    # The child imports the same package this process imported, whatever tree that
    # is, rather than whatever happens to be installed in its environment.
    source_root = str(Path(commentdraft.__file__).resolve().parents[1])

    pid, master = pty.fork()
    if pid == 0:
        os.environ["PYTHONPATH"] = source_root
        os.execv(
            sys.executable,
            [sys.executable, str(driver), str(record), str(tmp_path / "published.jsonl")],
        )

    try:
        # Five approvals, in the terminal's queue, before the child has printed a
        # single character. This is the whole of the attack.
        time.sleep(0.3)
        os.write(master, PAYLOAD)

        seen = _read_until(master, "[ 1 / 5 ]", "", time.time() + PATIENCE)
        assert "[ 1 / 5 ]" in seen, f"the first reply was never rendered: {seen!r}"
        assert "(y) send" in seen, f"the prompt was left in a buffer: {seen!r}"
        assert _published(record) == [], "typeahead approved a reply nobody had seen"
        assert "[ 2 / 5 ]" not in seen, "the queue moved on a key that arrived before the row"

        # And the prompt is alive rather than wedged: a key pressed now is read
        # now, with no Enter behind it, which is the other half of reading one byte.
        os.write(master, b"q")
        seen = _read_until(master, "sent 0", seen, time.time() + PATIENCE)
        assert "sent 0" in seen, f"quit did not end the run: {seen!r}"
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, 9)
        os.waitpid(pid, 0)
        os.close(master)

    assert _published(record) == [], "the run published something nobody approved"
