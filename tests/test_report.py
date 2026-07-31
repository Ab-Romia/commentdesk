# SPDX-License-Identifier: Apache-2.0
"""Run measurement: per call cost, and the end of run summary."""

import pytest

from commentdesk.report import build_report, estimate_cost

PRICING = {
    "input_per_mtok": 1.0,
    "cached_per_mtok": 0.1,
    "output_per_mtok": 6.0,
    "cache_write_per_mtok": 1.25,
}
USAGE = {
    "prompt_tokens": 29150,
    "completion_tokens": 120,
    "cached_tokens": 29000,
    "cache_write_tokens": 0,
}


def test_cached_input_is_billed_at_its_own_rate():
    cost = estimate_cost(USAGE, {"pricing": PRICING})
    expected = (150 * 1.0 + 29000 * 0.1 + 120 * 6.0) / 1e6
    assert cost == pytest.approx(expected)


def test_cache_writes_are_counted():
    """Writing the cache is billed at a premium on some routes. Leaving it out
    understates the first call of every run, which is the expensive one."""
    base = estimate_cost(USAGE, {"pricing": PRICING})
    assert base is not None  # PRICING is complete, so this call always prices.
    written = {**USAGE, "cache_write_tokens": 29000}
    assert estimate_cost(written, {"pricing": PRICING}) == pytest.approx(base + 29000 * 1.25 / 1e6)
    # Absent means zero for this rate alone, because the three required rates are
    # what decide whether the call can be priced at all.
    lean = {k: v for k, v in PRICING.items() if k != "cache_write_per_mtok"}
    assert estimate_cost(written, {"pricing": lean}) == pytest.approx(base)


def test_incomplete_pricing_returns_none_and_never_zero():
    """None, not zero. A blank column says the rate is unknown, which is true.
    A zero says the call was free, which is a claim, and a false one."""
    assert estimate_cost(USAGE, {}) is None
    assert estimate_cost(USAGE, {"pricing": {}}) is None
    assert estimate_cost(USAGE, {"pricing": None}) is None
    assert estimate_cost(USAGE, {"pricing": {"input_per_mtok": 1.0}}) is None
    partial = {k: v for k, v in PRICING.items() if k != "output_per_mtok"}
    assert estimate_cost(USAGE, {"pricing": partial}) is None


MARKERS = ["example.com/field-guide", "link in bio"]


def row(**kw):
    """One output row with every field the report reads, defaulted to empty."""
    base = {
        "id": "",
        "decision": "skip",
        "reply": "",
        "prompt_tokens": 0,
        "cached_tokens": 0,
        "cost_usd": "",
    }
    return base | kw


def test_report_counts_decisions_the_cache_and_the_cost():
    rows = [
        row(
            id="1",
            decision="reply",
            reply="Here you go",
            prompt_tokens=29150,
            cached_tokens=29000,
            cost_usd="0.0100",
        ),
        row(
            id="2",
            decision="reply",
            reply="Glad it helped",
            prompt_tokens=29150,
            cached_tokens=0,
            cost_usd="0.0200",
        ),
        row(id="3", decision="skip", prompt_tokens=29150, cached_tokens=29000, cost_usd="0.0050"),
        row(
            id="4", decision="escalate", prompt_tokens=29150, cached_tokens=29000, cost_usd="0.0050"
        ),
    ]
    report = build_report(rows, plug_cap=0.75, markers=MARKERS)
    assert "reply=2" in report
    assert "skip=1" in report
    assert "escalate=1" in report
    assert "cache: 3/4" in report
    assert "$0.0400" in report


def test_rows_that_came_back_through_a_csv_are_read_the_same_way():
    """The engine hands over ints. A rerun off review.csv hands over strings.
    Both must produce the same cache line rather than a TypeError."""
    rows = [
        row(
            id="1",
            decision="reply",
            reply="Here you go",
            prompt_tokens="29150",
            cached_tokens="29000",
            cost_usd="0.0100",
        ),
        row(
            id="2",
            decision="reply",
            reply="Glad it helped",
            prompt_tokens="29150",
            cached_tokens="0",
            cost_usd="0.0200",
        ),
    ]
    assert "cache: 1/2" in build_report(rows, plug_cap=0.75, markers=MARKERS)


def test_the_plug_alarm_fires_above_the_cap_and_not_at_it():
    rows = [
        row(id="1", decision="reply", reply="you can get it at https://example.com/field-guide"),
        row(id="2", decision="reply", reply="Sleep on it and see how it goes"),
    ]
    assert "1/2" in build_report(rows, plug_cap=0.4, markers=MARKERS)
    assert "OVER" in build_report(rows, plug_cap=0.4, markers=MARKERS)
    # Exactly at the cap is not over the cap, or the threshold means nothing.
    assert "OVER" not in build_report(rows, plug_cap=0.5, markers=MARKERS)
    assert "OVER" not in build_report(rows, plug_cap=0.6, markers=MARKERS)


def test_a_run_with_no_replies_does_not_divide_by_zero():
    """plug_cap 0.0 is the meanest case: any division at all would produce a
    ZeroDivisionError, and any sloppy comparison would raise a false alarm."""
    rows = [
        row(id="1", decision="skip", prompt_tokens=29150, cached_tokens=0),
        row(id="2", decision="escalate", prompt_tokens=29150, cached_tokens=0),
    ]
    report = build_report(rows, plug_cap=0.0, markers=MARKERS)
    assert "plugs: 0/0" in report
    assert "OVER" not in report
    assert "cache: 0/2" in report
    # An empty run still produces a report rather than an exception.
    empty = build_report([], plug_cap=0.0, markers=MARKERS)
    assert "cache: 0/0" in empty
    assert "plugs: 0/0" in empty


def test_an_unpriced_run_prints_no_dollar_figure():
    """Incomplete pricing leaves cost_usd blank on every row, and the report must
    say the total is unavailable rather than total up to a confident zero."""
    rows = [
        row(
            id="1", decision="reply", reply="Here you go", prompt_tokens=29150, cached_tokens=29000
        ),
        row(id="2", decision="skip", prompt_tokens=29150, cached_tokens=29000),
    ]
    report = build_report(rows, plug_cap=0.75, markers=MARKERS)
    assert "$" not in report
    assert "unavailable" in report


def test_a_partly_priced_run_totals_only_the_rows_that_have_a_price():
    rows = [
        row(id="1", decision="reply", reply="Here you go", cost_usd="0.0100"),
        row(id="2", decision="reply", reply="Glad it helped", cost_usd=""),
    ]
    assert "$0.0100" in build_report(rows, plug_cap=0.75, markers=MARKERS)


def test_repetition_flags_are_appended_and_cover_replies_only():
    rows = [
        row(id="1", decision="reply", reply="That helps a lot, thank you"),
        row(id="2", decision="reply", reply="Glad it landed, thank you!"),
        row(id="3", decision="reply", reply="Did that answer it, thank you?"),
        # A skipped row has no draft to vary, so it must not join the count.
        row(id="4", decision="skip", reply="That helps a lot, thank you"),
    ]
    report = build_report(rows, plug_cap=0.75, markers=MARKERS)
    assert "repetition: closing 'you' repeats in rows 1, 2, 3" in report
