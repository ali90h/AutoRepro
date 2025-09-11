"""Tests for JSON scan functionality core logic."""

import json
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from autorepro.cli import cmd_scan
from autorepro.detect import collect_evidence


class TestScanJsonCore:
    """Test the core JSON scanning functionality."""

    def test_python_only_pyproject(self):
        """Test Python detection with pyproject.toml only."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create pyproject.toml
            (tmpdir_path / "pyproject.toml").write_text("[build-system]\nrequires = []")

            evidence = collect_evidence(tmpdir_path)

            # Should detect only python
            assert list(evidence.keys()) == ["python"]
            assert evidence["python"]["score"] == 3

            reasons = evidence["python"]["reasons"]
            assert len(reasons) == 1
            assert reasons[0]["pattern"] == "pyproject.toml"
            assert reasons[0]["path"] == "./pyproject.toml"
            assert reasons[0]["kind"] == "config"
            assert reasons[0]["weight"] == 3

    def test_node_lockfile_only(self):
        """Test Node.js detection with pnpm-lock.yaml only."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create pnpm-lock.yaml
            (tmpdir_path / "pnpm-lock.yaml").write_text("lockfileVersion: 5.4")

            evidence = collect_evidence(tmpdir_path)

            # Should detect only node
            assert list(evidence.keys()) == ["node"]
            assert evidence["node"]["score"] == 4

            reasons = evidence["node"]["reasons"]
            assert len(reasons) == 1
            assert reasons[0]["pattern"] == "pnpm-lock.yaml"
            assert reasons[0]["path"] == "./pnpm-lock.yaml"
            assert reasons[0]["kind"] == "lock"
            assert reasons[0]["weight"] == 4

    def test_python_config_and_node_lock(self):
        """Test Python config + Node lock, node score should be higher."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create Python config file (weight 3)
            (tmpdir_path / "pyproject.toml").write_text("[build-system]")

            # Create Node lock file (weight 4)
            (tmpdir_path / "pnpm-lock.yaml").write_text("lockfileVersion: 5.4")

            evidence = collect_evidence(tmpdir_path)

            # Should detect both languages
            assert set(evidence.keys()) == {"python", "node"}

            # Node should have higher score (4) than Python (3)
            assert evidence["node"]["score"] == 4
            assert evidence["python"]["score"] == 3
            assert evidence["node"]["score"] > evidence["python"]["score"]

            # Check node reasons
            node_reasons = evidence["node"]["reasons"]
            assert len(node_reasons) == 1
            assert node_reasons[0]["kind"] == "lock"

            # Check python reasons
            python_reasons = evidence["python"]["reasons"]
            assert len(python_reasons) == 1
            assert python_reasons[0]["kind"] == "config"

    def test_glob_source_files_only(self):
        """Test source files detection with glob patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create only source files
            (tmpdir_path / "main.py").write_text("print('hello')")
            (tmpdir_path / "utils.py").write_text("def helper(): pass")

            evidence = collect_evidence(tmpdir_path)

            # Should detect only python
            assert list(evidence.keys()) == ["python"]
            assert evidence["python"]["score"] == 1  # source weight

            reasons = evidence["python"]["reasons"]
            assert len(reasons) == 1
            assert reasons[0]["pattern"] == "*.py"
            assert reasons[0]["kind"] == "source"
            assert reasons[0]["weight"] == 1
            # Path should be one of the .py files
            assert reasons[0]["path"] in ["./main.py", "./utils.py"]

    def test_multiple_source_files_same_pattern_weight(self):
        """Test that multiple files matching same pattern get weight only once."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create multiple .py files
            (tmpdir_path / "file1.py").write_text("pass")
            (tmpdir_path / "file2.py").write_text("pass")
            (tmpdir_path / "file3.py").write_text("pass")

            evidence = collect_evidence(tmpdir_path)

            # Should detect python with score=1 (not 3)
            assert evidence["python"]["score"] == 1

            # Should have only one reason for *.py pattern
            reasons = evidence["python"]["reasons"]
            assert len(reasons) == 1
            assert reasons[0]["pattern"] == "*.py"

    def test_mixed_weight_scoring(self):
        """Test mixed file types with proper weight accumulation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create files with different weights for Python
            (tmpdir_path / "pyproject.toml").write_text(
                "[build-system]"
            )  # config: weight 3
            (tmpdir_path / "setup.py").write_text(
                "from setuptools import setup"
            )  # setup: weight 2
            (tmpdir_path / "main.py").write_text("print('hello')")  # source: weight 1

            evidence = collect_evidence(tmpdir_path)

            # Should detect python with total score = 3 + 2 + 1 = 6
            assert evidence["python"]["score"] == 6

            reasons = evidence["python"]["reasons"]
            assert len(reasons) == 3

            # Check each reason type is present
            patterns = [r["pattern"] for r in reasons]
            assert "pyproject.toml" in patterns
            assert "setup.py" in patterns
            assert "*.py" in patterns

    def test_empty_directory(self):
        """Test empty directory returns empty evidence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            evidence = collect_evidence(tmpdir_path)

            assert evidence == {}

    def test_valid_json_schema_and_types(self):
        """Test that evidence structure matches expected JSON schema."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create test files
            (tmpdir_path / "pyproject.toml").write_text("[build-system]")
            (tmpdir_path / "pnpm-lock.yaml").write_text("lockfileVersion: 5.4")

            evidence = collect_evidence(tmpdir_path)

            # Test overall structure
            assert isinstance(evidence, dict)

            for lang_name, lang_data in evidence.items():
                # Language name should be string
                assert isinstance(lang_name, str)

                # Language data should have required keys
                assert isinstance(lang_data, dict)
                assert "score" in lang_data
                assert "reasons" in lang_data

                # Score should be integer
                assert isinstance(lang_data["score"], int)
                assert lang_data["score"] > 0

                # Reasons should be list
                assert isinstance(lang_data["reasons"], list)
                assert len(lang_data["reasons"]) > 0

                # Each reason should have required fields with correct types
                for reason in lang_data["reasons"]:
                    assert isinstance(reason, dict)
                    assert isinstance(reason["pattern"], str)
                    assert isinstance(reason["path"], str)
                    assert isinstance(reason["kind"], str)
                    assert isinstance(reason["weight"], int)

                    # Path should start with "./"
                    assert reason["path"].startswith("./")

                    # Kind should be valid
                    assert reason["kind"] in ["lock", "config", "setup", "source"]

                    # Weight should be positive
                    assert reason["weight"] > 0

    def test_csharp_detection(self):
        """Test C# detection with .csproj file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create .csproj file
            (tmpdir_path / "MyApp.csproj").write_text("<Project></Project>")

            evidence = collect_evidence(tmpdir_path)

            assert "csharp" in evidence
            assert evidence["csharp"]["score"] == 3

            reasons = evidence["csharp"]["reasons"]
            assert len(reasons) == 1
            assert reasons[0]["pattern"] == "*.csproj"
            assert reasons[0]["kind"] == "config"

    def test_go_detection(self):
        """Test Go detection with go.mod and go.sum."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create Go files
            (tmpdir_path / "go.mod").write_text("module test")
            (tmpdir_path / "go.sum").write_text("example.com/test v1.0.0")

            evidence = collect_evidence(tmpdir_path)

            assert "go" in evidence
            # go.mod (config: 3) + go.sum (lock: 4) = 7
            assert evidence["go"]["score"] == 7

            reasons = evidence["go"]["reasons"]
            assert len(reasons) == 2
            patterns = [r["pattern"] for r in reasons]
            assert "go.mod" in patterns
            assert "go.sum" in patterns

    def test_no_indicators_empty_result(self):
        """Test that directory with no indicators returns empty results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create only non-language files
            (tmpdir_path / "README.md").write_text("# Project")
            (tmpdir_path / "LICENSE").write_text("MIT License")

            evidence = collect_evidence(tmpdir_path)

            # Should have no detections
            assert evidence == {}

    def test_multiple_causes_grouped_deterministic_order(self):
        """Test multiple causes for same language are grouped with deterministic
        order."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create Python files with different weights
            (tmpdir_path / "pyproject.toml").write_text(
                "[build-system]"
            )  # config: weight 3
            (tmpdir_path / "requirements.txt").write_text("requests")  # setup: weight 2

            evidence = collect_evidence(tmpdir_path)

            # Should detect only python
            assert list(evidence.keys()) == ["python"]

            # Score should be sum: 3 + 2 = 5
            assert evidence["python"]["score"] == 5

            # Should have exactly 2 reasons
            reasons = evidence["python"]["reasons"]
            assert len(reasons) == 2

            # Order should be deterministic (based on order of processing)
            # pyproject.toml is processed first in WEIGHTED_PATTERNS
            assert reasons[0]["pattern"] == "pyproject.toml"
            assert reasons[0]["kind"] == "config"
            assert reasons[0]["weight"] == 3

            assert reasons[1]["pattern"] == "requirements.txt"
            assert reasons[1]["kind"] == "setup"
            assert reasons[1]["weight"] == 2

            # Verify paths are correct
            assert reasons[0]["path"] == "./pyproject.toml"
            assert reasons[1]["path"] == "./requirements.txt"

    def test_scan_json_schema_versioning_fields(self):
        """Test that scan --json output includes schema versioning fields."""
        from autorepro import __version__

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a Python file for detection
            (tmpdir_path / "setup.py").write_text("from setuptools import setup")

            # Change to temp directory and capture JSON output
            with patch("os.getcwd", return_value=tmpdir):
                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    exit_code = cmd_scan(json_output=True)

                    # Should succeed
                    assert exit_code == 0

                    # Parse JSON output
                    json_output = mock_stdout.getvalue()
                    result = json.loads(json_output)

                    # Check schema versioning fields
                    assert "schema_version" in result
                    assert result["schema_version"] == 1
                    assert isinstance(result["schema_version"], int)

                    assert "tool" in result
                    assert result["tool"] == "autorepro"
                    assert isinstance(result["tool"], str)

                    assert "tool_version" in result
                    assert result["tool_version"] == __version__
                    assert isinstance(result["tool_version"], str)

                    # Check key order - schema versioning fields should come first
                    keys_list = list(result.keys())
                    assert keys_list[0] == "schema_version"
                    assert keys_list[1] == "tool"
                    assert keys_list[2] == "tool_version"

                    # Check other required fields are still present
                    assert "root" in result
                    assert "detected" in result
                    assert "languages" in result
