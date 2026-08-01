# SPDX-License-Identifier: Apache-2.0
"""The constitutional tests. Two properties, both checked by walking the AST.

The first is that the engine holds no human-language copy. Every string in this
package is a machine token or English scaffolding: a JSON key, a CSV header, a
CLI flag, an error message for whoever runs the tool. All copy that reaches a
reader lives in files the operator writes, which is what lets the same code serve
a product in any language without a Python edit.

That rule is easy to state and easy to erode one convenient literal at a time,
usually while someone is debugging in a hurry. So it is checked mechanically.
ASCII-only is a proxy for it and a strict one: the moment copy in any other
script reaches a module the suite fails and names the line, which is exactly when
someone should be asked to move it into config instead.

Only string literals are checked, because those are what ship inside a prompt.
Comments are not AST nodes and are not scanned here.

The second is that nothing reaches a platform that a person did not read and
approve first. That half starts below the divider titled "the approval gate",
which also records what used to stand in its place and why it does not any more.
"""

import ast
import re
import tomllib
from pathlib import Path

import pytest

from conftest import MINIMAL_CONFIG_TOML, PACKAGE_ROOT, REPO_ROOT


def non_ascii_literals(source: str, filename: str) -> list[tuple[int, str]]:
    """Every non-ASCII string constant in `source`, as (line number, value).

    Docstrings are ast.Constant nodes like any other string, so they are covered
    without special handling. The parts of an f-string are Constant nodes under a
    JoinedStr, so ast.walk reaches those too.
    """
    tree = ast.parse(source, filename=filename)
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and not node.value.isascii()
        ):
            found.append((node.lineno, node.value))
    return found


def _module_paths() -> list[Path]:
    return sorted(PACKAGE_ROOT.rglob("*.py"))


# Relative to the package rather than p.name: three modules are called __init__.py,
# so p.name collapsed them into __init__.py0, __init__.py1 and __init__.py2, and a
# failing id named none of the three.
@pytest.mark.parametrize("module", _module_paths(), ids=lambda p: str(p.relative_to(PACKAGE_ROOT)))
def test_module_holds_no_non_ascii_literal(module: Path) -> None:
    source = module.read_text(encoding="utf-8")
    offenders = non_ascii_literals(source, str(module))
    detail = "\n".join(f"  {module}:{line}: {value!r}" for line, value in offenders)
    assert not offenders, f"non-ASCII string literal under src/:\n{detail}"


def test_every_module_is_covered() -> None:
    """A parameterized test over an empty list passes and proves nothing.

    If the glob ever stops matching, this is the test that says so.
    """
    modules = _module_paths()
    assert modules, f"no modules found under {PACKAGE_ROOT}"
    assert PACKAGE_ROOT / "__init__.py" in modules


def test_checker_flags_a_non_ascii_literal(tmp_path: Path) -> None:
    """The guard is only worth having if it actually catches something.

    The offending character is built with chr() so this file stays ASCII itself,
    which keeps it honest about the rule it enforces.
    """
    accented = "caf" + chr(0xE9)
    source = "\n".join(["X = 1", "", f'GREETING = "{accented}"', ""])
    module = tmp_path / "leaky.py"
    module.write_text(source, encoding="utf-8")

    offenders = non_ascii_literals(module.read_text(encoding="utf-8"), str(module))

    assert offenders == [(3, accented)]


def test_checker_flags_a_non_ascii_docstring(tmp_path: Path) -> None:
    """A docstring is the likeliest place for copy to arrive unnoticed."""
    dash = chr(0x2014)
    source = f'"""Summary {dash} with a dash."""\n'
    module = tmp_path / "docstring.py"
    module.write_text(source, encoding="utf-8")

    offenders = non_ascii_literals(module.read_text(encoding="utf-8"), str(module))

    assert len(offenders) == 1
    assert offenders[0][0] == 1
    assert dash in offenders[0][1]


def test_checker_flags_a_non_ascii_fstring_part(tmp_path: Path) -> None:
    """An f-string hides its literal parts one node deeper than a plain string."""
    arrow = chr(0x2192)
    source = f'def label(x):\n    return f"{{x}} {arrow} done"\n'
    module = tmp_path / "fstring.py"
    module.write_text(source, encoding="utf-8")

    offenders = non_ascii_literals(module.read_text(encoding="utf-8"), str(module))

    assert [value for _, value in offenders] == [" " + arrow + " done"]


