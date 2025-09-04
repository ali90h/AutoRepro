"""Golden tests for the plan command."""

from pathlib import Path

import pytest

from tests._golden_utils import (
    canon_json_bytes,
    canon_md,
    read,
    run_cli,
    unified_diff,
    write,
)

# Get golden directory path
GOLDEN_DIR = Path(__file__).parent / "golden"


@pytest.mark.parametrize("case", ["basic_pytest", "jest_watch", "ambiguous"])
def test_plan_golden(case: str, tmp_path):
    """Test plan command against golden files."""

    # Setup case directory with appropriate markers
    if case == "basic_pytest":
        write(tmp_path / "pyproject.toml", '[build-system]\nrequires = ["setuptools"]')
    elif case == "jest_watch":
        write(tmp_path / "package.json", '{"name": "test-project", "version": "1.0.0"}')
        write(tmp_path / "pnpm-lock.yaml", "{}")
    # ambiguous case has no markers

    # Copy description file to case directory
    desc_file = tmp_path / f"{case}.desc.txt"
    golden_desc = GOLDEN_DIR / "plan" / f"{case}.desc.txt"
    desc_file.write_text(golden_desc.read_text())

    # Test Markdown output
    stdout, stderr, code = run_cli(["plan", "--file", str(desc_file), "--out", "-"], tmp_path)
    assert code == 0, f"Command failed with stderr: {stderr}"

    actual_md = canon_md(stdout)
    expected_md = canon_md(read(GOLDEN_DIR / "plan" / f"{case}.expected.md"))

    if actual_md != expected_md:
        diff = unified_diff(expected_md, actual_md, "expected.md", "actual.md")
        raise AssertionError(f"MD mismatch for {case}\n{diff}")

    # Test JSON output
    stdout, stderr, code = run_cli(
        ["plan", "--file", str(desc_file), "--format", "json", "--out", "-"], tmp_path
    )
    assert code == 0, f"Command failed with stderr: {stderr}"

    actual_json = canon_json_bytes(stdout.encode("utf-8"))
    expected_json = canon_json_bytes(
        read(GOLDEN_DIR / "plan" / f"{case}.expected.json").encode("utf-8")
    )

    if actual_json != expected_json:
        diff = unified_diff(
            expected_json + "\n", actual_json + "\n", "expected.json", "actual.json"
        )
        raise AssertionError(f"JSON mismatch for {case}\n{diff}")


def test_plan_basic_pytest_assertions():
    """Test specific assertions for basic_pytest case."""
    expected_md = read(GOLDEN_DIR / "plan" / "basic_pytest.expected.md")

    # MD sections in order
    assert "# " in expected_md  # Title
    assert "## Assumptions" in expected_md
    assert "## Candidate Commands" in expected_md
    assert "## Needed Files/Env" in expected_md
    assert "## Next Steps" in expected_md

    # Should include pytest -q
    assert "pytest -q" in expected_md

    # Test JSON structure
    expected_json_str = read(GOLDEN_DIR / "plan" / "basic_pytest.expected.json")
    import json

    expected_json = json.loads(expected_json_str)

    # JSON top-level keys
    assert "title" in expected_json
    assert "assumptions" in expected_json
    assert "needs" in expected_json
    assert "commands" in expected_json
    assert "next_steps" in expected_json

    # commands[0].cmd contains pytest -q
    assert any("pytest -q" in cmd["cmd"] for cmd in expected_json["commands"])


def test_plan_jest_watch_assertions():
    """Test specific assertions for jest_watch case."""
    expected_md = read(GOLDEN_DIR / "plan" / "jest_watch.expected.md")

    # Should include npm test or jest commands
    has_npm_test = "npm test" in expected_md
    has_jest = "jest" in expected_md
    assert has_npm_test or has_jest, "Should include npm test or jest commands"

    # Test JSON structure
    expected_json_str = read(GOLDEN_DIR / "plan" / "jest_watch.expected.json")
    import json

    expected_json = json.loads(expected_json_str)

    # First command should reference jest, npm test, or vitest
    if expected_json["commands"]:
        first_cmd = expected_json["commands"][0]["cmd"]
        has_relevant = any(word in first_cmd.lower() for word in ["jest", "npm test", "vitest"])
        assert has_relevant, f"First command should reference jest/npm test/vitest: {first_cmd}"


def test_plan_ambiguous_assertions():
    """Test specific assertions for ambiguous case."""
    expected_md = read(GOLDEN_DIR / "plan" / "ambiguous.expected.md")

    # Should have assumptions with OS/version defaults
    assert "## Assumptions" in expected_md

    # Commands should be short (≤ 3) and generic
    command_lines = [
        line for line in expected_md.split("\n") if " — " in line and not line.startswith("#")
    ]
    assert len(command_lines) <= 3, f"Should have ≤ 3 commands, got {len(command_lines)}"

    # Test JSON structure
    expected_json_str = read(GOLDEN_DIR / "plan" / "ambiguous.expected.json")
    import json

    expected_json = json.loads(expected_json_str)

    # Should have assumptions with default environment info
    assumptions = expected_json.get("assumptions", [])
    assert len(assumptions) > 0, "Should have assumptions"
