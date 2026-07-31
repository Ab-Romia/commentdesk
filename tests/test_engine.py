# SPDX-License-Identifier: Apache-2.0
import pytest

from commentdesk.engine import DECISIONS, ParseError, is_retryable, parse_response


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
