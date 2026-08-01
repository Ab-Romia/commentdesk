# SPDX-License-Identifier: Apache-2.0
"""`commentdraft pull`, offline, with no key and no network.

The front of the loop. Everything here drives the real Facebook connector through
its transport seam, which is honoured only while a test runner is in the process
and fails closed when no fake is installed, so nothing in this file can reach
graph.facebook.com even by accident.

Two properties carry the whole feature and each has a test that fails loudly
without it:

  - what pull writes is what run reads, with no editing step in between. That is
    the round trip, and it runs both commands for real against a fake model.
  - a second pull over unchanged comments writes none of them a second time.
    Drafting is what costs money and costs a person keystrokes, so a read that
    quietly repeats itself is a bill and an audience annoyed twice.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from commentdraft.cli import main
from commentdraft.engine import IN_FIELDS, read_comments
from test_cli import build_product
from test_facebook import PAGE, POST, TOKEN_ENV, Graph, comment, feed, wired
from test_guarantees import _fake_client

FEED = f"{PAGE}/published_posts"

# A read only config: a Page, a read credential, and no [publish] table at all.
SOURCE = f"""
[source]
platform = "facebook"
credential_env = "{TOKEN_ENV}"
page_id = "{PAGE}"
"""

DRAFTED = json.dumps(
    {"decision": "reply", "reason": "asks the price", "reply_text": "eighteen dollars"}
)


@pytest.fixture
def product(tmp_path, monkeypatch):
    """A complete product directory whose config can read and cannot publish."""
    monkeypatch.setenv(TOKEN_ENV, "a-page-access-token")
    return build_product(tmp_path, extra=SOURCE)


def one_post(*comments) -> Graph:
    """A Page with one post carrying whatever comments a test hands over."""
    graph = Graph()
    graph.answer("GET", FEED, feed({"id": POST, "message": "a clip about foraging"}))
    graph.answer("GET", f"{POST}/comments", feed(*comments))
    return graph


def pull(config, out, graph, *extra) -> int:
    with wired(graph):
        return main(["pull", "--config", str(config), "--out", str(out), *extra])


# ---------------------------------------------------------------------------
# The round trip, which is the acceptance criterion for the whole command
# ---------------------------------------------------------------------------


def test_a_pull_writes_a_csv_that_run_reads_with_no_edit_in_between(
    product, tmp_path, monkeypatch, capsys
) -> None:
    """pull, then run, and nothing by hand between them.

    The two halves own one column list between them: the connector returns rows in
    the engine's own shape and engine.write_comments writes exactly those columns,
    so the file one command writes is the file the other reads, header spelling
    included. This is the test that fails the day either side grows a column.
    """
    from commentdraft import cli

    comments = tmp_path / "pulled.csv"
    graph = one_post(comment(f"{POST}_1"), comment(f"{POST}_2"))

    assert pull(product, comments, graph) == 0
    assert {call.method for call in graph.calls} == {"GET"}, "a pull issued a write"

    # It is a comments file in the engine's own terms, not merely a CSV.
    rows = read_comments(comments)
    assert [row["id"] for row in rows] == [f"{POST}_1", f"{POST}_2"]
    assert all(sorted(row) == sorted(IN_FIELDS) for row in rows)
    assert rows[0]["comment"] == "how much is it"
    assert rows[0]["platform"] == "facebook"
    assert rows[0]["post_title"] == "a clip about foraging"

    # And run reads it without being told anything about where it came from.
    monkeypatch.setenv("CD_KEY_MAIN", "not-a-real-key")
    monkeypatch.setattr(cli, "make_client", lambda model_cfg: _fake_client(DRAFTED))
    out = tmp_path / "out"
    assert (
        main(["run", "--config", str(product), "--comments", str(comments), "--out", str(out)]) == 0
    )

    drafted = (out / "review.csv").read_text(encoding="utf-8")
    assert f"{POST}_1" in drafted
    assert f"{POST}_2" in drafted
    assert drafted.count("eighteen dollars") == 2
    assert "Traceback" not in capsys.readouterr().err


def test_a_config_with_a_read_credential_and_no_publish_table_pulls(product, tmp_path) -> None:
    """The posture most operators should start in, driven from the command line.

    A platform can take weeks to grant a write scope. Reading the drafts for a
    week first has to be possible with the credential they already have, which
    means no part of the pull may ask for a [publish] table.
    """
    from commentdraft.config import load_config

    assert "publish" not in load_config(product)

    comments = tmp_path / "pulled.csv"
    assert pull(product, comments, one_post(comment(f"{POST}_1"))) == 0
    assert [row["id"] for row in read_comments(comments)] == [f"{POST}_1"]


# ---------------------------------------------------------------------------
# --since, and the state file that means it does not have to be retyped
# ---------------------------------------------------------------------------

OLD = "2026-07-01T09:00:00+0000"
EDGE = "2026-07-30T10:12:33+0000"
NEW = "2026-07-31T11:00:00+0000"


def three_comments() -> Graph:
    return one_post(
        comment(f"{POST}_old", created_time=OLD),
        comment(f"{POST}_edge", created_time=EDGE),
        comment(f"{POST}_new", created_time=NEW),
    )


def test_since_keeps_the_window_the_operator_asked_for(product, tmp_path) -> None:
    comments = tmp_path / "pulled.csv"
    assert pull(product, comments, three_comments(), "--since", NEW) == 0
    assert [row["id"] for row in read_comments(comments)] == [f"{POST}_new"]


def test_a_since_nobody_can_read_is_refused_and_nothing_is_written(
    product, tmp_path, capsys
) -> None:
    comments = tmp_path / "pulled.csv"
    assert pull(product, comments, three_comments(), "--since", "last tuesday") == 1
    err = capsys.readouterr().err
    assert "last tuesday" in err
    assert "Traceback" not in err
    assert not comments.exists()


def test_the_state_file_remembers_the_marker_so_it_is_typed_once(product, tmp_path) -> None:
    """The second run passes no --since at all and still gets the same window."""
    comments = tmp_path / "pulled.csv"
    state = tmp_path / "pull-state.json"

    assert pull(product, comments, three_comments(), "--since", NEW, "--state", str(state)) == 0
    assert [row["id"] for row in read_comments(comments)] == [f"{POST}_new"]

    stored = json.loads(state.read_text(encoding="utf-8"))
    assert stored["platform"] == "facebook"
    assert stored["since"] == NEW
    assert stored["seen"] == [f"{POST}_new"]

    # A second pull, no flags but the state file, and the old comments stay out
    # both because the marker is remembered and because the id is.
    assert pull(product, comments, three_comments(), "--state", str(state)) == 0
    assert comments.read_text(encoding="utf-8").strip() == ",".join(IN_FIELDS)


# ---------------------------------------------------------------------------
# Pulling twice
# ---------------------------------------------------------------------------


def test_a_second_pull_over_unchanged_comments_writes_none_of_them_again(
    product, tmp_path, capsys
) -> None:
    """The bill this feature exists to prevent.

    An operator runs this on a schedule. The same comment pulled twice is drafted
    twice, paid for twice, and offered to a person to approve twice, and the
    second copy of the reply is one somebody may already have received.
    """
    comments = tmp_path / "pulled.csv"
    state = tmp_path / "pull-state.json"
    rows = [comment(f"{POST}_1"), comment(f"{POST}_2")]

    assert pull(product, comments, one_post(*rows), "--state", str(state)) == 0
    assert len(read_comments(comments)) == 2
    capsys.readouterr()

    assert pull(product, comments, one_post(*rows), "--state", str(state)) == 0
    out = capsys.readouterr().out
    assert "read 2 comment(s)" in out
    assert "2 of them were pulled before" in out
    assert "wrote 0" in out
    # Header and nothing under it, and the message says what run will make of it.
    assert comments.read_text(encoding="utf-8").strip() == ",".join(IN_FIELDS)
    assert "header and nothing else" in out

    # A third comment appears. Only the third one is written.
    third = one_post(*rows, comment(f"{POST}_3"))
    assert pull(product, comments, third, "--state", str(state)) == 0
    assert [row["id"] for row in read_comments(comments)] == [f"{POST}_3"]
    assert json.loads(state.read_text(encoding="utf-8"))["seen"] == [
        f"{POST}_1",
        f"{POST}_2",
        f"{POST}_3",
    ]


def test_without_a_state_file_the_same_comments_come_back_and_the_output_says_so(
    product, tmp_path, capsys
) -> None:
    """The documented duplicate. It is loud rather than silent: the alternative
    was a state file written by default, which changes what a command does with
    no flag and no file the operator chose."""
    comments = tmp_path / "pulled.csv"
    rows = [comment(f"{POST}_1")]

    assert pull(product, comments, one_post(*rows)) == 0
    assert pull(product, comments, one_post(*rows)) == 0

    assert [row["id"] for row in read_comments(comments)] == [f"{POST}_1"]
    out = capsys.readouterr().out
    assert "nothing remembers this pull" in out
    assert "--state" in out


def test_a_state_file_written_for_another_platform_is_refused(product, tmp_path, capsys) -> None:
    """One file per platform. Two platforms sharing one file would each read the
    other's ids as their own and drop comments nobody has ever seen."""
    comments = tmp_path / "pulled.csv"
    state = tmp_path / "pull-state.json"
    state.write_text(json.dumps({"platform": "photo-site", "since": "", "seen": []}), "utf-8")

    assert pull(product, comments, one_post(comment(f"{POST}_1")), "--state", str(state)) == 2
    err = capsys.readouterr().err
    assert "photo-site" in err
    assert "facebook" in err
    assert "Traceback" not in err
    assert not comments.exists()


