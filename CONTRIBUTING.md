# Contributing

Pull requests are welcome. For anything larger than a small fix, please open an
issue first, so nobody spends a weekend on something that gets declined for a reason
they were never told.

## Setup

```bash
git clone https://github.com/Ab-Romia/commentdraft.git
cd commentdraft
uv sync --all-extras
make check
```

`make check` runs lint, typecheck and the whole test suite, in that order, and it is
exactly what CI runs. Run it before you open a pull request; a change that fails it
locally will fail it there too.

The test suite runs offline, with no network access and no API key. If a change makes
that untrue, the change is wrong, not the test that caught it.

One test is the deliberate exception. `test_every_shipped_model_id_exists_on_openrouter`
in `tests/test_examples.py` fetches OpenRouter's live model list and checks every model
ID in every shipped example config and test fixture against it, so a model a provider
has retired or renamed is caught here instead of on someone's first live run. It is
marked `live` and excluded from the default run (`addopts` passes `-m "not live"`), so
`make check` and a plain `pytest` stay offline. Run it before a release:

```bash
uv run pytest -m live
```

It needs network access to `openrouter.ai` and no API key, since the model list is a
public endpoint.

## Four rules a well-meaning pull request breaks by accident

1. **No non-ASCII character in any string literal under `src/`, docstrings included.**
   A test walks the AST of every module under `src/` and asserts it. This is the
   machine-checked form of "the engine holds no human-language copy": if you need
   words for a person to read, they belong in an operator's own config or voice file,
   never in a `.py` file.
2. **No posting path that is not gated.** Everything that can reach a platform goes
   through `src/commentdraft/approve.py`, one reply and one keystroke at a time.
   There is no `--yes`, no `--all` and no config key that changes that, and adding
   one fails a test in `tests/test_guarantees.py` rather than merely being frowned
   at. Network clients belong under `src/commentdraft/platforms/` and nowhere else.
   Several honest claims in `README.md` and `docs/platform-policy.md` depend on all
   of that staying true. A pull request that adds an unattended route to a platform
   will be declined regardless of what it is for.
3. **`data_collection` stays denied.** Every model entry, in every example config and
   every test fixture, sends `params.provider.data_collection = "deny"` nested inside
   `provider`. Do not move it to the top level of `params`, where a gateway commonly
   accepts the key, ignores it, and routes with data collection left at its own
   default. `docs/bakeoff.md` explains why the nesting is the part that matters.
4. **No em dash and no en dash, in prose, in code comments, or in a commit message.**
   `sanitize_reply` strips both out of a drafted reply before it ever reaches a
   reviewer; this repository holds its own prose to the same rule rather than asking
   contributors to follow a standard the codebase does not follow itself. A comma or
   a full stop says the same thing.

`make check` enforces the first and the third of these directly, and a docs test
enforces the fourth across every Markdown file outside `tests/fixtures/`. The second
has no automated check that a determined contributor could not route around; it is
enforced by review, and the answer will still be no.

## Style

- **Tests first.** A pull request that changes behavior without a test that failed
  before the change and passes after it will not be merged.
- **Tests are behavioral.** Asserting that a function returns whatever you just made
  it return is not a test of anything.
- **Comments explain why, not what.** If a choice is not obvious from the code next
  to it, the comment that explains the choice is worth more than a comment that
  narrates the line below it.
- **Conventional commit subjects:** `feat:`, `fix:`, `docs:`, `test:`, `refactor:`,
  `chore:`. No trailers and no attribution footers.
- **Public functions carry type annotations.** `make typecheck` runs `pyright` and it
  is not advisory; a pull request that fails it does not merge on the promise of a
  follow-up.

## Adding a knowledge source

`docs/sources.md` walks through the whole extension point: one file, one `@register`
decorator, deterministic output, and no network access from inside the handler.

## Things that will be declined

- Anything that posts, queues, schedules, or authenticates against a platform, for
  the reason given above.
- Retrieval, chunking, or a vector store. `docs/architecture.md` explains the
  decision and the one condition under which it would change, and that condition is a
  different project from this one.
- Per-row prompt variation, unless it demonstrably keeps the system prefix
  byte-identical across a run; see `docs/limits.md` for why that constraint exists
  and what it currently rules out.
- Human-language copy moved into a Python module instead of an operator's own file.
- A new runtime dependency. Today's list is `openai`, used as an OpenAI-compatible
  client pointed at whatever gateway the operator configures, plus `pymupdf` behind
  the optional `pdf` extra. Adding a third is a design discussion to have in an issue
  first, not a pull request to send first.

## License

By contributing, you agree that your contribution is licensed under Apache-2.0, the
same license as the rest of the project. See `LICENSE` and `NOTICE`.