def test_checker_passes_clean_source(tmp_path: Path) -> None:
    module = tmp_path / "clean.py"
    module.write_text('"""Fine."""\n\nNAME = "commentdraft"\nCOUNT = 3\n', encoding="utf-8")

    assert non_ascii_literals(module.read_text(encoding="utf-8"), str(module)) == []


# ============================================================================
# The approval gate
# ============================================================================
#
# What used to be here, in tests/test_generality.py, and why it is not any more.
#
# test_the_package_contains_no_client_for_any_platform walked the AST of every
# module and failed on a platform import name or a platform hostname string. Its
# docstring read:
#
#     The never-posts promise is a property of the code, not of a policy
#     document. ui.py legitimately serves on localhost, so http.server and
#     socketserver are fine. What may not exist anywhere is a way to reach a
#     platform's API.
#
# That claim was doing two jobs and only one of them was load bearing. The weak
# job was "no HTTP client exists", which is an implementation detail and was only
# ever a cheap way to make the real claim checkable. The load bearing job was
# NOTHING REACHES A PLATFORM THAT A PERSON DID NOT READ AND APPROVE FIRST.
#
# Connectors are being added, so the weak job cannot survive and the load bearing
# one is untouched by them. The guarantee therefore moves from "the capability is
# absent" to "the capability exists and is structurally gated". The tests below
# are that guarantee. They are deliberately harder than the one they replace:
# the old one could be satisfied by deleting a file, and these can only be
# satisfied by the send staying behind a keystroke.

GATE = PACKAGE_ROOT / "approve.py"
CONNECTORS = PACKAGE_ROOT / "platforms"

# The method a connector implements to put something on a platform. The name is
# the anchor for every structural test below, which is why it appears here once.
PUBLISH_METHOD = "publish_reply"

# The single function that reaches PUBLISH_METHOD, and the value it demands.
# The name is deliberately unmistakable rather than short: ui.py has a private
# _send of its own for writing HTTP responses, and a structural test anchored on
# a name two modules share is a test that reports the wrong file.
SEND_FUNCTION = "_send_approved"
APPROVAL_TYPE = "Approval"

# The names of the constants a branch has to compare against before it may reach
# a send. Not their values: a test that hardcoded "y" would keep passing if the
# send key were quietly rebound to Enter.
KEY_CONSTANTS = {"SEND_KEY", "EDIT_KEY"}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _parents(tree: ast.AST) -> dict[int, ast.AST]:
    """id(child) -> parent, for walking back up from a call site."""
    table: dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            table[id(child)] = node
    return table


def _ancestors(node: ast.AST, parents: dict[int, ast.AST]):
    current = node
    while id(current) in parents:
        current = parents[id(current)]
        yield current


