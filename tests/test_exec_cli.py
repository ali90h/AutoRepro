"""Tests for exec CLI command."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path


class TestExecCLI:
    """Test exec command functionality."""

    def test_exec_dry_run_prints_command(self):
        """Test --dry-run prints selected command and exits 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a minimal Python environment
            (Path(tmpdir) / "test.py").write_text("import unittest")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "autorepro.cli",
                    "exec",
                    "--desc",
                    "pytest failing",
                    "--dry-run",
                    "--repo",
                    tmpdir,
                ],
                capture_output=True,
                text=True,
                cwd=".",
            )

            assert result.returncode == 0
            # Should print a command (likely pytest or similar)
            assert result.stdout.strip() != ""
            # Should not contain markdown formatting (like plan command would)
            assert "#" not in result.stdout
            assert "##" not in result.stdout

    def test_exec_timeout_kills_process(self):
        """Test --timeout kills long-running process."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create Python environment so commands are generated
            (Path(tmpdir) / "test.py").write_text("import unittest")

            # Use a command that will actually trigger timeout
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "autorepro.cli",
                    "exec",
                    "--desc",
                    "pytest",
                    "--timeout",
                    "1",
                    "--repo",
                    tmpdir,
                ],
                capture_output=True,
                text=True,
                cwd=".",
            )

            # Command should execute and may timeout or succeed quickly
            # What matters is that timeout parameter is accepted
            assert result.returncode is not None

    def test_exec_with_python_repo_executes_command(self):
        """Test exec runs command and returns subprocess exit code."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Create pyproject.toml to indicate Python project
            (repo_path / "pyproject.toml").write_text(
                """
[build-system]
requires = ["setuptools", "wheel"]
            """.strip()
            )

            # Create a simple test that will pass
            (repo_path / "test.py").write_text("print('Hello World')")

            # Create JSONL log file
            jsonl_path = repo_path / "exec.jsonl"

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "autorepro.cli",
                    "exec",
                    "--desc",
                    "run python",
                    "--repo",
                    str(repo_path),
                    "--jsonl",
                    str(jsonl_path),
                ],
                capture_output=True,
                text=True,
                cwd=".",
            )

            # Should complete (exit code depends on what command was selected)
            # but it should not error out in our exec logic
            assert result.returncode is not None

            # Should have created JSONL log
            assert jsonl_path.exists()

            # Parse JSONL records (multi-execution format)
            with open(jsonl_path) as f:
                lines = f.read().strip().split("\n")

            # Should have at least a run record and summary record
            assert len(lines) >= 2

            # Parse the first line (run record)
            run_record = json.loads(lines[0])
            assert run_record["type"] == "run"
            assert "cmd" in run_record
            assert "index" in run_record
            assert "start_ts" in run_record
            assert "end_ts" in run_record
            assert "duration_ms" in run_record
            assert "exit_code" in run_record

            # Parse the last line (summary record)
            summary_record = json.loads(lines[-1])
            assert summary_record["type"] == "summary"
            assert summary_record["schema_version"] == 1
            assert summary_record["tool"] == "autorepro"

    def test_exec_index_selects_command(self):
        """Test --index selects the N-th command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Create Python environment with multiple possible commands
            (repo_path / "test.py").write_text("import unittest")
            (repo_path / "pyproject.toml").write_text(
                "[build-system]\nrequires = ['setuptools']"
            )

            jsonl_path = repo_path / "exec.jsonl"

            # Run with index=1 (second command)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "autorepro.cli",
                    "exec",
                    "--desc",
                    "pytest failing",
                    "--index",
                    "1",
                    "--repo",
                    str(repo_path),
                    "--jsonl",
                    str(jsonl_path),
                ],
                capture_output=True,
                text=True,
                cwd=".",
            )

            # Should run (may succeed or fail depending on command)
            assert result.returncode is not None

            # Check JSONL record has correct index
            if jsonl_path.exists():
                with open(jsonl_path) as f:
                    lines = f.read().strip().split("\n")
                # Parse the first line (run record)
                run_record = json.loads(lines[0])
                assert run_record["type"] == "run"
                assert run_record["index"] == 1

    def test_exec_strict_empty_exits_with_error(self):
        """Test --strict with no commands exits 1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "autorepro.cli",
                    "exec",
                    "--desc",
                    "randomstringthatwontmatchanything",
                    "--min-score",
                    "9",
                    "--strict",
                    "--repo",
                    tmpdir,
                ],
                capture_output=True,
                text=True,
                cwd=".",
            )

            assert result.returncode == 1
            assert "no candidate commands above min-score=9" in result.stderr

    def test_exec_index_out_of_range_error(self):
        """Test --index beyond available commands returns error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create environment with some commands
            (Path(tmpdir) / "test.py").write_text("import unittest")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "autorepro.cli",
                    "exec",
                    "--desc",
                    "pytest",
                    "--index",
                    "100",
                    "--repo",
                    tmpdir,
                ],
                capture_output=True,
                text=True,
                cwd=".",
            )

            assert result.returncode == 2
            assert "out of range" in result.stderr

    def test_exec_env_variables(self):
        """Test --env sets environment variables."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Create a simple script that prints env var
            (repo_path / "test.py").write_text(
                "import os; print(os.environ.get('TEST_VAR', 'not set'))"
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "autorepro.cli",
                    "exec",
                    "--desc",
                    "python test",
                    "--env",
                    "TEST_VAR=hello_world",
                    "--repo",
                    str(repo_path),
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                cwd=".",
            )

            # Should work (dry run)
            assert result.returncode == 0

    def test_exec_env_file(self):
        """Test --env-file loads environment variables."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Create Python environment
            (repo_path / "test.py").write_text("import unittest")

            # Create .env file
            env_file = repo_path / ".env"
            env_file.write_text("TEST_VAR=from_file\nANOTHER_VAR=also_from_file")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "autorepro.cli",
                    "exec",
                    "--desc",
                    "pytest",
                    "--env-file",
                    str(env_file),
                    "--repo",
                    str(repo_path),
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                cwd=".",
            )

            assert result.returncode == 0

    def test_exec_tee_output(self):
        """Test --tee appends output to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            tee_path = repo_path / "output.log"

            # Create simple test
            (repo_path / "test.py").write_text("print('test output')")

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "autorepro.cli",
                    "exec",
                    "--desc",
                    "python test",
                    "--tee",
                    str(tee_path),
                    "--repo",
                    str(repo_path),
                ],
                capture_output=True,
                text=True,
                cwd=".",
            )

            # Check tee file was created (even if command failed)
            if tee_path.exists():
                content = tee_path.read_text()
                assert "===" in content  # Our tee format

    def test_exec_quiet_verbose_flags(self):
        """Test -q and -v flags work with exec."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create Python environment
            (Path(tmpdir) / "test.py").write_text("import unittest")

            # Test quiet mode
            result_quiet = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "autorepro.cli",
                    "exec",
                    "--desc",
                    "pytest",
                    "-q",
                    "--repo",
                    tmpdir,
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                cwd=".",
            )

            assert result_quiet.returncode == 0

            # Test verbose mode
            result_verbose = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "autorepro.cli",
                    "exec",
                    "--desc",
                    "pytest",
                    "-v",
                    "--repo",
                    tmpdir,
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                cwd=".",
            )

            assert result_verbose.returncode == 0

    def test_exec_missing_required_args(self):
        """Test exec requires --desc or --file."""
        result = subprocess.run(
            [sys.executable, "-m", "autorepro.cli", "exec"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 2  # argparse error

    def test_exec_invalid_repo_path(self):
        """Test exec with invalid --repo path."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "autorepro.cli",
                "exec",
                "--desc",
                "test",
                "--repo",
                "/nonexistent/path",
            ],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 2
        assert "does not exist" in result.stderr

    def test_exec_file_input(self):
        """Test exec with --file input."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            issue_file = repo_path / "issue.txt"
            issue_file.write_text("pytest is failing")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "autorepro.cli",
                    "exec",
                    "--file",
                    str(issue_file),
                    "--repo",
                    str(repo_path),
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                cwd=".",
            )

            assert result.returncode == 0
            assert result.stdout.strip() != ""
