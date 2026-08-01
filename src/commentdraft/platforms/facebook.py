# SPDX-License-Identifier: Apache-2.0
"""The Facebook Pages connector: read comments on your own posts, reply to one.

Graph API v26.0. Stdlib HTTP only, because this package has one runtime
dependency and a connector is not a reason to grow a second.

Two things in here are not ordinary connector plumbing and both are load bearing.

1. THE REPLY PATH IS NOT SETTLED, SO IT IS PROVED AT RUNTIME.

   Meta documents POST to a comment node with a message body twice, under two
   incompatible headings. The Pages guide calls it "Reply to a Comment". The
   Comment node reference calls the same call "Updating", which is editing that
   comment. Both cannot be true, and if the guide is the wrong one then every
   approved reply silently rewrites the customer's comment and nobody finds out
   until somebody complains.

   So this connector posts to the comment's own comments edge, which is by
   definition its replies, and then it checks the result of every single write
   before it reports success. See publish_reply. The check is permanent. Meta
   changes edge behaviour between versions and this failure is silent without it.

2. THE TRANSPORT IS A SEAM, AND THE SEAM IS SEALED.

   The whole suite runs with no network and no credential, so the thing that
   makes the request is replaceable. It is replaceable in exactly the way the
   approval gate's keystroke seam is replaceable and for the same argument: a
   private module attribute, honoured only while a test runner is in the
   process, never a parameter an installed caller can pass. See _transport.

   The seam sits below the gate rather than beside it. Nothing here calls
   publish_reply; commentdraft.approve does, once per keystroke a person made,
   and tests/test_guarantees.py walks the AST of the package to keep that true.
   A fake transport can change where a write goes. It cannot make a write happen.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator
from datetime import datetime

from commentdraft.platforms import PUBLISH_SECTION, PlatformError, publish_target, register

PLATFORM_NAME = "facebook"

# Pinned, never left off. An unversioned Graph call silently follows whatever is
# newest, which is how an integration that has not been touched in a year starts
# behaving differently on a Tuesday.
API_VERSION = "v26.0"
GRAPH_HOST = "graph.facebook.com"

# The one key this connector adds to the [publish] table. The other two, the
# platform name and the credential variable, belong to every connector and are
# validated by the registry's own publish_target.
PAGE_KEY = "page_id"

# Seconds. A connector call sits between a person pressing a key and that person
# being told what happened, so it fails rather than hangs.
TIMEOUT = 30

# Feed and comment pages are followed until Meta stops handing back a next link.
# The cap is not a limit on how much can be read, it is a loop detector: the feed
# edge returns roughly 600 posts a year at 100 per request, so a run that walks
# past this many pages is following a cursor that is not advancing.
MAX_PAGES = 200

# Requested explicitly rather than left to Meta's defaults, and both of these are
# corrections to a default that hides data:
#   filter=stream         the default, toplevel, drops replies to replies, and a
#                         tool that reads with it looks like it is ignoring half
#                         a thread it then replies into.
#   live_filter=no_filter the default, filter_low_quality, hides comments from
#                         the API that a human moderator can see on the Page.
COMMENT_QUERY = {
    "fields": "id,message,created_time,from{id,name},parent{id},is_hidden,can_comment",
    "filter": "stream",
    "live_filter": "no_filter",
    "limit": "100",
}

POST_QUERY = {"fields": "id,message,created_time", "limit": "100"}

# The fields the write check reads back. message is not compared against what was
# sent: see publish_reply for why it is fetched anyway.
VERIFY_FIELDS = "id,parent{id},message"

# What each Graph error code and subcode means to the person holding the token,
# and what they have to do about it. Held as a table rather than as a chain of
# ifs so that the enumeration is readable next to Meta's own, and so that a code
# nobody mapped falls through to a message that says so instead of to silence.
#
# A tuple key of (code, None) is the fallback for that code when the subcode is
# absent or is one nobody mapped.
CAUSES: dict[tuple[int, int | None], str] = {
    (190, 458): (
        "the app is no longer installed for this account, which usually means the "
        "app was deauthorised. Log in again and exchange a new Page token."
    ),
    (190, 459): (
        "the account is checkpointed. Open facebook.com in a browser and clear "
        "whatever it asks for first, then log in again and exchange a new Page token."
    ),
    (190, 460): (
        "the password on the account behind this token was changed, which "
        "invalidates the token. Log in again and exchange a new Page token."
    ),
    (190, 463): (
        "the token has expired, been revoked, or is otherwise invalid. Log in "
        "again and exchange a new Page token."
    ),
    (190, 464): (
        "the account is unconfirmed. Open facebook.com in a browser and confirm "
        "it first, then log in again and exchange a new Page token."
    ),
    (190, 467): (
        "the token has expired, been revoked, or is otherwise invalid. Log in "
        "again and exchange a new Page token."
    ),
    (190, None): (
        "the access token is not usable any more. Log in again and exchange a new Page token."
    ),
    # The one that will actually happen, and the one that looks like a generic
    # auth failure if nobody names it. A permission your app has not used for 90
    # days has to be granted again by hand. This tool is used in bursts by
    # design, so an operator who answered a batch of comments in March and comes
    # back in July arrives here having changed nothing at all.
    (10, None): (
        "the permission this call needs is not granted. The most likely reason is "
        "the 90 day rule: Meta revokes a permission your app has not used for 90 "
        "days, and it has to be granted again by hand. commentdraft is used in "
        "bursts, so a setup that worked last quarter reaches this with no code "
        "change and nothing wrong. Run the login flow again and grant the pages "
        "permissions, then exchange a new Page token."
    ),
    (1705, None): (
        "this call was made as a person rather than as the Page. Exchange the user "
        "token for a Page token and put that in the credential variable."
    ),
    (4, None): (
        "the app has reached its rate limit. Wait before calling again: retrying "
        "into a rate limit extends the block rather than shortening it."
    ),
    (17, None): (
        "the account has reached its rate limit. Wait before calling again: "
        "retrying into a rate limit extends the block rather than shortening it."
    ),
    (32, None): (
        "this Page has reached its rate limit. The Pages budget scales with the "
        "number of people who engaged with the Page in the last day, so a quiet "
        "Page has a small one. Wait before calling again."
    ),
    (613, None): (
        "a custom rate limit has been reached. Wait before calling again rather "
        "than retrying, which extends the block."
    ),
}


class FacebookError(Exception):
    """The Graph API refused a call, or answered with something unusable.

    One row's failure. commentdraft.approve catches this, counts the row failed,
    prints the reason under the reply it belongs to, and offers the next row.
    """


class ReplyInvariantError(BaseException):
    """A write happened and could not be proved to be a reply. Stop everything.

    BaseException on purpose, and this is the one deliberate piece of rudeness in
    the connector.

    commentdraft.approve wraps the send in `except Exception` so that one refused
    row does not lose the rest of the queue, which is right for every ordinary
    failure and exactly wrong for this one. If the write path turns out to edit
    the customer's comment instead of replying to it, then it will do that to
    every remaining row too, and continuing the queue means damaging the next
    comment and the one after it while printing a line nobody reads until later.

    So this class sits outside the hierarchy that handler catches. The run ends.
    That is deliberately louder than anything else in this package, because the
    thing it reports is that somebody's own words may have been overwritten by
    ours, and there is no version of that worth continuing through.

    The right long term home for this is the registry rather than one connector:
    a platform level "halt the queue" type that the gate re-raises by name. That
    is a change to a module the approval tests are anchored on, so it is written
    up in notes/platforms/facebook-connector-report.md rather than made here.
    """


# The transport seam, and the seal on it.
#
# Same shape and same argument as the keystroke seam in commentdraft.approve. It
# is a private module attribute rather than a parameter, and it is honoured only
# while a test runner is in sys.modules. pytest is a development dependency: it
# is not installed beside the tool, so an installed caller cannot satisfy the
# second half of the condition without deliberately shipping one.
#
# What this seam can and cannot do is worth being precise about. It can change
# where a request goes and what comes back, which is what makes an offline suite
# possible. It cannot cause a reply to be sent, because nothing in this module
# calls publish_reply and the only caller in the package is the approval gate.
# Replacing the transport gets you a different answer to a call somebody already
# approved; it does not get you the call.
_scripted_transport: Callable[[str, str, dict | None], tuple[int, str]] | None = None
_TEST_RUNNER = "pytest"


def _transport() -> Callable[[str, str, dict | None], tuple[int, str]]:
    """The thing that makes the request: the real one, or the suite's."""
    if _TEST_RUNNER not in sys.modules:
        return _request
    if _scripted_transport is None:
        return _request
    return _scripted_transport


