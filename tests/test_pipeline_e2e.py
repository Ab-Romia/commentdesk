# SPDX-License-Identifier: Apache-2.0
import csv
import types

from commentdesk import cli
from commentdesk.engine import OUT_FIELDS

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

CANNED = [
    (
        '{"decision": "reply", "reason": "asks the price",'
        ' "reply_text": "Eighteen dollars, and here is the link:'
        ' https://example.com/field-guide"}'
    ),
    '{"decision": "skip", "reason": "no question in it", "reply_text": ""}',
    (
        '{"decision": "reply", "reason": "asks about coverage",'
        ' "reply_text": "Yes, it has a chapter on three common mushrooms."}'
    ),
]


class FakeCompletions:
    """Stands in for the SDK surface the engine uses.

    Hands back one canned response per call and keeps every request, so a test can
    check what went out without a network and without a key.
    """

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        index = min(len(self.calls) - 1, len(self.responses) - 1)
        # The first call pays to write the prefix into the cache, later calls read
        # it. The figures only have to be plausible: what is under test is that
        # they survive into the CSV, not what they are.
        first = len(self.calls) == 1
        usage = types.SimpleNamespace(
            prompt_tokens=1000,
            completion_tokens=20,
            prompt_tokens_details=types.SimpleNamespace(
                cached_tokens=0 if first else 900, cache_write_tokens=900 if first else 0
            ),
        )
        message = types.SimpleNamespace(content=self.responses[index])
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)], usage=usage)


def fake_client(responses):
    return types.SimpleNamespace(chat=types.SimpleNamespace(completions=FakeCompletions(responses)))


def build_product(tmp_path):
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "voice.md").write_text(VOICE, encoding="utf-8")
    (tmp_path / "prompts" / "examples.md").write_text(EXAMPLES, encoding="utf-8")
    (tmp_path / "knowledge.md").write_text(KNOWLEDGE, encoding="utf-8")
    (tmp_path / "comments.csv").write_text(COMMENTS, encoding="utf-8")
    config = tmp_path / "config.toml"
    config.write_text(CONFIG, encoding="utf-8")
    return config


def install_client(monkeypatch, responses):
    client = fake_client(responses)
    monkeypatch.setenv("CD_KEY_MAIN", "not-a-real-key")
    monkeypatch.setattr(cli, "make_client", lambda model_cfg: client)
    return client


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def test_pipeline_runs_end_to_end_and_the_page_renders_from_it(tmp_path, monkeypatch):
    config = build_product(tmp_path)
    client = install_client(monkeypatch, CANNED)
    out = tmp_path / "out"

    rc = cli.main(
        [
            "run",
            "--config",
            str(config),
            "--comments",
            str(tmp_path / "comments.csv"),
            "--out",
            str(out),
        ]
    )
    assert rc == 0

    fields, rows = read_csv(out / "review.csv")
    assert fields == OUT_FIELDS
    assert [r["id"] for r in rows] == ["1", "2", "3"]
    assert [r["decision"] for r in rows] == ["reply", "skip", "reply"]
    assert all(r["model"] == "test/model-small" for r in rows)
    assert all(r["error"] == "" for r in rows)
    assert float(rows[0]["cost_usd"]) > 0
    # The first call writes the prefix into the cache, the rest read it.
    assert rows[0]["cached_tokens"] == "0"
    assert rows[1]["cached_tokens"] == "900"

    calls = client.chat.completions.calls
    assert len(calls) == 3
    # The property the whole prompt design rests on: the system block is
    # byte-identical on every call in a run, so the provider serves it from cache.
    systems = [c["messages"][0]["content"] for c in calls]
    assert all(s == systems[0] for s in systems)
    assert "wild garlic" in systems[0][1]["text"]
    assert systems[0][1]["cache_control"] == {"type": "ephemeral"}
    # The operator data promise, end to end and in the request body itself.
    assert calls[0]["extra_body"]["provider"]["data_collection"] == "deny"
    assert calls[0]["model"] == "test/model-small"

    rc = cli.main(
        ["review", str(out / "review.csv"), "--out", str(out), "--title", "Field guide review"]
    )
    assert rc == 0
    page = (out / "review.html").read_text(encoding="utf-8")
    assert "Field guide review" in page
    assert "how much does it cost" in page
    assert "does it cover mushrooms" in page
    assert "DRAFT, NOT APPROVED" in page
    assert "3 comments: reply=2, skip=1" in page
    assert 'dir="auto"' in page


def test_a_run_that_lost_rows_exits_non_zero(tmp_path, monkeypatch):
    config = build_product(tmp_path)
    client = install_client(monkeypatch, ["there is no json in this at all"])
    out = tmp_path / "out"

    rc = cli.main(
        [
            "run",
            "--config",
            str(config),
            "--comments",
            str(tmp_path / "comments.csv"),
            "--out",
            str(out),
        ]
    )
    # A scripted caller must not read a run that dropped every comment as a pass.
    assert rc == 1

    fields, rows = read_csv(out / "review.csv")
    assert fields == OUT_FIELDS
    assert [r["decision"] for r in rows] == ["error", "error", "error"]
    assert all(r["error"] for r in rows)
    # One nudge retry per row and no more: a second nudge never helps.
    assert len(client.chat.completions.calls) == 6

    rc = cli.main(["review", str(out / "review.csv"), "--out", str(out)])
    assert rc == 0
    page = (out / "review.html").read_text(encoding="utf-8")
    assert 'class="row error"' in page
