# commentdraft

Triage social-media comments from a CSV and draft grounded replies for a person to send.

[![CI][ci-badge]][ci-link]
[![PyPI][pypi-badge]][pypi-link]
[![Python][python-badge]][python-link]
[![License][license-badge]][license-link]

> **The one thing to know before anything else.** Nothing is published that a person
> has not approved, one reply at a time. Approval is not a setting, a default, or a
> dialog you can hold Enter through: it is a keystroke against one specific reply,
> taken immediately before that one reply is sent. There is no `--yes`, no `--all`,
> and no config key that changes it. Not defaulted off. Absent.

## What it is

- **A triage step.** Every comment is classified `reply`, `skip` or `escalate`, each
  with a one-line reason you can disagree with.
- **A drafting step tied to one document you supply.** That document is the only thing
  a draft may state as fact. A question it does not answer becomes `escalate`, not a
  guess.
- **A review artefact.** One table, one row per comment, carrying the decision, the
  reason and the draft alongside the platform, the author and the model that produced
  it. Cost appears once per file, as a total the run actually billed, not per row: the
  per-row token counts and cost live in the CSV underneath the page, not in front of a
  reviewer. You read it, edit what needs editing, and approve one reply at a time.

## Requirements

Python 3.11 or newer, and an API key for any OpenAI-compatible chat endpoint.

## Install

```bash
uv tool install commentdraft
uv tool install "commentdraft[pdf]"
```

The second adds the PDF knowledge source, which is an optional extra because it
pulls in a rendering library that a text knowledge file does not need. `pip install`
works the same way if you would rather not use uv.

To run an unreleased change, install from the repository instead:

```bash
uv tool install git+https://github.com/Ab-Romia/commentdraft.git
```

## The whole thing, end to end

The repository ships a worked example: a fictional foraging field guide, with its
knowledge file, its voice file, its worked examples, and a small comment file.

```bash
git clone https://github.com/Ab-Romia/commentdraft.git
cd commentdraft/examples/field-guide-book

export OPENROUTER_API_KEY="your key"      # or whatever [model].api_key_env names
commentdraft run    --config config.toml --comments comments.csv --out out
commentdraft review out/review.csv --out out
```

`run` writes `out/review.csv` and prints a run report: how many replies, skips and
escalates, what the run cost, and which drafts repeat each other. `review` turns the
CSV into `out/review.html`, which is the page below.

![The review page, headed "Reply review". A tally line reads "11 comments: escalate=4, reply=4, skip=3" above "total cost: $0.0006". Then one table with columns for number, platform, author, context, comment, decision, reason, reply, model and error. Rows tinted green were answered: a question about mushrooms answered from the source and pointed at the book, a price and place question answered with both, a direct question about whether a person or software writes the replies, answered with the configured disclosure sentence, and a Polish question about regional coverage answered in Polish. Rows tinted pink were escalated to a person and carry no draft: a shipping question, an unhappy buyer, a piracy report, and an allergy question. Untinted rows were skipped: a discount request, an accusation, and a request to convert the price into euros. A footer reads "Nothing on this page has been posted anywhere. Publishing is a separate step that asks you to approve each reply on its own, one at a time."](docs/img/review-page.png)

One table, one row per comment, carrying the decision, the reason, the draft reply and
the model that wrote it, plus one cost total for the whole file rather than a column of
per-row figures in front of a reviewer; the per-row token counts and costs stay in the
CSV underneath. Green rows were answered, pink rows go to a person, and the rest were
left alone. The three decisions are the product: what it declines to answer matters as
much as what it drafts.

Nothing on that page is mocked up. Every row is real output from the run written up in
`docs/bakeoff.md`, which put thirty comments through three models. Eleven of those rows
are shown here, chosen so that all three decisions and the awkward cases are visible at
once rather than the first seven rows, which all happen to be replies. Your own run
produces the same page from `out/review.csv` with whatever it measured.

That page was rendered with `--approved`. Without it, every page carries a red banner
saying the drafts were approved by nobody, and it stays until you pass the flag, which
you pass after reading every row and not before:

```bash
commentdraft review out/review.csv --out out --approved
```

Both of those commands read a CSV. You can export one yourself, or, once a config
names a platform to read, have `commentdraft pull` write it:

```bash
commentdraft pull --config config.toml --out comments.csv --state pull-state.json
commentdraft run  --config config.toml --comments comments.csv --out out
```

