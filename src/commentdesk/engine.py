# SPDX-License-Identifier: Apache-2.0
"""The model call, the retry policy, and the per row loop.

Nothing in this module is written for a human to read except its own error
strings, which are ASCII English machine output. Every word an operator sees
comes from their own configuration and their own voice files.
"""

import csv
import json
import re
import time
from pathlib import Path

from commentdesk.config import ConfigError
from commentdesk.prompt import build_messages
from commentdesk.report import estimate_cost
from commentdesk.sanitize import sanitize_reply

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

RETRY_NUDGE = (
    'Return ONLY one valid JSON object with the keys "decision", '
    '"reason" and "reply_text". No other text.'
)

# Seconds to wait before each backoff retry. Three attempts past the first is
# enough to ride out a rate limit without stalling a long run behind one row.
RETRY_WAITS = (2, 6, 15)

EMPTY_USAGE = {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "cached_tokens": 0,
    "cache_write_tokens": 0,
}

# The configuration always supplies a separator. This fallback exists so that a
# partial behavior table, which is what the local UI can hand over mid edit, does
# not take down the call path.
DEFAULT_SEPARATOR = ", "


class ParseError(Exception):
    """The model answered, but not with a usable decision."""


def _string_field(data: dict, key: str) -> str:
    """Return data[key] as a string, or reject it if present with the wrong type.

    Absent or JSON null means the model omitted the field, which becomes an
    empty string exactly as before. A present value of the wrong type (a list,
    a number, an object) is a parse error rather than silently passed through
    str(), because str() on a non-string turns it into Python's repr of that
    value, and that repr is what would land in a field a human reads.
    """
    value = data.get(key)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ParseError(f"bad {key}: {value!r}")
    return value


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
    reason = _string_field(data, "reason").strip()
    if not reason:
        # The reason is the only part of the row a reviewer can check against the
        # comment without reading the draft. A row without one is not reviewable.
        raise ParseError("missing reason")
    reply_text = _string_field(data, "reply_text").strip()
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


