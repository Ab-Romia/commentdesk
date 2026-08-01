# SPDX-License-Identifier: Apache-2.0
"""Shared test paths and fixtures.

Paths are computed from this file, never from the working directory, so the suite
behaves the same under `pytest`, `pytest tests/some_test.py`, and an editor runner.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
PACKAGE_ROOT = SRC_ROOT / "commentdraft"

# A complete, valid config for a fictional product. Tests that need an invalid one
# edit a copy of this string, so a test never asserts against a config that quietly
# drifted away from the shape the loader accepts.
MINIMAL_CONFIG_TOML = """\
[product]
name = "The Backyard Forager's Field Guide"
kind = "field guide"
price_text = "$18"
purchase_link = "https://example.com/field-guide"
escalation_contact = "the team"

[knowledge]
source = "text"
path = "knowledge.md"

[voice]
rules = "prompts/voice.md"
examples = "prompts/examples.md"

[behavior]
cta_mode = "direct"
plug_cap = 0.75
max_reply_sentences = 2
bot_disclosure_text = "Replies are drafted with software and checked by a person before they post."
plug_markers = ["example.com/field-guide", "in the bio"]
banned_emoji = ""
separator = ", "
platforms = ["youtube", "tiktok"]

[cta.direct]
instruction = "If someone asks where to get it, give the link: {{purchase_link}}."
phrases = ["here is the link: {{purchase_link}}", "you can get it at {{purchase_link}}"]

[cta.bio_pointer]
instruction = "If someone asks where to get it, say the link is in the bio."
phrases = ["the link is in the bio", "you will find it in the profile"]

[model]
label = "primary"
base_url = "https://gateway.invalid/api/v1"
model = "vendor/model-a"
api_key_env = "COMMENTDRAFT_API_KEY"

[model.pricing]
input_per_mtok = 0.32
cached_per_mtok = 0.064
output_per_mtok = 1.28
cache_write_per_mtok = 0.4

[model.params]
reasoning = { enabled = false }
provider = { data_collection = "deny" }

[[bakeoff.models]]
label = "challenger"
model = "vendor/model-b"
pricing = { input_per_mtok = 0.09, cached_per_mtok = 0.018, output_per_mtok = 0.18, cache_write_per_mtok = 0.0 }
params = { reasoning = { enabled = false }, provider = { data_collection = "deny" } }
"""


@pytest.fixture
def repo_root() -> Path:
    """The checkout root."""
    return REPO_ROOT


@pytest.fixture
def package_root() -> Path:
    """The directory holding the packaged modules."""
    return PACKAGE_ROOT


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    """A valid config.toml written into its own directory.

    Written to tmp_path rather than pointing at examples/, because a test that
    edits one key must not be able to change what another test reads.
    """
    path = tmp_path / "config.toml"
    path.write_text(MINIMAL_CONFIG_TOML, encoding="utf-8")
    return path
