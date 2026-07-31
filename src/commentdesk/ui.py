# SPDX-License-Identifier: Apache-2.0
"""A test page on the loopback address: type a comment, see the decision, the reply,
and the whole trace behind it.

Standard library only and no build step. It exists so that an operator who has just
edited the voice file can see what that edit did in seconds, through the same code
path a run uses, and can read the exact bytes that were sent rather than a summary
of them.

Nothing specific to one operator is written into the page. The product name, the
platform names, the model list and every file path arrive as JSON from /meta and
/prompt, which read them from the config. That is what keeps one HTML string correct
for everybody, and it makes the JSON key names a contract: rename a key in the Python
without renaming it in the page and the page reads undefined, draws nothing, and
reports no error. Rename both sides in one commit.
"""

import contextlib
import json
import os
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .config import ConfigError, load_config, model_options, resolve_path, with_reasoning
from .engine import run_one
from .prompt import render_system_text
from .sources import load_knowledge

PREVIEW_CHARS = 600


def build_state(config_path):
    """Everything the server answers from, loaded at startup and again on reload.

    The knowledge document is read through the same registry a run uses, so what the
    page shows is what a run would send and not a second, kinder reading of the file.
    """
    config_path = Path(config_path)
    config_dir = config_path.parent
    cfg = load_config(config_path)
    voice = resolve_path(config_dir, cfg["voice"]["rules"])
    examples = resolve_path(config_dir, cfg["voice"]["examples"])
    knowledge = resolve_path(config_dir, cfg["knowledge"]["path"])
    return {
        "config_path": str(config_path),
        "cfg": cfg,
        "model_cfg": cfg["model"],
        # Every model the config offers, so a comparison can be run live instead of
        # quoted from a table. A bake-off entry may name its own base_url and
        # api_key_env, which is exactly why comparing across gateways is worth
        # doing, so get_client keys its cache on the gateway a model actually
        # names rather than assuming they all share the default's.
        "models": model_options(cfg),
        "voice_text": voice.read_text(encoding="utf-8"),
        "examples_text": examples.read_text(encoding="utf-8"),
        "config_text": config_path.read_text(encoding="utf-8"),
        "knowledge_text": load_knowledge(cfg, config_dir),
        "system_text": render_system_text(cfg, config_dir),
        "product_name": cfg["product"]["name"],
        # Shown next to each pane so the operator knows which file to open. They come
        # from the config, so moving a file moves the label with it.
        "paths": {
            "config": str(config_path),
            "voice": str(voice),
            "examples": str(examples),
            "knowledge": str(knowledge),
        },
        # Keyed by (base_url, api_key_env) rather than held as one slot, so a
        # bake-off entry on a different gateway than the default gets its own
        # client instead of silently reusing the default's.
        "clients": {},
        "trace": {},
    }


_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>commentdesk</title>
<style>
:root { --ink:#22211f; --soft:#6b675f; --line:#e5e1d8; --card:#ffffff;
        --bg:#f7f5f0; --accent:#155d33; --reply:#e8f3ec; --skip:#f1efea;
        --esc:#fbe9e9; --err:#fff3df; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink);
       font-family:system-ui,sans-serif; }
main { max-width:820px; margin:0 auto; padding:28px 18px 60px; }
h1 { font-size:1.25rem; margin:0; }
.sub { color:var(--soft); font-size:.85rem; margin:4px 0 20px; }
.panel { background:var(--card); border:1px solid var(--line); border-radius:12px;
         padding:16px; }
