# SPDX-License-Identifier: Apache-2.0
"""Turn the configuration into the list of models a bake-off should run.

A bake-off runs the same comments through several models so the review page can
put the drafts, the latencies and the prices side by side. This module owns only
the list of model configurations. Driving the runs belongs to the command line,
and rendering the comparison belongs to the review page.
"""

from .config import ConfigError

# The only two keys a bake-off entry inherits from [model].
GATEWAY_KEYS = ("base_url", "api_key_env")

REQUIRED_ENTRY_KEYS = ("label", "model", "params")


def bakeoff_model_cfgs(cfg: dict) -> list[dict]:
    """The default model first, then every [[bakeoff.models]] entry.

    Entries inherit ONLY base_url and api_key_env. Inheriting the whole [model]
    block would hand an entry that omits pricing the default model's rates, and a
    bake-off exists precisely to compare prices, so a silently mispriced row is
    worse than a blank cost column. The same applies to params: an entry that
    inherited them would look compliant while sending nothing of its own.

    params is required rather than optional for that reason. An entry with no
    params block is exactly the entry that would run with data collection left at
    the gateway default, which is the one promise about operator data that cannot
    survive being quietly wrong. It is checked here rather than at request time
    because a run that has already started has already sent the first comment.
    """
    entries = (cfg.get("bakeoff") or {}).get("models") or []
    gateway = {key: cfg["model"][key] for key in GATEWAY_KEYS}
    model_cfgs = [cfg["model"]]
    for position, entry in enumerate(entries, start=1):
        missing = [key for key in REQUIRED_ENTRY_KEYS if key not in entry]
        if missing:
            # Named by label where there is one, by position where there is not,
            # because the operator has to find the offending table in the file.
            name = entry.get("label") or f"entry {position}"
            raise ConfigError(f"[[bakeoff.models]] {name} is missing: {', '.join(missing)}")
        params = entry["params"]
        if not isinstance(params, dict):
            raise ConfigError(
                f"[[bakeoff.models]] entry '{entry['label']}' needs params to be a table"
            )
        provider = params.get("provider")
        # Nested inside provider, never at the top level of params. At the top
        # level the gateway accepts the key, ignores it, and defaults to allow.
        if not isinstance(provider, dict) or provider.get("data_collection") != "deny":
            raise ConfigError(
                f"[[bakeoff.models]] entry '{entry['label']}' must set "
                'params.provider.data_collection = "deny"'
            )
        model_cfgs.append({**gateway, **entry})
    return model_cfgs
