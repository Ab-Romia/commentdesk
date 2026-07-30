# SPDX-License-Identifier: Apache-2.0
import pytest

from commentdesk.config import ConfigError
from commentdesk.prompt import KNOWLEDGE_TAG, build_mapping, substitute


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
