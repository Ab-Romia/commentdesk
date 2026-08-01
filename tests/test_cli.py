# SPDX-License-Identifier: Apache-2.0
import argparse
import json
from typing import ClassVar

import pytest

from commentdraft.cli import format_trace, main, safe_name
from conftest import scripted_reviewer

CONFIG = """
[product]
name = "The Backyard Forager's Field Guide"
kind = "field guide"
price_text = "$18"
purchase_link = "https://example.com/field-guide"
escalation_contact = "the team"

[knowledge]
source = "text"
path = "knowledge.md"

[voice]
rules = "prompts/voice.md"
examples = "prompts/examples.md"

[behavior]
cta_mode = "direct"
plug_cap = 0.75
max_reply_sentences = 2
bot_disclosure_text = "Replies are drafted with software and read by a person first."
plug_markers = ["example.com/field-guide"]
banned_emoji = ""
separator = ", "
platforms = ["video-site", "photo-site"]

[cta.direct]
instruction = "If someone asks where to get it, give the link: {{purchase_link}}."
phrases = ["here is the link: {{purchase_link}}", "you can get it at {{purchase_link}}"]

[model]
label = "small"
base_url = "https://openrouter.ai/api/v1"
model = "test/model-small"
api_key_env = "CD_KEY_MAIN"

[model.pricing]
input_per_mtok = 0.30
cached_per_mtok = 0.06
output_per_mtok = 1.20
cache_write_per_mtok = 0.40

[model.params]
reasoning = { enabled = false }
provider = { data_collection = "deny" }
"""

VOICE = """
Answer like the person who wrote the guide: short, plain, one idea per reply.
Keep it to {{max_reply_sentences}} sentences.
State only what is inside the <{{knowledge_tag}}> block. Never guess a fact.
{{cta_instruction}}
If it needs a person, hand it to {{escalation_contact}}.
If someone asks whether you are software, tell them: {{bot_disclosure_text}}
"""

EXAMPLES = """
Comment: how much is it
Reply: {{price_text}}, and {{cta_phrase_1}}

Comment: first
Decision: skip, there is no question in it.
"""

KNOWLEDGE = """
The guide covers wild garlic, elderflower and three common mushrooms.
It is 180 pages and costs eighteen dollars.
"""

COMMENTS = """id,platform,author,comment,post_title
1,video-site,sam,how much does it cost,foraging clip
2,video-site,alex,first,foraging clip
3,photo-site,jo,does it cover mushrooms,mushroom clip
"""

GOOD_BAKEOFF = """
[[bakeoff.models]]
label = "alpha"
model = "test/model-alpha"
api_key_env = "CD_KEY_ALT"
pricing = { input_per_mtok = 0.1, cached_per_mtok = 0.02, output_per_mtok = 0.4, cache_write_per_mtok = 0.0 }
params = { reasoning = { enabled = false }, provider = { data_collection = "deny" } }
"""

LEAKY_BAKEOFF = """
[[bakeoff.models]]
label = "alpha"
model = "test/model-alpha"
params = { reasoning = { enabled = false } }
"""


def build_product(tmp_path, extra=""):
    """Write a complete, valid product directory and return the config path."""
    (tmp_path / "prompts").mkdir(parents=True)
    (tmp_path / "prompts" / "voice.md").write_text(VOICE, encoding="utf-8")
    (tmp_path / "prompts" / "examples.md").write_text(EXAMPLES, encoding="utf-8")
    (tmp_path / "knowledge.md").write_text(KNOWLEDGE, encoding="utf-8")
    (tmp_path / "comments.csv").write_text(COMMENTS, encoding="utf-8")
    config = tmp_path / "config.toml"
    config.write_text(CONFIG + extra, encoding="utf-8")
    return config


def clear_keys(monkeypatch):
    monkeypatch.delenv("CD_KEY_MAIN", raising=False)
    monkeypatch.delenv("CD_KEY_ALT", raising=False)


