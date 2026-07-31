# SPDX-License-Identifier: Apache-2.0
import csv
import types

import pytest

from commentdesk import engine
from commentdesk.config import ConfigError
from commentdesk.engine import (
    DECISIONS,
    EMPTY_COMMENT_REASON,
    IN_FIELDS,
    OUT_FIELDS,
    RETRY_NUDGE,
    RETRY_WAITS,
    ParseError,
    call_model,
    is_retryable,
    parse_response,
    process_comment,
    read_comments,
    run_one,
    run_pipeline,
    write_rows,
)


def test_decisions_are_the_three_the_contract_names():
    assert DECISIONS == ("reply", "skip", "escalate")


def test_parse_response_reads_a_clean_object():
    out = parse_response(
        '{"decision": "reply", "reason": "asked the price", "reply_text": "It is 18."}'
    )
    assert out == {"decision": "reply", "reason": "asked the price", "reply_text": "It is 18."}


def test_parse_response_tolerates_fences_and_prose_around_the_object():
    text = (
        "Sure, here you go:\n"
        "```json\n"
        '{"decision": "skip", "reason": "no question asked", "reply_text": ""}\n'
        "```\n"
        "Let me know if you want another one."
    )
    assert parse_response(text)["decision"] == "skip"


def test_parse_response_is_greedy_so_a_nested_object_survives():
    # A lazy first-brace-to-first-brace match would stop inside "meta" and hand
    # json.loads a truncated string. First brace to last brace is the point.
    text = (
        'noise {"decision": "escalate", "reason": "refund request", '
        '"reply_text": "", "meta": {"confidence": 0.4}} more noise'
    )
    out = parse_response(text)
    assert out["decision"] == "escalate"
    assert out["reason"] == "refund request"


def test_parse_response_rejects_two_sibling_top_level_objects():
    # The same greedy first-brace-to-last-brace match that lets a nested object
    # survive also spans two sibling objects into one range that is not valid
    # JSON on its own. Fail closed via a decode error rather than silently
    # picking either object.
    text = (
        '{"decision": "skip", "reason": "first", "reply_text": ""} '
        "noise "
        '{"decision": "reply", "reason": "second", "reply_text": "hi"}'
    )
    with pytest.raises(ParseError):
        parse_response(text)


def test_parse_response_rejects_an_empty_response():
    with pytest.raises(ParseError):
        parse_response("")
    with pytest.raises(ParseError):
        parse_response("   \n  ")


def test_parse_response_rejects_a_response_with_no_object():
    with pytest.raises(ParseError):
        parse_response("I cannot help with that.")


def test_parse_response_rejects_broken_json():
    with pytest.raises(ParseError):
        parse_response('{"decision": "skip", "reason": }')


def test_parse_response_rejects_a_decision_outside_the_taxonomy():
    with pytest.raises(ParseError):
        parse_response('{"decision": "maybe", "reason": "r", "reply_text": ""}')
    with pytest.raises(ParseError):
        parse_response('{"reason": "r", "reply_text": ""}')


def test_parse_response_requires_a_reason():
    # The reason is what a reviewer reads to decide whether to trust the row.
    with pytest.raises(ParseError):
        parse_response('{"decision": "skip", "reason": "  ", "reply_text": ""}')


def test_parse_response_rejects_a_reply_with_no_text():
    with pytest.raises(ParseError):
        parse_response('{"decision": "reply", "reason": "praise", "reply_text": ""}')


def test_parse_response_clears_reply_text_on_a_non_reply_decision():
    for decision in ("skip", "escalate"):
        out = parse_response(
            f'{{"decision": "{decision}", "reason": "r", "reply_text": "stray draft"}}'
        )
        assert out["reply_text"] == ""


def test_parse_response_rejects_a_non_string_reason():
    # A present but wrong typed reason must not be coerced into str()'s Python
    # repr, since the reason is what a reviewer reads first.
    with pytest.raises(ParseError):
        parse_response('{"decision": "skip", "reason": ["a", "b"], "reply_text": ""}')
    with pytest.raises(ParseError):
        parse_response('{"decision": "skip", "reason": 42, "reply_text": ""}')


def test_parse_response_rejects_a_non_string_reply_text():
    # Same coercion hazard as reason, but for reply_text: an object here would
    # otherwise land in the output CSV as a drafted reply reading "{'a': 1}".
    with pytest.raises(ParseError):
        parse_response('{"decision": "reply", "reason": "ok", "reply_text": {"a": 1}}')


