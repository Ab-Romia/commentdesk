# SPDX-License-Identifier: Apache-2.0
import re
from html.parser import HTMLParser

from commentdesk.render.review_html import (
    blind_label,
    label_paths,
    load_row_sets,
    render_review,
)


def make_row(**over):
    """A row shaped exactly as the pipeline writes it, so the test data cannot
    drift away from the CSV the page is asked to read."""
    row = {
        "id": "1",
        "platform": "video-site",
        "author": "sam",
        "comment": "how much is it",
        "post_title": "foraging clip",
        "decision": "reply",
        "reason": "direct question about price",
        "reply": "it is eighteen dollars",
        "model": "test/model-small",
        "prompt_tokens": "1000",
        "cached_tokens": "900",
        "cache_write_tokens": "0",
        "completion_tokens": "20",
        "cost_usd": "0.000100",
        "error": "",
    }
    row.update(over)
    return row


class Tags(HTMLParser):
    """Collects every start tag with its parsed attributes.

    Asserting on parsed attributes rather than on substrings of the output is the
    point: the parser unescapes attribute values, so a value that survives the
    round trip intact is a value that stayed inside its own attribute.
    """

    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def parse(page):
    tags = Tags()
    tags.feed(page)
    return tags.tags


def test_every_content_cell_carries_dir_auto():
    page, _ = render_review([("run", [make_row(id="1"), make_row(id="2")])], title="Review")
    cells = [attrs for tag, attrs in parse(page) if tag == "td"]
    assert len(cells) == 2 * 10, "expected one cell per column per row"
    assert all(attrs.get("dir") == "auto" for attrs in cells)


def test_hostile_values_stay_inside_their_attributes():
    # The regression the source project shipped and then fixed: the decision was
    # interpolated into a class attribute without escaping, so a CSV cell holding a
    # double quote closed the attribute and everything after it parsed as markup.
    rows = [make_row(decision='reply" onmouseover="x', id='9" autofocus="')]
    page, _ = render_review([("run", rows)], title="Review")
    tags = parse(page)
    names = {name for _, attrs in tags for name in attrs}
    assert "onmouseover" not in names
    assert "autofocus" not in names
    body_rows = [attrs for tag, attrs in tags if tag == "tr" and "data-id" in attrs]
    assert len(body_rows) == 1
    assert body_rows[0]["data-id"] == '9" autofocus="'
    assert body_rows[0]["class"] == 'row reply" onmouseover="x'


def test_markup_in_a_reply_is_escaped_in_the_cell():
    rows = [make_row(reply='say "hi" <b>now</b> & mean it')]
    page, _ = render_review([("run", rows)], title="Review")
    assert "<b>now</b>" not in page
    assert "&lt;b&gt;now&lt;/b&gt;" in page
    assert "&quot;hi&quot;" in page
    assert "&amp; mean it" in page


def test_blind_mode_relabels_the_sets_and_returns_the_key():
    page, key = render_review(
        [("orchid-mini", [make_row()]), ("swift-8b", [make_row()])], title="Comparison", blind=True
    )
    assert key == {"A": "orchid-mini", "B": "swift-8b"}
    assert "Set A" in page and "Set B" in page
    assert "orchid-mini" not in page
    assert "swift-8b" not in page
    # The model column names the source the letters exist to hide, so blind mode
    # drops it. Leaving it in would undo the blinding one column to the right.
    assert "test/model-small" not in page


def test_blind_mode_prints_no_cost_figure_and_plain_mode_still_does():
    """Cost names the source as surely as the model column does.

    The three totals this project measured are published per model in
    docs/bakeoff.md, so a reader of the repository's own documentation can undo
    the blinding from the page in seconds. Even with no table to consult, a route
    with cached prefix pricing lands an order of magnitude below one without, and
    a scorer who notices that cannot un-notice it. The author of this repository
    scored a blind page, read the cost lines, and used them to break a tie between
    two sources he had judged equal, which is the failure this pins.

    The decision tally is not the same kind of thing and stays: how many comments
    a source replied to, skipped and escalated is part of what a scorer is judging.
    """
    rows = [make_row(id="1"), make_row(id="2", decision="skip", cost_usd="")]
    blind, _ = render_review([("orchid-mini", rows)], title="Comparison", blind=True)
    assert "total cost" not in blind
    assert '<p class="cost"' not in blind
    # These rows quote no price of their own, so any dollar figure on the page came
    # from the renderer. A real page carries the product's price inside replies.
    assert re.search(r"\$\s*\d", blind) is None, "a cost figure survived on a blind page"
    assert "carry no cost figure" not in blind
    # The note explains a figure that is no longer on the page, and a note supplied
    # with --currency-note is one more place a source name can be typed by hand.
    assert "point-in-time" not in blind
    assert "2 comments: reply=1, skip=1" in blind

    plain, _ = render_review([("orchid-mini", rows)], title="Comparison")
    assert "total cost: $0.0001" in plain
    assert "1 of 2 rows carry no cost figure" in plain


def test_without_blind_the_key_is_empty_and_the_source_is_named():
    page, key = render_review([("run-a", [make_row()])], title="Review")
    assert key == {}
    assert "run-a" in page
    assert "test/model-small" in page


def test_draft_banner_is_there_by_default_and_gone_when_approved():
    draft, _ = render_review([("run", [make_row()])], title="Review")
    assert "DRAFT, NOT APPROVED" in draft
    approved, _ = render_review([("run", [make_row()])], title="Review", approved=True)
    assert "DRAFT" not in approved


def test_blind_labels_run_past_z_without_a_ceiling():
    assert blind_label(0) == "A"
    assert blind_label(25) == "Z"
    assert blind_label(26) == "AA"
    assert blind_label(27) == "AB"
    assert blind_label(51) == "AZ"
    assert blind_label(52) == "BA"


def test_duplicate_file_stems_get_distinct_headings():
    labels = label_paths(["first/review.csv", "second/review.csv", "second/review.csv"])
    assert labels == ["review", "second/review", "second/review (2)"]


def test_load_row_sets_reads_a_csv_written_with_a_byte_order_mark(tmp_path):
    path = tmp_path / "review.csv"
    path.write_text("id,comment,decision\n1,hello,reply\n", encoding="utf-8-sig")
    sets = load_row_sets([path])
    assert sets[0][0] == "review"
    # Without utf-8-sig the first key keeps the byte order mark in front of it and
    # every id column reads as blank.
    assert sets[0][1] == [{"id": "1", "comment": "hello", "decision": "reply"}]


def test_tally_and_cost_report_rows_that_carry_no_price():
    rows = [
        make_row(id="1", cost_usd="0.0010"),
        make_row(id="2", cost_usd=""),
        make_row(id="3", cost_usd="0.0020", decision="skip"),
    ]
    page, _ = render_review([("run", rows)], title="Review")
    assert "3 comments: reply=2, skip=1" in page
    assert "total cost: $0.0030" in page
    assert "1 of 3 rows carry no cost figure" in page


def test_currency_note_is_always_present_and_can_be_replaced():
    page, _ = render_review([("run", [make_row()])], title="Review")
    assert "point-in-time" in page
    assert "USD" in page
    custom, _ = render_review(
        [("run", [make_row()])],
        title="Review",
        currency_note="Rates read on 2026-07-30, point-in-time.",
    )
    assert "Rates read on 2026-07-30, point-in-time." in custom


def test_page_is_print_ready_with_no_generation_step():
    page, _ = render_review([("run", [make_row()])], title="Review")
    assert "@media print" in page
    assert "@page" in page
    assert page.startswith("<!doctype html>")
