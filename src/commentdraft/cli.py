# SPDX-License-Identifier: Apache-2.0
"""Command line entry point: run, review, publish, chat, ui, ingest, bakeoff.

Startup problems print one line and return 2. A traceback at that point would be
noise: nothing has run, and the only useful fact is which file or which variable
is wrong. A run that reached the model and lost rows returns 1 instead, so a
scripted caller can tell a partial pass from a clean one.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .bakeoff import bakeoff_model_cfgs
from .config import ConfigError, load_config, load_env
from .engine import read_comments, run_one, run_pipeline, write_rows
from .prompt import render_system_text
from .render.review_html import blind_label, load_row_sets, load_rows, render_review
from .report import build_report
from .sources import SourceError, load_knowledge

# transcribe_pdf is imported at module scope, not lazily inside cmd_ingest. The
# lazy version and its ImportError handler were both dead: sources/__init__.py
# imports pdf_vision eagerly to register the handler, so the line above has already
# loaded it before cmd_ingest can run. The module costs nothing to import either,
# because pymupdf is imported inside render_pages and a missing extra surfaces
# there as a SourceError, which cmd_ingest already catches.
from .sources.pdf_vision import transcribe_pdf

SAFE_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")


def _fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 2


def make_client(model_cfg: dict):
    """Build the API client for one model config.

    Imported inside the function rather than at module level so that importing
    this module never touches the SDK, which is what keeps the whole test suite
    offline. Tests replace this function to run the pipeline against a stub.
    """
    from openai import OpenAI

    return OpenAI(base_url=model_cfg["base_url"], api_key=os.environ[model_cfg["api_key_env"]])


def safe_name(label: str) -> str:
    """A label reduced to something that can only name a file inside --out.

    Labels come out of the config, so a label with a slash in it would otherwise
    write outside the output directory the operator asked for.
    """
    cleaned = "".join(ch if ch in SAFE_CHARS else "_" for ch in str(label))
    return cleaned or "model"


def format_trace(trace: dict) -> str:
    """One comment's whole story: what came back, what it cost, how many tries.

    Every key is read with .get so that a trace missing one field prints a blank
    rather than stopping an interactive session.
    """
    usage = trace.get("usage") or {}
    prompt = usage.get("prompt_tokens", 0) or 0
    cached = usage.get("cached_tokens", 0) or 0
    pct = round(100 * cached / prompt) if prompt else 0
    cost = trace.get("cost_usd")
    rule = "-" * 62
    lines = [
        rule,
        (
            f"model     {trace.get('model', '')}"
            f"   attempts {trace.get('attempts', '?')}"
            f"   {trace.get('latency_s', '?')}s"
        ),
        f"raw       {trace.get('raw_response') or '(no response)'}",
    ]
    if trace.get("error"):
        lines.append(f"error     {trace['error']}")
    lines += [
        f"decision  {trace.get('decision', '')}",
        f"reason    {trace.get('reason') or '(none)'}",
        f"reply     {trace.get('reply') or '(no reply)'}",
        (
            f"tokens    prompt {prompt} (cached {cached}, {pct}%)"
            f"   output {usage.get('completion_tokens', 0)}"
            f"   cache-write {usage.get('cache_write_tokens', 0)}"
        ),
        "cost      " + (f"${cost:.6f}" if isinstance(cost, (int, float)) else "n/a"),
        rule,
    ]
    return "\n".join(lines)


def _prepare(args):
    """Everything a run needs before it needs a key. Raises for the caller."""
    cfg = load_config(args.config)
    config_dir = Path(args.config).resolve().parent
    knowledge_text = load_knowledge(cfg, config_dir)
    system_text = render_system_text(cfg, config_dir)
    return cfg, knowledge_text, system_text


def _missing_keys(model_cfgs) -> list[str]:
    return sorted({mc["api_key_env"] for mc in model_cfgs if not os.environ.get(mc["api_key_env"])})


def _triage(args, *, bakeoff: bool) -> int:
    try:
        cfg, knowledge_text, system_text = _prepare(args)
    except (ConfigError, SourceError) as e:
        return _fail(str(e))
    except OSError as e:
        return _fail(f"cannot read a file named in {args.config}: {e}")
    try:
        comments = read_comments(args.comments)
    except ConfigError as e:
        return _fail(str(e))
    except UnicodeDecodeError as e:
        # A spreadsheet exporting "CSV" in a legacy single byte encoding lands here.
        return _fail(f"cannot read comments file: {e}\nSave it as CSV UTF-8 and try again.")
    except OSError as e:
        return _fail(f"cannot read comments file: {e}")

    if bakeoff:
        try:
            model_cfgs = bakeoff_model_cfgs(cfg)
        except ConfigError as e:
            return _fail(str(e))
        if len(model_cfgs) < 2:
            return _fail(f"bakeoff needs at least one [[bakeoff.models]] entry in {args.config}")
    else:
        model_cfgs = [cfg["model"]]

    # Every variable across every selected model, named at once, before the first
    # call. Finding the second one after the first model has been paid for is the
    # expensive way to learn it. This is the last check that costs nothing, so it
    # is the last thing that happens before a client exists.
    missing = _missing_keys(model_cfgs)
    if missing:
        return _fail(
            f"missing env var(s): {', '.join(missing)} (put them in .env next to {args.config})"
        )

    behavior = cfg["behavior"]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    had_errors = False
    for model_cfg in model_cfgs:
        client = make_client(model_cfg)
        print(f"model: {model_cfg['label']} ({model_cfg['model']})")
        rows = run_pipeline(cfg, model_cfg, comments, knowledge_text, system_text, client)
        name = f"review-{safe_name(model_cfg['label'])}.csv" if bakeoff else "review.csv"
        path = out_dir / name
        write_rows(rows, path)
        print(build_report(rows, float(behavior["plug_cap"]), list(behavior["plug_markers"])))
        print(f"wrote {path}\n")
        written.append(path)
        had_errors = had_errors or any(r.get("decision") == "error" for r in rows)

    if bakeoff:
        key = {blind_label(i): mc["label"] for i, mc in enumerate(model_cfgs)}
        key_path = out_dir / "bakeoff-blind_key.json"
        key_path.write_text(json.dumps(key, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {key_path}")
        # The letters are positional on the review page too, so passing the files
        # in this order reproduces exactly this key rather than a second one that
        # disagrees with it.
        print(
            "review them blind with:\n  commentdraft review "
            + " ".join(str(p) for p in written)
            + " --blind"
        )

    # Non-zero so a scripted run cannot mistake a partial pass for a clean one.
    return 1 if had_errors else 0


def cmd_run(args) -> int:
    return _triage(args, bakeoff=False)


def cmd_bakeoff(args) -> int:
    return _triage(args, bakeoff=True)


def cmd_review(args) -> int:
    paths = [Path(p) for p in args.csvs]
    for path in paths:
        if not path.exists():
            return _fail(f"csv not found: {path}")
    try:
        row_sets = load_row_sets(paths)
    except UnicodeDecodeError as e:
        return _fail(f"cannot read review csv: {e}\nSave it as CSV UTF-8.")
    except OSError as e:
        return _fail(f"cannot read review csv: {e}")
    page, key = render_review(
        row_sets,
        title=args.title,
        approved=args.approved,
        blind=args.blind,
        currency_note=args.currency_note,
    )
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    page_path = out_dir / "review.html"
    page_path.write_text(page, encoding="utf-8")
    print(f"wrote {page_path}")
    if key:
        # Named after the page it unlocks, so two pages written to different --out
        # cannot share one key file. Rewriting the same --out replaces both
        # together, which is correct: the key is regenerated with the page.
        key_path = page_path.with_name(page_path.stem + "-blind_key.json")
        key_path.write_text(json.dumps(key, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {key_path}")
    return 0


def cmd_chat(args) -> int:
    try:
        cfg, knowledge_text, system_text = _prepare(args)
    except (ConfigError, SourceError) as e:
        return _fail(str(e))
    except OSError as e:
        return _fail(f"cannot read a file named in {args.config}: {e}")
    model_cfg = cfg["model"]
    missing = _missing_keys([model_cfg])
    if missing:
        return _fail(
            f"missing env var(s): {', '.join(missing)} (put them in .env next to {args.config})"
        )
    platforms = list(cfg["behavior"].get("platforms") or [])
    platform = args.platform or (platforms[0] if platforms else "")
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    client = make_client(model_cfg)
    print("Type a comment to see the decision, the reply and the full trace.")
    print(f"Blank line or Ctrl+D to stop. Platform: {platform or '(none)'}")
    while True:
        try:
            comment = input("\ncomment> ").strip()
        except EOFError:
            break
        if not comment:
            break
        trace = run_one(
            cfg, model_cfg, client, knowledge_text, system_text, comment, platform, args.author
        )
        print(format_trace(trace))
        # The trace holds the entire request, knowledge document included, so it
        # goes under the output directory, which is not committed.
        (out_dir / "trace-last.json").write_text(
            json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return 0


def cmd_ui(args) -> int:
    # Lazy on the same rule as the ingest import below: a subcommand's own
    # dependencies load only when that subcommand runs, not on every invocation
    # of the CLI.
    from . import ui

    try:
        ui.serve(Path(args.config), port=args.port)
    except (ConfigError, SourceError) as e:
        return _fail(str(e))
    except OSError as e:
        return _fail(f"cannot start the server on port {args.port}: {e}")
    except KeyboardInterrupt:
        print()
    return 0


def cmd_publish(args) -> int:
    """Hand the drafted replies to a person, one at a time, and send what they approve.

    Every reason to refuse is found before a row is read, in the order an
    operator can act on: the config, then the platform, then the credential, then
    whether anybody is there to approve anything. A read only setup is the
    recommended starting point, so the message for one has to describe the setup
    rather than read as a fault.

    The credential check and the terminal check are made here for that ordering
    and made again inside the gate, which is where they are load bearing. This is
    not belt and braces: the gate cannot trust a caller, and this caller wants to
    report the reasons in an order that is useful rather than in the order the
    gate happens to reach them.
    """
    try:
        cfg = load_config(args.config)
    except ConfigError as e:
        return _fail(str(e))
    except OSError as e:
        return _fail(f"cannot read a file named in {args.config}: {e}")

    # Lazy, on the same rule as cmd_ui: a subcommand's dependencies load when that
    # subcommand runs, so importing this module still touches nothing.
    from .approve import GateError, approve_and_publish, at_a_keyboard
    from .platforms import PlatformError, find_platform, get_platform, publish_target

    try:
        platform_name, credential_env = publish_target(cfg)
        # Looked up, not built. A name nobody registered is worth saying now, and
        # a connector's constructor is not worth running before the refusals below.
        find_platform(platform_name)
    except PlatformError as e:
        return _fail(str(e))

    # Before a single row is read, and skipped entirely for a dry run: the whole
    # point of a dry run is that a person can read what a platform would receive
    # before granting any write scope at all, and demanding the write scope in
    # order to look would defeat it.
    if not args.dry_run and not os.environ.get(credential_env):
        return _fail(
            f"missing env var(s): {credential_env} (put them in .env next to {args.config})"
        )

    csv_path = Path(args.out) / "review.csv"
    if not csv_path.exists():
        return _fail(
            f"nothing to publish: {csv_path} does not exist. Run `commentdraft run` first."
        )
    try:
        rows = load_rows(csv_path)
    except UnicodeDecodeError as e:
        return _fail(f"cannot read {csv_path}: {e}\nSave it as CSV UTF-8.")
    except OSError as e:
        return _fail(f"cannot read {csv_path}: {e}")

    # Last, because it is the only refusal that is about how the command was
    # invoked rather than about how the operator's setup is written, and the
    # other three are more useful to hear first.
    if not args.dry_run and not at_a_keyboard():
        return _fail(
            "publish needs a terminal: every reply is approved one keystroke at a time, "
            "and a pipe or a redirect cannot read a reply. Run it from a terminal, or "
            "use --dry-run to see what would be sent."
        )

    # Built here and nowhere earlier: after every refusal above, and never at all
    # for a dry run. A connector's __init__ is somebody else's code, and running
    # it during the one command documented as needing no credential and no
    # keystroke would make that documentation false without a single send.
    platform = None
    if not args.dry_run:
        try:
            platform = get_platform(platform_name)
        except PlatformError as e:
            return _fail(str(e))

    try:
        counts = approve_and_publish(
            rows,
            cfg,
            platform,
            platform_name=platform_name,
            config_label=str(args.config),
            log_path=Path(args.out) / "published.jsonl",
            dry_run=args.dry_run,
        )
    except GateError as e:
        # The gate refuses for the same two reasons this function does, so an
        # operator only reaches this line by calling in a way that skipped them.
        return _fail(str(e))
    # Non-zero when a send was refused by the platform, or made and not written
    # down, on the same rule as a run that lost rows: a scripted caller must not
    # mistake a partial pass for a clean one. A reply the reviewer skipped is not
    # a failure, because skipping is a decision rather than a fault.
    return 1 if counts["failed"] or counts["unrecorded"] else 0


def cmd_ingest(args) -> int:
    try:
        cfg = load_config(args.config)
    except ConfigError as e:
        return _fail(str(e))
    out = Path(args.out)
    # Refuse before spending anything. The file already there may be the corrected
    # transcription, it is gitignored, and nothing can bring it back.
    if out.exists():
        return _fail(f"{out} already exists. Delete it, or pass --out to write somewhere else.")
    model_cfg = cfg["model"]
    missing = _missing_keys([model_cfg])
    if missing:
        return _fail(
            f"missing env var(s): {', '.join(missing)} (put them in .env next to {args.config})"
        )
    client = make_client(model_cfg)
    try:
        written = transcribe_pdf(Path(args.pdf), out, model_cfg, client)
    except (SourceError, OSError) as e:
        return _fail(str(e))
    print(f"wrote {written}")
    return 0


# --config and --out are added per subcommand rather than to all six, because two of
# the six never read the one they were given: cmd_review never looks at args.config
# and cmd_ui never looks at args.out. Both still appeared in --help, which offers an
# operator a flag that changes nothing.
def _config_arg(parser):
    parser.add_argument(
        "--config",
        default="config.toml",
        help="path to config.toml. Every path inside it is "
        "resolved against the directory holding it.",
    )
    return parser


def _out_arg(parser, default="out", text="output directory"):
    parser.add_argument("--out", default=default, help=text)
    return parser


def _common(parser, out_default="out", out_help="output directory"):
    return _out_arg(_config_arg(parser), out_default, out_help)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="commentdraft",
        description=(
            "Triage comments and draft replies. Nothing is published that a person "
            "has not approved, one reply at a time."
        ),
    )
    subs = parser.add_subparsers(dest="command")

    run = _common(subs.add_parser("run", help="triage a CSV of comments"))
    run.add_argument("--comments", default="comments.csv")

    bake = _common(
        subs.add_parser("bakeoff", help="run every configured model over the same comments")
    )
    bake.add_argument("--comments", default="comments.csv")

    # Reads CSVs named on the command line and nothing out of a config, so it takes
    # no --config.
    review = _out_arg(subs.add_parser("review", help="render result CSVs into one review page"))
    review.add_argument("csvs", nargs="+")
    review.add_argument(
        "--approved",
        action="store_true",
        help="drop the draft banner. A person has read and approved every reply on the page.",
    )
    review.add_argument(
        "--blind",
        action="store_true",
        help="label the sets A, B, C, drop the model column and the cost, "
        "and write the key to a separate file",
    )
    review.add_argument("--title", default="Reply review")
    review.add_argument("--currency-note", dest="currency_note", default="")

    # Reads out/review.csv and writes out/published.jsonl, so --out is the whole
    # of its file handling. There is deliberately no --yes and no --all: approval
    # is a keystroke against one reply and cannot be expressed on a command line,
    # which tests/test_guarantees.py asserts by walking every option this parser
    # offers. See src/commentdraft/approve.py for the argument.
    publish = _common(subs.add_parser("publish", help="send the replies a person approves"))
    publish.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="print what each send would carry and send nothing. Asks for no "
        "keystroke and no publish credential.",
    )

    chat = _common(subs.add_parser("chat", help="try one comment at a time"))
    chat.add_argument(
        "--platform", default="", help="defaults to the first entry of behavior.platforms"
    )
    chat.add_argument("--author", default="")

    # Writes no file, so it takes no --out.
    served = _config_arg(subs.add_parser("ui", help="local test interface"))
    # There is deliberately no --host. The page reads out the whole knowledge document
    # and spends the configured key on request, and the bind address is half of what
    # stops that reaching anyone else. A flag offering to bind elsewhere was a one word
    # path to publishing an operator's source document on a shared network, so it is
    # gone rather than warned about. See SECURITY.md.
    served.add_argument("--port", type=int, default=8377)

    ingest = _common(
        subs.add_parser("ingest", help="transcribe a PDF into a knowledge file"),
        out_default="knowledge.md",
        out_help="knowledge file to write (a file)",
    )
    ingest.add_argument("--pdf", required=True)
    return parser


HANDLERS = {
    "run": cmd_run,
    "bakeoff": cmd_bakeoff,
    "review": cmd_review,
    "publish": cmd_publish,
    "chat": cmd_chat,
    "ui": cmd_ui,
    "ingest": cmd_ingest,
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help(sys.stderr)
        return 2
    # The key file lives beside the config, on the same rule as every other path
    # the config names. A .env in the working directory still works. `review` takes
    # no --config, because it reads CSVs named on the command line and nothing out
    # of a config, so it falls back to the working directory like any other caller.
    config = getattr(args, "config", None)
    env_path = Path(config).resolve().parent / ".env" if config else Path(".env")
    load_env(env_path if env_path.exists() else ".env")
    return HANDLERS[args.command](args)
