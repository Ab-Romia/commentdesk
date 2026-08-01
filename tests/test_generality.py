# SPDX-License-Identifier: Apache-2.0
"""The acceptance gate.

Three tests carry every generality claim the README is allowed to make. Test one
proves no English is welded into the engine. Test two proves the pipeline runs over
three unrelated products offline. Test three proves the package cannot post.
"""

import ast
import json
from pathlib import Path

import pytest

from commentdraft.config import load_config
from commentdraft.engine import DECISIONS, OUT_FIELDS, read_comments, run_pipeline
from commentdraft.prompt import KNOWLEDGE_TAG, render_system_text
from commentdraft.sanitize import find_repetition, is_plug, sanitize_reply
from commentdraft.sources import load_knowledge

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "commentdraft"
OTHER_LANGUAGE = ROOT / "tests" / "fixtures" / "nazzef-kit-ar"

PRODUCTS = {
    "book": ROOT / "examples" / "field-guide-book",
    "course": ROOT / "examples" / "sourdough-course",
    "other-language": OTHER_LANGUAGE,
}


class FixedClient:
    """Returns the same canned completion for every call and records the calls.

    Fixed rather than queued on purpose: a row the engine decides locally, such as an
    empty comment, never reaches the client, and a queue would make the test depend on
    exactly how many rows do.
    """

    def __init__(self, content):
        self.calls = []
        outer = self

        class _Completions:
            def create(self, **kwargs):
                outer.calls.append(kwargs)
                return outer._response(content)

        class _Chat:
            completions = _Completions()

        self.chat = _Chat()

    @staticmethod
    def _response(content):
        import types

        details = types.SimpleNamespace(cached_tokens=8000, cache_write_tokens=0)
        usage = types.SimpleNamespace(
            prompt_tokens=8200, completion_tokens=40, prompt_tokens_details=details
        )
        message = types.SimpleNamespace(content=content)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)], usage=usage)


CANNED = json.dumps(
    {
        "decision": "reply",
        "reason": "a question about the product",
        "reply_text": "Glad you asked, that one is covered.",
    }
)


def test_a_product_in_another_language_gets_the_same_guarantees():
    """Every guarantee the two English examples get, in a language and a script
    that share nothing with them. If any of these assertions needs a special case
    for this fixture, then some English got welded into the engine."""
    cfg = load_config(OTHER_LANGUAGE / "config.toml")
    behavior = cfg["behavior"]

    text = render_system_text(cfg, OTHER_LANGUAGE)
    assert "{{" not in text and "}}" not in text
    assert cfg["product"]["name"] in text
    assert cfg["product"]["price_text"] in text  # non-ASCII currency symbol
    assert behavior["bot_disclosure_text"] in text
    assert f"<{KNOWLEDGE_TAG}>" in text
    assert cfg["cta"][behavior["cta_mode"]]["phrases"][0] in text

    knowledge = load_knowledge(cfg, OTHER_LANGUAGE)
    assert len(knowledge.split()) > 200  # same floor as the two English examples

    # sanitize_reply replaces the dash with the configured separator and nothing else.
    # The bug this pins: the separator used to be guessed from the script of the reply,
    # so a reply in an unmeasured script had punctuation from a third script injected
    # into it, which is precisely what this function exists to prevent. This fixture's
    # separator is the Arabic comma, "\u060c ". A fixture whose separator were a Latin
    # comma could not tell "the separator was read from config" apart from "the
    # separator is hardcoded to a Latin comma"; this one can, because the two marks
    # are visibly different and the assertions below check for each by name.
    raw = "الشمس ضرورية \u2014 قلل الماء 🙂"
    cleaned = sanitize_reply(raw, behavior["separator"], behavior["banned_emoji"])
    assert cleaned == "الشمس ضرورية\u060c قلل الماء"
    assert "\u2014" not in cleaned  # the em dash is gone
    assert "\u060c" in cleaned  # the Arabic comma from config made it into the output
    assert "," not in cleaned  # and no Latin comma took its place
    assert "\u3001" not in cleaned  # and no CJK ideographic comma either
    assert "🙂" not in cleaned

    # is_plug reads this config's markers, not a hardcoded word in any language
    assert is_plug("الرابط موجود في البايو", behavior["plug_markers"])
    assert is_plug("https://example.com/nazzef-kit", behavior["plug_markers"])
    assert not is_plug("التنظيف بالفرشاة الناعمة أسهل طريقة", behavior["plug_markers"])

    # find_repetition sees a repeated closing in this script too
    rows = [
        {"id": "1", "reply": "استخدم الفرشاة الناعمة أولاً، بالتوفيق"},
        {"id": "2", "reply": "جفف الحذاء بعيداً عن الشمس، بالتوفيق"},
        {"id": "3", "reply": "ابدأ بالمحلول المخفف، بالتوفيق"},
    ]
    flags = find_repetition(rows)
    assert flags, "a closing repeated three times was not reported"
    assert "بالتوفيق" in " ".join(flags)


