#!/usr/bin/env python3
"""
AutoRepro Issue module for creating and updating GitHub issue comments with tagged plan
content.

This module handles GitHub issue synchronization with autorepro plans, including:
- Comment rendering with tagged sync blocks
- Block detection and replacement for updates
- Report attachment metadata
- Cross-linking with PRs
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any, NamedTuple

from .config.github_ops import (
    CommentOperationRequest,
    GitHubOperationConfig,
    PlanGenerationConfig,
    PlanGenerationRequest,
)
from .io.github import (
    IssueNotFoundError,
    create_issue_comment,
    get_current_pr_for_branch,
    get_issue_comments,
)
from .report import collect_env_info, pack_zip, write_plan
from .sync import SyncCommentConfig, find_autorepro_content, render_sync_comment
from .utils.github_api import update_comment
from .utils.repro_bundle import generate_plan_content


class ReportMeta(NamedTuple):
    """Metadata for report attachment."""

    filename: str
    size_bytes: int
    path: str


def render_issue_comment_md(
    plan_content: str,
    format_type: str,
    *,
    attach_report: ReportMeta | None = None,
    links: list[str] | None = None,
) -> str:
    """
    Render issue comment in Markdown format with tagged sync block.

    Args:
        plan_content: The plan content (markdown or JSON)
        format_type: Format type ('md' or 'json')
        attach_report: Optional report metadata to include
        links: Optional list of cross-reference links

    Returns:
        Formatted comment body with sync block tags
    """
    # Convert ReportMeta to sync.ReportMeta if needed
    sync_report_meta = None
    if attach_report:
        from .sync import ReportMeta as SyncReportMeta

        sync_report_meta = SyncReportMeta(
            filename=attach_report.filename,
            size_bytes=attach_report.size_bytes,
            path=attach_report.path,
        )

    return render_sync_comment(
        SyncCommentConfig(
            plan_content=plan_content,
            format_type=format_type,
            context="issue",
            attach_report=sync_report_meta,
            links=links,
            use_details=True,
        )
    )


def build_cross_reference_links(
    link_pr: int | None = None,
    link_current_pr: bool = False,
    gh_path: str = "gh",
) -> list[str]:
    """
    Build list of cross-reference links for the comment.

    Args:
        link_pr: Specific PR number to link to
        link_current_pr: Whether to link to PR for current branch
        gh_path: Path to gh CLI tool

    Returns:
        List of formatted cross-reference links
    """
    links = []

    if link_pr:
        links.append(f"Relates to #{link_pr}")

    if link_current_pr:
        try:
            # Get current branch
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                check=True,
            )
            current_branch = result.stdout.strip()

            if current_branch:
                pr_number = get_current_pr_for_branch(current_branch, gh_path)
                if pr_number:
                    links.append(f"Relates to #{pr_number}")

        except subprocess.CalledProcessError:
            pass

    return links


def generate_plan_for_issue(  # noqa: PLR0913 # Backward compatibility requires extra parameters
    request: PlanGenerationRequest | None = None,
    *,
    # Backward compatibility parameters
    desc_or_file: str | None = None,
    format_type: str = "md",
    min_score: int = 2,
    max_commands: int = 5,
    repo_path: Path | None = None,
) -> str:
    """
    Generate plan content for issue comment.

    Args:
        request: Plan generation request with description/file and configuration
        desc_or_file: (deprecated) Issue description text or file path
        format_type: (deprecated) Output format ('md' or 'json')
        min_score: (deprecated) Minimum score for command suggestions
        max_commands: (deprecated) Maximum number of commands to include
        repo_path: (deprecated) Repository path (defaults to current directory)

    Returns:
        Generated plan content as string
    """
    # Handle backward compatibility
    if request is None:
        config = PlanGenerationConfig(
            format_type=format_type,
            min_score=min_score,
            max_commands=max_commands,
            repo_path=repo_path or Path.cwd(),
        )
        request = PlanGenerationRequest(
            desc_or_file=desc_or_file,
            config=config,
        )

    # Use shared plan content generation function
    return generate_plan_content(
        request.desc_or_file,
        request.config.repo_path or Path.cwd(),
        request.config.format_type,
        request.config.min_score,
    )


def find_autorepro_comment(comments: list[dict[str, Any]]) -> dict[str, Any] | None:
    """
    Find existing autorepro comment in list of comments.

    Args:
        comments: List of comment objects from GitHub

    Returns:
        Comment object if found, None otherwise
    """
    return find_autorepro_content(comments)


def update_issue_comment(
    comment_id: int,
    body: str,
    gh_path: str = "gh",
    dry_run: bool = False,
) -> int:
    """
    Update an existing issue comment.

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
    return update_comment(comment_id, body, gh_path, dry_run, "issue")


