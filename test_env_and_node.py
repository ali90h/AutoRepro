#!/usr/bin/env python3
"""Test the new env presence and node keywords tests manually."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def run_cli(cwd, *args):
    """Helper function to run autorepro plan CLI with subprocess."""
    env = os.environ.copy()
    current_dir = os.getcwd()
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = f"{current_dir}:{env['PYTHONPATH']}"
    else:
        env["PYTHONPATH"] = current_dir

    return subprocess.run(
        [sys.executable, "-m", "autorepro.cli", "plan", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        env=env,
    )


def test_plan_infers_env_presence():
    """Test that plan infers devcontainer presence in Needed Files/Env."""
    print("Testing plan infers env presence...")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Create .devcontainer/devcontainer.json
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        (devcontainer_dir / "devcontainer.json").write_text("{}")

        # Run with --desc "anything"
        result = run_cli(tmp_path, "--desc", "anything")

        print(f"Return code: {result.returncode}")

        # Should succeed
        assert result.returncode == 0, (
            f"Expected success, got {result.returncode}. STDERR: {result.stderr}"
        )

        # Assert repro.md contains devcontainer: present in Needed Files/Env
        repro_file = tmp_path / "repro.md"
        assert repro_file.exists(), "repro.md should be created"

        content = repro_file.read_text()
        print(f"Content preview: {content[:300]}...")
        assert "## Needed Files/Env" in content, "Should have Needed Files/Env section"
        assert "devcontainer: present" in content, "Should indicate devcontainer is present"

        # Show the specific line
        lines = content.split("\n")
        env_section_found = False
        for line in lines:
            if line == "## Needed Files/Env":
                env_section_found = True
            elif env_section_found and "devcontainer:" in line:
                print(f"Found devcontainer line: {line}")
                break

        print("✓ test_plan_infers_env_presence passed")


def test_plan_node_keywords():
    """Test that plan detects Node keywords and suggests appropriate commands."""
    print("\nTesting plan node keywords...")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Create package.json
        package_json = {"name": "x", "scripts": {"test": "jest"}}
        (tmp_path / "package.json").write_text(f"{package_json}".replace("'", '"'))

        # Run with --desc "tests failing on jest"
        result = run_cli(tmp_path, "--desc", "tests failing on jest")

        print(f"Return code: {result.returncode}")

        # Should succeed
        assert result.returncode == 0, (
            f"Expected success, got {result.returncode}. STDERR: {result.stderr}"
        )

        # Assert output contains either npm test -s or npx jest -w=1
        repro_file = tmp_path / "repro.md"
        assert repro_file.exists(), "repro.md should be created"

        content = repro_file.read_text()
        print(f"Content preview: {content[:300]}...")
        assert "## Candidate Commands" in content, "Should have Candidate Commands section"

        # Should contain either npm test -s or npx jest -w=1
        has_npm_test = "npm test -s" in content
        has_npx_jest = "npx jest -w=1" in content
        print(f"Has npm test -s: {has_npm_test}")
        print(f"Has npx jest -w=1: {has_npx_jest}")

        assert has_npm_test or has_npx_jest, (
            f"Should contain either 'npm test -s' or 'npx jest -w=1' in content: {content}"
        )

        # Show the commands section
        lines = content.split("\n")
        commands_section_found = False
        for line in lines:
            if line == "## Candidate Commands":
                commands_section_found = True
            elif commands_section_found and line.strip() and not line.startswith("#"):
                if "npm test" in line or "jest" in line:
                    print(f"Found command line: {line}")

        print("✓ test_plan_node_keywords passed")


def main():
    """Run all tests."""
    try:
        test_plan_infers_env_presence()
        test_plan_node_keywords()
        print("\n🎉 All new CLI tests passed!")
        return True
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