def _request(method: str, url: str, body: dict | None) -> tuple[int, str]:
    """One HTTP call, as (status, body text). Never raises for a 4xx or a 5xx.

    A Graph error arrives as a JSON body under a 4xx, and that body is the only
    place the code and subcode live. Letting urllib raise on it would throw away
    the one thing this connector needs in order to say anything useful, so the
    status comes back as a value and _call reads the body either way.
    """
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except urllib.error.URLError as exc:
        raise FacebookError(f"could not reach {GRAPH_HOST}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise FacebookError(f"{GRAPH_HOST} did not answer within {TIMEOUT} seconds") from exc


def _redacted(url: str) -> str:
    """The URL with the token taken out of it, for a message somebody may paste."""
    parts = urllib.parse.urlsplit(url)
    kept = [
        (key, value)
        for key, value in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
        if key != "access_token"
    ]
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(kept)))


def _url(path: str, token: str, query: dict[str, str] | None = None) -> str:
    """A versioned Graph URL with the token on it.

    The token goes in the query string rather than in an Authorization header
    because the query string is what Meta's own documented examples use, and this
    connector was written against the documentation rather than against a live
    endpoint. That puts a credential in a URL, so no URL is ever printed by this
    module without going through _redacted first.
    """
    params = dict(query or {})
    params["access_token"] = token
    quoted = urllib.parse.quote(path, safe="/")
    return f"https://{GRAPH_HOST}/{API_VERSION}/{quoted}?{urllib.parse.urlencode(params)}"


