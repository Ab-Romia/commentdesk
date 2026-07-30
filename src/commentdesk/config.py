# SPDX-License-Identifier: Apache-2.0
"""Load a config, check its shape, resolve its paths.

This module validates shape and never truth. A missing section, a cta_mode naming
no table, an empty plug_markers list: each of those produces output that is wrong
without being an error, so each one stops the run before a token is spent.

A wrong price or a dead purchase link passes straight through into the drafted
replies. Nothing here can tell a right price from a wrong one, and rejecting a
price that merely looks odd would make the tool feel checked when it is not. The
person who reviews every reply before it posts is the right place to catch it.
"""

import os
import tomllib
from pathlib import Path


class ConfigError(Exception):
    """Any shape problem in the config file."""


REQUIRED = {
    "product": ["name", "kind", "price_text", "purchase_link", "escalation_contact"],
    "knowledge": ["source", "path"],
    "voice": ["rules", "examples"],
    "behavior": [
        "cta_mode",
        "plug_cap",
        "max_reply_sentences",
        "bot_disclosure_text",
        "plug_markers",
        "separator",
        "banned_emoji",
    ],
    "model": ["label", "base_url", "model", "api_key_env"],
}

# Relative paths in the config, checked as a group because all three are read
# later and an empty one fails in the same quiet way.
PATH_KEYS = [("knowledge", "path"), ("voice", "rules"), ("voice", "examples")]


def load_config(path: str | Path = "config.toml") -> dict:
    """Read config.toml and return it, or raise ConfigError describing the problem."""
    try:
        with open(path, "rb") as handle:
            cfg = tomllib.load(handle)
    except FileNotFoundError:
        raise ConfigError(f"config file not found: {path}") from None
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML in {path}: {exc}") from exc

    for section, keys in REQUIRED.items():
        if section not in cfg:
            raise ConfigError(f"missing [{section}] section")
        if not isinstance(cfg[section], dict):
            raise ConfigError(f"[{section}] must be a table")
        for key in keys:
            if key not in cfg[section]:
                raise ConfigError(f"missing {section}.{key}")

    _check_paths(cfg)
    _check_behavior(cfg)

    # Both tables are optional in the file and read unconditionally downstream.
    cfg["model"].setdefault("params", {})
    cfg["model"].setdefault("pricing", {})
    return cfg


def _require_text(value: object, label: str, hint: str = "") -> str:
    if not isinstance(value, str) or not value.strip():
        suffix = f" ({hint})" if hint else ""
        raise ConfigError(f"{label} must be a non-empty string{suffix}")
    return value


def _require_text_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ConfigError(f"{label} must be a non-empty list of strings")
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ConfigError(f"{label}[{index}] must be a non-empty string")
    return value


def _check_paths(cfg: dict) -> None:
    """The operator's three files are named here and read from disk later.

    An empty path is worth catching now rather than at read time: it resolves to
    the directory holding config.toml, and the text source would then concatenate
    everything sitting next to the config into the prompt. That is a wrong answer
    that never raises.
    """
    _require_text(cfg["knowledge"]["source"], "knowledge.source", "a registered source name")
    for section, key in PATH_KEYS:
        _require_text(cfg[section][key], f"{section}.{key}", "a path relative to config.toml")


