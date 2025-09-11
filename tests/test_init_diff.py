"""Tests for the AutoRepro init command diff functionality."""

import json
import subprocess
import sys
from unittest.mock import patch

from autorepro.cli import main
from autorepro.env import default_devcontainer, json_diff, write_devcontainer


class TestJsonDiff:
    """Test the json_diff function."""

    def test_json_diff_no_changes(self):
        """Test diff with identical dictionaries."""
        old = {"name": "test", "features": {"python": {"version": "3.11"}}}
        new = {"name": "test", "features": {"python": {"version": "3.11"}}}

        diff = json_diff(old, new)
        assert diff == []

    def test_json_diff_value_change(self):
        """Test diff with changed value."""
        old = {"name": "test", "features": {"python": {"version": "3.10"}}}
        new = {"name": "test", "features": {"python": {"version": "3.11"}}}

        diff = json_diff(old, new)
        assert diff == ['~ features.python.version: "3.10" -> "3.11"']

    def test_json_diff_key_added(self):
        """Test diff with added key."""
        old = {"name": "test", "features": {}}
        new = {"name": "test", "features": {"go": {"version": "1.22"}}}

        diff = json_diff(old, new)
        assert diff == ['+ features.go: {"version": "1.22"}']

    def test_json_diff_key_removed(self):
        """Test diff with removed key."""
        old = {"name": "test", "features": {"rust": {"version": "1.75"}}}
        new = {"name": "test", "features": {}}

        diff = json_diff(old, new)
        assert diff == ['- features.rust: {"version": "1.75"}']

    def test_json_diff_multiple_changes(self):
        """Test diff with multiple types of changes."""
        old = {
            "name": "old-name",
            "features": {"python": {"version": "3.10"}, "rust": {"version": "1.75"}},
        }
        new = {
            "name": "new-name",
            "features": {"python": {"version": "3.11"}, "go": {"version": "1.22"}},
        }

        diff = json_diff(old, new)
        expected = [
            '+ features.go: {"version": "1.22"}',
            '- features.rust: {"version": "1.75"}',
            '~ features.python.version: "3.10" -> "3.11"',
            '~ name: "old-name" -> "new-name"',
        ]
        assert diff == expected

    def test_json_diff_nested_dict_change(self):
        """Test diff with deeply nested dictionary changes."""
        old = {"config": {"sub": {"deep": "old-value"}}}
        new = {"config": {"sub": {"deep": "new-value"}}}

        diff = json_diff(old, new)
        assert diff == ['~ config.sub.deep: "old-value" -> "new-value"']

    def test_json_diff_list_as_scalar(self):
        """Test that lists are treated as scalar values."""
        old = {"commands": ["cmd1", "cmd2"]}
        new = {"commands": ["cmd1", "cmd2", "cmd3"]}

        diff = json_diff(old, new)
        assert diff == ['~ commands: ["cmd1", "cmd2"] -> ["cmd1", "cmd2", "cmd3"]']

    def test_json_diff_sorting(self):
        """Test that diff lines are sorted by path."""
        old = {"z": 1, "a": 2, "m": 3}
        new = {"z": 10, "a": 20, "m": 30}

        diff = json_diff(old, new)
        expected = ["~ a: 2 -> 20", "~ m: 3 -> 30", "~ z: 1 -> 10"]
        assert diff == expected

    def test_json_diff_different_types(self):
        """Test diff between different types (treated as scalar)."""
        old = {"value": "string"}
        new = {"value": 123}

        diff = json_diff(old, new)
        assert diff == ['~ value: "string" -> 123']


