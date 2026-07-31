# SPDX-License-Identifier: Apache-2.0
import json

from commentdesk.cli import format_trace, main, safe_name

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

COMMENTS = """id,platform,author,comment,video_title
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
    (tmp_path / "prompts").mkdir()
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


def test_chat_reports_a_missing_key_without_a_traceback(tmp_path, capsys, monkeypatch):
    clear_keys(monkeypatch)
    config = build_product(tmp_path)
    rc = main(["chat", "--config", str(config), "--out", str(tmp_path / "out")])
    err = capsys.readouterr().err
    assert rc == 2
    assert "CD_KEY_MAIN" in err
    assert "Traceback" not in err


def test_ui_subcommand_wires_config_host_and_port_through(tmp_path, monkeypatch):
    """serve is patched out, so this never binds a real socket. It only checks that
    the subcommand hands serve the config path and the flags this test passed, and
    that a lazy import inside cmd_ui does not stop monkeypatch from reaching it."""
    from commentdesk import ui

    calls = []
    monkeypatch.setattr(
        ui,
        "serve",
        lambda config_path, host="127.0.0.1", port=8377: calls.append((config_path, host, port)),
    )
    config = build_product(tmp_path)
    rc = main(["ui", "--config", str(config), "--host", "0.0.0.0", "--port", "9000"])
    assert rc == 0
    assert calls == [(config, "0.0.0.0", 9000)]


def test_review_renders_a_page_from_a_csv(tmp_path, capsys):
    result = tmp_path / "review.csv"
    result.write_text(
        "id,platform,author,comment,video_title,decision,reason,reply,model,"
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
        "id,platform,author,comment,video_title,decision,reason,reply,model,"
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
