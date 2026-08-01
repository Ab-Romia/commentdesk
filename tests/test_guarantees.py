# SPDX-License-Identifier: Apache-2.0
"""The constitutional test: the engine holds no human-language copy.

Every string in this package is a machine token or English scaffolding: a JSON
key, a CSV header, a CLI flag, an error message for whoever runs the tool. All
copy that reaches a reader lives in files the operator writes, which is what lets
the same code serve a product in any language without a Python edit.

That rule is easy to state and easy to erode one convenient literal at a time,
usually while someone is debugging in a hurry. So it is checked mechanically.
ASCII-only is a proxy for it and a strict one: the moment copy in any other
script reaches a module the suite fails and names the line, which is exactly when
someone should be asked to move it into config instead.

Only string literals are checked, because those are what ship inside a prompt.
Comments are not AST nodes and are not scanned here.
"""

import ast
from pathlib import Path

import pytest

from conftest import PACKAGE_ROOT


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
