# Why each safety property exists

This is **not legal advice**. The clauses below were read on 2026-07-31, they change
without notice, and a platform's policy or a law's guidance can be reworded the day
after this file is. Read the source yourself before you rely on any of it. This is a
map from a feature in this repository to the specific rule it was built to satisfy,
so that a reviewer can check the reasoning instead of trusting a summary, and so that
nobody removes a feature without knowing what it was holding up. You are the operator.
The obligations belong to you, not to this tool, and this page is one input to
meeting them, not a substitute for meeting them.

## The map

| Property | How it is enforced here | The clause it exists for |
|---|---|---|
| It never posts | No HTTP client for any platform exists anywhere in the package; `tests/test_generality.py::test_the_package_contains_no_client_for_any_platform` walks the AST of every module on every push and asserts it by import name and by hostname string. | YouTube API Services Developer Policies, section III.I.2: an API client "must not automate or trigger... comments... or other actions without the user's prior specific and express consent." There is no action taken on anyone's behalf, so the clause is satisfied by construction rather than by policy alone. |
| A person holds editorial responsibility before anything ships | The review page carries a draft banner until a person passes `--approved`, and there is no code path from a draft to any platform that does not go through a person copying it by hand. | YouTube API Services Developer Policies, section III.E.3.d: an API client "must clearly identify any actions that they take to insert, share, update, or delete data or content on the authorizing user's behalf," and "the user must expressly consent to those actions prior to their actual execution." Meta's Developer Policies, section 1.7: "obtain consent from people before publishing content or taking any other action on their behalf." Both describe a consent step this tool never reaches, because it never takes the action at all. |
| It says what it is when asked | `[behavior].bot_disclosure_text` is required, validated as a non-empty string, and rendered into the prefix verbatim through `{{bot_disclosure_text}}`. There is no setting that turns the disclosure off; the evasive mode was removed from the config schema rather than defaulted to off, so it cannot be reintroduced by a typo. | EU AI Act Article 50(1): a provider of a system intended to interact with natural persons must design it so "the natural persons concerned are informed that they are interacting with an AI system." Article 50(5) is the separate paragraph that adds the timing: that information "shall be provided... in a clear and distinguishable manner at the latest at the time of the first interaction or exposure." YouTube API Services Developer Policies, section III.I.11, separately prohibits use of the API that would "confuse, deceive, defraud, mislead... or harass" anyone, which is the same property named from the angle of what evading the disclosure would do. |
| A published draft can still skip the disclosure once a person owns it | Nothing here disables `bot_disclosure_text`. This row states the boundary rather than a feature: Article 50(4) is about the operator's own downstream publication, not about this tool. | EU AI Act Article 50(4) exempts disclosure for text that "has undergone a process of human review or editorial control and where a natural or legal person holds editorial responsibility for the publication of the content." That provision is written for published text on matters of public interest, not for a reply to a social media comment, and citing it here is deliberately narrow: it names the same idea this tool's draft-and-approve design is built around (a human takes responsibility before anything goes out), not a claim that this specific paragraph governs your use case. Check whether it, or a different transparency rule in your jurisdiction, actually applies to what you publish. |
| It stays inside TikTok's terms too | Same answer as the row above: nothing posts, so nothing here needs TikTok's authorization. | TikTok's Terms of Service prohibit interacting with the platform through "any automated means" without TikTok's own authorization. This project has not pinned a section number for that clause because none was confirmed against a stable citation while writing this page; read TikTok's current terms directly rather than trusting a number here. |
| It cannot claim what your source does not say | The knowledge document is the only thing a draft may state as fact; a question it does not answer is meant to become `escalate` rather than a guess. `docs/architecture.md` and `docs/writing-a-voice.md` describe the mechanism. | Consumer protection law in most jurisdictions, and your own liability to whoever reads the reply. No platform clause is cited here on purpose: this property is not about any platform's rules, it is about what you are allowed to tell a customer, and that is a body of law specific to your jurisdiction and your product. |
| Your inputs are not sent for training | Every model entry, the default `[model]` and every `[[bakeoff.models]]` entry alike, must set `params.provider.data_collection = "deny"` nested inside `provider`, checked before the first call in every run. `docs/bakeoff.md` covers why the nesting matters and what it does and does not promise. | Not a platform clause. It is an instruction sent with the request to whichever gateway `[model].base_url` names; whether that gateway and the model behind it honor it is between you and whoever operates them, which is exactly why it is written down here rather than assumed. |
| Your source text stays on your machine | `knowledge/`, `*.pdf` and `*.csv` are excluded from version control by class, not by filename, in `.gitignore`. | Not a legal clause either. It is simply the mistake that is easy to make once, by committing a real product document into a public repository, and impossible to fully take back afterward. |
| Provenance | Every row in a review CSV records the exact `model` string that produced the draft. | Not a specific clause. It is the ordinary record-keeping expectation behind most of the transparency obligations above: you should be able to answer "which run, and which model, produced this" without guessing. |

## Why `data_collection` has to sit inside `provider`

At the top level of a request's parameters, a gateway commonly accepts the key,
ignores it, and routes with its own permissive default intact. Nested one level
inside `provider`, it is read. A flag sitting in the wrong place is indistinguishable
from a working one unless somebody reads the request body, which is exactly the class
of mistake that survives unnoticed for a long time. `commentdraft` checks the nesting
in code, on every model entry, before the first call of a run, rather than trusting a
setting on an account somewhere that nothing here can see or verify.

## Things this tool does not do for you

- It does not obtain platform API access, hold a token, or manage a scope. If you
  later build something that posts, every consent clause named above becomes yours to
  satisfy directly, and none of the reasoning on this page transfers automatically.
- It does not apply a disclosure label to anything you publish. Whatever labelling or
  disclosure your platform and your jurisdiction require at the moment of publication
  happens where you publish, using whatever mechanism that platform provides for it.
- It does not keep an audit log on your behalf. It writes a CSV per run. Retaining
  those, and for how long, is your policy to set, not a feature this tool has.
