#!/usr/bin/env python3
"""Regold script to regenerate golden test files."""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def run_cli(args, cwd):
    """Run autorepro CLI command."""
    import os

    # Get the autorepro root directory (parent of scripts/)
    autorepro_root = Path(__file__).parent.parent

    # Set up environment with PYTHONPATH
    env = os.environ.copy()
    env["PYTHONPATH"] = str(autorepro_root)

    cmd = [sys.executable, "-m", "autorepro"] + args
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)


def canon_json_bytes(b):
    """Canonicalize JSON bytes."""
    obj = json.loads(b.decode("utf-8"))
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def ensure_trailing_newline(content):
    """Ensure content ends with exactly one newline."""
    return content.rstrip() + "\n"


def normalize_scan_json(json_str, cwd):
    """Normalize scan JSON by replacing absolute root with relative."""
    obj = json.loads(json_str)
    if "root" in obj:
        obj["root"] = "."
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _setup_plan_test_case(tmp_path, case):
    """Setup test case directory with appropriate markers."""
    if case == "basic_pytest":
        (tmp_path / "pyproject.toml").write_text(
            '[build-system]\nrequires = ["setuptools"]'
        )
    elif case == "jest_watch":
        (tmp_path / "package.json").write_text(
            '{"name": "test-project", "version": "1.0.0"}'
        )
        (tmp_path / "pnpm-lock.yaml").write_text("{}")
    # ambiguous case has no markers


def _process_plan_markdown(case, temp_desc, tmp_path, plan_dir, write):
    """Process markdown generation for plan case."""
    result = run_cli(["plan", "--file", str(temp_desc), "--out", "-"], tmp_path)
    if result.returncode != 0:
        print(f"Error generating MD for {case}: {result.stderr}")
        return False

    md_content = ensure_trailing_newline(result.stdout)
    expected_md = plan_dir / f"{case}.expected.md"

    if write:
        expected_md.write_text(md_content)
        print(f"  Updated {expected_md}")
    else:
        if expected_md.exists():
            existing = expected_md.read_text()
            if existing != md_content:
                print(f"  MD differs for {case}")
        else:
            print(f"  MD missing for {case}")

    return True


def _process_plan_json(case, temp_desc, tmp_path, plan_dir, write):
    """Process JSON generation for plan case."""
    result = run_cli(
        ["plan", "--file", str(temp_desc), "--format", "json", "--out", "-"],
        tmp_path,
    )
    if result.returncode != 0:
        print(f"Error generating JSON for {case}: {result.stderr}")
        return False

    json_content = canon_json_bytes(result.stdout.encode("utf-8")) + "\n"
    expected_json = plan_dir / f"{case}.expected.json"

    if write:
        expected_json.write_text(json_content)
        print(f"  Updated {expected_json}")
    else:
        if expected_json.exists():
            existing = (
                canon_json_bytes(expected_json.read_text().encode("utf-8")) + "\n"
            )
            if existing != json_content:
                print(f"  JSON differs for {case}")
        else:
            print(f"  JSON missing for {case}")

    return True


def regold_plan(golden_dir, write=False):
    """Regenerate plan golden files."""
    plan_dir = golden_dir / "plan"
    cases = ["basic_pytest", "jest_watch", "ambiguous"]

    for case in cases:
        desc_file = plan_dir / f"{case}.desc.txt"
        if not desc_file.exists():
            print(f"Skipping {case}: {desc_file} not found")
            continue

        print(f"Processing plan case: {case}")

        # Create temporary directory with appropriate markers
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Setup case directory with appropriate markers
            _setup_plan_test_case(tmp_path, case)

            # Copy desc file to temp directory
            temp_desc = tmp_path / f"{case}.desc.txt"
            temp_desc.write_text(desc_file.read_text())

            # Generate markdown
            if not _process_plan_markdown(case, temp_desc, tmp_path, plan_dir, write):
                continue

            # Generate JSON
            _process_plan_json(case, temp_desc, tmp_path, plan_dir, write)


def _setup_scan_test_case(tmp_path, files):
    """Setup scan test case directory with specified files."""
    for filename, content in files.items():
        (tmp_path / filename).write_text(content)


def _process_scan_text(case, tmp_path, scan_dir, write):
    """Process text output generation for scan case."""
    result = run_cli(["scan"], tmp_path)
    if result.returncode != 0:
        print(f"Error generating text for {case}: {result.stderr}")
        return False

    text_content = ensure_trailing_newline(result.stdout)
    expected_txt = scan_dir / f"{case}.expected.txt"

    if write:
        expected_txt.write_text(text_content)
        print(f"  Updated {expected_txt}")
    else:
        if expected_txt.exists():
            existing = expected_txt.read_text()
            if existing != text_content:
                print(f"  Text differs for {case}")
        else:
            print(f"  Text missing for {case}")

    return True


def _process_scan_json(case, tmp_path, scan_dir, write):
    """Process JSON output generation for scan case."""
    result = run_cli(["scan", "--json"], tmp_path)
    if result.returncode != 0:
        print(f"Error generating JSON for {case}: {result.stderr}")
        return False

    # Normalize the JSON (remove absolute paths)
    json_content = normalize_scan_json(result.stdout, tmp_path) + "\n"
    expected_json = scan_dir / f"{case}.expected.json"

    if write:
        expected_json.write_text(json_content)
        print(f"  Updated {expected_json}")
    else:
        if expected_json.exists():
            existing = normalize_scan_json(expected_json.read_text(), tmp_path) + "\n"
            if existing != json_content:
                print(f"  JSON differs for {case}")
        else:
            print(f"  JSON missing for {case}")

    return True


def regold_scan(golden_dir, write=False):
    """Regenerate scan golden files."""
    scan_dir = golden_dir / "scan"
    cases = {
        "empty": {},
        "python_pyproject": {
            "pyproject.toml": '[build-system]\nrequires = ["setuptools"]'
        },
        "node_lock": {"pnpm-lock.yaml": "{}"},
        "mixed_py_node": {
            "pyproject.toml": '[build-system]\nrequires = ["setuptools"]',
            "pnpm-lock.yaml": "{}",
        },
        "glob_only": {"a.py": 'print("hello")'},
    }

    for case, files in cases.items():
        print(f"Processing scan case: {case}")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Create files for this case
            _setup_scan_test_case(tmp_path, files)

            # Generate text output (if not glob_only)
            if case != "glob_only":
                if not _process_scan_text(case, tmp_path, scan_dir, write):
                    continue

            # Generate JSON output
            _process_scan_json(case, tmp_path, scan_dir, write)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Regenerate golden test files")
    parser.add_argument(
        "--write", action="store_true", help="Actually write files (default: dry run)"
    )
    args = parser.parse_args()

    # Find golden directory relative to script location
    script_dir = Path(__file__).parent
    golden_dir = script_dir.parent / "tests" / "golden"

    if not golden_dir.exists():
        print(f"Golden directory not found: {golden_dir}")
        return 1

    print(f"Golden directory: {golden_dir}")
    print(f"Write mode: {args.write}")
    print()

    regold_plan(golden_dir, args.write)
    print()
    regold_scan(golden_dir, args.write)

    if not args.write:
        print()
        print("Run with --write to actually update files")

    return 0


if __name__ == "__main__":
    sys.exit(main())
