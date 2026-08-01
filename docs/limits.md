# Limits

Everything here is known, deliberate, and written down before you find it the hard
way. Where a limit has a workaround, the workaround is named. Where it does not, that
is said plainly instead of being quietly implied.

## One call to action style per run

`[behavior].cta_mode` is resolved once, before the loop over comments starts, and the
chosen style is rendered directly into the system prefix. Every row of a run gets the
same call to action style, regardless of what the `platform` column of that row says.

The workaround today is two configs and two runs, split by whatever decides the style
for you:

```bash
commentdraft run --config config-direct.toml --comments direct.csv --out out/direct
commentdraft run --config config-pointer.toml --comments pointer.csv --out out/pointer
commentdraft review out/direct/review.csv out/pointer/review.csv
```

Making the choice per row **breaks the cache**, which is why it has not been built.
The CTA phrases are woven through the worked examples in `examples.md`, not appended
at the end, so a per-row choice would mean rendering two different system prefixes and
picking between them mid-run. Whichever one a row does not use pays the full,
uncached input price on every single call, because the provider only ever has one
prefix warm at a time. That is a real feature with a real cost, and it stays deferred
rather than refused; see `docs/architecture.md` for why the prefix has to stay
byte-identical across a run in the first place.

## `plug_cap` measures, it does not limit

`[behavior].plug_cap` is an **alarm threshold**, never a limiter. `build_report`
computes the share of replies that matched one of your `plug_markers` and flags a run
that exceeds the cap you set. Nothing stops mid-run because of it, no reply is
rewritten because of it, and no row is dropped because of it.

What actually holds the rate down is the rule you wrote into your voice file. The
report only tells you, after the fact, whether that rule is still working.

`is_plug` itself is a case-insensitive substring test against your configured
markers, so the reported share is approximate in both directions: a reply that points
at your product without using any of your markers is not counted, and a reply that
quotes a marker for an unrelated reason is. `plug_markers` is required and validated
non-empty for exactly this reason: an empty list would make every reply score as "not
a plug," which reports a plug rate of zero on a run that could hold any true rate at
all, and a failure that reads as a clean run is the one this project is least willing
to ship.

Measured rather than asserted: in the bake-off run written up in `docs/bakeoff.md`, two
of the three models came in at 13 of 16 replies against the example config's `plug_cap`
of 0.75. The report said `OVER plug_cap 0.75` on both, and both runs then finished
normally, wrote every row, and rewrote nothing.

## `load_config` validates shape and never content

A wrong price, a dead purchase link, a stale contact name, and a knowledge document
describing last year's edition of your product all pass `load_config` cleanly. Every
one of them is shaped correctly; none of them is checked for being true.

This is not an oversight to fix later. Checking content would need a source of truth
that only you have, and a tool that half-checks content teaches you to trust the half
it does not actually check. A wrong fact travels through to a human reviewer, and the
human reviewer, reading the review page before anything is sent, is the control this
design depends on instead.

## `find_repetition` splits on whitespace

`find_repetition` tokenizes a reply by splitting on spaces, so it can see a repeated
opening or closing word in any script written the way English, Arabic or Russian
are, with spaces between words. It cannot see into a script written without spaces
between words, such as Japanese, Chinese or Thai: a whole reply in one of those
scripts is one token regardless of how many words a person would count in it, and a
single token never reaches the two-token minimum the function requires before a reply
enters either bucket. Three identical replies in such a script produce no flag at all,
however hard the case.

Seeing into that would need a word-segmentation dependency, and this project does not
take one on. `tests/test_sanitize.py::test_repetition_is_invisible_in_a_language_without_word_spaces`
pins the behavior on purpose, so a future change cannot silently "fix" it into
something that looks like coverage this function was never built to have.

## `{{max_reply_sentences}}` cannot inflect

The placeholder is substituted as a plain number: whatever `[behavior].max_reply_sentences`
holds becomes the literal digits in the rendered prompt, with no grammar layered on
top. That is fine in English, where "sentences" does not change with the count in
front of it. It is not fine in every language voice.md might be written in: Arabic
wants the dual form for exactly two and the plural form for three through ten, so a
rendered numeral followed by the singular noun form reads as grammatically wrong to a
native reader, in the same way "2 sentence" would read wrong in English where "2
sentences" is required. English happens to need only two forms and never disagrees
with a plain digit; Arabic needs more forms than a single rendered number can choose
between.

No placeholder system can fix this by itself in a language whose nouns inflect for
number, because the correct word depends on the number's value, not on where it sits
in a sentence, and this placeholder is filled in long before anyone looks at what
number it holds. The operator words around it directly in `voice.md`, writing out the
count in whichever grammatical form their own rule needs rather than leaning on the
placeholder to produce it, exactly as `tests/fixtures/nazzef-kit-ar` does.

## The engine's own English

The claim this project makes is that the engine holds no copy **in your language** and
none **about your product**. That claim is narrower than "the engine holds no English",
and the narrower one is the true one.