class TestWriteDevcontainerWithDiff:
    """Test write_devcontainer with diff functionality."""

    def test_write_devcontainer_new_file_returns_none_diff(self, tmp_path):
        """Test that new file creation returns None for diff."""
        config = {"name": "test"}
        output_file = tmp_path / "devcontainer.json"

        result_path, diff_lines = write_devcontainer(config, out=str(output_file))

        assert result_path == output_file
        assert diff_lines is None

    def test_write_devcontainer_overwrite_with_changes(self, tmp_path):
        """Test overwrite with changes returns diff lines."""
        # Create initial file
        old_config = {"name": "old", "features": {"python": {"version": "3.10"}}}
        output_file = tmp_path / "devcontainer.json"
        output_file.write_text(json.dumps(old_config, indent=2) + "\n")

        # Overwrite with new config
        new_config = {"name": "new", "features": {"python": {"version": "3.11"}}}
        result_path, diff_lines = write_devcontainer(
            new_config, force=True, out=str(output_file)
        )

        assert result_path == output_file
        assert diff_lines is not None
        expected_diff = [
            '~ features.python.version: "3.10" -> "3.11"',
            '~ name: "old" -> "new"',
        ]
        assert diff_lines == expected_diff

    def test_write_devcontainer_overwrite_no_changes(self, tmp_path):
        """Test overwrite with identical config returns empty diff."""
        # Create initial file
        config = {"name": "test", "features": {"python": {"version": "3.11"}}}
        output_file = tmp_path / "devcontainer.json"
        output_file.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")

        # Overwrite with same config
        result_path, diff_lines = write_devcontainer(
            config, force=True, out=str(output_file)
        )

        assert result_path == output_file
        assert diff_lines is not None
        assert diff_lines == []  # Empty list means no changes

    def test_write_devcontainer_invalid_json_existing_file(self, tmp_path):
        """Test overwrite when existing file has invalid JSON."""
        output_file = tmp_path / "devcontainer.json"
        output_file.write_text("invalid json content")

        config = {"name": "test"}
        result_path, diff_lines = write_devcontainer(
            config, force=True, out=str(output_file)
        )

        assert result_path == output_file
        assert diff_lines is not None
        assert diff_lines == []  # Empty list for invalid JSON case


class TestInitCommandDiff:
    """Test init command CLI with diff functionality."""

    def test_init_first_time_create_no_diff(self, tmp_path, monkeypatch, capsys):
        """Test first-time create shows no diff output."""
        monkeypatch.chdir(tmp_path)

        with patch("sys.argv", ["autorepro", "init"]):
            exit_code = main()

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Wrote devcontainer to" in captured.out
        assert "Changes:" not in captured.out
        assert "No changes." not in captured.out

    def test_init_force_with_changes_shows_diff(self, tmp_path, monkeypatch, capsys):
        """Test force overwrite with changes shows diff output."""
        monkeypatch.chdir(tmp_path)

        # Create initial devcontainer with different config
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        devcontainer_file = devcontainer_dir / "devcontainer.json"

        # Patch default_devcontainer to return different config for comparison
        old_config = {
            "name": "old-name",
            "features": {
                "ghcr.io/devcontainers/features/python:1": {"version": "3.10"}
            },
            "postCreateCommand": "old command",
        }
        devcontainer_file.write_text(
            json.dumps(old_config, indent=2, sort_keys=True) + "\n"
        )

        with patch("sys.argv", ["autorepro", "init", "--force"]):
            exit_code = main()

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Overwrote devcontainer at" in captured.out
        assert "Changes:" in captured.out
        # Should show the differences from the old config to default config
        assert "+" in captured.out or "~" in captured.out or "-" in captured.out

    def test_init_force_no_changes(self, tmp_path, monkeypatch, capsys):
        """Test force overwrite with no changes shows 'No changes.'."""
        monkeypatch.chdir(tmp_path)

        # Create initial devcontainer with same config as default
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        devcontainer_file = devcontainer_dir / "devcontainer.json"

        # Write the exact default configuration
        default_config = default_devcontainer()
        devcontainer_file.write_text(
            json.dumps(default_config, indent=2, sort_keys=True) + "\n"
        )

        with patch("sys.argv", ["autorepro", "init", "--force"]):
            exit_code = main()

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Overwrote devcontainer at" in captured.out
        assert "No changes." in captured.out

    def test_init_single_value_change(self, tmp_path, monkeypatch, capsys):
        """Test single value change in force overwrite."""
        monkeypatch.chdir(tmp_path)

        # Create devcontainer with modified postCreateCommand
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        devcontainer_file = devcontainer_dir / "devcontainer.json"

        config_with_diff = default_devcontainer()
        config_with_diff["postCreateCommand"] = "echo 'old command'"
        devcontainer_file.write_text(
            json.dumps(config_with_diff, indent=2, sort_keys=True) + "\n"
        )

        with patch("sys.argv", ["autorepro", "init", "--force"]):
            exit_code = main()

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Overwrote devcontainer at" in captured.out
        assert "Changes:" in captured.out
        assert "~ postCreateCommand:" in captured.out
        assert "echo 'old command'" in captured.out

    def test_init_key_added_removed(self, tmp_path, monkeypatch, capsys):
        """Test key addition and removal in force overwrite."""
        monkeypatch.chdir(tmp_path)

        # Create devcontainer with extra feature and missing standard feature
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        devcontainer_file = devcontainer_dir / "devcontainer.json"

        # Start with default config and modify it
        old_config = default_devcontainer()
        # Add a rust feature that won't be in the new default
        old_config["features"]["ghcr.io/devcontainers/features/rust:1"] = {
            "version": "1.75"
        }
        # Remove go feature
        del old_config["features"]["ghcr.io/devcontainers/features/go:1"]

        devcontainer_file.write_text(
            json.dumps(old_config, indent=2, sort_keys=True) + "\n"
        )

        with patch("sys.argv", ["autorepro", "init", "--force"]):
            exit_code = main()

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Overwrote devcontainer at" in captured.out
        assert "Changes:" in captured.out
        # Should show go being added and rust being removed
        assert "+ features" in captured.out and "go" in captured.out
        assert "- features" in captured.out and "rust" in captured.out