@pytest.mark.parametrize("name", sorted(PRODUCTS))
def test_the_whole_pipeline_runs_offline_for_every_product(name):
    directory = PRODUCTS[name]
    cfg = load_config(directory / "config.toml")
    comments = read_comments(directory / "comments.csv")
    knowledge = load_knowledge(cfg, directory)
    system_text = render_system_text(cfg, directory)
    client = FixedClient(CANNED)

    rows = run_pipeline(cfg, cfg["model"], comments, knowledge, system_text, client)

    assert len(rows) == len(comments)
    for row in rows:
        assert set(OUT_FIELDS) <= set(row)
        assert row["decision"] in DECISIONS
        assert row["error"] == ""
        assert row["model"] == cfg["model"]["model"]  # provenance on every row
        # cost_usd is priced whenever a call actually happened; a row decided
        # locally, such as an empty comment, made no call and its cost stays
        # blank rather than a misleading "0.000000". See tests/test_pipeline_e2e.py.
        if row["prompt_tokens"]:
            assert row["cost_usd"] != ""
        else:
            assert row["cost_usd"] == ""
    assert 0 < len(client.calls) <= len(comments)

    # The cached prefix is the architecture: it must be byte identical on every call,
    # so nothing per row may leak into the system message.
    prefixes = {
        json.dumps(call["messages"][0], ensure_ascii=False, sort_keys=True) for call in client.calls
    }
    assert len(prefixes) == 1, "the system prefix changed between rows"


BANNED_IMPORTS = {
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "urllib.request",
    "http.client",
    "googleapiclient",
    "google_auth_oauthlib",
    "google.oauth2",
    "google.auth",
    "tweepy",
    "facebook",
    "facebook_sdk",
    "instagrapi",
    "TikTokApi",
    "atproto",
    "praw",
}

BANNED_HOSTS = (
    "youtube.googleapis.com",
    "www.googleapis.com",
    "oauth2.googleapis.com",
    "accounts.google.com",
    "graph.facebook.com",
    "graph.instagram.com",
    "api.instagram.com",
    "open.tiktokapis.com",
    "open-api.tiktok.com",
    "api.tiktok.com",
    "api.twitter.com",
    "api.x.com",
)


def _module_trees():
    modules = sorted(SRC.rglob("*.py"))
    assert len(modules) >= 8, f"only found {len(modules)} modules under {SRC}"
    for path in modules:
        yield path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_the_package_contains_no_client_for_any_platform():
    """The never-posts promise is a property of the code, not of a policy document.

    ui.py legitimately serves on localhost, so http.server and socketserver are fine.
    What may not exist anywhere is a way to reach a platform's API.
    """
    for path, tree in _module_trees():
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                assert name not in BANNED_IMPORTS, f"{path.name} imports {name}"

        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                lowered = node.value.lower()
                for host in BANNED_HOSTS:
                    assert host not in lowered, f"{path.name} names {host}"
