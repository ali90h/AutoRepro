"""Tests to ensure output ends with newline."""

from tests.test_utils import run_autorepro_subprocess


def run_cli_subprocess(args, cwd=None):
    """Helper to run autorepro CLI via subprocess."""
    return run_autorepro_subprocess(args, cwd=cwd)


class TestNewlineEndings:
    """Test that all output formats end with newline."""

    def test_init_json_ends_with_newline(self, tmp_path):
        """Test that init --out - produces JSON ending with newline."""
        result = run_cli_subprocess(["init", "--out", "-"], cwd=tmp_path)
        assert result.returncode == 0
        assert result.stdout.endswith("\n"), "JSON output should end with newline"

    def test_init_dry_run_ends_with_newline(self, tmp_path):
        """Test that init --dry-run produces JSON ending with newline."""
        result = run_cli_subprocess(["init", "--dry-run"], cwd=tmp_path)
        assert result.returncode == 0
        assert result.stdout.endswith("\n"), "JSON output should end with newline"

    def test_plan_markdown_ends_with_newline(self, tmp_path):
        """Test that plan --out - produces Markdown ending with newline."""
        result = run_cli_subprocess(
            ["plan", "--desc", "test issue", "--out", "-"], cwd=tmp_path
        )
        assert result.returncode == 0
        assert result.stdout.endswith("\n"), "Markdown output should end with newline"

    def test_plan_dry_run_ends_with_newline(self, tmp_path):
        """Test that plan --dry-run produces Markdown ending with newline."""
        result = run_cli_subprocess(
            ["plan", "--desc", "test issue", "--dry-run"], cwd=tmp_path
        )
        assert result.returncode == 0
        assert result.stdout.endswith("\n"), "Markdown output should end with newline"

    def test_plan_file_output_ends_with_newline(self, tmp_path):
        """Test that plan file output ends with newline."""
        output_file = tmp_path / "test.md"
        result = run_cli_subprocess(
            ["plan", "--desc", "test issue", "--out", str(output_file)], cwd=tmp_path
        )
        assert result.returncode == 0
        assert output_file.exists()
        content = output_file.read_text()
        assert content.endswith("\n"), "Markdown file should end with newline"

    def test_init_file_output_ends_with_newline(self, tmp_path):
        """Test that init file output ends with newline."""
        result = run_cli_subprocess(["init"], cwd=tmp_path)
        assert result.returncode == 0
        devcontainer_file = tmp_path / ".devcontainer" / "devcontainer.json"
        assert devcontainer_file.exists()
        content = devcontainer_file.read_text()
        assert content.endswith("\n"), "JSON file should end with newline"
