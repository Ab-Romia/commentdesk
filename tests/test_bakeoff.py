# SPDX-License-Identifier: Apache-2.0
import pytest

from commentdesk.bakeoff import bakeoff_model_cfgs
from commentdesk.config import ConfigError
from commentdesk.report import estimate_cost

USAGE = {
    "prompt_tokens": 1000,
    "completion_tokens": 100,
    "cached_tokens": 900,
    "cache_write_tokens": 0,
}

DEFAULT_MODEL = {
    "label": "default",
    "model": "vendor-a/model-one",
    "base_url": "https://gateway.example/v1",
    "api_key_env": "GATEWAY_KEY",
    "params": {"provider": {"data_collection": "deny"}},
    "pricing": {
        "input_per_mtok": 1.0,
        "cached_per_mtok": 0.1,
        "output_per_mtok": 6.0,
        "cache_write_per_mtok": 1.25,
    },
}


def base_cfg(entries):
    return {"model": dict(DEFAULT_MODEL), "bakeoff": {"models": list(entries)}}


def test_the_default_model_runs_first_and_alone_when_there_are_no_entries():
    cfgs = bakeoff_model_cfgs({"model": dict(DEFAULT_MODEL)})
    assert len(cfgs) == 1
    assert cfgs[0]["model"] == "vendor-a/model-one"


def test_entries_inherit_the_gateway_keys():
    cfgs = bakeoff_model_cfgs(
        base_cfg(
            [
                {
                    "label": "challenger",
                    "model": "vendor-b/model-two",
                    "params": {"provider": {"data_collection": "deny"}},
                },
            ]
        )
    )
    assert [c["label"] for c in cfgs] == ["default", "challenger"]
    assert cfgs[1]["base_url"] == "https://gateway.example/v1"
    assert cfgs[1]["api_key_env"] == "GATEWAY_KEY"


def test_an_entry_may_override_the_gateway_it_inherited():
    cfgs = bakeoff_model_cfgs(
        base_cfg(
            [
                {
                    "label": "challenger",
                    "model": "vendor-b/model-two",
                    "base_url": "https://other.example/v1",
                    "api_key_env": "OTHER_KEY",
                    "params": {"provider": {"data_collection": "deny"}},
                },
            ]
        )
    )
    assert cfgs[1]["base_url"] == "https://other.example/v1"
    assert cfgs[1]["api_key_env"] == "OTHER_KEY"


def test_an_entry_without_pricing_gets_a_blank_cost_not_the_default_rates():
    # The bug this whole rule exists to prevent. Inheriting the [model] block
    # would price the challenger at the default's rates and the comparison, which
    # is the only reason to run a bake-off at all, would be quietly wrong.
    cfgs = bakeoff_model_cfgs(
        base_cfg(
            [
                {
                    "label": "challenger",
                    "model": "vendor-b/model-two",
                    "params": {"provider": {"data_collection": "deny"}},
                },
            ]
        )
    )
    assert "pricing" not in cfgs[1]
    assert estimate_cost(USAGE, cfgs[0]) is not None
    assert estimate_cost(USAGE, cfgs[1]) is None


def test_an_entry_keeps_its_own_pricing():
    cfgs = bakeoff_model_cfgs(
        base_cfg(
            [
                {
                    "label": "challenger",
                    "model": "vendor-b/model-two",
                    "params": {"provider": {"data_collection": "deny"}},
                    "pricing": {
                        "input_per_mtok": 2.0,
                        "cached_per_mtok": 0.2,
                        "output_per_mtok": 8.0,
                    },
                },
            ]
        )
    )
    assert estimate_cost(USAGE, cfgs[1]) == pytest.approx((100 * 2.0 + 900 * 0.2 + 100 * 8.0) / 1e6)


def test_an_entry_missing_params_is_rejected_by_label():
    # params is required, not optional. An entry with no params block is exactly
    # the entry that would ship with data collection left at the default.
    with pytest.raises(ConfigError) as caught:
        bakeoff_model_cfgs(
            base_cfg(
                [
                    {"label": "challenger", "model": "vendor-b/model-two"},
                ]
            )
        )
    assert "challenger" in str(caught.value)
    assert "params" in str(caught.value)


def test_an_entry_missing_a_label_is_rejected_by_position():
    with pytest.raises(ConfigError) as caught:
        bakeoff_model_cfgs(
            base_cfg(
                [
                    {
                        "label": "challenger",
                        "model": "vendor-b/model-two",
                        "params": {"provider": {"data_collection": "deny"}},
                    },
                    {
                        "model": "vendor-c/model-three",
                        "params": {"provider": {"data_collection": "deny"}},
                    },
                ]
            )
        )
    assert "entry 2" in str(caught.value)
    assert "label" in str(caught.value)


def test_an_entry_that_allows_data_collection_is_rejected():
    with pytest.raises(ConfigError) as caught:
        bakeoff_model_cfgs(
            base_cfg(
                [
                    {
                        "label": "challenger",
                        "model": "vendor-b/model-two",
                        "params": {"provider": {"data_collection": "allow"}},
                    },
                ]
            )
        )
    assert "challenger" in str(caught.value)
    assert "data_collection" in str(caught.value)


def test_data_collection_at_the_top_level_of_params_is_not_enough():
    # The gateway accepts a top level key, ignores it, and defaults to allow.
    # Only the nested form is read, so only the nested form counts.
    with pytest.raises(ConfigError):
        bakeoff_model_cfgs(
            base_cfg(
                [
                    {
                        "label": "challenger",
                        "model": "vendor-b/model-two",
                        "params": {"data_collection": "deny"},
                    },
                ]
            )
        )


def test_an_entry_with_no_provider_table_is_rejected():
    with pytest.raises(ConfigError) as caught:
        bakeoff_model_cfgs(
            base_cfg(
                [
                    {
                        "label": "challenger",
                        "model": "vendor-b/model-two",
                        "params": {"temperature": 0},
                    },
                ]
            )
        )
    assert "data_collection" in str(caught.value)


def test_validation_does_not_mutate_the_config():
    cfg = base_cfg(
        [
            {
                "label": "challenger",
                "model": "vendor-b/model-two",
                "params": {"provider": {"data_collection": "deny"}},
            }
        ]
    )
    bakeoff_model_cfgs(cfg)
    assert cfg["bakeoff"]["models"][0] == {
        "label": "challenger",
        "model": "vendor-b/model-two",
        "params": {"provider": {"data_collection": "deny"}},
    }
