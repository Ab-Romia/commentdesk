# SPDX-License-Identifier: Apache-2.0
import pytest

from commentdesk.config import ConfigError
from commentdesk.prompt import (
    KNOWLEDGE_TAG,
    OUTPUT_CONTRACT,
    build_mapping,
    build_messages,
    render_system_text,
    substitute,
)


def sample_cfg():
    """A complete config in the shape load_config returns, for one fictional product."""
    return {
        "product": {
            "name": "The Backyard Forager's Field Guide",
            "kind": "book",
            "price_text": "$18",
            "purchase_link": "https://example.com/field-guide",
            "escalation_contact": "the team",
        },
        "behavior": {
            "cta_mode": "direct",
            "max_reply_sentences": 2,
            "bot_disclosure_text": (
                "Replies are drafted with software and reviewed by a person before they post."
            ),
        },
        "cta": {
            "direct": {
                "instruction": (
                    "If someone asks where to get it, give the link: {{purchase_link}}."
                ),
                "phrases": [
                    "here is the link: {{purchase_link}}",
                    "you can get it at {{purchase_link}}",
                    "{{purchase_link}}",
                ],
            },
            "bio_pointer": {
                "instruction": (
                    "If someone asks where to get it, say the link is in the "
                    "bio. Do not write the address."
                ),
                "phrases": [
                    "the link is in the bio",
                    "you will find it in the profile",
                ],
            },
        },
    }


def test_substitute_fills_known_placeholders():
    out = substitute(
        "Get {{product_name}} for {{price_text}}.",
        {"product_name": "Field Guide", "price_text": "$18"},
    )
    assert out == "Get Field Guide for $18."


def test_substitute_matches_an_indexed_placeholder():
    """The pattern this replaced was [a-z_]+, which did not match a name with a
    digit in it. It substituted nothing and raised nothing, so the run shipped
    with literal braces in the prompt."""
    out = substitute("Close with {{cta_phrase_2}}.", {"cta_phrase_2": "it is in the bio"})
    assert out == "Close with it is in the bio."


def test_substitute_indexed_placeholder_with_no_value_is_an_error():
    with pytest.raises(ConfigError) as exc:
        substitute("Close with {{cta_phrase_9}}.", {"cta_phrase_1": "here"})
    assert "cta_phrase_9" in str(exc.value)


def test_substitute_unknown_placeholder_is_an_error():
    with pytest.raises(ConfigError) as exc:
        substitute("Hello {{nope}}.", {"product_name": "Field Guide"})
    assert "nope" in str(exc.value)


def test_substitute_rejects_a_name_the_pattern_cannot_match():
    """An uppercase or spaced name is not replaced by the pattern at all, so
    without the residual check it would ship as braces instead of failing."""
    with pytest.raises(ConfigError) as exc:
        substitute("Hello {{Product_Name}}.", {"product_name": "Field Guide"})
    assert "Product_Name" in str(exc.value)


def test_substitute_leaves_single_braces_alone():
    """The output contract appended to every prompt is JSON. Single braces are
    not placeholders and must survive untouched."""
    out = substitute('{"decision": "skip", "reply_text": ""}', {})
    assert out == '{"decision": "skip", "reply_text": ""}'


def test_build_mapping_resolves_product_values_inside_the_cta_table():
    mapping = build_mapping(sample_cfg())
    assert mapping["cta_instruction"] == (
        "If someone asks where to get it, give the link: https://example.com/field-guide."
    )
    assert mapping["cta_phrase_1"] == ("here is the link: https://example.com/field-guide")
    assert mapping["cta_phrase_3"] == "https://example.com/field-guide"


def test_build_mapping_renders_the_phrase_list_for_the_vary_it_instruction():
    mapping = build_mapping(sample_cfg())
    assert mapping["cta_phrases"] == (
        "here is the link: https://example.com/field-guide / "
        "you can get it at https://example.com/field-guide / "
        "https://example.com/field-guide"
    )