That is the loop end to end: pull, run, review, publish. `pull` needs a read
credential and nothing else. A config with a `[source]` table and no `[publish]`
table reads comments and drafts replies for them and cannot publish anything at
all, which is the posture to start in while a platform decides whether to grant a
write scope, and the posture some people should stay in.

`--state` is what keeps a scheduled pull from drafting the same comment twice: a
small JSON file holding every comment id pulled so far, and a comment already in it
is never written a second time. Without it, every pull writes every comment it can
see, every time, and the command says so rather than leaving it to a bill.
`docs/configuration.md` covers the table, the flags, and the cases where a duplicate
is still possible.

Two more things you will want on day one:

```bash
commentdraft chat --config config.toml    # one comment at a time, with the full trace
commentdraft ui   --config config.toml    # the same, in a page on 127.0.0.1 only
```

Both send one comment through the exact code a batch run uses and show the decision,
the draft, the token counts and the cost, without writing a CSV. `docs/writing-a-voice.md`
has a short section on using them to check an edit to your voice file before spending
on a full run.

And two you will want once:

```bash
commentdraft ingest  --config config.toml --pdf book.pdf --out knowledge.md
commentdraft bakeoff --config config.toml --comments comments.csv --out out
```

## Three concepts, and no fourth

| Concept | Where it lives | What it holds |
|---|---|---|
| Configuration | `config.toml` | what you sell, how it behaves, which model, what it costs |
| Knowledge | a text file you supply | the only thing a draft may state as fact |
| Voice | `prompts/voice.md`, `prompts/examples.md` | your rules and your worked examples, in your language |

The engine holds no copy in your language and none about your product. Everything a
reader of your replies perceives comes from your files, and you never open a `.py`
file to change it. No string literal under `src/` contains a non-ASCII character, and
a test walks the AST of every module to keep it that way.

The engine does hold English of its own, and it is machine scaffolding rather than
voice: the JSON output contract and the two instructions sent to a model, the review
page's fixed notices and column headings, the local test page's own button labels
and headings, the four lines of the run report, and the one reason string a locally
decided empty comment carries. That list is complete, it is written out in `docs/limits.md`
with who reads each item, and none of it enters a reply as your voice.

`tests/fixtures/nazzef-kit-ar` is a third product, config, voice, worked examples
and comments, written entirely in Arabic, and it passes the same acceptance tests as
the two English examples above. `docs/writing-a-voice.md` is the chapter to read next.

## What leaves your machine

Every comment and the whole knowledge document travel to whichever endpoint
`[model].base_url` names, as part of the request that drafts a reply. That is the one
place your data leaves the machine running commentdraft.

`load_config` refuses to start a run unless every model entry, the default one and
every `[[bakeoff.models]]` entry alike, sets `params.provider.data_collection = "deny"`
in its own table. That is an instruction sent with the request, not something this tool
can enforce once the request has left it: whether the endpoint honors it is between you
and whoever operates it. Nothing else about your product, your audience or their
comments leaves this machine: no telemetry, no analytics call, and no second server
this tool talks to.

## What it deliberately does not do

- **It does not queue, schedule, or send anything on its own.** One connector ships,
  for Facebook Pages, and reading and publishing through it are separate tables in
  the config holding separate credentials: `commentdraft pull` reads with the first
  and can write nothing at all. The code that sends exists in exactly one module,
  and reaching it costs one keystroke per reply. `commentdraft publish` shows you one
  comment and one draft at a time and waits: `y` sends that one, `e` opens it in
  `$EDITOR` and sends what comes back, `s` skips, `q` stops, and Enter does nothing
  at all. `commentdraft publish --dry-run` prints what each send would carry, asks
  for no keystroke, and needs no publish credential, so you can read it before
  granting any write scope anywhere.

  ```bash
  grep -rn --include='*.py' 'THE ONE SEND' src/
  ```

  returns exactly one line, on the statement that hands a reply to a connector,
  inside `_send_approved` in `src/commentdraft/approve.py`. The marker is the anchor
  rather than the filename on purpose: the version of this claim that read
  `--exclude=approve.py --exclude-dir=platforms` excluded the only two paths a send
  would ever live in, so it proved the send was not somewhere it had never been.
  `tests/test_guarantees.py::test_the_send_marker_appears_once_in_the_package_and_sits_on_the_send`
  asserts there is one and that it sits in that function.

  `tests/test_guarantees.py::test_the_only_reference_to_publish_reply_in_the_package_is_the_call_inside_the_gate`
  runs the version a grep cannot: it walks the AST of every module and fails the build
  if the send is named anywhere else, or named without being called, which is how
  `post = platform.publish_reply` would otherwise carry it into a loop. The tests
  beside it assert that every send sits inside a branch reached by a value that came
  out of the prompt itself, that no loop sits between that keystroke and the send,
  that the prompt has no default action and no conditional expression standing in for
  one, and that the config vocabulary is a frozen allowlist, so a key of any name that
  could stand in for a keystroke fails the build until somebody writes it down.

  Two properties are worth naming because they are what "approved" has to mean.
  The keystroke is read from the terminal after its input queue is discarded, so
  keys typed or pasted before a reply was on the screen approve nothing:
  `tests/test_typeahead.py` drives the real gate under a pty and asserts it. And the
  text shown to the reviewer and the text sent to the platform are one string rather
  than two that agree, so a reply cannot hide half of itself behind an escape
  sequence on the way past a reader.

  This replaces an older claim that no HTTP client existed anywhere. That was true,
  checkable, and about to stop being either. It was doing two jobs, and only one of
  them mattered: nothing reaches a platform that a person did not read and approve
  first. That one survives connectors intact, so it is the one that is enforced.
