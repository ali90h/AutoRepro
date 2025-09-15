#!/usr/bin/env python3
"""
AutoRepro report module for combining plan + run log + environment metadata.

Creates zip artifacts for CI systems and issue tracking.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import shlex
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from autorepro.utils.file_ops import FileOperations

from . import __version__
from .config import config
from .detect import collect_evidence, detect_languages
from .planner import (
    extract_keywords,
    normalize,
    suggest_commands,
)
from .utils.repro_bundle import generate_plan_content


@dataclass
class ExecOutputConfig:
    """Configuration for exec output logging."""

    log_path: Path
    jsonl_path: Path
    command_str: str
    index: int
    cwd: Path
    start_iso: str
    duration_ms: int
    exit_code: int
    timed_out: bool
    stdout_full: str
    stderr_full: str


def collect_env_info(repo: Path) -> str:
    """
    Collect environment information including Python version, autorepro version,
    platform info, and scan synopsis.

    Args:
        repo: Repository path to scan

    Returns:
        Environment information as formatted string
    """
    log = logging.getLogger("autorepro")

    env_lines = []

    # Python version
    try:
        python_version = subprocess.check_output(
            [sys.executable, "--version"], text=True
        ).strip()
        env_lines.append(f"Python: {python_version}")
    except (subprocess.CalledProcessError, OSError) as e:
        log.warning(f"Failed to get Python version: {e}")
        env_lines.append(f"Python: {sys.version.split()[0]}")

    # AutoRepro version
    env_lines.append(f"AutoRepro: {__version__}")

    # Platform info
    try:
        platform_info = platform.platform()
        env_lines.append(f"Platform: {platform_info}")
    except Exception as e:
        log.warning(f"Failed to get platform info: {e}")
        env_lines.append("Platform: unknown")

    # Scan synopsis (no absolute paths)
    try:
        original_cwd = Path.cwd()
        os.chdir(repo)

        evidence = collect_evidence(Path("."))
        detected_languages = sorted(evidence.keys())

        # Create scan synopsis
        scan_data = {
            "schema_version": 1,
            "tool": "autorepro",
            "tool_version": __version__,
            "root": ".",  # Use relative path instead of absolute
            "detected": detected_languages,
            "languages": evidence,
        }

        env_lines.append(
            f"Scan Synopsis: {json.dumps(scan_data, separators=(',', ':'))}"
        )

    except Exception as e:
        log.warning(f"Failed to collect scan info: {e}")
        env_lines.append("Scan Synopsis: {}")
    finally:
        os.chdir(original_cwd)

    return "\n".join(env_lines) + "\n"


def write_plan(
    repo: Path, desc_or_file: str | None, format_type: str
) -> tuple[Path, str | bytes]:
    """
    Generate plan content and write to temporary file.

    Args:
        repo: Repository path
        desc_or_file: Issue description or file path
        format_type: Output format ('md' or 'json')

    Returns:
        Tuple of (temp_file_path, content)
    """

    # Use shared plan content generation
    content_str = generate_plan_content(
        desc_or_file, repo, format_type, min_score=config.limits.min_score_threshold
    )

    # Write to temporary file
    extension = ".json" if format_type == "json" else ".md"
    temp_file = Path(tempfile.mktemp(suffix=extension))

    with open(temp_file, "w", encoding="utf-8") as f:
        f.write(content_str)

    return temp_file, content_str


def _read_exec_input_for_maybe_exec(
    desc_or_file: str | None,
) -> str:
    """Read input text from file or return description directly."""
    if desc_or_file and Path(desc_or_file).exists():
        with open(desc_or_file, encoding="utf-8") as f:
            return f.read()
    return desc_or_file or ""


def _generate_exec_suggestions_for_maybe_exec(
    text: str, opts: dict[str, Any]
) -> list[tuple[str, int, str]]:
    """Generate command suggestions from input text."""
    normalized_text = normalize(text)
    keywords = extract_keywords(normalized_text)

    detected_languages = detect_languages(".")
    lang_names = [lang for lang, _ in detected_languages]

    min_score = opts.get("min_score", config.limits.min_score_threshold)
    return suggest_commands(keywords, lang_names, min_score)


def _validate_and_select_command(
    suggestions: list[tuple[str, int, str]], opts: dict[str, Any]
) -> int | None:
    """
    Validate suggestions and select command by index.

    Returns:
        Exit code if validation fails, None if successful
    """
    log = logging.getLogger("autorepro")

    min_score = opts.get("min_score", config.limits.min_score_threshold)

    # Check strict mode
    if opts.get("strict", False) and not suggestions:
        log.error(f"no candidate commands above min-score={min_score}")
        return 1

    if not suggestions:
        log.error("No commands to execute")
        return 1

    # Select command by index
    index = opts.get("index", 0)
    if index >= len(suggestions):
        log.error(f"Index {index} out of range (0-{len(suggestions) - 1})")
        return 2

    return None  # No error


def _prepare_exec_environment_for_maybe_exec(
    repo: Path, opts: dict[str, Any]
) -> dict[str, str] | None:
    """
    Prepare execution environment with env file and variables.

    Returns:
        Environment dict or None if error occurred
    """
    log = logging.getLogger("autorepro")
    env = os.environ.copy()

    # Load env file
    env_file = opts.get("env_file")
    if env_file:
        try:
            env_file_path = Path(env_file)
            if not env_file_path.is_absolute():
                env_file_path = repo / env_file
            with open(env_file_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        env[key] = value
        except OSError as e:
            log.error(f"Failed to read env file: {e}")
            return None

    # Apply env vars
    env_vars = opts.get("env", [])
    if env_vars:
        for env_str in env_vars:
            if "=" not in env_str:
                log.error(f"Invalid environment variable format: {env_str}")
                return None
            key, value = env_str.split("=", 1)
            env[key] = value

    return env


def _setup_exec_log_paths(repo: Path, opts: dict[str, Any]) -> tuple[Path, Path]:
    """Setup log file paths for execution output."""
    # Setup log files in temp directory
    temp_dir = Path(tempfile.mkdtemp())
    log_path = temp_dir / "run.log"
    jsonl_path = temp_dir / "runs.jsonl"

    # Override with user-specified paths if provided
    if opts.get("tee"):
        user_tee = Path(opts["tee"])
        if not user_tee.is_absolute():
            user_tee = repo / user_tee
        log_path = user_tee

    if opts.get("jsonl"):
        user_jsonl = Path(opts["jsonl"])
        if not user_jsonl.is_absolute():
            user_jsonl = repo / user_jsonl
        jsonl_path = user_jsonl

    return log_path, jsonl_path


def _execute_command_subprocess(
    command_str: str,
    cmd_parts: list[str],
    repo: Path,
    env: dict[str, str],
    timeout: int,
) -> tuple[int, str, str, bool] | None:
    """
    Execute command via subprocess.

    Returns:
        Tuple of (exit_code, stdout, stderr, timed_out) or None if execution failed
    """
    log = logging.getLogger("autorepro")

    log.info(f"Executing: {command_str}")

    try:
        result = subprocess.run(
            cmd_parts,
            cwd=repo,
            env=env,
            timeout=timeout,
            capture_output=True,
            text=True,
        )

        exit_code = result.returncode
        stdout_full = result.stdout
        stderr_full = result.stderr
        timed_out = False

    except subprocess.TimeoutExpired:
        log.error(f"Command timed out after {timeout} seconds")
        exit_code = 124
        stdout_full = ""
        stderr_full = f"Command timed out after {timeout} seconds"
        timed_out = True

    except FileNotFoundError:
        log.error(f"Command not found: {cmd_parts[0]}")
        return None
    except OSError as e:
        log.error(f"Failed to execute command: {e}")
        return None

    return exit_code, stdout_full, stderr_full, timed_out


def _write_exec_output_logs(config: ExecOutputConfig) -> None:
    """Write execution results to log and JSONL files."""
    # Write log file
    log_content = (
        f"=== {config.start_iso} - {config.command_str} ===\n"
        "STDOUT:\n"
        f"{config.stdout_full}"
        "\nSTDERR:\n"
        f"{config.stderr_full}"
        f"\nExit code: {config.exit_code}\n"
        "=" * 50 + "\n\n"
    )
    FileOperations.atomic_write(config.log_path, log_content)

    # Write JSONL file
    stdout_preview = config.stdout_full[:2000] if config.stdout_full else ""
    stderr_preview = config.stderr_full[:2000] if config.stderr_full else ""

    jsonl_record = {
        "schema_version": 1,
        "tool": "autorepro",
        "tool_version": __version__,
        "cmd": config.command_str,
        "index": config.index,
        "cwd": str(config.cwd),
        "start": config.start_iso,
        "duration_ms": config.duration_ms,
        "exit_code": config.exit_code,
        "timed_out": config.timed_out,
        "stdout_preview": stdout_preview,
        "stderr_preview": stderr_preview,
    }

    jsonl_content = json.dumps(jsonl_record) + "\n"
    FileOperations.atomic_write(config.jsonl_path, jsonl_content)


def maybe_exec(
    repo: Path, opts: dict[str, Any]
) -> tuple[int, Path | None, Path | None]:
    """
    Optionally execute the best command and return execution results.

    Args:
        repo: Repository path
        opts: Execution options including timeout, env vars, etc.

    Returns:
        Tuple of (exit_code, log_path, jsonl_path)
    """
    if not opts.get("exec", False):
        return 0, None, None

    # Generate plan to get commands
    desc_or_file = opts.get("desc") or opts.get("file")
    original_cwd = Path.cwd()

    try:
        os.chdir(repo)

        # Process text to get suggestions
        text = _read_exec_input_for_maybe_exec(desc_or_file)
        suggestions = _generate_exec_suggestions_for_maybe_exec(text, opts)

        # Validate suggestions and select command
        validation_result = _validate_and_select_command(suggestions, opts)
        if validation_result is not None:
            return validation_result, None, None

        index = opts.get("index", 0)
        selected_command = suggestions[index]
        command_str, score, rationale = selected_command

        # Prepare environment
        env = _prepare_exec_environment_for_maybe_exec(repo, opts)
        if env is None:
            return 1, None, None

        # Parse command
        try:
            cmd_parts = shlex.split(command_str)
        except ValueError as e:
            log = logging.getLogger("autorepro")
            log.error(f"Failed to parse command: {e}")
            return 2, None, None

        # Setup log paths
        log_path, jsonl_path = _setup_exec_log_paths(repo, opts)

        # Execute command
        start_time = datetime.now()
        start_iso = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        timeout = opts.get("timeout", config.timeouts.default_seconds)

        exec_result = _execute_command_subprocess(
            command_str, cmd_parts, repo, env, timeout
        )

        if exec_result is None:
            return 127, None, None  # Command not found or execution failed

        exit_code, stdout_full, stderr_full, timed_out = exec_result

        end_time = datetime.now()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)

        # Write output logs
        exec_config = ExecOutputConfig(
            log_path=log_path,
            jsonl_path=jsonl_path,
            command_str=command_str,
            index=index,
            cwd=repo,
            start_iso=start_iso,
            duration_ms=duration_ms,
            exit_code=exit_code,
            timed_out=timed_out,
            stdout_full=stdout_full,
            stderr_full=stderr_full,
        )
        _write_exec_output_logs(exec_config)

        return exit_code, log_path, jsonl_path

    finally:
        os.chdir(original_cwd)


def pack_zip(out_path: Path, files: dict[str, Path | str | bytes]) -> None:
    """
    Pack files into a zip archive.

    Args:
        out_path: Output zip file path
        files: Dictionary mapping archive names to file paths, strings, or bytes
    """
    log = logging.getLogger("autorepro")

    # Ensure output directory exists
    FileOperations.ensure_directory(out_path.parent)

    try:
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for archive_name, content in sorted(files.items()):
                if isinstance(content, Path):
                    # Add file from path
                    if content.exists():
                        zf.write(content, archive_name)
                    else:
                        log.warning(f"File not found, skipping: {content}")
                elif isinstance(content, str):
                    # Add string content
                    zf.writestr(archive_name, content)
                elif isinstance(content, bytes):
                    # Add bytes content
                    zf.writestr(archive_name, content)
                else:
                    log.warning(
                        f"Unknown content type for {archive_name}: {type(content)}"
                    )

        log.info(f"Created report bundle: {out_path}")

    except Exception as e:
        log.error(f"Failed to create zip file: {e}")
        raise


def cmd_report(  # noqa: PLR0913, C901, PLR0911, PLR0912
    desc: str | None = None,
    file: str | None = None,
    out: str = "repro_bundle.zip",
    format_type: str = "md",
    include: str | None = None,
    exec_: bool = False,
    timeout: int = 30,
    index: int = 0,
    env: list[str] | None = None,
    env_file: str | None = None,
    repo: str | None = None,
    force: bool = False,
    quiet: bool = False,
    verbose: int = 0,
) -> int:
    """
    Handle the report command with v2 support.

    Args:
        desc: Issue description text
        file: File path containing issue description
        out: Output path for the report bundle (use '-' for stdout preview)
        format_type: Output format for plan content ('md' or 'json')
        include: Comma-separated list of sections to include
        exec_: Whether to execute commands and include execution logs
        timeout: Timeout for command execution in seconds
        index: Index of command to execute
        env: List of environment variables to set
        env_file: Path to environment file
        repo: Repository path to analyze
        force: Whether to overwrite existing output file
        quiet: Show errors only
        verbose: Verbosity level

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    if env is None:
        env = []

    log = logging.getLogger("autorepro")

    # Parse include sections
    if include is None:
        include_sections = ["plan", "env"]
        if exec_:
            include_sections.append("exec")
    else:
        include_sections = [s.strip() for s in include.split(",") if s.strip()]

    # Validate include sections
    valid_sections = {"scan", "init", "plan", "env", "exec"}
    invalid_sections = set(include_sections) - valid_sections
    if invalid_sections:
        log.error(f"Invalid include sections: {', '.join(invalid_sections)}")
        return 1

    # Determine input text
    if desc and file:
        log.error("Cannot specify both --desc and --file")
        return 1
    elif not desc and not file:
        log.error("Must specify either --desc or --file")
        return 1

    # Read input text
    if file:
        try:
            with open(file, encoding="utf-8") as f:
                input_text = f.read().strip()
        except OSError as e:
            log.error(f"Failed to read file {file}: {e}")
            return 1
    else:
        input_text = desc or ""

    if not input_text:
        log.error("Input text cannot be empty")
        return 1

    # Determine repository path
    repo_path = Path(repo) if repo else Path.cwd()
    if not repo_path.exists():
        log.error(f"Repository path does not exist: {repo_path}")
        return 1

    # Handle stdout preview
    if out == "-":
        return _generate_report_preview(
            input_text,
            repo_path,
            include_sections,
            format_type,
            exec_,
            timeout,
            index,
            env,
            env_file,
        )

    # Generate report bundle
    try:
        bundle_path = _generate_report_bundle(
            input_text,
            repo_path,
            include_sections,
            format_type,
            exec_,
            timeout,
            index,
            env,
            env_file,
        )

        # Move to final location
        final_path = Path(out)
        if final_path.exists() and not force:
            log.error(f"Output file exists: {final_path}. Use --force to overwrite.")
            return 1

        bundle_path.rename(final_path)

        if not quiet:
            size_bytes = final_path.stat().st_size
            print(
                f"Report bundle created: {final_path} ({size_bytes:,} bytes)",
                file=sys.stderr,
            )

        return 0

    except Exception as e:
        log.error(f"Failed to generate report bundle: {e}")
        return 1