def _called_name(node: ast.Call) -> str:
    """The bare name being called: `x.publish_reply(...)` and `_send(...)` alike."""
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _call_sites(name: str) -> list[tuple[Path, ast.Call, ast.Module]]:
    sites = []
    for path in _module_paths():
        tree = _tree(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _called_name(node) == name:
                sites.append((path, node, tree))
    return sites


def _enclosing_function(node: ast.AST, parents: dict[int, ast.AST]) -> str:
    for ancestor in _ancestors(node, parents):
        if isinstance(ancestor, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return ancestor.name
    return ""


def _contains(statement: ast.AST, target: ast.AST) -> bool:
    return any(node is target for node in ast.walk(statement))


def _tests_a_key_constant(node: ast.If) -> bool:
    """True when this `if` is an equality check against SEND_KEY or EDIT_KEY.

    Equality specifically. `if pressed != SKIP_KEY:` reads almost the same and
    means the opposite: it sends on anything that is not a skip, Enter included.
    """
    if not isinstance(node.test, ast.Compare):
        return False
    if [type(op) for op in node.test.ops] != [ast.Eq]:
        return False
    operands = [node.test.left, *node.test.comparators]
    return any(isinstance(part, ast.Name) and part.id in KEY_CONSTANTS for part in operands)


def _guarding_branch(node: ast.AST, parents: dict[int, ast.AST]) -> ast.If | None:
    """The `if pressed == SEND_KEY:` this node sits in the body of, if any.

    The body, never the orelse. An `else:` that reached a send would be reached
    by every key that is not the ones above it, which is the whole failure being
    guarded against.
    """
    for ancestor in _ancestors(node, parents):
        if (
            isinstance(ancestor, ast.If)
            and _tests_a_key_constant(ancestor)
            and any(_contains(statement, node) for statement in ancestor.body)
        ):
            return ancestor
    return None


# --- a. the send exists in exactly one place --------------------------------


def test_the_only_call_to_publish_reply_in_the_package_is_inside_the_gate() -> None:
    """This is what replaces the no-client claim.

    The old test said a platform client did not exist. That was true, checkable,
    and about to stop being either. This one says the capability exists and has
    exactly one call site, in the module whose entire job is to put a person in
    front of it. A connector added tomorrow does not weaken it; a second call
    site anywhere fails the build and names the file and the line.

    Exactly one, not "none outside the gate": a test that tolerated zero would
    keep passing after somebody deleted the send and left the gate an empty
    ceremony, and a test that tolerated two inside the gate would let a second,
    ungated route grow next to the first.
    """
    sites = _call_sites(PUBLISH_METHOD)
    located = [f"{path.relative_to(REPO_ROOT)}:{node.lineno}" for path, node, _ in sites]
    assert len(sites) == 1, f"{PUBLISH_METHOD} is called at {len(sites)} places: {located}"

    path, node, tree = sites[0]
    assert path == GATE, f"{PUBLISH_METHOD} is called outside the approval gate: {located[0]}"
    enclosing = _enclosing_function(node, _parents(tree))
    assert enclosing == SEND_FUNCTION, (
        f"{PUBLISH_METHOD} is called from {enclosing or 'module level'}, not {SEND_FUNCTION}"
    )


def test_no_module_reaches_the_send_by_its_name_as_a_string() -> None:
    """getattr(connector, "publish_reply")(...) is a call the test above cannot see.

    The AST records that as a call to getattr, so the name has to be banned as a
    literal too. The interface declaration in the connector registry is a `def`,
    not a string, so nothing legitimate in this package writes this name as data.
    """
    offenders = []
    for path in _module_paths():
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.Constant) and node.value == PUBLISH_METHOD:
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")
    assert offenders == [], (
        f"{PUBLISH_METHOD} appears as a string literal, which is how a call gets "
        f"past an AST check: {offenders}"
    )


# --- b. no path reaches a send without a value the prompt produced ----------


@pytest.mark.parametrize("name", [SEND_FUNCTION, APPROVAL_TYPE])
def test_every_send_sits_inside_a_branch_an_explicit_keystroke_reaches(name: str) -> None:
    """Structure, not the behaviour of one run.

    Two things carry the send: the Approval that holds the approved text, and
    _send, the only function that hands it to a connector. Every construction of
    the first and every call of the second has to sit lexically inside the body
    of an `if` comparing the pressed key against SEND_KEY or EDIT_KEY. Move
    either one out of that branch, wrap it in a loop over a batch, or reach it
    from an `else`, and this fails and names the line.
    """
    sites = _call_sites(name)
    assert sites, f"{name} is never used; the gate has been hollowed out"
    offenders = []
    for path, node, tree in sites:
        where = f"{path.relative_to(REPO_ROOT)}:{node.lineno}"
        if path != GATE:
            offenders.append(f"{where} (outside the approval gate)")
            continue
        if _guarding_branch(node, _parents(tree)) is None:
            offenders.append(f"{where} (not inside a branch testing {' or '.join(KEY_CONSTANTS)})")
    assert offenders == [], f"{name} is reachable without a keystroke: {offenders}"


@pytest.mark.parametrize("name", [SEND_FUNCTION, APPROVAL_TYPE])
def test_the_send_cannot_be_smuggled_out_of_its_branch_as_a_value(name: str) -> None:
    """A guarded call site is worth nothing if the callable can be handed elsewhere.

    `later = _send` inside the branch, then `later(...)` in a loop outside it,
    would satisfy the test above and defeat the point of it entirely. So these
    two names may appear only where they are defined and where they are called.
    An annotation is allowed: it moves no value at runtime.
    """
    offenders = []
    for path in _module_paths():
        tree = _tree(path)
        parents = _parents(tree)
        annotated = {
            id(inner)
            for node in ast.walk(tree)
            for field in ("annotation", "returns")
            for outer in [getattr(node, field, None)]
            if outer is not None
            for inner in ast.walk(outer)
        }
        for node in ast.walk(tree):
            if not isinstance(node, ast.Name) or node.id != name:
                continue
            if id(node) in annotated:
                continue
            parent = parents.get(id(node))
            if isinstance(parent, ast.Call) and parent.func is node:
                continue
            offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")
    assert offenders == [], f"{name} is used as a value rather than called: {offenders}"


def test_the_prompt_loop_carries_no_else_branch_at_all() -> None:
    """There is no default action, and the shape of the code is what says so.

    Every branch in the loop is a positive test against one named key. An `else`
    is by definition reached by every key that did not match, which is every key
    a resting finger produces, Enter first among them. Adding one is a deliberate
    act and this is the test that makes it one.
    """
    tree = _tree(GATE)
    (loop,) = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "approve_and_publish"
    ]
    offenders = [node.lineno for node in ast.walk(loop) if isinstance(node, ast.If) and node.orelse]
    assert offenders == [], f"approve_and_publish grew an else at line(s) {offenders}"