def test_a_state_file_that_is_not_json_is_refused_rather_than_read_as_empty(
    product, tmp_path, capsys
) -> None:
    """Read as empty it would silently re-pull everything it existed to prevent."""
    comments = tmp_path / "pulled.csv"
    state = tmp_path / "pull-state.json"
    state.write_text("{not json", encoding="utf-8")

    assert pull(product, comments, one_post(comment(f"{POST}_1")), "--state", str(state)) == 2
    assert "Traceback" not in capsys.readouterr().err
    assert not comments.exists()


# ---------------------------------------------------------------------------
# Nothing to pull, and pulls that did not come back whole
# ---------------------------------------------------------------------------


def test_an_empty_result_writes_a_header_and_says_what_run_will_do_with_it(
    product, tmp_path, capsys
) -> None:
    comments = tmp_path / "pulled.csv"
    assert pull(product, comments, one_post()) == 0
    out = capsys.readouterr().out
    assert "read 0 comment(s)" in out
    assert "header and nothing else" in out
    assert comments.read_text(encoding="utf-8").strip() == ",".join(IN_FIELDS)


def test_a_post_that_could_not_be_read_is_named_and_the_pull_reports_itself_partial(
    product, tmp_path, capsys
) -> None:
    """Expired posts are documented as inaccessible, so this is a normal Tuesday.

    The rows that were read are still written, because half a Page is worth
    drafting. The exit code is not 0, because a scheduled caller must not read a
    partial pull as a clean one and go on to publish out of it.
    """
    comments = tmp_path / "pulled.csv"
    graph = Graph()
    graph.answer(
        "GET", FEED, feed({"id": POST, "message": "one"}, {"id": "gone", "message": "two"})
    )
    graph.answer("GET", f"{POST}/comments", feed(comment(f"{POST}_1")))
    graph.answer("GET", "gone/comments", {"error": {"code": 100, "message": "no such post"}}, 400)

    assert pull(product, comments, graph) == 1
    err = capsys.readouterr().err
    assert "gone" in err
    assert "Traceback" not in err
    assert [row["id"] for row in read_comments(comments)] == [f"{POST}_1"]


