# Configuration reference

Everything an operator sets lives in one `config.toml`. This page lists every table
and every key `load_config` reads, which ones are required, and what each one does.
It does not repeat how to write good copy for the ones that hold prose; that is
`docs/writing-a-voice.md`'s job, and this page points there rather than duplicating it.

A key marked required stops the run with a `ConfigError` naming exactly that key if
it is missing, before a single comment is read. A key marked optional is safe to
leave out entirely; the tool falls back to a sensible default rather than guessing at
one silently. Nothing on this page is checked for being *true*, only for being
*shaped correctly*; see `docs/limits.md` for why that boundary is deliberate.

## `[product]`

All five keys are required, and each has to be a non-empty string rather than a value that only looks like one: `price_text = 18` is refused, because the placeholder ships a string and the currency you meant to type would go missing without a word. What the string says is never judged; see `docs/limits.md`. All five are also placeholders you
can use in `voice.md` and `examples.md`; see `docs/writing-a-voice.md` for the full
placeholder table.

| Key | Placeholder | What it holds |
|---|---|---|
| `name` | `{{product_name}}` | the exact name of the thing you sell |
| `kind` | `{{product_kind}}` | the noun for it: a book, a course, a kit |
| `price_text` | `{{price_text}}` | the price exactly as you would type it, currency and all; a string, never a number |
| `purchase_link` | `{{purchase_link}}` | the URL, in the one place you change it |
| `escalation_contact` | `{{escalation_contact}}` | who a deferred question goes to, in your words |

## `[knowledge]`

```toml
[knowledge]
source = "text"
path = "knowledge.md"
```

`source` and `path` are both required, non-empty strings. `source` names a registered
handler (`text` and `pdf_vision` ship with the package); `path` is resolved against
the directory holding `config.toml` unless it is absolute. Any other key you add to
this table is passed through to the handler as its own settings, unread by anything
else. `docs/sources.md` covers both built-in handlers and how to add your own.

## `[voice]`

```toml
[voice]
rules = "prompts/voice.md"
examples = "prompts/examples.md"
```

Both keys are required and both are paths, resolved the same way `knowledge.path` is.
What to write inside the two files they name is the whole subject of
`docs/writing-a-voice.md`.

## `[behavior]`

| Key | Required | What it does |
|---|---|---|
| `cta_mode` | yes | names one of your `[cta.<name>]` tables, checked against your own config rather than a fixed list |
| `plug_cap` | yes | a number from 0 to 1: the alarm threshold `build_report` compares your measured plug rate against. It has to be an actual number, not `true` and not a quoted `"0.75"`, because `true` would load as 1.0 and silently make the alarm unable to fire. It does not limit anything; see `docs/limits.md`. |
| `max_reply_sentences` | yes, a whole number of 1 or more | substituted verbatim into `{{max_reply_sentences}}` and sent to the model, which is why it has to be a number rather than anything that merely survives `str()`; see `docs/limits.md` for the one language limit this has |
| `bot_disclosure_text` | yes | the exact sentence used when someone asks whether a person wrote the reply, substituted into `{{bot_disclosure_text}}`; see `docs/platform-policy.md` for why this has no off switch |
| `plug_markers` | yes, non-empty list | the exact substrings `is_plug` looks for, case-insensitively, to decide a reply mentions your product; see `docs/limits.md` for why an empty list is refused rather than defaulted |
| `separator` | yes, non-empty string | what `sanitize_reply` substitutes for every em dash and en dash it strips out of a draft |
| `banned_emoji` | yes | one string of characters to strip from every draft; an empty string `""` is a valid value meaning "ban nothing" |
| `platforms` | no | a list of platform names used only to pre-fill the platform picker in `commentdraft chat` and `commentdraft ui`. Omit it and both still work; the picker just starts empty. |

## `[cta.<name>]`

At least one such table must exist, named by `behavior.cta_mode`. Each one you define
needs:

```toml
[cta.direct]
instruction = "If someone asks where to get it, give the link: {{purchase_link}}."
phrases = [
  "here is the link: {{purchase_link}}",
  "you can get it at {{purchase_link}}",
]
```

`instruction` is a required, non-empty string, and `phrases` is a required, non-empty
list of strings. Both may use the `[product]` placeholders; `docs/writing-a-voice.md`
covers the two-pass substitution that resolves them and why `{{cta_phrase_1}}`,
`{{cta_phrase_2}}`, and so on exist as separate names.

