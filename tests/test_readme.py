# SPDX-License-Identifier: Apache-2.0
"""The README makes promises. These tests keep it from making the wrong ones.

Every claim checked here is one that would be expensive to walk back after the
repository is public: an overstated capability, a limiter that is really an alarm,
or a credit owed to another project.
"""

import json
import re
import shlex
import shutil
import subprocess
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"

# Words that would each make a claim this project cannot support. "integrat" covers
# integrate/integration/integrates: there is nothing to integrate with, by design.
FORBIDDEN = [
    r"\bbots?\b",
    r"\bauto-?repl(y|ies)\b",
    r"\bengagement\b",
    r"\bgrowth\b",
    r"\bautonomous(ly)?\b",
    r"\bguardrails?\b",
    r"\bcheapest\b",
    r"integrat",
]


@pytest.fixture(scope="module")
def text():
    return README.read_text(encoding="utf-8")


def test_readme_is_ascii(text):
    bad = [(i + 1, line) for i, line in enumerate(text.splitlines()) if not line.isascii()]
    assert bad == [], f"non-ascii in README at lines {[n for n, _ in bad]}"


def test_readme_has_no_dash_typography(text):
    # The tool strips these from replies. The README does not get to print them.
    # Built from chr(), on the same rule as test_examples.py's em-dash check, so
    # this file stays free of the very characters it is checking for.
    assert chr(0x2014) not in text  # em dash
    assert chr(0x2013) not in text  # en dash


def test_readme_makes_no_claim_it_cannot_support(text):
    lower = text.lower()
    hits = [pat for pat in FORBIDDEN if re.search(pat, lower)]
    assert hits == [], f"README uses forbidden claim language: {hits}"


def test_readme_never_says_plug_cap_limits_anything(text):
    assert "`plug_cap` is an alarm threshold" in text
    for sentence in re.findall(r"[^.\n]*plug_cap[^.\n]*", text):
        assert not re.search(r"\blimits\b|\benforces\b|\bcaps\b|\bprevents\b", sentence), (
            f"plug_cap described as a limiter: {sentence.strip()!r}"
        )


def test_readme_states_the_grep_checkable_guarantee(text):
    """The README dares the reader to grep for a platform client. Quoting the word
    "grep" is not evidence; running the exact command the prose shows is. The
    pattern is extracted from the README itself, not copied here by hand, so a
    pattern loosened in a future edit fails this test instead of sliding through.
    """
    assert "There is no code path that posts" in text
    # The grep lives inside a bullet, so its fenced block is indented.
    match = re.search(r"```bash\n[ \t]*(grep[^\n]+)\n", text)
    assert match, "no grep command found in the README"
    # Tokenized and run without a shell: the command comes from this repository's
    # own README, not from anything external, but there is no reason to hand a
    # shell a string to parse when shlex can hand subprocess a plain argv list.
    argv = shlex.split(match.group(1))
    assert argv[0] == "grep", f"expected the README's command to start with grep: {argv!r}"
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.stdout == "", f"the README's own grep command found something: {result.stdout}"
    assert result.returncode == 1, (
        f"expected the grep to match nothing (exit 1), got exit {result.returncode}: "
        f"{result.stderr}"
    )


def test_readme_credits_promptfoo(text):
    assert "promptfoo" in text


def test_readme_badges_are_reference_style_and_defined_at_the_bottom(text):
    used = set()
    for m in re.finditer(r"\[!\[[^\]]+\]\[([a-z-]+)\]\]\[([a-z-]+)\]", text):
        used.update(m.groups())
    assert used, "no reference-style badges found"

    defined = {m.group(1) for m in re.finditer(r"(?m)^\[([a-z-]+)\]:\s+\S+$", text)}
    assert used <= defined, f"badge labels with no definition: {sorted(used - defined)}"

    first_def = min(text.index(f"[{label}]:") for label in defined)
    assert first_def > text.index("## License"), "badge definitions must sit at the bottom"


def test_readme_quickstart_paths_exist(text):
    example = ROOT / "examples" / "field-guide-book"
    for rel in (
        "config.toml",
        "comments.csv",
        "knowledge.md",
        "prompts/voice.md",
        "prompts/examples.md",
    ):
        assert (example / rel).exists(), f"README quickstart references a missing {rel}"
    assert "examples/field-guide-book" in text


def test_readme_screenshot_target_directory_exists():
    assert (ROOT / "docs" / "img").is_dir()


# --- The quickstart is not prose about a command. It is a command. ---------------
#
# Everything below parses the actual `commentdesk ...` lines out of the walkthrough
# and either runs them for real (offline, against the shipped example, with a fake
# model client) or feeds them to the real argument parser. A flag that got renamed
# in the code and never updated here is exactly the kind of drift that makes a
# skeptical reader stop trusting the rest of the page.


def _section(text: str, start_heading: str, end_heading: str) -> str:
    part = text.split(start_heading, 1)[1]
    return part.split(end_heading, 1)[0]


