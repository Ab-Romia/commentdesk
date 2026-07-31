# SPDX-License-Identifier: Apache-2.0
"""The model call, the retry policy, and the per row loop.

Nothing in this module is written for a human to read except its own error
strings, which are ASCII English machine output. Every word an operator sees
comes from their own configuration and their own voice files.
"""

import json
import re

DECISIONS = ("reply", "skip", "escalate")

# Rate limits, timeouts and server side failures. Everything else is permanent.
RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}

# Matched by class name rather than by importing the SDK's exception types. The
# engine never imports a client library, so the same policy applies to whatever
# OpenAI compatible object the caller hands it.
RETRYABLE_EXC_NAMES = frozenset(
    {
        "RateLimitError",
        "APITimeoutError",
        "APIConnectionError",
        "InternalServerError",
    }
)


class ParseError(Exception):
    """The model answered, but not with a usable decision."""


def parse_response(text: str) -> dict:
    """Extract the one JSON object, tolerating fences and stray prose around it.

    The match is greedy on purpose: first brace to last, so a nested object
    survives intact. Whatever the model wrapped around the JSON is discarded
    rather than treated as a failure, because a chatty preamble is the single
    most common way a good answer arrives in a bad envelope.
    """
    if not text or not text.strip():
        raise ParseError("empty response")
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ParseError("no JSON object in response")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise ParseError(f"invalid JSON: {exc}") from exc
    decision = data.get("decision")
    if decision not in DECISIONS:
        raise ParseError(f"bad decision: {decision!r}")
    reason = str(data.get("reason") or "").strip()
    if not reason:
        # The reason is the only part of the row a reviewer can check against the
        # comment without reading the draft. A row without one is not reviewable.
        raise ParseError("missing reason")
    reply_text = str(data.get("reply_text") or "").strip()
    if decision == "reply" and not reply_text:
        # Rejected here rather than downstream: a row marked reply with an empty
        # reply cell is the one output a reviewer cannot act on.
        raise ParseError("decision=reply but reply_text is empty")
    if decision != "reply":
        # skip and escalate carry no draft. Clearing it stops a stray reply_text
        # from reaching the review page under a decision that says not to send it.
        reply_text = ""
    return {"decision": decision, "reason": reason, "reply_text": reply_text}


def is_retryable(exc: Exception) -> bool:
    """Rate limits and server side failures only.

    A 429 is the provider explicitly saying to try again shortly. It is free, it
    is transient, and treating it as fatal loses a comment for no reason. A 401
    or a malformed request will fail identically forever, so retrying those only
    burns time and money.

    The class name is checked as well as the status because connection and
    timeout failures carry no status code at all.
    """
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if isinstance(status, int) and status in RETRYABLE_STATUS:
        return True
    return type(exc).__name__ in RETRYABLE_EXC_NAMES
