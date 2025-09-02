#!/usr/bin/env python3
"""
AutoRepro PR module for automatically creating Draft PRs from reproduction plans.

Integrates with GitHub CLI to create PRs without additional Python dependencies.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .detect import detect_languages
from .planner import (
    build_repro_json,
    build_repro_md,
    extract_keywords,
    normalize,
    safe_truncate_60,
    suggest_commands,
)
from .sync import (
    ReportMeta,
    find_autorepro_content,
    find_synced_block,
    replace_synced_block,
)


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

            if in_assumptions and line.strip():
                if line.startswith("- "):
                    assumptions_section.append(line)
            elif in_commands and line.strip():
                if line.startswith("- "):
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


def detect_repo_slug() -> str:
    """
    Detect GitHub repository slug (owner/repo) from git remote.

    Returns:
        Repository slug in format 'owner/repo'

    Raises:
        RuntimeError: If unable to detect repository
    """
    try:
        # Get remote URL
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True,
        )
        remote_url = result.stdout.strip()

        # Parse different URL formats
        # SSH: git@github.com:owner/repo.git
        # HTTPS: https://github.com/owner/repo.git
        ssh_match = re.search(r"git@github\.com:([^/]+)/([^/]+)(?:\.git)?$", remote_url)
        if ssh_match:
            owner, repo = ssh_match.groups()
            return f"{owner}/{repo.removesuffix('.git')}"

        https_match = re.search(r"https://github\.com/([^/]+)/([^/]+)(?:\.git)?/?$", remote_url)
        if https_match:
            owner, repo = https_match.groups()
            return f"{owner}/{repo.removesuffix('.git')}"

        raise RuntimeError(f"Unable to parse GitHub URL: {remote_url}")

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to get git remote: {e}") from e


def ensure_pushed(head_branch: str) -> bool:
    """
    Ensure the current branch is pushed to origin.

    Args:
        head_branch: Branch name to push

    Returns:
        True if push was needed and successful, False if already up to date

    Raises:
        RuntimeError: If push fails
    """
    log = logging.getLogger("autorepro")

    try:
        # Check if remote branch exists and is up to date
        result = subprocess.run(
            ["git", "ls-remote", "--heads", "origin", head_branch],
            capture_output=True,
            text=True,
        )

        remote_exists = bool(result.stdout.strip())

        if remote_exists:
            # Check if local is ahead of remote
            result = subprocess.run(
                ["git", "rev-list", "--count", f"origin/{head_branch}..HEAD"],
                capture_output=True,
                text=True,
            )

            commits_ahead = int(result.stdout.strip()) if result.returncode == 0 else 1

            if commits_ahead == 0:
                log.info(f"Branch {head_branch} is up to date with remote")
                return False

        # Push branch to origin
        log.info(f"Pushing branch {head_branch} to origin...")
        subprocess.run(
            ["git", "push", "-u", "origin", head_branch],
            check=True,
            capture_output=True,
        )

        return True

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to push branch {head_branch}: {e}") from e


def find_existing_draft(head_branch: str, gh_path: str = "gh") -> int | None:
    """
    Find existing draft PR for the given head branch.

    Args:
        head_branch: Branch name to search for
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
                "--state",
                "open",
                "--head",
                head_branch,
                "--json",
                "number,isDraft",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        prs = json.loads(result.stdout)

        # Find draft PR
        for pr in prs:
            if pr.get("isDraft", False):
                return pr.get("number")

        return None

    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None