class TestInitDiffIntegration:
    """Integration tests for init diff using subprocess."""

    def test_init_diff_subprocess_first_create(self, tmp_path):
        """Test first-time create via subprocess shows no diff."""
        args_str = ", ".join(f"'{arg}'" for arg in ["init"])
        cmd = [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, '.'); from autorepro.cli import main; "
            f"sys.exit(main([{args_str}]))",
        ]
        result = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True)

        assert result.returncode == 0
        assert "Wrote devcontainer to" in result.stdout
        assert "Changes:" not in result.stdout

    def test_init_diff_subprocess_force_with_changes(self, tmp_path):
        """Test force overwrite with changes via subprocess."""
        # Create initial file
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        devcontainer_file = devcontainer_dir / "devcontainer.json"
        devcontainer_file.write_text('{"name": "old-name"}')

        args_str = ", ".join(f"'{arg}'" for arg in ["init", "--force"])
        cmd = [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, '.'); from autorepro.cli import main; "
            f"sys.exit(main([{args_str}]))",
        ]
        result = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True)

        assert result.returncode == 0
        assert "Overwrote devcontainer at" in result.stdout
        assert "Changes:" in result.stdout

    def test_init_diff_subprocess_force_no_changes(self, tmp_path):
        """Test force overwrite with no changes via subprocess."""
        # Create file with default config
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        devcontainer_file = devcontainer_dir / "devcontainer.json"

        default_config = default_devcontainer()
        devcontainer_file.write_text(
            json.dumps(default_config, indent=2, sort_keys=True) + "\n"
        )

        args_str = ", ".join(f"'{arg}'" for arg in ["init", "--force"])
        cmd = [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, '.'); from autorepro.cli import main; "
            f"sys.exit(main([{args_str}]))",
        ]
        result = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True)

        assert result.returncode == 0
        assert "Overwrote devcontainer at" in result.stdout
        assert "No changes." in result.stdout
