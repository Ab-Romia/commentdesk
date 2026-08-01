# SPDX-License-Identifier: Apache-2.0
"""The Facebook Pages connector, offline, with no key and no network.

The tests that matter most in this file are the write invariant ones. Meta
documents two incompatible things about replying to a comment, and if the wrong
one is true then every approved reply overwrites the customer's comment. So the
connector checks the result of every write, and these tests are what prove the
check fires: a scripted Graph that answers a write with the parent's own id has
to produce a loud, specific, queue-stopping failure, because that answer is the
signature of having edited somebody's comment instead of replying to it.

Every request goes through the connector's transport seam, which is honoured
only while a test runner is in the process. Nothing here reaches a network.
"""

from __future__ import annotations

import json
import sys
import urllib.parse
from contextlib import contextmanager
from dataclasses import dataclass

import pytest

from commentdraft.engine import IN_FIELDS
from commentdraft.platforms import PlatformError, get_platform
from commentdraft.platforms import facebook as fb

TOKEN_ENV = "CD_FB_TOKEN"
PAGE = "1122334455"
POST = "1122334455_98765"

CONFIG = {
    "publish": {
        "platform": "facebook",
        "credential_env": TOKEN_ENV,
        "page_id": PAGE,
    }
}


@dataclass(frozen=True)
class Call:
    method: str
    path: str
    query: dict
    body: dict | None


class Graph:
    """A scripted Graph API: answers by (method, path), records every call.

    Answers queue per route, so a route asked twice can hand back a first page
    and then a second one. A route with one answer left keeps giving it, which is
    what lets a test script the write path without also scripting how many times
    the connector reads back.
    """

    def __init__(self) -> None:
        self.answers: dict[tuple[str, str], list[tuple[int, object]]] = {}
        self.calls: list[Call] = []

    def answer(self, method: str, path: str, payload: object, status: int = 200) -> Graph:
        self.answers.setdefault((method, path), []).append((status, payload))
        return self

    def __call__(self, method: str, url: str, body: dict | None) -> tuple[int, str]:
        path, query = _split(url)
        self.calls.append(Call(method, path, query, body))
        queue = self.answers.get((method, path))
        if not queue:
            raise AssertionError(f"the connector called {method} {path}, which is not scripted")
        status, payload = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(payload, str):
            return status, payload
        return status, json.dumps(payload)

    def of(self, method: str, path: str) -> list[Call]:
        return [call for call in self.calls if call.method == method and call.path == path]


def _split(url: str) -> tuple[str, dict]:
    parts = urllib.parse.urlsplit(url)
    assert parts.scheme == "https"
    assert parts.hostname == fb.GRAPH_HOST
    prefix = f"/{fb.API_VERSION}/"
    assert parts.path.startswith(prefix), parts.path
    return parts.path[len(prefix) :], dict(urllib.parse.parse_qsl(parts.query))


@contextmanager
def wired(graph: Graph):
    """Install a scripted Graph for one test, and take it out again.

    The seam is a private module attribute honoured only under a test runner, on
    the same argument as the approval gate's keystroke seam. This is the only
    supported way to reach it, and it is installed around one test rather than
    left set, because a transport leaking into another test is a test proving the
    wrong thing.
    """
    previous = fb._scripted_transport
    fb._scripted_transport = graph
    try:
        yield graph
    finally:
        fb._scripted_transport = previous


@pytest.fixture
def token(monkeypatch):
    monkeypatch.setenv(TOKEN_ENV, "a-page-access-token")


@pytest.fixture
def connector():
    return get_platform("facebook")


def comment(identifier: str, **extra) -> dict:
    row = {
        "id": identifier,
        "message": "how much is it",
        "created_time": "2026-07-30T10:12:33+0000",
        "from": {"id": "9", "name": "Jo"},
    }
    row.update(extra)
    return row


def feed(*posts, **paging) -> dict:
    return {"data": list(posts), **paging}


