# SPDX-License-Identifier: Apache-2.0
"""Tests for the loopback test page.

Nothing here reaches the network beyond 127.0.0.1 and nothing here needs a key: the
server is driven on an ephemeral port with a hand built state dict.
"""

import contextlib
import email.message
import http.client
import json
import re
import threading

import pytest

from commentdraft import ui

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
        "clients": {},
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


def test_meta_json_does_not_require_platforms():
    """behavior.platforms is optional, same as it already is for the chat subcommand.

    config.py's REQUIRED never lists it, so a config built from the documentation
    alone can omit it. meta_json used to read it with a bare [], which raised a
    KeyError from inside do_GET, a route with no try/except around it, instead of
    the ConfigError this project gives for every other missing setting. It must
    read as an empty list rather than raise.
    """
    state = make_state()
    state["cfg"] = {"behavior": {}}
    meta = json.loads(ui.meta_json(state))
    assert meta["platforms"] == []


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


class _Probe(ui._Handler):
    """A handler driven straight, with no socket under it.

    _local_only is the whole access control boundary and its first check is on the
    peer address, which cannot be reached over a real connection from a test: every
    connection a test can open is already from 127.0.0.1. So the handler is built by
    hand with the three attributes that check reads. __init__ is overridden rather
    than called, because BaseHTTPRequestHandler's own __init__ serves a request.
    """

    def __init__(self, peer, headers=None, port=8377):
        # A real message object rather than a dict, because that is what the handler
        # is handed on a live request and headers are case-insensitive there.
        message = email.message.Message()
        for name, value in (headers or {}).items():
            message[name] = value
        self.client_address = (peer, 51000)
        self.headers = message
        self.port = port
        self.sent = []

    def _send(self, code, body, ctype):
        self.sent.append(code)


@pytest.mark.parametrize(
    "peer",
    ["127.0.0.1", "127.0.0.53", "::1", "::ffff:127.0.0.1", "localhost"],
)
def test_a_loopback_peer_is_served(peer):
    """The mapped form is the one a dual-stack socket reports for an IPv4 peer, and
    IPv6Address.is_loopback is False for it, so the check has to undo the mapping or
    it refuses the operator's own browser on a machine with IPv6 enabled."""
    probe = _Probe(peer, {"Host": "localhost:8377"})
    assert probe._local_only() is True
    assert probe.sent == []


@pytest.mark.parametrize("peer", ["192.168.1.40", "10.0.0.7", "203.0.113.9", "fd00::1", ""])
def test_a_peer_off_this_machine_is_refused_however_it_sets_its_headers(peer):
    """The finding this test exists for: bound to 0.0.0.0, a client anywhere on the
    network could send `Host: localhost` by hand and read the entire knowledge
    document out of /prompt, then spend the operator's key through /api/reply. Host
    and Origin describe what a browser believes, which is worth checking against a
    browser and worth nothing against a client that writes them itself. The peer
    address is the one thing in the request the client does not get to choose."""
    probe = _Probe(peer, {"Host": "localhost:8377", "Origin": "http://localhost:8377"})
    assert probe._local_only() is False
    assert probe.sent == [403]


def test_serve_refuses_to_bind_anywhere_but_loopback(tmp_path):
    """Refused rather than warned about. A warning printed into a terminal nobody is
    watching does not stop the knowledge document being served to the network, and
    the bind address is half of the two controls that do."""
    from commentdraft.config import ConfigError

    with pytest.raises(ConfigError) as excinfo:
        ui.serve(tmp_path / "config.toml", host="0.0.0.0")
    message = str(excinfo.value)
    assert "0.0.0.0" in message
    assert "127.0.0.1" in message


def test_the_ui_subcommand_offers_no_way_to_ask_for_another_address():
    """The flag that made the finding reachable in one word. Removed rather than
    documented, so this asserts the parser rejects it rather than that help text
    warns about it."""
    from commentdraft.cli import build_parser

    parser = build_parser()
    assert parser.parse_args(["ui", "--port", "9000"]).port == 9000
    with pytest.raises(SystemExit):
        parser.parse_args(["ui", "--host", "0.0.0.0"])


