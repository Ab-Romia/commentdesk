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

from conftest import MINIMAL_CONFIG_TOML, PACKAGE_ROOT, REPO_ROOT, scripted_reviewer


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

# The prompt loop, and the one function that returns a key a person pressed.
# Everything below anchors on provenance rather than on spelling: it is not
# enough that a branch compares something to SEND_KEY, the thing compared has to
# have come out of _press.
GATE_FUNCTION = "approve_and_publish"
PRESS_FUNCTION = "_press"

# The only keywords an in-package caller may pass the gate. out, edit and now are
# real parameters with real defaults because the suite drives the loop through
# them, and one of them at the call site in cmd_publish is the cheapest bypass in
# the repo: a caller supplying its own `edit` answers a prompt it also asked.
GATE_CALL_KEYWORDS = {"platform_name", "config_label", "log_path", "dry_run"}

# The private attribute the suite installs a scripted reviewer on. It is honoured
# only while a test runner is in sys.modules, and it replaced a public `read_key`
# keyword that let any importer publish a whole queue with `lambda: "y"`. No
# module under src/ but the gate may so much as name it.
SCRIPTED_SEAM = "_scripted_keys"


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


def _annotated(tree: ast.AST) -> set[int]:
    """id() of every node inside an annotation. An annotation moves no value."""
    return {
        id(inner)
        for node in ast.walk(tree)
        for field in ("annotation", "returns")
        for outer in [getattr(node, field, None)]
        if outer is not None
        for inner in ast.walk(outer)
    }


def _references(name: str) -> list[tuple[Path, ast.AST, ast.Module]]:
    """Every mention of `name` in the package, whether or not it heads a call.

    Collecting ast.Call was the hole under all three structural tests. The
    statement `post = platform.publish_reply` contains no Call node at all, so a
    loop calling `post(cfg, parent_id, text)` afterwards registered zero call
    sites, and the same trick reached _send_approved through the module object.
    An Attribute stores its name in the plain string field `.attr` rather than as
    a Name node, so an attribute load was invisible to the Name-only checks too.

    So the anchor is the reference rather than the call: any Name with this id,
    and any Attribute whose .attr is this name, wherever either appears. A `def`
    or a `class` of the same name is not a reference, because its name is also a
    plain string field, which is what keeps the definitions themselves out.

    Annotations are excluded. `approval: Approval` binds nothing at runtime, and
    a test that reported it would push contributors to drop the annotations that
    make this module readable.
    """
    sites: list[tuple[Path, ast.AST, ast.Module]] = []
    for path in _module_paths():
        tree = _tree(path)
        skip = _annotated(tree)
        for node in ast.walk(tree):
            if id(node) in skip:
                continue
            if (isinstance(node, ast.Name) and node.id == name) or (
                isinstance(node, ast.Attribute) and node.attr == name
            ):
                sites.append((path, node, tree))
    return sites


def _is_called(node: ast.AST, parents: dict[int, ast.AST]) -> bool:
    """True when this reference is the thing being called, not a value being moved."""
    parent = parents.get(id(node))
    return isinstance(parent, ast.Call) and parent.func is node


def _where(path: Path, node: ast.AST) -> str:
    return f"{path.relative_to(REPO_ROOT)}:{getattr(node, 'lineno', '?')}"