# ---------------------------------------------------------------------------
# The write invariant. Written first, and made to fail for the right reason
# before the check existed.
# ---------------------------------------------------------------------------


def test_the_write_goes_to_the_comments_edge_and_never_to_the_comment_itself(
    token, connector
) -> None:
    """The whole reason this connector was built before it was documented.

    POST to the comment node is documented by Meta as "Reply to a Comment" in one
    place and as "Updating", which is editing it, in another. This connector
    posts to the comment's own comments edge instead, and this test is what pins
    that choice in the code rather than in a comment about the code.
    """
    graph = Graph()
    graph.answer("POST", f"{POST}_1/comments", {"id": "reply-1"})
    graph.answer("GET", "reply-1", {"id": "reply-1", "parent": {"id": f"{POST}_1"}, "message": "x"})

    with wired(graph):
        assigned = connector.publish_reply(CONFIG, f"{POST}_1", "we cover that in chapter three")

    assert assigned == "reply-1"
    written = graph.of("POST", f"{POST}_1/comments")
    assert len(written) == 1
    assert written[0].body == {"message": "we cover that in chapter three"}
    assert graph.of("POST", f"{POST}_1") == [], "a write reached the comment node itself"


def test_a_write_answered_with_the_parent_id_is_reported_as_an_edit(token, connector) -> None:
    """The signature of having overwritten somebody's comment.

    If the platform hands back the id we posted to, then the call did not create
    anything: it rewrote the comment it was pointed at, and the customer's own
    words are gone. The failure has to name that in words, name the comment, and
    it must not be swallowed by the per-row handler in the approval gate.
    """
    graph = Graph()
    graph.answer("POST", f"{POST}_1/comments", {"id": f"{POST}_1"})

    with wired(graph), pytest.raises(fb.ReplyInvariantError) as exc:
        connector.publish_reply(CONFIG, f"{POST}_1", "we cover that in chapter three")

    message = str(exc.value)
    assert f"{POST}_1" in message, "the failure does not name the comment it may have overwritten"
    lowered = message.lower()
    assert "edit" in lowered
    assert "reply" in lowered
    # And nothing else was attempted afterwards. Whatever happened to that
    # comment, the queue does not get to do it again to the next one.
    assert graph.of("GET", f"{POST}_1") == []


def test_the_edit_failure_is_outside_the_hierarchy_the_gate_catches() -> None:
    """approve._send_approved wraps the send in `except Exception` so that one
    refused row does not lose the queue. That is right for every ordinary failure
    and exactly wrong for this one: a write path that edits rather than replies
    will do it to every remaining row too. So the type sits outside that."""
    assert issubclass(fb.ReplyInvariantError, BaseException)
    assert not issubclass(fb.ReplyInvariantError, Exception)


def test_a_reply_with_no_parent_landed_on_the_post_and_is_refused(token, connector) -> None:
    """The second failure mode. An absent parent means the comment was created as
    a top level comment on the post, not as a reply under the one a person
    approved a reply to. It is not destructive and it is still wrong."""
    graph = Graph()
    graph.answer("POST", f"{POST}_1/comments", {"id": "reply-1"})
    graph.answer("GET", "reply-1", {"id": "reply-1", "message": "x"})

    with wired(graph), pytest.raises(fb.ReplyInvariantError) as exc:
        connector.publish_reply(CONFIG, f"{POST}_1", "we cover that in chapter three")

    message = str(exc.value)
    assert "reply-1" in message
    assert f"{POST}_1" in message
    assert "parent" in message.lower()


def test_a_reply_landing_under_a_different_comment_is_refused(token, connector) -> None:
    """Both ids go in the message. If Meta ever spells a parent id in a different
    form than the one it was handed, this is the failure an operator will see, and
    they can only tell that from a wrong parent by reading both."""
    graph = Graph()
    graph.answer("POST", f"{POST}_1/comments", {"id": "reply-1"})
    graph.answer("GET", "reply-1", {"id": "reply-1", "parent": {"id": f"{POST}_9"}})

    with wired(graph), pytest.raises(fb.ReplyInvariantError) as exc:
        connector.publish_reply(CONFIG, f"{POST}_1", "we cover that in chapter three")

    assert f"{POST}_9" in str(exc.value)
    assert f"{POST}_1" in str(exc.value)


