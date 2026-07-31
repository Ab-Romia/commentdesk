# SPDX-License-Identifier: Apache-2.0
"""Command line entry point: run, review, chat, ui, ingest, bakeoff.

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
from .render.review_html import blind_label, load_row_sets, render_review
from .report import build_report
from .sources import SourceError, load_knowledge

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
            "review them blind with:\n  commentdesk review "
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
        ui.serve(Path(args.config), host=args.host, port=args.port)
    except (ConfigError, SourceError) as e:
        return _fail(str(e))
    except OSError as e:
        return _fail(f"cannot start the server on {args.host}:{args.port}: {e}")
    except KeyboardInterrupt:
        print()
    return 0


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
    try:
        # sources/pdf_vision.py depends on the optional pdf extra, so the import
        # is lazy: ingest is the only subcommand that ever needs it.
        from .sources.pdf_vision import transcribe_pdf
    except ImportError as e:
        return _fail(f"pdf ingestion needs the optional extra: pip install commentdesk[pdf] ({e})")
    client = make_client(model_cfg)
    try:
        written = transcribe_pdf(Path(args.pdf), out, model_cfg, client)
    except (SourceError, OSError) as e:
        return _fail(str(e))
    print(f"wrote {written}")
    return 0


def _common(parser, out_default="out", out_help="output directory"):
    parser.add_argument(
        "--config",
        default="config.toml",
        help="path to config.toml. Every path inside it is "
        "resolved against the directory holding it.",
    )
    parser.add_argument("--out", default=out_default, help=out_help)
    return parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="commentdesk",
        description="Triage comments and draft replies. It never posts anything.",
    )
    subs = parser.add_subparsers(dest="command")

    run = _common(subs.add_parser("run", help="triage a CSV of comments"))
    run.add_argument("--comments", default="comments.csv")

    bake = _common(
        subs.add_parser("bakeoff", help="run every configured model over the same comments")
    )
    bake.add_argument("--comments", default="comments.csv")

    review = _common(subs.add_parser("review", help="render result CSVs into one review page"))
    review.add_argument("csvs", nargs="+")
    review.add_argument(
        "--approved",
        action="store_true",
        help="drop the draft banner. A person has read and approved every reply on the page.",
    )
    review.add_argument(
        "--blind",
        action="store_true",
        help="label the sets A, B, C and write the key to a separate file",
    )
    review.add_argument("--title", default="Reply review")
    review.add_argument("--currency-note", dest="currency_note", default="")

    chat = _common(subs.add_parser("chat", help="try one comment at a time"))
    chat.add_argument(
        "--platform", default="", help="defaults to the first entry of behavior.platforms"
    )
    chat.add_argument("--author", default="")

    served = _common(subs.add_parser("ui", help="local test interface"))
    served.add_argument("--host", default="127.0.0.1")
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
    # the config names. A .env in the working directory still works.
    env_path = Path(args.config).resolve().parent / ".env"
    load_env(env_path if env_path.exists() else ".env")
    return HANDLERS[args.command](args)
