#!/usr/bin/env python3
"""
Behavioral validation script to ensure no regressions after refactoring.
Compares current CLI output with baseline outputs.
"""

import difflib
import json
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str]) -> str:
    """Run a command and return its stdout."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True, cwd=Path(__file__).parent.parent.parent
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {' '.join(cmd)}")
        print(f"Exit code: {e.returncode}")
        print(f"Stderr: {e.stderr}")
        raise


def compare_json_outputs(baseline_file: str, current_output: str, test_name: str) -> bool:
    """Compare JSON outputs, ignoring whitespace differences."""
    baseline_path = Path(__file__).parent / baseline_file

    if not baseline_path.exists():
        print(f"❌ {test_name}: Baseline file {baseline_file} not found")
        return False

    with open(baseline_path) as f:
        baseline_content = f.read().strip()

    try:
        baseline_json = json.loads(baseline_content)
        current_json = json.loads(current_output.strip())

        if baseline_json == current_json:
            print(f"✅ {test_name}: JSON outputs match")
            return True
        else:
            print(f"❌ {test_name}: JSON outputs differ")
            print("Baseline:", json.dumps(baseline_json, indent=2)[:200] + "...")
            print("Current:", json.dumps(current_json, indent=2)[:200] + "...")
            return False

    except json.JSONDecodeError as e:
        print(f"❌ {test_name}: JSON decode error - {e}")
        return False


def compare_text_outputs(baseline_file: str, current_output: str, test_name: str) -> bool:
    """Compare text outputs line by line."""
    baseline_path = Path(__file__).parent / baseline_file

    if not baseline_path.exists():
        print(f"❌ {test_name}: Baseline file {baseline_file} not found")
        return False

    with open(baseline_path) as f:
        baseline_lines = f.read().strip().splitlines()

    current_lines = current_output.strip().splitlines()

    if baseline_lines == current_lines:
        print(f"✅ {test_name}: Text outputs match")
        return True
    else:
        print(f"❌ {test_name}: Text outputs differ")
        diff = difflib.unified_diff(
            baseline_lines, current_lines, fromfile="baseline", tofile="current", lineterm=""
        )
        for line in list(diff)[:10]:  # Show first 10 diff lines
            print(line)
        if len(list(difflib.unified_diff(baseline_lines, current_lines))) > 10:
            print("... (diff truncated)")
        return False


def test_scan_json():
    """Test scan command JSON output."""
    current = run_command(["python", "-m", "autorepro", "scan", "--json"])
    return compare_json_outputs("baseline_scan.json", current, "Scan JSON")


def test_plan_json():
    """Test plan command JSON output."""
    current = run_command(
        [
            "python",
            "-m",
            "autorepro",
            "plan",
            "--desc",
            "pytest failing tests",
            "--format",
            "json",
            "--out",
            "-",
        ]
    )
    return compare_json_outputs("baseline_plan.json", current, "Plan JSON")


def test_plan_markdown():
    """Test plan command markdown output."""
    current = run_command(
        ["python", "-m", "autorepro", "plan", "--desc", "npm test failing in CI", "--dry-run"]
    )
    return compare_text_outputs("baseline_plan.md", current, "Plan Markdown")


def test_init_output():
    """Test init command output."""
    current = run_command(["python", "-m", "autorepro", "init", "--dry-run"])
    return compare_text_outputs("baseline_init.txt", current, "Init Output")


def test_help_output():
    """Test help command output."""
    current = run_command(["python", "-m", "autorepro", "--help"])
    return compare_text_outputs("baseline_help.txt", current, "Help Output")


def main():
    """Run all behavioral validation tests."""
    print("🔍 Running behavioral validation tests...")
    print("=" * 60)

    tests = [
        test_help_output,
        test_scan_json,
        test_plan_json,
        test_plan_markdown,
        test_init_output,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ {test_func.__name__}: Exception - {e}")
            failed += 1
        print()

    print("=" * 60)
    print(f"📊 Results: {passed} passed, {failed} failed")

    if failed > 0:
        print("❌ Behavioral validation FAILED")
        sys.exit(1)
    else:
        print("✅ All behavioral validation tests PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