textarea { width:100%; min-height:74px; border:1px solid var(--line);
           border-radius:8px; padding:10px 12px; font:inherit; font-size:1rem;
           resize:vertical; background:#fdfcfa; }
textarea:focus { outline:2px solid var(--accent); border-color:transparent; }
.row { display:flex; gap:10px; margin-top:10px; align-items:center; flex-wrap:wrap; }
select { font:inherit; padding:7px 10px; border:1px solid var(--line);
         border-radius:8px; background:#fdfcfa; }
button { font:inherit; font-weight:bold; background:var(--accent); color:#fff;
         border:0; border-radius:8px; padding:9px 26px; cursor:pointer; }
button:disabled { opacity:.5; cursor:wait; }
button.ghost { background:transparent; color:var(--accent);
               border:1px solid var(--accent); font-weight:normal; padding:7px 16px;
               font-size:.85rem; }
.hint { color:var(--soft); font-size:.8rem; margin-inline-start:auto; }
.think { font-size:.85rem; color:var(--soft); display:flex; align-items:center;
         gap:5px; cursor:pointer; }
.badge { display:inline-block; font-size:.72rem; color:var(--soft);
         border:1px solid var(--line); border-radius:99px; padding:1px 8px;
         margin-inline-start:8px; }
.turn { background:var(--card); border:1px solid var(--line); border-radius:12px;
        padding:16px; margin-top:16px; }
.comment { color:var(--soft); font-size:.95rem; margin-bottom:10px; }
.comment b { color:var(--ink); }
.chip { display:inline-block; font-size:.8rem; font-weight:bold; border-radius:99px;
        padding:2px 12px; margin-inline-end:8px; }
.chip.reply { background:var(--reply); color:#155d33; }
.chip.skip { background:var(--skip); color:#6b675f; }
.chip.escalate { background:var(--esc); color:#a32020; }
.chip.error { background:var(--err); color:#8a5a00; }
.reason { color:var(--soft); font-size:.85rem; }
.bubble { background:var(--reply); border-radius:10px; padding:10px 14px;
          margin:10px 0; font-size:1.05rem; line-height:1.9; }
.stats { display:flex; flex-wrap:wrap; gap:6px 14px; color:var(--soft);
         font-size:.8rem; border-top:1px dashed var(--line); padding-top:10px; }
.stats b { color:var(--ink); font-weight:600; }
.warm { color:#155d33; font-weight:bold; }
.cold { color:#a35a00; font-weight:bold; }
details { margin-top:10px; }
summary { cursor:pointer; color:var(--accent); font-size:.85rem; }
pre { background:#f4f2ec; border-radius:8px; padding:10px 12px; font-size:.78rem;
      overflow-x:auto; white-space:pre-wrap; word-break:break-word;
      font-family:ui-monospace,monospace; }
.errbox { background:var(--err); border-radius:8px; padding:10px 14px;
          margin-top:10px; }
a { color:var(--accent); }
/* The only direction handling on the page, and deliberately the only one. Every
   block that can hold operator text or model text carries dir="auto", so the
   browser takes that block's direction from that block's own first strong
   character, and plaintext stops a quoted link or a number from flipping the run
   around it. A page level direction rule would decide for every block in advance
   and be wrong for any script it was not written for. */
[dir="auto"] { unicode-bidi:plaintext; }
</style></head><body><main>
<h1>commentdesk</h1>
<p class="sub" id="meta"></p>
<div class="row" style="margin-bottom:14px">
  <button id="showPrompt" class="ghost">Show prompt and config</button>
  <button id="reload" class="ghost">Reload after edits</button>
  <span class="hint" id="reloadNote"></span>
</div>
<div id="promptPanel" class="panel" style="display:none; margin-bottom:16px">
  <p class="reason">Edit any of these files, then press Reload and test again. The
    first request after an edit pays for a cold cache.</p>
  <details open><summary>1. Voice rules<span class="badge" id="voicePath"></span>
    </summary><pre dir="auto" id="voiceText"></pre></details>
  <details><summary>2. Worked examples<span class="badge" id="examplesPath"></span>
    </summary><pre dir="auto" id="examplesText"></pre></details>
  <details><summary>3. Config<span class="badge" id="configPath"></span>
    </summary><pre dir="auto" id="configText"></pre></details>
  <details><summary>4. The prompt actually sent, placeholders filled. Built from 1,
    2 and 3, so it has no file of its own.</summary>
    <pre dir="auto" id="systemText"></pre></details>
  <details><summary>5. Knowledge<span class="badge" id="knowledgePath"></span>
    </summary><p class="reason" id="knowledgeStats"></p>
    <pre dir="auto" id="knowledgePreview"></pre></details>
</div>
<div class="panel">
  <textarea id="comment" dir="auto"
    placeholder="Type a test comment in any language"></textarea>
  <div class="row">
    <select id="platform"></select>
    <select id="model"></select>
    <label class="think"><input type="checkbox" id="reasoning"> hidden reasoning</label>
    <button id="send">Test</button>
    <span class="hint">Ctrl+Enter to send</span>
  </div>
</div>
<div id="turns"></div>
<script>
const $ = id => document.getElementById(id);
function esc(s) { const d = document.createElement('span');
  d.textContent = s == null ? '' : String(s); return d.innerHTML; }
function fill(sel, pairs, chosen) {
  // Rebuilt on every reload so a model added to the config shows up without a
  // restart, with the operator's current pick put back rather than reset.
  const current = sel.value;
  sel.textContent = '';
  pairs.forEach(pair => {
    const o = document.createElement('option');
    o.value = pair[0]; o.textContent = pair[1];
    if (pair[0] === chosen) o.selected = true;
    sel.appendChild(o);
  });
  if (pairs.some(pair => pair[0] === current)) sel.value = current;
}
// m is the /meta payload and p is the /prompt payload, everywhere on this page.
// Those key names are the contract with the Python that builds them.
function applyMeta(m) {
  $('meta').textContent = m.product;
  fill($('model'), m.models.map(x => [x.label, x.label + ' (' + x.model + ')']),
       m.label);
  fill($('platform'), m.platforms.map(x => [x, x]), m.platforms[0]);
}
fetch('/meta').then(r => r.json()).then(applyMeta);
async function send() {
  const comment = $('comment').value.trim();
  if (!comment) return;
  $('send').disabled = true; $('send').textContent = '...';
  try {
    const res = await fetch('/api/reply', {method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({comment: comment, platform: $('platform').value,
                            model: $('model').value,
                            reasoning: $('reasoning').checked})});
    const t = await res.json();
    if (!res.ok) throw new Error(t.error || res.status);
    render(t);
    $('comment').value = '';
  } catch (e) {
    const div = document.createElement('div');
    div.className = 'turn';
    div.innerHTML = '<div class="errbox" dir="auto">Error: ' +
      esc(String(e.message || e)) + '</div>';
    $('turns').prepend(div);
  }
  $('send').disabled = false; $('send').textContent = 'Test';
}
function render(t) {
  const u = t.usage, pct = u.prompt_tokens
    ? Math.round(100 * u.cached_tokens / u.prompt_tokens) : 0;
  const userMsg = t.request_messages[t.request_messages.length - 1].content;
  const sysBlocks = t.request_messages[0].content;
  const sysChars = sysBlocks.reduce((n, b) => n + (b.text || '').length, 0);
  // esc() escapes text, not attribute values, so the one value that lands inside an
  // attribute is checked against the set the parser can produce. It goes through
  // esc() as well, so that every value concatenated into markup goes through esc()
  // with no exceptions, which is a rule a test can check mechanically.
  const cls = ['reply', 'skip', 'escalate', 'error'].indexOf(t.decision) < 0
    ? 'error' : t.decision;
  // Built here rather than inside the markup, so that every value in the block
  // below is a single esc() call and the escaping rule can be checked by reading it.
  const cost = t.cost_usd == null ? 'n/a' : '$' + t.cost_usd.toFixed(6);
  const div = document.createElement('div');
  div.className = 'turn';
  div.innerHTML =
    '<div class="comment"><b dir="auto">' + esc(t.comment) + '</b> ' +
      esc(t.platform) +
      '<span class="badge">' + esc(t.model) + '</span>' +
      '<span class="badge">reasoning ' + (t.reasoning ? 'ON' : 'off') + '</span>' +
    '</div>' +
    '<span class="chip ' + esc(cls) + '">' + esc(t.decision) + '</span>' +
    '<span class="reason" dir="auto">' + esc(t.reason) + '</span>' +
    (t.reply ? '<div class="bubble" dir="auto">' + esc(t.reply) + '</div>' : '') +
    (t.error ? '<div class="errbox" dir="auto">' + esc(t.error) + '</div>' : '') +
    '<div class="stats">' +
      '<span>input tokens <b>' + esc(u.prompt_tokens) + '</b></span>' +
      '<span>cached <b class="' + (pct > 50 ? 'warm' : 'cold') + '">' +
        esc(u.cached_tokens) + ' (' + esc(pct) + '%)</b></span>' +
      '<span>output <b>' + esc(u.completion_tokens) + '</b></span>' +
      '<span>cost <b>' + esc(cost) + '</b></span>' +
      '<span>time <b>' + esc(t.latency_s) + 's</b></span>' +
      '<span>attempts <b>' + esc(t.attempts) + '</b></span></div>' +
    '<details><summary>Full trace</summary>' +
      '<p class="reason">Raw model output, before parsing:</p><pre>' +
        esc(t.raw_response || '(none)') + '</pre>' +
      '<p class="reason">The message sent after the prompt and the knowledge:</p>' +
        '<pre dir="auto">' + esc(userMsg) + '</pre>' +
      '<p class="reason">Prompt and knowledge: ' +
        esc(sysChars.toLocaleString('en-US')) +
        ' chars sent with every request and cached. Request params:</p><pre>' +
        esc(JSON.stringify(t.params, null, 1)) + '</pre>' +
      '<p class="reason"><a href="/trace" target="_blank">The whole request and ' +
        'response as JSON</a></p>' +
    '</details>';
  $('turns').prepend(div);
}
$('send').onclick = send;
$('comment').addEventListener('keydown',
  e => { if (e.key === 'Enter' && e.ctrlKey) send(); });
async function loadPrompt() {
  const p = await (await fetch('/prompt')).json();
  $('voiceText').textContent = p.voice_text;
  $('voicePath').textContent = p.voice_path;
  $('examplesText').textContent = p.examples_text;
  $('examplesPath').textContent = p.examples_path;
  $('configText').textContent = p.config_text;
  $('configPath').textContent = p.config_path;
  $('systemText').textContent = p.system_text;
  $('knowledgePath').textContent = p.knowledge_path;
  $('knowledgeStats').textContent = 'Size: ' +
    p.knowledge_chars.toLocaleString('en-US') + ' chars, ' +
    p.knowledge_words.toLocaleString('en-US') +
    ' words, sent in full with every request and cached. First part:';
  $('knowledgePreview').textContent = p.knowledge_preview;
}
$('showPrompt').onclick = async () => {
  const panel = $('promptPanel');
  if (panel.style.display === 'none') { await loadPrompt(); panel.style.display = ''; }
  else panel.style.display = 'none';
};
$('reload').onclick = async () => {
  $('reloadNote').textContent = '...';
  const res = await fetch('/api/reload', {method: 'POST'});
  const body = await res.json();
  if (!res.ok) {
    $('reloadNote').textContent = 'Error: ' + (body.error || res.status);
    return;
  }
  applyMeta(body);
  if ($('promptPanel').style.display !== 'none') await loadPrompt();
  $('reloadNote').textContent = 'Reloaded';
  setTimeout(() => { $('reloadNote').textContent = ''; }, 4000);
};
</script></main></body></html>"""


def build_page():
    """The page, which is the same bytes for every operator.

    It takes no arguments on purpose. Anything that varies between operators is
    fetched from /meta and /prompt at load time, so there is exactly one way for a
    product name or a file path to reach the page, and it is the one the reload
    button already refreshes.
    """
    return _PAGE


def meta_json(state):
    """What the page needs to draw its controls: the product it is testing against,
    every model the config offers with the configured default marked, and the
    platform names. The page carries none of them, which is why it stays correct for
    an operator selling something else somewhere else.
    """
    return json.dumps(
        {
            "product": state["product_name"],
            "label": state["model_cfg"]["label"],
            "models": [
                {"label": label, "model": cfg["model"]} for label, cfg in state["models"].items()
            ],
            "platforms": list(state["cfg"]["behavior"]["platforms"]),
        }
    )


def prompt_json(state):
    """The inspector: each source file with the path to open to edit it, the rendered
    prompt that came out of them, and what the knowledge document costs to send.

    The knowledge document is not sent whole here. It is sent whole in the trace,
    where it is the point, but the inspector only needs its size and its opening.
    """
    paths = state["paths"]
    knowledge = state["knowledge_text"]
    return json.dumps(
        {
            "voice_text": state["voice_text"],
            "voice_path": paths["voice"],
            "examples_text": state["examples_text"],
            "examples_path": paths["examples"],
            "config_text": state["config_text"],
            "config_path": paths["config"],
            "system_text": state["system_text"],
            "knowledge_path": paths["knowledge"],
            "knowledge_chars": len(knowledge),
            "knowledge_words": len(knowledge.split()),
            "knowledge_preview": knowledge[:PREVIEW_CHARS],
        }
    )


def get_client(state, model_cfg):
    """The gateway client for model_cfg, built on first use and cached by gateway.

    Caching per (base_url, api_key_env) rather than as a single slot is what
    lets a request follow the model actually selected on the page. A bake-off
    entry may legitimately name a different gateway than the default model,
    since comparing a model across gateways is itself a reason to run a
    bake-off, and a single cached client would otherwise send every request
    through the default's gateway regardless of which model was picked, while
    still reporting the picked model's name in the trace.

    The import is here rather than at module scope so that the tests, and anyone
    reading the page without a key, never need the package or the network.
    """
    key = (model_cfg["base_url"], model_cfg["api_key_env"])
    clients = state.setdefault("clients", {})
    if key not in clients:
        api_key_env = model_cfg["api_key_env"]
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise ConfigError(f"environment variable {api_key_env} is not set")
        from openai import OpenAI

        clients[key] = OpenAI(base_url=model_cfg["base_url"], api_key=api_key)
    return clients[key]


def apply_reload(state):
    """Rebuild everything from disk in place, keeping only the cached clients whose
    gateway a model in the fresh config still names.

    A client is bound to the gateway it was built for. Checking only the default
    model's gateway missed every other one: a bake-off entry naming its own
    base_url or api_key_env is exactly the case a comparison across gateways
    exists for, and a client cached under a key none of the fresh models name
    would otherwise go on serving requests, and spending the operator's key,
    for a gateway the fresh config no longer offers under that label. Keeping
    every cached client whose key still matches some fresh model, rather than
    dropping the whole cache, is what lets the ordinary case, editing the voice
    file and changing no gateway, reload without paying to reconnect clients
    that are still correct. A changed key VALUE in .env is a different matter
    and still needs a restart: load_env uses setdefault, so whatever is already
    in the environment wins.
    """
    fresh = build_state(state["config_path"])
    fresh_gateways = {(mc["base_url"], mc["api_key_env"]) for mc in fresh["models"].values()}
    old_clients = state.get("clients") or {}
    fresh["clients"] = {key: client for key, client in old_clients.items() if key in fresh_gateways}
    fresh["trace"] = state.get("trace") or {}
    state.clear()
    state.update(fresh)
    return state


class _Handler(BaseHTTPRequestHandler):
    """One instance per request, so the shared state and the bound port live on the
    class. make_server puts them there on a fresh subclass."""

    state: dict
    port: int

    def log_message(self, format, *args):
        pass  # the terminal belongs to the operator, not to a request log

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _forbid(self):
        self._send(403, b'{"error": "forbidden"}', "application/json")
        return False

    def _local_only(self):
        """Reject anything that was not typed into this machine's own browser tab.

        Two attacks, one guard. Any page the operator happens to have open can POST
        to /api/reply and spend money on their key, so a request carrying a foreign
        Origin is refused. And a hostname the attacker controls that resolves to
        127.0.0.1, which is DNS rebinding, would let that page read /prompt and
        /trace, which between them hold the whole knowledge document. So the Host
        header has to be a loopback name too. There is no authentication here because
        there are no accounts, and this is what stands in for it.
        """
        raw = (self.headers.get("Host") or "").strip()
        if raw.startswith("["):  # an IPv6 literal keeps its brackets
            host = raw[1 : raw.find("]")] if "]" in raw else ""
        else:
            host = raw.rsplit(":", 1)[0]
        # Lowercased because a hostname is case-insensitive: an attacker's page
        # is free to write "Localhost" and a bare string comparison would miss it.
        if host.lower() not in ("127.0.0.1", "localhost", "::1"):
            return self._forbid()
        origin = self.headers.get("Origin")
        # No Origin header at all is the ordinary case: a same origin GET sends none.
        if origin and origin not in (
            f"http://127.0.0.1:{self.port}",
            f"http://localhost:{self.port}",
        ):
            return self._forbid()
        return True

    def do_GET(self):
        if not self._local_only():
            return
        if self.path == "/":
            self._send(200, build_page().encode(), "text/html")
        elif self.path == "/meta":
            self._send(200, meta_json(self.state).encode(), "application/json")
        elif self.path == "/prompt":
            self._send(200, prompt_json(self.state).encode(), "application/json")
        elif self.path == "/trace":
            # The last trace, held in memory rather than written to disk: it contains
            # the whole knowledge document, and a file would be one more thing to
            # remember not to commit.
            body = json.dumps(self.state.get("trace") or {}, indent=2).encode()
            self._send(200, body, "application/json")
        elif self.path == "/favicon.ico":
            self._send(204, b"", "image/x-icon")
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if not self._local_only():
            return
        if self.path == "/api/reload":
            try:
                apply_reload(self.state)
                self._send(200, meta_json(self.state).encode(), "application/json")
            except Exception as exc:  # noqa: BLE001 - every failure belongs on the page
                # Broad on purpose: a reload runs whatever the operator has just typed
                # through the whole loader, and every way that can fail belongs on the
                # page in front of them.
                body = json.dumps({"error": str(exc)}).encode()
                self._send(400, body, "application/json")
            return
        if self.path != "/api/reply":
            self._send(404, b'{"error": "not found"}', "application/json")
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            comment = (payload.get("comment") or "").strip()
            if not comment:
                raise ValueError("empty comment")
            # The picked model, or the configured default when the page sends a label
            # this process does not know. Reasoning is set explicitly either way,
            # rather than left to whatever the config happened to say, because the
            # checkbox is the whole point of having it here.
            model_cfg = self.state["models"].get(payload.get("model"), self.state["model_cfg"])
            reasoning = bool(payload.get("reasoning"))
            trace = run_one(
                self.state["cfg"],
                with_reasoning(model_cfg, reasoning),
                get_client(self.state, model_cfg),
                self.state["knowledge_text"],
                self.state["system_text"],
                comment,
                platform=payload.get("platform") or "",
            )
            trace["reasoning"] = reasoning
            self.state["trace"] = trace
            # The trace goes back whole, request messages and all, so that what the
            # page shows is what was sent rather than a reconstruction of it.
            self._send(200, json.dumps(trace).encode(), "application/json")
        except Exception as exc:  # noqa: BLE001 - a bad request or a model failure
            # both land on the page as text rather than a traceback in a terminal
            # nobody is watching.
            body = json.dumps({"error": str(exc)}).encode()
            self._send(400, body, "application/json")


def make_server(state, host="127.0.0.1", port=8377):
    """Bind and return the server without starting it, so a caller can drive it on an
    ephemeral port. Threading, because a slow model call must not block the page from
    loading its own stylesheet.

    The state and the bound port go on a fresh handler subclass: the server builds a
    new handler for every request, so the class is the only thing both ends can see,
    and a subclass per server keeps two servers in one process from sharing it.
    """

    class Bound(_Handler):
        pass

    server = ThreadingHTTPServer((host, port), Bound)
    Bound.state = state
    Bound.port = server.server_port
    return server


def serve(config_path, host="127.0.0.1", port=8377):
    """Serve the test page until interrupted.

    The loopback default is not a convenience. The page spends one model call per
    request against the operator's own key, so anything that can reach it can spend
    money, and the whole knowledge document is readable from it. The address it binds
    to and the guard in _local_only are the entire security model.
    """
    state = build_state(config_path)
    key_env = state["model_cfg"]["api_key_env"]
    if not os.environ.get(key_env):
        # Not fatal. The prompt inspector is worth reading with no key at all, and the
        # first test says so on the page rather than in a terminal nobody is watching.
        print(f"warning: {key_env} is not set, so a test will fail until it is")
    server = make_server(state, host, port)
    url = f"http://{host}:{server.server_port}"
    print(f"open {url} in a browser, Ctrl+C to stop")
    with contextlib.suppress(Exception):
        # a headless machine has no browser to open and does not need one
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
