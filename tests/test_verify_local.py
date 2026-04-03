"""Regression coverage for the maintained local verification entrypoint."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = ROOT / "scripts" / "verify_local.sh"
README_PATH = ROOT / "README.md"
USAGE_PATH = ROOT / "docs" / "USAGE.md"
EXPECTED_COMMAND = "./scripts/verify_local.sh"


def test_verify_local_script_uses_repo_venv_commands() -> None:
    script = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "#!/usr/bin/env bash" in script
    assert "set -euo pipefail" in script
    assert "./venv/bin/python -m pytest tests -q" in script
    assert "./venv/bin/python -m ruff check javs tests" in script


def test_docs_reference_single_local_verification_entrypoint() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    usage = USAGE_PATH.read_text(encoding="utf-8")

    assert EXPECTED_COMMAND in readme
    assert EXPECTED_COMMAND in usage