def test_every_subcommand_offers_only_the_flags_it_reads():
    """`--config` and `--out` used to be added to all six subcommands uniformly, and
    two of the six never read the one they were given: cmd_review never looks at
    args.config and cmd_ui never looks at args.out. Both still showed up in --help,
    which offers an operator a flag that changes nothing about what happens."""
    from commentdraft.cli import build_parser

    parser = build_parser()
    takes = {
        "pull": {"--config", "--out"},
        "run": {"--config", "--out"},
        "bakeoff": {"--config", "--out"},
        "review": {"--out"},
        "publish": {"--config", "--out"},
        "chat": {"--config", "--out"},
        "ui": {"--config"},
        "ingest": {"--config", "--out"},
    }
    # The one subparsers action argparse builds for `subs`.
    (action,) = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
    for name, expected in takes.items():
        offered = {
            option
            for sub_action in action.choices[name]._actions
            for option in sub_action.option_strings
        }
        assert offered & {"--config", "--out"} == expected, f"{name} offers the wrong flags"


def test_no_subcommand_prints_usage_and_returns_two(capsys):
    assert main([]) == 2
    assert "usage" in capsys.readouterr().err


def test_missing_config_names_the_file_and_shows_no_traceback(tmp_path, capsys):
    rc = main(["run", "--config", str(tmp_path / "nope.toml")])
    err = capsys.readouterr().err
    assert rc == 2
    assert "nope.toml" in err
    assert "Traceback" not in err


def test_missing_comments_file_is_reported_plainly(tmp_path, capsys, monkeypatch):
    clear_keys(monkeypatch)
    config = build_product(tmp_path)
    rc = main(["run", "--config", str(config), "--comments", str(tmp_path / "absent.csv")])
    err = capsys.readouterr().err
    assert rc == 2
    assert "absent.csv" in err
    assert "Traceback" not in err


def test_a_csv_with_the_wrong_header_is_refused_rather_than_skipped(tmp_path, capsys, monkeypatch):
    # Without this check every row is skipped silently and the run still exits 0,
    # which looks exactly like a comment section with nothing worth answering.
    clear_keys(monkeypatch)
    config = build_product(tmp_path)
    bad = tmp_path / "wrong.csv"
    bad.write_text("id,Comment\n1,how much is it\n", encoding="utf-8")
    rc = main(["run", "--config", str(config), "--comments", str(bad)])
    err = capsys.readouterr().err
    assert rc == 2
    assert "comment" in err


# The single likeliest real operator mistake: a document exported from a desktop word
# processor on a Windows machine is not UTF-8. It is hit before any call, so it is
# free to hit over and over while somebody is setting up, and every one of these three
# files used to answer it with a UnicodeDecodeError traceback. That is a ValueError,
# so cli.py's OSError handlers never saw it, while the comments CSV four lines below
# had been getting a clean message all along.
LEGACY_ENCODED = "The guide costs eighteen euros: 18\N{EURO SIGN}\n".encode("cp1252")


@pytest.mark.parametrize(
    ("relative_path", "expected"),
    [
        ("knowledge.md", "knowledge.md"),
        ("prompts/voice.md", "voice.md"),
        ("prompts/examples.md", "examples.md"),
        ("config.toml", "config.toml"),
    ],
)
def test_a_file_that_is_not_utf8_names_itself_instead_of_raising(
    tmp_path, capsys, monkeypatch, relative_path, expected
):
    clear_keys(monkeypatch)
    config = build_product(tmp_path)
    (tmp_path / relative_path).write_bytes(LEGACY_ENCODED)
    rc = main(["run", "--config", str(config), "--comments", str(tmp_path / "comments.csv")])
    err = capsys.readouterr().err
    assert rc == 2
    assert "Traceback" not in err
    assert expected in err
    assert "UTF-8" in err


def test_the_ui_names_a_missing_voice_file_instead_of_blaming_the_socket(
    tmp_path, capsys, monkeypatch
):
    """build_state read the voice files before render_system_text could raise its own
    clean "voice file not found", so the FileNotFoundError, an OSError, was wrapped by
    cmd_ui's handler as a failure to bind a port that was never touched. The ui exists
    so an operator can iterate on voice files, which makes this the one error it will
    actually meet, and it was the one it misreported."""
    clear_keys(monkeypatch)
    config = build_product(tmp_path)
    (tmp_path / "prompts" / "voice.md").unlink()
    rc = main(["ui", "--config", str(config)])
    err = capsys.readouterr().err
    assert rc == 2
    assert "voice.md" in err
    assert "cannot start the server" not in err
    assert "Traceback" not in err


