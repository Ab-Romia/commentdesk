# SPDX-License-Identifier: Apache-2.0
"""config.py checks the shape of a config and refuses to judge its contents."""

import os
from pathlib import Path

import pytest

from commentdesk.config import (
    ConfigError,
    load_config,
    load_env,
    model_options,
    resolve_path,
    with_reasoning,
)
from conftest import MINIMAL_CONFIG_TOML


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")
    return path


def drop_key(text: str, key: str) -> str:
    """Delete the first `key = ...` line. Keys are written at column zero."""
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.startswith(f"{key} ="):
            del lines[index]
            return "".join(lines)
    raise AssertionError(f"{key} is not in the fixture config")


def set_key(text: str, key: str, literal: str) -> str:
    """Replace the first `key = ...` line with `key = <literal>`."""
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.startswith(f"{key} ="):
            lines[index] = f"{key} = {literal}\n"
            return "".join(lines)
    raise AssertionError(f"{key} is not in the fixture config")


def drop_section(text: str, header: str) -> str:
    """Delete a `[section]` header and every line up to the next header."""
    lines = text.splitlines(keepends=True)
    start = next(i for i, line in enumerate(lines) if line.startswith(header))
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith("[")),
        len(lines),
    )
    del lines[start:end]
    return "".join(lines)


# --- shape ------------------------------------------------------------------


def test_load_config_accepts_a_complete_config(config_file: Path) -> None:
    cfg = load_config(config_file)
    assert cfg["product"]["kind"] == "field guide"
    assert cfg["behavior"]["cta_mode"] in cfg["cta"]
    assert cfg["model"]["base_url"].startswith("https://")
    # .get twice over: the bake-off section is optional and deleting it is a
    # documented action, which must not turn into a KeyError inside a test.
    assert len(cfg.get("bakeoff", {}).get("models", [])) == 1


def test_load_config_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "no-such-file.toml")


def test_load_config_invalid_toml(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="invalid TOML"):
        load_config(write(tmp_path, "[product\nname = \n"))


@pytest.mark.parametrize("header", ["[product]", "[knowledge]", "[voice]", "[behavior]"])
def test_load_config_rejects_a_missing_section(tmp_path: Path, header: str) -> None:
    text = drop_section(MINIMAL_CONFIG_TOML, header)
    with pytest.raises(ConfigError, match=header.strip("[]")):
        load_config(write(tmp_path, text))


@pytest.mark.parametrize(
    "key",
    [
        "name",
        "kind",
        "price_text",
        "purchase_link",
        "escalation_contact",
        "source",
        "path",
        "rules",
        "examples",
        "base_url",
        "api_key_env",
        "cta_mode",
        "plug_cap",
        "max_reply_sentences",
    ],
)
def test_load_config_rejects_a_missing_key(tmp_path: Path, key: str) -> None:
    text = drop_key(MINIMAL_CONFIG_TOML, key)
    with pytest.raises(ConfigError, match=key):
        load_config(write(tmp_path, text))


def test_load_config_defaults_the_optional_model_tables(tmp_path: Path) -> None:
    """Downstream reads cfg["model"]["params"] unconditionally, so it must exist."""
    text = drop_section(MINIMAL_CONFIG_TOML, "[model.params]")
    text = drop_section(text, "[model.pricing]")
    cfg = load_config(write(tmp_path, text))
    assert cfg["model"]["params"] == {}
    assert cfg["model"]["pricing"] == {}


def test_load_config_does_not_judge_the_contents(tmp_path: Path) -> None:
    """A wrong price and a dead link are the reviewer's job, not the loader's.

    Nothing here can tell a right price from a wrong one. Rejecting a price that
    looks odd would make the tool feel checked when it is not.
    """
    text = set_key(MINIMAL_CONFIG_TOML, "price_text", '"free forever"')
    text = set_key(text, "purchase_link", '"not-a-url"')
    cfg = load_config(write(tmp_path, text))
    assert cfg["product"]["price_text"] == "free forever"
    assert cfg["product"]["purchase_link"] == "not-a-url"


# --- plug_cap ---------------------------------------------------------------


@pytest.mark.parametrize("literal", ["-0.1", "1.5", '"most"'])
def test_plug_cap_must_be_between_zero_and_one(tmp_path: Path, literal: str) -> None:
    text = set_key(MINIMAL_CONFIG_TOML, "plug_cap", literal)
    with pytest.raises(ConfigError, match="plug_cap"):
        load_config(write(tmp_path, text))