def test_the_operators_own_tab_still_works_when_the_server_is_bound_broadly():
    """The peer check has to refuse the network without refusing the operator, so a
    broadly bound server still answers a request that came in over loopback."""
    server = ui.make_server(make_state(), host="0.0.0.0", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, body = get(
            server.server_port, "/prompt", {"Host": f"localhost:{server.server_port}"}
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    assert status == 200
    assert json.loads(body)["knowledge_words"] == 4


def test_a_case_varied_localhost_host_header_is_still_accepted():
    """A hostname is case-insensitive on the wire even though browsers normalize it
    in practice, so the check must not depend on that normalization happening."""
    with running(make_state()) as port:
        status, _ = get(port, "/meta", {"Host": f"LOCALHOST:{port}"})
    assert status == 200


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


def test_reload_drops_a_client_for_a_gateway_the_config_no_longer_names(monkeypatch):
    """Keeping it would report a successful reload and then keep sending the
    operator's requests, and the operator's key, to the address they just changed.
    Clients are cached per gateway, so this has to check every cached one rather
    than only the default model's, or a bake-off entry on its own gateway would
    keep a stale client after that gateway was edited away."""
    state = make_state()
    old_key = (state["model_cfg"]["base_url"], state["model_cfg"]["api_key_env"])
    state["clients"] = {old_key: object()}
    fresh = make_state()
    fresh["model_cfg"] = {**fresh["model_cfg"], "base_url": "https://other.example/v1"}
    fresh["models"] = {"base": fresh["model_cfg"]}
    monkeypatch.setattr(ui, "build_state", lambda path: fresh)
    ui.apply_reload(state)
    assert state["clients"] == {}
    assert state["model_cfg"]["base_url"] == "https://other.example/v1"


def test_reload_keeps_a_client_whose_gateway_is_still_configured(monkeypatch):
    """The ordinary case is editing the voice file, and reconnecting for that would
    throw away a live connection for nothing."""
    state = make_state()
    sentinel = object()
    key = (state["model_cfg"]["base_url"], state["model_cfg"]["api_key_env"])
    state["clients"] = {key: sentinel}
    monkeypatch.setattr(ui, "build_state", lambda path: make_state())
    ui.apply_reload(state)
    assert state["clients"][key] is sentinel


def test_get_client_follows_the_selected_models_gateway_not_the_default(monkeypatch):
    """A bake-off entry can legitimately name a base_url and api_key_env different
    from the default model, since comparing a model across gateways is itself a
    reason to run a bake-off. The client used for a request has to be built for
    the model actually selected, not silently reused from the default's gateway,
    or the trace would report the selected model's name while the request went
    out through a different gateway entirely."""
    built = []

    class FakeClient:
        def __init__(self, *, base_url, api_key):
            self.base_url = base_url
            self.api_key = api_key
            built.append(self)

    monkeypatch.setattr("openai.OpenAI", FakeClient)
    monkeypatch.setenv("GATEWAY_KEY", "default-key-value")
    monkeypatch.setenv("RIVAL_KEY", "rival-key-value")

    state = make_state()
    rival = {
        **state["model_cfg"],
        "label": "rival",
        "base_url": "https://rival.example/v1",
        "api_key_env": "RIVAL_KEY",
    }

    default_client = ui.get_client(state, state["model_cfg"])
    rival_client = ui.get_client(state, rival)

    assert default_client is not rival_client
    assert default_client.base_url == "https://gateway.example/api/v1"
    assert default_client.api_key == "default-key-value"
    assert rival_client.base_url == "https://rival.example/v1"
    assert rival_client.api_key == "rival-key-value"
    # A second call for a model already served reuses the cached client for that
    # gateway rather than building a second one.
    assert ui.get_client(state, state["model_cfg"]) is default_client
    assert len(built) == 2


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