def _call(method: str, url: str, body: dict | None = None) -> dict:
    """One Graph call, as a dict, or a FacebookError naming what went wrong."""
    status, text = _transport()(method, url, body)
    try:
        payload = json.loads(text or "{}")
    except json.JSONDecodeError:
        raise FacebookError(
            f"{method} {_redacted(url)} answered {status} with a body that is not JSON"
        ) from None
    if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
        raise _named(payload["error"])
    if status >= 400:
        raise FacebookError(f"{method} {_redacted(url)} answered {status}: {text[:400]}")
    if not isinstance(payload, dict):
        raise FacebookError(
            f"{method} {_redacted(url)} answered {status} with a {type(payload).__name__}"
        )
    return payload


def _named(error: dict) -> FacebookError:
    """A Graph error object turned into the sentence its owner has to act on.

    Meta's own message is kept on the end rather than replaced. It is often the
    more specific of the two, and dropping it in favour of our reading of the
    code is how a support thread ends with nobody knowing what the API said.
    """
    code = error.get("code")
    subcode = error.get("error_subcode")
    said = str(error.get("message") or "").strip()
    cause = ""
    if isinstance(code, int):
        cause = CAUSES.get((code, subcode if isinstance(subcode, int) else None), "")
        if not cause:
            cause = CAUSES.get((code, None), "")
    if not cause:
        cause = "this code is not one this connector has a reading for."
    where = f"code {code}"
    if subcode is not None:
        where = f"code {code}, subcode {subcode}"
    detail = f' Meta said: "{said}"' if said else ""
    return FacebookError(f"facebook refused the call ({where}): {cause}{detail}")


def _publish_table(config: dict) -> dict:
    section = config.get(PUBLISH_SECTION)
    if not isinstance(section, dict):
        raise PlatformError(
            f"[{PUBLISH_SECTION}] must be a table holding {PAGE_KEY} for this connector"
        )
    return section