@pytest.mark.parametrize("literal", ["0", "1", "0.75"])
def test_plug_cap_accepts_the_whole_range(tmp_path: Path, literal: str) -> None:
    text = set_key(MINIMAL_CONFIG_TOML, "plug_cap", literal)
    assert float(load_config(write(tmp_path, text))["behavior"]["plug_cap"]) == float(literal)


# --- resolve_path -----------------------------------------------------------


def test_resolve_path_is_relative_to_the_config_not_the_shell(tmp_path: Path) -> None:
    """`commentdesk run --config examples/x/config.toml` has to work from anywhere."""
    config_dir = tmp_path / "examples" / "field-guide"
    config_dir.mkdir(parents=True)
    assert resolve_path(config_dir, "knowledge.md") == config_dir / "knowledge.md"
    assert resolve_path(config_dir, "prompts/voice.md") == config_dir / "prompts" / "voice.md"


def test_resolve_path_ignores_the_working_directory(tmp_path: Path, monkeypatch) -> None:
    config_dir = tmp_path / "cfg"
    config_dir.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert resolve_path(config_dir, "knowledge.md") == config_dir / "knowledge.md"


def test_resolve_path_honours_an_absolute_path(tmp_path: Path) -> None:
    absolute = tmp_path / "shared" / "knowledge.md"
    assert resolve_path(tmp_path / "cfg", str(absolute)) == absolute


def test_resolve_path_normalises_a_parent_reference(tmp_path: Path) -> None:
    config_dir = tmp_path / "cfg" / "nested"
    config_dir.mkdir(parents=True)
    assert (
        resolve_path(config_dir, "../shared/knowledge.md")
        == tmp_path / "cfg" / "shared" / "knowledge.md"
    )


# --- model_options ----------------------------------------------------------


def test_model_options_offers_every_model_and_inherits_only_the_gateway(
    config_file: Path,
) -> None:
    """A bake-off entry that omits pricing must not inherit the default's rates.

    A comparison between models is exactly where a wrong price does the most
    damage, so a missing rate has to show up as a blank cost column instead.
    """
    cfg = load_config(config_file)
    options = model_options(cfg)

    assert set(options) == {"primary", "challenger"}
    challenger = options["challenger"]
    assert challenger["base_url"] == cfg["model"]["base_url"]
    assert challenger["api_key_env"] == cfg["model"]["api_key_env"]
    assert challenger["model"] == "vendor/model-b"
    assert challenger["pricing"] == cfg["bakeoff"]["models"][0]["pricing"]
    assert "label" in challenger


def test_model_options_gives_no_pricing_to_an_entry_that_declares_none(
    tmp_path: Path,
) -> None:
    text = MINIMAL_CONFIG_TOML.replace(
        "pricing = { input_per_mtok = 0.09, cached_per_mtok = 0.018, output_per_mtok = 0.18, cache_write_per_mtok = 0.0 }\n",
        "",
    )
    cfg = load_config(write(tmp_path, text))
    options = model_options(cfg)
    assert "pricing" not in options["challenger"]


def test_model_options_skips_an_unlabelled_entry(config_file: Path) -> None:
    """Every consumer keys on the label, so an entry without one has no name."""
    cfg = load_config(config_file)
    cfg["bakeoff"]["models"].append({"model": "vendor/model-c"})
    assert set(model_options(cfg)) == {"primary", "challenger"}


def test_model_options_tolerates_a_config_with_no_bakeoff(tmp_path: Path) -> None:
    text = drop_section(MINIMAL_CONFIG_TOML, "[[bakeoff.models]]")
    cfg = load_config(write(tmp_path, text))
    assert set(model_options(cfg)) == {"primary"}


# --- with_reasoning ---------------------------------------------------------


def test_with_reasoning_sets_the_switch_the_gateway_actually_reads() -> None:
    """The provider-native flag is passed through untranslated on some routes.

    The gateway's own `reasoning` key is the one that takes effect, so both are
    written when reasoning is off and only the effective one when it is on.
    """
    base = {
        "model": "vendor/model-a",
        "params": {"enable_thinking": False, "provider": {"data_collection": "deny"}},
    }

    off = with_reasoning(base, False)
    assert off["params"]["reasoning"] == {"enabled": False}
    assert off["params"]["enable_thinking"] is False

    on = with_reasoning(base, True)
    assert on["params"]["reasoning"] == {"enabled": True}
    # Leaving the native flag set would contradict the switch that works.
    assert "enable_thinking" not in on["params"]