def test_parse_response_missing_reason_is_still_the_missing_reason_error():
    # An absent field is the model omitting it, not a wrong type. It must keep
    # raising the existing "missing reason" error, not a new type error.
    with pytest.raises(ParseError, match="missing reason"):
        parse_response('{"decision": "skip", "reply_text": ""}')


def test_is_retryable_separates_transient_from_permanent():
    def status_error(status):
        exc = type("ApiStatusError", (Exception,), {})()
        exc.status_code = status  # pyright: ignore[reportAttributeAccessIssue]
        return exc

    assert is_retryable(status_error(429))
    assert is_retryable(status_error(500))
    assert is_retryable(status_error(503))
    # A rejected key or a malformed request fails identically forever. Retrying
    # those burns time and money and still loses the comment.
    assert not is_retryable(status_error(401))
    assert not is_retryable(status_error(400))
    assert not is_retryable(status_error(404))
    assert not is_retryable(ValueError("nothing to do with the network"))


def test_is_retryable_recognises_failures_that_carry_no_status():
    for name in ("RateLimitError", "APITimeoutError", "APIConnectionError", "InternalServerError"):
        exc = type(name, (Exception,), {})()
        assert is_retryable(exc), name


SKIP_JSON = '{"decision": "skip", "reason": "no question asked", "reply_text": ""}'
BEHAVIOR = {"separator": ", ", "banned_emoji": ""}


def fake_response(text, prompt=29150, completion=120, cached=29000, cache_write=0):
    details = types.SimpleNamespace(cached_tokens=cached, cache_write_tokens=cache_write)
    usage = types.SimpleNamespace(
        prompt_tokens=prompt, completion_tokens=completion, prompt_tokens_details=details
    )
    message = types.SimpleNamespace(content=text)
    return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)], usage=usage)