def _generate_report_preview(  # noqa: PLR0913
    input_text: str,
    repo_path: Path,
    include_sections: list[str],
    format_type: str,
    exec_: bool,
    timeout: int,
    index: int,
    env: list[str],
    env_file: str | None,
) -> int:
    """Generate report preview for stdout output."""
    print("schema=v2")
    print("Report bundle contents:")

    # Always include MANIFEST.json
    print("MANIFEST.json")

    # Include sections based on what's requested
    if "plan" in include_sections:
        plan_filename = f"repro.{format_type}"
        print(plan_filename)

    if "env" in include_sections:
        print("ENV.txt")

    if "scan" in include_sections:
        print("SCAN.json")

    if "init" in include_sections:
        print("INIT.preview.json")

    if "exec" in include_sections and exec_:
        print("run.log")
        print("runs.jsonl")

    return 0


def _generate_report_bundle(  # noqa: PLR0913
    input_text: str,
    repo_path: Path,
    include_sections: list[str],
    format_type: str,
    exec_: bool,
    timeout: int,
    index: int,
    env: list[str],
    env_file: str | None,
) -> Path:
    """Generate the actual report bundle and return the path."""
    import tempfile

    # Create temporary directory for bundle
    temp_dir = Path(tempfile.mkdtemp())
    bundle_path = temp_dir / "report_bundle.zip"

    # Prepare files for the bundle
    files: dict[str, Path | str | bytes] = {}

    # Generate plan content if requested
    if "plan" in include_sections:
        plan_content = generate_plan_content(
            input_text, repo_path, format_type, min_score=2
        )
        plan_filename = f"repro.{format_type}"
        files[plan_filename] = plan_content

    # Generate environment info if requested
    if "env" in include_sections:
        env_info = collect_env_info(repo_path)
        files["ENV.txt"] = env_info

    # Generate scan results if requested
    if "scan" in include_sections:
        scan_json = _generate_scan_json(repo_path)
        files["SCAN.json"] = scan_json

    # Generate init preview if requested
    if "init" in include_sections:
        init_preview = _generate_init_preview(repo_path)
        files["INIT.preview.json"] = init_preview

    # Generate execution logs if requested
    if "exec" in include_sections and exec_:
        exec_logs = _generate_exec_logs(
            input_text, repo_path, timeout, index, env, env_file
        )
        if exec_logs:
            files.update(exec_logs)

    # Generate MANIFEST.json
    manifest = _generate_manifest_json(include_sections, files, exec_)
    files["MANIFEST.json"] = manifest

    # Create the zip bundle
    pack_zip(bundle_path, files)

    return bundle_path


