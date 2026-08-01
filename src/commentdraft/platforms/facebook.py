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

import http.client
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import warnings
from collections.abc import Callable, Iterator
from datetime import datetime
from typing import NoReturn

from commentdraft.platforms import (
    PUBLISH_SECTION,
    SOURCE_SECTION,
    PlatformError,
    PlatformHalt,
    publish_target,
    register,
    source_target,
)

PLATFORM_NAME = "facebook"

# Pinned, never left off. An unversioned Graph call silently follows whatever is
# newest, which is how an integration that has not been touched in a year starts
# behaving differently on a Tuesday.
API_VERSION = "v26.0"
GRAPH_HOST = "graph.facebook.com"

# The one key this connector adds to a table of its own. The other two, the
# platform name and the credential variable, belong to every connector and are
# validated by the registry's own publish_target and source_target.
#
# The same spelling in both tables. Reading is where it is actually used, and it
# is declared under [publish] as well because that is where it shipped: a config
# written before [source] existed names the Page there, and pulling has to go on
# working for it rather than telling an operator their working setup is wrong.
PAGE_KEY = "page_id"

# Seconds. A connector call sits between a person pressing a key and that person
# being told what happened, so it fails rather than hangs.
TIMEOUT = 30

# Feed and comment pages are followed until Meta stops handing back a next link.
# The cap is not a limit on how much can be read, it is a loop detector: the feed
# edge returns roughly 600 posts a year at 100 per request, so a run that walks
# past this many pages is following a cursor that is not advancing.
MAX_PAGES = 200

# Requested explicitly rather than left to Meta's defaults. Only one of these two
# changes what comes back, and saying which is which matters:
#   filter=stream         the correction. Meta's default, toplevel, drops replies
#                         to replies, and a tool that reads with it looks like it
#                         is ignoring half a thread it then replies into. This is
#                         the whole of the fix.
#   live_filter=no_filter asked for and inert nearly everywhere. Meta's own text:
#                         "For comments on a Live streaming video ... In all other
#                         circumstances this parameter is ignored." It is sent
#                         because it costs nothing and because a Page that starts
#                         streaming should not need a code change, not because it
#                         reveals anything on an ordinary post. The claim that it
#                         un-hides comments a human moderator can see is Meta's
#                         description of the parameter, contradicted by Meta's own
#                         sentence about when the parameter applies.
COMMENT_QUERY = {
    "fields": "id,message,created_time,from{id,name},parent{id},is_hidden,can_comment",
    "filter": "stream",
    "live_filter": "no_filter",
    "limit": "100",
}

POST_QUERY = {"fields": "id,message,created_time", "limit": "100"}

# The Page's own posts. Not /feed, which carries posts other people made on the
# Page and posts that merely tag it: replying to those from the Page's account is
# not what an operator asked for, and the ids are not the operator's to answer
# under. published_posts is the edge that means "what this Page published".
POSTS_EDGE = "published_posts"

# The fields the write check reads back. message is not compared against what was
# sent: see publish_reply for why it is fetched anyway.
VERIFY_FIELDS = "id,parent{id},message"

# The fields read off the comment a person approved a reply to, when this
# connector has to answer "is that comment still the customer's own words". Two
# fields, because that is the whole question.
PARENT_FIELDS = "id,message"

