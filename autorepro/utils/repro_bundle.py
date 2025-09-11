#!/usr/bin/env python3
"""Shared reproduction bundle generation utilities."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from ..core.planning import safe_truncate_60
from ..render.formats import build_repro_json, build_repro_md
from ..utils.plan_processing import process_plan_input


def generate_plan_content(
    desc_or_file: str | None,
    repo_path: Path,
    format_type: str,
    min_score: int = 2,
) -> str:
    """
    Generate plan content string for both PR and report use cases.

    Args:
        desc_or_file: Issue description or file path
        repo_path: Repository path
        format_type: Output format ('md' or 'json')
        min_score: Minimum score for command suggestions

    Returns:
        Generated plan content as string with proper newline termination
    """
    # Use common plan processing function
    plan_data = process_plan_input(desc_or_file, repo_path, min_score)

    # Generate content
    # Convert suggestions back to tuples for the builder functions
    command_tuples = [
        (suggestion["cmd"], suggestion["score"], suggestion["rationale"])
        for suggestion in plan_data.suggestions[:5]  # Limit to 5 commands
    ]

    if format_type == "json":
        content = build_repro_json(
            title=safe_truncate_60(plan_data.title),
            assumptions=plan_data.assumptions,
            commands=command_tuples,
            needs=plan_data.needs,
            next_steps=plan_data.next_steps,
        )
        content_str = json.dumps(content, indent=2)
    else:
        content_str = build_repro_md(
            plan_data.title,
            plan_data.assumptions,
            command_tuples,
            plan_data.needs,
            plan_data.next_steps,
        )

    # Ensure proper newline termination
    return content_str.rstrip() + "\n"


def _prepare_bundle_files(
    desc: str, repo_path: Path, format_type: str
) -> tuple[dict[str, Path | str | bytes], str]:
    """Prepare base files for the reproduction bundle."""
    from ..report import collect_env_info

    # Generate plan content
    plan_content = generate_plan_content(desc, repo_path, format_type, min_score=2)

    # Collect environment information
    env_info = collect_env_info(repo_path)

    # Prepare files for zip
    files: dict[str, Path | str | bytes] = {}
    files[f"repro.{format_type}"] = plan_content
    files["ENV.txt"] = env_info

    return files, env_info


def _execute_and_add_results(
    files: dict[str, Path | str | bytes], desc: str, repo_path: Path, timeout: int
) -> tuple[Path | None, Path | None]:
    """Execute command and add results to bundle files."""
    from ..report import maybe_exec

    exec_opts = {
        "exec": True,
        "timeout": timeout,
        "env": {},
        "desc_or_file": desc,
    }
    exit_code, log_path, jsonl_path = maybe_exec(repo_path, exec_opts)

    # Add execution results to bundle if available
    if log_path and log_path.exists():
        files["execution.log"] = log_path
    if jsonl_path and jsonl_path.exists():
        files["execution.jsonl"] = jsonl_path

    return log_path, jsonl_path


def _cleanup_temp_files(log_path: Path | None, jsonl_path: Path | None) -> None:
    """Clean up temporary execution files."""
    if log_path and log_path.exists():
        try:
            log_path.unlink()
        except OSError:
            pass  # Ignore cleanup errors
    if jsonl_path and jsonl_path.exists():
        try:
            jsonl_path.unlink()
        except OSError:
            pass  # Ignore cleanup errors


def build_repro_bundle(
    desc: str, timeout: int = 30, exec_: bool = False
) -> tuple[Path, int]:
    """
    Build a reproduction bundle with plan content and optional execution results.

    Args:
        desc: Issue description to create reproduction plan from
        timeout: Timeout for execution in seconds (default: 30)
        exec_: Whether to execute the best command (default: False)

    Returns:
        Tuple of (bundle_path, size_bytes)

    Raises:
        ValueError: If desc is empty or invalid
        RuntimeError: If bundle creation fails
    """
    # Import here to avoid circular dependencies
    from ..report import pack_zip

    if not desc or not desc.strip():
        raise ValueError("Description cannot be empty")

    repo_path = Path.cwd()
    format_type = "md"  # Default to markdown format

    try:
        # Prepare base bundle files
        files, env_info = _prepare_bundle_files(desc, repo_path, format_type)

        # Execute command if requested
        log_path, jsonl_path = None, None
        if exec_:
            log_path, jsonl_path = _execute_and_add_results(
                files, desc, repo_path, timeout
            )

        # Create bundle in temp directory
        temp_dir = Path(tempfile.mkdtemp())
        bundle_path = temp_dir / "repro_bundle.zip"

        pack_zip(bundle_path, files)

        # Get file size
        size_bytes = bundle_path.stat().st_size

        # Clean up temporary execution files
        if exec_:
            _cleanup_temp_files(log_path, jsonl_path)

        return bundle_path, size_bytes

    except Exception as e:
        raise RuntimeError(f"Failed to build repro bundle: {e}") from e
