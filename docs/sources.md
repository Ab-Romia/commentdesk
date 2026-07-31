# Knowledge sources

A knowledge source is one function that turns a configured path into text. That
string becomes the whole grounding for a run: it is the only thing a draft may state
as fact, and it goes into the cached prefix once per run. That is the whole extension
point. There is no plugin manifest, no entry point scan, and no lifecycle.

```python
SOURCES: dict[str, Callable[[Path, dict], str]]
```

The registry lives in `src/commentdesk/sources/__init__.py`. It holds the `SOURCES`
dict above, the `register(name)` decorator that fills it, `load_knowledge(cfg,
config_dir)`, which reads `[knowledge]` and dispatches to the named handler, and
`SourceError`, which every handler should raise instead of anything else.

You select one in `config.toml`:

```toml
[knowledge]
source = "text"
path = "knowledge.md"
```

## What a handler receives

A handler is a function of shape `(path: Path, options: dict) -> str`.

`path` arrives already resolved: `load_knowledge` reads `knowledge.path`, resolves it
against the directory holding `config.toml`, and checks that it exists before calling
the handler at all. A handler never resolves a path itself.

`options` is the whole `[knowledge]` table, handed over as a plain `dict` copy. That
copy includes `source` and `path` themselves along with anything else you wrote in
that table; a handler with settings of its own just reads them with
`options.get("your_key", default)`, and the config schema never has to learn the new
key exists. It is a copy, not the live table, so nothing a handler does to it can
reach back into the loaded config.

If the returned string is empty or only whitespace, `load_knowledge` raises
`SourceError` before the prefix is ever built. An empty knowledge document would mean
every factual claim in the run rests on nothing, and nothing downstream can tell a
grounded draft from an ungrounded one after the fact, so this is the last point that
can catch it.

## The built-in sources

### `text`

```toml
[knowledge]
source = "text"
path = "knowledge.md"
```

Reads one `.md` or `.txt` file and returns its contents. If `path` is a directory, it
concatenates every `.md` and `.txt` file directly inside it in sorted filename order,
each preceded by a heading made from the file stem, so the model can tell where one
document ends and the next begins. Sorted order means the assembled text is
byte-identical between runs, which is what keeps the cached prefix warm; a directory
whose sections arrive in a different order than yesterday pays the uncached price on
every call of that run. Reads as `utf-8-sig`, so a byte order mark a desktop editor
left behind is dropped instead of becoming the first character of the prompt. Zero
dependencies. This is the default, and it is what most configs use forever.

### `pdf_vision`

```toml
[knowledge]
source = "pdf_vision"
path = "field-guide.pdf"
transcript = "knowledge.md"
```

Behind an optional extra:

```bash
uv tool install "commentdesk[pdf]"
```

This one differs from `text` in an important way: it is a one time conversion, not a
per run reader. You run `commentdesk ingest` once to produce a text file, you read
that file yourself, and every run after that reads the text file, never the PDF
again.

```bash
commentdesk ingest --config config.toml --pdf field-guide.pdf --out knowledge.md
```

Reading and transcribing are two different paths through `path`, and that is worth
being precise about. At run time, the handler never opens the PDF: it looks beside
`path` for the transcript, named by the `transcript` option above, or, if you leave
that option out, for `path` with its suffix swapped for `.md` (`field-guide.md`
here). Set `transcript` explicitly, as above, whenever you want the output of
`ingest` to land under a different name than that default, the way `knowledge.md`
does here.

The PDF still has to be sitting at `path`, transcript or no. `load_knowledge` checks
that `[knowledge].path` exists before it calls any handler, `pdf_vision` included, so
deleting the PDF once you have a transcript you trust turns every future run into a
`knowledge path not found` error even though no run after `ingest` ever reads the
PDF's bytes again. Keep the PDF next to the transcript, or point `path` at some other
file that continues to exist.

It renders each page of the PDF to an image and asks a vision capable model to
transcribe it, rather than reading the PDF's own embedded text layer. That layer is
only as reliable as whatever wrote it: a right to left script comes back with the
visual order already applied, ligatures come back split across separate spans, and a
two column layout comes back interleaved. A rendered page is what a person looking at
it would see, and transcribing that is the one approach that behaves the same
regardless of script or layout.