# --- c. no config key and no flag can stand in for the keystroke ------------
#
# The one that matters in a year. Everything above describes today's code. This
# describes what a future contributor will try to add, for a good reason, on a
# afternoon when publishing thirty replies by hand is genuinely annoying.
#
# Each pattern pairs a modifier with an action, rather than banning a bare word,
# so that it names the thing being refused instead of reserving vocabulary. A key
# called `approved` on a review row is fine; `auto_approve` is not.

BYPASS_SHAPES = [
    r"auto[_-]?(approve|approval|publish|send|post|repl(y|ies))",
    r"(approve|approval|publish|send|post)[_-]?(all|everything|each|every|batch)",
    r"^y(es)?$",
    r"assume[_-]?yes",
    r"(skip|no|without|suppress|disable)[_-]?(prompt|confirm|confirmation|approval|review|gate)",
    r"non[_-]?interactive",
    r"unattended",
    r"headless",
    r"(force|always)[_-]?(send|publish|approve|post)",
    r"batch[_-]?(approve|publish|send|post)",
    r"bypass",
]

BYPASS_KEY = re.compile("|".join(BYPASS_SHAPES), re.IGNORECASE)

CONFIG_FILES = sorted(REPO_ROOT.glob("examples/*/config.toml")) + sorted(
    REPO_ROOT.glob("tests/fixtures/*/config.toml")
)