def _text_key(section: dict, key: str, hint: str) -> str:
    """A non-empty string, or a PlatformError naming the key and what belongs in it.

    Shape and type, never content, on the same rule as config.load_config and the
    registry's own publish_target: nothing here asks whether a Page id names a
    real Page. A bool is rejected before the isinstance check can matter, because
    TOML has a bool literal and str(True) is a plausible looking value.
    """
    value = section.get(key)
    if isinstance(value, bool) or not isinstance(value, str) or not value.strip():
        raise PlatformError(f"{PUBLISH_SECTION}.{key} must be a non-empty string ({hint})")
    return value.strip()


def _page_id(config: dict) -> str:
    return _text_key(_publish_table(config), PAGE_KEY, "the numeric id of your Facebook Page")


def _token(config: dict) -> str:
    """The Page access token, out of the variable the config names.

    publish_target does the shape checking on the two keys every connector has,
    so a config that names no platform or no credential variable is refused with
    the registry's own wording rather than with a second one written here.
    """
    _, credential_env = publish_target(config)
    token = os.environ.get(credential_env, "")
    if not token.strip():
        raise PlatformError(
            f"{credential_env} is not set, so there is no Page access token to call with"
        )
    return token.strip()


def _parse_time(value: object) -> datetime | None:
    """Graph's created_time, which is ISO 8601 with a numeric offset.

    Returns None rather than raising: a comment whose timestamp cannot be read is
    a comment that still needs answering, and dropping it because of a field
    nobody looks at would be the wrong trade.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+0000"
    for shape in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S"):
        try:
            # The third shape has no offset and produces a naive datetime on
            # purpose. Graph always sends one, but the same parser reads the
            # since marker a caller stored, and refusing an operator's
            # "2026-08-01T09:30:00" over a missing "+0000" would be a rule about
            # typing rather than about time. _newer is what handles the mixture,
            # by reading a naive value as being in the other value's zone.
            return datetime.strptime(text, shape)  # noqa: DTZ007
        except ValueError:
            continue
    return None


def _cutoff(since: str | None) -> datetime | None:
    """The marker the caller stored, as a datetime, or a refusal naming the shape.

    since is opaque to everything above this module, so this connector defines
    it: an ISO 8601 timestamp, with or without an offset, which is the shape
    Graph's own created_time arrives in and the shape the approval log writes.
    A marker that cannot be read is refused rather than ignored, because ignoring
    it means silently re-reading the whole window.
    """
    if since is None:
        return None
    parsed = _parse_time(since)
    if parsed is None:
        raise FacebookError(
            f"since is not a timestamp this connector can read: {since!r}. "
            "Use an ISO 8601 time such as 2026-08-01T09:30:00+0000."
        )
    return parsed


def _newer(created: datetime | None, cutoff: datetime | None) -> bool:
    """Whether a comment falls inside the window the caller asked for.

    Inclusive at the boundary, and a comment with no readable timestamp is kept.
    Both defaults point the same way: a duplicated row costs one model call and a
    person one keystroke, and a dropped row is somebody who never got an answer.
    """
    if cutoff is None or created is None:
        return True
    if created.tzinfo is None:
        return created.replace(tzinfo=cutoff.tzinfo) >= cutoff
    if cutoff.tzinfo is None:
        return created >= cutoff.replace(tzinfo=created.tzinfo)
    return created >= cutoff


def _paged(url: str) -> Iterator[dict]:
    """Every item on a Graph edge, following the next cursor until it stops.

    The next link is used as Meta hands it over, because it carries cursors this
    connector has no way to rebuild, but it is checked for host and scheme first.
    A redirect of the paging cursor is a redirect of a URL that has the Page
    token on it.
    """
    seen = 0
    following: str | None = url
    while following:
        payload = _call("GET", following)
        data = payload.get("data")
        if not isinstance(data, list):
            raise FacebookError(f"GET {_redacted(following)} answered with no data list")
        for item in data:
            if isinstance(item, dict):
                yield item
        seen += 1
        if seen >= MAX_PAGES:
            raise FacebookError(
                f"stopped after {MAX_PAGES} pages of {_redacted(url)}. The paging cursor "
                "is not advancing, so the result would be wrong rather than merely long."
            )
        following = _next_link(payload)


def _next_link(payload: dict) -> str | None:
    paging = payload.get("paging")
    if not isinstance(paging, dict):
        return None
    following = paging.get("next")
    if not isinstance(following, str) or not following:
        return None
    parts = urllib.parse.urlsplit(following)
    if parts.scheme != "https" or parts.hostname != GRAPH_HOST:
        raise FacebookError(
            f"the paging cursor points somewhere other than {GRAPH_HOST}: {_redacted(following)}"
        )
    return following


def _author(comment: dict) -> str:
    """The commenter's name, or an empty string.

    Empty is a normal answer, not a fallback. The from field is absent whenever
    the token cannot see it, and engine.read_comments already treats author as
    optional: an absent author means the prompt omits that clause rather than
    inventing a placeholder name for a stranger.
    """
    sender = comment.get("from")
    if not isinstance(sender, dict):
        return ""
    name = sender.get("name")
    if not isinstance(name, str):
        return ""
    return name.strip()


def _title(post: dict) -> str:
    """What the reviewer sees as the post this comment sits under.

    The post's own message when it has one, and its id when it does not, which is
    the case for a photo or a share. Never empty: the id is the one thing an
    operator can paste into a browser to find the post.
    """
    message = post.get("message")
    if isinstance(message, str) and message.strip():
        return message.strip()
    identifier = post.get("id")
    if isinstance(identifier, str):
        return identifier
    return ""


@register(PLATFORM_NAME)
class Facebook:
    """Read comments on the operator's own Page posts, and reply to one.

    Stateless. Everything it needs is in the config it is handed and in the
    environment variable that config names, so the instance the registry builds
    carries nothing between calls and holds no credential of its own.
    """

    def fetch_comments(self, config: dict, since: str | None = None) -> list[dict]:
        """Every comment on the Page's own posts, in engine.IN_FIELDS shape.

        Two edges, in the order the research file establishes: the Page's feed
        for the operator's own posts, then each post's comments.

        The since filter is applied here rather than passed to Meta. The comments
        edge does document a since parameter, but this connector has never been
        run against the live API, and a server side filter that turns out to
        measure something other than creation time drops rows silently. Filtering
        what came back is slower and cannot be wrong in that direction.

        Nothing is dropped for being hidden or for being closed to replies. Both
        facts are read from the API and there is nowhere in IN_FIELDS to carry
        them, and silently discarding a customer's comment because a flag on it
        says a reply would fail is a worse answer than drafting one and finding
        out at the send. That gap is written up in the connector report.
        """
        token = _token(config)
        page_id = _page_id(config)
        cutoff = _cutoff(since)
        rows: list[dict] = []
        for post in _paged(_url(f"{page_id}/feed", token, POST_QUERY)):
            post_id = post.get("id")
            if not isinstance(post_id, str) or not post_id:
                continue
            title = _title(post)
            for comment in _paged(_url(f"{post_id}/comments", token, COMMENT_QUERY)):
                comment_id = comment.get("id")
                if not isinstance(comment_id, str) or not comment_id:
                    continue
                if not _newer(_parse_time(comment.get("created_time")), cutoff):
                    continue
                message = comment.get("message")
                rows.append(
                    {
                        "id": comment_id,
                        "platform": PLATFORM_NAME,
                        "author": _author(comment),
                        "comment": message.strip() if isinstance(message, str) else "",
                        "post_title": title,
                    }
                )
        return rows

    def publish_reply(self, config: dict, parent_id: str, text: str) -> str:
        """Reply to one comment, prove it was a reply, and return the new id.

        The write goes to the comment's own comments edge, which is by definition
        its replies, and not to the comment node itself. Meta documents the
        second one as both "Reply to a Comment" and as "Updating", and only one
        of those can be true.

        Then the result is checked, every time, before anything reports success:

          1. the id that came back is not the id we posted to. Equal means the
             call edited the customer's comment rather than replying to it.
          2. reading that id back gives that id, and gives a parent, and the
             parent is the comment a person approved a reply to. No parent means
             it landed on the post as a fresh top level comment.

        Check one is made twice: once on the write response, before anything else
        happens, and again on the read back. The early one needs no second call,
        so the worst case in this whole connector is detected even on a run where
        the read back is the thing that fails.

        This does not go away once somebody confirms the path against a live
        Page. Meta changes edge behaviour between versions, the failure is silent
        without this, and one extra read against a person pressing a key per
        reply costs nothing anybody can measure.

        The message field is read back and deliberately not compared to what was
        sent. A platform is allowed to normalise whitespace or trim, and a
        connector that refused a good reply over a stripped trailing space would
        teach its operator to stop reading the failures. It is fetched because it
        is the evidence: on an edit it is our text sitting where the customer's
        words used to be, and the operator needs to see that in the failure.
        """
        token = _token(config)
        parent = (parent_id or "").strip()
        if not parent:
            raise FacebookError("there is no comment id to reply to")
        if not text.strip():
            raise FacebookError("there is no reply text to send")
        created = _call("POST", _url(f"{parent}/comments", token), {"message": text})
        published = created.get("id")
        if not isinstance(published, str) or not published:
            raise FacebookError("the platform accepted the reply and returned no id for it")
        if published == parent:
            raise ReplyInvariantError(_overwritten(parent))
        seen = _verify(published, parent, token)
        _confirm(published, parent, seen)
        return published


def _verify(published: str, parent: str, token: str) -> dict:
    """Read the new comment back, or refuse to call the write a success.

    The reply is live by the time this runs, so a failure here is not "the send
    did not happen". It is "the send happened and nobody can say what it did",
    which is the one outcome that must not be reported as either success or an
    ordinary per-row failure.
    """
    try:
        return _call("GET", _url(published, token, {"fields": VERIFY_FIELDS}))
    except FacebookError as exc:
        raise ReplyInvariantError(_unverified(published, parent, str(exc))) from exc


def _confirm(published: str, parent: str, seen: dict) -> None:
    """The read back, checked against what was asked for."""
    if seen.get("id") != published:
        raise ReplyInvariantError(
            _unverified(published, parent, f"reading it back gave id {seen.get('id')!r} instead")
        )
    found = seen.get("parent")
    under = found.get("id") if isinstance(found, dict) else None
    if under == parent:
        return
    if under is None:
        raise ReplyInvariantError(
            f"the reply was published as {published} and it has no parent, which means it "
            f"landed on the post as a new top level comment rather than as a reply under "
            f"comment {parent}. Nothing was overwritten. The reply path in this connector "
            "is not doing what it says, so the queue is stopped rather than repeating it "
            "on every remaining row. Find the reply on the Page and move or delete it."
        )
    raise ReplyInvariantError(
        f"the reply was published as {published} but it sits under comment {under}, not "
        f"under comment {parent}, which is the one a person approved a reply to. Nothing "
        "was overwritten. Read both ids: if they are the same comment written two "
        "different ways then this connector is comparing ids the platform spells "
        "differently, and if they are not, the reply is under the wrong comment. Either "
        "way the queue is stopped rather than repeating it on every remaining row."
    )


def _overwritten(parent: str) -> str:
    """The worst thing this connector can report, in the words it has to use.

    Nothing about this is hedged. The call was a write, the platform handed back
    the id of the thing that was written, and that id is the customer's comment.
    """
    return (
        f"the write to comment {parent} came back carrying that same id, which means it "
        f"did not create a reply: it EDITED comment {parent}. The text a person approved "
        "is now standing where that customer's own words used to be, and their words are "
        "gone. Nothing else will be published: this is not one row's problem, because the "
        "same call would do the same thing to every remaining reply in the queue. Open "
        f"comment {parent} on the Page now and see what it says. Then stop using this "
        "connector to publish until the reply path is fixed, and read "
        "notes/platforms/facebook-connector-report.md, which is where this exact outcome "
        "is written up as the thing the check exists to catch."
    )


def _unverified(published: str, parent: str, why: str) -> str:
    return (
        f"the reply to comment {parent} WAS PUBLISHED, as {published}, and it could not be "
        f"checked: {why}. It is live either way. Nobody can say from here whether it is a "
        f"reply under {parent}, a top level comment on the post, or an edit of somebody "
        "else's comment, so it is not reported as sent and the queue is stopped rather "
        f"than writing again through a path nobody verified. Look at {published} on the "
        "Page, then run publish again for the rest."
    )