def test_build_mapping_selects_the_table_named_by_cta_mode():
    cfg = sample_cfg()
    cfg["behavior"]["cta_mode"] = "bio_pointer"
    mapping = build_mapping(cfg)
    assert mapping["cta_phrase_1"] == "the link is in the bio"
    assert mapping["cta_phrase_2"] == "you will find it in the profile"
    assert "cta_phrase_3" not in mapping


def test_build_mapping_unknown_cta_mode_names_the_tables_that_exist():
    cfg = sample_cfg()
    cfg["behavior"]["cta_mode"] = "carrier_pigeon"
    with pytest.raises(ConfigError) as exc:
        build_mapping(cfg)
    message = str(exc.value)
    assert "carrier_pigeon" in message
    assert "direct" in message
    assert "bio_pointer" in message


def test_build_mapping_rejects_a_value_that_expands_into_a_placeholder():
    """Recursion is rejected, not performed. A purchase link carrying its own
    placeholder resolves to something the second pass would have to expand
    again, and one level of resolution is the whole contract."""
    cfg = sample_cfg()
    cfg["product"]["purchase_link"] = "https://example.com/{{product_kind}}"
    with pytest.raises(ConfigError) as exc:
        build_mapping(cfg)
    assert "product_kind" in str(exc.value)


def test_build_mapping_rejects_a_cta_string_referencing_another_cta_value():
    cfg = sample_cfg()
    cfg["cta"]["direct"]["instruction"] = "Vary it: {{cta_phrases}}."
    with pytest.raises(ConfigError) as exc:
        build_mapping(cfg)
    message = str(exc.value)
    assert "cta_phrases" in message
    assert "cta.direct" in message


def test_build_mapping_carries_the_product_values_and_the_knowledge_tag():
    mapping = build_mapping(sample_cfg())
    assert mapping["product_name"] == "The Backyard Forager's Field Guide"
    assert mapping["product_kind"] == "book"
    assert mapping["price_text"] == "$18"
    assert mapping["escalation_contact"] == "the team"
    assert mapping["max_reply_sentences"] == "2"
    assert mapping["bot_disclosure_text"].startswith("Replies are drafted")
    assert mapping["knowledge_tag"] == KNOWLEDGE_TAG


def test_build_mapping_missing_config_value_names_the_key():
    cfg = sample_cfg()
    del cfg["product"]["price_text"]
    with pytest.raises(ConfigError) as exc:
        build_mapping(cfg)
    assert "price_text" in str(exc.value)


def voice_cfg(tmp_path, rules, examples):
    """Write a voice and an examples file, and return a config pointing at them.

    The paths in the config are relative, exactly as an operator writes them.
    Only resolve_path knows they are relative to the directory holding
    config.toml.
    """
    prompts = tmp_path / "prompts"
    prompts.mkdir(exist_ok=True)
    (prompts / "voice.md").write_text(rules, encoding="utf-8")
    (prompts / "examples.md").write_text(examples, encoding="utf-8")
    return {
        "product": {
            "name": "The Backyard Forager's Field Guide",
            "kind": "book",
            "price_text": "$18",
            "purchase_link": "https://example.com/field-guide",
            "escalation_contact": "the team",
        },
        "behavior": {
            "cta_mode": "direct",
            "max_reply_sentences": 2,
            "bot_disclosure_text": (
                "Replies are drafted with software and reviewed by a person before they post."
            ),
        },
        "voice": {
            "rules": "prompts/voice.md",
            "examples": "prompts/examples.md",
        },
        "cta": {
            "direct": {
                "instruction": (
                    "If someone asks where to get it, give the link: {{purchase_link}}."
                ),
                "phrases": [
                    "here is the link: {{purchase_link}}",
                    "you can get it at {{purchase_link}}",
                ],
            },
        },
    }


def test_render_system_text_orders_voice_then_examples_then_contract(tmp_path):
    cfg = voice_cfg(
        tmp_path,
        "RULES: never exceed {{max_reply_sentences}} sentences.",
        "EXAMPLES: close with {{cta_phrase_1}}.",
    )
    out = render_system_text(cfg, tmp_path)
    assert out.index("RULES") < out.index("EXAMPLES") < out.index(OUTPUT_CONTRACT)
    assert "never exceed 2 sentences" in out
    assert "close with here is the link: https://example.com/field-guide" in out
    assert "{{" not in out


