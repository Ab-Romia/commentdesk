# SPDX-License-Identifier: Apache-2.0
import pytest

from commentdesk.sources import SOURCES, SourceError, load_knowledge, register
from commentdesk.sources.text import load_text


@pytest.fixture
def registry_snapshot():
    """Restore SOURCES after a test that registers into it."""
    saved = dict(SOURCES)
    yield SOURCES
    SOURCES.clear()
    SOURCES.update(saved)


def test_text_source_reads_a_single_file(tmp_path):
    doc = tmp_path / "knowledge.md"
    doc.write_text("Chapter one.\nChapter two.\n", encoding="utf-8")
    assert load_text(doc, {}) == "Chapter one.\nChapter two.\n"


def test_text_source_strips_a_byte_order_mark(tmp_path):
    doc = tmp_path / "knowledge.md"
    doc.write_bytes("Body".encode("utf-8-sig"))
    assert load_text(doc, {}) == "Body"


def test_text_source_concatenates_a_directory_in_name_order(tmp_path):
    kb = tmp_path / "kb"
    kb.mkdir()
    (kb / "c-third.md").write_text("Gamma", encoding="utf-8")
    (kb / "a-first.md").write_text("Alpha", encoding="utf-8")
    (kb / "b-second.txt").write_text("Bravo", encoding="utf-8")
    (kb / "cover.pdf").write_bytes(b"%PDF-1.7")
    (kb / "drafts").mkdir()
    assert load_text(kb, {}) == (
        "\n\n## a-first\n\nAlpha\n\n## b-second\n\nBravo\n\n## c-third\n\nGamma"
    )


def test_load_knowledge_dispatches_on_the_configured_source(tmp_path):
    (tmp_path / "kb.md").write_text("Body", encoding="utf-8")
    cfg = {"knowledge": {"source": "text", "path": "kb.md"}}
    assert load_knowledge(cfg, tmp_path) == "Body"


def test_load_knowledge_resolves_the_path_against_the_config_dir(tmp_path):
    project = tmp_path / "project"
    (project / "docs").mkdir(parents=True)
    (project / "docs" / "kb.md").write_text("Body", encoding="utf-8")
    cfg = {"knowledge": {"source": "text", "path": "docs/kb.md"}}
    assert load_knowledge(cfg, project) == "Body"


def test_missing_knowledge_path_is_an_error(tmp_path):
    cfg = {"knowledge": {"source": "text", "path": "kb.md"}}
    with pytest.raises(SourceError) as exc:
        load_knowledge(cfg, tmp_path)
    assert "kb.md" in str(exc.value)


def test_unknown_source_name_lists_the_registered_ones(tmp_path):
    (tmp_path / "kb.md").write_text("Body", encoding="utf-8")
    cfg = {"knowledge": {"source": "html_scrape", "path": "kb.md"}}
    with pytest.raises(SourceError) as exc:
        load_knowledge(cfg, tmp_path)
    message = str(exc.value)
    assert "html_scrape" in message
    assert "text" in message


def test_empty_knowledge_file_is_an_error(tmp_path):
    """An empty knowledge base is not a cheap run, it is an ungrounded one.

    Nothing downstream can tell the difference between a model quoting a source
    and a model quoting nothing, so this is the last place it can be caught.
    """
    (tmp_path / "kb.md").write_text("   \n\n", encoding="utf-8")
    cfg = {"knowledge": {"source": "text", "path": "kb.md"}}
    with pytest.raises(SourceError) as exc:
        load_knowledge(cfg, tmp_path)
    assert "empty" in str(exc.value).lower()


def test_register_adds_a_handler_and_returns_it_unchanged(registry_snapshot):
    def handler(path, options):
        return "handled"

    assert register("fixture_source")(handler) is handler
    assert registry_snapshot["fixture_source"] is handler


def test_register_refuses_to_shadow_an_existing_name(registry_snapshot):
    with pytest.raises(SourceError):
        register("text")(lambda path, options: "")
    assert registry_snapshot["text"] is load_text
