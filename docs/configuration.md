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
| `platforms` | no | a list of platform names used only to pre-fill the platform picker in `commentdesk chat` and `commentdesk ui`. Omit it and both still work; the picker just starts empty. |

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

Optional, and only read by `commentdesk bakeoff`. Each entry needs its own `label`,
`model` and `params`, with the same `data_collection = "deny"` rule as `[model]`.
Every entry inherits only `base_url` and `api_key_env` from `[model]`, never
`pricing`, on purpose. `docs/bakeoff.md` is the full chapter on this table, including
why the inheritance rule is that narrow and how to run and read a comparison.
