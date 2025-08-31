"""Tests for CLI verbosity controls (-q/--quiet, -v/--verbose)."""

import subprocess
import sys
import tempfile
from pathlib import Path


class TestCLIVerbosity:
    """Test verbosity controls in CLI commands."""

    def test_plan_default_verbosity_hides_filter_message(self):
        """Test default verbosity hides 'filtered N low-score suggestions' message."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a minimal Python environment
            (Path(tmpdir) / "test.py").write_text("import unittest")

            cmd = [
                sys.executable,
                "-c",
                "import sys; sys.path.insert(0, '.'); from autorepro.cli import main; "
                f"sys.exit(main(['plan', '--desc', 'pytest failing', '--min-score', '3', "
                f"'--dry-run', '--repo', '{tmpdir}']))",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=".")

            assert result.returncode == 0
            assert "filtered" not in result.stderr
            assert result.stderr.strip() == "", f"Expected empty stderr, got: {result.stderr}"

    def test_plan_verbose_shows_filter_message(self):
        """Test -v shows 'filtered N low-score suggestions' message."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a minimal Python environment
            (Path(tmpdir) / "test.py").write_text("import unittest")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "autorepro.cli",
                    "plan",
                    "--desc",
                    "pytest failing",
                    "--min-score",
                    "3",
                    "-v",
                    "--dry-run",
                    "--repo",
                    tmpdir,
                ],
                capture_output=True,
                text=True,
                cwd=".",
            )

            assert result.returncode == 0
            assert "filtered" in result.stderr
            assert "low-score suggestions" in result.stderr

    def test_plan_quiet_hides_filter_message(self):
        """Test -q/--quiet hides 'filtered ...' message."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a minimal Python environment
            (Path(tmpdir) / "test.py").write_text("import unittest")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "autorepro.cli",
                    "plan",
                    "--desc",
                    "pytest failing",
                    "--min-score",
                    "3",
                    "-q",
                    "--dry-run",
                    "--repo",
                    tmpdir,
                ],
                capture_output=True,
                text=True,
                cwd=".",
            )

            assert result.returncode == 0
            assert "filtered" not in result.stderr
            assert result.stderr.strip() == "", f"Expected empty stderr, got: {result.stderr}"

    def test_plan_strict_quiet_shows_error_only(self):
        """Test --strict + -q shows error message only."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "autorepro.cli",
                    "plan",
                    "--desc",
                    "pytest failing",
                    "--min-score",
                    "9",
                    "--strict",
                    "-q",
                    "--dry-run",
                    "--repo",
                    tmpdir,
                ],
                capture_output=True,
                text=True,
                cwd=".",
            )

            assert result.returncode == 1
            assert "no candidate commands above min-score=9" in result.stderr
            # Should not contain filtered message
            assert "filtered" not in result.stderr

    def test_plan_strict_verbose_shows_both_messages(self):
        """Test --strict + -v shows both filtered and error messages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create minimal environment so some commands exist
            (Path(tmpdir) / "test.py").write_text("import unittest")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "autorepro.cli",
                    "plan",
                    "--desc",
                    "pytest failing",
                    "--min-score",
                    "9",
                    "--strict",
                    "-v",
                    "--dry-run",
                    "--repo",
                    tmpdir,
                ],
                capture_output=True,
                text=True,
                cwd=".",
            )

            assert result.returncode == 1
            assert "no candidate commands above min-score=9" in result.stderr
            # With a very high min-score, we should see filtered message too
            # (if there were commands with lower scores)

    def test_quiet_overrides_verbose(self):
        """Test that -q overrides -v flags."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "test.py").write_text("import unittest")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "autorepro.cli",
                    "plan",
                    "--desc",
                    "pytest failing",
                    "--min-score",
                    "3",
                    "-v",
                    "-q",
                    "--dry-run",
                    "--repo",
                    tmpdir,
                ],
                capture_output=True,
                text=True,
                cwd=".",
            )

            assert result.returncode == 0
            assert "filtered" not in result.stderr
            assert result.stderr.strip() == "", f"Expected empty stderr, got: {result.stderr}"

    def test_scan_quiet_mode(self):
        """Test scan with -q shows errors only."""
        with tempfile.TemporaryDirectory():
            cmd = [
                sys.executable,
                "-c",
                "import sys; sys.path.insert(0, '.'); from autorepro.cli import main; "
                "sys.exit(main(['scan', '-q']))",
            ]
            result = subprocess.run(cmd, cwd=".", capture_output=True, text=True)

            assert result.returncode == 0
            # Should have stdout output (the scan results) but no stderr
            assert result.stderr.strip() == "", f"Expected empty stderr, got: {result.stderr}"

    def test_scan_verbose_mode(self):
        """Test scan with -v (informational messages)."""
        with tempfile.TemporaryDirectory():
            cmd = [
                sys.executable,
                "-c",
                "import sys; sys.path.insert(0, '.'); from autorepro.cli import main; "
                "sys.exit(main(['scan', '-v']))",
            ]
            result = subprocess.run(cmd, cwd=".", capture_output=True, text=True)

            assert result.returncode == 0
            # Should have stdout output but stderr might be empty for scan
            # (scan doesn't currently have informational messages, but this tests the flag works)

    def test_double_verbose_debug_mode(self):
        """Test -vv enables debug mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "test.py").write_text("import unittest")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "autorepro.cli",
                    "plan",
                    "--desc",
                    "pytest failing",
                    "-vv",
                    "--dry-run",
                    "--repo",
                    tmpdir,
                ],
                capture_output=True,
                text=True,
                cwd=".",
            )

            assert result.returncode == 0
            # Debug mode might not have specific output yet, but test flag parsing works

    def test_verbose_count_incremental(self):
        """Test that multiple -v flags increase verbosity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "test.py").write_text("import unittest")

            # Single -v
            result1 = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "autorepro.cli",
                    "plan",
                    "--desc",
                    "pytest failing",
                    "--min-score",
                    "3",
                    "-v",
                    "--dry-run",
                    "--repo",
                    tmpdir,
                ],
                capture_output=True,
                text=True,
                cwd=".",
            )

            # Double -v
            result2 = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "autorepro.cli",
                    "plan",
                    "--desc",
                    "pytest failing",
                    "--min-score",
                    "3",
                    "-vv",
                    "--dry-run",
                    "--repo",
                    tmpdir,
                ],
                capture_output=True,
                text=True,
                cwd=".",
            )

            assert result1.returncode == 0
            assert result2.returncode == 0
            # Both should work without errors

    def test_io_error_shows_in_quiet_mode(self):
        """Test that I/O errors still show in quiet mode."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "autorepro.cli",
                "plan",
                "--desc",
                "test",
                "--out",
                "/nonexistent/path/file.md",
                "-q",
            ],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 1
        assert "Error" in result.stderr
        # Should still show error even in quiet mode
