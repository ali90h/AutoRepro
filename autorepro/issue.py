#!/usr/bin/env python3
"""
AutoRepro Issue module for creating and updating GitHub issue comments with tagged plan content.

This module handles GitHub issue synchronization with autorepro plans, including:
- Comment rendering with tagged sync blocks
- Block detection and replacement for updates
- Report attachment metadata
- Cross-linking with PRs
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, NamedTuple

from .detect import detect_languages
from .planner import (
    build_repro_json,
    build_repro_md,
    extract_keywords,
    normalize,
    safe_truncate_60,
    suggest_commands,
)
from .report import collect_env_info, pack_zip, write_plan
from .sync import (
    find_autorepro_content,
    render_sync_comment,
)


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
        plan_content,
        format_type,
        context="issue",
        attach_report=sync_report_meta,
        links=links,
        use_details=True,  # Default to using details for issues
    )


def get_current_pr_for_branch(branch_name: str, gh_path: str = "gh") -> int | None:
    """
    Get PR number for current branch if one exists.

    Args:
        branch_name: Branch name to search for
        gh_path: Path to gh CLI tool

    Returns:
        PR number if found, None otherwise
    """
    try:
        result = subprocess.run(
            [
                gh_path,
                "pr",
                "list",
                "--head",
                branch_name,
                "--state",
                "open",
                "--json",
                "number",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        prs = json.loads(result.stdout)
        if prs:
            return prs[0].get("number")
        return None

    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None


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


def generate_plan_for_issue(
    desc_or_file: str | None,
    format_type: str = "md",
    min_score: int = 2,
    max_commands: int = 5,
    repo_path: Path | None = None,
) -> str:
    """
    Generate plan content for issue comment.

    Args:
        desc_or_file: Issue description text or file path
        format_type: Output format ('md' or 'json')
        min_score: Minimum score for command suggestions
        max_commands: Maximum number of commands to include
        repo_path: Repository path (defaults to current directory)

    Returns:
        Generated plan content as string
    """
    if repo_path is None:
        repo_path = Path.cwd()

    # Read input text
    if desc_or_file and Path(desc_or_file).exists():
        # It's a file
        try:
            with open(desc_or_file, encoding="utf-8") as f:
                text = f.read()
        except OSError as e:
            # Try repo-relative path
            repo_file = repo_path / desc_or_file
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
        os.chdir(repo_path)

        normalized_text = normalize(text)
        keywords = extract_keywords(normalized_text)

        detected_languages = detect_languages(".")
        lang_names = [lang for lang, _ in detected_languages]

        suggestions = suggest_commands(keywords, lang_names, min_score)

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
        devcontainer_dir = repo_path / ".devcontainer/devcontainer.json"
        devcontainer_root = repo_path / "devcontainer.json"
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

        # Limit suggestions to max_commands
        limited_suggestions = suggestions[:max_commands]

        # Generate content
        if format_type == "json":
            content = build_repro_json(
                title=safe_truncate_60(title),
                assumptions=assumptions,
                commands=limited_suggestions,
                needs=needs,
                next_steps=next_steps,
            )
            content_str = json.dumps(content, indent=2)
        else:
            content_str = build_repro_md(title, assumptions, limited_suggestions, needs, next_steps)

        # Ensure proper newline termination
        content_str = content_str.rstrip() + "\n"

        return content_str

    finally:
        os.chdir(original_cwd)


class IssueNotFoundError(Exception):
    """Raised when specified issue number doesn't exist."""

    pass


