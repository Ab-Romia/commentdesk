# SPDX-License-Identifier: Apache-2.0
"""Render one or more result CSVs into a single page for a person to review.

This is the only reviewer artefact. It is print ready through an @media print
block, so handing someone a document needs no PDF step, no headless browser and
no second template that can drift out of step with this one.

Every content cell carries dir="auto", and nothing else in the file sets a
direction. The browser then reads the direction out of the text in each cell,
which is what lets one page hold rows in any script, mixed together, with no
configuration anywhere in the tool. Setting a direction on the page and
overriding it per cell reaches the same result for one language and the wrong
result for the next one.
"""

from __future__ import annotations

import csv
import html
from pathlib import Path

from commentdraft.report import parse_cost

# Display order and headings. Deliberately not engine.OUT_FIELDS: the page must
# render a CSV that a person has edited by hand, columns removed and all, and the
# token counters belong in the CSV rather than in front of a reviewer.
COLUMNS = [
    ("id", "#"),
    ("platform", "Platform"),
    ("author", "Author"),
    ("post_title", "Context"),
    ("comment", "Comment"),
    ("decision", "Decision"),
    ("reason", "Reason"),
    ("reply", "Reply"),
    ("model", "Model"),
    ("error", "Error"),
]

# Dropped when blind=True. The model id names the very thing the neutral labels
# exist to hide, so printing it would undo the blinding one column to the right.
BLIND_HIDDEN = {"model"}

DRAFT_BANNER = (
    "DRAFT, NOT APPROVED. Every reply below was drafted by software and has been "
    "approved by nobody. Read each one, edit what needs editing, and take "
    "editorial responsibility for it before it goes anywhere."
)

DEFAULT_CURRENCY_NOTE = (
    "Costs are USD, computed from the usage the provider billed on this run "
    "rather than from a rate card. They are point-in-time observations and they "
    "go stale, so check them before quoting them. No conversion to any other "
    "currency is applied here: converting would multiply two numbers that both "
    "decay, and the result would look more precise than either input."
)

NEVER_POSTED_NOTE = "Nothing on this page has been posted anywhere. This tool has no way to post."

STYLE = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
       margin: 1.5rem; background: #fafafa; color: #1a1a1a; line-height: 1.6; }
h1 { font-size: 1.4rem; margin: 0 0 1rem; }
h2 { font-size: 1.1rem; margin: 2.4rem 0 .5rem; }
p { margin: .35rem 0; }
.banner { border: 2px solid #b00020; background: #fff1f1; color: #6b0016;
          padding: .8rem 1rem; border-radius: 4px; font-weight: 600;
          max-width: 62em; }