def _generate_scan_json(repo_path: Path) -> str:
    """Generate SCAN.json by calling scan --json."""
    try:
        from autorepro.detect import collect_evidence

        evidence = collect_evidence(repo_path)
        detected_languages = sorted(evidence.keys())

        scan_result = {
            "schema_version": 1,
            "tool": "autorepro",
            "tool_version": __version__,
            "root": str(repo_path.resolve()),
            "detected": detected_languages,
            "languages": evidence,
        }

        return json.dumps(scan_result, indent=2)
    except Exception as e:
        log = logging.getLogger("autorepro")
        log.error(f"Failed to generate scan results: {e}")
        return json.dumps({"error": str(e)})


def _generate_init_preview(repo_path: Path) -> str:
    """Generate INIT.preview.json without modifying the repository."""
    try:
        from autorepro.env import default_devcontainer

        # Generate devcontainer config in preview mode
        config = default_devcontainer()

        init_result = {
            "schema_version": 1,
            "tool": "autorepro",
            "tool_version": __version__,
            "preview": True,
            "devcontainer": config,
        }

        return json.dumps(init_result, indent=2)
    except Exception as e:
        log = logging.getLogger("autorepro")
        log.error(f"Failed to generate init preview: {e}")
        return json.dumps({"error": str(e)})