def _enclosing_function(node: ast.AST, parents: dict[int, ast.AST]) -> str:
    for ancestor in _ancestors(node, parents):
        if isinstance(ancestor, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return ancestor.name
    return ""


def _contains(statement: ast.AST, target: ast.AST) -> bool:
    return any(node is target for node in ast.walk(statement))


def _gate_function(tree: ast.Module) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == GATE_FUNCTION:
            return node
    return None


def _bindings(function: ast.AST):
    """(name, value) for every place a name is bound inside `function`.

    Every binding form, not only ast.Assign. A `for` target, a walrus, a `with
    ... as`, an `except ... as` and a comprehension target all rebind a name, and
    a check that counted assignments alone would call a name bound twice "bound
    exactly once", which is the whole of what the provenance rule rests on.
    """
    for node in ast.walk(function):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                for name in ast.walk(target):
                    if isinstance(name, ast.Name):
                        yield name.id, node.value
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            for name in ast.walk(node.target):
                if isinstance(name, ast.Name):
                    yield name.id, node.value
        elif isinstance(node, ast.NamedExpr):
            yield node.target.id, node.value
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
            for name in ast.walk(node.target):
                if isinstance(name, ast.Name):
                    yield name.id, None
        elif isinstance(node, ast.withitem) and node.optional_vars is not None:
            for name in ast.walk(node.optional_vars):
                if isinstance(name, ast.Name):
                    yield name.id, None
        elif isinstance(node, ast.ExceptHandler) and node.name:
            yield node.name, None


def _keystroke_names(tree: ast.Module) -> frozenset[str]:
    """Names in the prompt loop bound exactly once, directly from _press(...).

    This is the reframe from shape to provenance. The old rule asked only that
    *some* operand of the `==` be a Name in KEY_CONSTANTS, which is satisfied by
    `if _autopilot(cfg) == SEND_KEY:` and by the always-true `if "y" == SEND_KEY:`.
    Neither of those reads a key from anybody. What actually has to be true is
    that the value on the other side of the comparison came out of the prompt.

    Bound exactly once, so the name cannot be rebound to something else further
    down. A direct call by Name, so `mod._press(...)` through a module object,
    which is the laundering trick this file now watches for everywhere else, does
    not establish provenance here either.
    """
    function = _gate_function(tree)
    if function is None:
        return frozenset()
    counts: dict[str, int] = {}
    from_press: set[str] = set()
    for name, value in _bindings(function):
        counts[name] = counts.get(name, 0) + 1
        if (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id == PRESS_FUNCTION
        ):
            from_press.add(name)
    return frozenset(name for name in from_press if counts[name] == 1)


def _tests_a_key_constant(node: ast.If, keystroke: frozenset[str]) -> bool:
    """True when this `if` compares a value that came from the prompt to a key.

    Equality specifically. `if pressed != SKIP_KEY:` reads almost the same and
    means the opposite: it sends on anything that is not a skip, Enter included.

    Both sides must be plain Names, one of them a key constant and the other one
    of the names _press produced. A Call or a Constant on either side is not a
    keystroke, whatever it is spelled.
    """
    if not isinstance(node.test, ast.Compare):
        return False
    if [type(op) for op in node.test.ops] != [ast.Eq]:
        return False
    operands = [node.test.left, *node.test.comparators]
    if len(operands) != 2 or not all(isinstance(part, ast.Name) for part in operands):
        return False
    names = {part.id for part in operands}  # type: ignore[attr-defined]
    return bool(names & KEY_CONSTANTS) and bool(names & keystroke)


def _guarding_branch(
    node: ast.AST, parents: dict[int, ast.AST], keystroke: frozenset[str]
) -> ast.If | None:
    """The `if pressed == SEND_KEY:` this node sits in the body of, if any.

    The body, never the orelse. An `else:` that reached a send would be reached
    by every key that is not the ones above it, which is the whole failure being
    guarded against.
    """
    for ancestor in _ancestors(node, parents):
        if (
            isinstance(ancestor, ast.If)
            and _tests_a_key_constant(ancestor, keystroke)
            and any(_contains(statement, node) for statement in ancestor.body)
        ):
            return ancestor
    return None


# --- a. the send exists in exactly one place --------------------------------


def test_the_only_reference_to_publish_reply_in_the_package_is_the_call_inside_the_gate() -> None:
    """This is what replaces the no-client claim.

    The old test said a platform client did not exist. That was true, checkable,
    and about to stop being either. This one says the capability exists and is
    mentioned exactly once, in the module whose entire job is to put a person in
    front of it. A connector added tomorrow does not weaken it; a second mention
    anywhere fails the build and names the file and the line.

    Exactly one, not "none outside the gate": a test that tolerated zero would
    keep passing after somebody deleted the send and left the gate an empty
    ceremony, and a test that tolerated two inside the gate would let a second,
    ungated route grow next to the first.

    Reference, not call. `post = platform.publish_reply` is not a Call node, so
    the call-counting version of this test saw nothing at all while the send was
    handed to a loop one line later.
    """
    sites = _references(PUBLISH_METHOD)
    located = [_where(path, node) for path, node, _ in sites]
    assert len(sites) == 1, f"{PUBLISH_METHOD} is named at {len(sites)} places: {located}"

    path, node, tree = sites[0]
    assert path == GATE, f"{PUBLISH_METHOD} is named outside the approval gate: {located[0]}"
    parents = _parents(tree)
    assert _is_called(node, parents), (
        f"{PUBLISH_METHOD} is referenced without being called at {located[0]}, which is "
        "how a send gets carried out of its branch as a value"
    )
    enclosing = _enclosing_function(node, parents)
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
    sites = _references(name)
    assert sites, f"{name} is never used; the gate has been hollowed out"
    offenders = []
    for path, node, tree in sites:
        where = _where(path, node)
        if path != GATE:
            offenders.append(f"{where} (outside the approval gate)")
            continue
        if _guarding_branch(node, _parents(tree), _keystroke_names(tree)) is None:
            offenders.append(f"{where} (not inside a branch testing {' or '.join(KEY_CONSTANTS)})")
    assert offenders == [], f"{name} is reachable without a keystroke: {offenders}"


LOOPS = (
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
)


@pytest.mark.parametrize("name", [SEND_FUNCTION, APPROVAL_TYPE])
def test_no_loop_sits_between_the_keystroke_and_the_send(name: str) -> None:
    """One keystroke is one reply, and a loop is how one becomes thirty.

    The branch test above is satisfied by `for row in queue: _send_approved(...)`
    written inside the send branch, which is the shortest path from this design
    to the one it exists to refuse. So nothing that repeats may sit between the
    `if` that read the key and the call it guards.
    """
    offenders = []
    for path, node, tree in _references(name):
        parents = _parents(tree)
        branch = _guarding_branch(node, parents, _keystroke_names(tree))
        if branch is None:
            continue  # the branch test above already reports this one
        for ancestor in _ancestors(node, parents):
            if ancestor is branch:
                break
            if isinstance(ancestor, LOOPS):
                offenders.append(
                    f"{_where(path, node)} is inside {type(ancestor).__name__} "
                    f"at line {getattr(ancestor, 'lineno', '?')}"
                )
    assert offenders == [], f"one keystroke could reach more than one send: {offenders}"


@pytest.mark.parametrize("name", [SEND_FUNCTION, APPROVAL_TYPE, PUBLISH_METHOD])
def test_the_send_cannot_be_smuggled_out_of_its_branch_as_a_value(name: str) -> None:
    """A guarded call site is worth nothing if the callable can be handed elsewhere.

    `later = _send_approved` inside the branch, then `later(...)` in a loop
    outside it, would satisfy the test above and defeat the point of it entirely.
    So these names may appear only where they are defined and where they are
    called. An annotation is allowed: it moves no value at runtime, and
    _references already leaves annotations out.

    An attribute load counts. `post = platform.publish_reply` is the same
    smuggling written through the object instead of through the name, and the
    Name-only version of this test could not see it.
    """
    offenders = [
        _where(path, node)
        for path, node, tree in _references(name)
        if not _is_called(node, _parents(tree))
    ]
    assert offenders == [], f"{name} is used as a value rather than called: {offenders}"


# Every reference to the three anchors, as file:function, frozen. Set equality
# rather than a bound, so that a reference appearing anywhere new fails until
# somebody writes it down here in the same diff. The old tests asked "is each one
# I can see in the right place", which is a question that answers itself when the
# thing that got added is a shape they cannot see.
REVIEWED_REFERENCES = {
    PUBLISH_METHOD: ["approve.py:_send_approved"],
    SEND_FUNCTION: ["approve.py:approve_and_publish", "approve.py:approve_and_publish"],
    APPROVAL_TYPE: ["approve.py:approve_and_publish", "approve.py:approve_and_publish"],
}


@pytest.mark.parametrize("name", sorted(REVIEWED_REFERENCES))
def test_the_package_inventory_of_each_anchor_is_the_reviewed_list(name: str) -> None:
    found = sorted(
        f"{path.relative_to(PACKAGE_ROOT)}:{_enclosing_function(node, _parents(tree)) or '<module>'}"
        for path, node, tree in _references(name)
    )
    assert found == sorted(REVIEWED_REFERENCES[name]), (
        f"the places {name} is reached from have changed: {found}"
    )


def test_the_prompt_loop_carries_no_else_branch_and_no_conditional_expression() -> None:
    """There is no default action, and the shape of the code is what says so.

    Every branch in the loop is a positive test against one named key. An `else`
    is by definition reached by every key that did not match, which is every key
    a resting finger produces, Enter first among them. Adding one is a deliberate
    act and this is the test that makes it one.

    `a if b else c` is banned in the same breath and for the same reason. It is
    an else by another spelling, it is an ast.IfExp rather than an ast.If, and
    `pressed = SEND_KEY if settled else _press(stream, scripted)` walked straight
    through the version of this test that collected only ast.If.
    """
    tree = _tree(GATE)
    loop = _gate_function(tree)
    assert loop is not None, f"{GATE_FUNCTION} is gone from the gate"
    offenders = [
        f"{type(node).__name__} at line {node.lineno}"
        for node in ast.walk(loop)
        if (isinstance(node, ast.If) and node.orelse) or isinstance(node, ast.IfExp)
    ]
    assert offenders == [], f"{GATE_FUNCTION} grew a default action: {offenders}"


def test_the_branch_that_sends_compares_a_value_the_prompt_produced() -> None:
    """The provenance anchor itself, asserted rather than assumed.

    Every structural test above is satisfied vacuously if no name in the loop
    can be traced back to _press: _tests_a_key_constant would return False
    everywhere, _guarding_branch would find nothing, and a test that only
    collected offenders would report none. So the set has to be non-empty, and
    the branches that guard the sends have to be built out of it.
    """
    assert _keystroke_names(_tree(GATE)), (
        f"no name in {GATE_FUNCTION} is bound exactly once from a direct call to "
        f"{PRESS_FUNCTION}, so nothing compared against a key constant is a keystroke"
    )
    unguarded = [
        _where(path, node)
        for path, node, tree in _references(SEND_FUNCTION) + _references(APPROVAL_TYPE)
        if _guarding_branch(node, _parents(tree), _keystroke_names(tree)) is None
    ]
    assert unguarded == [], f"a send is not guarded by a branch reading a keystroke: {unguarded}"


def test_the_provenance_rule_rejects_a_comparison_that_reads_no_key(tmp_path: Path) -> None:
    """The guard is only worth having if it catches the thing it was written for.

    All three of these pass the old rule, which asked only that some operand be
    a Name in KEY_CONSTANTS. None of them reads a key from a person.
    """
    for body in (
        "    if _autopilot(cfg) == SEND_KEY:\n        _send_approved()\n",
        '    if "y" == SEND_KEY:\n        _send_approved()\n',
        "    pressed = SEND_KEY\n    if pressed == SEND_KEY:\n        _send_approved()\n",
    ):
        source = f"def {GATE_FUNCTION}():\n{body}"
        module = tmp_path / "loop.py"
        module.write_text(source, encoding="utf-8")
        tree = ast.parse(source, filename=str(module))
        keystroke = _keystroke_names(tree)
        branches = [node for node in ast.walk(tree) if isinstance(node, ast.If)]
        assert branches, source
        assert not any(_tests_a_key_constant(node, keystroke) for node in branches), (
            f"this reads no key and the rule accepted it:\n{source}"
        )

    # And the real shape still passes, so the rule is not simply always false.
    source = (
        f"def {GATE_FUNCTION}():\n"
        f"    pressed = {PRESS_FUNCTION}(stream, scripted)\n"
        "    if pressed == SEND_KEY:\n        _send_approved()\n"
    )
    tree = ast.parse(source, filename="loop.py")
    branches = [node for node in ast.walk(tree) if isinstance(node, ast.If)]
    assert any(_tests_a_key_constant(node, _keystroke_names(tree)) for node in branches)


def test_a_name_rebound_after_the_prompt_carries_no_provenance(tmp_path: Path) -> None:
    """Bound exactly once is the load bearing half. A name that came from _press
    and was then reassigned is a name whose value at the comparison is whatever
    the second assignment put there."""
    source = (
        f"def {GATE_FUNCTION}():\n"
        f"    pressed = {PRESS_FUNCTION}(stream, scripted)\n"
        "    pressed = SEND_KEY\n"
        "    if pressed == SEND_KEY:\n        _send_approved()\n"
    )
    tree = ast.parse(source, filename="loop.py")
    assert _keystroke_names(tree) == frozenset()


def test_no_caller_in_the_package_supplies_the_gate_a_seam() -> None:
    """The cheapest bypass in the repo was one keyword argument in cmd_publish.

    out, edit and now are real parameters with real defaults, because the suite
    drives the whole loop through them rather than mocking the prompt away. That
    is fine for a test and not fine for shipped code: a caller that passes its
    own `edit` is answering a question it also asked. So the keywords an
    in-package caller may use are an allowlist, and it does not include them.
    """
    seen = 0
    offenders = []
    for path in _module_paths():
        for node in ast.walk(_tree(path)):
            if not isinstance(node, ast.Call) or _called_name(node) != GATE_FUNCTION:
                continue
            seen += 1
            if any(keyword.arg is None for keyword in node.keywords):
                offenders.append(f"{_where(path, node)}: **kwargs")
            extra = {keyword.arg for keyword in node.keywords if keyword.arg} - GATE_CALL_KEYWORDS
            if extra:
                offenders.append(f"{_where(path, node)}: {sorted(extra)}")
    assert seen, f"nothing under src/ calls {GATE_FUNCTION}; the publish path is gone"
    assert offenders == [], f"a caller under src/ hands the gate its own answer: {offenders}"


def test_no_module_but_the_gate_names_the_scripted_keystroke_seam() -> None:
    """The seam the suite drives the loop with, sealed against installed code.

    Checked as text rather than as an AST node, because reaching it by name at
    all is the offence: setattr(approve, "_scripted_keys", ...) spells it as a
    string, and a source edit that merely mentioned it would be the first half of
    wiring it up.
    """
    offenders = [
        str(path.relative_to(REPO_ROOT))
        for path in _module_paths()
        if path != GATE and SCRIPTED_SEAM in path.read_text(encoding="utf-8")
    ]
    assert offenders == [], f"a module outside the gate names the keystroke seam: {offenders}"

    # And it is still there to be sealed, rather than renamed out from under this.
    assert SCRIPTED_SEAM in GATE.read_text(encoding="utf-8")


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
    # Added after a review found that `pre_approved` matched none of the eleven
    # shapes above and was the single key three separate reported bypasses used.
    # It is also the exact idea APPROVAL.md rejects by name: approval expressed
    # ahead of time, in a file, rather than as a keystroke against one reply.
    r"(pre|already)[_-]?(approv(e|ed|al)|sent|publish(ed)?|confirm(ed)?|ok(ay|ed)?)",
    r"(consent|approval|decision)[_-]?(file|column|field|source|from)",
]