.tally, .cost { font-variant-numeric: tabular-nums; color: #333; }
.note { color: #555; font-size: .9rem; max-width: 62em; }
table { border-collapse: collapse; width: 100%; background: #fff; }
th, td { border: 1px solid #d8d8d8; padding: .5rem .6rem; vertical-align: top;
         font-size: .95rem; }
/* Logical, not left or right, so a heading follows the cell under it. */
th { background: #eeeeee; text-align: start; }
/* Colour is a second channel and only a second channel. The decision word is in
   the row, so the page still reads correctly in greyscale, on a photocopy, and
   to a reader who does not see these hues apart. */
tr.reply { background: #f1f8f2; }
tr.skip { background: #f7f7f7; }
tr.escalate { background: #fdf1f1; }
tr.error { background: #fff6ec; }
@page { size: A4; margin: 14mm; }
@media print {
  body { margin: 0; background: #ffffff; font-size: 10pt; }
  table { font-size: 9pt; }
  .banner { border-width: 2pt; }
  h2 { break-after: avoid; page-break-after: avoid; }
  thead { display: table-header-group; }
  tr { break-inside: avoid; page-break-inside: avoid; }
}
"""


def _esc(value) -> str:
    """One escaping rule for every interpolated value, attributes included.

    quote=True is not decoration here. An id or a decision lands inside a quoted
    attribute, and an unescaped double quote there closes the attribute early and
    hands whatever follows to the parser as markup. These values arrive from a CSV
    that a person may have edited, so they are untrusted input even when the run
    that produced them was not.
    """
    return html.escape("" if value is None else str(value), quote=True)


def blind_label(index: int) -> str:
    """A, B, ... Z, AA, AB, and onward.

    ASCII letters whatever language the rows are written in, so the label carries
    no hint about the set it names, and no fixed alphabet means no ceiling on how
    many sets can be compared at once.
    """
    if index < 0:
        raise ValueError("blind label index must not be negative")
    out = ""
    n = index
    while True:
        out = chr(ord("A") + n % 26) + out
        n = n // 26 - 1
        if n < 0:
            return out


def load_rows(path) -> list[dict]:
    """Read one result CSV.

    utf-8-sig because spreadsheets write a byte order mark, and restval="" so a
    short or hand-edited row arrives with empty cells rather than None, which would
    crash the summary instead of naming the file that is wrong.
    """
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, restval=""))


def label_paths(paths) -> list[str]:
    """A readable and unique heading for each input file.

    Two inputs with the same stem would collapse into one heading and print the
    last file's tally under both. The parent directory name is the useful hint,
    since that is usually what differs; a counter is the fallback for when the
    parent collides too.
    """
    labels: list[str] = []
    used: set[str] = set()
    for path in paths:
        p = Path(path)
        name = p.stem
        if name in used and p.parent.name:
            name = f"{p.parent.name}/{name}"
        base, n = name, 2
        while name in used:
            name = f"{base} ({n})"
            n += 1
        used.add(name)
        labels.append(name)
    return labels


def load_row_sets(paths) -> list[tuple[str, list[dict]]]:
    """Load every input into the (label, rows) pairs render_review expects."""
    labels = label_paths(paths)
    return [(label, load_rows(path)) for label, path in zip(labels, paths, strict=True)]


def decision_counts(rows) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = (row.get("decision") or "").strip() or "(blank)"
        counts[key] = counts.get(key, 0) + 1
    return counts


def total_cost(rows) -> tuple[float, int]:
    """Total billed cost, and how many rows carried no usable figure.

    The second number is reported rather than swallowed. A cost cell is empty
    whenever the model config had incomplete pricing, and a total that quietly
    skips those rows reads as complete when it is not.

    parse_cost is shared with report.build_report rather than reimplemented here.
    Two implementations of one job is how the two ended up disagreeing about what
    unpriced means: this one counted `nan` as a real figure and printed a nan total,
    the other crashed on an unreadable one. There is one rule now and both use it.
    """
    total = 0.0
    unpriced = 0
    for row in rows:
        cost = parse_cost(row.get("cost_usd"))
        if cost is None:
            unpriced += 1
        else:
            total += cost
    return total, unpriced


def render_review(
    row_sets: list[tuple[str, list[dict]]],
    *,
    title: str,
    approved: bool = False,
    blind: bool = False,
    currency_note: str = "",
) -> tuple[str, dict[str, str]]:
    """Build the review page. Returns (html, blind_key).

    blind_key maps each neutral label to the source it stands for, and is empty
    when blind is False. It is returned rather than written so that the caller
    decides where it lands, which is what keeps the key out of the page itself.

    blind=True withholds three things: the source name in each heading, the model
    column, and the cost line with the currency note under it. What it cannot
    withhold is text a model wrote about itself, in a reply, in a reason, or in an
    error string that quotes the request back. Nothing here reads those cells for
    a name, and a scorer should expect the occasional one.
    """
    columns = [c for c in COLUMNS if not (blind and c[0] in BLIND_HIDDEN)]
    key: dict[str, str] = {}
    parts = [
        "<!doctype html>",
        '<html lang="en">',
        '<head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{_esc(title)}</title>",
        f"<style>{STYLE}</style>",
        "</head>",
        "<body>",
        f"<h1>{_esc(title)}</h1>",
    ]
    if not approved:
        parts.append(f'<p class="banner" role="alert">{_esc(DRAFT_BANNER)}</p>')

    for index, (source, rows) in enumerate(row_sets):
        if blind:
            label = blind_label(index)
            key[label] = source
            heading = f"Set {label}"
        else:
            heading = source
        parts.append(f"<h2>{_esc(heading)}</h2>")

        tally = ", ".join(f"{name}={n}" for name, n in sorted(decision_counts(rows).items()))
        line = f"{len(rows)} comments" + (f": {tally}" if tally else "")
        parts.append(f'<p class="tally">{_esc(line)}</p>')

        # No cost figure on a blind page. Cost identifies a source as surely as the
        # model column does: the totals this project measured are published per model
        # in docs/bakeoff.md, so a reader of this repository can undo the blinding
        # from the page in seconds, and even with no table to consult a route with
        # cached prefix pricing lands an order of magnitude below one without. A
        # scorer who reads that cannot un-read it. It has already decided a tie here.
        # The tally above stays, because how many comments a source replied to,
        # skipped and escalated is part of what a scorer is judging. Cost is not, and
        # it belongs to the phase after the key file is opened.
        if not blind:
            total, unpriced = total_cost(rows)
            cost_line = f"total cost: ${total:.4f}"
            if unpriced:
                cost_line += f" ({unpriced} of {len(rows)} rows carry no cost figure)"
            parts.append(f'<p class="cost">{_esc(cost_line)}</p>')

        parts.append(
            "<table><thead><tr>"
            + "".join(f'<th scope="col">{_esc(head)}</th>' for _, head in columns)
            + "</tr></thead><tbody>"
        )
        for row in rows:
            decision = (row.get("decision") or "").strip()
            cells = "".join(
                f'<td dir="auto">{_esc(row.get(field, ""))}</td>' for field, _ in columns
            )
            parts.append(
                f'<tr class="row {_esc(decision)}" data-id="{_esc(row.get("id", ""))}">{cells}</tr>'
            )
        parts.append("</tbody></table>")

    # The currency note explains the figure the branch above withholds, so a blind
    # page carries neither. It is also the one line on the page an operator writes
    # by hand, and a hand-written note about rates is a natural place to type the
    # name of the route those rates belong to.
    if not blind:
        parts.append(f'<p class="note">{_esc(currency_note or DEFAULT_CURRENCY_NOTE)}</p>')
    parts.append(f'<p class="note">{_esc(NEVER_POSTED_NOTE)}</p>')
    parts.append("</body></html>")
    return "\n".join(parts), key