def get_issue_comments(issue_number: int, gh_path: str = "gh") -> list[dict[str, Any]]:
    """
    Get all comments for a specific issue.

    Args:
        issue_number: Issue number to get comments for
        gh_path: Path to gh CLI tool

    Returns:
        List of comment objects with id, body, author, created_at

    Raises:
        IssueNotFoundError: If issue doesn't exist
        RuntimeError: If gh command fails
    """
    try:
        result = subprocess.run(
            [
                gh_path,
                "issue",
                "view",
                str(issue_number),
                "--json",
                "comments",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        issue_data = json.loads(result.stdout)
        return issue_data.get("comments", [])

    except subprocess.CalledProcessError as e:
        if "Could not resolve" in (e.stderr or ""):
            raise IssueNotFoundError(f"Issue #{issue_number} not found") from e
        raise RuntimeError(f"Failed to get issue comments: {e}") from e
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON response from gh: {e}") from e


def find_autorepro_comment(comments: list[dict[str, Any]]) -> dict[str, Any] | None:
    """
    Find existing autorepro comment in list of comments.

    Args:
        comments: List of comment objects from GitHub

    Returns:
        Comment object if found, None otherwise
    """
    return find_autorepro_content(comments)


def create_issue_comment(
    issue_number: int,
    body: str,
    gh_path: str = "gh",
    dry_run: bool = False,
) -> int:
    """
    Create a new comment on an issue.

    Args:
        issue_number: Issue number to comment on
        body: Comment body text
        gh_path: Path to gh CLI tool
        dry_run: If True, print command instead of executing

    Returns:
        Exit code (0 for success)

    Raises:
        RuntimeError: If comment creation fails
    """
    # Write body to temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(body)
        body_file = f.name

    try:
        cmd = [
            gh_path,
            "issue",
            "comment",
            str(issue_number),
            "--body-file",
            body_file,
        ]

        if dry_run:
            print(f"Would run: {' '.join(cmd)}")
            return 0

        subprocess.run(cmd, check=True, capture_output=True)
        return 0

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to create issue comment: {e}") from e
    finally:
        # Clean up temp file
        try:
            os.unlink(body_file)
        except OSError:
            pass


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
    # Write body to temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(body)
        body_file = f.name

    try:
        cmd = [
            gh_path,
            "api",
            f"/repos/{{owner}}/{{repo}}/issues/comments/{comment_id}",
            "--method",
            "PATCH",
            "--field",
            f"body=@{body_file}",
        ]

        if dry_run:
            print(f"Would run: {' '.join(cmd)}")
            return 0

        subprocess.run(cmd, check=True, capture_output=True)
        return 0

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to update issue comment: {e}") from e
    finally:
        # Clean up temp file
        try:
            os.unlink(body_file)
        except OSError:
            pass


def create_issue(
    title: str,
    body: str = "",
    labels: list[str] | None = None,
    assignees: list[str] | None = None,
    gh_path: str = "gh",
    dry_run: bool = False,
) -> int:
    """
    Create a new issue.

    Args:
        title: Issue title
        body: Issue body text
        labels: Labels to add to issue
        assignees: Users to assign to issue
        gh_path: Path to gh CLI tool
        dry_run: If True, print command instead of executing

    Returns:
        Issue number if successful

    Raises:
        RuntimeError: If issue creation fails
    """
    # Write body to temporary file if not empty
    body_file = None
    if body:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(body)
            body_file = f.name

    try:
        cmd = [gh_path, "issue", "create", "--title", title]

        if body_file:
            cmd.extend(["--body-file", body_file])
        else:
            cmd.extend(["--body", ""])

        if labels:
            cmd.extend(["--label", ",".join(labels)])

        if assignees:
            cmd.extend(["--assignee", ",".join(assignees)])

        if dry_run:
            print(f"Would run: {' '.join(cmd)}")
            return 0

        result = subprocess.run(cmd, check=True, capture_output=True, text=True)

        # Extract issue number from URL output
        issue_url = result.stdout.strip()
        issue_number = int(issue_url.split("/")[-1])
        return issue_number

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to create issue: {e}") from e
    except (ValueError, IndexError) as e:
        raise RuntimeError(f"Could not parse issue number from response: {result.stdout}") from e
    finally:
        # Clean up temp file
        if body_file:
            try:
                os.unlink(body_file)
            except OSError:
                pass


def add_issue_labels(
    issue_number: int,
    labels: list[str],
    gh_path: str = "gh",
    dry_run: bool = False,
) -> int:
    """
    Add labels to an issue (idempotent).

    Args:
        issue_number: Issue number to add labels to
        labels: List of label names to add
        gh_path: Path to gh CLI tool
        dry_run: If True, print command instead of executing

    Returns:
        Exit code (0 for success)
    """
    if not labels:
        return 0

    cmd = [
        gh_path,
        "issue",
        "edit",
        str(issue_number),
        "--add-label",
        ",".join(labels),
    ]

    if dry_run:
        print(f"Would run: {' '.join(cmd)}")
        return 0

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return 0
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to add labels: {e}") from e


def add_issue_assignees(
    issue_number: int,
    assignees: list[str],
    gh_path: str = "gh",
    dry_run: bool = False,
) -> int:
    """
    Add assignees to an issue (idempotent).

    Args:
        issue_number: Issue number to add assignees to
        assignees: List of usernames to assign
        gh_path: Path to gh CLI tool
        dry_run: If True, print command instead of executing

    Returns:
        Exit code (0 for success)
    """
    if not assignees:
        return 0

    cmd = [
        gh_path,
        "issue",
        "edit",
        str(issue_number),
        "--add-assignee",
        ",".join(assignees),
    ]

    if dry_run:
        print(f"Would run: {' '.join(cmd)}")
        return 0

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return 0
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to add assignees: {e}") from e


def upsert_issue_comment(
    issue_number: int,
    body: str,
    *,
    replace_block: bool = True,
    gh_path: str = "gh",
    dry_run: bool = False,
) -> tuple[int, bool]:
    """
    Create or update issue comment with autorepro sync block.

    Args:
        issue_number: Issue number to comment on
        body: Comment body with sync block
        replace_block: Whether to replace existing sync block or create new comment
        gh_path: Path to gh CLI tool
        dry_run: If True, print commands instead of executing

    Returns:
        Tuple of (exit_code, updated_existing)
    """
    log = logging.getLogger("autorepro")

    try:
        # Get existing comments
        comments = get_issue_comments(issue_number, gh_path)
        existing_comment = find_autorepro_comment(comments)

        if existing_comment and replace_block:
            # Update existing comment
            comment_id = existing_comment["id"]
            log.info(f"Updating existing autorepro comment #{comment_id}")

            exit_code = update_issue_comment(comment_id, body, gh_path, dry_run)
            return exit_code, True
        else:
            # Create new comment
            log.info(f"Creating new autorepro comment on issue #{issue_number}")
            exit_code = create_issue_comment(issue_number, body, gh_path, dry_run)
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
