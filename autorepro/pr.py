#!/usr/bin/env python3
"""
AutoRepro PR module for automatically creating Draft PRs from reproduction plans.

Integrates with GitHub CLI to create PRs without additional Python dependencies.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .io.github import (
    create_pr_comment,
    get_pr_details,
    update_pr_body,
)
from .planner import (
    safe_truncate_60,
)
from .sync import ReportMeta, find_autorepro_content, find_synced_block, replace_synced_block
from .utils.github_api import update_comment
from .utils.repro_bundle import generate_plan_content


def build_pr_title(plan_data: dict[str, Any], is_draft: bool = True) -> str:
    """
    Build PR title from plan data.

    Args:
        plan_data: Plan JSON data with title field
        is_draft: Whether the PR will be created as draft

    Returns:
        Formatted PR title
    """
    title = plan_data.get("title", "Issue Reproduction Plan")
    # Truncate and clean title for PR
    clean_title = safe_truncate_60(title)
    suffix = " [draft]" if is_draft else ""
    return f"chore(repro): {clean_title}{suffix}"


def build_pr_body(plan_content: str, format_type: str) -> str:
    """
    Build PR body from plan content.

    Args:
        plan_content: Plan content (markdown or JSON)
        format_type: Format type ('md' or 'json')

    Returns:
        Formatted PR body in markdown
    """
    if format_type == "json":
        try:
            plan_data = json.loads(plan_content)
            title = plan_data.get("title", "Issue Reproduction Plan")
            assumptions = plan_data.get("assumptions", [])
            commands = plan_data.get("commands", [])[:3]  # Top 3 commands

            body_parts = [
                f"# {title}",
                "",
                "## Assumptions",
                "",
            ]

            for assumption in assumptions:
                body_parts.append(f"- {assumption}")

            body_parts.extend(
                [
                    "",
                    "## Candidate Commands (Top 3)",
                    "",
                ]
            )

            if commands:
                for i, cmd in enumerate(commands, 1):
                    cmd_str = cmd.get("cmd", "")
                    score = cmd.get("score", 0)
                    rationale = cmd.get("rationale", "")
                    body_parts.append(f"{i}. **`{cmd_str}`** (score: {score})")
                    body_parts.append(f"   - {rationale}")
                    body_parts.append("")
            else:
                body_parts.append("No candidate commands found.")
                body_parts.append("")

        except json.JSONDecodeError:
            body_parts = [
                "# Issue Reproduction Plan",
                "",
                "Error parsing plan data. See CI artifacts for details.",
                "",
            ]
    else:
        # For markdown format, extract key sections
        lines = plan_content.split("\n")
        title = "Issue Reproduction Plan"
        assumptions_section = []
        commands_section = []

        in_assumptions = False
        in_commands = False

        for line in lines:
            if line.startswith("# "):
                title = line[2:].strip()
            elif line.startswith("## Assumptions"):
                in_assumptions = True
                in_commands = False
                continue
            elif line.startswith("## Candidate Commands"):
                in_assumptions = False
                in_commands = True
                continue
            elif line.startswith("## "):
                in_assumptions = False
                in_commands = False
                continue

            if in_assumptions and line.strip() and line.startswith("- "):
                assumptions_section.append(line)
            elif in_commands and line.strip() and line.startswith("- "):
                commands_section.append(line)
                if len(commands_section) >= 3:  # Limit to top 3
                    break

        body_parts = [
            f"# {title}",
            "",
            "## Assumptions",
            "",
        ]

        if assumptions_section:
            body_parts.extend(assumptions_section)
        else:
            body_parts.append("- Standard development environment")

        body_parts.extend(
            [
                "",
                "## Candidate Commands (Top 3)",
                "",
            ]
        )

        if commands_section:
            for i, cmd_line in enumerate(commands_section[:3], 1):
                # Convert to numbered list
                body_parts.append(f"{i}.{cmd_line[1:]}")  # Remove "- " and add number
        else:
            body_parts.append("1. No candidate commands found")

        body_parts.append("")

    # Add artifact note
    body_parts.extend(
        [
            "---",
            "",
            "**Note**: Comprehensive reproduction bundle (with execution logs and "
            "environment metadata) is available as CI artifact.",
            "",
        ]
    )

    return "\n".join(body_parts)


def generate_plan_data(
    repo_path: Path,
    desc_or_file: str | None,
    format_type: str,
    min_score: int = 2,
) -> tuple[str, str]:
    """
    Generate plan data for PR creation.

    Args:
        repo_path: Repository path
        desc_or_file: Issue description or file path
        format_type: Output format ('md' or 'json')
        min_score: Minimum score for command suggestions

    Returns:
        Tuple of (plan_content, format_type)
    """
    # Use shared plan content generation
    content_str = generate_plan_content(desc_or_file, repo_path, format_type, min_score)

    return content_str, format_type


# New PR Enrichment Functions for T-018


def update_pr_comment(
    comment_id: int,
    body: str,
    gh_path: str = "gh",
    dry_run: bool = False,
) -> int:
    """
    Update an existing PR comment.

    Args:
        comment_id: Comment ID to update
        body: New comment body text
        gh_path: Path to gh CLI tool
        dry_run: If True, print command instead of executing

    Returns:
        Exit code (0 for success)

    Raises:
        RuntimeError: If comment update fails
    """
    return update_comment(comment_id, body, gh_path, dry_run, "PR")


def upsert_pr_comment(
    pr_number: int,
    body: str,
    *,
    replace_block: bool = True,
    gh_path: str = "gh",
    dry_run: bool = False,
) -> tuple[int, bool]:
    """
    Create or update PR comment with autorepro sync block.

    Args:
        pr_number: PR number to comment on
        body: Comment body with sync block
        replace_block: Whether to replace existing sync block or create new comment
        gh_path: Path to gh CLI tool
        dry_run: If True, print commands instead of executing

    Returns:
        Tuple of (exit_code, updated_existing)
    """
    log = logging.getLogger("autorepro")

    try:
        # Get existing PR details
        pr_data = get_pr_details(pr_number, gh_path)
        comments = pr_data.get("comments", [])
        existing_comment = find_autorepro_content(comments)

        if existing_comment and replace_block:
            # Update existing comment
            comment_id = existing_comment["id"]
            log.info(f"Updating existing autorepro comment #{comment_id}")

            exit_code = update_pr_comment(comment_id, body, gh_path, dry_run)
            return exit_code, True
        else:
            # Create new comment
            log.info(f"Creating new autorepro comment on PR #{pr_number}")
            exit_code = create_pr_comment(pr_number, body, gh_path, dry_run)
            return exit_code, False

    except Exception as e:
        log.error(f"Failed to upsert PR comment: {e}")
        return 1, False


def upsert_pr_body_sync_block(
    pr_number: int,
    plan_content: str,
    *,
    gh_path: str = "gh",
    dry_run: bool = False,
) -> int:
    """
    Add or update sync block in PR body/description.

    Args:
        pr_number: PR number to update
        plan_content: Plan content to include in sync block
        gh_path: Path to gh CLI tool
        dry_run: If True, print commands instead of executing

    Returns:
        Exit code (0 for success)
    """
    log = logging.getLogger("autorepro")

    try:
        # Get current PR details
        pr_data = get_pr_details(pr_number, gh_path)
        current_body = pr_data.get("body", "")

        # Check if sync block already exists
        if find_synced_block(current_body):
            # Replace existing sync block
            updated_body = replace_synced_block(current_body, plan_content)
            log.info(f"Updating existing sync block in PR #{pr_number} body")
        else:
            # Add new sync block at the end
            collapsible_block = f"""

