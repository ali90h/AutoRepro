"""Test message consistency and --out - behavior.

Tests that:
1. Messages are consistent across init/plan commands
2. --out - prints only content and ignores --force
"""

import subprocess
import sys


def run_cli_subprocess(args, cwd=None):
    """Run autorepro CLI via subprocess."""
    cmd = [sys.executable, "-m", "autorepro.cli"] + args
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=30)


class TestMessageConsistency:
    """Test message consistency across commands."""

    def test_init_message_consistency(self, tmp_path):
        """Test that init messages use consistent prepositions."""
        # First write - should say "to"
        result1 = run_cli_subprocess(["init"], cwd=tmp_path)
        assert result1.returncode == 0
        assert "Wrote devcontainer to" in result1.stdout

        # Force overwrite - should say "at" (not "to")
        result2 = run_cli_subprocess(["init", "--force"], cwd=tmp_path)
        assert result2.returncode == 0
        assert "Overwrote devcontainer at" in result2.stdout
        assert "No changes." in result2.stdout

    def test_plan_message_consistency(self, tmp_path):
        """Test that plan messages use consistent format."""
        # First write - should say "to"
        result1 = run_cli_subprocess(["plan", "--desc", "test issue"], cwd=tmp_path)
        assert result1.returncode == 0
        assert "Wrote repro to" in result1.stdout

        # Already exists - should show path first
        result2 = run_cli_subprocess(["plan", "--desc", "test issue"], cwd=tmp_path)
        assert result2.returncode == 0
        assert "repro.md exists; use --force to overwrite" in result2.stdout

    def test_custom_output_paths_in_messages(self, tmp_path):
        """Test that custom output paths appear correctly in messages."""
        custom_path = tmp_path / "custom_repro.md"

        # First write with custom path
        result1 = run_cli_subprocess(
            ["plan", "--desc", "test issue", "--out", str(custom_path)], cwd=tmp_path
        )
        assert result1.returncode == 0
        assert f"Wrote repro to {custom_path}" in result1.stdout

        # Already exists with custom path
        result2 = run_cli_subprocess(
            ["plan", "--desc", "test issue", "--out", str(custom_path)], cwd=tmp_path
        )
        assert result2.returncode == 0
        assert f"{custom_path} exists; use --force to overwrite" in result2.stdout


class TestStdoutIgnoresForce:
    """Test that --out - prints only content and ignores --force."""

    def test_init_stdout_ignores_force_no_write_messages(self, tmp_path):
        """Test that init --out - ignores --force and shows no write messages."""
        # Create existing devcontainer first
        run_cli_subprocess(["init"], cwd=tmp_path)

        # Test --out - with --force - should only show JSON content
        result = run_cli_subprocess(["init", "--out", "-", "--force"], cwd=tmp_path)

        assert result.returncode == 0
        # Should contain JSON content
        assert result.stdout.strip().startswith("{")
        assert "features" in result.stdout
        # Should NOT contain any write messages
        assert "Wrote devcontainer" not in result.stdout
        assert "Overwrote devcontainer" not in result.stdout
        assert "exists" not in result.stdout
        assert "use --force" not in result.stdout

    def test_plan_stdout_ignores_force_no_write_messages(self, tmp_path):
        """Test that plan --out - ignores --force and shows no write messages."""
        # Create existing repro file first
        run_cli_subprocess(["plan", "--desc", "test issue"], cwd=tmp_path)

        # Test --out - with --force - should only show markdown content
        result = run_cli_subprocess(
            ["plan", "--desc", "different issue", "--out", "-", "--force"], cwd=tmp_path
        )

        assert result.returncode == 0
        # Should contain markdown content
        assert "# Different Issue" in result.stdout
        assert "## Assumptions" in result.stdout
        # Should NOT contain any write messages
        assert "Wrote repro" not in result.stdout
        assert "exists" not in result.stdout
        assert "use --force" not in result.stdout

    def test_init_stdout_no_file_modification(self, tmp_path):
        """Test that init --out - doesn't modify existing files even with --force."""
        # Create initial devcontainer
        result1 = run_cli_subprocess(["init"], cwd=tmp_path)
        assert result1.returncode == 0

        devcontainer_file = tmp_path / ".devcontainer" / "devcontainer.json"
        original_content = devcontainer_file.read_text()
        original_mtime = devcontainer_file.stat().st_mtime

        # Use --out - with --force
        result2 = run_cli_subprocess(["init", "--out", "-", "--force"], cwd=tmp_path)
        assert result2.returncode == 0

        # File should be unchanged
        assert devcontainer_file.read_text() == original_content
        assert devcontainer_file.stat().st_mtime == original_mtime

    def test_plan_stdout_no_file_modification(self, tmp_path):
        """Test that plan --out - doesn't modify existing files even with --force."""
        # Create initial repro file
        result1 = run_cli_subprocess(["plan", "--desc", "original issue"], cwd=tmp_path)
        assert result1.returncode == 0

        repro_file = tmp_path / "repro.md"
        original_content = repro_file.read_text()
        original_mtime = repro_file.stat().st_mtime

        # Use --out - with --force and different content
        result2 = run_cli_subprocess(
            ["plan", "--desc", "completely different issue", "--out", "-", "--force"], cwd=tmp_path
        )
        assert result2.returncode == 0

        # File should be unchanged
        assert repro_file.read_text() == original_content
        assert repro_file.stat().st_mtime == original_mtime
        # But stdout should have new content
        assert "# Completely Different Issue" in result2.stdout

    def test_dry_run_also_ignores_force(self, tmp_path):
        """Test that --dry-run also ignores --force and shows no write messages."""
        # Create existing repro file first
        run_cli_subprocess(["plan", "--desc", "test issue"], cwd=tmp_path)

        # Test --dry-run with --force - should only show markdown content
        result = run_cli_subprocess(
            ["plan", "--desc", "different issue", "--dry-run", "--force"], cwd=tmp_path
        )

        assert result.returncode == 0
        # Should contain markdown content
        assert "# Different Issue" in result.stdout
        assert "## Assumptions" in result.stdout
        # Should NOT contain any write messages
        assert "Wrote repro" not in result.stdout
        assert "exists" not in result.stdout
        assert "use --force" not in result.stdout