def test_render_system_text_reads_the_files_relative_to_the_config_dir(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    cfg = voice_cfg(project, "RULES about {{product_kind}}.", "EXAMPLES.")
    out = render_system_text(cfg, project)
    assert "RULES about book." in out


def test_render_system_text_missing_voice_file_names_the_path(tmp_path):
    cfg = voice_cfg(tmp_path, "RULES.", "EXAMPLES.")
    (tmp_path / "prompts" / "examples.md").unlink()
    with pytest.raises(ConfigError) as exc:
        render_system_text(cfg, tmp_path)
    assert "examples.md" in str(exc.value)


def test_output_contract_is_ascii_and_states_the_shape():
    OUTPUT_CONTRACT.encode("ascii")  # raises UnicodeEncodeError if it drifts
    for key in ("decision", "reason", "reply_text"):
        assert key in OUTPUT_CONTRACT
    for decision in ("reply", "skip", "escalate"):
        assert decision in OUTPUT_CONTRACT


def test_build_messages_shape_and_cache_marker():
    messages = build_messages(
        "SYSTEM",
        "BODY",
        {
            "platform": "youtube",
            "author": "Dana",
            "comment": "how much is it?",
            "video_title": "Ten wild greens",
        },
    )
    assert [m["role"] for m in messages] == ["system", "user"]
    blocks = messages[0]["content"]
    assert blocks[0] == {"type": "text", "text": "SYSTEM"}
    assert blocks[1]["text"] == "<knowledge>\nBODY\n</knowledge>"
    assert blocks[1]["cache_control"] == {"type": "ephemeral"}
    assert "cache_control" not in blocks[0]
    user = messages[1]["content"]
    assert "Platform: youtube" in user
    assert "Ten wild greens" in user
    assert user.endswith("Comment from Dana:\nhow much is it?")


def test_build_messages_omits_labels_for_fields_that_are_empty():
    """No invented author. A fallback word for the commenter teaches the model
    to address a person who is not there, and these labels are the last thing it
    reads before generating."""
    messages = build_messages(
        "SYSTEM", "BODY", {"platform": "", "author": "", "comment": "great video"}
    )
    user = messages[1]["content"]
    assert user == "Comment:\ngreat video"
    assert "Platform" not in user


def test_build_messages_prefix_is_identical_across_rows():
    """The economics of a run rest on this. If anything per row reached the
    system blocks, every call would pay full uncached input price."""
    first = build_messages(
        "SYSTEM", "BODY", {"platform": "tiktok", "author": "Dana", "comment": "one"}
    )
    second = build_messages(
        "SYSTEM", "BODY", {"platform": "youtube", "author": "Sam", "comment": "two"}
    )
    assert first[0] == second[0]
    assert first[1] != second[1]


def test_knowledge_tag_round_trip(tmp_path):
    """What the voice file points at is what the request actually contains.

    The grounding rule in an operator's voice file names the element wrapping
    the source document. If the tag rendered into the prompt and the tag emitted
    by build_messages ever drift, the rule names an element that is not in the
    request and nothing fails: the model is simply ungrounded for the whole run.
    """
    cfg = voice_cfg(
        tmp_path,
        "State nothing that is not inside <{{knowledge_tag}}>.",
        "EXAMPLES.",
    )
    system_text = render_system_text(cfg, tmp_path)
    messages = build_messages(system_text, "BODY", {"comment": "hi"})
    block = messages[0]["content"][1]["text"]
    assert build_mapping(cfg)["knowledge_tag"] == KNOWLEDGE_TAG
    assert f"<{KNOWLEDGE_TAG}>" in system_text
    assert block.startswith(f"<{KNOWLEDGE_TAG}>\n")
    assert block.endswith(f"\n</{KNOWLEDGE_TAG}>")