BYPASS_KEY = re.compile("|".join(BYPASS_SHAPES), re.IGNORECASE)

# --- the allowlist, which is the half that survives a name nobody predicted ----
#
# The denylist above is kept, and it is the second signal rather than the first.
# A review demonstrated why: it is eleven guesses at how somebody will spell an
# idea, it missed `pre_approved`, and the fix for that is one more guess. What
# APPROVAL.md item 3 actually asked for was that the config schema contain no key
# that could bypass the prompt, "so adding one is a deliberate act that fails a
# test", and only an allowlist makes adding ANY key the deliberate act.
#
# So the config vocabulary is frozen. Every section and every key the loader
# declares, every key a shipped or fixture config carries, and the two keys the
# [publish] table is made of. A new key of any name at all fails this until it is
# written down here, in the diff that adds it, where a reviewer reads it next to
# the reason.
CONFIG_SCHEMA = frozenset(
    {
        "product",
        "product.name",
        "product.kind",
        "product.price_text",
        "product.purchase_link",
        "product.escalation_contact",
        "knowledge",
        "knowledge.source",
        "knowledge.path",
        "voice",
        "voice.rules",
        "voice.examples",
        "behavior",
        "behavior.cta_mode",
        "behavior.plug_cap",
        "behavior.max_reply_sentences",
        "behavior.bot_disclosure_text",
        "behavior.plug_markers",
        "behavior.separator",
        "behavior.banned_emoji",
        "behavior.platforms",
        "model",
        "model.label",
        "model.base_url",
        "model.model",
        "model.api_key_env",
        "model.params",
        "model.params.enable_thinking",
        "model.params.reasoning",
        "model.params.reasoning.enabled",
        "model.params.reasoning.effort",
        "model.params.provider",
        "model.params.provider.allow_fallbacks",
        "model.params.provider.data_collection",
        "model.pricing",
        "model.pricing.input_per_mtok",
        "model.pricing.output_per_mtok",
        "model.pricing.cached_per_mtok",
        "model.pricing.cache_write_per_mtok",
        "cta",
        "cta.direct",
        "cta.direct.instruction",
        "cta.direct.phrases",
        "cta.bio_link",
        "cta.bio_link.instruction",
        "cta.bio_link.phrases",
        "cta.bio_pointer",
        "cta.bio_pointer.instruction",
        "cta.bio_pointer.phrases",
        "bakeoff",
        "bakeoff.models",
        "bakeoff.models.label",
        "bakeoff.models.model",
        "bakeoff.models.params",
        "bakeoff.models.params.reasoning",
        "bakeoff.models.params.reasoning.enabled",
        "bakeoff.models.params.provider",
        "bakeoff.models.params.provider.allow_fallbacks",
        "bakeoff.models.params.provider.data_collection",
        "bakeoff.models.pricing",
        "bakeoff.models.pricing.input_per_mtok",
        "bakeoff.models.pricing.output_per_mtok",
        "bakeoff.models.pricing.cached_per_mtok",
        "bakeoff.models.pricing.cache_write_per_mtok",
        # Absent by default. A config with no [publish] table is a read only
        # deployment, which is the recommended starting point.
        "publish",
        "publish.platform",
        "publish.credential_env",
    }
)