def test_missing_key_is_named_before_any_call(tmp_path, capsys, monkeypatch):
    clear_keys(monkeypatch)
    config = build_product(tmp_path)
    rc = main(
        [
            "run",
            "--config",
            str(config),
            "--comments",
            str(tmp_path / "comments.csv"),
            "--out",
            str(tmp_path / "out"),
        ]
    )
    err = capsys.readouterr().err
    assert rc == 2
    assert "CD_KEY_MAIN" in err
    assert not (tmp_path / "out").exists()


def test_bakeoff_names_every_missing_key_at_once(tmp_path, capsys, monkeypatch):
    # Both variables in one message. Learning about the second one after the first
    # model has already been paid for is the expensive way to find out.
    clear_keys(monkeypatch)
    config = build_product(tmp_path, extra=GOOD_BAKEOFF)
    rc = main(
        [
            "bakeoff",
            "--config",
            str(config),
            "--comments",
            str(tmp_path / "comments.csv"),
            "--out",
            str(tmp_path / "out"),
        ]
    )
    err = capsys.readouterr().err
    assert rc == 2
    assert "CD_KEY_MAIN" in err
    assert "CD_KEY_ALT" in err


def test_bakeoff_refuses_an_entry_that_does_not_deny_data_collection(tmp_path, capsys, monkeypatch):
    clear_keys(monkeypatch)
    config = build_product(tmp_path, extra=LEAKY_BAKEOFF)
    rc = main(
        [
            "bakeoff",
            "--config",
            str(config),
            "--comments",
            str(tmp_path / "comments.csv"),
            "--out",
            str(tmp_path / "out"),
        ]
    )
    err = capsys.readouterr().err
    assert rc == 2
    assert "data_collection" in err


def test_bakeoff_without_entries_says_so(tmp_path, capsys, monkeypatch):
    clear_keys(monkeypatch)
    config = build_product(tmp_path)
    rc = main(
        [
            "bakeoff",
            "--config",
            str(config),
            "--comments",
            str(tmp_path / "comments.csv"),
            "--out",
            str(tmp_path / "out"),
        ]
    )
    err = capsys.readouterr().err
    assert rc == 2
    assert "bakeoff.models" in err


def test_ingest_refuses_to_overwrite_before_it_asks_for_a_key(tmp_path, capsys, monkeypatch):
    # The refusal has to come first: the file already there may be the corrected
    # transcription, it is gitignored, and nothing can bring it back.
    clear_keys(monkeypatch)
    config = build_product(tmp_path)
    rc = main(
        [
            "ingest",
            "--config",
            str(config),
            "--pdf",
            str(tmp_path / "doc.pdf"),
            "--out",
            str(tmp_path / "knowledge.md"),
        ]
    )
    err = capsys.readouterr().err
    assert rc == 2
    assert "already exists" in err
    assert "CD_KEY_MAIN" not in err


def test_ingest_reports_a_missing_key_without_touching_the_pdf_extra(tmp_path, capsys, monkeypatch):
    """The missing key check has to come before the lazy import of pdf_vision, so a
    machine without the pdf extra, without a real key and without a real PDF still
    gets a clean, actionable message rather than a traceback from either dependency
    it has not paid for."""
    clear_keys(monkeypatch)
    config = build_product(tmp_path)
    rc = main(
        [
            "ingest",
            "--config",
            str(config),
            "--pdf",
            str(tmp_path / "doc.pdf"),
            "--out",
            str(tmp_path / "new-knowledge.md"),
        ]
    )
    err = capsys.readouterr().err
    assert rc == 2
    assert "CD_KEY_MAIN" in err
    assert "Traceback" not in err


def test_chat_reports_a_missing_key_without_a_traceback(tmp_path, capsys, monkeypatch):
    clear_keys(monkeypatch)
    config = build_product(tmp_path)
    rc = main(["chat", "--config", str(config), "--out", str(tmp_path / "out")])
    err = capsys.readouterr().err
    assert rc == 2
    assert "CD_KEY_MAIN" in err
    assert "Traceback" not in err


def test_ui_subcommand_wires_config_and_port_through_and_never_an_address(tmp_path, monkeypatch):
    """serve is patched out, so this never binds a real socket. It only checks that
    the subcommand hands serve the config path and the port this test passed, and
    that a lazy import inside cmd_ui does not stop monkeypatch from reaching it.

    The address is deliberately not wired through. `--host` used to exist with no
    help text, and `--host 0.0.0.0` served the whole knowledge document to anything
    on the network that sent `Host: localhost`, so the subcommand no longer offers a
    way to name one and serve keeps its loopback default.
    """
    from commentdraft import ui

    calls = []
    monkeypatch.setattr(
        ui,
        "serve",
        lambda config_path, host="127.0.0.1", port=8377: calls.append((config_path, host, port)),
    )
    config = build_product(tmp_path)
    rc = main(["ui", "--config", str(config), "--port", "9000"])
    assert rc == 0
    assert calls == [(config, "127.0.0.1", 9000)]


