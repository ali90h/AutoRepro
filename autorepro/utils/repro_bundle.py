#!/usr/bin/env python3
"""
Shared reproduction bundle generation utilities.
"""

from __future__ import annotations

import json
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
    content_str = content_str.rstrip() + "\n"

    return content_str