def test_the_check_reads_back_the_new_id_with_the_documented_fields(token, connector) -> None:
    graph = Graph()
    graph.answer("POST", f"{POST}_1/comments", {"id": "reply-1"})
    graph.answer("GET", "reply-1", {"id": "reply-1", "parent": {"id": f"{POST}_1"}})

    with wired(graph):
        connector.publish_reply(CONFIG, f"{POST}_1", "hello")

    read = graph.of("GET", "reply-1")
    assert len(read) == 1, "the write was not checked exactly once"
    assert read[0].query["fields"] == fb.VERIFY_FIELDS


def test_a_check_that_reads_back_a_different_id_is_refused(token, connector) -> None:
    """The read back is what the whole claim rests on, so it has to be the thing
    that was written and not something else that happened to answer."""
    graph = Graph()
    graph.answer("POST", f"{POST}_1/comments", {"id": "reply-1"})
    graph.answer("GET", "reply-1", {"id": "somebody-else", "parent": {"id": f"{POST}_1"}})

    with wired(graph), pytest.raises(fb.ReplyInvariantError):
        connector.publish_reply(CONFIG, f"{POST}_1", "hello")


def test_a_write_that_cannot_be_checked_stops_the_queue_rather_than_reporting_success(
    token, connector
) -> None:
    """The reply is already live at this point. Reporting success would put an id
    in the audit log that nobody proved is a reply, and reporting an ordinary
    failure would let the queue carry on writing through a path nobody verified.
    Neither is available, so the run ends."""
    graph = Graph()
    graph.answer("POST", f"{POST}_1/comments", {"id": "reply-1"})
    graph.answer("GET", "reply-1", {"error": {"code": 190, "error_subcode": 460}}, status=400)

    with wired(graph), pytest.raises(fb.ReplyInvariantError) as exc:
        connector.publish_reply(CONFIG, f"{POST}_1", "hello")

    assert "reply-1" in str(exc.value), "the id of a live reply is not in the failure"


def test_a_write_answered_with_no_id_is_a_plain_failure(token, connector) -> None:
    """Nothing was created that anyone can point at, so this is one row's problem
    rather than a reason to end the run."""
    graph = Graph()
    graph.answer("POST", f"{POST}_1/comments", {"ok": True})

    with wired(graph), pytest.raises(fb.FacebookError):
        connector.publish_reply(CONFIG, f"{POST}_1", "hello")


@pytest.mark.parametrize(("parent", "text"), [("", "hello"), ("   ", "hello"), ("c1", "   ")])
def test_an_empty_parent_or_an_empty_reply_reaches_no_network_at_all(
    token, connector, parent, text
) -> None:
    graph = Graph()
    with wired(graph), pytest.raises(fb.FacebookError):
        connector.publish_reply(CONFIG, parent, text)
    assert graph.calls == []


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def test_every_row_is_exactly_the_shape_the_engine_reads(token, connector) -> None:
    graph = Graph()
    graph.answer("GET", f"{PAGE}/feed", feed({"id": POST, "message": "a clip about foraging"}))
    graph.answer("GET", f"{POST}/comments", feed(comment(f"{POST}_1")))

    with wired(graph):
        rows = connector.fetch_comments(CONFIG, None)

    assert len(rows) == 1
    assert set(rows[0]) == set(IN_FIELDS)
    assert rows[0] == {
        "id": f"{POST}_1",
        "platform": "facebook",
        "author": "Jo",
        "comment": "how much is it",
        "post_title": "a clip about foraging",
    }


