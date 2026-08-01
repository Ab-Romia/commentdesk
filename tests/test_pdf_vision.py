# SPDX-License-Identifier: Apache-2.0
"""Tests for the PDF knowledge source.

No PDF is opened and pymupdf is never needed: page rendering is the one function that
wants it, and these tests replace it.
"""

import base64
import importlib
import sys
import types

import pytest

from commentdraft.sources import SourceError, pdf_vision


class FakeClient:
    """A client that answers with the given items in order, raising any item that is
    an exception. That is enough to reproduce the failure that matters, which is a
    batch failing after earlier batches have already been paid for."""

    def __init__(self, items):
        self.items = list(items)
        self.calls = []
        self.chat = types.SimpleNamespace(completions=self)

    def create(self, **kwargs):
        self.calls.append(kwargs)
        item = self.items.pop(0)
        if isinstance(item, Exception):
            raise item
        message = types.SimpleNamespace(content=item)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])


def fake_pages(count):
    return [f"page-{i}".encode("ascii") for i in range(count)]


def test_batches_keeps_order_and_the_short_tail():
    assert pdf_vision.batches([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]
    assert pdf_vision.batches([], 4) == []


def test_to_data_url_round_trips_the_png():
    url = pdf_vision.to_data_url(b"\x89PNG\r\n")
    assert url.startswith("data:image/png;base64,")
    assert base64.b64decode(url.split(",", 1)[1]) == b"\x89PNG\r\n"


def test_the_prompt_names_no_kind_of_document():
    """Naming a kind of document is how a general tool turns back into the single
    product it came from."""
    prompt = pdf_vision.TRANSCRIBE_PROMPT
    prompt.encode("ascii")
    lowered = prompt.lower()
    for word in ("book", "chapter", "verse", "scripture", "novel", "manual", "textbook", "guide"):
        assert word not in lowered
    assert "translate" in lowered
    assert "summar" in lowered


def test_transcribe_refuses_to_overwrite_and_spends_nothing(tmp_path):
    """The file already there may be a transcription someone has read and corrected,
    it is gitignored by class, and nothing here can get it back."""
    out = tmp_path / "knowledge.md"
    out.write_text("corrected by hand", encoding="utf-8")
    client = FakeClient(["never reached"])
    with pytest.raises(SourceError) as excinfo:
        pdf_vision.transcribe_pdf(tmp_path / "doc.pdf", out, {"model": "vendor/a"}, client)
    assert str(out) in str(excinfo.value)
    assert out.read_text(encoding="utf-8") == "corrected by hand"
    assert client.calls == []


def test_a_failed_batch_keeps_the_pages_already_paid_for(tmp_path, monkeypatch):
    """The second batch fails. The first one was billed, so it is written out before
    the error is re-raised, and it is written under a name that cannot be mistaken for
    a finished transcription."""
    monkeypatch.setattr(pdf_vision, "render_pages", lambda pdf, dpi=150: fake_pages(8))
    client = FakeClient(["first four pages", RuntimeError("gateway refused")])
    out = tmp_path / "knowledge.md"
    with pytest.raises(RuntimeError):
        pdf_vision.transcribe_pdf(tmp_path / "doc.pdf", out, {"model": "vendor/a"}, client, batch=4)
    assert not out.exists()
    salvaged = list(tmp_path.glob("knowledge-partial-*batches-*.md"))
    assert len(salvaged) == 1
    assert salvaged[0].read_text(encoding="utf-8") == "first four pages"


def test_a_clean_run_joins_every_batch(tmp_path, monkeypatch):
    monkeypatch.setattr(pdf_vision, "render_pages", lambda pdf, dpi=150: fake_pages(6))
    client = FakeClient(["part one", "part two"])
    out = tmp_path / "knowledge.md"
    result = pdf_vision.transcribe_pdf(
        tmp_path / "doc.pdf",
        out,
        {"model": "vendor/a", "params": {"provider": {"data_collection": "deny"}}},
        client,
        batch=4,
    )
    assert result == out
    assert out.read_text(encoding="utf-8") == "part one\n\npart two"
    assert len(client.calls) == 2
    # The deny flag travels on a transcription exactly as it does on a reply call.
    assert client.calls[0]["extra_body"] == {"provider": {"data_collection": "deny"}}
    assert client.calls[0]["messages"][0]["content"][0]["text"] == pdf_vision.TRANSCRIBE_PROMPT
    assert len(client.calls[0]["messages"][0]["content"]) == 5  # prompt plus 4 pages
    assert list(tmp_path.glob("*partial*")) == []


def test_loading_reads_the_transcript_beside_the_pdf(tmp_path):
    (tmp_path / "doc.md").write_text("transcribed text", encoding="utf-8")
    assert pdf_vision.load_pdf_vision(tmp_path / "doc.pdf", {}) == "transcribed text"


def test_loading_follows_an_explicit_transcript_option(tmp_path):
    (tmp_path / "other.md").write_text("elsewhere", encoding="utf-8")
    options = {"source": "pdf_vision", "transcript": "other.md"}
    assert pdf_vision.load_pdf_vision(tmp_path / "doc.pdf", options) == "elsewhere"


def test_loading_without_a_transcript_names_the_command_that_makes_one(tmp_path):
    """Reading is separated from transcribing, so the error has to say which command
    to run rather than silently starting a run that costs money."""
    with pytest.raises(SourceError) as excinfo:
        pdf_vision.load_pdf_vision(tmp_path / "doc.pdf", {})
    assert "ingest" in str(excinfo.value)


def test_rendering_without_pymupdf_names_the_extra(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "pymupdf", None)
    with pytest.raises(SourceError) as excinfo:
        pdf_vision.render_pages(tmp_path / "doc.pdf")
    assert "commentdraft[pdf]" in str(excinfo.value)


def test_the_registry_imports_without_the_pdf_extra(monkeypatch):
    """The extra is optional, so a machine without pymupdf must still import the
    registry, register both handlers, and run against a text source."""
    monkeypatch.setitem(sys.modules, "pymupdf", None)
    for name in [n for n in sys.modules if n.startswith("commentdraft")]:
        monkeypatch.delitem(sys.modules, name, raising=False)
    module = importlib.import_module("commentdraft.sources")
    assert "text" in module.SOURCES
    assert "pdf_vision" in module.SOURCES