def _generate_exec_logs(  # noqa: PLR0913
    input_text: str,
    repo_path: Path,
    timeout: int,
    index: int,
    env: list[str],
    env_file: str | None,
) -> dict[str, str] | None:
    """Generate execution logs if exec is requested."""
    try:
        # This would integrate with the exec command logic
        # For now, return placeholder logs
        log_content = "=== Execution Log ===\nCommand: placeholder\nExit code: 0\n"
        jsonl_content = (
            json.dumps(
                {
                    "type": "run",
                    "index": index,
                    "cmd": "placeholder",
                    "exit_code": 0,
                }
            )
            + "\n"
        )

        return {
            "run.log": log_content,
            "runs.jsonl": jsonl_content,
        }
    except Exception as e:
        log = logging.getLogger("autorepro")
        log.error(f"Failed to generate execution logs: {e}")
        return None


def _generate_manifest_json(  # noqa: C901
    include_sections: list[str],
    files: dict[str, Path | str | bytes],
    exec_: bool,
) -> str:
    """Generate MANIFEST.json with schema version 2."""
    # Determine which sections are actually included
    sections = []
    if "plan" in include_sections:
        sections.append("plan")
    if "env" in include_sections:
        sections.append("env")
    if "scan" in include_sections:
        sections.append("scan")
    if "init" in include_sections:
        sections.append("init")
    if "exec" in include_sections and exec_:
        sections.append("exec")

    # List files in stable order
    file_list = []
    if "plan" in include_sections:
        file_list.append("repro.md" if "repro.md" in files else "repro.json")
    if "env" in include_sections:
        file_list.append("ENV.txt")
    if "scan" in include_sections:
        file_list.append("SCAN.json")
    if "init" in include_sections:
        file_list.append("INIT.preview.json")
    if "exec" in include_sections and exec_:
        file_list.extend(["run.log", "runs.jsonl"])

    # Always include MANIFEST.json
    file_list.append("MANIFEST.json")

    manifest = {
        "schema_version": 2,
        "tool": "autorepro",
        "tool_version": __version__,
        "sections": sections,
        "files": file_list,
    }

    return json.dumps(manifest, indent=2)