def test_a_comment_with_no_author_still_comes_through(token, connector) -> None:
    """from is absent whenever the token cannot see it, and author is optional in
    the engine on purpose: an absent name means the prompt omits that clause
    rather than inventing a placeholder for a stranger."""
    graph = Graph()
    graph.answer("GET", f"{PAGE}/feed", feed({"id": POST, "message": "a clip"}))
    without = comment(f"{POST}_1")
    del without["from"]
    graph.answer(
        "GET",
        f"{POST}/comments",
        feed(without, comment(f"{POST}_2", **{"from": {"id": "9"}})),
    )

    with wired(graph):
        rows = connector.fetch_comments(CONFIG, None)

    assert [row["author"] for row in rows] == ["", ""]
    assert [row["id"] for row in rows] == [f"{POST}_1", f"{POST}_2"]


def test_a_post_with_no_message_is_titled_with_its_id(token, connector) -> None:
    graph = Graph()
    graph.answer("GET", f"{PAGE}/feed", feed({"id": POST}))
    graph.answer("GET", f"{POST}/comments", feed(comment(f"{POST}_1")))

    with wired(graph):
        rows = connector.fetch_comments(CONFIG, None)

    assert rows[0]["post_title"] == POST


def test_both_edges_are_followed_to_the_end_of_their_paging(token, connector) -> None:
    """Two pages of posts and two pages of comments on one of them. A connector
    that reads the first page only looks like a Page with very few comments."""
    graph = Graph()
    graph.answer(
        "GET",
        f"{PAGE}/feed",
        feed({"id": POST, "message": "one"}, paging=_next(f"{PAGE}/feed", "p2")),
    )
    graph.answer("GET", f"{PAGE}/feed", feed({"id": "post-2", "message": "two"}))
    graph.answer(
        "GET",
        f"{POST}/comments",
        feed(comment(f"{POST}_1"), paging=_next(f"{POST}/comments", "c2")),
    )
    graph.answer("GET", f"{POST}/comments", feed(comment(f"{POST}_2")))
    graph.answer("GET", "post-2/comments", feed(comment("post-2_1")))

    with wired(graph):
        rows = connector.fetch_comments(CONFIG, None)

    assert [row["id"] for row in rows] == [f"{POST}_1", f"{POST}_2", "post-2_1"]
    assert [row["post_title"] for row in rows] == ["one", "one", "two"]
    assert len(graph.of("GET", f"{PAGE}/feed")) == 2
    assert len(graph.of("GET", f"{POST}/comments")) == 2


def _next(path: str, cursor: str) -> dict:
    return {"next": f"https://{fb.GRAPH_HOST}/{fb.API_VERSION}/{path}?after={cursor}"}


def test_a_paging_cursor_that_points_off_the_graph_host_is_refused(token, connector) -> None:
    """The next link carries the Page token. Following it wherever it points is
    handing the credential to whoever wrote the response."""
    graph = Graph()
    graph.answer(
        "GET",
        f"{PAGE}/feed",
        feed({"id": POST}, paging={"next": "https://example.invalid/v26.0/steal"}),
    )
    graph.answer("GET", f"{POST}/comments", feed())

    with wired(graph), pytest.raises(fb.FacebookError) as exc:
        connector.fetch_comments(CONFIG, None)

    assert fb.GRAPH_HOST in str(exc.value)


def test_a_cursor_that_never_advances_is_stopped_and_named(token, connector, monkeypatch) -> None:
    monkeypatch.setattr(fb, "MAX_PAGES", 3)
    graph = Graph()
    graph.answer("GET", f"{PAGE}/feed", feed({"id": POST}, paging=_next(f"{PAGE}/feed", "stuck")))
    graph.answer("GET", f"{POST}/comments", feed())

    with wired(graph), pytest.raises(fb.FacebookError) as exc:
        connector.fetch_comments(CONFIG, None)

    assert "3" in str(exc.value)


