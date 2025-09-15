"""Tests for the AutoRepro init command and environment functions."""

import json
import subprocess
import sys
from unittest.mock import patch

import pytest

from autorepro.cli import main
from autorepro.env import (
    DevcontainerExistsError,
    DevcontainerMisuseError,
    default_devcontainer,
    write_devcontainer,
)


class TestDefaultDevcontainer:
    """Test default devcontainer configuration generation."""

    def test_default_devcontainer_structure(self):
        """Test that default devcontainer has required structure."""
        config = default_devcontainer()

        assert isinstance(config, dict)
        assert config["name"] == "autorepro-dev"
        assert "features" in config
        assert "postCreateCommand" in config

    def test_default_devcontainer_features(self):
        """Test that default devcontainer includes required features."""
        config = default_devcontainer()
        features = config["features"]

        # Check Python 3.11
        assert "ghcr.io/devcontainers/features/python:1" in features
        assert features["ghcr.io/devcontainers/features/python:1"]["version"] == "3.11"

        # Check Node 20
        assert "ghcr.io/devcontainers/features/node:1" in features
        assert features["ghcr.io/devcontainers/features/node:1"]["version"] == "20"

        # Check Go 1.22
        assert "ghcr.io/devcontainers/features/go:1" in features
        assert features["ghcr.io/devcontainers/features/go:1"]["version"] == "1.22"

    def test_default_devcontainer_post_create(self):
        """Test that default devcontainer includes virtual environment setup."""
        config = default_devcontainer()
        post_create = config["postCreateCommand"]

        assert "python -m venv .venv" in post_create
        assert "source .venv/bin/activate" in post_create
        assert "pip install -e ." in post_create


class TestWriteDevcontainer:
    """Test devcontainer file writing functionality."""

    def test_write_devcontainer_success(self, tmp_path):
        """Test successful devcontainer creation."""
        config = {"name": "test", "features": {}}
        output_file = tmp_path / ".devcontainer" / "devcontainer.json"

        result_path, diff_lines = write_devcontainer(config, out=str(output_file))

        assert result_path == output_file
        assert diff_lines is None  # New file, no diff
        assert output_file.exists()

        # Verify content
        with open(output_file) as f:
            written_config = json.load(f)
        assert written_config == config

    def test_write_devcontainer_default_path(self, tmp_path, monkeypatch):
        """Test writing to default path."""
        monkeypatch.chdir(tmp_path)
        config = {"name": "test"}

        result_path, diff_lines = write_devcontainer(config)

        default_file = tmp_path / ".devcontainer" / "devcontainer.json"
        assert result_path == default_file
        assert diff_lines is None  # New file, no diff
        assert default_file.exists()

    def test_write_devcontainer_idempotent_without_force(self, tmp_path):
        """Test that existing file prevents overwrite without force."""
        output_file = tmp_path / "devcontainer.json"
        output_file.write_text("existing content")

        config = {"name": "test"}

        with pytest.raises(DevcontainerExistsError) as exc_info:
            write_devcontainer(config, out=str(output_file))

        assert exc_info.value.path == output_file
        assert output_file.read_text() == "existing content"

    def test_write_devcontainer_force_overwrite(self, tmp_path):
        """Test that force flag allows overwriting existing file."""
        output_file = tmp_path / "devcontainer.json"
        output_file.write_text("existing content")

        config = {"name": "test"}
        result_path, diff_lines = write_devcontainer(
            config, force=True, out=str(output_file)
        )

        assert result_path == output_file
        assert diff_lines is not None  # Overwritten file, should have diff info
        with open(output_file) as f:
            written_config = json.load(f)
        assert written_config == config

    def test_write_devcontainer_creates_parent_directories(self, tmp_path):
        """Test that parent directories are created as needed."""
        output_file = tmp_path / "deep" / "nested" / "path" / "devcontainer.json"
        config = {"name": "test"}

        result_path, diff_lines = write_devcontainer(config, out=str(output_file))

        assert result_path == output_file
        assert diff_lines is None  # New file, no diff
        assert output_file.exists()

    def test_write_devcontainer_invalid_path_error(self, tmp_path):
        """Test error handling for invalid paths."""
        config = {"name": "test"}
        # Use null character which is invalid in most filesystems
        invalid_path = str(tmp_path / "invalid\x00path")

        with pytest.raises(DevcontainerMisuseError):
            write_devcontainer(config, out=invalid_path)

    def test_write_devcontainer_permission_denied_error(self, tmp_path):
        """Test error handling for permission denied."""
        config = {"name": "test"}

        # Create a read-only directory to simulate permission error
        read_only_dir = tmp_path / "readonly"
        read_only_dir.mkdir()
        read_only_dir.chmod(0o444)  # Read-only

        output_file = read_only_dir / "devcontainer.json"

        with pytest.raises((OSError, PermissionError)):
            write_devcontainer(config, out=str(output_file))

        # Restore permissions for cleanup
        read_only_dir.chmod(0o755)

    def test_write_devcontainer_json_formatting(self, tmp_path):
        """Test that JSON is properly formatted."""
        config = {"name": "test", "features": {"b": 2, "a": 1}}
        output_file = tmp_path / "devcontainer.json"

        result_path, diff_lines = write_devcontainer(config, out=str(output_file))

        assert result_path == output_file
        assert diff_lines is None  # New file, no diff
        content = output_file.read_text()

        # Check formatting
        assert content.endswith("\n")
        assert "  " in content  # Indentation
        # Keys should be sorted
        lines = content.split("\n")
        feature_lines = [line for line in lines if '"a"' in line or '"b"' in line]
        assert len(feature_lines) == 2
        assert '"a"' in feature_lines[0]  # 'a' should come before 'b'


