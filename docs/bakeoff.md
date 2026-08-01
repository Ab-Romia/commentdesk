# Comparing models

`commentdesk bakeoff` runs the same comments through your `[model]` plus every
`[[bakeoff.models]]` entry, one CSV per label, and `commentdesk review --blind` turns
those CSVs into one page with the sources hidden behind letters and a key file
returned separately. It exists because choosing a model by reading a benchmark table
and then feeling confident is a way to be wrong slowly, and the failures that matter
here (an invented price, a claim your source document contradicts) are not the ones a
general benchmark measures.

One measured run is written up below, against the fictional field guide that ships in
this repository, so every figure on this page resolves to a command you can run
yourself rather than to a number carried over from somewhere else. It is one run, on
one example, on one day, and it is dated for that reason. Measure your own, write the
date next to it, and re-verify anything you read here before you rely on it.

## Setting it up

```toml
[model]
label = "primary"
base_url = "https://openrouter.ai/api/v1"
model = "vendor/model-name"
api_key_env = "OPENROUTER_API_KEY"

[model.pricing]
input_per_mtok = 0.32
cached_per_mtok = 0.064
output_per_mtok = 1.28

[model.params]
provider = { data_collection = "deny" }

[[bakeoff.models]]
label = "challenger"
model = "othervendor/other-model"
params = { provider = { data_collection = "deny" } }
pricing = { input_per_mtok = 0.1, cached_per_mtok = 0.01, output_per_mtok = 0.4 }
```

The model names and the rates in that block are placeholders showing the shape, not
any real route's prices. The rates a real run was actually billed at are further down,
with their date.

A `[[bakeoff.models]]` entry inherits **only** the gateway keys, `base_url` and
`api_key_env`. It does not inherit `pricing` and it does not inherit `params`. That is
on purpose: inheriting the whole `[model]` table would hand an entry that forgot
`pricing` the default model's rates, and a bake-off exists specifically to compare
prices, so a silently mispriced row is worse than a blank cost column. An entry that
omits `pricing` gets a blank cost figure in its CSV instead, because `estimate_cost`
returns nothing rather than a fabricated zero when the rates are incomplete. Blank
reads as "not known", which is true. Zero would read as "this call was free", which is
a claim, and a wrong one.

`label`, `model` and `params` are required on every entry, the default `[model]` table
included. `params.provider.data_collection` must be `"deny"`, nested inside `provider`
rather than at the top level of `params`. At the top level a gateway accepts the key,
ignores it, and routes with data collection left at its own default, which is usually
allow. A config missing this, in the default model or in any challenger, is refused
before the first comment is sent, not partway through a run that already spent money
on a route you did not mean to use.

## Running it

```bash
commentdesk bakeoff --config config.toml --comments comments.csv --out out
```