def create_or_update_pr(
    title: str,
    body: str,
    base_branch: str = "main",
    head_branch: str | None = None,
    draft: bool = True,
    labels: list[str] | None = None,
    assignees: list[str] | None = None,
    reviewers: list[str] | None = None,
    update_if_exists: bool = False,
    gh_path: str = "gh",
    dry_run: bool = False,
) -> tuple[int, bool]:  # (exit_code, created_new)
    """
    Create or update a GitHub PR.

    Args:
        title: PR title
        body: PR body
        base_branch: Target branch
        head_branch: Source branch (current if None)
        draft: Whether to create as draft
        labels: Labels to add
        assignees: Users to assign
        reviewers: Users to request review from
        update_if_exists: Whether to update existing draft PR
        gh_path: Path to gh CLI
        dry_run: Print commands without executing

    Returns:
        Tuple of (exit_code, created_new)
    """
    log = logging.getLogger("autorepro")

    # Get current branch if head not specified
    if head_branch is None:
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                check=True,
            )
            head_branch = result.stdout.strip()
        except subprocess.CalledProcessError as e:
            log.error(f"Failed to get current branch: {e}")
            return 1, False

    # Write body to temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(body)
        body_file = f.name

    try:
        # Check for existing draft PR if update requested
        existing_pr = None
        if update_if_exists:
            existing_pr = find_existing_draft(head_branch, gh_path)

        if existing_pr:
            # Update existing PR
            cmd = [
                gh_path,
                "pr",
                "edit",
                str(existing_pr),
                "--title",
                title,
                "--body-file",
                body_file,
            ]

            if dry_run:
                print(f"Would run: {' '.join(cmd)}")
                return 0, False

            log.info(f"Updating existing draft PR #{existing_pr}")
            subprocess.run(cmd, check=True)
            log.info(f"Updated PR #{existing_pr}")
            return 0, False

        else:
            # Create new PR
            cmd = [
                gh_path,
                "pr",
                "create",
                "--title",
                title,
                "--body-file",
                body_file,
                "--base",
                base_branch,
                "--head",
                head_branch,
            ]

            if draft:
                cmd.append("--draft")

            if labels:
                cmd.extend(["--label", ",".join(labels)])

            if assignees:
                cmd.extend(["--assignee", ",".join(assignees)])

            if reviewers:
                cmd.extend(["--reviewer", ",".join(reviewers)])

            if dry_run:
                print(f"Would run: {' '.join(cmd)}")
                return 0, True

            log.info("Creating new draft PR")
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            # Extract PR URL from output
            pr_url = result.stdout.strip()
            log.info(f"Created PR: {pr_url}")
            return 0, True

    except subprocess.CalledProcessError as e:
        log.error(f"GitHub CLI error: {e}")
        if hasattr(e, "stderr") and e.stderr:
            log.error(f"Error details: {e.stderr}")
        return 1, False

    finally:
        # Clean up temp file
        try:
            os.unlink(body_file)
        except OSError:
            pass


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

        return content_str, format_type

    finally:
        os.chdir(original_cwd)


# New PR Enrichment Functions for T-018


def get_pr_details(pr_number: int, gh_path: str = "gh") -> dict[str, Any]:
    """
    Get PR details including comments and body.

    Args:
        pr_number: PR number to get details for
        gh_path: Path to gh CLI tool

    Returns:
        PR data with comments and body

    Raises:
        RuntimeError: If gh command fails
    """
    try:
        result = subprocess.run(
            [
                gh_path,
                "pr",
                "view",
                str(pr_number),
                "--json",
                "comments,body,number,title",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        pr_data = json.loads(result.stdout)
        return pr_data

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to get PR details: {e}") from e
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON response from gh: {e}") from e


def create_pr_comment(
    pr_number: int,
    body: str,
    gh_path: str = "gh",
    dry_run: bool = False,
) -> int:
    """
    Create a new comment on a PR.

    Args:
        pr_number: PR number to comment on
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
            "pr",
            "comment",
            str(pr_number),
            "--body-file",
            body_file,
        ]

        if dry_run:
            print(f"Would run: {' '.join(cmd)}")
            return 0

        subprocess.run(cmd, check=True, capture_output=True)
        return 0

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to create PR comment: {e}") from e
    finally:
        # Clean up temp file
        try:
            os.unlink(body_file)
        except OSError:
            pass


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
        raise RuntimeError(f"Failed to update PR comment: {e}") from e
    finally:
        # Clean up temp file
        try:
            os.unlink(body_file)
        except OSError:
            pass


def update_pr_body(
    pr_number: int,
    body: str,
    gh_path: str = "gh",
    dry_run: bool = False,
) -> int:
    """
    Update PR body/description.

    Args:
        pr_number: PR number to update
        body: New PR body text
        gh_path: Path to gh CLI tool
        dry_run: If True, print command instead of executing

    Returns:
        Exit code (0 for success)

    Raises:
        RuntimeError: If PR body update fails
    """
    # Write body to temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(body)
        body_file = f.name

    try:
        cmd = [
            gh_path,
            "pr",
            "edit",
            str(pr_number),
            "--body-file",
            body_file,
        ]

        if dry_run:
            print(f"Would run: {' '.join(cmd)}")
            return 0

        subprocess.run(cmd, check=True, capture_output=True)
        return 0

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to update PR body: {e}") from e
    finally:
        # Clean up temp file
        try:
            os.unlink(body_file)
        except OSError:
            pass


def add_pr_labels(
    pr_number: int,
    labels: list[str],
    gh_path: str = "gh",
    dry_run: bool = False,
) -> int:
    """
    Add labels to a PR (idempotent).

    Args:
        pr_number: PR number to add labels to
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
        "pr",
        "edit",
        str(pr_number),
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
        raise RuntimeError(f"Failed to add PR labels: {e}") from e


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