class TestInitCommand:
    """Test init command CLI integration."""

    def test_init_creates_default_devcontainer(self, tmp_path, monkeypatch):
        """Test that init command creates default devcontainer."""
        monkeypatch.chdir(tmp_path)

        with patch("sys.argv", ["autorepro", "init"]):
            exit_code = main()

        assert exit_code == 0
        devcontainer_file = tmp_path / ".devcontainer" / "devcontainer.json"
        assert devcontainer_file.exists()

        with open(devcontainer_file) as f:
            config = json.load(f)
        assert config["name"] == "autorepro-dev"

    def test_init_idempotent_behavior_without_force(self, tmp_path, monkeypatch):
        """Test that init command is idempotent without force."""
        monkeypatch.chdir(tmp_path)
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        devcontainer_file = devcontainer_dir / "devcontainer.json"
        devcontainer_file.write_text("existing")

        with patch("sys.argv", ["autorepro", "init"]):
            exit_code = main()

        assert exit_code == 0
        assert devcontainer_file.read_text() == "existing"

    def test_init_force_flag_overwrites_existing(self, tmp_path, monkeypatch):
        """Test that init --force overwrites existing file."""
        monkeypatch.chdir(tmp_path)
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        devcontainer_file = devcontainer_dir / "devcontainer.json"
        devcontainer_file.write_text("existing")

        with patch("sys.argv", ["autorepro", "init", "--force"]):
            exit_code = main()

        assert exit_code == 0
        with open(devcontainer_file) as f:
            config = json.load(f)
        assert config["name"] == "autorepro-dev"

    def test_init_custom_output_path(self, tmp_path, monkeypatch):
        """Test that init --out creates file at custom path."""
        monkeypatch.chdir(tmp_path)
        custom_path = tmp_path / "custom" / "my-devcontainer.json"

        with patch("sys.argv", ["autorepro", "init", "--out", str(custom_path)]):
            exit_code = main()

        assert exit_code == 0
        assert custom_path.exists()

        with open(custom_path) as f:
            config = json.load(f)
        assert config["name"] == "autorepro-dev"

    def test_init_creates_parent_directories(self, tmp_path, monkeypatch):
        """Test that init creates parent directories."""
        monkeypatch.chdir(tmp_path)
        nested_path = tmp_path / "deep" / "nested" / "devcontainer.json"

        with patch("sys.argv", ["autorepro", "init", "--out", str(nested_path)]):
            exit_code = main()

        assert exit_code == 0
        assert nested_path.exists()

    def test_init_invalid_path_error(self, tmp_path, monkeypatch):
        """Test init error handling for invalid paths."""
        monkeypatch.chdir(tmp_path)

        with patch("sys.argv", ["autorepro", "init", "--out", "invalid\x00path"]):
            exit_code = main()

        assert exit_code == 2

    def test_init_out_points_to_directory_error(self, tmp_path, monkeypatch):
        """Test init error when --out points to a directory."""
        monkeypatch.chdir(tmp_path)
        directory = tmp_path / "existing_dir"
        directory.mkdir()

        with patch("sys.argv", ["autorepro", "init", "--out", str(directory)]):
            exit_code = main()

        assert exit_code == 2

    def test_init_devcontainer_content_validation(self, tmp_path, monkeypatch):
        """Test that init creates valid devcontainer with all required features."""
        monkeypatch.chdir(tmp_path)

        with patch("sys.argv", ["autorepro", "init"]):
            exit_code = main()

        assert exit_code == 0

        devcontainer_file = tmp_path / ".devcontainer" / "devcontainer.json"
        with open(devcontainer_file) as f:
            config = json.load(f)

        # Validate required components
        assert config["name"] == "autorepro-dev"
        features = config["features"]

        # Validate Python 3.11
        assert "ghcr.io/devcontainers/features/python:1" in features
        assert features["ghcr.io/devcontainers/features/python:1"]["version"] == "3.11"

        # Validate Node 20
        assert "ghcr.io/devcontainers/features/node:1" in features
        assert features["ghcr.io/devcontainers/features/node:1"]["version"] == "20"

        # Validate Go 1.22
        assert "ghcr.io/devcontainers/features/go:1" in features
        assert features["ghcr.io/devcontainers/features/go:1"]["version"] == "1.22"

        # Validate post-creation command
        assert "postCreateCommand" in config
        post_create = config["postCreateCommand"]
        assert "python -m venv .venv" in post_create