def test_since_keeps_the_comments_made_after_it(token, connector) -> None:
    graph = Graph()
    graph.answer("GET", f"{PAGE}/feed", feed({"id": POST, "message": "a clip"}))
    graph.answer(
        "GET",
        f"{POST}/comments",
        feed(
            comment(f"{POST}_old", created_time="2026-07-01T09:00:00+0000"),
            comment(f"{POST}_edge", created_time="2026-07-30T10:12:33+0000"),
            comment(f"{POST}_new", created_time="2026-07-31T11:00:00+0000"),
        ),
    )

    with wired(graph):
        rows = connector.fetch_comments(CONFIG, "2026-07-30T10:12:33+0000")

    # Inclusive at the boundary: a duplicated row costs one model call and one
    # keystroke, and a dropped row is somebody who never got an answer.
    assert [row["id"] for row in rows] == [f"{POST}_edge", f"{POST}_new"]


def test_since_is_not_handed_to_the_platform_as_a_filter(token, connector) -> None:
    """The comments edge documents a since parameter and this connector has never
    been run against the live API. A server side filter measuring something other
    than creation time drops rows with no error, so the filtering is done here."""
    graph = Graph()
    graph.answer("GET", f"{PAGE}/feed", feed({"id": POST}))
    graph.answer("GET", f"{POST}/comments", feed(comment(f"{POST}_1")))

    with wired(graph):
        connector.fetch_comments(CONFIG, "2026-07-01T09:00:00+0000")

    for call in graph.calls:
        assert "since" not in call.query


def test_a_comment_with_an_unreadable_timestamp_is_kept(token, connector) -> None:
    graph = Graph()
    graph.answer("GET", f"{PAGE}/feed", feed({"id": POST}))
    graph.answer("GET", f"{POST}/comments", feed(comment(f"{POST}_1", created_time="whenever")))

    with wired(graph):
        rows = connector.fetch_comments(CONFIG, "2026-07-30T10:12:33+0000")

    assert [row["id"] for row in rows] == [f"{POST}_1"]


def test_a_since_marker_nobody_can_read_is_refused_rather_than_ignored(token, connector) -> None:
    """Ignoring it means silently re-reading the whole window, which reads as the
    tool having found a hundred new comments this morning."""
    graph = Graph()
    with wired(graph), pytest.raises(fb.FacebookError) as exc:
        connector.fetch_comments(CONFIG, "last tuesday")
    assert "last tuesday" in str(exc.value)
    assert graph.calls == []


def test_the_read_corrects_both_defaults_that_hide_comments(token, connector) -> None:
    """toplevel drops replies to replies, and filter_low_quality hides comments
    from the API that a human moderator can see on the Page. Both are Meta's
    defaults and both make this tool look like it is ignoring people."""
    graph = Graph()
    graph.answer("GET", f"{PAGE}/feed", feed({"id": POST}))
    graph.answer("GET", f"{POST}/comments", feed(comment(f"{POST}_1")))

    with wired(graph):
        connector.fetch_comments(CONFIG, None)

    query = graph.of("GET", f"{POST}/comments")[0].query
    assert query["filter"] == "stream"
    assert query["live_filter"] == "no_filter"


# ---------------------------------------------------------------------------
# Errors that name the cause
# ---------------------------------------------------------------------------


NAMED = [
    (190, 460, ["password", "log in again"]),
    (190, 458, ["deauthorised", "log in again"]),
    (190, 459, ["checkpointed", "facebook.com"]),
    (190, 463, ["expired", "log in again"]),
    (190, 467, ["expired", "log in again"]),
    (190, 464, ["unconfirmed", "facebook.com"]),
    (190, None, ["not usable any more"]),
    (10, None, ["90 day", "granted again"]),
    (1705, None, ["as a person rather than as the page"]),
    (32, None, ["rate limit"]),
]


