#!/usr/bin/env python3
"""
AutoRepro I/O layer - GitHub API and git operations.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tempfile
from typing import Any

# Import shared GitHub utilities


def detect_repo_slug() -> str:
    """
    Detect repository owner/name from git remote origin.

    Returns:
        Repository slug in format "owner/repo"

    Raises:
        RuntimeError: If unable to determine repository slug
    """
    try:
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            check=True,
        )
        remote_url = result.stdout.strip()

        # SSH: git@github.com:owner/repo.git
        # HTTPS: https://github.com/owner/repo.git
        ssh_match = re.search(r"git@github\.com:([^/]+)/([^/]+)(?:\.git)?$", remote_url)
        if ssh_match:
            return f"{ssh_match.group(1)}/{ssh_match.group(2)}"

        https_match = re.search(r"https://github\.com/([^/]+)/([^/]+)(?:\.git)?/?$", remote_url)
        if https_match:
            return f"{https_match.group(1)}/{https_match.group(2)}"

        raise RuntimeError(f"Unable to parse GitHub repository from remote URL: {remote_url}")

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to get git remote origin URL: {e}") from e


def ensure_pushed(head_branch: str) -> bool:
    """
    Ensure the head branch is pushed to remote origin.

    Args:
        head_branch: Branch name to push

    Returns:
        True if push was successful or branch was already up to date

    Raises:
        RuntimeError: If push fails
    """
    try:
        # Check if branch exists on remote
        result = subprocess.run(
            ["git", "ls-remote", "--heads", "origin", head_branch],
            capture_output=True,
            text=True,
            check=True,
        )

        if not result.stdout.strip():
            # Branch doesn't exist on remote, push it
            result = subprocess.run(
                ["git", "push", "-u", "origin", head_branch],
                capture_output=True,
                text=True,
                check=True,
            )
        else:
            # Branch exists, push any new commits
            subprocess.run(
                ["git", "push", "origin", head_branch],
                capture_output=True,
                text=True,
                check=True,
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
                "--head",
                head_branch,
                "--state",
                "open",
                "--draft",
                "--json",
                "number",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        prs = json.loads(result.stdout)
        if prs:
            return prs[0]["number"]
        return None

    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None


def get_pr_details(pr_number: int, gh_path: str = "gh") -> dict[str, Any]:
    """
    Get PR details including comments and body.

    Args:
        pr_number: PR number to get details for
        gh_path: Path to gh CLI tool

    Returns:
        Dictionary containing PR details

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
                "title,body,number,headRefName,baseRefName,state,isDraft",
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
        # Include the raw output for debugging
        raw_output = result.stdout[:200] + "..." if len(result.stdout) > 200 else result.stdout
        raise RuntimeError(f"Invalid JSON response from gh: {e}. Raw output: {raw_output!r}") from e


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
    Add labels to a PR.

    Args:
        pr_number: PR number to add labels to
        labels: List of label names to add
        gh_path: Path to gh CLI tool
        dry_run: If True, print command instead of executing

    Returns:
        Exit code (0 for success)

    Raises:
        RuntimeError: If adding labels fails
    """
    if not labels:
        return 0

    try:
        cmd = [gh_path, "pr", "edit", str(pr_number), "--add-label", ",".join(labels)]

        if dry_run:
            print(f"Would run: {' '.join(cmd)}")
            return 0

        subprocess.run(cmd, check=True, capture_output=True)

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to add PR labels: {e}") from e

    return 0


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


class IssueNotFoundError(Exception):
    """Raised when specified issue number doesn't exist."""


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