- **It does not retrieve.** The whole knowledge document goes into the cached prompt
  prefix. That is the right answer while the document fits the context window and the
  wrong one afterwards. `docs/architecture.md` says where the line is.
- **It does not evaluate models in general.** `commentdraft bakeoff` runs your own
  comments through several models and builds a blind judging page. That is the whole
  feature. If you want an evaluation harness with datasets, assertions and CI gates,
  use [promptfoo][promptfoo]. It is the right tool for that job and this is not trying
  to be it.
- **It does not check whether your facts are true.** `load_config` validates shape and
  never content. A wrong price travels straight through to a human reviewer, which is
  the correct place to catch it.
- **`plug_cap` is an alarm threshold.** It reports the share of replies matching one of
  your configured `plug_markers`, a case-insensitive substring test, and flags a run
  that goes over. It does not know what a link or a price looks like on its own; it
  only recognizes the exact markers you listed. Nothing stops mid-run. What holds the
  rate down is what you wrote in your voice file. `docs/limits.md` covers the false
  positives and false negatives that come with a substring test.

## Documentation

| File | What it covers |
|---|---|
| `docs/architecture.md` | the cached prefix, why there is no retrieval, and where that stops working |
| `docs/configuration.md` | every key `config.toml` accepts, which are required, and what each does |
| `docs/comments-csv.md` | the input CSV: every column, which are required, and what happens to the rest |
| `docs/writing-a-voice.md` | writing your rules and examples, in your language, placeholder by placeholder |
| `docs/sources.md` | adding a knowledge source handler |
| `docs/bakeoff.md` | comparing models blind, one measured run against the example, and one parameter that lies |
| `docs/platform-policy.md` | which clause each safety property exists for |
| `docs/limits.md` | what this cannot do, stated before you find out |
| `docs/platforms/index.md` | the eight platform guides, what each one costs to reach, and the order worth trying them in |
| `docs/platforms/facebook.md` | connecting a Facebook Page: scopes, tokens, the contested reply path, and what breaks |

## What this does, and what it does not do

commentdraft drafts, and publishes nothing that a person has not approved, one reply
at a time. Every draft leaves this tool as a row in a CSV and a card on an HTML page,
and the only way one reaches an audience is a person reading that specific reply and
pressing a key to send that specific reply. There is no batch, no queue and no
schedule: publishing thirty replies costs thirty keystrokes, which is the design and
not an oversight. `tests/test_guarantees.py::test_every_send_sits_inside_a_branch_an_explicit_keystroke_reaches`
fails the build on any arrangement that weakens it.

That person is responsible for what they send. The tool has no view on whether a draft
is accurate, appropriate, or permitted where they are about to publish it, and it is
not capable of forming one. `load_config` validates the shape of your configuration
and never its truth: a wrong price passes straight through, on purpose, to the
reviewer who can recognize it.

This is a design decision, not a missing feature. `docs/platform-policy.md` maps this
behavior, clause by clause, to the platform and legal provisions it was built to
satisfy; that mapping is not repeated here.

This project is not affiliated with, authorized by, maintained by, or endorsed by
Google, YouTube, Meta, Instagram, or TikTok. Platform names appear in this repository
only to cite a published policy clause or as an example configuration value. Anything
you publish with this tool's help is your responsibility, under the terms of whichever
platform you publish on.

