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
from datetime import datetime
from pathlib import Path
from typing import Any

from . import __version__
from .detect import collect_evidence, detect_languages
from .planner import (
    build_repro_json,
    build_repro_md,
    extract_keywords,
    normalize,
    safe_truncate_60,
    suggest_commands,
)


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
        python_version = subprocess.check_output([sys.executable, "--version"], text=True).strip()
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

        env_lines.append(f"Scan Synopsis: {json.dumps(scan_data, separators=(',', ':'))}")

    except Exception as e:
        log.warning(f"Failed to collect scan info: {e}")
        env_lines.append("Scan Synopsis: {}")
    finally:
        os.chdir(original_cwd)

    return "\n".join(env_lines) + "\n"


def write_plan(repo: Path, desc_or_file: str | None, format_type: str) -> tuple[Path, str | bytes]:
    """
    Generate plan content and write to temporary file.

    Args:
        repo: Repository path
        desc_or_file: Issue description or file path
        format_type: Output format ('md' or 'json')

    Returns:
        Tuple of (temp_file_path, content)
    """

    # Determine if input is a file or description
    if desc_or_file and Path(desc_or_file).exists():
        # It's a file
        try:
            with open(desc_or_file, encoding="utf-8") as f:
                text = f.read()
        except OSError as e:
            # Try repo-relative path
            repo_file = repo / desc_or_file
            if repo_file.exists():
                with open(repo_file, encoding="utf-8") as f:
                    text = f.read()
            else:
                raise OSError(f"Cannot read file {desc_or_file}") from e
    else:
        # It's a description
        text = desc_or_file or ""

    # Process text like in cmd_plan
    original_cwd = Path.cwd()
    try:
        os.chdir(repo)

        normalized_text = normalize(text)
        keywords = extract_keywords(normalized_text)

        detected_languages = detect_languages(".")
        lang_names = [lang for lang, _ in detected_languages]

        suggestions = suggest_commands(keywords, lang_names, min_score=2)

        # Generate title from first few words
        title_words = normalized_text.split()[:8]
        title = "Issue Reproduction Plan"
        if title_words:
            title = " ".join(title_words).title()

        # Generate assumptions
        assumptions = []
        if lang_names:
            lang_list = ", ".join(lang_names)
            assumptions.append(f"Project uses {lang_list} based on detected files")
        else:
            assumptions.append("Standard development environment")

        if "test" in keywords or "tests" in keywords or "testing" in keywords:
            assumptions.append("Issue is related to testing")
        if "ci" in keywords:
            assumptions.append("Issue occurs in CI/CD environment")
        if "install" in keywords or "setup" in keywords:
            assumptions.append("Installation or setup may be involved")

        if not assumptions:
            assumptions.append("Issue can be reproduced locally")

        # Generate environment needs
        needs = []

        # Check for devcontainer
        devcontainer_dir = repo / ".devcontainer/devcontainer.json"
        devcontainer_root = repo / "devcontainer.json"
        if devcontainer_dir.exists() or devcontainer_root.exists():
            needs.append("devcontainer: present")

        for lang in lang_names:
            if lang == "python":
                needs.append("Python 3.7+")
                if "pytest" in keywords:
                    needs.append("pytest package")
                if "tox" in keywords:
                    needs.append("tox package")
            elif lang in ("node", "javascript"):
                needs.append("Node.js 16+")
                needs.append("npm or yarn")
            elif lang == "go":
                needs.append("Go 1.19+")

        if not needs:
            needs.append("Standard development environment")

        # Generate next steps
        next_steps = [
            "Run the suggested commands in order of priority",
            "Check logs and error messages for patterns",
            "Review environment setup if commands fail",
            "Document any additional reproduction steps found",
        ]

        # Generate content
        if format_type == "json":
            content = build_repro_json(
                title=safe_truncate_60(title),
                assumptions=assumptions,
                commands=suggestions[:5],  # Limit to 5 commands
                needs=needs,
                next_steps=next_steps,
            )
            content_str = json.dumps(content, indent=2)
        else:
            content_str = build_repro_md(title, assumptions, suggestions[:5], needs, next_steps)

        # Ensure proper newline termination
        content_str = content_str.rstrip() + "\n"

        # Write to temporary file
        extension = ".json" if format_type == "json" else ".md"
        temp_file = Path(tempfile.mktemp(suffix=extension))

        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(content_str)

        return temp_file, content_str

    finally:
        os.chdir(original_cwd)