Two behaviours are worth knowing before you run it, and both exist because this step
spends real money:

- **It refuses to overwrite an existing output file.** The file already sitting at
  `--out` may be a transcription somebody has already read and corrected by hand, and
  nothing in this tool can get that back. Pass a different `--out`, or delete the old
  file yourself first. Deleting your knowledge file has to be a decision you made on
  purpose, never a side effect of running the command again.
- **A failed batch does not lose the batches before it.** Pages are transcribed in
  groups; if a later batch fails, the earlier ones were already paid for. They are
  written to a file named after the original output path with the batch count and a
  timestamp added, for example `knowledge-partial-4batches-1735689600.md`, so a second
  failed attempt cannot overwrite what the first one salvaged and nobody mistakes a
  partial result for a finished one. The error is then re-raised rather than
  swallowed.

Your `[model]` during ingest must point at a vision capable route. The model you want
for per comment cost usually is not that model, so it is normal to point `--config` at
a second config file for the one time ingest and switch back to the everyday one
afterward.

The transcription prompt is neutral: it asks for a faithful transcription of printed
pages and says nothing about what kind of document it is looking at. There is no
subject specific check afterward, and there should not be one. A check that only makes
sense for one kind of document belongs to whoever owns that document, not to a
general purpose tool.

## Writing your own

One file, one decorated function. Here is a source that reads a directory of subtitle
files:

```python
# SPDX-License-Identifier: Apache-2.0
"""Knowledge source: a directory of subtitle files."""

import re
from pathlib import Path

from . import SourceError, register

TIMESTAMP = re.compile(r"^\d+$|^[\d:,]+\s*-->\s*[\d:,]+$")


@register("subtitles")
def load_subtitles(path: Path, options: dict) -> str:
    """Concatenate .srt files into plain prose.

    options:
        suffix: file extension to look for. Default ".srt".
    """
    suffix = options.get("suffix", ".srt")
    files = sorted(path.glob(f"*{suffix}")) if path.is_dir() else [path]
    if not files:
        raise SourceError(f"no {suffix} files under {path}")

    parts = []
    for f in files:
        lines = [
            line.strip()
            for line in f.read_text(encoding="utf-8-sig").splitlines()
            if line.strip() and not TIMESTAMP.match(line.strip())
        ]
        parts.append(f"\n\n## {f.stem}\n\n" + " ".join(lines))
    return "".join(parts)
```

Save that as, say, `src/commentdesk/sources/subtitles.py`. The `@register("subtitles")`
call above only runs once Python imports the module, and nothing imports it yet, so
you have to add it to the bottom of `src/commentdesk/sources/__init__.py`:

```python
from . import pdf_vision, subtitles, text  # noqa: E402,F401  imported for the side effect of registering
```

That one line is the entire wiring step. Adding a source to the package is one new
file plus one new name on that line; nothing else in the package needs to learn the
name exists. Then select it the same way you select any other source:

```toml
[knowledge]
source = "subtitles"
path = "transcripts/"
suffix = ".srt"
```

Four rules for a handler, all of which follow from the cache:

1. **Return text, not chunks.** The whole return value goes straight into the prompt
   prefix. There is no assembly step after your function returns.
2. **Be deterministic.** The same input has to produce byte-identical output, or every
   run starts cold. Sort anything you iterate over, the way both built-in sources do.
3. **Raise `SourceError`, with the path in the message.** The operator reading that
   message is the person who has to act on it, not someone who is going to read your
   code first. That includes the encoding case, which is the one that gets missed:
   `UnicodeDecodeError` is a `ValueError`, so nothing that catches `OSError` catches
   it and it reaches the operator as a traceback. Read your files through
   `sources.read_utf8`, which both built-in handlers use; a document saved in a
   legacy encoding then arrives as a message naming the file and saying to save it
   as UTF-8.
4. **Do not fetch anything over the network.** Sources read local files. A handler
   that reaches out to the network is a handler whose output can change out from
   under a cached prefix, and it puts a client for something into a package that is
   supposed to hold none.
