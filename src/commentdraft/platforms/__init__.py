# SPDX-License-Identifier: Apache-2.0
"""Connector registry: the two calls a platform has to answer, and nothing else.

The same shape as commentdraft.sources, deliberately, so that a contributor who
has read one registry has read both: a register decorator, a dict, and a lookup
that names what is registered when it fails.

Two methods, and only two. fetch_comments brings rows in, publish_reply sends one
reply out. They are separate because the credentials and the scopes behind them
are separate on every platform worth connecting to, and a connector that can only
read is a legitimate connector that most operators should run for a while before
they ask anyone for a write scope.

The config is separate in the same way and for the same reason. [source] names
what to read and the variable holding the read credential; [publish] names what
to write and the variable holding the write credential. Reading used to be
spelled out of [publish], which meant a read only deployment could not be written
down at all, and the posture most operators should start in was the one posture
the config had no way to express.

Nothing in this module calls publish_reply. The only caller in the package is
commentdraft.approve, which reaches it once per keystroke a person actually made,
and tests/test_guarantees.py walks the AST of every module to keep that true.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable


class PlatformError(Exception):
    """A platform name that is not registered, or a [publish] table that is not usable."""


class PlatformHalt(BaseException):
    """A write happened, could not be proved, and the rest of the queue must stop.

    BaseException on purpose, and this is the one deliberate piece of rudeness in
    the whole package.

    commentdraft.approve wraps the send in `except Exception` so that one refused
    row does not lose the rest of the queue. That is right for every ordinary
    failure and exactly wrong for this one: a write path that damages the thing it
    was pointed at will damage the next one too, and continuing means doing it
    again while printing a line nobody reads until later. So this class sits
    outside the hierarchy that handler catches, and the gate re-raises it by name
    after it has written down what was published.

    published_id is the whole reason this lives in the registry rather than in one
    connector. A halt is raised when a write is live and unproved, so there is an
    id, or a suspicion of one, and it is the only thing that lets an operator
    answer "what did my account post". The gate writes it into the audit file
    marked unverified before the run ends. Empty is allowed and means the
    connector could not get an id at all, which is itself worth recording.
    """

    def __init__(self, message: str, published_id: str = "") -> None:
        super().__init__(message)
        self.published_id = published_id


# The attribute a connector may hang on any exception to say "this failure left a
# live write behind, and here is what it is called". PlatformHalt always carries
# one. An ordinary per-row error may carry one too, for the case where the queue
# can safely continue and yet something is already published: the gate reads this
# name off whatever was raised and writes the audit line either way.
PUBLISHED_ID = "published_id"


# The class attribute a connector uses to declare the [publish] keys it reads
# beyond the two every connector has. Without it a connector's own keys are
# invisible to the vocabulary freeze in tests/test_guarantees.py, which then
# passes over them without seeing them: `publish.page_id` was shipped and
# documented for a whole release while the test that freezes the config format
# had no way to know it existed.
DECLARED_KEYS = "PUBLISH_KEYS"

# The same convention for the reading table, because the same hole opens the
# moment a connector reads a key out of it. One attribute per table rather than
# one attribute carrying both: a connector may well name the account differently
# on each side, and a single list could not say which table a key belonged to.
DECLARED_SOURCE_KEYS = "SOURCE_KEYS"


@runtime_checkable
class Platform(Protocol):
    """What a connector implements. Kept minimal on purpose.

    fetch_comments returns rows in engine.IN_FIELDS shape, so that whatever a
    connector pulls in is the same thing read_comments produces from a CSV and the
    rest of the pipeline never learns where a row came from. Exactly that shape,
    not a superset: `commentdraft pull` writes those rows straight into the CSV
    `commentdraft run` reads, and a sixth key would be a column nothing downstream
    has a meaning for. `since` is an opaque marker the connector itself defines,
    which the caller stores and hands back and never reads.

    publish_reply sends one reply under one parent and returns the id the platform
    assigned to it. That returned id is the whole point: it is what an operator
    needs to answer a complaint about something their own account posted.
    """

    def fetch_comments(self, config: dict, since: str) -> list[dict]: ...

    def publish_reply(self, config: dict, parent_id: str, text: str) -> str: ...


PLATFORMS: dict[str, type] = {}

# The table an operator writes to turn publishing on, and the two keys in it.
# Absent by default: a config with no [publish] table is a read only deployment,
# which is the recommended starting point and has to stay a real one.
PUBLISH_SECTION = "publish"
PLATFORM_KEY = "platform"
CREDENTIAL_KEY = "credential_env"

# The table an operator writes to turn reading on. The same two keys, and a
# separate table on purpose: reading and writing are separate scopes on every
# platform worth connecting to, they are granted weeks apart, and a config
# holding only this one is the read only deployment most operators should start
# with. Reading used to be spelled out of [publish], which made a read only
# deployment impossible to write down: pulling a comment required naming a write
# credential that nobody had been granted yet.
SOURCE_SECTION = "source"


def register(name: str) -> Callable[[type], type]:
    """Bind a connector class to the name operators write in [publish].platform."""

    def decorator(connector: type) -> type:
        if name in PLATFORMS:
            # Two connectors under one name means the operator reaches whichever
            # module happened to import last. That depends on import order rather
            # than on anything they wrote, so refuse instead.
            raise PlatformError(f"platform already registered: {name}")
        PLATFORMS[name] = connector
        return connector

    return decorator


def find_platform(name: str) -> type:
    """The connector class registered under `name`, or a PlatformError naming what is.

    Lookup is separate from construction because a caller has refusals to make
    between the two. `commentdraft publish` needs to say "unknown platform" before
    it asks about a credential, and it must not run a connector's constructor
    before it knows there is a credential, a queue and a person at the terminal.
    Nothing here builds anything, so a name can be checked for free.
    """
    connector = PLATFORMS.get(name)
    if connector is None:
        registered = ", ".join(sorted(PLATFORMS)) or "none"
        raise PlatformError(f"unknown platform: {name}. registered: {registered}")
    return connector


def get_platform(name: str) -> Platform:
    """The connector registered under `name`, built, or a PlatformError naming what is.

    The interface check happens here rather than in register, and it is a runtime
    protocol check rather than a list of method names, so that adding a method to
    Platform cannot leave a second list behind to drift out of step with it. A
    connector missing half the interface is caught before the first prompt rather
    than at the moment of the send, which is the worst possible time to find out.
    """
    instance = find_platform(name)()
    if not isinstance(instance, Platform):
        raise PlatformError(
            f"the connector registered as {name} does not implement the platform "
            "interface: it needs fetch_comments and publish_reply"
        )
    return instance


def publish_target(cfg: dict) -> tuple[str, str]:
    """The platform name and the variable holding the write credential, or an error.

    Shape and type, never content, on the same rule as config.load_config: nothing
    here asks whether a token is valid, only whether the operator named one. That
    is why this lives beside the registry rather than inside load_config: every
    other subcommand has to keep loading a config that has no [publish] table at
    all, and requiring one there would make a read only deployment impossible.
    """
    section = cfg.get(PUBLISH_SECTION)
    if section is None:
        raise PlatformError(
            "this config has no [publish] table, so it cannot publish anything. "
            f"Add one with {PLATFORM_KEY} and {CREDENTIAL_KEY} to set publishing up."
        )
    if not isinstance(section, dict):
        raise PlatformError(f"[{PUBLISH_SECTION}] must be a table")
    return (
        _require_text(section, PUBLISH_SECTION, PLATFORM_KEY, "a registered platform name"),
        _require_text(
            section, PUBLISH_SECTION, CREDENTIAL_KEY, "the name of an environment variable"
        ),
    )


def source_target(cfg: dict) -> tuple[str, str]:
    """The platform name and the variable holding the read credential, or an error.

    [source] when the config has one. [publish] when it does not, which is the
    one place these two tables touch, and the direction matters: a config written
    before [source] existed goes on pulling from the table it already has, and
    nothing anywhere reads [source] to publish with. A read credential cannot
    become a write credential by being pointed at from the other side.

    Shape and type, never content, on the same rule as publish_target above.
    """
    section = cfg.get(SOURCE_SECTION)
    if section is None:
        if cfg.get(PUBLISH_SECTION) is not None:
            return publish_target(cfg)
        raise PlatformError(
            f"this config has no [{SOURCE_SECTION}] table and no [{PUBLISH_SECTION}] "
            f"table, so there is nothing to pull from. Add [{SOURCE_SECTION}] with "
            f"{PLATFORM_KEY} and {CREDENTIAL_KEY}, plus whatever key the connector "
            "needs to name the account, and pulling works with no write credential "
            "anywhere near the machine."
        )
    if not isinstance(section, dict):
        raise PlatformError(f"[{SOURCE_SECTION}] must be a table")
    return (
        _require_text(section, SOURCE_SECTION, PLATFORM_KEY, "a registered platform name"),
        _require_text(
            section, SOURCE_SECTION, CREDENTIAL_KEY, "the name of an environment variable"
        ),
    )


def declared_publish_keys() -> set[str]:
    """Every [publish] key the config format has, as dotted names.

    The two the registry owns, plus whatever each registered connector declares
    through the class attribute named by DECLARED_KEYS. This is what the config
    vocabulary freeze reads, so a connector that adds a key and does not declare
    it here is a connector whose key nothing reviews.
    """
    return _declared(PUBLISH_SECTION, DECLARED_KEYS)


def declared_source_keys() -> set[str]:
    """The same inventory for [source], and the reason the convention is two calls.

    A connector's reading key is exactly as invisible to review as its publishing
    key was, and for the same reason: it is read through a module constant, so no
    string literal under src/ spells it where an AST walk could find it.
    """
    return _declared(SOURCE_SECTION, DECLARED_SOURCE_KEYS)


def _declared(section: str, attribute: str) -> set[str]:
    names = {
        section,
        f"{section}.{PLATFORM_KEY}",
        f"{section}.{CREDENTIAL_KEY}",
    }
    for connector in PLATFORMS.values():
        for key in getattr(connector, attribute, ()):
            names.add(f"{section}.{key}")
    return names


def _require_text(section: dict, table: str, key: str, hint: str) -> str:
    """A non-empty string, or a PlatformError naming the key and what belongs in it.

    A bool is rejected before the isinstance check can matter, on the same argument
    config._require_number makes: TOML has a bool literal, an operator can type one
    anywhere, and a value coerced with str() becomes a plausible looking name that
    matches no registered platform and no environment variable.

    The table is a parameter rather than a constant because the same two keys are
    written in two tables now, and a message that names the wrong one sends an
    operator to edit a table that is already correct.
    """
    value = section.get(key)
    if isinstance(value, bool) or not isinstance(value, str) or not value.strip():
        raise PlatformError(f"{table}.{key} must be a non-empty string ({hint})")
    return value


# Imported for the side effect of registering the built in connectors, on the same
# convention as commentdraft.sources. The import sits at the bottom because the
# module above defines the decorator they use, and the name is unused on purpose.
from . import facebook  # noqa: E402,F401  imported for the side effect of registering