def maybe_exec(repo: Path, opts: dict[str, Any]) -> tuple[int, Path | None, Path | None]:
    """
    Optionally execute the best command and return execution results.

    Args:
        repo: Repository path
        opts: Execution options including timeout, env vars, etc.

    Returns:
        Tuple of (exit_code, log_path, jsonl_path)
    """
    log = logging.getLogger("autorepro")

    if not opts.get("exec", False):
        return 0, None, None

    # Generate plan to get commands
    desc_or_file = opts.get("desc") or opts.get("file")
    original_cwd = Path.cwd()

    try:
        os.chdir(repo)

        # Process text to get suggestions
        if desc_or_file and Path(desc_or_file).exists():
            with open(desc_or_file, encoding="utf-8") as f:
                text = f.read()
        else:
            text = desc_or_file or ""

        normalized_text = normalize(text)
        keywords = extract_keywords(normalized_text)

        detected_languages = detect_languages(".")
        lang_names = [lang for lang, _ in detected_languages]

        min_score = opts.get("min_score", 2)
        suggestions = suggest_commands(keywords, lang_names, min_score)

        # Check strict mode
        if opts.get("strict", False) and not suggestions:
            log.error(f"no candidate commands above min-score={min_score}")
            return 1, None, None

        if not suggestions:
            log.error("No commands to execute")
            return 1, None, None

        # Select command by index
        index = opts.get("index", 0)
        if index >= len(suggestions):
            log.error(f"Index {index} out of range (0-{len(suggestions) - 1})")
            return 2, None, None

        selected_command = suggestions[index]
        command_str, score, rationale = selected_command

        # Prepare environment
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
                return 1, None, None

        # Apply env vars
        env_vars = opts.get("env", [])
        if env_vars:
            for env_str in env_vars:
                if "=" not in env_str:
                    log.error(f"Invalid environment variable format: {env_str}")
                    return 2, None, None
                key, value = env_str.split("=", 1)
                env[key] = value

        # Parse command
        try:
            cmd_parts = shlex.split(command_str)
        except ValueError as e:
            log.error(f"Failed to parse command: {e}")
            return 2, None, None

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

        # Execute command
        start_time = datetime.now()
        start_iso = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        timeout = opts.get("timeout", 120)

        log.info(f"Executing: {command_str}")
        timed_out = False

        try:
            result = subprocess.run(
                cmd_parts,
                cwd=repo,
                env=env,
                timeout=timeout,
                capture_output=True,
                text=True,
            )

            end_time = datetime.now()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            exit_code = result.returncode
            stdout_full = result.stdout
            stderr_full = result.stderr

        except subprocess.TimeoutExpired:
            end_time = datetime.now()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            log.error(f"Command timed out after {timeout} seconds")
            exit_code = 124
            stdout_full = ""
            stderr_full = f"Command timed out after {timeout} seconds"
            timed_out = True

        except FileNotFoundError:
            log.error(f"Command not found: {cmd_parts[0]}")
            return 127, None, None
        except OSError as e:
            log.error(f"Failed to execute command: {e}")
            return 1, None, None

        # Write log file
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"=== {start_iso} - {command_str} ===\n")
            f.write("STDOUT:\n")
            f.write(stdout_full)
            f.write("\nSTDERR:\n")
            f.write(stderr_full)
            f.write(f"\nExit code: {exit_code}\n")
            f.write("=" * 50 + "\n\n")

        # Write JSONL file
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)

        stdout_preview = stdout_full[:2000] if stdout_full else ""
        stderr_preview = stderr_full[:2000] if stderr_full else ""

        jsonl_record = {
            "schema_version": 1,
            "tool": "autorepro",
            "tool_version": __version__,
            "cmd": command_str,
            "index": index,
            "cwd": str(repo),
            "start": start_iso,
            "duration_ms": duration_ms,
            "exit_code": exit_code,
            "timed_out": timed_out,
            "stdout_preview": stdout_preview,
            "stderr_preview": stderr_preview,
        }

        with open(jsonl_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(jsonl_record) + "\n")

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
    out_path.parent.mkdir(parents=True, exist_ok=True)

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
                    log.warning(f"Unknown content type for {archive_name}: {type(content)}")

        log.info(f"Created report bundle: {out_path}")

    except Exception as e:
        log.error(f"Failed to create zip file: {e}")
        raise
