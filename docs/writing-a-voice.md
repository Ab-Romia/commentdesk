# Writing a voice

This is the chapter that makes the tool yours. Everything a reader of your replies
will actually perceive lives in two files you write, in your language, and the engine
never inspects either one beyond substituting placeholders into it.

- `prompts/voice.md` holds your rules: who you are, when to reply, when to stay quiet,
  when to hand a question to a person, and what a good reply sounds like.
- `prompts/examples.md` holds worked examples: real comments and the replies you would
  have written yourself.

Both are plain text. Write them in the language you sell in. There is no language
setting, because there is no language handling. If your rules are in Portuguese, the
model reads Portuguese rules and writes Portuguese replies.

## What gets sent

The system prefix is assembled in this order and nothing else is added:

1. `voice.md`, with placeholders substituted
2. `examples.md`, with placeholders substituted
3. the **output contract**, which is engine-owned, always English, and always appended
4. your knowledge document, wrapped as `<knowledge>...</knowledge>`

Point 3 is not yours to edit and is not in your files on purpose. It states the exact
JSON shape the engine parses. An operator who edited it, even only to translate it,
would break parsing for every row of the run, so it lives where an operator cannot
reach it: it is written into the prefix by the engine itself, never read from a file
you control.

## The placeholders

Write any of these in either file and it is replaced before the call. They come from
`config.toml`.

| Placeholder | Comes from | Use it for |
|---|---|---|
| `{{product_name}}` | `[product].name` | naming the thing you sell, so the model never invents a variant of the name |
| `{{product_kind}}` | `[product].kind` | the noun you use for it: a book, a course, a kit. Free text. |
| `{{price_text}}` | `[product].price_text` | the price exactly as you would type it, currency and all. It is a string, never a number, because you are the one who knows how to write it. |
| `{{purchase_link}}` | `[product].purchase_link` | the URL, in the one place you can change it |
| `{{escalation_contact}}` | `[product].escalation_contact` | who a deferred question goes to, in your words: "the team", "our support inbox", a first name |
| `{{max_reply_sentences}}` | `[behavior].max_reply_sentences` | writing the length rule as a number rather than as an adjective |
| `{{bot_disclosure_text}}` | `[behavior].bot_disclosure_text` | the exact sentence to use when someone asks whether a person wrote this |
| `{{knowledge_tag}}` | the engine | naming the tag your source document is wrapped in, so your grounding rule can point at it |
| `{{cta_instruction}}` | the selected `[cta.<mode>]` table | the rule for how to point at where to buy |
| `{{cta_phrases}}` | the same table | showing the model the full set of acceptable closings |
| `{{cta_phrase_1}}`, `{{cta_phrase_2}}`, ... | the same table, one per entry | putting a *different* closing into each worked example |

An unknown placeholder is a **hard error** the moment the prefix is rendered, which
happens once, at the start of a run, before a single comment is sent. It is not a
silent pass-through: a typo like `{{purchase_url}}` stops the run immediately instead
of shipping literal braces into a reply that a customer reads.

Indexed names are matched too. `{{cta_phrase_2}}` resolves; it does not sit there
looking like it worked.

## Substitution runs in two passes

CTA strings are themselves templates. `[cta.direct].instruction` normally contains
`{{purchase_link}}`.

- **Pass one** resolves the product placeholders *inside* the selected `[cta.*]` table.
- **Pass two** substitutes the results of pass one, plus the remaining product values,
  into `voice.md` and `examples.md`.

A placeholder still standing after pass two is the hard error described above. Nesting
deeper than that is not supported: a CTA phrase whose expansion contains another
placeholder is rejected rather than expanded again. Two passes is the whole contract,
and it is stated here so nobody has to discover it from a stack trace.

## The grounding rule and `{{knowledge_tag}}`

Your source document arrives inside a tag. Write the rule that binds claims to it
using the placeholder, never by typing the tag name yourself:

```markdown
Everything you state as fact must appear inside <{{knowledge_tag}}>. If a question is
not answered there, do not answer it. Choose escalate and say that
{{escalation_contact}} will follow up.
```

If you type the tag by hand and the engine's tag ever differs, your grounding rule
silently points at nothing and every reply looks fine while resting on nothing. The
placeholder makes the two impossible to drift apart, and a test asserts the round trip.

## A voice file you can start from

