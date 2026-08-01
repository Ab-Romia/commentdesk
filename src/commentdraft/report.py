# SPDX-License-Identifier: Apache-2.0
"""Measure a run. Change nothing about it.

Cost is reported in USD only. There is no currency conversion here, because
converting multiplies two numbers that both decay, the token rates and the
exchange rate, and the product reads more precise than either of its inputs.
"""

from __future__ import annotations

import math

from commentdraft.sanitize import find_repetition, is_plug

# Without all three, the call cannot be priced at all.
REQUIRED_PRICING = ("input_per_mtok", "cached_per_mtok", "output_per_mtok")


def _is_rate(value: object) -> bool:
    """True for a real numeric rate.

    A quoted rate from a config typo (`input_per_mtok = "1.0"`) is a str, and
    letting it through would have `uncached * "1.0"` build a repeated string
    that only fails, confusingly, one line later when it meets a float. A bool
    is technically an int subclass in Python, but True must not count: it
    would price a call at 1.0 per million tokens rather than being caught as
    the non-rate it is.

    nan and inf are both spellable in TOML, so `input_per_mtok = nan` is a rate an
    operator can write by accident. Neither is a price, and either one turns every
    figure downstream of it into nan or inf without raising anywhere.
    """
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def parse_cost(value: object) -> float | None:
    """A row's cost as a finite float, or None when the row carries no usable figure.

    One definition of "unpriced", used by build_report here and by
    render.review_html.total_cost, which are the two places that total a column of
    costs. They used to disagree: this module treated any non-blank cell as priced
    and then crashed on `float("abc")`, while review_html caught the ValueError and
    counted the row as unpriced. review_html is the one that reads hand-edited CSVs,
    so review_html was right, and this is its rule made shared.

    A real 0.0 is priced, not blank: a call, or a locally decided row, that truly
    cost nothing is an answer. Only an absent, blank or unreadable cell is unpriced.
    nan and inf are unreadable for this purpose: "total cost: $nan" is not a figure,
    and one inf makes the whole run's total inf.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) else None
    text = str(value).strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def estimate_cost(usage: dict, model_cfg: dict) -> float | None:
    """Cost of one call in USD, or None when the rates are not fully known.

    None rather than zero, always. A blank cost column reads as "not known",
    which is true. A zero reads as "this call was free", which is a claim and a
    wrong one, and a bake off entry that inherits no pricing would print it on
    every row of the comparison. The same principle covers a rate that is
    present but not actually a number: it is exactly as unknown as a missing
    one, so it returns None rather than crashing or silently miscosting.
    """
    pricing = model_cfg.get("pricing") or {}
    if not all(key in pricing and _is_rate(pricing[key]) for key in REQUIRED_PRICING):
        return None
    # Optional, but if present it is billed same as the required three, so a
    # non-numeric value here is exactly as disqualifying as one of those.
    cache_write_rate = pricing.get("cache_write_per_mtok", 0)
    if not _is_rate(cache_write_rate):
        return None
    # Cached input is billed at its own lower rate, so the input rate applies to
    # the uncached remainder rather than to the whole prompt.
    uncached = usage["prompt_tokens"] - usage["cached_tokens"]
    total = (
        uncached * pricing["input_per_mtok"]
        + usage["cached_tokens"] * pricing["cached_per_mtok"]
        + usage["completion_tokens"] * pricing["output_per_mtok"]
        # A premium on some routes and nothing on others. Absent means zero for
        # this rate alone, which is why it is not in REQUIRED_PRICING.
        + usage["cache_write_tokens"] * cache_write_rate
    )
    return total / 1e6


def _as_int(value: object) -> int:
    """Token counts arrive as ints from the engine and as strings after a CSV
    round trip. Both are real inputs, and neither should be able to crash a
    summary that exists to be read at the end of a long run.
    """
    text = str(value or "").strip()
    if not text:
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def build_report(rows: list[dict], plug_cap: float, markers: list[str]) -> str:
    """Summarise a run in four lines plus any repetition flags.

    plug_cap is an alarm threshold, never a limiter. What holds the plug rate
    down is the prompt, and this line is how you find out whether it still does
    after an edit to the voice file. Nothing here modifies a row.

    The template is ASCII English. The values interpolated into it are the
    operator's own data and may be in any script.
    """
    counts: dict[str, int] = {}
    for r in rows:
        key = str(r.get("decision") or "")
        counts[key] = counts.get(key, 0) + 1

    replies = [r for r in rows if r.get("decision") == "reply"]
    plugs = sum(1 for r in replies if is_plug(str(r.get("reply") or ""), markers))
    # The guard on replies is what keeps a run of pure skips from dividing by
    # zero, and it also keeps a plug_cap of 0.0 from firing on a run with no
    # replies in it to be over the cap.
    over_cap = bool(replies) and plugs / len(replies) > plug_cap

    calls = [r for r in rows if _as_int(r.get("prompt_tokens")) > 0]
    warm = sum(1 for r in calls if _as_int(r.get("cached_tokens")) > 0)

    priced = [cost for cost in (parse_cost(r.get("cost_usd")) for r in rows) if cost is not None]
    if priced:
        cost_line = "total cost: $" + format(sum(priced), ".4f")
        # "Made a call" reuses the same prompt_tokens > 0 notion as the cache
        # line above, rather than inventing a second one. A row that made no
        # call (a locally decided reply, never sent to a model) is not a gap
        # in pricing and must not count against the total as though it were.
        if len(priced) < len(calls):
            cost_line += f" across {len(priced)} of {len(calls)} priced calls"
    else:
        # No row carried a price, so no figure is honest here. Summing to zero
        # would print a confident dollar amount for an unmeasured run.
        cost_line = "total cost: unavailable, pricing incomplete"

    decisions = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    lines = [
        "decisions: " + (decisions or "none"),
        f"plugs: {plugs}/{len(replies)} replies contain a configured plug marker"
        + (f" OVER plug_cap {plug_cap}" if over_cap else ""),
        f"cache: {warm}/{len(calls)} calls hit the prompt cache",
        cost_line,
    ]
    # Repetition is a property of the drafts, so only rows that produced one.
    lines += [f"repetition: {flag}" for flag in find_repetition(replies)]
    return "\n".join(lines)
