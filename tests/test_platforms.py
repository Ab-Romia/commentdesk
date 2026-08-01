# SPDX-License-Identifier: Apache-2.0
"""The connector registry, in the same shape as the knowledge source registry.

Nothing here is a connector. These tests pin the interface a connector has to
implement and the errors an operator sees when their config names one that is
not there, because both were decided before the first connector was written and
a connector written first would have decided them by accident.
"""

import pytest

from commentdraft.platforms import (
    PLATFORMS,
    Platform,
    PlatformError,
    get_platform,
    publish_target,
    register,
)


@pytest.fixture
def registry_snapshot():
    """Restore PLATFORMS after a test that registers into it."""
    saved = dict(PLATFORMS)
    yield PLATFORMS
    PLATFORMS.clear()
    PLATFORMS.update(saved)


class Recorder:
    """A connector that records what it was asked to do and reaches nothing.

    Every test in the suite that needs a platform uses one of these. There is no
    other kind available, which is what keeps the suite offline.
    """

    calls: list[tuple]

    def __init__(self) -> None:
        self.calls = []

    def fetch_comments(self, config: dict, since: str) -> list[dict]:
        self.calls.append(("fetch_comments", since))
        return []

    def publish_reply(self, config: dict, parent_id: str, text: str) -> str:
        self.calls.append(("publish_reply", parent_id, text))
        return "assigned-" + parent_id


def test_register_adds_a_connector_and_returns_it_unchanged(registry_snapshot):
    assert register("fixture_platform")(Recorder) is Recorder
    assert registry_snapshot["fixture_platform"] is Recorder


def test_register_refuses_to_shadow_an_existing_name(registry_snapshot):
    register("fixture_platform")(Recorder)
    with pytest.raises(PlatformError):
        register("fixture_platform")(Recorder)


def test_get_platform_returns_an_instance_of_the_registered_connector(registry_snapshot):
    register("fixture_platform")(Recorder)
    connector = get_platform("fixture_platform")
    assert isinstance(connector, Recorder)
    assert isinstance(connector, Platform)


def test_an_unknown_platform_names_what_is_registered(registry_snapshot):
    register("fixture_platform")(Recorder)
    with pytest.raises(PlatformError) as exc:
        get_platform("not_a_platform")
    message = str(exc.value)
    assert "not_a_platform" in message
    assert "fixture_platform" in message


def test_an_empty_registry_says_none_rather_than_an_empty_list(registry_snapshot):
    """An operator reading "registered: " with nothing after it learns nothing."""
    registry_snapshot.clear()
    with pytest.raises(PlatformError) as exc:
        get_platform("anything")
    assert "none" in str(exc.value)


def test_a_connector_missing_half_the_interface_is_refused_by_name(registry_snapshot):
    """A read only connector is a legitimate thing to want and this is not how to
    build one: a class that simply omits publish_reply would fail at the moment of
    the send, which is the worst possible time to find out."""

    class ReadOnly:
        def fetch_comments(self, config: dict, since: str) -> list[dict]:
            return []

    register("half_a_platform")(ReadOnly)
    with pytest.raises(PlatformError) as exc:
        get_platform("half_a_platform")
    assert "half_a_platform" in str(exc.value)


PUBLISH_SECTION = {"platform": "fixture_platform", "credential_env": "CD_PUBLISH_TOKEN"}


def test_publish_target_returns_the_platform_and_the_credential_variable():
    assert publish_target({"publish": dict(PUBLISH_SECTION)}) == (
        "fixture_platform",
        "CD_PUBLISH_TOKEN",
    )


def test_a_config_with_no_publish_section_is_refused_with_a_sentence():
    """The recommended starting point is a config that cannot publish at all, so
    this is the message most operators of this subcommand will ever see. It has to
    read as a description of their setup rather than as a fault."""
    with pytest.raises(PlatformError) as exc:
        publish_target({"product": {"name": "anything"}})
    message = str(exc.value)
    assert "publish" in message
    assert "KeyError" not in message


@pytest.mark.parametrize("missing", ["platform", "credential_env"])
def test_a_half_written_publish_section_names_the_missing_key(missing):
    section = dict(PUBLISH_SECTION)
    del section[missing]
    with pytest.raises(PlatformError) as exc:
        publish_target({"publish": section})
    assert missing in str(exc.value)


@pytest.mark.parametrize("key", ["platform", "credential_env"])
@pytest.mark.parametrize("value", [42, "", "   ", True, ["a"]])
def test_a_publish_key_of_the_wrong_type_is_refused_rather_than_coerced(key, value):
    """The same rule config.py applies to every other value an operator types: a
    number where the file's own syntax has a string is a mistake, and str() on it
    produces a plausible looking platform name that matches nothing."""
    section = dict(PUBLISH_SECTION)
    section[key] = value
    with pytest.raises(PlatformError) as exc:
        publish_target({"publish": section})
    assert key in str(exc.value)


def test_a_publish_section_that_is_not_a_table_is_refused():
    with pytest.raises(PlatformError) as exc:
        publish_target({"publish": "fixture_platform"})
    assert "publish" in str(exc.value)