def test_review_renders_a_page_from_a_csv(tmp_path, capsys):
    result = tmp_path / "review.csv"
    result.write_text(
        "id,platform,author,comment,post_title,decision,reason,reply,model,"
        "prompt_tokens,cached_tokens,cache_write_tokens,completion_tokens,"
        "cost_usd,error\n"
        "1,video-site,sam,how much is it,clip,reply,asks the price,"
        "eighteen dollars,test/model-small,1000,0,900,20,0.000400,\n",
        encoding="utf-8",
    )
    rc = main(["review", str(result), "--out", str(tmp_path / "out")])
    assert rc == 0
    page = (tmp_path / "out" / "review.html").read_text(encoding="utf-8")
    assert "DRAFT, NOT APPROVED" in page
    assert 'dir="auto"' in page
    assert "wrote" in capsys.readouterr().out


def test_review_blind_writes_the_key_beside_the_page(tmp_path):
    header = (
        "id,platform,author,comment,post_title,decision,reason,reply,model,"
        "prompt_tokens,cached_tokens,cache_write_tokens,completion_tokens,"
        "cost_usd,error\n"
    )
    paths = []
    for label in ("alpha", "beta"):
        p = tmp_path / f"review-{label}.csv"
        p.write_text(
            header + f"1,video-site,sam,how much is it,clip,reply,asks,"
            f"eighteen dollars,test/model-{label},"
            f"1000,0,900,20,0.000400,\n",
            encoding="utf-8",
        )
        paths.append(str(p))
    rc = main(["review", *paths, "--blind", "--out", str(tmp_path / "out")])
    assert rc == 0
    key = json.loads((tmp_path / "out" / "review-blind_key.json").read_text(encoding="utf-8"))
    assert key == {"A": "review-alpha", "B": "review-beta"}
    page = (tmp_path / "out" / "review.html").read_text(encoding="utf-8")
    assert "review-alpha" not in page
    assert "Set A" in page
    # End to end, from the command a scorer actually types: no cost figure reaches
    # the page, because the totals are per model and published in docs/bakeoff.md.
    assert "total cost" not in page
    assert "0.000400" not in page


def test_review_approved_drops_the_banner(tmp_path):
    result = tmp_path / "review.csv"
    result.write_text("id,comment,decision,reply\n1,how much,reply,eighteen\n", encoding="utf-8")
    rc = main(["review", str(result), "--approved", "--out", str(tmp_path / "out")])
    assert rc == 0
    page = (tmp_path / "out" / "review.html").read_text(encoding="utf-8")
    assert "DRAFT" not in page


def test_safe_name_keeps_a_label_inside_the_output_directory():
    assert safe_name("small") == "small"
    assert safe_name("vendor/model 2") == "vendor_model_2"
    assert safe_name("../../etc/passwd") == ".._.._etc_passwd"
    assert safe_name("") == "model"


def test_format_trace_prints_na_when_the_model_carries_no_pricing():
    trace = {
        "model": "test/model-small",
        "decision": "reply",
        "reason": "asks the price",
        "reply": "eighteen dollars",
        "error": "",
        "attempts": 1,
        "latency_s": 0.4,
        "raw_response": '{"decision": "reply"}',
        "cost_usd": None,
        "usage": {
            "prompt_tokens": 1000,
            "cached_tokens": 900,
            "completion_tokens": 20,
            "cache_write_tokens": 0,
        },
    }
    out = format_trace(trace)
    assert "cost      n/a" in out
    assert "cached 900, 90%" in out
    assert out.isascii()


# --- publish ----------------------------------------------------------------
#
# The subcommand only ever reaches commentdraft.approve, whose own suite drives
# the keystrokes. What is checked here is the startup order: every reason to
# refuse has to be found before a row is read, and none of them may arrive as a
# traceback.

PUBLISH_CONFIG = """
[publish]
platform = "fixture-platform"
credential_env = "CD_PUBLISH_TOKEN"
"""

