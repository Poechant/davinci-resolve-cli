"""AC17 — SKILL.md frontmatter sanity + example coverage."""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

SKILL_PATH = Path(__file__).resolve().parents[2] / "SKILL.md"


@pytest.fixture(scope="module")
def skill_text() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def frontmatter(skill_text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---\n", skill_text, flags=re.DOTALL)
    assert m, "SKILL.md must start with a YAML frontmatter block delimited by ---"
    return yaml.safe_load(m.group(1))


def test_frontmatter_has_required_fields(frontmatter: dict) -> None:
    assert frontmatter["name"] == "davinci-resolve-cli"
    assert isinstance(frontmatter.get("description"), str) and len(frontmatter["description"]) > 40
    assert frontmatter.get("binary") == "dvr"


def test_skill_lists_five_example_tasks(skill_text: str) -> None:
    # Headings start with "### N. "
    examples = re.findall(r"^### \d+\. ", skill_text, flags=re.MULTILINE)
    assert len(examples) == 5, f"expected 5 example tasks, got {len(examples)}"


def test_skill_mentions_all_command_domains(skill_text: str) -> None:
    for domain in ("doctor", "project", "media", "render", "timeline"):
        assert f"`{domain}" in skill_text or f"`dvr {domain}" in skill_text, f"missing mention of {domain}"


def test_skill_documents_error_codes(skill_text: str) -> None:
    for code in (
        "resolve_not_running",
        "version_unsupported",
        "api_unavailable",
        "validation_error",
        "not_found",
        "api_call_failed",
    ):
        assert code in skill_text, f"missing error code reference: {code}"


def test_skill_documents_exit_codes(skill_text: str) -> None:
    assert "Exit code 0" in skill_text or "exit code 0" in skill_text.lower()
    for code in ("0", "1", "2", "3"):
        assert code in skill_text


def test_skill_examples_use_format_json(skill_text: str) -> None:
    assert skill_text.count("--format json") >= 5
