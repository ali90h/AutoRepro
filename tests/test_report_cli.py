"""Tests for report CLI command."""

import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


class TestReportCLI:
    """Test report command functionality."""

    def test_report_help(self):
        """Test --help shows report command help."""
        result = subprocess.run(
            [sys.executable, "-m", "autorepro.cli", "report", "--help"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 0
        assert "Generate a comprehensive report bundle" in result.stdout
        assert "--include" in result.stdout
        assert "--out" in result.stdout

    def test_report_requires_desc_or_file(self):
        """Test report requires either --desc or --file."""
        result = subprocess.run(
            [sys.executable, "-m", "autorepro.cli", "report"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 2
        assert "error" in result.stderr.lower()

    def test_report_stdout_preview(self):
        """Test --out - shows preview with schema=v2."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "autorepro.cli",
                "report",
                "--desc",
                "test issue",
                "--out",
                "-",
            ],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 0
        assert "schema=v2" in result.stdout
        assert "MANIFEST.json" in result.stdout
        assert "repro.md" in result.stdout
        assert "ENV.txt" in result.stdout

    def test_report_with_scan_and_init(self):
        """Test report with scan and init includes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a minimal Python environment
            (Path(tmpdir) / "pyproject.toml").write_text(
                "[build-system]\nrequires = ['setuptools']"
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "autorepro.cli",
                    "report",
                    "--desc",
                    "pytest failing",
                    "--include",
                    "scan,init",
                    "--out",
                    str(Path(tmpdir) / "test.zip"),
                    "--repo",
                    tmpdir,
                ],
                capture_output=True,
                text=True,
                cwd=".",
            )

            assert result.returncode == 0
            assert "Report bundle created" in result.stderr

            # Verify zip contents
            zip_path = Path(tmpdir) / "test.zip"
            assert zip_path.exists()

            with zipfile.ZipFile(zip_path, "r") as z:
                files = set(z.namelist())
                assert "MANIFEST.json" in files
                assert "SCAN.json" in files
                assert "INIT.preview.json" in files

                # Check MANIFEST.json
                manifest = json.loads(z.read("MANIFEST.json").decode("utf-8"))
                assert manifest["schema_version"] == 2
                assert manifest["tool"] == "autorepro"
                assert "scan" in manifest["sections"]
                assert "init" in manifest["sections"]
                assert "SCAN.json" in manifest["files"]
                assert "INIT.preview.json" in manifest["files"]

    def test_report_default_sections(self):
        """Test report includes plan and env by default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "autorepro.cli",
                    "report",
                    "--desc",
                    "test issue",
                    "--out",
                    str(Path(tmpdir) / "test.zip"),
                ],
                capture_output=True,
                text=True,
                cwd=".",
            )

            assert result.returncode == 0

            # Verify zip contents
            zip_path = Path(tmpdir) / "test.zip"
            with zipfile.ZipFile(zip_path, "r") as z:
                files = set(z.namelist())
                assert "MANIFEST.json" in files
                assert "repro.md" in files
                assert "ENV.txt" in files

                # Check MANIFEST.json
                manifest = json.loads(z.read("MANIFEST.json").decode("utf-8"))
                assert manifest["schema_version"] == 2
                assert "plan" in manifest["sections"]
                assert "env" in manifest["sections"]

    def test_report_invalid_include_sections(self):
        """Test report with invalid include sections fails."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "autorepro.cli",
                "report",
                "--desc",
                "test issue",
                "--include",
                "invalid,section",
            ],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 1
        assert "Invalid include sections" in result.stderr

    def test_report_file_input(self):
        """Test report with --file input."""
        with tempfile.TemporaryDirectory() as tmpdir:
            issue_file = Path(tmpdir) / "issue.txt"
            issue_file.write_text("pytest is failing")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "autorepro.cli",
                    "report",
                    "--file",
                    str(issue_file),
                    "--out",
                    str(Path(tmpdir) / "test.zip"),
                ],
                capture_output=True,
                text=True,
                cwd=".",
            )

            assert result.returncode == 0
            assert "Report bundle created" in result.stderr

    def test_report_force_overwrite(self):
        """Test report --force overwrites existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "test.zip"
            zip_path.write_text("existing content")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "autorepro.cli",
                    "report",
                    "--desc",
                    "test issue",
                    "--out",
                    str(zip_path),
                    "--force",
                ],
                capture_output=True,
                text=True,
                cwd=".",
            )

            assert result.returncode == 0
            assert "Report bundle created" in result.stderr

    def test_report_no_force_existing_file(self):
        """Test report fails when file exists and no --force."""
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "test.zip"
            zip_path.write_text("existing content")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "autorepro.cli",
                    "report",
                    "--desc",
                    "test issue",
                    "--out",
                    str(zip_path),
                ],
                capture_output=True,
                text=True,
                cwd=".",
            )

            assert result.returncode == 1
            assert "Output file exists" in result.stderr