`tests/test_guarantees.py` proves that no string literal under `src/` contains a
non-ASCII character. That is a real guarantee and it is worth having, but notice what
it cannot prove: English is ASCII, so an ASCII-only check can never catch English copy
arriving in a module. The English that is there is listed here instead, in full, so
that the guarantee and the list together say the whole truth.

| Where | What it is | Who reads it |
|---|---|---|
| `prompt.py`, `OUTPUT_CONTRACT` | the JSON shape `parse_response` requires | the model |
| `prompt.py`, `build_messages` | the user-message labels: `Platform:`, `Post title:`, `Comment from <author>:` | the model |
| `engine.py`, `RETRY_NUDGE` | the one nudge appended after an unparseable answer | the model |
| `sources/pdf_vision.py`, `TRANSCRIBE_PROMPT` | the transcription instruction | the model |
| `render/review_html.py`, `DRAFT_BANNER`, `DEFAULT_CURRENCY_NOTE`, `NEVER_POSTED_NOTE` | three fixed notices on the review page | your reviewer |
| `render/review_html.py`, `COLUMNS` | the ten column headings on the review page | your reviewer |
| `engine.py`, `EMPTY_COMMENT_REASON` | the reason written for a row whose comment is empty | your reviewer, in the `reason` column |
| `report.py`, `build_report` | the four lines of the end-of-run report | you, in your terminal |
| `cli.py` | flag names, help text and startup error messages | you, in your terminal |
| `ui.py`, `_PAGE` | the local test page's chrome: button labels, section headings and stat labels | you, in the browser |

Nothing on that list is configurable today, and nothing on it enters a drafted reply.
The first four are sent to the model and are wire format rather than voice: an operator
who translated `OUTPUT_CONTRACT` would break parsing on comment one, which is exactly
why it lives where an operator cannot reach it (`docs/writing-a-voice.md` says the same
thing from the other side). The rest is machine output around your content, not your
content.

The item that costs a non-English operator the most is the review page: a reviewer
working in Arabic opens `review.html` and reads an English banner above a table of
Arabic replies, under English headings. Making the three notices overridable from
config would fix that, and it is not built yet. Stating it is the point of this page.

## Knowledge larger than the context window

The whole knowledge document is read once and placed in the cached system prefix, in
full. Nothing is chunked, nothing is retrieved on demand, nothing is summarized, and
nothing is silently truncated to make it fit.

When your source document outgrows the **context window** of the model you have
chosen, this design stops being the right one, and retrieval becomes the right answer
instead. `docs/architecture.md` explains exactly where that line sits and why this
project accepts it as a limit rather than pretending a chunker would not change the
guarantee the whole design rests on. Fitting your source to your model is your job to
solve before a run, not something the tool will attempt quietly on your behalf.

## Repetition can be reported but not prevented

Each comment is answered by a separate model call carrying no memory of any other
call in the run. The model drafting the last reply in a batch has no way to know
how it worded the first nineteen, so repetition across a batch **cannot be prevented**
while any one draft is being written. It can only be found afterward, by rereading
every reply once the run is done.

`find_repetition` does that rereading and reports what it finds in the run report,
across ASCII and non-ASCII punctuation alike, subject to the whitespace limit above. A
human breaks the repeats up before anything is sent. Writing a different
`{{cta_phrase_N}}` into each worked example measurably reduces how often this happens,
as `docs/writing-a-voice.md` describes, and it is a mitigation rather than a fix for
the same reason: the property being asked for is a fact about the whole batch, and
nothing in a stateless, one-call-per-comment design can see the whole batch while any
one reply is being written.

Measured rather than asserted: in the bake-off run written up in `docs/bakeoff.md`, the
default model closed 13 of its 16 replies on the identical purchase link and opened 6
of them on the identical word. `find_repetition` named every row in the run report.
Nothing prevented any of it, because nothing in this design could have.

Take this one seriously even though nothing here is unsafe in the way a wrong price
is: several platforms demote near-identical comments as spam, and a demoted comment
produces no error message anywhere in this tool. The failure is silent on the
platform's side, which is exactly why this project goes out of its way to make it
visible on its own.

## A run overwrites its own output

Writing the review CSV opens the output path for writing. Running the same command
again over the same `--out` replaces `review.csv`, including any edits a person made
in a copy left in that same file. Copy a reviewed file aside, or point `--out` at a
new directory, before running the same comments through again.

## Not built, on purpose

Posting, scheduling, holding platform credentials, a hosted service, a database, and a
plugin marketplace. Language packs are the one item on this list with an unusual
reason: nothing in the engine inspects, detects or adapts to the language you write
in, so there is no language setting for a pack to fill. Your language lives entirely
in the files you write. What the engine does hold in English of its own is the fixed
scaffolding listed under "The engine's own English" above, and a language pack is not
what that section is asking for.