def upsert_issue_comment(  # noqa: PLR0913 # Backward compatibility requires extra parameters
    issue_number_or_request: int | CommentOperationRequest | None = None,
    body: str | None = None,
    *,
    # Configuration parameters
    replace_block: bool = True,
    gh_path: str = "gh",
    dry_run: bool = False,
    # Backward compatibility keyword arguments
    issue_number: int | None = None,
) -> tuple[int, bool]:
    """
    Create or update issue comment with autorepro sync block.

    Args:
        issue_number_or_request: Issue number (int) or CommentOperationRequest object
        body: Comment body with sync block (required if first arg is int)
        replace_block: Whether to replace existing sync block or create new comment
        gh_path: Path to gh CLI tool
        dry_run: If True, print commands instead of executing

    Returns:
        Tuple of (exit_code, updated_existing)
    """
    # Handle different call patterns
    if isinstance(issue_number_or_request, CommentOperationRequest):
        request = issue_number_or_request
    elif isinstance(issue_number_or_request, int):
        if body is None:
            raise ValueError("body is required when issue_number_or_request is an int")

        config = GitHubOperationConfig(
            gh_path=gh_path,
            dry_run=dry_run,
            replace_block=replace_block,
        )
        request = CommentOperationRequest(
            target_id=issue_number_or_request,
            body=body,
            config=config,
        )
    elif issue_number is not None:
        # Handle keyword argument case
        if body is None:
            raise ValueError("body is required when issue_number is specified")

        config = GitHubOperationConfig(
            gh_path=gh_path,
            dry_run=dry_run,
            replace_block=replace_block,
        )
        request = CommentOperationRequest(
            target_id=issue_number,
            body=body,
            config=config,
        )
    else:
        raise ValueError(
            "Either issue_number_or_request or issue_number must be provided"
        )

    log = logging.getLogger("autorepro")

    try:
        # Get existing comments
        comments = get_issue_comments(request.target_id, request.config.gh_path)
        existing_comment = find_autorepro_comment(comments)

        if existing_comment and request.config.replace_block:
            # Update existing comment
            comment_id = existing_comment["id"]
            log.info(f"Updating existing autorepro comment #{comment_id}")

            exit_code = update_issue_comment(
                comment_id, request.body, request.config.gh_path, request.config.dry_run
            )
            return exit_code, True
        else:
            # Create new comment
            log.info(f"Creating new autorepro comment on issue #{request.target_id}")
            exit_code = create_issue_comment(
                request.target_id,
                request.body,
                request.config.gh_path,
                request.config.dry_run,
            )
            return exit_code, False

    except IssueNotFoundError:
        raise
    except Exception as e:
        log.error(f"Failed to upsert issue comment: {e}")
        return 1, False


def generate_report_metadata(
    desc_or_file: str | None,
    format_type: str = "md",
    repo_path: Path | None = None,
) -> ReportMeta:
    """
    Generate report bundle and return metadata for issue comment.

    Args:
        desc_or_file: Issue description text or file path
        format_type: Output format ('md' or 'json')
        repo_path: Repository path (defaults to current directory)

    Returns:
        ReportMeta with filename, size, and path information
    """
    if repo_path is None:
        repo_path = Path.cwd()

    log = logging.getLogger("autorepro")

    try:
        # Generate plan
        log.info("Generating reproduction plan for report...")
        plan_path, plan_content = write_plan(repo_path, desc_or_file, format_type)

        # Collect environment information
        log.info("Collecting environment information...")
        env_info = collect_env_info(repo_path)

        # Prepare files for zip
        files: dict[str, Path | str | bytes] = {}

        # Add plan file
        plan_filename = f"repro.{format_type}"
        files[plan_filename] = plan_content

        # Add environment info
        files["ENV.txt"] = env_info

        # Create zip bundle in temp directory
        import tempfile

        temp_dir = Path(tempfile.mkdtemp())
        zip_path = temp_dir / "repro_bundle.zip"

        pack_zip(zip_path, files)

        # Get file size
        size_bytes = zip_path.stat().st_size

        # Clean up temp plan file
        if plan_path.exists():
            plan_path.unlink()

        return ReportMeta(
            filename="repro_bundle.zip",
            size_bytes=size_bytes,
            path=str(zip_path),
        )

    except Exception as e:
        log.error(f"Failed to generate report bundle: {e}")
        # Return a placeholder metadata on error
        return ReportMeta(
            filename="repro_bundle.zip",
            size_bytes=0,
            path="(generation failed)",
        )
