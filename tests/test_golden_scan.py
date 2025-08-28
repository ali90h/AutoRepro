"""Golden tests for the scan command."""

import json
from pathlib import Path

import pytest

from tests._golden_utils import canon_md, read, run_cli, unified_diff, write

# Get golden directory path
GOLDEN_DIR = Path(__file__).parent / "golden"


def normalize_scan_json(json_str: str, cwd: Path) -> str:
    """Normalize JSON output by replacing absolute root path with relative."""
    obj = json.loads(json_str)
    # Replace absolute root with relative path
    if "root" in obj:
        obj["root"] = "."
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


@pytest.mark.parametrize(
    "case,text_expected",
    [
        ("empty", True),
        ("python_pyproject", True),
        ("node_lock", True),
        ("mixed_py_node", True),
        ("glob_only", False),  # no text output for this case
    ],
)
def test_scan_golden(case: str, text_expected: bool, tmp_path):
    """Test scan command against golden files."""

    # Setup case directory with appropriate markers
    if case == "python_pyproject":
        write(tmp_path / "pyproject.toml", '[build-system]\nrequires = ["setuptools"]')
    elif case == "node_lock":
        write(tmp_path / "pnpm-lock.yaml", "{}")
    elif case == "mixed_py_node":
        write(tmp_path / "pyproject.toml", '[build-system]\nrequires = ["setuptools"]')
        write(tmp_path / "pnpm-lock.yaml", "{}")
    elif case == "glob_only":
        write(tmp_path / "a.py", 'print("hello")')
    # empty case has no markers

    # Test text output if expected
    if text_expected:
        stdout, stderr, code = run_cli(["scan"], tmp_path)
        assert code == 0, f"Command failed with stderr: {stderr}"

        actual_text = canon_md(stdout)
        expected_text = canon_md(read(GOLDEN_DIR / "scan" / f"{case}.expected.txt"))

        if actual_text != expected_text:
            diff = unified_diff(expected_text, actual_text, "expected.txt", "actual.txt")
            raise AssertionError(f"Text mismatch for {case}\n{diff}")

    # Test JSON output
    stdout, stderr, code = run_cli(["scan", "--json"], tmp_path)
    assert code == 0, f"Command failed with stderr: {stderr}"

    actual_json = normalize_scan_json(stdout, tmp_path)
    expected_json = normalize_scan_json(
        read(GOLDEN_DIR / "scan" / f"{case}.expected.json"), tmp_path
    )

    if actual_json != expected_json:
        diff = unified_diff(
            expected_json + "\n", actual_json + "\n", "expected.json", "actual.json"
        )
        raise AssertionError(f"JSON mismatch for {case}\n{diff}")


def test_scan_empty_assertions():
    """Test specific assertions for empty case."""
    expected_text = read(GOLDEN_DIR / "scan" / "empty.expected.txt")
    assert expected_text.strip() == "No known languages detected."

    expected_json_str = read(GOLDEN_DIR / "scan" / "empty.expected.json")
    expected_json = json.loads(expected_json_str)

    assert expected_json["detected"] == []
    assert expected_json["languages"] == {}


def test_scan_python_pyproject_assertions():
    """Test specific assertions for python_pyproject case."""
    expected_json_str = read(GOLDEN_DIR / "scan" / "python_pyproject.expected.json")
    expected_json = json.loads(expected_json_str)

    assert "python" in expected_json["detected"]
    assert expected_json["languages"]["python"]["score"] == 3
    assert expected_json["languages"]["python"]["reasons"][0]["kind"] == "config"


def test_scan_node_lock_assertions():
    """Test specific assertions for node_lock case."""
    expected_json_str = read(GOLDEN_DIR / "scan" / "node_lock.expected.json")
    expected_json = json.loads(expected_json_str)

    assert "node" in expected_json["detected"]
    assert expected_json["languages"]["node"]["score"] == 4
    assert expected_json["languages"]["node"]["reasons"][0]["kind"] == "lock"


def test_scan_mixed_py_node_assertions():
    """Test specific assertions for mixed_py_node case."""
    expected_json_str = read(GOLDEN_DIR / "scan" / "mixed_py_node.expected.json")
    expected_json = json.loads(expected_json_str)

    # Node score (4) > Python score (3)
    assert "node" in expected_json["detected"]
    assert "python" in expected_json["detected"]
    node_score = expected_json["languages"]["node"]["score"]
    python_score = expected_json["languages"]["python"]["score"]
    assert node_score > python_score


def test_scan_glob_only_assertions():
    """Test specific assertions for glob_only case."""
    expected_json_str = read(GOLDEN_DIR / "scan" / "glob_only.expected.json")
    expected_json = json.loads(expected_json_str)

    assert "python" in expected_json["detected"]
    assert expected_json["languages"]["python"]["score"] == 1
    assert expected_json["languages"]["python"]["reasons"][0]["kind"] == "source"
