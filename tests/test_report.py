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


def test_a_non_numeric_rate_returns_none_and_never_crashes():
    """A quoted rate from a config typo (`input_per_mtok = "1.0"`) must be
    treated the same as a missing one: None, not a TypeError two lines later
    when the string meets a float, and not a silently wrong price. A bool
    must not count as numeric either, since True would otherwise price a
    call at 1.0 per million tokens rather than being caught as the non-rate
    it is."""
    string_rate = {**PRICING, "input_per_mtok": "1.0"}
    assert estimate_cost(USAGE, {"pricing": string_rate}) is None
    none_rate = {**PRICING, "cached_per_mtok": None}
    assert estimate_cost(USAGE, {"pricing": none_rate}) is None
    bool_rate = {**PRICING, "output_per_mtok": True}
    assert estimate_cost(USAGE, {"pricing": bool_rate}) is None
    # Optional, but if present it is billed the same as the required three,
    # so a bad value here is exactly as disqualifying as one of those.
    bad_cache_write = {**PRICING, "cache_write_per_mtok": "1.25"}
    assert estimate_cost(USAGE, {"pricing": bad_cache_write}) is None


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
    # Every row that made a call is priced, so the common case stays clean.
    assert "priced calls" not in report


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
        row(
            id="1",
            decision="reply",
            reply="Here you go",
            prompt_tokens=29150,
            cost_usd="0.0100",
        ),
        row(
            id="2",
            decision="reply",
            reply="Glad it helped",
            prompt_tokens=29150,
            cost_usd="",
        ),
    ]
    report = build_report(rows, plug_cap=0.75, markers=MARKERS)
    assert "$0.0100" in report
    # One of the two rows that made a call has no price, so the total must
    # say it covers only that one rather than reading as a complete total.
    assert "across 1 of 2 priced calls" in report


def test_a_real_zero_cost_counts_as_priced_not_blank():
    """0.0 is a real answer: a call, or a locally decided row, that truly cost
    nothing. `value or ""` would treat it as falsy and drop it to blank, which reads
    as unpriced rather than priced-at-zero.

    Every row is a float here, and 0.0 is the only row. The earlier version of this
    test paired a 0.0 row with a "0.0100" row and asserted "$0.0100", which passes
    with the 0.0 row dropped entirely and so proved nothing about the behaviour it
    names. One row, and the total has to be the figure only that row can produce.
    """
    rows = [row(id="1", decision="reply", reply="Here you go", prompt_tokens=29150, cost_usd=0.0)]
    report = build_report(rows, plug_cap=0.75, markers=MARKERS)
    assert "total cost: $0.0000" in report
    assert "unavailable" not in report
    assert "priced calls" not in report
    # And the qualifier stays off when a real zero sits beside a real figure.
    rows.append(
        row(
            id="2", decision="reply", reply="Glad it helped", prompt_tokens=29150, cost_usd="0.0100"
        )
    )
    both = build_report(rows, plug_cap=0.75, markers=MARKERS)
    assert "$0.0100" in both
    assert "priced calls" not in both


@pytest.mark.parametrize("figure", ["nan", "inf", "-inf", "NaN", "Infinity"])
def test_a_non_finite_cost_is_unpriced_rather_than_printed(figure):
    """`total cost: $nan` is not a figure, and one inf makes a whole run's total inf.
    Both are spellable in TOML as a rate and both survive float(), so neither is
    caught by anything that only asks whether the cell parses."""
    rows = [
        row(id="1", decision="reply", reply="Here you go", prompt_tokens=29150, cost_usd=figure),
        row(id="2", decision="reply", reply="Glad it helped", prompt_tokens=29150, cost_usd="0.01"),
    ]
    report = build_report(rows, plug_cap=0.75, markers=MARKERS)
    assert "nan" not in report.lower()
    assert "inf" not in report.lower()
    assert "$0.0100" in report
    assert "across 1 of 2 priced calls" in report


def test_an_unreadable_cost_is_unpriced_rather_than_a_crash():
    """A review CSV is hand-editable, which is the whole point of it, so a cell that
    holds a word has to be a row this summary skips rather than an exception at the
    end of a long run. render/review_html.py already behaved this way; this module
    raised ValueError, and the two disagreeing was the finding."""
    rows = [
        row(id="1", decision="reply", reply="Here you go", prompt_tokens=29150, cost_usd="abc"),
        row(id="2", decision="reply", reply="Glad it helped", prompt_tokens=29150, cost_usd="0.01"),
    ]
    report = build_report(rows, plug_cap=0.75, markers=MARKERS)
    assert "$0.0100" in report
    assert "across 1 of 2 priced calls" in report


@pytest.mark.parametrize("rate", [float("nan"), float("inf")])
def test_a_non_finite_rate_prices_nothing(rate):
    """nan and inf are both TOML float literals, so `input_per_mtok = nan` is a rate
    an operator can write. Neither is a price, and either one silently poisons every
    figure downstream instead of raising."""
    assert estimate_cost(USAGE, {"pricing": {**PRICING, "input_per_mtok": rate}}) is None
    assert estimate_cost(USAGE, {"pricing": {**PRICING, "cache_write_per_mtok": rate}}) is None


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