def call_model(client, model_cfg: dict, messages: list) -> tuple[str, dict]:
    """Return the raw text plus the usage the API actually reported.

    Costs are computed from these numbers rather than assumed, so a model that
    quietly bills hidden reasoning tokens still shows its true price in the CSV.
    Every field is read defensively because usage is optional in the response
    schema and some routes omit the cache counters entirely.
    """
    resp = client.chat.completions.create(
        model=model_cfg["model"],
        messages=messages,
        extra_body=model_cfg.get("params") or {},
    )
    text = resp.choices[0].message.content or ""
    reported = resp.usage
    details = getattr(reported, "prompt_tokens_details", None)
    usage = {
        "prompt_tokens": getattr(reported, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(reported, "completion_tokens", 0) or 0,
        "cached_tokens": (getattr(details, "cached_tokens", 0) or 0) if details else 0,
        "cache_write_tokens": (getattr(details, "cache_write_tokens", 0) or 0) if details else 0,
    }
    return text, usage


def process_comment(client, model_cfg: dict, messages: list, behavior: dict) -> dict:
    """One call, a second if the response will not parse, and a few more only if
    the provider itself said to try again.

    Three failure classes, three behaviours. A malformed response gets one retry
    with a nudge appended, since it is usually the model being chatty around an
    otherwise good answer. A rate limit or a 5xx gets backed off and retried,
    because the provider is telling us the call did not go through. Anything
    else, a rejected key or a bad request, stops immediately, because it will
    fail identically forever.

    Usage from every attempt is summed so the cost column stays truthful: a
    retried row was billed twice and the report has to say so.
    """
    separator = behavior.get("separator") or DEFAULT_SEPARATOR
    banned_emoji = behavior.get("banned_emoji") or ""
    last_error = ""
    last_reason = ""
    usage_total = dict(EMPTY_USAGE)
    raw_text = ""
    # Not dead: RETRY_WAITS is a fixed non-empty tuple so the loop below always
    # runs, but pyright cannot prove that from range(2 + len(RETRY_WAITS)) alone
    # and flags `attempt` as possibly unbound at the final return without this.
    attempt = 0
    backoffs = 0
    started = time.monotonic()
    for attempt in range(2 + len(RETRY_WAITS)):
        try:
            text, usage = call_model(client, model_cfg, messages)
            raw_text = text
            for key in usage_total:
                usage_total[key] += usage[key]
            parsed = parse_response(text)
            # Kept for the error row: if the draft is discarded below, the model's
            # read of the comment is still the most useful thing in that row.
            last_reason = parsed["reason"]
            parsed["reply_text"] = sanitize_reply(parsed["reply_text"], separator, banned_emoji)
            if parsed["decision"] == "reply" and not parsed["reply_text"]:
                # A draft made only of banned characters would otherwise land as
                # decision=reply with an empty reply cell.
                raise ParseError("reply_text empty after style sanitation")
            return {
                **parsed,
                "error": "",
                "usage": usage_total,
                "raw": raw_text,
                "attempts": attempt + 1,
                "latency_s": round(time.monotonic() - started, 2),
            }
        except ParseError as exc:
            last_error = str(exc)
            if any(m.get("content") == RETRY_NUDGE for m in messages):
                break  # one nudge is enough, a second never helps
            messages = [*messages, {"role": "user", "content": RETRY_NUDGE}]
        except Exception as exc:  # noqa: BLE001 - the class is decided by is_retryable
            last_error = f"{type(exc).__name__}: {exc}"
            if not is_retryable(exc) or backoffs >= len(RETRY_WAITS):
                break
            time.sleep(RETRY_WAITS[backoffs])
            backoffs += 1
    return {
        "decision": "error",
        "reason": last_reason,
        "reply_text": "",
        "error": last_error,
        "usage": usage_total,
        "raw": raw_text,
        "attempts": attempt + 1,
        "latency_s": round(time.monotonic() - started, 2),
    }


IN_FIELDS = ["id", "platform", "author", "comment", "video_title"]

OUT_FIELDS = [
    "id",
    "platform",
    "author",
    "comment",
    "video_title",
    "decision",
    "reason",
    "reply",
    "model",
    "prompt_tokens",
    "cached_tokens",
    "cache_write_tokens",
    "completion_tokens",
    "cost_usd",
    "error",
]

EMPTY_COMMENT_REASON = "empty comment, nothing to answer"


def read_comments(path: str | Path) -> list[dict]:
    """Read the input CSV into rows keyed by IN_FIELDS.

    utf-8-sig because a spreadsheet export writes an invisible marker before the
    first header. Read as plain utf-8 it becomes part of that column's name, so
    the id column silently stops matching and every row loses its identifier.

    Only `comment` is required. `author` is optional on purpose: it is personal
    data in a real export, many operators strip it before the file leaves their
    machine, and an absent author means the request omits that clause rather than
    inventing a placeholder name.
    """
    with open(path, encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [{k: (raw.get(k) or "").strip() for k in IN_FIELDS} for raw in reader]
        fields = reader.fieldnames or []
    if not rows:
        raise ConfigError(f"no comments found in {path}")
    # Checked after emptiness so a zero byte file gets the message that names its
    # actual problem. A header spelled "Comment" would otherwise read every row
    # as empty, skip all of them, and still exit 0.
    if "comment" not in fields:
        raise ConfigError(f"{path} has no 'comment' column (found: {', '.join(fields) or 'none'})")
    return rows


def write_rows(rows: list[dict], path: str | Path) -> None:
    """Write the review CSV, creating the output directory if it is missing."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def run_pipeline(cfg, model_cfg, comments, knowledge_text, system_text, client):
    """One model call per comment, in input order.

    system_text arrives as a parameter rather than being rendered here so that
    the batch path, the single comment path and the local UI all share one
    rendering. Rendering per row would also change the prefix from row to row,
    and the prefix is identical across a run precisely so the provider can serve
    it from cache after the first call.
    """
    behavior = cfg.get("behavior") or {}
    out_rows = []
    for row in comments:
        base = {k: row.get(k, "") for k in IN_FIELDS}
        if not base["comment"].strip():
            # Decided locally, so an empty comment never costs a call, and it
            # never prices out at a real, honest zero either: no call happened
            # to have a cost, so the cost column stays blank rather than "free".
            result = {
                "decision": "skip",
                "reason": EMPTY_COMMENT_REASON,
                "reply_text": "",
                "error": "",
                "usage": dict(EMPTY_USAGE),
            }
            cost = None
        else:
            messages = build_messages(system_text, knowledge_text, row)
            result = process_comment(client, model_cfg, messages, behavior)
            cost = estimate_cost(result["usage"], model_cfg)
        usage = result["usage"]
        out_rows.append(
            {
                **base,
                "decision": result["decision"],
                "reason": result["reason"],
                "reply": result["reply_text"],
                "model": model_cfg["model"],
                "prompt_tokens": usage["prompt_tokens"],
                "cached_tokens": usage["cached_tokens"],
                "cache_write_tokens": usage["cache_write_tokens"],
                "completion_tokens": usage["completion_tokens"],
                "cost_usd": f"{cost:.6f}" if cost is not None else "",
                "error": result["error"],
            }
        )
        print(
            f"  [{base['id']}] {result['decision']}"
            + (f" | {result['error']}" if result["error"] else "")
        )
    return out_rows


def run_one(
    cfg,
    model_cfg,
    client,
    knowledge_text,
    system_text,
    comment: str,
    platform: str = "",
    author: str = "",
) -> dict:
    """Process one ad hoc comment and return the whole trace.

    Shared by the chat subcommand and the local UI, so that what an operator
    tries by hand is produced by exactly the code that produces a batch row.
    """
    row = {"platform": platform, "author": author, "comment": comment, "video_title": ""}
    messages = build_messages(system_text, knowledge_text, row)
    result = process_comment(client, model_cfg, messages, cfg.get("behavior") or {})
    return {
        "model": model_cfg["model"],
        "base_url": model_cfg.get("base_url", ""),
        "params": model_cfg.get("params") or {},
        "comment": comment,
        "platform": platform,
        "request_messages": messages,
        "raw_response": result.get("raw", ""),
        "decision": result["decision"],
        "reason": result["reason"],
        "reply": result["reply_text"],
        "error": result["error"],
        "usage": result["usage"],
        "attempts": result.get("attempts"),
        "latency_s": result.get("latency_s"),
        "cost_usd": estimate_cost(result["usage"], model_cfg),
    }