class FakeClient:
    """Stands in for the chat completions client. Returns queued responses."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


class ErrorClient:
    """Raises `error()` for the first `fail_times` calls, then returns `then`."""

    def __init__(self, error, fail_times, then=None):
        self.error = error
        self.fail_times = fail_times
        self.then = then
        self.calls = []
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) <= self.fail_times:
            raise self.error()
        return self.then


def rate_limited():
    exc = RuntimeError("429 too many requests")
    exc.status_code = 429  # pyright: ignore[reportAttributeAccessIssue]
    return exc


def test_call_model_sends_the_params_verbatim_and_reads_the_usage():
    client = FakeClient([fake_response(SKIP_JSON)])
    model_cfg = {"model": "vendor-a/model-one", "params": {"provider": {"data_collection": "deny"}}}
    text, usage = call_model(client, model_cfg, [{"role": "user", "content": "x"}])
    assert text == SKIP_JSON
    assert client.calls[0]["model"] == "vendor-a/model-one"
    assert client.calls[0]["extra_body"] == {"provider": {"data_collection": "deny"}}
    assert usage == {
        "prompt_tokens": 29150,
        "completion_tokens": 120,
        "cached_tokens": 29000,
        "cache_write_tokens": 0,
    }


def test_call_model_survives_a_response_that_reports_no_usage():
    message = types.SimpleNamespace(content=SKIP_JSON)
    bare = types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)], usage=None)
    client = FakeClient([bare])
    text, usage = call_model(client, {"model": "vendor-a/model-one"}, [])
    assert text == SKIP_JSON
    assert usage == {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "cached_tokens": 0,
        "cache_write_tokens": 0,
    }


def test_process_comment_returns_the_parsed_decision_and_the_trace():
    client = FakeClient([fake_response(SKIP_JSON)])
    out = process_comment(
        client, {"model": "vendor-a/model-one"}, [{"role": "user", "content": "x"}], BEHAVIOR
    )
    assert out["decision"] == "skip"
    assert out["reason"] == "no question asked"
    assert out["error"] == ""
    assert out["attempts"] == 1
    assert out["raw"] == SKIP_JSON
    assert isinstance(out["latency_s"], float)


def test_process_comment_nudges_once_and_never_twice():
    client = FakeClient([fake_response("chatty nonsense"), fake_response("still nonsense")])
    out = process_comment(
        client, {"model": "vendor-a/model-one"}, [{"role": "user", "content": "x"}], BEHAVIOR
    )
    assert out["decision"] == "error"
    assert len(client.calls) == 2
    assert client.calls[1]["messages"][-1]["content"] == RETRY_NUDGE
    # Both attempts were billed even though neither parsed. An error row that
    # only counted the last attempt would understate what the run actually cost.
    assert out["usage"] == {
        "prompt_tokens": 58300,
        "completion_tokens": 240,
        "cached_tokens": 58000,
        "cache_write_tokens": 0,
    }


def test_process_comment_recovers_on_the_nudge():
    client = FakeClient([fake_response("chatty nonsense"), fake_response(SKIP_JSON)])
    out = process_comment(
        client, {"model": "vendor-a/model-one"}, [{"role": "user", "content": "x"}], BEHAVIOR
    )
    assert out["decision"] == "skip"
    assert out["error"] == ""
    assert out["attempts"] == 2


def test_process_comment_sums_usage_from_every_attempt():
    # Both calls were billed. A cost column that reports only the last one is a
    # cost column that understates every retry in the run.
    client = FakeClient(
        [
            fake_response("nonsense", prompt=100, completion=10, cached=0),
            fake_response(SKIP_JSON, prompt=100, completion=20, cached=90),
        ]
    )
    out = process_comment(
        client, {"model": "vendor-a/model-one"}, [{"role": "user", "content": "x"}], BEHAVIOR
    )
    assert out["usage"]["prompt_tokens"] == 200
    assert out["usage"]["completion_tokens"] == 30
    assert out["usage"]["cached_tokens"] == 90


def test_process_comment_backs_off_and_retries_a_rate_limit(monkeypatch):
    waits = []
    monkeypatch.setattr(engine.time, "sleep", waits.append)
    client = ErrorClient(rate_limited, fail_times=2, then=fake_response(SKIP_JSON))
    out = process_comment(
        client, {"model": "vendor-a/model-one"}, [{"role": "user", "content": "x"}], BEHAVIOR
    )
    assert out["decision"] == "skip", out["error"]
    assert len(client.calls) == 3
    assert waits == [2, 6]


def test_process_comment_gives_up_rather_than_looping_forever(monkeypatch):
    waits = []
    monkeypatch.setattr(engine.time, "sleep", waits.append)
    client = ErrorClient(rate_limited, fail_times=99)
    out = process_comment(
        client, {"model": "vendor-a/model-one"}, [{"role": "user", "content": "x"}], BEHAVIOR
    )
    assert out["decision"] == "error"
    assert len(client.calls) == len(RETRY_WAITS) + 1
    assert waits == list(RETRY_WAITS) == [2, 6, 15]


def test_process_comment_does_not_retry_a_permanent_failure():
    def rejected_key():
        exc = RuntimeError("401 invalid key")
        exc.status_code = 401  # pyright: ignore[reportAttributeAccessIssue]
        return exc

    client = ErrorClient(rejected_key, fail_times=99)
    out = process_comment(
        client, {"model": "vendor-a/model-one"}, [{"role": "user", "content": "x"}], BEHAVIOR
    )
    assert len(client.calls) == 1
    assert out["decision"] == "error"
    assert "401 invalid key" in out["error"]


def test_process_comment_sanitizes_with_the_behavior_it_is_given():
    drafted = (
        '{"decision": "reply", "reason": "asked where to get it", '
        '"reply_text": "Yes \\u2014 the link is in the profile."}'
    )
    client = FakeClient([fake_response(drafted)])
    out = process_comment(
        client,
        {"model": "vendor-a/model-one"},
        [{"role": "user", "content": "x"}],
        {"separator": " | ", "banned_emoji": ""},
    )
    assert out["decision"] == "reply"
    assert "\u2014" not in out["reply_text"]
    assert "|" in out["reply_text"]


def test_a_reply_emptied_by_sanitation_does_not_ship_as_a_reply():
    # A draft made only of banned characters would otherwise land as
    # decision=reply with an empty reply cell.
    only_banned = '{"decision": "reply", "reason": "praise", "reply_text": "\\u263a"}'
    client = FakeClient([fake_response(only_banned), fake_response(only_banned)])
    out = process_comment(
        client,
        {"model": "vendor-a/model-one"},
        [{"role": "user", "content": "x"}],
        {"separator": ", ", "banned_emoji": "\u263a"},
    )
    assert out["decision"] == "error"
    assert out["reply_text"] == ""
    # The model's read of the comment is still the most useful thing in the row.
    assert out["reason"] == "praise"
    # Both attempts were billed even though the row ships as an error. The
    # sanitised-empty path discards the draft, not the call it took to get it.
    assert out["usage"] == {
        "prompt_tokens": 58300,
        "completion_tokens": 240,
        "cached_tokens": 58000,
        "cache_write_tokens": 0,
    }


PRICED = {
    "model": "vendor-a/model-one",
    "params": {},
    "base_url": "https://gateway.example/v1",
    "api_key_env": "GATEWAY_KEY",
    "pricing": {
        "input_per_mtok": 1.0,
        "cached_per_mtok": 0.1,
        "output_per_mtok": 6.0,
        "cache_write_per_mtok": 1.25,
    },
}
CFG = {"behavior": {"separator": ", ", "banned_emoji": ""}}


def test_read_comments_strips_the_spreadsheet_byte_order_mark(tmp_path):
    # A spreadsheet export carries a mark before the first header, which would
    # otherwise become part of the first column's name and lose every id.
    path = tmp_path / "comments.csv"
    path.write_text(
        "id,platform,author,comment\n1,forum,Dana,How much is it?\n", encoding="utf-8-sig"
    )
    rows = read_comments(path)
    assert rows[0]["id"] == "1"
    assert rows[0]["comment"] == "How much is it?"


def test_read_comments_accepts_a_file_with_no_author_column(tmp_path):
    # The author is personal data. An export without it is the normal case, not
    # an error, and the row simply carries an empty author.
    path = tmp_path / "comments.csv"
    path.write_text("id,platform,comment\n1,forum,Does it cover winter?\n", encoding="utf-8")
    rows = read_comments(path)
    assert rows[0]["author"] == ""
    assert rows[0]["comment"] == "Does it cover winter?"
    assert set(rows[0]) == set(IN_FIELDS)


def test_read_comments_reads_the_old_video_title_header_as_post_title(tmp_path):
    """video_title named one medium in an engine that claims to have none, and it was
    the last place that claim was visibly broken: the label sent to the model was
    already "Post title:" and the review page heading was already "Context", but the
    column an operator types into a spreadsheet still said video. post_title is the
    name now, and the old header is read silently rather than refused, because an
    export already sitting on somebody's disk is not a mistake worth stopping for."""
    path = tmp_path / "comments.csv"
    path.write_text(
        "id,platform,author,comment,video_title\n1,forum,Dana,How much is it?,Ep 3\n",
        encoding="utf-8",
    )
    rows = read_comments(path)
    assert rows[0]["post_title"] == "Ep 3"
    assert set(rows[0]) == set(IN_FIELDS)