---

<details>
<summary>📋 Reproduction Plan</summary>

<!-- autorepro:begin plan schema=1 -->
{plan_content.rstrip()}
<!-- autorepro:end plan -->

</details>"""
            updated_body = current_body.rstrip() + collapsible_block
            log.info(f"Adding new sync block to PR #{pr_number} body")

        return update_pr_body(pr_number, updated_body, gh_path, dry_run)

    except Exception as e:
        log.error(f"Failed to update PR body sync block: {e}")
        return 1


def generate_report_metadata_for_pr(
    desc_or_file: str | None,
    format_type: str = "md",
    repo_path: Path | None = None,
) -> ReportMeta:
    """
    Generate report bundle and return metadata for PR comment.

    Args:
        desc_or_file: Issue description text or file path
        format_type: Output format ('md' or 'json')
        repo_path: Repository path (defaults to current directory)

    Returns:
        ReportMeta with filename, size, and path information
    """
    # Reuse the existing report generation logic from issue module
    from .issue import generate_report_metadata

    # Convert issue.ReportMeta to sync.ReportMeta
    issue_meta = generate_report_metadata(desc_or_file, format_type, repo_path)
    return ReportMeta(
        filename=issue_meta.filename,
        size_bytes=issue_meta.size_bytes,
        path=issue_meta.path,
    )