def _bash_blocks(section: str) -> list[str]:
    blocks = re.findall(r"```bash\n(.*?)```", section, re.DOTALL)
    assert blocks, "expected at least one bash block in the walkthrough section"
    return blocks


def _commentdesk_invocations(block: str) -> list[list[str]]:
    """Every `commentdesk ...` line in a code block, tokenized, minus the program name.

    Trailing `# comment` text is stripped first: several lines in the walkthrough
    carry an explanatory comment after the real command.
    """
    invocations = []
    for raw_line in block.splitlines():
        line = raw_line.split(" #", 1)[0].rstrip()
        if line.strip().startswith("commentdesk "):
            tokens = shlex.split(line)
            invocations.append(tokens[1:])
    return invocations


class _FakeCompletions:
    """Stands in for the SDK surface the engine uses, offline and keyless.

    Mirrors tests/test_pipeline_e2e.py's fake client: one canned decision, replayed
    for every row past the first, so a comments file with more rows than canned
    responses still runs end to end.
    """

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        index = min(len(self.calls) - 1, len(self.responses) - 1)
        first = len(self.calls) == 1
        usage = types.SimpleNamespace(
            prompt_tokens=1000,
            completion_tokens=10,
            prompt_tokens_details=types.SimpleNamespace(
                cached_tokens=0 if first else 900, cache_write_tokens=900 if first else 0
            ),
        )
        message = types.SimpleNamespace(content=self.responses[index])
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)], usage=usage)


def test_readme_quickstart_invocations_parse_as_real_cli_commands(text):
    """Every commentdesk command shown between the two headings must be one the
    real argument parser accepts. This is what catches a renamed or removed flag
    that the prose never got updated to match.
    """
    from commentdesk.cli import HANDLERS, build_parser

    section = _section(text, "## The whole thing, end to end", "## Three concepts")
    invocations = [
        argv for block in _bash_blocks(section) for argv in _commentdesk_invocations(block)
    ]
    assert len(invocations) >= 6, "expected run, review (x2), chat, ui, ingest and bakeoff"

    parser = build_parser()
    for argv in invocations:
        parsed = parser.parse_args(argv)
        assert parsed.command in HANDLERS


def test_readme_run_and_review_commands_actually_produce_the_files_they_claim(
    text, monkeypatch, tmp_path
):
    """The two commands the walkthrough shows running are executed for real,
    offline, against the shipped field-guide-book example with a fake model
    client. If `--out` ever stopped meaning "a directory" and `review.html`
    stopped being the fixed filename inside it, this fails.
    """
    from commentdesk import cli

    section = _section(text, "## The whole thing, end to end", "## Three concepts")
    blocks = _bash_blocks(section)

    quickstart_invocations = _commentdesk_invocations(blocks[0])
    assert len(quickstart_invocations) == 2, "expected exactly a run and a review command"
    run_argv, review_argv = quickstart_invocations
    assert run_argv[0] == "run"
    assert review_argv[0] == "review"

    (approved_argv,) = _commentdesk_invocations(blocks[1])
    assert approved_argv[0] == "review"
    assert "--approved" in approved_argv

    product = tmp_path / "field-guide-book"
    shutil.copytree(ROOT / "examples" / "field-guide-book", product)
    monkeypatch.chdir(product)
    monkeypatch.setenv("OPENROUTER_API_KEY", "not-a-real-key")

    canned = json.dumps({"decision": "skip", "reason": "quickstart smoke test", "reply_text": ""})
    fake_client = types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=_FakeCompletions([canned]))
    )
    monkeypatch.setattr(cli, "make_client", lambda model_cfg: fake_client)

    assert cli.main(run_argv) == 0
    review_csv = product / "out" / "review.csv"
    assert review_csv.exists(), "README says `run` writes out/review.csv"

    assert cli.main(review_argv) == 0
    review_html = product / "out" / "review.html"
    assert review_html.exists(), "README says `review` writes out/review.html"
    draft_page = review_html.read_text(encoding="utf-8")
    assert "DRAFT" in draft_page, "the page should carry a banner before --approved"

    assert cli.main(approved_argv) == 0
    approved_page = review_html.read_text(encoding="utf-8")
    assert "DRAFT" not in approved_page, "--approved should drop the draft banner"


def test_readme_carries_the_four_legal_blocks(text):
    for heading in (
        "## What this does, and what it does not do",
        "## What you supply",
        "## Transparency",
        "## About any cost figures",
    ):
        assert heading in text, f"README is missing the block: {heading}"


def test_readme_disclaims_affiliation(text):
    assert "not affiliated with" in text.lower()


def test_readme_puts_responsibility_for_the_source_document_on_the_operator(text):
    section = text.split("## What you supply", 1)[1].split("\n## ", 1)[0]
    assert "you have the right" in section.lower()
    assert "does not check" in section.lower()


def test_the_legal_blocks_sit_above_the_origin_note(text):
    # An origin note is a story. These are terms. Terms come first.
    assert text.index("## What this does, and what it does not do") < text.index(
        "## Where this came from"
    )