def _check_behavior(cfg: dict) -> None:
    behavior = cfg["behavior"]

    # cta_mode is checked against the tables this config defines, not against a
    # set of names in Python. Any number of CTA styles can exist, each written
    # entirely in TOML, which is what keeps the last block of reader-facing copy
    # out of the package.
    mode = behavior["cta_mode"]
    tables = cfg.get("cta")
    if not isinstance(tables, dict):
        tables = {}
    if not isinstance(mode, str):
        raise ConfigError("behavior.cta_mode must be a string naming a [cta.<name>] table")
    if mode not in tables:
        available = ", ".join(sorted(tables)) if tables else "none defined"
        raise ConfigError(
            f"behavior.cta_mode is {mode!r} but no [cta.{mode}] table exists; "
            f"defined cta tables: {available}"
        )

    # Only the selected table is rendered, so only it has to be complete. An
    # operator drafting a second style must not be blocked by a half-written one.
    table = tables[mode]
    if not isinstance(table, dict):
        raise ConfigError(f"[cta.{mode}] must be a table")
    _require_text(table.get("instruction"), f"cta.{mode}.instruction")
    _require_text_list(table.get("phrases"), f"cta.{mode}.phrases")

    # plug_markers decides which replies count as a plug, and both the run report
    # and plug_cap read that count. Hardcoding the markers has already failed
    # once: written for one product, they matched nothing under any other config,
    # so every reply scored as not a plug, the report printed a plug count of
    # zero, and plug_cap could never fire. Nothing errored. A run reporting zero
    # plugs is indistinguishable from a run that has none, which makes it a
    # failure that looks like success. Requiring the list makes the state
    # unreachable instead of merely unlikely.
    _require_text_list(behavior.get("plug_markers"), "behavior.plug_markers")

    # One required string and no enum. The mode that dodged the question is not
    # configurable because it no longer exists anywhere in the package. A
    # disclosure with an off switch is not a disclosure.
    _require_text(behavior["bot_disclosure_text"], "behavior.bot_disclosure_text")

    # separator replaces the dashes taken out of a reply. It is stated, never
    # inferred: the version that guessed it from the script of the text defaulted
    # every script it could not measure to one language's comma and injected that
    # mark into replies written in languages that have no such punctuation, which
    # is the exact failure the sanitizer exists to prevent.
    if not isinstance(behavior["separator"], str) or not behavior["separator"]:
        raise ConfigError("behavior.separator must be a non-empty string")

    # banned_emoji is a set of characters written as one string, so empty is a
    # meaningful value that bans nothing. A list is the natural mistake and it
    # would silently ban nothing too.
    if not isinstance(behavior["banned_emoji"], str):
        raise ConfigError("behavior.banned_emoji must be a string, empty to ban nothing")

    # An alarm threshold, never a limiter. Nothing stops a run that crosses it:
    # the report says so and a person decides. A limiter would drop exactly the
    # replies most worth reading.
    try:
        plug_cap = float(behavior["plug_cap"])
    except (TypeError, ValueError):
        raise ConfigError("behavior.plug_cap must be a number between 0 and 1") from None
    if not 0 <= plug_cap <= 1:
        raise ConfigError("behavior.plug_cap must be between 0 and 1")


def resolve_path(config_dir: Path, rel: str) -> Path:
    """Resolve a path from the config against the directory holding config.toml.

    Every path in the file is relative to the config, never to the working
    directory. That is what lets a run be pointed at a config in another
    directory and still find the knowledge document and the voice files, and what
    lets an example directory be copied elsewhere and still work. An absolute
    path is honoured as written.
    """
    path = Path(rel)
    if path.is_absolute():
        return path
    return (Path(config_dir) / path).resolve()


def model_options(cfg: dict) -> dict[str, dict]:
    """Every model the config offers, keyed by label, the default one first.

    Entries inherit only the gateway keys. Inheriting the whole [model] table
    would hand an entry that declares no pricing the default model's rates, and a
    comparison between models is exactly where a wrong price does the most
    damage. A missing rate has to show up as a blank cost, not a plausible one.
    """
    gateway = {key: cfg["model"][key] for key in ("base_url", "api_key_env")}
    options = {cfg["model"]["label"]: cfg["model"]}
    for entry in (cfg.get("bakeoff") or {}).get("models", []):
        # Every consumer keys on the label, so an entry without one has no name
        # to be selected by. It is skipped rather than guessed at.
        if "label" in entry:
            options[entry["label"]] = {**gateway, **entry}
    return options


def with_reasoning(model_cfg: dict, enabled: bool) -> dict:
    """A copy of a model config with hidden reasoning forced on or off.

    Off is the production setting: on this task the model thinks for thousands of
    tokens nobody reads, which costs money and seconds and changed nothing
    measurable in the output. On exists for comparison, and for the models that
    refuse to switch it off the error they return is itself the finding.

    Both keys are written when it is off. `reasoning` is the gateway's own switch
    and is the one that takes effect; `enable_thinking` is the provider-native
    flag, accepted and silently ignored on some routes. When reasoning is on the
    native flag is removed, because leaving it set contradicts the switch that
    works.
    """
    params = dict(model_cfg.get("params") or {})
    params["reasoning"] = {"enabled": bool(enabled)}
    if enabled:
        params.pop("enable_thinking", None)
    else:
        params["enable_thinking"] = False
    return {**model_cfg, "params": params}


def load_env(path: str | Path = ".env") -> None:
    """Load every KEY=VALUE line from an env file into the environment.

    setdefault rather than assignment: a variable already exported in the shell
    wins over the file, so a run can be pointed at a different key without
    editing the file that holds the real one. A missing file is normal and does
    nothing, because the keys may come from the shell alone.
    """
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())