## What you supply

You supply the source document. Everything a draft states as fact comes from it,
which makes it the single most important input and the one this project has the
least ability to check.

By pointing commentdraft at a document you confirm that you have the right to use it
this way: that you own it, licensed it, or are otherwise permitted to send its
contents to the model provider you have configured. The tool does not check
ownership, licensing, copyright status, or whether the document contains personal
data, and it cannot. commentdraft includes, distributes, and licenses no book, course,
or other work of its own; the example products in this repository are fictional,
written for this project, and not a real product for you to reuse.

The same applies to the comments you feed it. They were written by people. Exporting
them, sending them to a provider, and storing the output CSV are all processing
decisions you are making, under whatever law applies to you.

Two defaults exist to keep those inputs where you put them:

- Source text, PDFs and CSVs are gitignored by class rather than by filename, so an
  accidental commit takes deliberate effort. `knowledge/` and any `*.pdf` file are
  covered by that rule, and they should stay that way in any fork or deployment of
  this project.
- Every model entry is required to send `provider.data_collection = "deny"`, and a
  test asserts it on every entry. Whether the provider honors it is between you and
  the provider. The request is the part this project controls, and it makes that part
  unambiguous.

## Transparency

Drafts are written by software. Pretending otherwise is dishonest and, in a growing
number of jurisdictions, unlawful.

`bot_disclosure_text` is a required, non-empty setting: the exact sentence used when
someone asks whether a person wrote a reply. It is validated non-empty and there is
no evasive mode; an earlier version of this design had one and it was removed rather
than defaulted off, because a setting that exists is a setting somebody eventually
turns on.

A human reads every draft, edits it, and takes editorial responsibility for it before
anything is sent. Whether the disclosure sentence alone satisfies your obligations
depends on where you are and what you publish, and this README is not legal advice.
Any deployment obligation that follows from publishing a reply belongs to you, the
operator, not to this repository. `docs/platform-policy.md` maps each property here to
the specific clause it was built against, so you can check the reasoning rather than
trust this summary.

## About any cost figures

Any rate that appears in a config file or a document in this repository is a
point-in-time observation, dated where it appears, and never a quote. Providers change
pricing without notice, and a number that was true on the date it was written can be
wrong by the time you read it. Verify against your provider's current rates before you
plan around any figure here.

Cost per row is computed from the token counts the API actually returned, never from
an estimate, and it is left blank rather than set to zero when pricing is incomplete.
Blank is the truth. Zero is a claim.

The one set of measured figures this repository publishes is in `docs/bakeoff.md`: one
bake-off run against the shipped example on 2026-08-01, three models, with the command
that reproduces it and the same dating rule applied to every number in it.

## Where this came from

This started as a private commission. The person on the other end had a real product,
a real price and a real audience, and a public reply that quoted the wrong price or
invented a claim was a cost that landed on them, not on the tool. That is the entire
explanation for the parts of this design that look over-careful: the review page, the
disclosure line that is required and has no evasive setting, the refusal to answer
outside the source document, and a posting path that costs one keystroke per reply.

The client-specific parts are gone. The product, the language, the source document and
the platform credentials all stayed behind, and nothing here was copied forward from
them. What survived is the shape those constraints forced, which turned out to be the
useful part.

## Contributing

Read `CONTRIBUTING.md`. In short: tests first, no non-ASCII string literals under
`src/`, no posting path that is not gated behind a keystroke per reply, and no dash
typography in prose. `make check` runs what CI runs.

## License

Apache-2.0. See `LICENSE` and `NOTICE`.

[ci-badge]: https://github.com/Ab-Romia/commentdraft/actions/workflows/ci.yml/badge.svg
[ci-link]: https://github.com/Ab-Romia/commentdraft/actions/workflows/ci.yml
[pypi-badge]: https://img.shields.io/pypi/v/commentdraft.svg
[pypi-link]: https://pypi.org/project/commentdraft/
[python-badge]: https://img.shields.io/badge/python-3.11%2B-blue.svg
[python-link]: https://github.com/Ab-Romia/commentdraft/blob/main/pyproject.toml
[license-badge]: https://img.shields.io/badge/license-Apache--2.0-blue.svg
[license-link]: https://github.com/Ab-Romia/commentdraft/blob/main/LICENSE
[promptfoo]: https://github.com/promptfoo/promptfoo