REVIEW_CSV = (
    "id,platform,author,comment,post_title,decision,reason,reply,model,"
    "prompt_tokens,cached_tokens,cache_write_tokens,completion_tokens,cost_usd,error\n"
    "1,fixture-platform,sam,how much is it,clip,reply,asks the price,"
    "eighteen dollars,test/model-small,1000,0,900,20,0.000400,\n"
    "2,fixture-platform,jo,first,clip,skip,no question,,test/model-small,1000,0,0,20,0.000400,\n"
)


class FixturePlatform:
    """A connector that records calls and reaches nothing.

    The record is on the class rather than the instance because get_platform
    builds the instance itself, so a test never holds the object the CLI used.
    """

    calls: ClassVar[list[tuple]] = []

    def fetch_comments(self, config, since):
        return []

    def publish_reply(self, config, parent_id, text):
        FixturePlatform.calls.append((parent_id, text))
        return "published-" + parent_id


@pytest.fixture
def registered_platform(monkeypatch):
    """Register the fake connector for the length of one test."""
    from commentdraft.platforms import PLATFORMS

    FixturePlatform.calls = []
    monkeypatch.setitem(PLATFORMS, "fixture-platform", FixturePlatform)
    return FixturePlatform


@pytest.fixture
def at_a_keyboard(monkeypatch):
    """Say that a person is at the terminal, which pytest's stdin is not.

    Patched on the gate, which is where the predicate now lives and where the
    refusal that matters is made. cmd_publish imports it at call time, so this
    covers both the early refusal and the one inside the gate.
    """
    from commentdraft import approve

    monkeypatch.setattr(approve, "at_a_keyboard", lambda: True)


def build_publishable(tmp_path, extra=PUBLISH_CONFIG):
    config = build_product(tmp_path, extra=extra)
    out = tmp_path / "out"
    out.mkdir()
    (out / "review.csv").write_text(REVIEW_CSV, encoding="utf-8")
    return config, out


def test_publish_refuses_a_config_with_no_publish_table_before_reading_a_row(
    tmp_path, capsys, monkeypatch
):
    """A config that cannot publish is the recommended starting point, so this is
    the message most people who type this subcommand will ever see."""
    clear_keys(monkeypatch)
    config, out = build_publishable(tmp_path, extra="")
    rc = main(["publish", "--config", str(config), "--out", str(out)])
    err = capsys.readouterr().err
    assert rc == 2
    assert "publish" in err
    assert "Traceback" not in err


def test_publish_names_an_unregistered_platform_and_lists_what_is_registered(
    tmp_path, capsys, monkeypatch
):
    clear_keys(monkeypatch)
    config, out = build_publishable(tmp_path)
    rc = main(["publish", "--config", str(config), "--out", str(out)])
    err = capsys.readouterr().err
    assert rc == 2
    assert "fixture-platform" in err
    assert "registered" in err


def test_publish_names_the_missing_credential_before_it_reads_a_row(
    tmp_path, capsys, monkeypatch, registered_platform
):
    clear_keys(monkeypatch)
    monkeypatch.delenv("CD_PUBLISH_TOKEN", raising=False)
    config, out = build_publishable(tmp_path)
    (out / "review.csv").unlink()  # the credential check has to come first
    rc = main(["publish", "--config", str(config), "--out", str(out)])
    err = capsys.readouterr().err
    assert rc == 2
    assert "CD_PUBLISH_TOKEN" in err
    assert "review.csv" not in err
    assert "Traceback" not in err


def test_publish_says_so_when_there_are_no_drafts_yet(
    tmp_path, capsys, monkeypatch, registered_platform
):
    clear_keys(monkeypatch)
    monkeypatch.setenv("CD_PUBLISH_TOKEN", "not-a-real-token")
    config, out = build_publishable(tmp_path)
    (out / "review.csv").unlink()
    rc = main(["publish", "--config", str(config), "--out", str(out)])
    err = capsys.readouterr().err
    assert rc == 2
    assert "review.csv" in err
    assert "Traceback" not in err


