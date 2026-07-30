# SPDX-License-Identifier: Apache-2.0
"""Placeholder substitution and prompt assembly.

The system prefix is rendered exactly once per run. It is byte identical on
every call of that run, which is what makes the run cost what it does: the
provider serves it from cache after the first comment. Nothing that varies per
row may enter it.
"""

import re

from commentdesk.config import ConfigError

# The element the knowledge document is wrapped in. The operator's voice file
# names this tag in the rule that binds every factual claim to the source, so it
# is exposed as a value rather than typed twice.
KNOWLEDGE_TAG = "knowledge"

# Digits belong in the class. The pattern this replaced was [a-z_]+, which
# declined to match an indexed name such as cta_phrase_2: nothing matched, so
# nothing raised, and the rendered prompt kept the literal braces.
PLACEHOLDER = re.compile(r"\{\{([a-z_0-9]+)\}\}")

# Anything still wrapped in double braces once substitution has run. It catches
# the two cases PLACEHOLDER cannot. First, a name the pattern rejects, such as
# an uppercase or spaced one, which would otherwise ship as braces. Second, a
# value that itself expands into a placeholder. The second is not expanded
# again: one level of resolution is the contract, and a config that needs two is
# a mistake worth stopping for rather than a feature.
RESIDUAL = re.compile(r"\{\{[^{}]*\}\}")


def substitute(template: str, mapping: dict[str, str]) -> str:
    """Replace every {{name}} in template, raising on anything left over."""

    def replace(match: re.Match) -> str:
        key = match.group(1)
        if key not in mapping:
            raise ConfigError(
                "unknown placeholder {{"
                + key
                + "}}. known placeholders: "
                + ", ".join(sorted(mapping))
            )
        return str(mapping[key])

    rendered = PLACEHOLDER.sub(replace, template)
    left = RESIDUAL.search(rendered)
    if left is not None:
        raise ConfigError(
            "unresolved placeholder "
            + left.group(0)
            + ". placeholder names are lowercase letters, digits and underscores"
        )
    return rendered


def build_mapping(cfg: dict) -> dict[str, str]:
    """Every placeholder value for one run.

    Pass one runs here. The CTA strings in config.toml are themselves templates:
    an instruction in [cta.direct] carries the purchase link as a placeholder,
    so the table is resolved against the non CTA values before anything else can
    use it. Pass two is the caller substituting the returned mapping into the
    voice and example files.

    The CTA derived keys are exactly the keys missing from pass one, so a CTA
    string that names another CTA string fails here rather than expanding. That
    is deliberate: a cycle in an operator's config should be an error message,
    not a recursion.
    """
    product = cfg.get("product") or {}
    behavior = cfg.get("behavior") or {}
    try:
        base = {
            "product_name": str(product["name"]),
            "product_kind": str(product["kind"]),
            "price_text": str(product["price_text"]),
            "purchase_link": str(product["purchase_link"]),
            "escalation_contact": str(product["escalation_contact"]),
            "max_reply_sentences": str(behavior["max_reply_sentences"]),
            "bot_disclosure_text": str(behavior["bot_disclosure_text"]),
            "knowledge_tag": KNOWLEDGE_TAG,
        }
    except KeyError as exc:
        raise ConfigError(f"missing config value for placeholder: {exc.args[0]}") from exc

    # cta_mode is checked against the config rather than against a set of names
    # in this file. An operator can define as many CTA styles as they like and
    # never open a .py file to do it.
    mode = behavior.get("cta_mode")
    tables = cfg.get("cta") or {}
    table = tables.get(mode) if isinstance(mode, str) else None
    if table is None:
        raise ConfigError(
            f"behavior.cta_mode names no table: {mode}. defined: " + ", ".join(sorted(tables))
        )

    try:
        instruction = substitute(str(table.get("instruction", "")), base)
        phrases = [substitute(str(p), base) for p in table.get("phrases") or []]
    except ConfigError as exc:
        raise ConfigError(
            f"in [cta.{mode}]: {exc}. a CTA string may use only these "
            "placeholders: " + ", ".join(sorted(base))
        ) from exc

    mapping = dict(base)
    mapping["cta_instruction"] = instruction
    # The numbered phrases exist so that different worked examples can close on
    # different wording. A single string repeated across every example teaches
    # the model that string and it then closes most replies with it, measured at
    # 6 of 8 in the project this engine came from. Rendering different phrases
    # into different examples got it to 4 of 8. That is a mitigation and not a
    # fix: the real fix is rotating per row, which cannot happen inside a cached
    # prefix. find_repetition reports what survives, for a person to break up.
    for index, phrase in enumerate(phrases, start=1):
        mapping[f"cta_phrase_{index}"] = phrase
    # One readable list, for the instruction that asks for variety in prose
    # rather than demonstrating it in an example.
    mapping["cta_phrases"] = " / ".join(phrases)
    return mapping
