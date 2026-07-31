# SPDX-License-Identifier: Apache-2.0
"""Tests for the loopback test page.

Nothing here reaches the network beyond 127.0.0.1 and nothing here needs a key: the
server is driven on an ephemeral port with a hand built state dict.
"""

import contextlib
import http.client
import json
import re
import threading

from commentdesk import ui

# The keys run_one puts in a trace, plus the one /api/reply adds. The page reads
# trace values as t.<key>, and the test below holds the page to this list.
TRACE_KEYS = {
    "model",
    "base_url",
    "params",
    "comment",
    "platform",
    "request_messages",
    "raw_response",
    "decision",
    "reason",
    "reply",
    "error",
    "usage",
    "attempts",
    "latency_s",
    "cost_usd",
    "reasoning",
}


def make_state():
    """A state dict shaped like build_state's output, built without touching disk."""
    model_cfg = {
        "label": "base",
        "model": "vendor/model-a",
        "params": {},
        "base_url": "https://gateway.example/api/v1",
        "api_key_env": "GATEWAY_KEY",
    }
    rival = {**model_cfg, "label": "rival", "model": "vendor/model-b"}
    return {
        "config_path": "config.toml",
        "cfg": {"behavior": {"platforms": ["alpha", "beta"]}},
        "model_cfg": model_cfg,
        "models": {"base": model_cfg, "rival": rival},
        "voice_text": "voice rules",
        "examples_text": "worked examples",
        "config_text": "[product]\n",
        "knowledge_text": "one two three four",
        "system_text": "rendered system text",
        "product_name": "Test Product",
        "paths": {
            "config": "/somewhere/config.toml",
            "voice": "/somewhere/prompts/voice.md",
            "examples": "/somewhere/prompts/examples.md",
            "knowledge": "/somewhere/knowledge.md",
        },
        "client": None,
        "trace": {},
    }


