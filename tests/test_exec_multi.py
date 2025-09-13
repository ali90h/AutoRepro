"""Tests for multi-execution functionality in exec command."""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from autorepro.cli import (
    ExecConfig,
    _create_run_record,
    _create_summary_record,
    _resolve_command_selection,
)
from autorepro.config.exceptions import FieldValidationError


class TestExecConfigValidation:
    """Test validation of multi-execution fields in ExecConfig."""

    def test_valid_multi_execution_config(self):
        """Test valid multi-execution configurations."""
        # Valid --all
        config = ExecConfig(desc="test", all=True)
        config.validate()  # Should not raise

        # Valid --indexes
        config = ExecConfig(desc="test", indexes="0,2-4")
        config.validate()  # Should not raise

        # Valid --until-success
        config = ExecConfig(desc="test", until_success=True)
        config.validate()  # Should not raise

    def test_indexes_parsing_valid_formats(self):
        """Test parsing of valid indexes formats."""
        config = ExecConfig(desc="test", indexes="0")
        assert config._parse_indexes("0") == [0]

        config = ExecConfig(desc="test", indexes="0,2,4")
        assert config._parse_indexes("0,2,4") == [0, 2, 4]

        config = ExecConfig(desc="test", indexes="0-3")
        assert config._parse_indexes("0-3") == [0, 1, 2, 3]

        config = ExecConfig(desc="test", indexes="0,2-4,6")
        assert config._parse_indexes("0,2-4,6") == [0, 2, 3, 4, 6]

        # Test duplicate removal and sorting
        config = ExecConfig(desc="test", indexes="3,1,2,1")
        assert config._parse_indexes("3,1,2,1") == [1, 2, 3]

    def test_indexes_parsing_invalid_formats(self):
        """Test parsing of invalid indexes formats."""
        config = ExecConfig(desc="test", indexes="invalid")

        # Empty string
        with pytest.raises(FieldValidationError, match="invalid indexes format"):
            config.validate()

        # Invalid index
        config.indexes = "abc"
        with pytest.raises(FieldValidationError, match="invalid indexes format"):
            config.validate()

        # Negative index
        config.indexes = "-1"
        with pytest.raises(FieldValidationError, match="invalid indexes format"):
            config.validate()

        # Invalid range
        config.indexes = "3-1"  # start > end
        with pytest.raises(FieldValidationError, match="invalid indexes format"):
            config.validate()

        # Invalid range format
        config.indexes = "1-2-3"
        with pytest.raises(FieldValidationError, match="invalid indexes format"):
            config.validate()


class TestCommandSelection:
    """Test command selection logic for multi-execution."""

    def test_resolve_command_selection_single_index(self):
        """Test single index selection (default behavior)."""
        suggestions = [
            ("cmd1", 5, "rationale1"),
            ("cmd2", 4, "rationale2"),
            ("cmd3", 3, "rationale3"),
        ]
        config = ExecConfig(desc="test", index=1)

        selected_indices, error = _resolve_command_selection(suggestions, config)

        assert error is None
        assert selected_indices == [1]

    def test_resolve_command_selection_all(self):
        """Test --all flag selection."""
        suggestions = [
            ("cmd1", 5, "rationale1"),
            ("cmd2", 4, "rationale2"),
            ("cmd3", 3, "rationale3"),
        ]
        config = ExecConfig(desc="test", all=True)

        selected_indices, error = _resolve_command_selection(suggestions, config)

        assert error is None
        assert selected_indices == [0, 1, 2]

    def test_resolve_command_selection_indexes(self):
        """Test --indexes flag selection."""
        suggestions = [
            ("cmd1", 5, "rationale1"),
            ("cmd2", 4, "rationale2"),
            ("cmd3", 3, "rationale3"),
        ]
        config = ExecConfig(desc="test", indexes="0,2")

        selected_indices, error = _resolve_command_selection(suggestions, config)

        assert error is None
        assert selected_indices == [0, 2]

    def test_resolve_command_selection_indexes_precedence(self):
        """Test that --indexes takes precedence over --all."""
        suggestions = [
            ("cmd1", 5, "rationale1"),
            ("cmd2", 4, "rationale2"),
            ("cmd3", 3, "rationale3"),
        ]
        config = ExecConfig(desc="test", all=True, indexes="1")

        selected_indices, error = _resolve_command_selection(suggestions, config)

        assert error is None
        assert selected_indices == [1]  # indexes takes precedence

    def test_resolve_command_selection_index_out_of_range(self):
        """Test error handling for out-of-range indices."""
        suggestions = [("cmd1", 5, "rationale1"), ("cmd2", 4, "rationale2")]
        config = ExecConfig(desc="test", index=5)

        selected_indices, error = _resolve_command_selection(suggestions, config)

        assert error == 1
        assert selected_indices is None

    def test_resolve_command_selection_indexes_out_of_range(self):
        """Test error handling for out-of-range indexes in --indexes."""
        suggestions = [("cmd1", 5, "rationale1"), ("cmd2", 4, "rationale2")]
        config = ExecConfig(desc="test", indexes="0,5")

        selected_indices, error = _resolve_command_selection(suggestions, config)

        assert error == 1
        assert selected_indices is None

    def test_resolve_command_selection_empty_suggestions(self):
        """Test handling of empty suggestions list."""
        suggestions = []
        config = ExecConfig(desc="test", all=True)

        selected_indices, error = _resolve_command_selection(suggestions, config)

        assert error is None
        assert selected_indices == []


