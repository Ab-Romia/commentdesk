# The comments file

`commentdraft run` and `commentdraft bakeoff` read one CSV. This page is the whole
format: every column the engine reads, which ones matter, and what happens to
everything else.

```csv
id,platform,author,comment,post_title
1,video-site,sam,how much does it cost,Ten wild greens
2,video-site,,first,Ten wild greens
3,photo-site,jo,does it cover mushrooms,Mushrooms for beginners
```

`examples/field-guide-book/comments.csv` and `examples/sourdough-course/comments.csv`
are both real files in this shape, and
`tests/fixtures/nazzef-kit-ar/comments.csv` is the same shape written in Arabic.

## Where the file comes from

Two ways, and the format is the same either way.

Export it yourself, from whatever the platform gives you, and keep the five columns
below. Or let `commentdraft pull` write it:

```bash
commentdraft pull --config config.toml --out comments.csv --state pull-state.json
commentdraft run  --config config.toml --comments comments.csv --out out
```

`pull` reads the platform named in the `[source]` table of your config and writes
exactly these columns, so nothing needs editing between the two commands. It needs a
read credential and no write credential at all. `--state` is what stops a scheduled
pull from writing the same comment twice; `docs/configuration.md` covers the table,
the flags, and the cases where a duplicate is still possible.

A pull that found nothing new writes the header and no rows, and `run` over that file
refuses it by name rather than drafting nothing quietly.

## The columns

| Column | Required | What it does |
|---|---|---|
| `comment` | **yes** | the text the model answers. A row whose comment is empty after stripping is decided locally as `skip`, with no call and no cost. |
| `id` | no | copied to the output row and printed in the run log, so you can find one row again in a file of three hundred. Any string. |
| `platform` | no | becomes one line of the user message, `Platform: <value>`, and appears in the review page's Platform column. It selects nothing: one run uses one config and one call to action style whatever this column says. |
| `author` | no | when present, the comment is introduced as `Comment from <author>:`. When absent, that clause is omitted rather than filled with a stand-in. See below. |
| `post_title` | no | becomes one line of the user message, `Post title: <value>`, and appears in the review page under the heading `Context`. It is whatever the comment sat under: a video, a post, a thread, an issue. |

Every other column is read and dropped. A spreadsheet export with fifteen columns of
platform metadata needs no cleaning first; the five above are taken and the rest are
ignored, including on the way out. The output CSV is written from
`engine.OUT_FIELDS`, not from your header row.

## `author` is optional on purpose

It is personal data in a real export, and many operators strip it before the file
leaves their machine. An absent author changes the request: the comment is introduced
as `Comment:` rather than `Comment from <name>:`. Nothing invents a placeholder name,
because a stand-in teaches the model to address somebody who is not there.

## `post_title`, and the header it used to be

The canonical name is `post_title`. `video_title` is read as a silent alias, so an
export written before the rename still carries its titles through, and a file that
somehow has both is read from `post_title`.

The rename is not cosmetic. Nothing in this engine knows what medium a comment came
from: the label sent to the model has always been `Post title:` and the review page
heading has always been `Context`. The CSV column was the one place a single medium
was still named, and it is the place an operator actually types.

## The header row

- A header spelled `Comment`, or anything else that is not exactly `comment`, is
  **refused** with a message naming the columns that were found. Without that check
  every row reads as empty, every row is skipped, and the run exits 0 having answered
  nothing, which is the failure that looks most like success.
- The file is read as `utf-8-sig`, so the invisible marker a spreadsheet writes before
  the first header is dropped instead of becoming part of that column's name.
- A file that is not UTF-8 at all is refused with a message saying to save it as CSV
  UTF-8. That is what a spreadsheet's plain "CSV" export produces on a Windows
  machine, so it is worth knowing before it happens.
- An empty file is refused before the header is judged, so a zero byte file gets the
  message that names its actual problem.

## What comes back

`run` writes `out/review.csv`: your five columns, then `decision`, `reason`, `reply`,
`model`, the four token counters, `cost_usd` and `error`. `commentdraft review` renders
that file, or several of them, into `out/review.html`.

`cost_usd` is blank rather than zero whenever no call was billed, which covers both an
empty comment decided locally and a call that failed before the provider reported any
usage. Blank means not known. Zero would mean free, and that is a claim.

The review page reads a CSV a person may have edited by hand, columns removed and
all, so editing `reply` in a spreadsheet and re-rendering is a supported way to work.
Re-running `run` over the same `--out`, on the other hand, replaces `review.csv`
including your edits; `docs/limits.md` says so under its own heading.