CONFIG_FILES = sorted(REPO_ROOT.glob("examples/*/config.toml")) + sorted(
    REPO_ROOT.glob("tests/fixtures/*/config.toml")
)


def _lookup_keys(tree: ast.Module):
    """(line, name) for every string literal this module reads a value out of.

    A setting nothing reads changes nothing, so a bypass flag has to be read
    somewhere under src/ to do any harm. This finds the reading of it.

    Six shapes, not the four the mapping-only version had. os.getenv("auto_approve")
    and getattr(args, "auto_approve", False) both read a setting and neither is a
    mapping subscript, so an environment variable and a parsed argparse flag, which
    are the two most natural places to put a bypass, went past unseen.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            index = node.slice
            if isinstance(index, ast.Constant) and isinstance(index.value, str):
                yield node.lineno, index.value
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in ("get", "setdefault", "pop", "getenv") and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    yield node.lineno, first.value
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            # getattr(args, "yes", False) reads a flag off the parsed namespace,
            # and getenv/environ are the same idea through the process instead.
            if node.func.id in ("getattr", "hasattr") and len(node.args) >= 2:
                second = node.args[1]
                if isinstance(second, ast.Constant) and isinstance(second.value, str):
                    yield node.lineno, second.value
            elif node.func.id == "getenv" and node.args:
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


def _declared_schema() -> set[str]:
    from commentdraft.config import REQUIRED
    from commentdraft.platforms import CREDENTIAL_KEY, PLATFORM_KEY, PUBLISH_SECTION

    names = set(REQUIRED)
    names |= {f"{section}.{key}" for section, keys in REQUIRED.items() for key in keys}
    names |= {
        PUBLISH_SECTION,
        f"{PUBLISH_SECTION}.{PLATFORM_KEY}",
        f"{PUBLISH_SECTION}.{CREDENTIAL_KEY}",
    }
    return names


def _shipped_schema() -> set[str]:
    names: set[str] = set()
    for path in CONFIG_FILES:
        names |= set(_toml_keys(tomllib.loads(path.read_text(encoding="utf-8"))))
    names |= set(_toml_keys(tomllib.loads(MINIMAL_CONFIG_TOML)))
    return names


def test_the_config_vocabulary_is_exactly_the_reviewed_list() -> None:
    """The allowlist, and the one that matters in a year.

    Everything the denylist does is guess how somebody will spell an idea. It
    guessed eleven ways and missed `pre_approved`, which is what three separate
    reported bypasses used, and the repair for a missed guess is another guess.

    This asks the opposite question. Here is the entire vocabulary of the config
    format: every section and key the loader requires, the two the [publish]
    table is made of, and every key the shipped examples and the suite's own
    fixtures carry. A key of any name that is not on this list fails, whether it
    is called auto_approve, pre_approved, or something nobody has thought of yet,
    and the only way to add one is to write it down here where it gets read.

    Set equality in both directions. A key that disappears from the schema and
    stays on this list is a list rotting into decoration, which is exactly what
    happened to the guard this replaces.
    """
    observed = _declared_schema() | _shipped_schema()
    added = sorted(observed - CONFIG_SCHEMA)
    dropped = sorted(CONFIG_SCHEMA - observed)
    assert added == [], (
        "the config format grew a key nobody reviewed. Approval is a keystroke "
        f"against one reply and cannot be expressed in a file: {added}"
    )
    assert dropped == [], f"CONFIG_SCHEMA lists keys the config format no longer has: {dropped}"


def test_the_allowlist_refuses_a_key_the_denylist_never_matched() -> None:
    """The two guards, on the key that got past the one this replaces.

    `pre_approved` is now on the denylist as well, but the point of this test is
    the order of the arguments: the allowlist refuses it because it is not on the
    list, which is a property of the mechanism rather than of anybody having
    predicted the name.
    """
    unpredicted = "publish.pre_approved"
    assert unpredicted not in CONFIG_SCHEMA
    # And the denylist, second, now that it has been told about this one.
    assert BYPASS_KEY.search("pre_approved")


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


def _parser_names(parser, path: str = ""):
    """Every option string and positional dest in this parser and every one under it.

    Recursive, and it starts at the top. The version this replaces iterated
    subparsers.choices only, so `parser.add_argument("--yes", ...)` on the
    top-level parser was never scanned, and `commentdraft --yes publish` is the
    form an operator types first. It also assumed exactly one level of nesting,
    which is a thing that stops being true the day a subcommand grows one.
    """
    import argparse

    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, sub in action.choices.items():
                yield from _parser_names(sub, f"{path}{name} ")
            continue
        for option in action.option_strings:
            yield f"{path}{option}", option.lstrip("-")
        if not action.option_strings and action.dest:
            # A positional called `yes` is the same offence with the dashes off.
            yield f"{path}{action.dest}", action.dest


def test_no_command_offers_a_flag_that_could_stand_in_for_a_keystroke() -> None:
    """There is no --yes and no --all. Not defaulted off. Absent.

    A flag that exists is a flag somebody sets once, in a shell alias or a cron
    line, and forgets. The whole claim collapses the first time it is set on a
    machine nobody is watching, and nothing about the run afterwards looks wrong.
    """
    from commentdraft.cli import build_parser

    names = list(_parser_names(build_parser()))
    assert names, "the parser offers no arguments at all, so this test proves nothing"
    assert any(shown == "-h" for shown, _ in names), (
        "the top-level parser was not reached, which is where an operator types first"
    )
    assert any(shown.startswith("publish ") for shown, _ in names), (
        "the publish subcommand was not reached"
    )
    offenders = [shown for shown, bare in names if BYPASS_KEY.search(bare)]
    assert offenders == [], f"a command offers an approval bypass flag: {offenders}"


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
        # The one it missed. A review found that none of the eleven original
        # shapes matched this, and that it was the key three separate reported
        # bypasses reached for. The allowlist above is the durable answer; these
        # are here so the second signal knows about it too.
        "pre_approved",
        "pre-approved",
        "preapproved",
        "already_approved",
        "already_sent",
        "preconfirmed",
        "approval_file",
        "decision_column",
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
# Matched as dotted prefixes, not by exact name. `from urllib import request`
# records module "urllib" and alias "request", which is a bare "urllib" under an
# exact-match rule and passed; `from http import client` passed the same way. The
# transport layer is on the list for the same reason: banning http.client while
# leaving socket and ssl available bans one spelling of the capability.
BANNED_IMPORT_PREFIXES = {
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "urllib.request",
    "urllib.error",
    "http.client",
    "socket",
    "ssl",
    "ftplib",
    "smtplib",
    "telnetlib",
    "xmlrpc",
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

# The other half of the test this inherited, which was dropped with no successor
# while tests/test_generality.py went on describing the move as if both halves
# had made it. An import is one way to reach an API and a hostname in a string is
# the other, and the second one needs no dependency in pyproject.toml at all.
BANNED_HOSTS = (
    "googleapis.com",
    "youtube.com",
    "youtu.be",
    "graph.facebook.com",
    "facebook.com",
    "instagram.com",
    "tiktokapis.com",
    "tiktok.com",
    "api.twitter.com",
    "twitter.com",
    "reddit.com",
    "bsky.social",
    "linkedin.com",
    "threads.net",
)


def _imported_names(tree: ast.Module):
    """(line, dotted name) for every import, normalised so `from x import y` is x.y.

    Both forms are yielded for an ImportFrom: the module on its own and the
    module joined to each alias. `from urllib import request` has to be read as
    urllib.request, and `from googleapiclient import discovery` has to stay
    caught by the bare googleapiclient prefix.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.lineno, node.module
            for alias in node.names:
                yield node.lineno, f"{node.module}.{alias.name}"