class TestJSONLRecords:
    """Test JSONL record creation functions."""

    def test_create_run_record(self):
        """Test creation of run records."""
        results = {
            "exit_code": 0,
            "duration_ms": 1234,
            "stdout_path": "/tmp/stdout.txt",
            "stderr_path": "/tmp/stderr.txt",
        }
        start_time = datetime(2025, 9, 13, 12, 0, 0)
        end_time = datetime(2025, 9, 13, 12, 0, 1)

        record = _create_run_record(2, "test command", results, start_time, end_time)

        assert record["type"] == "run"
        assert record["index"] == 2
        assert record["cmd"] == "test command"
        assert record["start_ts"] == "2025-09-13T12:00:00Z"
        assert record["end_ts"] == "2025-09-13T12:00:01Z"
        assert record["exit_code"] == 0
        assert record["duration_ms"] == 1234
        assert record["stdout_path"] == "/tmp/stdout.txt"
        assert record["stderr_path"] == "/tmp/stderr.txt"

    def test_create_run_record_minimal(self):
        """Test creation of run records with minimal fields."""
        results = {
            "exit_code": 1,
            "duration_ms": 500,
        }
        start_time = datetime(2025, 9, 13, 12, 0, 0)
        end_time = datetime(2025, 9, 13, 12, 0, 1)

        record = _create_run_record(0, "test command", results, start_time, end_time)

        assert record["type"] == "run"
        assert record["index"] == 0
        assert record["cmd"] == "test command"
        assert record["exit_code"] == 1
        assert record["duration_ms"] == 500
        assert "stdout_path" not in record
        assert "stderr_path" not in record

    def test_create_summary_record(self):
        """Test creation of summary records."""
        record = _create_summary_record(5, 2, 1)

        assert record["type"] == "summary"
        assert record["schema_version"] == 1
        assert record["tool"] == "autorepro"
        assert record["runs"] == 5
        assert record["successes"] == 2
        assert record["first_success_index"] == 1

    def test_create_summary_record_no_successes(self):
        """Test creation of summary records with no successes."""
        record = _create_summary_record(3, 0, None)

        assert record["type"] == "summary"
        assert record["runs"] == 3
        assert record["successes"] == 0
        assert record["first_success_index"] is None