# ---------------------------------------------------------------------------
# Every way a credential dies, named rather than flattened
# ---------------------------------------------------------------------------

NAMED = [
    (190, 460, "password"),
    (190, 492, "appropriate role on the page"),
    (190, 463, "expired"),
    (10, None, "90 day"),
    (200, None, "permission"),
    (1705, None, "as a person rather than as the page"),
    (32, None, "rate limit"),
    (100, None, "page_id"),
    (368, None, "abusive"),
]


@pytest.mark.parametrize(("code", "subcode", "phrase"), NAMED, ids=lambda v: str(v))
def test_a_refused_call_says_which_refusal_it_was(
    product, tmp_path, capsys, code, subcode, phrase
) -> None:
    """Five different things kill a Page token and each has a different fix.

    The connector already reads Meta's subcodes and says which one happened. A
    pull that printed "request failed" over the top of that would send an operator
    to exchange a new token for a failure that a new token cannot fix.
    """
    error = {"code": code, "message": "Error validating access token"}
    if subcode is not None:
        error["error_subcode"] = subcode
    graph = Graph()
    graph.answer("GET", FEED, {"error": error}, status=400)
    comments = tmp_path / "pulled.csv"

    assert pull(product, comments, graph) == 1
    err = capsys.readouterr().err
    assert phrase in err.lower(), f"code {code}/{subcode} was flattened: {err}"
    assert "Error validating access token" in err, "Meta's own wording was thrown away"
    assert "Traceback" not in err
    assert not comments.exists(), "a failed pull replaced the comments file"