## `[model]`

| Key | Required | What it does |
|---|---|---|
| `label` | yes | the name this model is shown under, in reports, in a review page, and as a bake-off column |
| `base_url` | yes | the OpenAI-compatible endpoint to call |
| `model` | yes | the model identifier your gateway expects |
| `api_key_env` | yes | the name of an environment variable holding the API key, never the key itself |
| `params` | yes, a table | extra request parameters, sent through unread. `params.provider.data_collection` must be `"deny"`, nested inside `provider`; `docs/platform-policy.md` and `docs/bakeoff.md` both explain why the nesting is what is actually checked. |
| `pricing` | no | `input_per_mtok`, `cached_per_mtok` and `output_per_mtok` together, plus an optional `cache_write_per_mtok`. Missing or incomplete, `estimate_cost` returns nothing rather than a wrong number, and the cost column in your CSV stays blank rather than showing a fabricated zero. Every rate you write here is a dated observation, never a quote; `docs/bakeoff.md` measures what one set of them did to one real bill and says how fast that goes stale. |

`api_key_env` names a variable read from the real environment or from a `.env` file
next to `config.toml`; a value already exported in your shell always wins over the
file, so pointing a run at a different key never means editing `.env`.

## `[[bakeoff.models]]`

Optional, and only read by `commentdraft bakeoff`. Each entry needs its own `label`,
`model` and `params`, with the same `data_collection = "deny"` rule as `[model]`.
Every entry inherits only `base_url` and `api_key_env` from `[model]`, never
`pricing`, on purpose. `docs/bakeoff.md` is the full chapter on this table, including
why the inheritance rule is that narrow and how to run and read a comparison.

## `[source]`

Absent by default, and the table `commentdraft pull` reads. Adding it turns reading
on and nothing else: a config with a `[source]` table and no `[publish]` table pulls
comments, drafts replies for them, renders the review page, and cannot publish
anything at all.

That combination is the recommended place to start, and it is a place the config
could not describe until this table existed. Platforms grant reading and writing as
separate scopes, weeks apart, and the Page a connector reads used to be named in
`[publish]`, so pulling a single comment required writing down a write credential
nobody had been granted yet.

| Key | Required | What it does |
|---|---|---|
| `platform` | yes | the name of a registered connector. `facebook` is the one that ships. An unregistered name is refused before a credential is asked for, and the message lists what is registered. |
| `credential_env` | yes | the name of an environment variable holding the read token, never the token itself, on the same rule as `model.api_key_env` |
| `page_id` | yes, for `facebook` | the numeric id of the Facebook Page to read comments from |

Keys beyond the first two belong to whichever connector you named, and only that
connector reads them. `page_id` is Facebook's.

A config written before this table existed keeps pulling. With no `[source]` table,
`commentdraft pull` reads `[publish]` instead: the same platform name, the same
credential variable and the same `page_id`. The fallback runs one way only.
`commentdraft publish` never reads `[source]`, so a token granted for reading cannot
become the token something writes with by being pointed at from the other side.

### Pulling twice

`commentdraft pull --config config.toml --out comments.csv` writes the file
`commentdraft run --comments` reads, with nothing to edit in between. Run on a
schedule, the question that matters is what happens the second time, because a
comment pulled twice is drafted twice, billed twice, and offered to a person to
approve twice.

```bash
commentdraft pull --config config.toml --out comments.csv --state pull-state.json
```

`--state` names a small JSON file holding the platform it was written for, the
`--since` marker last used, and the id of every comment the platform has handed over
while that file has existed. A comment whose id is in it is left out of the CSV. So a
second pull over unchanged comments writes none of them: it prints how many were read,
how many were left out, and leaves `comments.csv` holding its header and nothing else,
which `commentdraft run` then refuses by name rather than drafting an empty file.

The file grows by one line per comment ever pulled and never shrinks by itself.
Twenty thousand comments is a few hundred kilobytes. Delete it to start that platform
over, and keep one per platform: pulling two platforms through one file would have
each of them read the other's ids as its own. A file written for another platform is
refused rather than merged.

`--since` narrows what the connector asks the platform for at all, which is what keeps
a scheduled pull cheap in API calls. The shape is the connector's to define; the
Facebook connector reads an ISO 8601 time such as `2026-08-01T09:30:00+0000` and
refuses a marker it cannot read rather than silently reading the whole window again.
A marker typed on the command line wins over the one in the state file and is then
written back to it, so it is typed once.