class TestMultiExecutionIntegration:
    """Integration tests for multi-execution functionality."""

    @patch("autorepro.cli._handle_exec_output_logging")
    @patch("autorepro.cli._execute_command")
    @patch("autorepro.cli._prepare_exec_environment")
    def test_multi_execution_all_commands(self, mock_env, mock_execute, mock_logging):
        """Test executing all commands with --all flag."""
        from autorepro.cli import _execute_multiple_commands

        # Mock environment setup
        mock_env.return_value = ({"PATH": "/usr/bin"}, None)

        # Mock command executions
        mock_execute.side_effect = [
            (
                {
                    "exit_code": 1,
                    "duration_ms": 100,
                    "stdout_full": "",
                    "stderr_full": "",
                },
                None,
            ),
            (
                {
                    "exit_code": 0,
                    "duration_ms": 200,
                    "stdout_full": "success",
                    "stderr_full": "",
                },
                None,
            ),
            (
                {
                    "exit_code": 2,
                    "duration_ms": 150,
                    "stdout_full": "",
                    "stderr_full": "error",
                },
                None,
            ),
        ]

        suggestions = [
            ("python3 -c 'import sys; sys.exit(1)'", 9, "rationale1"),
            ("python3 -c 'import sys; sys.exit(0)'", 8, "rationale2"),
            ("python3 -c 'import sys; sys.exit(2)'", 7, "rationale3"),
        ]
        selected_indices = [0, 1, 2]

        with tempfile.TemporaryDirectory() as tmpdir:
            jsonl_path = Path(tmpdir) / "runs.jsonl"
            summary_path = Path(tmpdir) / "summary.json"
            config = ExecConfig(
                desc="test",
                all=True,
                jsonl_path=str(jsonl_path),
                summary_path=str(summary_path),
            )

            exit_code = _execute_multiple_commands(
                suggestions, selected_indices, None, config
            )

            # Should return 0 because one command succeeded
            assert exit_code == 0

            # Check JSONL output
            assert jsonl_path.exists()
            lines = jsonl_path.read_text().strip().split("\n")
            assert len(lines) == 4  # 3 run records + 1 summary record

            # Check run records
            run1 = json.loads(lines[0])
            assert run1["type"] == "run"
            assert run1["index"] == 0
            assert run1["exit_code"] == 1

            run2 = json.loads(lines[1])
            assert run2["type"] == "run"
            assert run2["index"] == 1
            assert run2["exit_code"] == 0

            run3 = json.loads(lines[2])
            assert run3["type"] == "run"
            assert run3["index"] == 2
            assert run3["exit_code"] == 2

            # Check summary record
            summary = json.loads(lines[3])
            assert summary["type"] == "summary"
            assert summary["runs"] == 3
            assert summary["successes"] == 1
            assert summary["first_success_index"] == 1

            # Check summary file
            assert summary_path.exists()
            summary_file = json.loads(summary_path.read_text())
            assert summary_file == summary

    @patch("autorepro.cli._handle_exec_output_logging")
    @patch("autorepro.cli._execute_command")
    @patch("autorepro.cli._prepare_exec_environment")
    def test_multi_execution_until_success(self, mock_env, mock_execute, mock_logging):
        """Test executing commands with --until-success flag."""
        from autorepro.cli import _execute_multiple_commands

        # Mock environment setup
        mock_env.return_value = ({"PATH": "/usr/bin"}, None)

        # Mock command executions - first fails, second succeeds
        mock_execute.side_effect = [
            (
                {
                    "exit_code": 1,
                    "duration_ms": 100,
                    "stdout_full": "",
                    "stderr_full": "",
                },
                None,
            ),
            (
                {
                    "exit_code": 0,
                    "duration_ms": 200,
                    "stdout_full": "success",
                    "stderr_full": "",
                },
                None,
            ),
        ]

        suggestions = [
            ("python3 -c 'import sys; sys.exit(1)'", 9, "rationale1"),
            ("python3 -c 'import sys; sys.exit(0)'", 8, "rationale2"),
            ("python3 -c 'import sys; sys.exit(2)'", 7, "rationale3"),
        ]
        selected_indices = [0, 1, 2]  # All three, but should stop after second

        with tempfile.TemporaryDirectory() as tmpdir:
            jsonl_path = Path(tmpdir) / "runs.jsonl"
            config = ExecConfig(
                desc="test", all=True, until_success=True, jsonl_path=str(jsonl_path)
            )

            exit_code = _execute_multiple_commands(
                suggestions, selected_indices, None, config
            )

            # Should return 0 because a command succeeded
            assert exit_code == 0

            # Check JSONL output - should only have 2 run records + 1 summary
            lines = jsonl_path.read_text().strip().split("\n")
            assert len(lines) == 3  # 2 run records + 1 summary record

            # Check that execution stopped after success
            summary = json.loads(lines[2])
            assert summary["runs"] == 2
            assert summary["successes"] == 1
            assert summary["first_success_index"] == 1

    @patch("autorepro.cli._handle_exec_output_logging")
    @patch("autorepro.cli._execute_command")
    @patch("autorepro.cli._prepare_exec_environment")
    def test_multi_execution_indexes(self, mock_env, mock_execute, mock_logging):
        """Test executing specific commands with --indexes flag."""
        from autorepro.cli import _execute_multiple_commands

        # Mock environment setup
        mock_env.return_value = ({"PATH": "/usr/bin"}, None)

        # Mock command executions
        mock_execute.side_effect = [
            (
                {
                    "exit_code": 0,
                    "duration_ms": 100,
                    "stdout_full": "success",
                    "stderr_full": "",
                },
                None,
            ),
            (
                {
                    "exit_code": 2,
                    "duration_ms": 150,
                    "stdout_full": "",
                    "stderr_full": "error",
                },
                None,
            ),
        ]

        suggestions = [
            ("python3 -c 'import sys; sys.exit(1)'", 9, "rationale1"),
            ("python3 -c 'import sys; sys.exit(0)'", 8, "rationale2"),
            ("python3 -c 'import sys; sys.exit(2)'", 7, "rationale3"),
        ]
        selected_indices = [1, 2]  # Only execute commands at indices 1 and 2

        with tempfile.TemporaryDirectory() as tmpdir:
            jsonl_path = Path(tmpdir) / "runs.jsonl"
            config = ExecConfig(desc="test", indexes="1,2", jsonl_path=str(jsonl_path))

            exit_code = _execute_multiple_commands(
                suggestions, selected_indices, None, config
            )

            # Should return 0 because first selected command succeeded
            assert exit_code == 0

            # Check JSONL output
            lines = jsonl_path.read_text().strip().split("\n")
            assert len(lines) == 3  # 2 run records + 1 summary record

            # Check that correct commands were executed
            run1 = json.loads(lines[0])
            assert run1["index"] == 1
            assert run1["exit_code"] == 0

            run2 = json.loads(lines[1])
            assert run2["index"] == 2
            assert run2["exit_code"] == 2

            summary = json.loads(lines[2])
            assert summary["runs"] == 2
            assert summary["successes"] == 1
            assert summary["first_success_index"] == 1