def _lookup_keys(tree: ast.Module):
    """(line, key) for every string literal this module uses as a mapping key.

    A setting nothing reads changes nothing, so a bypass flag has to be read
    somewhere under src/ to do any harm. This finds the reading of it, in all
    four shapes the package uses: subscript, .get, .setdefault and `in`.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            index = node.slice
            if isinstance(index, ast.Constant) and isinstance(index.value, str):
                yield node.lineno, index.value
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in ("get", "setdefault", "pop") and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    yield node.lineno, first.value
        elif isinstance(node, ast.Compare) and isinstance(node.left, ast.Constant):
            if isinstance(node.left.value, str) and any(
                isinstance(op, (ast.In, ast.NotIn)) for op in node.ops
            ):
                yield node.lineno, node.left.value


def _toml_keys(table: dict, prefix: str = ""):
    for key, value in table.items():
        yield f"{prefix}{key}"
        if isinstance(value, dict):
            yield from _toml_keys(value, f"{prefix}{key}.")
        elif isinstance(value, list):
            for entry in value:
                if isinstance(entry, dict):
                    yield from _toml_keys(entry, f"{prefix}{key}.")


def test_no_setting_the_package_reads_could_stand_in_for_a_keystroke() -> None:
    """Assert the absence of the key, not the behaviour of the code that has none.

    A test that ran the loop and checked that a config flag was ignored would
    pass just as well on the day somebody wires the flag up wrongly. This one
    fails on the line that reads the key, which is before the wiring exists.
    """
    offenders = []
    for path in _module_paths():
        for line, key in _lookup_keys(_tree(path)):
            if BYPASS_KEY.search(key):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{line}: {key!r}")
    assert offenders == [], (
        "a setting shaped like an approval bypass is read under src/. Approval is "
        f"a keystroke against one reply and cannot be expressed in a file: {offenders}"
    )


def test_the_declared_config_schema_holds_no_such_key() -> None:
    from commentdraft.config import REQUIRED

    declared = [section for section in REQUIRED] + [
        f"{section}.{key}" for section, keys in REQUIRED.items() for key in keys
    ]
    offenders = [name for name in declared if BYPASS_KEY.search(name.rsplit(".", 1)[-1])]
    assert offenders == [], f"config.REQUIRED declares an approval bypass: {offenders}"


@pytest.mark.parametrize("path", CONFIG_FILES, ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_no_shipped_config_carries_such_a_key(path: Path) -> None:
    """The examples are what an operator copies. A key demonstrated there is a
    key that gets carried into every config derived from it."""
    keys = list(_toml_keys(tomllib.loads(path.read_text(encoding="utf-8"))))
    offenders = [key for key in keys if BYPASS_KEY.search(key.rsplit(".", 1)[-1])]
    assert offenders == [], f"{path.name} carries an approval bypass: {offenders}"


def test_the_config_the_suite_itself_uses_carries_no_such_key() -> None:
    keys = list(_toml_keys(tomllib.loads(MINIMAL_CONFIG_TOML)))
    offenders = [key for key in keys if BYPASS_KEY.search(key.rsplit(".", 1)[-1])]
    assert offenders == [], f"the shared test config carries an approval bypass: {offenders}"


def test_no_subcommand_offers_a_flag_that_could_stand_in_for_a_keystroke() -> None:
    """There is no --yes and no --all. Not defaulted off. Absent.

    A flag that exists is a flag somebody sets once, in a shell alias or a cron
    line, and forgets. The whole claim collapses the first time it is set on a
    machine nobody is watching, and nothing about the run afterwards looks wrong.
    """
    import argparse

    from commentdraft.cli import build_parser

    parser = build_parser()
    (subparsers,) = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
    offenders = []
    for name, sub in subparsers.choices.items():
        for action in sub._actions:
            for option in action.option_strings:
                if BYPASS_KEY.search(option.lstrip("-")):
                    offenders.append(f"{name} {option}")
    assert offenders == [], f"a subcommand offers an approval bypass flag: {offenders}"


def test_the_bypass_pattern_catches_the_keys_somebody_will_actually_reach_for() -> None:
    """A guard is only worth having if it catches something.

    Every name below is one a reasonable contributor would pick while solving a
    real problem: thirty keystrokes is genuinely tedious and the fix looks
    obvious. The point of the list is that each of them fails a test rather than
    landing in a Friday pull request nobody reads closely.
    """
    for name in (
        "auto_approve",
        "auto-approve",
        "autoapprove",
        "auto_publish",
        "auto_send",
        "auto_reply",
        "approve_all",
        "publish_all",
        "send_every",
        "yes",
        "y",
        "assume_yes",
        "skip_prompt",
        "no_confirm",
        "no-confirmation",
        "without_review",
        "disable_gate",
        "non_interactive",
        "noninteractive",
        "unattended",
        "headless",
        "force_publish",
        "always_send",
        "batch_approve",
        "bypass_approval",
    ):
        assert BYPASS_KEY.search(name), f"the bypass pattern misses {name!r}"

    # And the other half: names this project legitimately uses, or plausibly
    # would, that the pattern must not reserve. A guard that fires on ordinary
    # words gets an exception list, and an exception list is where the real one
    # eventually hides.
    for name in (
        "approved",
        "approval_log",
        "published_id",
        "publish",
        "platform",
        "credential_env",
        "reply",
        "post_title",
        "plug_cap",
        "escalation_contact",
        "banned_emoji",
        "cta_mode",
        "max_reply_sentences",
        "data_collection",
        "api_key_env",
    ):
        assert not BYPASS_KEY.search(name), f"the bypass pattern reserves {name!r}"


# --- the network stays inside the connectors --------------------------------

# Everything the old no-client test banned outright. It is not banned outright
# any more, because a connector is a thing that talks to a platform. It is
# confined instead: only modules under platforms/ may hold one, so the gate, the
# engine, the CLI and the review page still cannot reach a platform by any route,
# and a reviewer auditing the network surface has one directory to read.
BANNED_IMPORTS = {
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "urllib.request",
    "http.client",
    "googleapiclient",
    "google_auth_oauthlib",
    "google.oauth2",
    "google.auth",
    "tweepy",
    "facebook",
    "facebook_sdk",
    "instagrapi",
    "TikTokApi",
    "atproto",
    "praw",
}


def test_no_module_outside_the_connectors_can_reach_a_platform() -> None:
    """ui.py legitimately serves on localhost, so http.server and socketserver
    are fine and are not on the list. What may not exist outside platforms/ is a
    way to reach somebody else's API."""
    offenders = []
    for path in _module_paths():
        if CONNECTORS in path.parents:
            continue
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.Import):
                imported = [(node.lineno, alias.name) for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported = [(node.lineno, node.module)]
            else:
                continue
            for line, name in imported:
                if name in BANNED_IMPORTS:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{line}: {name}")
    assert offenders == [], f"a module outside platforms/ imports a network client: {offenders}"


# --- e and f, driven through the real loop ----------------------------------


class _Recorder:
    """A connector that records calls and reaches nothing."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def fetch_comments(self, config: dict, since: str) -> list[dict]:
        self.calls.append(("fetch_comments", since))
        return []

    def publish_reply(self, config: dict, parent_id: str, text: str) -> str:
        self.calls.append((PUBLISH_METHOD, parent_id, text))
        return "published-" + parent_id


class _Stream:
    def __init__(self) -> None:
        self.chunks: list[str] = []

    def write(self, text: str) -> int:
        self.chunks.append(text)
        return len(text)

    @property
    def text(self) -> str:
        return "".join(self.chunks)


def _rows(count: int) -> list[dict]:
    return [
        {
            "id": f"c{index}",
            "platform": "video-site",
            "comment": "how much is it",
            "post_title": "a clip",
            "decision": "reply",
            "reply": f"draft {index}",
        }
        for index in range(1, count + 1)
    ]


def _drive(rows, keys, platform, tmp_path, **kwargs):
    from commentdraft.approve import approve_and_publish

    pressed = list(keys)
    stream = _Stream()

    def read_key() -> str:
        if not pressed:
            raise EOFError
        return pressed.pop(0)

    counts = approve_and_publish(
        rows,
        {},
        platform,
        platform_name="video-site",
        config_label="config.toml",
        log_path=tmp_path / "published.jsonl",
        read_key=read_key,
        out=stream,
        **kwargs,
    )
    return counts, stream, pressed


def test_a_dry_run_issues_no_call_at_all(tmp_path: Path) -> None:
    """Against a connector that records everything it is asked to do. A dry run
    exists so a person can read what a platform would receive before granting any
    write scope, which means it has to be safe on a setup that has none.

    The scripted reviewer is holding the send key down. That is the point: a dry
    run that merely happened to reach the end of a queue nobody approved would
    pass an emptier version of this test, and would still send the day somebody's
    stdin had a `y` in it.
    """
    platform = _Recorder()
    counts, stream, unread = _drive(_rows(3), ["y", "y", "y"], platform, tmp_path, dry_run=True)

    assert platform.calls == []
    assert counts["sent"] == 0
    assert unread == ["y", "y", "y"], "a dry run read a keystroke"
    assert not (tmp_path / "published.jsonl").exists()
    assert "draft 1" in stream.text and "draft 3" in stream.text


def test_enter_alone_advances_nothing_and_sends_nothing(tmp_path: Path) -> None:
    """The property the four keys were chosen for. A reviewer with a finger
    resting on Enter cannot walk the queue, because Enter is not one of them and
    there is no default underneath them."""
    platform = _Recorder()
    counts, stream, unread = _drive(_rows(2), ["", "", "", "", "q"], platform, tmp_path)

    assert platform.calls == []
    assert counts["sent"] == 0
    assert unread == [], "the loop stopped reading keys before the script ran out"
    assert stream.text.count("[ 1 / 2 ]") == 1, "Enter moved the queue"
    assert "[ 2 / 2 ]" not in stream.text


def test_one_keystroke_sends_exactly_one_reply(tmp_path: Path) -> None:
    """The other half of the same claim: the key that does send, sends one."""
    platform = _Recorder()
    counts, _, _ = _drive(_rows(3), ["y", "q"], platform, tmp_path)

    assert platform.calls == [(PUBLISH_METHOD, "c1", "draft 1")]
    assert counts["sent"] == 1


# --- d. a read only deployment is a real one --------------------------------


def _fake_client(canned: str):
    """The SDK surface the engine uses, offline and keyless."""
    import types

    class _Completions:
        def create(self, **kwargs):
            usage = types.SimpleNamespace(
                prompt_tokens=1000,
                completion_tokens=10,
                prompt_tokens_details=types.SimpleNamespace(cached_tokens=0, cache_write_tokens=0),
            )
            message = types.SimpleNamespace(content=canned)
            return types.SimpleNamespace(
                choices=[types.SimpleNamespace(message=message)], usage=usage
            )

    return types.SimpleNamespace(chat=types.SimpleNamespace(completions=_Completions()))


def test_a_config_with_no_publish_credential_loads_runs_and_drafts(tmp_path, monkeypatch) -> None:
    """Most people should run this way for a while and some should run this way
    forever, so it cannot be a degraded mode that limps.

    The product directory is built by tests/test_cli.py's own builder rather than
    a second one written here: two definitions of "a valid product" is how the
    two end up disagreeing about what a valid product is.
    """
    import json as _json

    from commentdraft import cli
    from commentdraft.config import load_config
    from commentdraft.platforms import PlatformError, publish_target
    from test_cli import build_product

    config = build_product(tmp_path)  # no [publish] table at all
    monkeypatch.setenv("CD_KEY_MAIN", "not-a-real-key")
    canned = _json.dumps(
        {"decision": "reply", "reason": "asks the price", "reply_text": "eighteen dollars"}
    )
    monkeypatch.setattr(cli, "make_client", lambda model_cfg: _fake_client(canned))

    # It loads.
    cfg = load_config(config)
    assert "publish" not in cfg

    # It runs and it drafts.
    out = tmp_path / "out"
    rc = cli.main(
        [
            "run",
            "--config",
            str(config),
            "--comments",
            str(tmp_path / "comments.csv"),
            "--out",
            str(out),
        ]
    )
    assert rc == 0
    drafted = (out / "review.csv").read_text(encoding="utf-8")
    assert "eighteen dollars" in drafted

    # And publishing refuses it, by name, rather than by KeyError.
    with pytest.raises(PlatformError) as exc:
        publish_target(cfg)
    assert "publish" in str(exc.value)


def test_publish_refuses_a_config_with_no_credential_and_names_what_is_missing(
    tmp_path, capsys, monkeypatch
) -> None:
    """Three separate ways to have no write scope, and each one has to say which
    one it is. An operator who reads "missing credential" when the real problem
    is a platform nobody registered will go looking for a token they already
    have."""
    from commentdraft import cli
    from commentdraft.platforms import PLATFORMS
    from test_cli import build_product

    class _Connector:
        def fetch_comments(self, config, since):
            return []

        def publish_reply(self, config, parent_id, text):
            raise AssertionError("no test may reach this")

    monkeypatch.delenv("CD_PUBLISH_TOKEN", raising=False)

    # 1. No [publish] table.
    config = build_product(tmp_path / "readonly", extra="")
    assert cli.main(["publish", "--config", str(config), "--out", str(tmp_path / "o1")]) == 2
    assert "publish" in capsys.readouterr().err

    # 2. A [publish] table naming a platform nobody registered.
    named = '\n[publish]\nplatform = "fixture-gate"\ncredential_env = "CD_PUBLISH_TOKEN"\n'
    config = build_product(tmp_path / "unknown", extra=named)
    assert cli.main(["publish", "--config", str(config), "--out", str(tmp_path / "o2")]) == 2
    assert "fixture-gate" in capsys.readouterr().err

    # 3. A registered platform and no token in the environment.
    monkeypatch.setitem(PLATFORMS, "fixture-gate", _Connector)
    config = build_product(tmp_path / "keyless", extra=named)
    assert cli.main(["publish", "--config", str(config), "--out", str(tmp_path / "o3")]) == 2
    err = capsys.readouterr().err
    assert "CD_PUBLISH_TOKEN" in err
    assert "Traceback" not in err