def _banned_import(name: str) -> str:
    for prefix in BANNED_IMPORT_PREFIXES:
        if name == prefix or name.startswith(prefix + "."):
            return prefix
    return ""


def test_no_module_outside_the_connectors_can_reach_a_platform() -> None:
    """ui.py legitimately serves on localhost, so http.server and socketserver
    are fine and are not on the list. What may not exist outside platforms/ is a
    way to reach somebody else's API."""
    offenders = []
    for path in _module_paths():
        if CONNECTORS in path.parents:
            continue
        for line, name in _imported_names(_tree(path)):
            prefix = _banned_import(name)
            if prefix:
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{line}: {name} ({prefix})")
    assert offenders == [], f"a module outside platforms/ imports a network client: {offenders}"


def test_the_import_rule_reads_a_from_import_as_the_dotted_name(tmp_path: Path) -> None:
    """The exact-match hole, pinned. Both of these were legal under the old rule."""
    module = tmp_path / "sneaky.py"
    module.write_text("from urllib import request\nfrom http import client\n", encoding="utf-8")
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
    caught = {_banned_import(name) for _, name in _imported_names(tree)} - {""}
    assert caught == {"urllib.request", "http.client"}

    # And the ordinary neighbours of both are still allowed, or the rule would
    # ban the review page's own server and the URL parsing the engine does.
    module.write_text(
        "from urllib.parse import quote\nfrom http.server import ThreadingHTTPServer\n",
        encoding="utf-8",
    )
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
    assert {_banned_import(name) for _, name in _imported_names(tree)} == {""}