class TestInitIntegration:
    """Integration tests using subprocess to test the actual CLI command."""

    def test_init_cli_success_via_subprocess(self, tmp_path):
        """Test init command success using subprocess."""
        result = subprocess.run(
            [sys.executable, "-m", "autorepro.cli", "init"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "Wrote devcontainer to" in result.stdout

        devcontainer_file = tmp_path / ".devcontainer" / "devcontainer.json"
        assert devcontainer_file.exists()

    def test_init_cli_force_flag_via_subprocess(self, tmp_path):
        """Test init --force flag using subprocess."""
        # Create existing file
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        devcontainer_file = devcontainer_dir / "devcontainer.json"
        devcontainer_file.write_text("existing")

        result = subprocess.run(
            [sys.executable, "-m", "autorepro.cli", "init", "--force"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "Overwrote devcontainer at" in result.stdout

    def test_init_cli_custom_out_via_subprocess(self, tmp_path):
        """Test init --out flag using subprocess."""
        custom_path = tmp_path / "my-container.json"

        result = subprocess.run(
            [sys.executable, "-m", "autorepro.cli", "init", "--out", str(custom_path)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert custom_path.exists()

    def test_init_cli_error_handling_via_subprocess(self, tmp_path):
        """Test init error handling using subprocess."""
        # Create existing file without force
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        devcontainer_file = devcontainer_dir / "devcontainer.json"
        devcontainer_file.write_text("existing")

        result = subprocess.run(
            [sys.executable, "-m", "autorepro.cli", "init"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "already exists" in result.stdout or "already exists" in result.stderr
        assert "Use --force" in result.stdout or "Use --force" in result.stderr

    def test_init_out_dash_ignores_force_flag(self, tmp_path):
        """Test that --out - ignores --force flag and outputs to stdout."""
        result = subprocess.run(
            [sys.executable, "-m", "autorepro.cli", "init", "--out", "-", "--force"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        # Should output JSON to stdout
        assert result.stdout.strip().startswith("{")
        assert result.stdout.strip().endswith("}")
        # Should not create any files
        devcontainer_file = tmp_path / ".devcontainer" / "devcontainer.json"
        assert not devcontainer_file.exists()

        # Parse JSON to verify it's valid
        import json

        config = json.loads(result.stdout)
        assert config["name"] == "autorepro-dev"

    def test_init_force_no_changes_preserves_mtime(self, tmp_path):
        """Test that init --force preserves mtime when content is unchanged."""
        import os
        import time

        # Create initial devcontainer
        args_str = ", ".join(f"'{arg}'" for arg in ["init"])
        cmd = [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, '.'); from autorepro.cli import main; "
            f"sys.exit(main([{args_str}]))",
        ]
        result1 = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True)
        assert result1.returncode == 0

        devcontainer_file = tmp_path / ".devcontainer" / "devcontainer.json"
        assert devcontainer_file.exists()

        # Get initial mtime
        mtime1 = os.path.getmtime(devcontainer_file)

        # Wait to ensure different timestamp would be visible
        time.sleep(0.1)

        # Run init --force when content would be identical
        args_str = ", ".join(f"'{arg}'" for arg in ["init", "--force"])
        cmd = [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, '.'); from autorepro.cli import main; "
            f"sys.exit(main([{args_str}]))",
        ]
        result2 = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True)
        assert result2.returncode == 0

        # mtime should be unchanged since content is identical
        mtime2 = os.path.getmtime(devcontainer_file)
        assert mtime2 == mtime1, (
            f"mtime should be preserved when content is unchanged. mtime1={mtime1}, mtime2={mtime2}"
        )

    def test_init_dry_run_ignores_force_flag(self, tmp_path):
        """Test that --dry-run ignores --force flag and outputs to stdout."""
        result = subprocess.run(
            [sys.executable, "-m", "autorepro.cli", "init", "--dry-run", "--force"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        # Should output JSON to stdout
        assert result.stdout.strip().startswith("{")
        assert result.stdout.strip().endswith("}")
        # Should not create any files
        devcontainer_file = tmp_path / ".devcontainer" / "devcontainer.json"
        assert not devcontainer_file.exists()

        # Parse JSON to verify it's valid
        import json

        config = json.loads(result.stdout)
        assert config["name"] == "autorepro-dev"

    def test_init_force_no_changes_preserves_mtime_alt(self, tmp_path):
        """Test that init --force preserves mtime when content is unchanged (alt)."""
        import os
        import time

        # Create initial devcontainer
        args_str = ", ".join(f"'{arg}'" for arg in ["init"])
        cmd = [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, '.'); from autorepro.cli import main; "
            f"sys.exit(main([{args_str}]))",
        ]
        result1 = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True)
        assert result1.returncode == 0

        devcontainer_file = tmp_path / ".devcontainer" / "devcontainer.json"
        assert devcontainer_file.exists()

        # Get initial mtime
        mtime1 = os.path.getmtime(devcontainer_file)

        # Wait to ensure different timestamp would be visible
        time.sleep(0.1)

        # Run init --force when content would be identical
        args_str = ", ".join(f"'{arg}'" for arg in ["init", "--force"])
        cmd = [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, '.'); from autorepro.cli import main; "
            f"sys.exit(main([{args_str}]))",
        ]
        result2 = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True)
        assert result2.returncode == 0

        # mtime should be unchanged since content is identical
        mtime2 = os.path.getmtime(devcontainer_file)
        assert mtime2 == mtime1, (
            f"mtime should be preserved when content is unchanged. mtime1={mtime1}, mtime2={mtime2}"
        )
