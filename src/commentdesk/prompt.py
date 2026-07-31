# SPDX-License-Identifier: Apache-2.0
"""Placeholder substitution and prompt assembly.

The system prefix is rendered exactly once per run. It is byte identical on
every call of that run, which is what makes the run cost what it does: the
provider serves it from cache after the first comment. Nothing that varies per
row may enter it.
"""

import re
from pathlib import Path

from commentdesk.config import ConfigError, resolve_path

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


# The wire format, owned by this file and appended after the operator's own.
# It is not a voice choice. parse_response reads exactly this shape, so an
# operator who edited it, even only to translate it, would break every row of
# the run, and the first sign would be an unparseable response on comment one.
# Keeping it out of voice.md and examples.md makes that edit impossible rather
# than merely discouraged. The voice is theirs. The wire format is not.
OUTPUT_CONTRACT = (
    "## Output format\n"
    "\n"
    "Answer with a single JSON object and nothing else. No code fence, no text "
    "before it, no text after it, no second object.\n"
    "\n"
    "Three keys, all of them always present:\n"
    "\n"
    "- decision: one of reply, skip, escalate.\n"
    "- reason: one short sentence explaining the decision.\n"
    "- reply_text: the reply to publish when decision is reply, and an empty "
    "string for skip and for escalate.\n"
    "\n"
    "The shape, not the content:\n"
    "\n"
    '{"decision": "skip", "reason": "...", "reply_text": ""}\n'
)


def render_system_text(cfg: dict, config_dir: Path) -> str:
    """The static prefix: the operator's rules, their worked examples, then the
    output contract, with every placeholder resolved.

    Called once per run. This is the cached prefix, so it must not vary between
    comments, which is also why it takes no row.
    """
    voice = cfg.get("voice") or {}
    rules_rel = voice.get("rules")
    examples_rel = voice.get("examples")
    if not rules_rel or not examples_rel:
        raise ConfigError("voice.rules and voice.examples must both name a file")
    parts = []
    for rel in (rules_rel, examples_rel):
        path = resolve_path(config_dir, rel)
        if not path.is_file():
            raise ConfigError(f"voice file not found: {path}")
        # Stripped, so that a trailing newline one operator's editor adds and
        # another's does not cannot change the spacing between the sections.
        parts.append(path.read_text(encoding="utf-8-sig").strip())
    parts.append(OUTPUT_CONTRACT)
    return substitute("\n\n".join(parts), build_mapping(cfg))


def build_messages(system_text: str, knowledge_text: str, row: dict) -> list[dict]:
    """The rules block, then the whole source document, then the one comment.

    cache_control marks the end of the static prefix. Everything up to that
    point is identical on every call of a run, so the provider serves it from
    cache at a fraction of the input price. Some routes need the marker to do
    it; the rest cache on their own and ignore it, so it is always sent.

    The CTA style is already baked into system_text, so one run uses one style
    for every row regardless of the platform column. Mixed platform input wants
    two runs with two configs rather than one run. Varying it per row is not a
    one line change either: the CTA phrases are woven through the worked
    examples, so it would mean maintaining two rendered prefixes and paying the
    cache miss on whichever one the row did not use.

    The user message below sits after the cache marker. It is billed at full
    input rate on every single call and it is the last thing the model reads
    before it generates, so it stays short, its labels are plain ASCII English,
    and a field with no value contributes no line at all. A label followed by
    nothing is a question the model has to answer for itself, and an invented
    stand in for a missing author is worse: it teaches the model to address
    somebody who is not there.
    """
    system_blocks = [
        {"type": "text", "text": system_text},
        {
            "type": "text",
            "text": f"<{KNOWLEDGE_TAG}>\n{knowledge_text}\n</{KNOWLEDGE_TAG}>",
            "cache_control": {"type": "ephemeral"},
        },
    ]
    parts = []
    platform = str(row.get("platform") or "").strip()
    if platform:
        parts.append(f"Platform: {platform}")
    title = str(row.get("video_title") or "").strip()
    if title:
        parts.append(f"Post title: {title}")
    author = str(row.get("author") or "").strip()
    comment = str(row.get("comment") or "")
    if author:
        parts.append(f"Comment from {author}:\n{comment}")
    else:
        parts.append(f"Comment:\n{comment}")
    return [
        {"role": "system", "content": system_blocks},
        {"role": "user", "content": "\n".join(parts)},
    ]
