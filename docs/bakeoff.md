# Comparing models

`commentdesk bakeoff` runs the same comments through your `[model]` plus every
`[[bakeoff.models]]` entry, one CSV per label, and `commentdesk review --blind` turns
those CSVs into one page with the sources hidden behind letters and a key file
returned separately. It exists because choosing a model by reading a benchmark table
and then feeling confident is a way to be wrong slowly, and the failures that matter
here (an invented price, a claim your source document contradicts) are not the ones a
general benchmark measures.

This page carries no results table. No figure here has been re-measured against the
fictional example products in this repository, and a number carried over from
somewhere else is worse than no number at all. Measure your own, write the date next
to it, and re-verify anything you read below before you rely on it.

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

Two things worth knowing before you start. First, the cost spread across a plausible
field of models is usually small next to the time a person spends reviewing each run,
so cost is rarely the deciding variable; measure it anyway and decide with your eyes
open rather than assuming. Second, a templated feel across a batch is usually a
prompt problem rather than a model problem: `docs/writing-a-voice.md` explains which
part of the prompt causes it and what reduces it.

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

[promptfoo]: https://github.com/promptfoo/promptfoo
