"""Tests for --respect-gitignore functionality."""

import json
import tempfile
from pathlib import Path

from autorepro.cli import main


class TestScanGitignore:
    """Test --respect-gitignore functionality."""

    def test_gitignore_directory_exclusion(self, capsys):
        """Test that .gitignore excludes directories correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create test structure
            (tmpdir_path / "pyproject.toml").write_text("[build-system]\nrequires = []")
            (tmpdir_path / "node_modules").mkdir()
            (tmpdir_path / "node_modules" / "package.json").write_text("{}")
            (tmpdir_path / "src").mkdir()
            (tmpdir_path / "src" / "main.py").write_text("print('hello')")

            # Create .gitignore that ignores node_modules/
            (tmpdir_path / ".gitignore").write_text("node_modules/\n")

            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir_path)

                # Test without --respect-gitignore (should find both python and node)
                import sys

                original_argv = sys.argv
                sys.argv = ["autorepro", "scan", "--json"]

                exit_code = main()
                assert exit_code == 0

                captured = capsys.readouterr()
                result = json.loads(captured.out)

                # Should detect both python and node
                detected = set(result["detected"])
                assert "python" in detected
                assert "node" in detected

                # Test with --respect-gitignore (should only find python)
                sys.argv = ["autorepro", "scan", "--json", "--respect-gitignore"]

                exit_code = main()
                assert exit_code == 0

                captured = capsys.readouterr()
                result = json.loads(captured.out)

                # Should only detect python (node_modules is ignored)
                detected = set(result["detected"])
                assert "python" in detected
                assert "node" not in detected

            finally:
                sys.argv = original_argv
                os.chdir(original_cwd)

    def test_gitignore_file_pattern_exclusion(self, capsys):
        """Test that .gitignore excludes file patterns correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create test structure
            (tmpdir_path / "pyproject.toml").write_text("[build-system]\nrequires = []")
            (tmpdir_path / "main.py").write_text("print('hello')")
            (tmpdir_path / "test.py").write_text("def test(): pass")
            (tmpdir_path / "config.py").write_text("DEBUG = True")

            # Create .gitignore that ignores test.py and config.py
            (tmpdir_path / ".gitignore").write_text("test.py\nconfig.py\n")

            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir_path)

                # Test without --respect-gitignore
                import sys

                original_argv = sys.argv
                sys.argv = ["autorepro", "scan", "--json"]

                exit_code = main()
                assert exit_code == 0

                captured = capsys.readouterr()
                result = json.loads(captured.out)

                # Should detect python and have multiple files in files_sample
                assert "python" in result["detected"]
                python_files = result["languages"]["python"]["files_sample"]
                assert len(python_files) >= 3  # pyproject.toml + main.py + others

                # Test with --respect-gitignore
                sys.argv = ["autorepro", "scan", "--json", "--respect-gitignore"]

                exit_code = main()
                assert exit_code == 0

                captured = capsys.readouterr()
                result = json.loads(captured.out)

                # Should still detect python but with fewer files
                assert "python" in result["detected"]
                python_files = result["languages"]["python"]["files_sample"]

                # Should not include ignored files
                file_names = [Path(f).name for f in python_files]
                assert "test.py" not in file_names
                assert "config.py" not in file_names
                assert "pyproject.toml" in file_names or "main.py" in file_names

            finally:
                sys.argv = original_argv
                os.chdir(original_cwd)

    def test_gitignore_negation_patterns(self, capsys):
        """Test that .gitignore negation patterns (!pattern) work correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create test structure
            (tmpdir_path / "pyproject.toml").write_text("[build-system]\nrequires = []")
            (tmpdir_path / "dist").mkdir()
            (tmpdir_path / "dist" / "package.json").write_text("{}")
            (tmpdir_path / "dist" / ".keep").write_text("")

            # Create .gitignore that ignores dist/ but re-includes .keep files
            (tmpdir_path / ".gitignore").write_text("dist/\n!**/.keep\n")

            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir_path)

                # Test with --respect-gitignore
                import sys

                original_argv = sys.argv
                sys.argv = ["autorepro", "scan", "--json", "--respect-gitignore"]

                exit_code = main()
                assert exit_code == 0

                captured = capsys.readouterr()
                result = json.loads(captured.out)

                # Should only detect python (package.json is ignored, .keep is not a language file)
                detected = set(result["detected"])
                assert "python" in detected
                assert "node" not in detected

            finally:
                sys.argv = original_argv
                os.chdir(original_cwd)

    def test_gitignore_language_disappears_when_all_files_ignored(self, capsys):
        """Test that languages disappear entirely when all their files are ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create test structure - only node files, no python
            (tmpdir_path / "src").mkdir()
            (tmpdir_path / "src" / "package.json").write_text("{}")
            (tmpdir_path / "src" / "main.js").write_text("console.log('hello');")

            # Create .gitignore that ignores the entire src/ directory
            (tmpdir_path / ".gitignore").write_text("src/\n")

            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir_path)

                # Test without --respect-gitignore (should find node)
                import sys

                original_argv = sys.argv
                sys.argv = ["autorepro", "scan", "--json"]

                exit_code = main()
                assert exit_code == 0

                captured = capsys.readouterr()
                result = json.loads(captured.out)

                # Should detect node
                assert "node" in result["detected"]

                # Test with --respect-gitignore (should find nothing)
                sys.argv = ["autorepro", "scan", "--json", "--respect-gitignore"]

                exit_code = main()
                assert exit_code == 0

                captured = capsys.readouterr()
                result = json.loads(captured.out)

                # Should detect no languages
                assert result["detected"] == []
                assert result["languages"] == {}

            finally:
                sys.argv = original_argv
                os.chdir(original_cwd)

    def test_gitignore_glob_patterns(self, capsys):
        """Test that .gitignore glob patterns work correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create test structure
            (tmpdir_path / "pyproject.toml").write_text("[build-system]\nrequires = []")
            (tmpdir_path / "test1.py").write_text("def test1(): pass")
            (tmpdir_path / "test2.py").write_text("def test2(): pass")
            (tmpdir_path / "main.py").write_text("print('hello')")
            (tmpdir_path / "utils").mkdir()
            (tmpdir_path / "utils" / "test_helper.py").write_text("def helper(): pass")

            # Create .gitignore that ignores all test*.py files
            (tmpdir_path / ".gitignore").write_text("test*.py\n**/test*.py\n")

            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir_path)

                # Test with --respect-gitignore
                import sys

                original_argv = sys.argv
                sys.argv = ["autorepro", "scan", "--json", "--respect-gitignore"]

                exit_code = main()
                assert exit_code == 0

                captured = capsys.readouterr()
                result = json.loads(captured.out)

                # Should detect python but exclude test files
                assert "python" in result["detected"]
                python_files = result["languages"]["python"]["files_sample"]

                # Should not include test files
                file_names = [Path(f).name for f in python_files]
                assert "test1.py" not in file_names
                assert "test2.py" not in file_names
                assert "test_helper.py" not in file_names
                assert "pyproject.toml" in file_names or "main.py" in file_names

            finally:
                sys.argv = original_argv
                os.chdir(original_cwd)

    def test_gitignore_no_file_means_no_filtering(self, capsys):
        """Test that missing .gitignore file means no filtering occurs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create test structure (no .gitignore file)
            (tmpdir_path / "pyproject.toml").write_text("[build-system]\nrequires = []")
            (tmpdir_path / "node_modules").mkdir()
            (tmpdir_path / "node_modules" / "package.json").write_text("{}")

            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir_path)

                # Test with --respect-gitignore (should behave same as without)
                import sys

                original_argv = sys.argv

                # Without --respect-gitignore
                sys.argv = ["autorepro", "scan", "--json"]
                exit_code = main()
                assert exit_code == 0
                captured = capsys.readouterr()
                result_without = json.loads(captured.out)

                # With --respect-gitignore
                sys.argv = ["autorepro", "scan", "--json", "--respect-gitignore"]
                exit_code = main()
                assert exit_code == 0
                captured = capsys.readouterr()
                result_with = json.loads(captured.out)

                # Results should be identical (normalize root paths)
                result_without["root"] = "."
                result_with["root"] = "."
                assert result_without == result_with

            finally:
                sys.argv = original_argv
                os.chdir(original_cwd)