```markdown
You reply to comments under videos about {{product_name}}, a {{product_kind}}.

Who you are: the person who made the thing. Warm, brief, never salesy.

Rules:
- At most {{max_reply_sentences}} sentences. Shorter is better.
- Everything you state as fact must appear inside <{{knowledge_tag}}>.
- If the answer is not there, choose escalate and say that {{escalation_contact}}
  will follow up. Do not guess about shipping, editions, refunds, or availability.
- The price is {{price_text}}. Never convert it into another currency, and never
  describe it as cheap, expensive, or a bargain.
- {{cta_instruction}}
- Most replies carry no link and no price. Answer the question that was asked.
- If someone asks whether a person wrote this, say exactly: {{bot_disclosure_text}}
- Never repeat a phrase you have already used elsewhere in this batch.

Decide first, then write:
- reply: you can answer it well from the source, or it is simple appreciation.
- skip: spam, abuse, a comment aimed at someone else, or one with nothing to answer.
- escalate: a real question you cannot ground, or anything about money, delivery,
  legal matters, or a complaint.
```

## Worked examples, and the trap in them

`examples.md` teaches more than `voice.md` does. Demonstration beats instruction, which
is the useful half of the finding and also the dangerous half.

If every worked example closes with the same call to action string, the model learns
that string and closes most of its replies with it. In the project this engine came
from, one closing phrase repeated across every worked example was measured at six of
eight replies closing with it. Writing a *different* `{{cta_phrase_N}}` into each
example brought that down to four of eight.

That is a real improvement, and it is not a fix. Reducing is not fixing: each call is
stateless, so the model drafting reply nineteen has no idea how it ended replies one
through eighteen, and it cannot avoid repeating itself. The engine reports what
survives, through `find_repetition`, in the run report. A human breaks up the repeats
before sending. `docs/limits.md` explains why the real fix, rotating phrasing per row,
is not available in a cached prefix.

Write your examples as *reasoning*, not as ready-to-ship strings:

```markdown
Comment: "does this cover mushrooms in the pacific northwest?"
Decision: reply.
Why: the source has a regional chapter list, so this is answerable from the source.
A good reply: confirm which regions the {{product_kind}} covers, in one sentence,
using the chapter names as they appear in the source. Close with {{cta_phrase_1}}
only if they asked where to get it. They did not, so do not.

Comment: "how long does shipping take to Canada?"
Decision: escalate.
Why: nothing in the source answers it, and a guess about delivery is a promise.
A good reply: say you will get them an answer and that {{escalation_contact}} will
follow up.
```

This repository ships two worked `voice.md` files as reference points:
`examples/field-guide-book/prompts/voice.md`, the long one, and
`examples/sourdough-course/prompts/voice.md`, the short one. Read the short one and it
will look like less rule. It is not a lesser version: the full
rule set is a choice you make for your own product, not a floor every voice file has
to reach. A course sold by two people who address their own audience directly needs
fewer paragraphs than a book sold from an account most viewers do not know publishes
anything, and both files pass the same acceptance tests.

`tests/fixtures/nazzef-kit-ar` is the proof that none of this is tied to English or to
a Latin alphabet: a fictional product, its config, its voice file and its worked
examples, written entirely in Arabic. Its `behavior.separator` is the Arabic comma, not
the Latin one, which is exactly the point: the separator is read from config, never
guessed from the script of the text, so a reply written in a script the tool has never
seen still gets the punctuation you configured for it rather than punctuation borrowed
from somewhere else.

## Changing the call to action

CTA styles are defined entirely in TOML. `[behavior].cta_mode` names one of your
`[cta.*]` tables, and it is validated against your own config rather than against a
list inside the code. Add as many as you like:

```toml
[behavior]
cta_mode = "direct"

[cta.direct]
instruction = "If someone asks where to get it, give the link: {{purchase_link}}."
phrases = ["here is the link: {{purchase_link}}",
           "you can get it at {{purchase_link}}",
           "{{purchase_link}}"]

[cta.bio_pointer]
instruction = "If someone asks where to get it, say the link is in the bio. Do not write the URL."
phrases = ["the link is in the bio", "it is in the bio", "you will find it in the profile"]
```

One CTA style applies to a whole run, because it lives in the cached prefix. A comment
file that mixes places where links are allowed with places where they are not wants two
runs and two configs. That is a real limitation and it is written down in
`docs/limits.md` rather than papered over here.