def test_post_title_wins_when_a_file_somehow_carries_both_headers(tmp_path):
    """A file half-migrated by hand. The canonical name is the one to believe."""
    path = tmp_path / "comments.csv"
    path.write_text(
        "id,comment,post_title,video_title\n1,How much is it?,New,Old\n",
        encoding="utf-8",
    )
    assert read_comments(path)[0]["post_title"] == "New"


def test_read_comments_rejects_a_file_whose_comment_column_is_misspelled(tmp_path):
    # Without this check every row is read as empty and the run exits 0 having
    # answered nothing, which is the failure that looks most like success.
    path = tmp_path / "comments.csv"
    path.write_text("id,platform,Comment\n1,forum,How much is it?\n", encoding="utf-8")
    with pytest.raises(ConfigError) as caught:
        read_comments(path)
    assert "comment" in str(caught.value)
    assert "Comment" in str(caught.value)


def test_read_comments_reports_emptiness_before_it_reports_a_bad_header(tmp_path):
    # A zero byte file has no header to complain about. Checking emptiness first
    # gets the operator the message that names the actual problem.
    path = tmp_path / "comments.csv"
    path.write_text("", encoding="utf-8")
    with pytest.raises(ConfigError) as caught:
        read_comments(path)
    assert "no comments found" in str(caught.value)


def test_run_pipeline_decides_an_empty_comment_without_calling_the_model():
    client = FakeClient([])  # popping from this would raise IndexError
    rows = run_pipeline(
        CFG,
        PRICED,
        [{"id": "1", "platform": "forum", "author": "", "comment": "   ", "post_title": ""}],
        "KNOWLEDGE",
        "SYSTEM",
        client,
    )
    assert client.calls == []
    assert rows[0]["decision"] == "skip"
    assert rows[0]["reason"] == EMPTY_COMMENT_REASON
    assert rows[0]["reason"].isascii()
    assert rows[0]["cost_usd"] == ""