# What each Graph error code and subcode means to the person holding the token,
# and what they have to do about it. Held as a table rather than as a chain of
# ifs so that the enumeration is readable next to Meta's own, and so that a code
# nobody mapped falls through to a message that says so instead of to silence.
#
# A tuple key of (code, None) is the fallback for that code when the subcode is
# absent or is one nobody mapped. A key of (None, subcode) is the reading of a
# subcode whatever code carried it: Meta prints the 190 subcodes under code 102
# and under a bare OAuthException as well, and a table keyed only on the pair told
# an operator whose token had died in a way it names precisely that this was a
# code nobody had a reading for.
CAUSES: dict[tuple[int | None, int | None], str] = {
    (None, 458): (
        "the app is no longer installed for this account, which usually means the "
        "app was deauthorised. Log in again and exchange a new Page token."
    ),
    (None, 459): (
        "the account is checkpointed. Open facebook.com in a browser and clear "
        "whatever it asks for first, then log in again and exchange a new Page token."
    ),
    (None, 460): (
        "the password on the account behind this token was changed, which "
        "invalidates the token. Log in again and exchange a new Page token."
    ),
    (None, 463): (
        "the token has expired, been revoked, or is otherwise invalid. Log in "
        "again and exchange a new Page token."
    ),
    (None, 464): (
        "the account is unconfirmed. Open facebook.com in a browser and confirm "
        "it first, then log in again and exchange a new Page token."
    ),
    (None, 467): (
        "the token has expired, been revoked, or is otherwise invalid. Log in "
        "again and exchange a new Page token."
    ),
    # The Page role death, which the fallback below used to swallow. Meta's own
    # words for it are "User associated with the Page access token does not have
    # an appropriate role on the Page", and the fix is not the fix for any other
    # 190: exchanging a new token gets a token that dies exactly the same way,
    # because a Page token is unique to one Page, one admin and one app, and the
    # thing that broke is the human's role on the Page.
    (None, 492): (
        "the user associated with the Page access token does not have an "
        "appropriate role on the Page. This is not a token that expired and "
        "exchanging a new one will produce another token that fails here: a Page "
        "token is tied to one person's role on one Page, so somebody has to give "
        "that account its role back, or at minimum the MODERATE and CREATE_CONTENT "
        "tasks, before any token can work."
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
    (200, None): (
        "the token does not carry the permission this call needs. Meta prints this "
        "as a permissions error and the specific meaning varies by permission. For "
        "this connector it is one of pages_read_engagement, pages_read_user_content "
        "or pages_manage_engagement: run the login flow again, grant all of them, "
        "and exchange a new Page token."
    ),
    (1705, None): (
        "this call was made as a person rather than as the Page. Exchange the user "
        "token for a Page token and put that in the credential variable."
    ),
    (100, None): (
        "a parameter on the call was rejected, which for this connector usually "
        "means the id it was pointed at does not exist, is not visible to this "
        "token, or is a Page id that belongs to somebody else. Check "
        f"{SOURCE_SECTION}.{PAGE_KEY}, or {PUBLISH_SECTION}.{PAGE_KEY} if that is "
        "where your config names the Page, against the Page the token was issued for."
    ),
    (368, None): (
        "the action was blocked as abusive or otherwise disallowed. This is a "
        "temporary block on the account or the Page rather than a bad call, and "
        "publishing again through it makes it longer. Stop, wait it out, and read "
        "Meta's spam policy before sending another batch."
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
        "the user or app whose token is being used in this Pages API request has "
        "reached its rate limit. The budget is 4800 calls a day multiplied by the "
        "number of people who engaged with the Page in the last 24 hours, so a "
        "quiet Page has almost none. Wait before calling again."
    ),
    (613, None): (
        "a custom rate limit has been reached. Wait before calling again rather "
        "than retrying, which extends the block."
    ),
    (80001, None): (
        "the per-Page call limit for this edge has been reached. Wait before "
        "calling again: the block lengthens while calls keep arriving."
    ),
}

# Meta documents 200-299 as one band, "Multiple values depending on permission",
# and prints no table of the individual codes. A number in it that nothing above
# names is still a permissions failure and not a mystery, so it is read as one
# rather than falling through to the message that says nobody mapped this.
PERMISSION_CODES = range(200, 300)


class FacebookError(Exception):
    """The Graph API refused a call, or answered with something unusable.

    One row's failure. commentdraft.approve catches this, counts the row failed,
    prints the reason under the reply it belongs to, and offers the next row.

    published_id is empty for almost all of them, because almost all of them are
    raised before anything was written. It is set on the one shape that is not: a
    reply that is live and in the wrong place, where the queue can safely carry on
    and yet something exists on the Page with this tool's text in it. The gate
    reads it off whatever was raised and writes the audit line for it.
    """

    def __init__(self, message: str, published_id: str = "") -> None:
        super().__init__(message)
        self.published_id = published_id


class ReplyInvariantError(PlatformHalt):
    """A write happened and could not be proved to be a reply. Stop everything.

    Outside the hierarchy commentdraft.approve catches per row, because it
    inherits from the registry's PlatformHalt, which is a BaseException. That is
    the one deliberate piece of rudeness here.

    commentdraft.approve wraps the send in `except Exception` so that one refused
    row does not lose the rest of the queue, which is right for every ordinary
    failure and exactly wrong for this one. If the write path turns out to edit
    the customer's comment instead of replying to it, then it will do that to
    every remaining row too, and continuing the queue means damaging the next
    comment and the one after it while printing a line nobody reads until later.

    So the run ends. That is deliberately louder than anything else in this
    package, because the thing it reports is that somebody's own words may have
    been overwritten by ours, and there is no version of that worth continuing
    through.

    The type lives in the registry now rather than in this connector, so the gate
    can re-raise it by name and write down the id it carries before it does.
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
    """The thing that makes the request: the real one, or the suite's.

    Fails closed under a test runner. This used to fall through to the real
    transport when no fake was installed, which made "the whole suite runs with no
    network and no credential" a convention that held because every test happened
    to remember, rather than a property of the code. One test written without the
    seam and the suite reaches graph.facebook.com from somebody's laptop, or from
    CI, with whatever token is in that environment.
    """
    if _TEST_RUNNER not in sys.modules:
        return _request
    if _scripted_transport is None:
        raise FacebookError(
            f"{_TEST_RUNNER} is running and no fake transport is installed, so this call "
            "would go to the real Graph API. Install one for the test that made this "
            "call: tests/test_facebook.py has wired(), which is the only supported way "
            "to reach the seam."
        )
    return _scripted_transport


def _request(method: str, url: str, body: dict | None) -> tuple[int, str]:
    """One HTTP call, as (status, body text). Never raises for a 4xx or a 5xx.

    A Graph error arrives as a JSON body under a 4xx, and that body is the only
    place the code and subcode live. Letting urllib raise on it would throw away
    the one thing this connector needs in order to say anything useful, so the
    status comes back as a value and _call reads the body either way.

    Everything else that can come out of a socket becomes a FacebookError. urllib
    raises OSError in shapes URLError does not cover, and http.client raises its
    own hierarchy, RemoteDisconnected among them, which is what a server closing a
    keep alive connection produces. Those used to escape this function as ordinary
    Exceptions: harmless on a read, and on the write check the difference between
    "the queue stops" and "the queue writes again".
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
    except (OSError, http.client.HTTPException) as exc:
        raise FacebookError(
            f"the connection to {GRAPH_HOST} failed: {type(exc).__name__}: {exc}"
        ) from exc


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
    code = error.get("code") if isinstance(error.get("code"), int) else None
    subcode = error.get("error_subcode") if isinstance(error.get("error_subcode"), int) else None
    said = str(error.get("message") or "").strip()
    kind = str(error.get("type") or "").strip()
    cause = _cause(code, subcode)
    where = f"code {code}"
    if code is None:
        where = kind or "no code"
    if subcode is not None:
        where = f"{where}, subcode {subcode}"
    detail = f' Meta said: "{said}"' if said else ""
    return FacebookError(f"facebook refused the call ({where}): {cause}{detail}")


def _cause(code: int | None, subcode: int | None) -> str:
    """The reading of one (code, subcode), in the order that finds the specific one.

    The pair first, then the subcode on its own, then the code on its own, then
    the permissions band. The subcode step is the one that was missing: Meta
    prints the same token subcodes under code 190, under code 102, and under an
    OAuthException carrying no code this connector can read, and a lookup keyed
    only on the pair reported the most precisely diagnosable failures in the whole
    table as codes nobody had a reading for.
    """
    if code is not None and subcode is not None:
        pair = CAUSES.get((code, subcode), "")
        if pair:
            return pair
    if subcode is not None:
        by_subcode = CAUSES.get((None, subcode), "")
        if by_subcode:
            return by_subcode
    if code is not None:
        by_code = CAUSES.get((code, None), "")
        if by_code:
            return by_code
        if code in PERMISSION_CODES:
            return CAUSES[(200, None)]
    return "this code is not one this connector has a reading for."


def _read_table(config: dict) -> tuple[str, dict]:
    """The table the Page id is read out of, and what it is called.

    [source] when the config has one, and [publish] when it does not, exactly as
    the registry's source_target picks the credential. Both have to answer the
    same way or a config could be pulled with one table's token against the other
    table's Page.
    """
    for name in (SOURCE_SECTION, PUBLISH_SECTION):
        section = config.get(name)
        if section is not None:
            if not isinstance(section, dict):
                raise PlatformError(f"[{name}] must be a table holding {PAGE_KEY}")
            return name, section
    raise PlatformError(f"this config names no Page: add [{SOURCE_SECTION}] with {PAGE_KEY} in it")


def _text_key(table: str, section: dict, key: str, hint: str) -> str:
    """A non-empty string, or a PlatformError naming the key and what belongs in it.

    Shape and type, never content, on the same rule as config.load_config and the
    registry's own publish_target: nothing here asks whether a Page id names a
    real Page. A bool is rejected before the isinstance check can matter, because
    TOML has a bool literal and str(True) is a plausible looking value.
    """
    value = section.get(key)
    if isinstance(value, bool) or not isinstance(value, str) or not value.strip():
        raise PlatformError(f"{table}.{key} must be a non-empty string ({hint})")
    return value.strip()


def _page_id(config: dict) -> str:
    table, section = _read_table(config)
    return _text_key(table, section, PAGE_KEY, "the numeric id of your Facebook Page")


def _read_token(config: dict) -> str:
    """The Page access token for reading, out of the variable the config names.

    source_target does the shape checking on the two keys every connector has, so
    a config that names no platform or no credential variable is refused with the
    registry's own wording rather than with a second one written here. It reads
    [source] first and falls back to [publish], which is what lets a config that
    has only ever had a write credential go on pulling.
    """
    _, credential_env = source_target(config)
    return _credential(credential_env)


def _write_token(config: dict) -> str:
    """The Page access token for publishing, out of the [publish] table alone.

    No fallback in this direction. Reading may borrow the publish credential when
    that is the only one an operator has written down, and publishing may never
    borrow the read one: a token granted for reading is the one credential this
    connector must not be able to write with by accident.
    """
    _, credential_env = publish_target(config)
    return _credential(credential_env)


def _credential(credential_env: str) -> str:
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

    No marker at all is a different thing from an unreadable one, and both
    spellings of it mean the same: read everything. The registry's interface types
    since as a string, so a caller with nothing stored has an empty one to hand
    over, and refusing that would make a first pull impossible.
    """
    if since is None or not since.strip():
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
        following = _next_link(payload)
        # After the next link is read, not before it. Checked first, a walk that
        # finished on its last page raised as though the cursor were stuck: the
        # cap is a loop detector, and there is no loop to detect when the platform
        # has just said there is nothing after this.
        if following and seen >= MAX_PAGES:
            raise FacebookError(
                f"stopped after {MAX_PAGES} pages of {_redacted(url)}. The paging cursor "
                "is not advancing, so the result would be wrong rather than merely long."
            )


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


def _is_a_reply(comment: dict) -> bool:
    """Whether this comment hangs under another comment rather than under the post.

    Read off the parent field, which COMMENT_QUERY already asks for and which the
    connector used to fetch and throw away. Anything present under `parent` counts,
    including a shape this code cannot read: an unreadable parent is not evidence
    of there being none, and the safe reading of "this may be a reply to a reply"
    is to leave it out of a queue whose replies would land somewhere else.
    """
    return comment.get("parent") is not None


def _comments_on(post_id: str, title: str, token: str, cutoff: datetime | None) -> list[dict]:
    """The rows for one post, or none and a warning naming the post that failed.

    The whole walk of one post is inside the try, not each page, because a cursor
    that dies half way through leaves a partial list nobody can tell from a
    complete one, and half a post's comments presented as all of them is worse
    than none of them plus a line saying so.
    """
    rows: list[dict] = []
    try:
        for comment in _paged(_url(f"{post_id}/comments", token, COMMENT_QUERY)):
            comment_id = comment.get("id")
            if not isinstance(comment_id, str) or not comment_id:
                continue
            if _is_a_reply(comment):
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
    except FacebookError as exc:
        warnings.warn(
            f"no comments were read for post {post_id}: {exc}. Every other post in this "
            "run was read normally, so this is one post missing rather than a failed run.",
            stacklevel=2,
        )
        return []
    return rows


@register(PLATFORM_NAME)
class Facebook:
    """Read comments on the operator's own Page posts, and reply to one.

    Stateless. Everything it needs is in the config it is handed and in the
    environment variable that config names, so the instance the registry builds
    carries nothing between calls and holds no credential of its own.
    """

    # The keys this connector reads beyond the two every connector has, declared
    # per table where the registry can see them. Without this the key is real,
    # shipped and documented, and invisible to the test that freezes the config
    # vocabulary, which then passes over it while claiming to have read the whole
    # format. The constant above and these tuples are the same fact written twice
    # on purpose: one is what the code reads, the other is what review reads.
    #
    # The Page id is declared in both tables because it is honoured in both:
    # [source] is where it belongs, and [publish] is where it shipped.
    PUBLISH_KEYS = (PAGE_KEY,)
    SOURCE_KEYS = (PAGE_KEY,)

    def fetch_comments(self, config: dict, since: str | None = None) -> list[dict]:
        """Every comment on the Page's own posts, in engine.IN_FIELDS shape.

        Two edges: the Page's published_posts for the operator's own posts, then
        each post's comments. Not /feed, which also carries posts visitors made on
        the Page and posts that merely tag it.

        The since filter is applied here rather than passed to Meta. The comments
        edge does document a since parameter, but this connector has never been
        run against the live API, and a server side filter that turns out to
        measure something other than creation time drops rows silently. Filtering
        what came back is slower and cannot be wrong in that direction.

        One thing is dropped, and only one: a comment that arrives carrying a
        parent, which is a reply to another comment rather than a comment on the
        post. That is not tidiness. filter=stream asks for them by design, and
        Facebook flattens threads, so a reply written under one of them comes back
        parented to the top level comment instead and the write check reads that
        as a reply in the wrong place. Queueing a row this connector cannot
        correctly reply to is offering a person a keystroke that cannot work.

        Nothing is dropped for being hidden or for being closed to replies. Both
        facts are read from the API and there is nowhere in IN_FIELDS to carry
        them, and silently discarding a customer's comment because a flag on it
        says a reply would fail is a worse answer than drafting one and finding
        out at the send. That gap is written up in the connector report.

        One unreadable post does not lose the rest. An expired post is documented
        as inaccessible, and a walk that raised on it threw away every row already
        collected from every post before it, which is a run that reads as a Page
        with no comments. The post is named through the warnings module and the
        walk carries on.
        """
        token = _read_token(config)
        page_id = _page_id(config)
        cutoff = _cutoff(since)
        rows: list[dict] = []
        for post in _paged(_url(f"{page_id}/{POSTS_EDGE}", token, POST_QUERY)):
            post_id = post.get("id")
            if not isinstance(post_id, str) or not post_id:
                continue
            rows.extend(_comments_on(post_id, _title(post), token, cutoff))
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

        THE RULE UNDERNEATH ALL OF IT: A 2xx POST IS A WRITE THAT HAPPENED.

        Not every answer to that write carries an id this connector can use.
        Graph answers an update with {"success": true}, and an id can come back as
        a number rather than as a string. Neither of those is "nothing was
        created", and treating them that way is what let three comments be
        overwritten while the operator was told nothing had been sent. A number is
        read as the id it is. An answer with no id at all sends this connector to
        read the parent comment back, and whatever it finds there, the run ends:
        either the parent is now holding our text, which is the overwrite, or
        nobody can say what the write did, which is not something to publish
        through again.

        Nothing here retries. One keystroke is at most one POST, and that is the
        property the whole approval claim rests on. A retry inside this method
        would break it silently and no test above this layer would notice.
        """
        token = _write_token(config)
        parent = (parent_id or "").strip()
        if not parent:
            raise FacebookError("there is no comment id to reply to")
        if not text.strip():
            raise FacebookError("there is no reply text to send")
        created = _call("POST", _url(f"{parent}/comments", token), {"message": text})
        published = _identifier(created.get("id"))
        if not published:
            raise _unusable(parent, token, text)
        if _same_comment(published, parent):
            raise ReplyInvariantError(_overwritten(parent), parent)
        seen = _verify(published, parent, token)
        _confirm(published, parent, token, text, seen)
        return published


def _identifier(value: object) -> str:
    """An id out of a Graph response, as text, or an empty string.

    A number is an id. Graph's own comment ids are digits with an underscore in
    them and arrive quoted, but a JSON document is allowed to spell 98765 as a
    number and the previous version of this function refused that answer as "no
    id", which threw away the one thing that could locate a live write. A bool is
    refused before isinstance can matter, because True is an int in Python and
    "the id is True" is not an id.
    """
    if isinstance(value, bool):
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return value.strip()
    return ""


def _same_comment(left: str, right: str) -> bool:
    """Whether two ids name the same comment, in either of the two spellings.

    Facebook writes a comment id both as `98765` and as `1122334455_98765`, the
    second prefixed with the object it hangs under, and it does not promise which
    one an endpoint hands back. Exact equality was the whole overwrite alarm, so
    an edit answered with the other spelling of the id it was pointed at walked
    straight past it and was reported to the operator as a reply that had merely
    landed in the wrong place, with the words "Nothing was overwritten" on it.

    The segment after the last underscore is the comment's own id, so it is
    compared as well. Two different comments cannot share it.
    """
    if left == right:
        return True
    return left.rsplit("_", 1)[-1] == right.rsplit("_", 1)[-1]


def _parent_state(token: str, parent: str, text: str) -> tuple[bool, str]:
    """Read the parent comment back and say whether our text is standing in it.

    Returns (overwritten, evidence). This is the only thing in this connector
    entitled to say the customer's comment is intact, and it exists because the
    two mismatch branches below used to say it without asking anybody.

    A failed read is not a clean answer, so it comes back as "not overwritten"
    with the failure as the evidence, and every caller words its own message so
    that an unread parent is never described as an unharmed one.
    """
    try:
        seen = _call("GET", _url(parent, token, {"fields": PARENT_FIELDS}))
    # Every exception, deliberately: any failure here is an unread parent rather
    # than a safe one, and the caller words its message accordingly.
    except Exception as exc:  # noqa: BLE001
        return False, f"comment {parent} could not be read back: {type(exc).__name__}: {exc}"
    message = seen.get("message")
    if not isinstance(message, str):
        return False, f"comment {parent} came back with no readable message field"
    if _same_text(message, text):
        return True, f"comment {parent} now holds the text that was just sent"
    return False, f"comment {parent} still holds its own text, so it was not overwritten"


def _same_text(left: str, right: str) -> bool:
    """Whether two messages are the same words, allowing for platform whitespace."""
    return " ".join(left.split()) == " ".join(right.split())


def _unusable(parent: str, token: str, text: str) -> PlatformHalt:
    """A 2xx write whose answer carries no id, decided by reading the parent back.

    This is the case the whole connector exists for and the one it used to miss.
    {"success": true} is exactly how Graph answers an update, and answering it
    with an ordinary per-row failure meant the queue wrote again, and again, while
    the summary said nothing had been sent at all.

    So the question is not "did we get an id" but "what is in that comment now".
    If our text is standing in it, that is the overwrite, said in the words the
    overwrite gets. If it is not, the write is somewhere nobody can name, which is
    not a row to move past either.
    """
    overwritten, evidence = _parent_state(token, parent, text)
    if overwritten:
        return ReplyInvariantError(f"{_overwritten(parent)} Read back: {evidence}.", parent)
    return ReplyInvariantError(
        f"the write to comment {parent} was accepted and answered with no id, so there is "
        "nothing to read back and nothing to record. A write that was accepted is a write "
        f"that happened. Read back: {evidence}. Nobody can say from here whether a reply "
        f"exists under {parent}, whether one landed on the post, or whether something else "
        f"was changed, so the queue is stopped rather than sending again through a path "
        f"that answers like this. Open comment {parent} on the Page and look.",
        parent,
    )


def _verify(published: str, parent: str, token: str) -> dict:
    """Read the new comment back, or refuse to call the write a success.

    The reply is live by the time this runs, so a failure here is not "the send
    did not happen". It is "the send happened and nobody can say what it did",
    which is the one outcome that must not be reported as either success or an
    ordinary per-row failure.

    Every exception is caught, not only FacebookError. urllib raises OSError
    families that _request did not used to wrap, and http.client raises its own,
    so a connection dropped on this one GET escaped as an ordinary Exception, the
    gate counted one failed row, and the queue carried on offering the next one
    with a live unverified reply behind it.
    """
    try:
        return _call("GET", _url(published, token, {"fields": VERIFY_FIELDS}))
    # Deliberately every exception, on the argument in the docstring above.
    except Exception as exc:
        raise ReplyInvariantError(
            _unverified(published, parent, f"{type(exc).__name__}: {exc}"), published
        ) from exc


def _confirm(published: str, parent: str, token: str, text: str, seen: dict) -> None:
    """The read back, checked against what was asked for.

    Three outcomes rather than two, and the difference between them is what the
    operator is told about the customer's comment:

      - the reply sits under the parent a person approved. Nothing to say.
      - it sits somewhere else, or nowhere, and the parent is proved intact. That
        is one misplaced reply, so it costs one row rather than the queue.
      - it sits somewhere else and the parent is not proved intact. That is a
        halt, because the only thing worse than stopping is not stopping.

    The downgrade in the middle is not a softening. Facebook flattens threads: a
    reply to a second level comment comes back parented to the top level comment
    it hangs under, which is Meta behaving as documented rather than this
    connector damaging anything, and ending the run over it loses every remaining
    row for a reason that will recur on the next run too.
    """
    if seen.get("id") != published:
        raise ReplyInvariantError(
            _unverified(published, parent, f"reading it back gave id {seen.get('id')!r} instead"),
            published,
        )
    found = seen.get("parent")
    if isinstance(found, dict):
        under = _identifier(found.get("id"))
        if under and _same_comment(under, parent):
            return
        if under:
            _misplaced(
                published,
                parent,
                token,
                text,
                f"it sits under comment {under}, not under comment {parent}, which is the "
                "one a person approved a reply to",
            )
        # A parent field that came back as a dict with no readable id is the
        # middle state: the reply may well be in the right place and this
        # connector cannot see that it is. It is not the same fact as having no
        # parent at all, and it used to be reported as if it were.
        raise ReplyInvariantError(
            _unverified(
                published,
                parent,
                "it came back carrying a parent whose id could not be read",
            ),
            published,
        )
    if found is not None:
        raise ReplyInvariantError(
            _unverified(
                published,
                parent,
                f"it came back with a parent field that is a {type(found).__name__} "
                "rather than an object",
            ),
            published,
        )
    _misplaced(
        published,
        parent,
        token,
        text,
        "it has no parent, which means it landed on the post as a new top level comment "
        f"rather than as a reply under comment {parent}",
    )


def _misplaced(published: str, parent: str, token: str, text: str, what: str) -> NoReturn:
    """A reply that is not under the approved comment, halting only if it may have eaten it.

    Always raises. The parent is read back first, every time: no branch in this
    connector gets to tell an operator their customer's comment is intact without
    having looked at it, which is what both of these branches used to do.
    """
    overwritten, evidence = _parent_state(token, parent, text)
    if overwritten:
        raise ReplyInvariantError(f"{_overwritten(parent)} Read back: {evidence}.", parent)
    raise FacebookError(
        f"the reply was published as {published} and {what}. Read back: {evidence}. This "
        "row is counted failed and the rest of the queue carries on, because a reply in "
        "the wrong place is one reply in the wrong place. It is live, so it is written to "
        "the audit file marked unverified. Find it on the Page and move or delete it.",
        published,
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