@contextlib.contextmanager
def running(state):
    """Serve on an ephemeral loopback port for the duration of one test."""
    server = ui.make_server(state, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def get(port, path, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", path, headers=headers or {})
        resp = conn.getresponse()
        return resp.status, resp.read()
    finally:
        conn.close()


def test_page_has_no_page_level_direction_rule():
    """dir="auto" plus unicode-bidi:plaintext already gives every block the direction
    of its own content. A page level rule overrides that and is wrong for any script
    it was not written for, so there must not be one."""
    flat = re.sub(r"\s+", "", ui.build_page()).lower()
    assert "direction:rtl" not in flat
    assert "direction:ltr" not in flat
    assert 'dir="rtl"' not in flat
    assert 'dir="auto"' in flat
    assert "unicode-bidi:plaintext" in flat


def test_page_is_ascii_and_names_no_path_product_or_platform():
    """Everything specific to one operator arrives as JSON. A path or a platform baked
    into the page starts lying the moment someone moves a file or sells somewhere
    else."""
    page = ui.build_page()
    page.encode("ascii")
    for literal in ("config.toml", "prompts/", ".md", ".toml"):
        assert literal not in page
    lower = page.lower()
    for platform in ("tiktok", "youtube", "instagram"):
        assert platform not in lower


def test_page_reads_only_keys_the_server_sends():
    """The JSON keys are a contract. m is the /meta payload and p is the /prompt
    payload, and a key renamed on one side only reads undefined with no error."""
    page = ui.build_page()
    state = make_state()
    sent = set(json.loads(ui.meta_json(state))) | set(json.loads(ui.prompt_json(state)))
    read = set(re.findall(r"\b[mp]\.([a-z_]+)", page))
    assert read, "the page reads nothing, so the regex stopped matching"
    assert read <= sent


def test_page_reads_only_trace_keys_a_run_produces():
    """Same contract on the reply payload, and the only check that catches a typo in
    a value name inside an HTML string nothing else parses."""
    read = set(re.findall(r"\bt\.([a-z_]+)", ui.build_page()))
    assert read
    assert read <= TRACE_KEYS


def test_page_shows_the_whole_trace():
    """The point of the page: the raw output before parsing, the exact message sent,
    and the request params, not a summary of any of them."""
    page = ui.build_page()
    assert "Full trace" in page
    assert "t.raw_response" in page
    assert "t.request_messages" in page
    assert "JSON.stringify(t.params" in page
    assert "/trace" in page


def test_page_labels_each_pane_with_the_file_to_edit():
    page = ui.build_page()
    for element in ("voicePath", "examplesPath", "configPath", "knowledgePath"):
        assert element in page
    assert "p.voice_path" in page
    assert "p.examples_path" in page
    assert "p.config_path" in page
    assert "p.knowledge_path" in page


def test_every_value_written_into_markup_is_escaped():
    """innerHTML is built by concatenation, so one unescaped value is a comment
    containing a script tag away from running in the operator's browser."""
    assignments = re.findall(r"innerHTML =(.*?);\n", ui.build_page(), re.DOTALL)
    assert len(assignments) == 2
    for block in assignments:
        assert re.findall(r"\+\s*(?!esc\()([A-Za-z_][\w.]*)", block) == []


def test_a_page_on_another_origin_cannot_read_the_prompt():
    """Any page the operator happens to have open could otherwise read the whole
    knowledge document out of this server, or spend the key through /api/reply."""
    with running(make_state()) as port:
        status, _ = get(port, "/prompt", {"Origin": "https://someone-elses.example"})
    assert status == 403


def test_a_rebound_hostname_cannot_reach_the_server():
    """A name that resolves to 127.0.0.1 defeats the origin check on its own, so the
    Host header has to be a loopback name too."""
    with running(make_state()) as port:
        status, _ = get(port, "/meta", {"Host": "attacker.example"})
    assert status == 403


def test_the_operators_own_tab_is_served():
    with running(make_state()) as port:
        status, body = get(port, "/meta")
        assert status == 200
        meta = json.loads(body)
        assert meta["product"] == "Test Product"
        assert meta["label"] in [m["label"] for m in meta["models"]]
        assert len(meta["models"]) == 2
        assert meta["platforms"] == ["alpha", "beta"]
        status, body = get(port, "/prompt", {"Origin": f"http://127.0.0.1:{port}"})
        assert status == 200
        assert json.loads(body)["knowledge_words"] == 4


def test_reload_drops_a_client_built_for_another_gateway(monkeypatch):
    """Keeping it would report a successful reload and then keep sending the
    operator's requests, and the operator's key, to the address they just changed."""
    state = make_state()
    state["client"] = object()
    fresh = make_state()
    fresh["model_cfg"] = {**fresh["model_cfg"], "base_url": "https://other.example/v1"}
    fresh["models"] = {"base": fresh["model_cfg"]}
    monkeypatch.setattr(ui, "build_state", lambda path: fresh)
    ui.apply_reload(state)
    assert state["client"] is None
    assert state["model_cfg"]["base_url"] == "https://other.example/v1"


def test_reload_keeps_the_client_when_the_gateway_is_unchanged(monkeypatch):
    """The ordinary case is editing the voice file, and reconnecting for that would
    throw away a live connection for nothing."""
    state = make_state()
    sentinel = object()
    state["client"] = sentinel
    monkeypatch.setattr(ui, "build_state", lambda path: make_state())
    ui.apply_reload(state)
    assert state["client"] is sentinel


def test_reload_reports_a_broken_config_on_the_page(monkeypatch):
    """A reload runs whatever the operator just typed through the whole loader, so
    every failure belongs on the page rather than in a terminal nobody is watching."""

    def explode(path):
        raise ValueError("missing product.name")

    monkeypatch.setattr(ui, "build_state", explode)
    with running(make_state()) as port:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("POST", "/api/reload", body=b"")
        resp = conn.getresponse()
        status, body = resp.status, resp.read()
        conn.close()
    assert status == 400
    assert "missing product.name" in json.loads(body)["error"]