This writes one CSV per model into `out/` (`out/review-primary.csv`,
`out/review-challenger.csv`, and so on, named from each entry's `label`), prints a run
report per model, and finishes by writing `out/bakeoff-blind_key.json`, a letter to
label mapping, plus the exact command to run next. Do not open that key file yet.

```bash
commentdesk review out/review-primary.csv out/review-challenger.csv --blind
```

This is the command `bakeoff` printed for you; run it as given rather than retyping it,
because the letter each source gets depends on the order the files are listed in.
`--blind` labels each source A, B, C in that order, drops the model column from the
page entirely, and writes a second key file, `out/review-blind_key.json`, next to
`out/review.html`. It maps the same letters to the CSV file names this time rather
than to the labels, since this command never saw your config's labels, only the
files, but as long as you passed the files in the order `bakeoff` printed, the two key
files agree letter for letter.

A blind page also prints no cost total and no currency note. The plain page prints
both. Cost identifies a source: the totals from the run below are published per model
further down this very page, and a route with cached input pricing sits an order of
magnitude under one without, so a figure per letter is a name per letter. The decision
tally stays, because how many comments a source replied to, skipped and escalated is
part of what you are scoring. Read the costs out of the run report or the CSVs after
you have opened the key.

What blinding cannot cover: a model that names itself inside a reply, inside its
recorded reason, or inside an error string that quotes the request back. Nothing reads
those cells looking for a name. Expect the occasional one and score the rest.

Score the page first. Open a key file afterward. This is not ceremony: the letters
change scores, and you will not notice yourself doing it.

## The method that produced something worth keeping

1. **Use your own comments.** Thirty of your real ones beat any public set, because
   the failures you care about are specific to what you sell.
2. **Include the awkward cases on purpose.** An empty comment. Abuse. A question the
   source document genuinely does not answer. A question about refunds. Someone
   asking whether a person wrote the reply. Most of the useful signal sits here, not
   in the easy comments.
3. **Score blind, and score dimensions rather than one feeling.** Accuracy, triage
   correctness, brevity, rule compliance, and how templated the replies feel across
   the batch are five separate things, and models are good at different ones.
4. **Have a second person re-check the winner adversarially,** hunting specifically
   for invented facts. Enthusiasm about tone is the easiest way to ship a model that
   makes things up.
5. **Weight accuracy failures above style failures.** A stiff sentence is
   embarrassing. An invented price, an invented delivery promise, or a claim the
   source document contradicts is a cost that lands on a real person, not on you.

Two things worth knowing before you start. First, be careful which cost you are
comparing. The absolute amounts across a plausible field of models are usually small
next to the time a person spends reviewing a run, so cost alone is rarely the deciding
variable; the ratio between two entries is a different number entirely and it can be
large, as the run below measured. Look at both and decide with your eyes open rather
than assuming either. Second, a templated feel across a batch is usually a prompt
problem rather than a model problem: `docs/writing-a-voice.md` explains which part of
the prompt causes it and what reduces it.

## One measured run, 2026-08-01

Run from the repository root, against the field guide example:

```bash
commentdesk bakeoff --config examples/field-guide-book/config.toml \
  --comments examples/field-guide-book/comments.csv --out out/bakeoff
```

Thirty comments in the file, twenty-nine billed calls. One comment is empty, and an
empty comment is decided locally as `skip` with no call and no cost, so it counts in
the decisions and in neither the cache nor the cost figures. The cached prefix measured
4,162 tokens.

The totals, the cache lines and the decision counts below were read out of the run
report each model printed. The per-call column is the only derived figure on the page:
it is each total divided by the twenty-nine calls that were billed.

| label | model id | total cost | per billed call | cache hits | decisions |
|---|---|---|---|---|---|
| `primary` | `qwen/qwen3.7-flash` | $0.0012 | $0.000040 | 28/29 | escalate 5, reply 16, skip 9 |
| `cheap` | `deepseek/deepseek-chat` | $0.0318 | $0.001095 | 0/29 | escalate 5, reply 16, skip 9 |
| `small` | `mistralai/mistral-small-3.2-24b-instruct` | $0.0093 | $0.000320 | 0/29 | escalate 4, reply 16, skip 10 |

The rates those totals were computed from, USD per million tokens, read from the
gateway's own live model list that day and written into
`examples/field-guide-book/config.toml` with the same date beside them:

| label | input | cached input | output | cache write |
|---|---|---|---|---|
| `primary` | 0.03 | 0.006 | 0.13 | 0.038 |
| `cheap` | 0.2574 | 0.0 | 1.0287 | 0.0 |
| `small` | 0.075 | 0.0 | 0.2 | 0.0 |

### What the cost column actually measured

The entry labelled `cheap` cost about 27 times more per comment than the default did.
Its input rate is 8.6 times the default's and its output rate 7.9 times, so the
published rates on their own predict a gap somewhere near 8, not near 27. The rest of
the gap is the prompt cache.

The prefix dominates the bill on every call here: 4,162 tokens of rendered voice rules,
worked examples, output contract and the whole knowledge document, against a user
message holding one comment and a reply of a sentence or two. `primary` billed that
prefix at the cached rate of 0.006 on 28 of its 29 calls. `cheap` and `small` billed it
at their full input rate on all 29, because neither route served it from a cache at all.

That is the argument in `docs/architecture.md` arriving as a measurement rather than an
assertion. The prefix is assembled once and kept byte-identical across a run
specifically so a provider can serve it from cache, and on this run that property was
worth more than the difference in sticker price between these three routes. One piece
of arithmetic on the same two rates, offered as arithmetic and not as a second
measurement: 4,162 tokens billed at 0.03 rather than 0.006 is about $0.0001 more per
call, so this run priced entirely uncached at `primary`'s own published input rate
would have cost roughly three times what it did. Three is larger than the 2.5 between
`primary`'s input rate and `small`'s.

Read that narrowly. It is one run, one example product, one gateway, one day. A route
that adds cached input pricing, drops it, or changes what it charges to write a cache
entry moves this column further than these three models differ from each other, and
none of those changes announces itself.

### The results that do not flatter

Two of the three went over the alarm threshold the example config sets. The report
line, identical for `primary` and `cheap`:

```
plugs: 13/16 replies contain a configured plug marker OVER plug_cap 0.75
```

`small` came in at 11 of 16, under the cap. Nothing stopped, nothing was rewritten and
no row was dropped on either of the two that went over, because `plug_cap` is an alarm
threshold and never a limiter. This run is the demonstration rather than the claim: the
rate exceeded the number and the run finished exactly as it would have otherwise. What
holds the rate down is the rule in the voice file, and `docs/limits.md` covers what the
substring test behind that number can and cannot see.

`primary`'s report carried both repetition flags as well:

```
repetition: closing 'https://example.com/field-guide' repeats in rows 1, 2, 3, 4, 7, 9, 22, 23, 24, 25, 26, 28, 30
repetition: opening 'It' repeats in rows 4, 7, 22, 25, 26, 28
```

Thirteen of its sixteen replies ended on the same pointer, and six of them opened on
the same word. The plug line and the closing line report 13 for one reason: the
configured plug marker is that same URL, so both are counting the same behavior from
two sides.

This is the limit `docs/limits.md` states under "Repetition can be reported but not
prevented", and it is structural rather than a tuning problem. Each comment is answered
by a separate call carrying no memory of any other call in the run, so the model writing
the last reply cannot know how it ended the first, and no instruction in the prompt can
enforce a rule about a set the model was never shown. `find_repetition` rereads the
whole batch once the run is over and names the rows, so a person can break them up
before anything is sent. This run is evidence that the limit is real and that the
detector works, in that order.

Both of those belong here at the same size as the cost finding. A results section that
reports only the flattering measurement is not evidence, it is advertising.

### Triage agreed, and that is thinner evidence than it looks

All three produced 16 replies. `primary` and `cheap` produced identical counts across
all three decisions, and `small` differed by one, with one fewer escalate and one more
skip.

What that supports: none of the three collapsed into answering everything or escalating
everything. Both are real failure modes, and ruling them out for a tenth of a dollar is
worth the run on its own.

What it does not support: that the three agreed comment by comment. These are totals,
and two models can produce identical totals while disagreeing about which comments they
apply to. This run recorded no per-row comparison, so what agreed here is the counts,
not demonstrably the decisions. It also says nothing about any of them being right: a
comment every model reads the same wrong way looks exactly like agreement, and there is
no ground truth anywhere in these tables. Cost and counts are the half of a bake-off a
machine can measure. The blind page is the other half, and no figure above replaces
scoring it. The next section is that pass.

### The blind scoring pass, 2026-08-01

One scorer, the author of this repository. One pass over the blind page the command
above produces. The ranking that came out of it: `primary` first, `cheap` second,
`small` third.

`primary` and `cheap` were judged indistinguishable on reply quality across all thirty
comments. Nothing in this pass separates them.

`small` was ranked below both for one specific reason, on one row. Row 8 is the comment
"Do you ship to Canada and how long does it take?". `primary` and `cheap` both
escalated it. `small` skipped it, and its own recorded reason shows it had read the
situation correctly before choosing:

```
shipping question that has to be deflected, the deflection is the whole reply and the pointer is dropped
```

A skip writes no draft and routes the comment to nobody, so the person who asked gets
silence. An escalation writes no draft either, but it sends the comment to the person
who can answer it. That is a triage failure with a real reader on the other end, not a
matter of style, and it is the only thing this pass held against `small`; everything
else about its output was acceptable. The counts above show `small` with one fewer
escalate and one more skip, and this row is a difference of exactly that shape. Whether
it is the only one is not something this pass established, for the reason the section
above gives.

**First place was decided on cost, not on quality.** The scorer judged `primary` and
`cheap` equal on their replies and broke the tie with the cost totals, which the blind
page was printing per source at the time. It should not have been: cost identifies a
source, the totals for these three are published further up this page, and the whole
point of the blind page is that the scorer does not know which source is which. That
was a defect in the page and it is fixed, which is why the section on running a
bake-off now says a blind page prints no cost. So the quality result from this pass is
two tied and one below them. The ordering inside the tie is a cost decision made after
the fact, written down here as one, and it is not a quality ranking.

### What the scoring pass does not establish

One scorer, one pass. Point 4 of the method above asks for a second person to re-check
the winner adversarially, hunting specifically for invented facts. That did not happen
here. Point 3 asks for scores across five named dimensions, accuracy, triage
correctness, brevity, rule compliance and how templated the batch feels, rather than
one overall feeling. That did not happen either: this pass produced a ranking and one
finding, not thirty rows of five scores.

So this document currently asks more of you than it demonstrates itself. The pass is
real and it found a real defect in one of the three models, which is more than any
table above can do. It is also thinner than the method it sits under, and that gap
belongs in the results section rather than left for a reader to work out.

### The caveat that applies to every figure above

Point-in-time observations from 2026-08-01: thirty comments, one fictional example
product, one gateway, three routes, one run each, no repeats, and one scoring pass by
one scorer with the limits that pass names for itself.
Providers change prices and change routing without notice and without a version number,
so a figure that was true on the date beside it can be wrong by the time you read it.
The rates are copied into `examples/field-guide-book/config.toml` carrying the same
date; if they have moved since, the totals above moved with them and nothing in this
repository will notice. Re-run the command before you rely on any of it.

## A parameter that lies

Some model routes offer two ways to turn off hidden reasoning: a gateway's own switch,
and a provider-native flag the underlying model defines for itself. Set both together
whenever reasoning should be off, specifically because the second one is not
guaranteed to be honored: a gateway sitting in front of the provider can accept
that provider-native key, forward it unread, and have the provider ignore it. The
request still succeeds. Nothing in the response warns you. The model reasons anyway,
and every one of those hidden reasoning tokens is billed to you as output.

Observed 2026-07-27, on one gateway route: a config that set only the provider-native
flag came back with an ordinary-looking short reply, after a noticeably longer wait,
having billed a completion token count wildly larger than the visible text could
account for. Setting the gateway's own switch instead brought back the same reply
quickly, with a completion count that matched what it actually wrote. **Re-verify
this before you rely on it.** It is exactly the kind of behavior that changes on a
provider's side without any announcement, and it was true of one route on one day, not
a property of any vendor in general.

The lesson worth keeping past any specific figure: **a parameter being accepted is not
the same as a parameter being honored, and the only way to tell is to read the token
counts you were actually billed for.** That is why `call_model` computes cost from the
usage the API reports rather than from what a request was supposed to do, and why
every row in a review CSV carries its own `completion_tokens` and `cost_usd`.

To check your own route, run the same comment through two configs that differ only in
which reasoning switch is set, and compare the CSVs:

```bash
commentdesk run --config with-native-flag.toml --comments one-comment.csv --out out/a
commentdesk run --config with-gateway-flag.toml --comments one-comment.csv --out out/b
```

Read `completion_tokens` and `cost_usd` in each `review.csv`. A route worth trusting
shows the same number either way. Keep both flags set together once you know your
answer: the provider-native one costs nothing when it is honored and nothing when it
is ignored, and it helps the moment a route starts honoring it.

Write both yourself, in every model table that turns reasoning off. `commentdesk run`
and `commentdesk bakeoff` send your `params` through to the request verbatim and add
nothing to them; `config.with_reasoning` is the only thing in the package that sets
the pair for you, and its only caller is the reasoning checkbox on the local test
page. So the tool sets both when you toggle reasoning in the ui, and in a batch run
the two flags are yours. Every config in this repository that turns reasoning off
sets both, and a test asserts it, which is the only reason that sentence is worth
anything.

## What this is not

If you want an evaluation harness with datasets, assertions, and a place to wire into
CI, use [promptfoo][promptfoo]. It is the right tool for that job. What this feature
claims is narrower: the experiment ships inside the application you are already
running, and every number in it resolves back to one TOML file anyone on your team can
open and re-run, rather than to a slide someone made once.

## Writing your results down

When you have measured, add your findings to this file with the date, the comment
count, how many scoring passes were run, and who scored them. Date every figure. Quote
one currency and do not convert others into it: an exchange rate and a model's price
are two separately aging numbers, and multiplying them produces a figure that looks
more precise than either input and is wrong twice.

"One measured run" above is the shape to copy, including the part that is easy to skip:
it reports the two results that made this project look bad next to the one that made it
look good, at the same size and in the same detail. Write yours the same way. The
purpose of measuring is to find out, and a page of only good news is proof that
somebody stopped looking.

[promptfoo]: https://github.com/promptfoo/promptfoo