def test_no_module_outside_the_connectors_names_a_platform_host() -> None:
    """The half that was dropped. A hostname in a string needs no dependency.

    Scoped exactly like the import ban: a connector is a thing that talks to a
    platform and has to name one, and nothing else in the package may. This is
    what makes the network surface one directory a reviewer can read, rather than
    one directory plus whatever a string literal reaches.
    """
    offenders = []
    for path in _module_paths():
        if CONNECTORS in path.parents:
            continue
        for node in ast.walk(_tree(path)):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            lowered = node.value.casefold()
            for host in BANNED_HOSTS:
                if host in lowered:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}: {host}")
    assert offenders == [], f"a module outside platforms/ names a platform host: {offenders}"


def test_the_host_rule_catches_a_hostname_in_a_literal(tmp_path: Path) -> None:
    module = tmp_path / "hosty.py"
    module.write_text('URL = "https://www.googleapis.com/youtube/v3/comments"\n', encoding="utf-8")
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
    found = [
        host
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        for host in BANNED_HOSTS
        if host in node.value.casefold()
    ]
    assert "googleapis.com" in found


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

    with scripted_reviewer(read_key):
        counts = approve_and_publish(
            rows,
            {},
            platform,
            platform_name="video-site",
            config_label="config.toml",
            log_path=tmp_path / "published.jsonl",
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