def test_run_pipeline_writes_every_out_field_and_the_model_it_used():
    client = FakeClient([fake_response(SKIP_JSON)])
    rows = run_pipeline(
        CFG,
        PRICED,
        [
            {
                "id": "7",
                "platform": "forum",
                "author": "Dana",
                "comment": "Nice one",
                "post_title": "Ep 3",
            }
        ],
        "KNOWLEDGE",
        "SYSTEM",
        client,
    )
    assert set(rows[0]) == set(OUT_FIELDS)
    assert rows[0]["model"] == "vendor-a/model-one"
    assert rows[0]["id"] == "7" and rows[0]["author"] == "Dana"
    assert rows[0]["prompt_tokens"] == 29150
    assert float(rows[0]["cost_usd"]) > 0


def test_run_pipeline_leaves_the_cost_blank_when_pricing_is_incomplete():
    # A blank cost is honest. A zero reads as free.
    unpriced = {"model": "vendor-b/model-two", "params": {}}
    client = FakeClient([fake_response(SKIP_JSON)])
    rows = run_pipeline(
        CFG,
        unpriced,
        [{"id": "1", "platform": "forum", "author": "", "comment": "Nice one", "post_title": ""}],
        "KNOWLEDGE",
        "SYSTEM",
        client,
    )
    assert rows[0]["cost_usd"] == ""


def test_run_pipeline_sends_an_identical_system_prefix_for_every_row():
    # The whole cost model depends on this. A per row difference in the prefix
    # turns every call into a cache miss.
    client = FakeClient([fake_response(SKIP_JSON), fake_response(SKIP_JSON)])
    comments = [
        {
            "id": "1",
            "platform": "forum",
            "author": "Dana",
            "comment": "How much?",
            "post_title": "Ep 3",
        },
        {
            "id": "2",
            "platform": "forum",
            "author": "Sam",
            "comment": "Where do I get it?",
            "post_title": "Ep 4",
        },
    ]
    run_pipeline(CFG, PRICED, comments, "KNOWLEDGE", "SYSTEM", client)
    first, second = client.calls
    assert first["messages"][0] == second["messages"][0]
    assert first["messages"][1] != second["messages"][1]


def test_write_rows_round_trips_through_the_csv(tmp_path):
    row = dict.fromkeys(OUT_FIELDS, "")
    row.update(id="1", decision="reply", reply="Yes, it covers winter.")
    path = tmp_path / "nested" / "review.csv"
    write_rows([row], path)
    with open(path, encoding="utf-8", newline="") as handle:
        back = list(csv.DictReader(handle))
    assert list(back[0]) == OUT_FIELDS
    assert back[0]["reply"] == "Yes, it covers winter."


def test_run_one_returns_the_whole_trace():
    client = FakeClient([fake_response(SKIP_JSON)])
    trace = run_one(CFG, PRICED, client, "KNOWLEDGE", "SYSTEM", "How much is it?")
    assert trace["decision"] == "skip"
    assert trace["model"] == "vendor-a/model-one"
    assert trace["base_url"] == "https://gateway.example/v1"
    assert trace["comment"] == "How much is it?"
    assert trace["platform"] == ""
    assert trace["raw_response"] == SKIP_JSON
    assert trace["request_messages"] == client.calls[0]["messages"]
    assert trace["cost_usd"] > 0
    assert trace["attempts"] == 1


def test_run_one_leaves_the_cost_blank_rather_than_a_false_zero_on_a_rejected_key():
    # Same defect as I-3, on the path commentdesk chat and the local UI share: a
    # permanent failure reports no usage at all, and pricing that zero usage against
    # a real rate table yields a confident, false $0.00 for a call that was never
    # billed anything because it never happened. Blank is the truth. Zero is a claim.
    def rejected_key():
        exc = RuntimeError("401 invalid key")
        exc.status_code = 401  # pyright: ignore[reportAttributeAccessIssue]
        return exc

    client = ErrorClient(rejected_key, fail_times=99)
    trace = run_one(CFG, PRICED, client, "KNOWLEDGE", "SYSTEM", "How much is it?")
    assert trace["decision"] == "error"
    assert trace["cost_usd"] is None