def test_a_failed_pull_leaves_the_state_file_alone(product, tmp_path) -> None:
    """Nothing was read, so nothing may be marked as read."""
    comments = tmp_path / "pulled.csv"
    state = tmp_path / "pull-state.json"

    assert pull(product, comments, one_post(comment(f"{POST}_1")), "--state", str(state)) == 0
    before = state.read_text(encoding="utf-8")

    dead = Graph()
    dead.answer("GET", FEED, {"error": {"code": 190, "error_subcode": 460}}, status=400)
    assert pull(product, comments, dead, "--state", str(state)) == 1
    assert state.read_text(encoding="utf-8") == before


# ---------------------------------------------------------------------------
# Every refusal that comes before the platform is called
# ---------------------------------------------------------------------------


def test_pull_refuses_a_config_that_names_nothing_to_read(tmp_path, capsys) -> None:
    config = build_product(tmp_path, extra="")
    rc = main(["pull", "--config", str(config), "--out", str(tmp_path / "pulled.csv")])
    err = capsys.readouterr().err
    assert rc == 2
    assert "source" in err
    assert "Traceback" not in err


def test_pull_names_an_unregistered_platform_and_lists_what_is_registered(tmp_path, capsys) -> None:
    named = '\n[source]\nplatform = "fixture-source"\ncredential_env = "CD_ABSENT_TOKEN"\n'
    config = build_product(tmp_path, extra=named)
    rc = main(["pull", "--config", str(config), "--out", str(tmp_path / "pulled.csv")])
    err = capsys.readouterr().err
    assert rc == 2
    assert "fixture-source" in err
    assert "registered" in err


def test_pull_names_the_missing_credential_before_it_builds_a_connector(
    tmp_path, capsys, monkeypatch
) -> None:
    """The credential is checked before the connector's own code runs, on the same
    order cmd_publish uses: an operator can act on "this variable is not set"
    without knowing anything about the connector behind it."""
    monkeypatch.delenv("CD_ABSENT_READ_TOKEN", raising=False)
    named = (
        '\n[source]\nplatform = "facebook"\n'
        'credential_env = "CD_ABSENT_READ_TOKEN"\npage_id = "1122334455"\n'
    )
    config = build_product(tmp_path, extra=named)
    out = tmp_path / "pulled.csv"

    # No transport is installed, so the seam refuses any call that reaches it.
    rc = main(["pull", "--config", str(config), "--out", str(out)])

    err = capsys.readouterr().err
    assert rc == 2
    assert "CD_ABSENT_READ_TOKEN" in err
    assert "Traceback" not in err
    assert not out.exists()


# ---------------------------------------------------------------------------
# The state file on its own
# ---------------------------------------------------------------------------


def test_a_repeat_inside_one_pull_is_written_once(tmp_path) -> None:
    from commentdraft.pull import State, unseen

    rows = [{"id": "a"}, {"id": "b"}, {"id": "a"}]
    assert [row["id"] for row in unseen(rows, State())] == ["a", "b"]


def test_a_row_with_no_id_is_kept_every_time(tmp_path) -> None:
    """There is nothing to remember it by, so the choice is a duplicate or a
    comment nobody ever answers. docs/configuration.md says which was chosen."""
    from commentdraft.pull import State, remember, unseen

    rows = [{"id": ""}, {"id": "a"}]
    state = remember(State(), "facebook", "", rows)

    assert state.seen == {"a"}
    assert [row["id"] for row in unseen(rows, state)] == [""]


def test_what_was_dropped_is_remembered_as_firmly_as_what_was_written(tmp_path) -> None:
    """Recording only the rows that reached the CSV would forget a comment the
    moment it was suppressed once, and write it again on the run after that."""
    from commentdraft.pull import State, load_state, remember, save_state, unseen

    rows = [{"id": "a"}, {"id": "b"}]
    first = remember(State(), "facebook", "", rows)
    path = Path(tmp_path) / "state.json"
    save_state(path, first)

    reloaded = load_state(path, "facebook")
    assert unseen(rows, reloaded) == []
    second = remember(reloaded, "facebook", "", rows)
    assert second.seen == {"a", "b"}