class TestBackwardCompatibility:
    """Test that multi-execution doesn't break existing functionality."""

    def test_single_command_execution_unchanged(self):
        """Test that single command execution behavior is unchanged."""
        from autorepro.cli import _execute_exec_pipeline

        with patch("autorepro.cli._validate_exec_repo_path") as mock_repo:
            with patch("autorepro.cli._read_exec_input_text") as mock_text:
                with patch(
                    "autorepro.cli._generate_exec_suggestions"
                ) as mock_suggestions:
                    with patch("autorepro.cli._execute_exec_command_real") as mock_exec:
                        # Mock the pipeline components
                        mock_repo.return_value = (Path("/tmp"), None)
                        mock_text.return_value = ("test description", None)
                        mock_suggestions.return_value = (
                            [("cmd1", 5, "rationale")],
                            None,
                        )
                        mock_exec.return_value = 0

                        config = ExecConfig(
                            desc="test", index=0
                        )  # No multi-execution flags

                        exit_code = _execute_exec_pipeline(config)

                        assert exit_code == 0
                        # Should use single command execution path
                        mock_exec.assert_called_once()

    def test_jsonl_triggers_multi_execution_path(self):
        """Test that --jsonl triggers multi-execution path even for single command."""
        from autorepro.cli import _execute_exec_pipeline

        with patch("autorepro.cli._validate_exec_repo_path") as mock_repo:
            with patch("autorepro.cli._read_exec_input_text") as mock_text:
                with patch(
                    "autorepro.cli._generate_exec_suggestions"
                ) as mock_suggestions:
                    with patch(
                        "autorepro.cli._execute_multiple_commands"
                    ) as mock_multi_exec:
                        # Mock the pipeline components
                        mock_repo.return_value = (Path("/tmp"), None)
                        mock_text.return_value = ("test description", None)
                        mock_suggestions.return_value = (
                            [("cmd1", 5, "rationale")],
                            None,
                        )
                        mock_multi_exec.return_value = 0

                        config = ExecConfig(
                            desc="test", index=0, jsonl_path="runs.jsonl"
                        )

                        exit_code = _execute_exec_pipeline(config)

                        assert exit_code == 0
                        # Should use multi-execution path because of JSONL
                        mock_multi_exec.assert_called_once()