def test_publish_refuses_to_run_without_a_terminal(
    tmp_path, capsys, monkeypatch, registered_platform
):
    """`yes | commentdraft publish` is exactly the thing the four keys were chosen
    to prevent, and a pipe answers a prompt faster than any finger can. There is
    nothing at the other end of a redirect that can read a reply, so there is
    nothing there that can approve one."""
    clear_keys(monkeypatch)
    monkeypatch.setenv("CD_PUBLISH_TOKEN", "not-a-real-token")
    config, out = build_publishable(tmp_path)
    rc = main(["publish", "--config", str(config), "--out", str(out)])
    err = capsys.readouterr().err
    assert rc == 2
    assert "terminal" in err
    assert FixturePlatform.calls == []


def test_publish_dry_run_needs_no_credential_and_no_terminal(
    tmp_path, capsys, monkeypatch, registered_platform
):
    """The point of a dry run is reading what a platform would receive before
    granting any write scope, so requiring the write credential to run one would
    defeat it entirely."""
    clear_keys(monkeypatch)
    monkeypatch.delenv("CD_PUBLISH_TOKEN", raising=False)
    config, out = build_publishable(tmp_path)
    rc = main(["publish", "--config", str(config), "--out", str(out), "--dry-run"])
    output = capsys.readouterr().out
    assert rc == 0
    assert FixturePlatform.calls == []
    assert "eighteen dollars" in output
    assert not (out / "published.jsonl").exists()


def test_publish_offers_only_the_rows_decided_reply(
    tmp_path, capsys, monkeypatch, registered_platform
):
    clear_keys(monkeypatch)
    monkeypatch.setenv("CD_PUBLISH_TOKEN", "not-a-real-token")
    config, out = build_publishable(tmp_path)
    rc = main(["publish", "--config", str(config), "--out", str(out), "--dry-run"])
    output = capsys.readouterr().out
    assert rc == 0
    assert "[ 1 / 1 ]" in output  # two rows in the file, one of them a reply


def test_publish_sends_one_reply_per_keystroke_and_records_it(
    tmp_path, capsys, monkeypatch, registered_platform, at_a_keyboard
):
    """End to end from the command an operator types, with a scripted reviewer."""
    import json

    clear_keys(monkeypatch)
    monkeypatch.setenv("CD_PUBLISH_TOKEN", "not-a-real-token")
    config, out = build_publishable(tmp_path)
    pressed = iter(["y"])

    with scripted_reviewer(lambda: next(pressed)):
        rc = main(["publish", "--config", str(config), "--out", str(out)])

    assert rc == 0
    assert FixturePlatform.calls == [("1", "eighteen dollars")]
    (line,) = (out / "published.jsonl").read_text(encoding="utf-8").splitlines()
    entry = json.loads(line)
    assert entry["published_id"] == "published-1"
    assert entry["parent_id"] == "1"
    assert entry["edited"] is False
    assert entry["config"] == str(config)


class HaltingPlatform:
    """A connector whose write halts the queue, carrying the id it left live."""

    calls: ClassVar[list[tuple]] = []

    def fetch_comments(self, config, since):
        return []

    def publish_reply(self, config, parent_id, text):
        from commentdraft.platforms import PlatformHalt

        HaltingPlatform.calls.append((parent_id, text))
        raise PlatformHalt("the write could not be proved to be a reply", "live-1")


def test_publish_reports_a_halt_rather_than_letting_a_traceback_out(
    tmp_path, capsys, monkeypatch, at_a_keyboard
):
    """A halt used to leave the command with a bare traceback.

    That reads as a crash in the tool rather than as a report about somebody's
    Page, and it exited 1: the same code as a run where one row was refused and
    everything else went fine. Those are not the same event, so they do not share
    a number, and the message names what is live and where the record is.
    """
    import json

    from commentdraft.cli import HALT_EXIT
    from commentdraft.platforms import PLATFORMS

    HaltingPlatform.calls = []
    monkeypatch.setitem(PLATFORMS, "fixture-platform", HaltingPlatform)
    clear_keys(monkeypatch)
    monkeypatch.setenv("CD_PUBLISH_TOKEN", "not-a-real-token")
    config, out = build_publishable(tmp_path)
    pressed = iter(["y"])

    with scripted_reviewer(lambda: next(pressed)):
        rc = main(["publish", "--config", str(config), "--out", str(out)])

    err = capsys.readouterr().err
    assert rc == HALT_EXIT
    assert rc not in (0, 1, 2), "a halt shares an exit code with an ordinary outcome"
    assert "Traceback" not in err
    assert "live-1" in err
    assert "published.jsonl" in err
    (line,) = (out / "published.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(line)["verified"] is False
