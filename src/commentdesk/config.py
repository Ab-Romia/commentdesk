# SPDX-License-Identifier: Apache-2.0
"""Load a config, check its shape, resolve its paths.

This module validates shape and never truth. A missing section or an out of range
threshold stops the run before a token is spent, because each one produces output
that is wrong without being an error.

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

    # An alarm threshold, never a limiter. Nothing stops a run that crosses it:
    # the report says so and a person decides. A limiter would drop exactly the
    # replies most worth reading.
    try:
        plug_cap = float(cfg["behavior"]["plug_cap"])
    except (TypeError, ValueError):
        raise ConfigError("behavior.plug_cap must be a number between 0 and 1") from None
    if not 0 <= plug_cap <= 1:
        raise ConfigError("behavior.plug_cap must be between 0 and 1")

    # Both tables are optional in the file and read unconditionally downstream.
    cfg["model"].setdefault("params", {})
    cfg["model"].setdefault("pricing", {})
    return cfg


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