@pytest.mark.parametrize(("code", "subcode", "phrases"), NAMED, ids=lambda v: str(v))
def test_each_graph_error_is_read_back_as_the_thing_the_operator_has_to_do(
    token, connector, code, subcode, phrases
) -> None:
    """A token that stopped working looks identical from the outside whatever
    killed it. The subcode is the only thing that says which of five different
    fixes applies, so it is read rather than folded into one auth failure."""
    error = {"code": code, "message": "Error validating access token"}
    if subcode is not None:
        error["error_subcode"] = subcode
    graph = Graph()
    graph.answer("GET", f"{PAGE}/feed", {"error": error}, status=400)

    with wired(graph), pytest.raises(fb.FacebookError) as exc:
        connector.fetch_comments(CONFIG, None)

    message = str(exc.value)
    for phrase in phrases:
        assert phrase in message.lower(), f"code {code}/{subcode} omits {phrase!r}: {message}"
    assert str(code) in message
    assert "Error validating access token" in message, "Meta's own wording was thrown away"


def test_the_ninety_day_rule_is_named_rather_than_left_as_a_permission_error(
    token, connector
) -> None:
    """The most likely reason a working setup stops working with no code change,
    and it arrives as a bare permission error. If this connector does not name
    it, the operator goes looking for a token they already have."""
    graph = Graph()
    graph.answer("GET", f"{PAGE}/feed", {"error": {"code": 10, "message": "no"}}, status=403)

    with wired(graph), pytest.raises(fb.FacebookError) as exc:
        connector.fetch_comments(CONFIG, None)

    message = str(exc.value)
    assert "90 day" in message
    assert "bursts" in message, "the reason this tool in particular hits it is not stated"


def test_a_code_nobody_mapped_says_so_instead_of_guessing(token, connector) -> None:
    graph = Graph()
    graph.answer("GET", f"{PAGE}/feed", {"error": {"code": 8675309, "message": "new"}}, status=400)

    with wired(graph), pytest.raises(fb.FacebookError) as exc:
        connector.fetch_comments(CONFIG, None)

    assert "8675309" in str(exc.value)
    assert "new" in str(exc.value)


def test_a_body_that_is_not_json_is_reported_without_the_token_in_it(token, connector) -> None:
    graph = Graph()
    graph.answer("GET", f"{PAGE}/feed", "<html>502 Bad Gateway</html>", status=502)

    with wired(graph), pytest.raises(fb.FacebookError) as exc:
        connector.fetch_comments(CONFIG, None)

    assert "502" in str(exc.value)
    assert "a-page-access-token" not in str(exc.value)


def test_no_failure_message_carries_the_page_token(token, connector) -> None:
    """Every one of these prints a URL, and the URL is where the credential is."""
    graph = Graph()
    graph.answer("GET", f"{PAGE}/feed", {"data": "not a list"})

    with wired(graph), pytest.raises(fb.FacebookError) as exc:
        connector.fetch_comments(CONFIG, None)

    assert "access_token" not in str(exc.value)
    assert "a-page-access-token" not in str(exc.value)


# ---------------------------------------------------------------------------
# Config, on the same rule as the rest of the project: shape and type, never content
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", [42, "", "   ", True, ["1122334455"], None])
def test_a_page_id_of_the_wrong_type_is_refused_rather_than_coerced(
    token, connector, value
) -> None:
    section = dict(CONFIG["publish"])
    if value is None:
        del section[fb.PAGE_KEY]
    else:
        section[fb.PAGE_KEY] = value

    with pytest.raises(PlatformError) as exc:
        connector.fetch_comments({"publish": section}, None)

    assert fb.PAGE_KEY in str(exc.value)


def test_a_config_with_no_publish_table_names_the_table(connector) -> None:
    with pytest.raises(PlatformError) as exc:
        connector.fetch_comments({"product": {"name": "anything"}}, None)
    assert "publish" in str(exc.value)


def test_an_unset_credential_variable_is_named(connector, monkeypatch) -> None:
    monkeypatch.delenv(TOKEN_ENV, raising=False)
    with pytest.raises(PlatformError) as exc:
        connector.fetch_comments(CONFIG, None)
    assert TOKEN_ENV in str(exc.value)


