# SPDX-License-Identifier: Apache-2.0
"""A knowledge source that transcribes PDF pages with a vision capable model.

The rendered page is transcribed rather than the PDF's own text layer, because that
layer is only ever as good as the tool that wrote it: right to left scripts come back
with the visual order already applied, ligatures come back split into pieces, and a
two column layout comes back interleaved. None of that happens to a rendered page,
because a rendered page is what a reader sees.

The dependency is optional and lives behind the pdf extra, so importing this module
costs nothing and only the function that rasterises a page asks for it.
"""

import base64
import time
from pathlib import Path

from . import SourceError, read_utf8, register

# Neutral on purpose. It says what to do with the pixels and nothing about what the
# document is, because the moment a prompt names a kind of document it stops being
# usable for every other kind.
TRANSCRIBE_PROMPT = (
    "Transcribe the text of these document pages faithfully. Preserve headings as "
    "headings and keep the paragraph breaks where they are. Do not summarise. Do "
    "not translate. Do not correct what is printed. Do not add commentary or notes "
    "of your own. Output only the transcribed text."
)


def to_data_url(png):
    """Images travel inline. A transcription is a one time job on a local file, so
    uploading the pages somewhere first would add a second thing that can fail and a
    second place the operator's document sits."""
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def batches(items, size=4):
    """Pages go up in groups. One call per page pays for the prompt over and over,
    and a whole document in one call runs past what a single response can hold."""
    return [items[i : i + size] for i in range(0, len(items), size)]


def render_pages(pdf, dpi=150):
    """One PNG per page, in page order.

    pymupdf is imported here rather than at module scope so that importing this
    package works without the pdf extra installed. A machine that only reads an
    already made transcription never reaches this function.
    """
    try:
        import pymupdf
    except ImportError as exc:
        raise SourceError(
            'rendering a PDF needs the pdf extra: uv tool install "commentdesk[pdf]"'
        ) from exc
    doc = pymupdf.open(Path(pdf))
    try:
        return [page.get_pixmap(dpi=dpi).tobytes("png") for page in doc]
    finally:
        doc.close()


def transcribe_batch(client, model_cfg, pngs):
    """One call: the instruction, then the page images, in order.

    params is passed through as extra_body exactly as it is on a reply call, which is
    how provider.data_collection = "deny" reaches a transcription too. A document the
    operator paid to have transcribed is the last thing that should end up in
    somebody's training set.
    """
    content = [{"type": "text", "text": TRANSCRIBE_PROMPT}]
    content += [{"type": "image_url", "image_url": {"url": to_data_url(png)}} for png in pngs]
    resp = client.chat.completions.create(
        model=model_cfg["model"],
        messages=[{"role": "user", "content": content}],
        # `or {}` rather than a default, matching engine.call_model: a config that
        # writes `params =` with nothing after it hands over None, and a default
        # only covers the key being absent. Unreachable behind load_config, and
        # this file is the worked example docs/sources.md points a reader at.
        extra_body=model_cfg.get("params") or {},
    )
    return (resp.choices[0].message.content or "").strip()


def transcribe_pdf(pdf, out, model_cfg, client, *, dpi=150, batch=4):
    """Transcribe every page of `pdf` into `out` and return the path written."""
    pdf, out = Path(pdf), Path(out)
    # Refuse before spending anything. The file already sitting there may be a
    # transcription somebody has read and corrected line by line, it is gitignored by
    # class so version control does not have it either, and nothing here can get it
    # back. Deleting it has to be a decision, not a side effect of re-running.
    if out.exists():
        raise SourceError(f"{out} already exists: delete it, or write the transcription elsewhere")
    pages = render_pages(pdf, dpi=dpi)
    print(f"{len(pages)} pages rendered")
    parts = []
    try:
        for index, chunk in enumerate(batches(pages, batch)):
            first = index * batch + 1
            print(f"transcribing pages {first} to {first + len(chunk) - 1} of {len(pages)}")
            parts.append(transcribe_batch(client, model_cfg, chunk))
    except BaseException:
        # The batches that already came back were paid for, and they are worth more
        # than a clean exit. Written under a name that carries the batch count and the
        # time, so a second failure cannot overwrite what the first one salvaged, and
        # so nobody mistakes it for a finished transcription. Then re-raised: a
        # partial result must not look like a whole one to whatever called this.
        if parts:
            stamp = int(time.time())
            salvage = out.with_name(f"{out.stem}-partial-{len(parts)}batches-{stamp}{out.suffix}")
            salvage.parent.mkdir(parents=True, exist_ok=True)
            salvage.write_text("\n\n".join(parts), encoding="utf-8")
            print(
                f"failed after {len(parts)} batch(es), kept what was paid for in "
                f"{salvage} (re-running transcribes every page again)"
            )
        raise
    text = "\n\n".join(parts)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"wrote {out} ({len(text)} chars)")
    return out


@register("pdf_vision")
def load_pdf_vision(path, options):
    """Return the transcription belonging to `path`.

    Reading is deliberately separated from transcribing. A transcription costs real
    money and takes minutes, so it happens once, under a command the operator typed,
    and every run after that reads the file it produced. That also keeps this function
    clear of both the network and the pdf extra, which is why a run works on a machine
    that has neither as long as the transcription is already there.

    The transcript sits next to the PDF under the same stem unless [knowledge] names
    another one. A relative name is resolved against the PDF's own directory, so the
    pair travels together when the operator moves it.
    """
    path = Path(path)
    transcript = path.parent / (options.get("transcript") or path.with_suffix(".md").name)
    if not transcript.exists():
        raise SourceError(f"{transcript} not found: run 'commentdesk ingest' to transcribe {path}")
    # Written by this tool as UTF-8, then corrected by hand in whatever editor the
    # operator has, which is where a re-save in a legacy encoding gets in.
    return read_utf8(transcript)