def test_with_reasoning_never_mutates_its_input() -> None:
    """One model config is reused across every request the local UI serves."""
    base = {"model": "vendor/model-a", "params": {"provider": {"data_collection": "deny"}}}
    result = with_reasoning(base, True)
    assert "reasoning" not in base["params"]
    assert result["params"]["provider"] == {"data_collection": "deny"}


def test_with_reasoning_works_on_a_config_with_no_params() -> None:
    result = with_reasoning({"model": "vendor/model-a"}, False)
    assert result["params"] == {"reasoning": {"enabled": False}, "enable_thinking": False}


# --- load_env ---------------------------------------------------------------


def test_load_env_does_not_overwrite_an_exported_variable(tmp_path: Path, monkeypatch) -> None:
    """A key exported in the shell wins over the file.

    That is how a run is pointed at a different key without editing the file
    holding the real one.
    """
    monkeypatch.setenv("COMMENTDESK_TEST_KEY", "from-the-shell")
    env = tmp_path / ".env"
    env.write_text("COMMENTDESK_TEST_KEY=from-the-file\n", encoding="utf-8")
    load_env(env)
    assert os.environ["COMMENTDESK_TEST_KEY"] == "from-the-shell"


def test_load_env_reads_a_key_the_shell_does_not_have(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("COMMENTDESK_OTHER_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text(
        "# a comment\n\n  COMMENTDESK_OTHER_KEY = from-the-file  \nnot-an-assignment\n",
        encoding="utf-8",
    )
    load_env(env)
    assert os.environ["COMMENTDESK_OTHER_KEY"] == "from-the-file"
    monkeypatch.delenv("COMMENTDESK_OTHER_KEY")


def test_load_env_on_a_missing_file_is_a_no_op(tmp_path: Path) -> None:
    """Keys may come from the shell alone, so an absent file is normal."""
    before = dict(os.environ)
    load_env(tmp_path / "nothing-here")
    assert dict(os.environ) == before


def test_load_env_keeps_an_equals_sign_inside_the_value(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("COMMENTDESK_PADDED_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text("COMMENTDESK_PADDED_KEY=abc=def==\n", encoding="utf-8")
    load_env(env)
    assert os.environ["COMMENTDESK_PADDED_KEY"] == "abc=def=="
    monkeypatch.delenv("COMMENTDESK_PADDED_KEY")


# --- cta_mode ---------------------------------------------------------------


def test_cta_mode_must_name_a_defined_table(tmp_path: Path) -> None:
    text = set_key(MINIMAL_CONFIG_TOML, "cta_mode", '"shouty"')
    with pytest.raises(ConfigError) as caught:
        load_config(write(tmp_path, text))
    message = str(caught.value)
    assert "shouty" in message
    # The error is only useful if it says what the operator may write instead.
    assert "bio_pointer" in message
    assert "direct" in message


def test_cta_mode_error_survives_a_config_with_no_cta_tables(tmp_path: Path) -> None:
    text = drop_section(MINIMAL_CONFIG_TOML, "[cta.direct]")
    text = drop_section(text, "[cta.bio_pointer]")
    with pytest.raises(ConfigError, match="cta"):
        load_config(write(tmp_path, text))


def test_cta_mode_must_be_a_string(tmp_path: Path) -> None:
    """A list here would blow up on a dict lookup rather than on a config error."""
    text = set_key(MINIMAL_CONFIG_TOML, "cta_mode", '["direct"]')
    with pytest.raises(ConfigError, match="cta_mode"):
        load_config(write(tmp_path, text))


def test_selected_cta_table_needs_an_instruction_and_phrases(tmp_path: Path) -> None:
    text = drop_key(MINIMAL_CONFIG_TOML, "instruction")
    with pytest.raises(ConfigError, match=r"cta\.direct\.instruction"):
        load_config(write(tmp_path, text))


def test_selected_cta_phrases_must_be_a_non_empty_list(tmp_path: Path) -> None:
    text = set_key(MINIMAL_CONFIG_TOML, "phrases", "[]")
    with pytest.raises(ConfigError, match=r"cta\.direct\.phrases"):
        load_config(write(tmp_path, text))


def test_unselected_cta_table_is_not_validated(tmp_path: Path) -> None:
    """Only the selected mode is rendered, so only it has to be complete.

    An operator drafting a second CTA style must not be blocked by it.
    """
    text = MINIMAL_CONFIG_TOML.replace(
        '[cta.bio_pointer]\ninstruction = "If someone asks where to get it, say the link is in the bio."\n',
        "[cta.bio_pointer]\n",
    )
    cfg = load_config(write(tmp_path, text))
    assert "instruction" not in cfg["cta"]["bio_pointer"]


# --- plug_markers -----------------------------------------------------------


def test_plug_markers_is_required(tmp_path: Path) -> None:
    text = drop_key(MINIMAL_CONFIG_TOML, "plug_markers")
    with pytest.raises(ConfigError, match="plug_markers"):
        load_config(write(tmp_path, text))


@pytest.mark.parametrize("literal", ["[]", '""', '"in the bio"', '["in the bio", ""]', "[3]"])
def test_plug_markers_must_be_a_non_empty_list_of_non_empty_strings(
    tmp_path: Path, literal: str
) -> None:
    """The silent-zero-plugs state has to be unreachable, not merely unlikely.

    With no usable markers is_plug answers False for every reply, the report
    prints a plug count of zero, and plug_cap can never fire. Nothing errors, and
    the output is indistinguishable from a clean run.
    """
    text = set_key(MINIMAL_CONFIG_TOML, "plug_markers", literal)
    with pytest.raises(ConfigError, match="plug_markers"):
        load_config(write(tmp_path, text))


# --- bot_disclosure_text ----------------------------------------------------


@pytest.mark.parametrize("literal", ['""', '"   "', "false"])
def test_bot_disclosure_text_must_be_a_non_empty_string(tmp_path: Path, literal: str) -> None:
    text = set_key(MINIMAL_CONFIG_TOML, "bot_disclosure_text", literal)
    with pytest.raises(ConfigError, match="bot_disclosure_text"):
        load_config(write(tmp_path, text))


def test_bot_disclosure_text_is_required(tmp_path: Path) -> None:
    text = drop_key(MINIMAL_CONFIG_TOML, "bot_disclosure_text")
    with pytest.raises(ConfigError, match="bot_disclosure_text"):
        load_config(write(tmp_path, text))


def test_bot_disclosure_has_no_off_switch() -> None:
    """There is no mode name to configure, because the evasive mode is gone."""
    from commentdesk import config

    source = Path(config.__file__).read_text(encoding="utf-8")
    assert "deflect" not in source
    assert "bot_disclosure_text" in config.REQUIRED["behavior"]


# --- separator and banned_emoji ---------------------------------------------


def test_separator_is_required_and_non_empty(tmp_path: Path) -> None:
    text = set_key(MINIMAL_CONFIG_TOML, "separator", '""')
    with pytest.raises(ConfigError, match="separator"):
        load_config(write(tmp_path, text))


def test_separator_is_stated_never_guessed(tmp_path: Path) -> None:
    """Any punctuation the operator writes is accepted verbatim.

    The version that inferred a separator from the script of the text defaulted
    every script it could not measure to one language's comma and injected it
    into replies written in languages that have no such mark.
    """
    text = set_key(MINIMAL_CONFIG_TOML, "separator", '" / "')
    cfg = load_config(write(tmp_path, text))
    assert cfg["behavior"]["separator"] == " / "


def test_banned_emoji_is_required_but_may_be_empty(tmp_path: Path) -> None:
    cfg = load_config(write(tmp_path, MINIMAL_CONFIG_TOML))
    assert cfg["behavior"]["banned_emoji"] == ""

    missing = drop_key(MINIMAL_CONFIG_TOML, "banned_emoji")
    with pytest.raises(ConfigError, match="banned_emoji"):
        load_config(write(tmp_path, missing))


def test_banned_emoji_must_be_a_string(tmp_path: Path) -> None:
    """A list of characters is the natural mistake and it silently bans nothing."""
    text = set_key(MINIMAL_CONFIG_TOML, "banned_emoji", '["a", "b"]')
    with pytest.raises(ConfigError, match="banned_emoji"):
        load_config(write(tmp_path, text))


# --- paths ------------------------------------------------------------------


@pytest.mark.parametrize("key", ["path", "rules", "examples"])
def test_operator_file_paths_must_be_non_empty(tmp_path: Path, key: str) -> None:
    """An empty path resolves to the config directory itself.

    The text source would then concatenate everything sitting next to config.toml
    into the prompt, which is a wrong answer that never raises.
    """
    text = set_key(MINIMAL_CONFIG_TOML, key, '""')
    with pytest.raises(ConfigError, match=key):
        load_config(write(tmp_path, text))
