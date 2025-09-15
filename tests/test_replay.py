"""Tests for replay command functionality."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from autorepro.cli import ReplayConfig, cmd_replay, _parse_jsonl_file, _filter_records_by_indexes, _create_replay_run_record, _create_replay_summary_record
from autorepro.config.exceptions import FieldValidationError


class TestReplayConfig:
    """Test ReplayConfig validation and parsing."""

    def test_valid_config(self):
        """Test valid replay configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.jsonl"
            test_file.write_text('{"type": "run", "index": 0, "cmd": "echo test", "exit_code": 0}\n')
            
            config = ReplayConfig(from_path=str(test_file))
            config.validate()  # Should not raise

    def test_missing_from_path(self):
        """Test validation fails when from_path is missing."""
        config = ReplayConfig(from_path="")
        with pytest.raises(FieldValidationError, match="from_path is required"):
            config.validate()

    def test_nonexistent_file(self):
        """Test validation fails when file doesn't exist."""
        config = ReplayConfig(from_path="/nonexistent/file.jsonl")
        with pytest.raises(FieldValidationError, match="input file does not exist"):
            config.validate()

    def test_invalid_timeout(self):
        """Test validation fails with invalid timeout."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.jsonl"
            test_file.write_text('{"type": "run", "index": 0, "cmd": "echo test", "exit_code": 0}\n')
            
            config = ReplayConfig(from_path=str(test_file), timeout=0)
            with pytest.raises(FieldValidationError, match="timeout must be positive"):
                config.validate()

    def test_valid_indexes_parsing(self):
        """Test valid indexes string parsing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.jsonl"
            test_file.write_text('{"type": "run", "index": 0, "cmd": "echo test", "exit_code": 0}\n')
            
            config = ReplayConfig(from_path=str(test_file), indexes="0,2-4,7")
            result = config._parse_indexes("0,2-4,7")
            expected = [0, 2, 3, 4, 7]
            assert result == expected

    def test_invalid_indexes_parsing(self):
        """Test invalid indexes string parsing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.jsonl"
            test_file.write_text('{"type": "run", "index": 0, "cmd": "echo test", "exit_code": 0}\n')
            
            config = ReplayConfig(from_path=str(test_file), indexes="invalid")
            with pytest.raises(FieldValidationError, match="invalid indexes format"):
                config.validate()


class TestJSONLParsing:
    """Test JSONL file parsing functionality."""

    def test_parse_valid_jsonl(self):
        """Test parsing valid JSONL file with run records."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.jsonl"
            content = '''{"type": "run", "index": 0, "cmd": "echo test1", "exit_code": 0}
{"type": "run", "index": 1, "cmd": "echo test2", "exit_code": 1}
{"type": "summary", "runs": 2}
'''
            test_file.write_text(content)
            
            records = _parse_jsonl_file(str(test_file))
            assert len(records) == 2
            assert records[0]["cmd"] == "echo test1"
            assert records[1]["cmd"] == "echo test2"

    def test_parse_empty_file(self):
        """Test parsing empty JSONL file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "empty.jsonl"
            test_file.write_text("")
            
            records = _parse_jsonl_file(str(test_file))
            assert records == []

    def test_parse_no_run_records(self):
        """Test parsing JSONL file with no run records."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.jsonl"
            content = '''{"type": "summary", "runs": 0}
{"type": "other", "data": "value"}
'''
            test_file.write_text(content)
            
            records = _parse_jsonl_file(str(test_file))
            assert records == []

    def test_parse_invalid_json_lines(self):
        """Test parsing JSONL file with some invalid JSON lines."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.jsonl"
            content = '''{"type": "run", "index": 0, "cmd": "echo test1", "exit_code": 0}
invalid json line
{"type": "run", "index": 1, "cmd": "echo test2", "exit_code": 1}
'''
            test_file.write_text(content)
            
            records = _parse_jsonl_file(str(test_file))
            assert len(records) == 2
            assert records[0]["cmd"] == "echo test1"
            assert records[1]["cmd"] == "echo test2"


class TestIndexFiltering:
    """Test index filtering functionality."""

    def test_filter_by_single_index(self):
        """Test filtering by single index."""
        records = [
            {"type": "run", "index": 0, "cmd": "cmd0"},
            {"type": "run", "index": 1, "cmd": "cmd1"},
            {"type": "run", "index": 2, "cmd": "cmd2"},
        ]
        
        filtered = _filter_records_by_indexes(records, "1")
        assert len(filtered) == 1
        assert filtered[0]["cmd"] == "cmd1"

    def test_filter_by_range(self):
        """Test filtering by range."""
        records = [
            {"type": "run", "index": 0, "cmd": "cmd0"},
            {"type": "run", "index": 1, "cmd": "cmd1"},
            {"type": "run", "index": 2, "cmd": "cmd2"},
            {"type": "run", "index": 3, "cmd": "cmd3"},
        ]
        
        filtered = _filter_records_by_indexes(records, "1-2")
        assert len(filtered) == 2
        assert filtered[0]["cmd"] == "cmd1"
        assert filtered[1]["cmd"] == "cmd2"

    def test_filter_by_mixed_indexes(self):
        """Test filtering by mixed indexes and ranges."""
        records = [
            {"type": "run", "index": 0, "cmd": "cmd0"},
            {"type": "run", "index": 1, "cmd": "cmd1"},
            {"type": "run", "index": 2, "cmd": "cmd2"},
            {"type": "run", "index": 3, "cmd": "cmd3"},
            {"type": "run", "index": 4, "cmd": "cmd4"},
        ]
        
        filtered = _filter_records_by_indexes(records, "0,2-3")
        assert len(filtered) == 3
        assert filtered[0]["cmd"] == "cmd0"
        assert filtered[1]["cmd"] == "cmd2"
        assert filtered[2]["cmd"] == "cmd3"

    def test_filter_no_matches(self):
        """Test filtering with no matching indexes."""
        records = [
            {"type": "run", "index": 0, "cmd": "cmd0"},
            {"type": "run", "index": 1, "cmd": "cmd1"},
        ]
        
        filtered = _filter_records_by_indexes(records, "5-7")
        assert filtered == []

    def test_filter_no_indexes_specified(self):
        """Test filtering with no indexes specified returns all records."""
        records = [
            {"type": "run", "index": 0, "cmd": "cmd0"},
            {"type": "run", "index": 1, "cmd": "cmd1"},
        ]
        
        filtered = _filter_records_by_indexes(records, None)
        assert filtered == records


class TestRecordCreation:
    """Test replay record creation functions."""

    def test_create_replay_run_record(self):
        """Test creation of replay run records."""
        from datetime import datetime
        
        results = {
            "exit_code": 1,
            "duration_ms": 150,
            "start_time": datetime(2025, 9, 15, 12, 0, 0),
            "end_time": datetime(2025, 9, 15, 12, 0, 1),
            "stdout_preview": "output",
            "stderr_preview": "error",
        }
        
        record = _create_replay_run_record(2, "test command", 0, results)
        
        assert record["type"] == "run"
        assert record["index"] == 2
        assert record["cmd"] == "test command"
        assert record["exit_code_original"] == 0
        assert record["exit_code_replay"] == 1
        assert record["matched"] is False
        assert record["duration_ms"] == 150
        assert record["stdout_preview"] == "output"
        assert record["stderr_preview"] == "error"

    def test_create_replay_summary_record(self):
        """Test creation of replay summary records."""
        record = _create_replay_summary_record(5, 3, 2, 4, 1, 1)
        
        assert record["type"] == "summary"
        assert record["schema_version"] == 1
        assert record["tool"] == "autorepro"
        assert record["mode"] == "replay"
        assert record["runs"] == 5
        assert record["successes"] == 3
        assert record["failures"] == 2
        assert record["matches"] == 4
        assert record["mismatches"] == 1
        assert record["first_success_index"] == 1


class TestReplayExecution:
    """Test end-to-end replay execution."""

    def test_replay_dry_run(self):
        """Test replay dry run functionality."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test JSONL file
            test_file = Path(tmpdir) / "test.jsonl"
            content = '''{"type": "run", "index": 0, "cmd": "echo test1", "exit_code": 0}
{"type": "run", "index": 1, "cmd": "echo test2", "exit_code": 1}
'''
            test_file.write_text(content)
            
            config = ReplayConfig(from_path=str(test_file), dry_run=True)
            result = cmd_replay(config)
            
            assert result == 0

    def test_replay_simple_execution(self):
        """Test simple replay execution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test JSONL file
            test_file = Path(tmpdir) / "test.jsonl"
            content = '''{"type": "run", "index": 0, "cmd": "echo 'success'", "exit_code": 0}
{"type": "run", "index": 1, "cmd": "python -c 'import sys; sys.exit(1)'", "exit_code": 1}
'''
            test_file.write_text(content)
            
            # Create output files
            jsonl_file = Path(tmpdir) / "replay.jsonl"
            summary_file = Path(tmpdir) / "summary.json"
            
            config = ReplayConfig(
                from_path=str(test_file),
                jsonl_path=str(jsonl_file),
                summary_path=str(summary_file),
            )
            result = cmd_replay(config)
            
            assert result == 0
            assert jsonl_file.exists()
            assert summary_file.exists()
            
            # Verify JSONL output
            jsonl_lines = jsonl_file.read_text().strip().split('\n')
            assert len(jsonl_lines) == 3  # 2 run records + 1 summary
            
            # Verify summary
            summary = json.loads(summary_file.read_text())
            assert summary["runs"] == 2
            assert summary["successes"] == 1
            assert summary["failures"] == 1

    def test_replay_with_index_filtering(self):
        """Test replay with index filtering."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test JSONL file
            test_file = Path(tmpdir) / "test.jsonl"
            content = '''{"type": "run", "index": 0, "cmd": "echo 'cmd0'", "exit_code": 0}
{"type": "run", "index": 1, "cmd": "echo 'cmd1'", "exit_code": 0}
{"type": "run", "index": 2, "cmd": "echo 'cmd2'", "exit_code": 0}
'''
            test_file.write_text(content)
            
            summary_file = Path(tmpdir) / "summary.json"
            
            config = ReplayConfig(
                from_path=str(test_file),
                indexes="0,2",
                summary_path=str(summary_file),
            )
            result = cmd_replay(config)
            
            assert result == 0
            
            # Verify only 2 commands were run
            summary = json.loads(summary_file.read_text())
            assert summary["runs"] == 2

    def test_replay_until_success(self):
        """Test replay with until-success flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test JSONL file - first command fails, second succeeds
            test_file = Path(tmpdir) / "test.jsonl"
            content = '''{"type": "run", "index": 0, "cmd": "python -c 'import sys; sys.exit(1)'", "exit_code": 1}
{"type": "run", "index": 1, "cmd": "echo 'success'", "exit_code": 0}
{"type": "run", "index": 2, "cmd": "echo 'should not run'", "exit_code": 0}
'''
            test_file.write_text(content)
            
            summary_file = Path(tmpdir) / "summary.json"
            
            config = ReplayConfig(
                from_path=str(test_file),
                until_success=True,
                summary_path=str(summary_file),
            )
            result = cmd_replay(config)
            
            assert result == 0
            
            # Should stop after second command (first success)
            summary = json.loads(summary_file.read_text())
            assert summary["runs"] == 2
            assert summary["successes"] == 1
            assert summary["first_success_index"] == 1

    def test_replay_error_cases(self):
        """Test replay error handling."""
        # Test with nonexistent file
        config = ReplayConfig(from_path="/nonexistent/file.jsonl")
        result = cmd_replay(config)
        assert result == 1
        
        # Test with empty JSONL file
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "empty.jsonl"
            test_file.write_text("")
            
            config = ReplayConfig(from_path=str(test_file))
            result = cmd_replay(config)
            assert result == 1

    def test_replay_invalid_indexes(self):
        """Test replay with invalid indexes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test JSONL file
            test_file = Path(tmpdir) / "test.jsonl"
            content = '''{"type": "run", "index": 0, "cmd": "echo test", "exit_code": 0}
'''
            test_file.write_text(content)
            
            config = ReplayConfig(from_path=str(test_file), indexes="invalid")
            result = cmd_replay(config)
            assert result == 1

    def test_replay_no_matching_indexes(self):
        """Test replay when no records match specified indexes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test JSONL file
            test_file = Path(tmpdir) / "test.jsonl"
            content = '''{"type": "run", "index": 0, "cmd": "echo test", "exit_code": 0}
'''
            test_file.write_text(content)
            
            config = ReplayConfig(from_path=str(test_file), indexes="5-7")
            result = cmd_replay(config)
            assert result == 1