Duplicates are still possible in exactly these cases, and each is a case where nothing
could have known better:

- **No `--state` file.** Every pull writes every comment it can see, every time. The
  command says so on its last line rather than leaving it to be discovered.
- **A comment the platform hands over with no id.** There is nothing to remember it
  by, so it is written every time. The alternative is dropping a comment nobody ever
  answers, which is worse. The Facebook connector does not produce these: it skips a
  comment with no id.
- **A state file that was deleted, moved, or pointed at a different path.** The memory
  is the file. Nothing else remembers.
- **A comment that changed id on the platform.** A new id is a new comment as far as
  anything here can tell.

A pull that could not read one post is not a clean pull. The rows it did read are
still written, the post that failed is named on standard error, and the exit code is
1 rather than 0, so a scheduled caller does not read a partial pull as a whole one.
A pull the platform refused outright writes nothing at all and leaves the state file
untouched.

## `[publish]`

Absent by default, and that is the recommended way to start. A config with no
`[publish]` table cannot publish anything at all, which is a real deployment rather
than a degraded one: `commentdraft pull` still reads, `commentdraft run` still drafts,
`commentdraft review` still renders, and there is no write credential anywhere near
the machine.

Adding the table turns `commentdraft publish` on. It does not turn anything
automatic on: every reply still costs one keystroke from a person looking at that
reply, and `docs/limits.md` says why there is no flag that changes it.

| Key | Required | What it does |
|---|---|---|
| `platform` | yes | the name of a registered connector. `facebook` is the one that ships. An unregistered name is refused before a credential is asked for, and the message lists what is registered. |
| `credential_env` | yes | the name of an environment variable holding the platform token, never the token itself, on the same rule as `model.api_key_env` |
| `page_id` | no | where the Page id used to live. It belongs in `[source]` now, because reading is what uses it, and it is still honoured here so that a config written before `[source]` existed goes on pulling. Publishing does not read it: a reply is sent to the id of the comment it answers. |

Keys beyond the first two belong to whichever connector you named, and only that
connector reads them. `page_id` is Facebook's.

### `platform = "facebook"`

`credential_env` has to name a variable holding a **Page** access token, not a user
access token. This is the mistake that costs the most time: several comment edges
answer a user token with an empty list and HTTP 200, so a Page with plenty of
comments reads as a Page with none and nothing anywhere reports an error. Where a
call does fail on it, the connector names error 1705 and says so in a sentence.

`source.page_id` is the Page the connector reads posts and comments from. It is
checked for shape only, exactly like every other value here: nothing asks whether it
names a real Page, and a Page id that belongs to somebody other than the token's owner
surfaces as a permission error from Meta rather than as a config error from this tool.

The same wording applies to `[source].credential_env`. Reading needs
`pages_read_engagement` and `pages_read_user_content`; publishing also needs
`pages_manage_engagement`. Both are Page access tokens, and they can be the same
token: the two tables exist so that they do not have to be.

The token dies on specific events rather than on a clock, and each one has a
different fix. The connector reads Meta's error subcodes and says which happened. The
one to expect is the 90 day rule: a permission your app has not used for 90 days is
revoked and has to be granted again by hand. This tool is used in bursts by design,
so a setup that worked last quarter can stop working with nothing changed anywhere.
One of them is not a token problem at all: subcode 492 means the account behind the
token lost its role on the Page, and a fresh token will fail in exactly the same way
until somebody gives that account its role back.

The connector reads the Page's own `published_posts`, not its `feed`. `feed` also
carries posts visitors made on the Page and posts that merely tag it, and neither is
yours to answer under. It also holds back comments that are replies to other
comments: Facebook flattens threads, so a reply written under one of those lands
under the top level comment instead, which is not the reply anybody approved.

`commentdraft publish` exits 3, rather than 0, 1 or 2, when a write reached the
platform and could not be proved to have done what it says. The queue stops there,
and the last line in `out/published.jsonl` is marked `"verified": false` and carries
the id of what is live, or of what is suspected. Read it and look at the Page before
running publish again.

Publishing is not settled documentation yet. Read
`notes/platforms/facebook-connector-report.md` for what a person with real
credentials still has to confirm before it is.
