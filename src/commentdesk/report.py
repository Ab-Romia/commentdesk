# SPDX-License-Identifier: Apache-2.0
"""Measure a run. Change nothing about it.

Cost is reported in USD only. There is no currency conversion here, because
converting multiplies two numbers that both decay, the token rates and the
exchange rate, and the product reads more precise than either of its inputs.
"""

from __future__ import annotations

from commentdesk.sanitize import find_repetition, is_plug

# Without all three, the call cannot be priced at all.
REQUIRED_PRICING = ("input_per_mtok", "cached_per_mtok", "output_per_mtok")


def estimate_cost(usage: dict, model_cfg: dict) -> float | None:
    """Cost of one call in USD, or None when the rates are not fully known.

    None rather than zero, always. A blank cost column reads as "not known",
    which is true. A zero reads as "this call was free", which is a claim and a
    wrong one, and a bake off entry that inherits no pricing would print it on
    every row of the comparison.
    """
    pricing = model_cfg.get("pricing") or {}
    if not all(key in pricing for key in REQUIRED_PRICING):
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
        + usage["cache_write_tokens"] * pricing.get("cache_write_per_mtok", 0)
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

    priced = [r for r in rows if str(r.get("cost_usd") or "").strip()]
    if priced:
        total = sum(float(r["cost_usd"]) for r in priced)
        cost_line = "total cost: $" + format(total, ".4f")
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