def test_the_connector_is_registered_and_implements_the_whole_interface() -> None:
    from commentdraft.platforms import Platform

    assert isinstance(get_platform("facebook"), Platform)


# ---------------------------------------------------------------------------
# The seam, and what it is not
# ---------------------------------------------------------------------------


def test_the_transport_seam_is_ignored_when_no_test_runner_is_present(monkeypatch) -> None:
    """An installed copy of this package has no pytest beside it, so setting the
    attribute there changes nothing at all. Same seal, same argument, as the
    approval gate's keystroke seam."""
    graph = Graph()
    with wired(graph):
        assert fb._transport() is graph
        monkeypatch.delitem(sys.modules, fb._TEST_RUNNER)
        assert fb._transport() is fb._request


def test_a_scripted_transport_cannot_make_a_send_happen(tmp_path, monkeypatch) -> None:
    """The seam sits below the gate, not beside it. It can change where a write
    goes; it cannot produce a write, because nothing in the connector calls the
    send and the only caller in the package is the approval gate. Here the
    reviewer skips every row, and a fully scripted, fully willing Graph never
    hears from anybody."""
    from commentdraft.approve import approve_and_publish
    from conftest import scripted_reviewer

    monkeypatch.setenv(TOKEN_ENV, "a-page-access-token")
    graph = Graph()
    graph.answer("POST", "c1/comments", {"id": "reply-1"})
    rows = [
        {
            "id": "c1",
            "platform": "facebook",
            "comment": "how much is it",
            "post_title": "a clip",
            "decision": "reply",
            "reply": "eighteen dollars",
        }
    ]
    pressed = iter(["s"])

    class _Stream:
        def write(self, text: str) -> int:
            return len(text)

    with wired(graph), scripted_reviewer(lambda: next(pressed)):
        counts = approve_and_publish(
            rows,
            CONFIG,
            get_platform("facebook"),
            platform_name="facebook",
            config_label="config.toml",
            log_path=tmp_path / "published.jsonl",
            out=_Stream(),
        )

    assert counts["sent"] == 0
    assert graph.calls == [], "a connector call happened with no keystroke behind it"


def test_an_edited_comment_ends_the_run_instead_of_moving_to_the_next_row(
    tmp_path, monkeypatch
) -> None:
    """Driven through the real approval loop, not through the connector alone.

    Two rows, a reviewer pressing the send key on both, and a platform whose
    answer to the first write is the signature of an edit. The run has to end on
    row one. The alternative, which is what an ordinary Exception would get, is
    that the loop reports one failed row and then does the same thing to the
    second customer's comment.
    """
    from commentdraft.approve import approve_and_publish
    from conftest import scripted_reviewer

    monkeypatch.setenv(TOKEN_ENV, "a-page-access-token")
    graph = Graph()
    graph.answer("POST", "c1/comments", {"id": "c1"})
    graph.answer("POST", "c2/comments", {"id": "reply-2"})
    rows = [
        {
            "id": identifier,
            "platform": "facebook",
            "comment": "how much is it",
            "post_title": "a clip",
            "decision": "reply",
            "reply": "eighteen dollars",
        }
        for identifier in ("c1", "c2")
    ]
    pressed = iter(["y", "y"])
    log = tmp_path / "published.jsonl"

    class _Stream:
        def write(self, text: str) -> int:
            return len(text)

    with (
        wired(graph),
        scripted_reviewer(lambda: next(pressed)),
        pytest.raises(fb.ReplyInvariantError),
    ):
        approve_and_publish(
            rows,
            CONFIG,
            get_platform("facebook"),
            platform_name="facebook",
            config_label="config.toml",
            log_path=log,
            out=_Stream(),
        )

    assert graph.of("POST", "c2/comments") == [], "the queue carried on after an edit"
    assert next(pressed) == "y", "the second row was offered"
    # And nothing claims to have been published, because nothing was: the write
    # that happened was an edit and there is no id for a reply that never existed.
    assert not log.exists()
