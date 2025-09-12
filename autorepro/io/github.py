#!/usr/bin/env python3
"""
AutoRepro I/O layer - GitHub API and git operations.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Any

from autorepro.config.exceptions import FieldValidationError

# Import shared GitHub utilities


@dataclass
class GitHubPRConfig:
    """Configuration for GitHub PR creation/update operations."""

    title: str
    body: str
    base_branch: str = "main"
    head_branch: str | None = None
    draft: bool = True
    labels: list[str] | None = None
    assignees: list[str] | None = None
    reviewers: list[str] | None = None
    update_if_exists: bool = False
    gh_path: str = "gh"
    dry_run: bool = False

    def validate(self) -> None:
        """Validate GitHub PR configuration and raise descriptive errors."""
        # Field validation
        if not self.title.strip():
            raise FieldValidationError(
                "title cannot be empty or whitespace-only", field="title"
            )

        if not self.base_branch.strip():
            raise FieldValidationError(
                "base_branch cannot be empty or whitespace-only", field="base_branch"
            )

        # Branch name validation (basic git ref validation)
        invalid_chars = [" ", "~", "^", ":", "?", "*", "[", "\\"]
        for char in invalid_chars:
            if char in self.base_branch:
                raise FieldValidationError(
                    f"base_branch contains invalid character '{char}': {self.base_branch}",
                    field="base_branch",
                )

        if self.head_branch is not None:
            if not self.head_branch.strip():
                raise FieldValidationError(
                    "head_branch cannot be empty or whitespace-only",
                    field="head_branch",
                )

            for char in invalid_chars:
                if char in self.head_branch:
                    raise FieldValidationError(
                        f"head_branch contains invalid character '{char}': {self.head_branch}",
                        field="head_branch",
                    )


@dataclass
class IssueConfig:
    """Configuration for GitHub issue creation operations."""

    title: str
    body: str = ""
    labels: list[str] | None = None
    assignees: list[str] | None = None
    gh_path: str = "gh"
    dry_run: bool = False

    def validate(self) -> None:
        """Validate GitHub issue configuration and raise descriptive errors."""
        # Field validation
        if not self.title.strip():
            raise FieldValidationError(
                "title cannot be empty or whitespace-only", field="title"
            )


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

        https_match = re.search(
            r"https://github\.com/([^/]+)/([^/]+)(?:\.git)?/?$", remote_url
        )
        if https_match:
            return f"{https_match.group(1)}/{https_match.group(2)}"

        raise RuntimeError(
            f"Unable to parse GitHub repository from remote URL: {remote_url}"
        )

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

        return json.loads(result.stdout)

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to get PR details: {e}") from e
    except json.JSONDecodeError as e:
        # Include the raw output for debugging
        raw_output = (
            result.stdout[:200] + "..." if len(result.stdout) > 200 else result.stdout
        )
        raise RuntimeError(
            f"Invalid JSON response from gh: {e}. Raw output: {raw_output!r}"
        ) from e


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
            logging.getLogger("autorepro.github").info(
                "Would run",
                extra={"cmd": cmd, "dry_run": True, "op": "create_pr_comment"},
            )
            return 0

        subprocess.run(cmd, check=True, capture_output=True)
        return 0

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to create PR comment: {e}") from e
    finally:
        # Clean up temp file
        with contextlib.suppress(OSError):
            os.unlink(body_file)


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
            logging.getLogger("autorepro.github").info(
                "Would run",
                extra={"cmd": cmd, "dry_run": True, "op": "update_pr_body"},
            )
            return 0

        subprocess.run(cmd, check=True, capture_output=True)
        return 0

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to update PR body: {e}") from e
    finally:
        # Clean up temp file
        with contextlib.suppress(OSError):
            os.unlink(body_file)


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
            logging.getLogger("autorepro.github").info(
                "Would run",
                extra={"cmd": cmd, "dry_run": True, "op": "add_pr_labels"},
            )
            return 0

        subprocess.run(cmd, check=True, capture_output=True)

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to add PR labels: {e}") from e

    return 0


def _get_current_branch_if_needed(config: GitHubPRConfig) -> tuple[int, bool] | None:
    """
    Get current branch if head_branch not specified.

    Returns:
        None if successful, or (exit_code, created_new) tuple if error occurred
    """
    if config.head_branch is None:
        log = logging.getLogger("autorepro")
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                check=True,
            )
            config.head_branch = result.stdout.strip()
        except subprocess.CalledProcessError as e:
            log.error(f"Failed to get current branch: {e}")
            return 1, False
    return None


def _create_temp_body_file(body: str) -> str:
    """
    Create temporary file with PR body content.

    Returns:
        Path to the temporary file
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(body)
        return f.name


def _update_existing_pr(
    config: GitHubPRConfig, existing_pr: int, body_file: str
) -> tuple[int, bool]:
    """
    Update an existing PR.

    Returns:
        Tuple of (exit_code, created_new)
    """
    log = logging.getLogger("autorepro")
    cmd = [
        config.gh_path,
        "pr",
        "edit",
        str(existing_pr),
        "--title",
        config.title,
        "--body-file",
        body_file,
    ]

    if config.dry_run:
        logging.getLogger("autorepro.github").info(
            "Would run",
            extra={"cmd": cmd, "dry_run": True, "op": "_update_existing_pr"},
        )
        return 0, False

    log.info(f"Updating existing draft PR #{existing_pr}")
    subprocess.run(cmd, check=True)
    log.info(f"Updated PR #{existing_pr}")
    return 0, False


def _build_create_pr_command(config: GitHubPRConfig, body_file: str) -> list[str]:
    """
    Build command for creating new PR.

    Returns:
        List of command arguments
    """
    cmd = [
        config.gh_path,
        "pr",
        "create",
        "--title",
        config.title,
        "--body-file",
        body_file,
        "--base",
        config.base_branch or "main",
        "--head",
        config.head_branch or "HEAD",
    ]

    if config.draft:
        cmd.append("--draft")

    if config.labels:
        labels_filtered = [label for label in config.labels if label is not None]
        if labels_filtered:
            cmd.extend(["--label", ",".join(labels_filtered)])

    if config.assignees:
        assignees_filtered = [
            assignee for assignee in config.assignees if assignee is not None
        ]
        if assignees_filtered:
            cmd.extend(["--assignee", ",".join(assignees_filtered)])

    if config.reviewers:
        reviewers_filtered = [
            reviewer for reviewer in config.reviewers if reviewer is not None
        ]
        if reviewers_filtered:
            cmd.extend(["--reviewer", ",".join(reviewers_filtered)])

    return cmd


def _create_new_pr(config: GitHubPRConfig, body_file: str) -> tuple[int, bool]:
    """
    Create a new PR.

    Returns:
        Tuple of (exit_code, created_new)
    """
    log = logging.getLogger("autorepro")
    cmd = _build_create_pr_command(config, body_file)

    if config.dry_run:
        logging.getLogger("autorepro.github").info(
            "Would run",
            extra={"cmd": cmd, "dry_run": True, "op": "_create_new_pr"},
        )
        return 0, True

    log.info("Creating new draft PR")
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)

    # Extract PR URL from output
    pr_url = result.stdout.strip()
    log.info(f"Created PR: {pr_url}")
    return 0, True


def create_or_update_pr(
    config: GitHubPRConfig,
) -> tuple[int, bool]:  # (exit_code, created_new)
    """
    Create or update a GitHub PR.

    Args:
        config: GitHub PR configuration object

    Returns:
        Tuple of (exit_code, created_new)
    """
    log = logging.getLogger("autorepro")

    # Validate configuration
    config.validate()

    # Get current branch if head not specified
    branch_error = _get_current_branch_if_needed(config)
    if branch_error is not None:
        return branch_error

    # Write body to temporary file
    body_file = _create_temp_body_file(config.body)

    try:
        # Check for existing draft PR if update requested
        existing_pr = None
        if config.update_if_exists and config.head_branch:
            existing_pr = find_existing_draft(config.head_branch, config.gh_path)

        if existing_pr:
            return _update_existing_pr(config, existing_pr, body_file)
        else:
            return _create_new_pr(config, body_file)

    except subprocess.CalledProcessError as e:
        log.error(f"GitHub CLI error: {e}")
        if hasattr(e, "stderr") and e.stderr:
            log.error(f"Error details: {e.stderr}")
        return 1, False

    finally:
        # Clean up temp file
        with contextlib.suppress(OSError):
            os.unlink(body_file)


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
            logging.getLogger("autorepro.github").info(
                "Would run",
                extra={"cmd": cmd, "dry_run": True, "op": "create_issue_comment"},
            )
            return 0

        subprocess.run(cmd, check=True, capture_output=True)
        return 0

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to create issue comment: {e}") from e
    finally:
        # Clean up temp file
        with contextlib.suppress(OSError):
            os.unlink(body_file)


def create_issue(config: IssueConfig) -> int:
    """
    Create a new issue.

    Args:
        config: Issue configuration

    Returns:
        Issue number if successful

    Raises:
        RuntimeError: If issue creation fails
    """
    # Validate configuration
    config.validate()

    # Write body to temporary file if not empty
    body_file = None
    if config.body:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(config.body)
            body_file = f.name

    try:
        cmd = [config.gh_path, "issue", "create", "--title", config.title]

        if body_file:
            cmd.extend(["--body-file", body_file])
        else:
            cmd.extend(["--body", ""])

        if config.labels:
            cmd.extend(["--label", ",".join(config.labels)])

        if config.assignees:
            cmd.extend(["--assignee", ",".join(config.assignees)])

        if config.dry_run:
            logging.getLogger("autorepro.github").info(
                "Would run",
                extra={"cmd": cmd, "dry_run": True, "op": "create_issue"},
            )
            return 0

        result = subprocess.run(cmd, check=True, capture_output=True, text=True)

        # Extract issue number from URL output
        return int(result.stdout.strip().split("/")[-1])

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to create issue: {e}") from e
    except (ValueError, IndexError) as e:
        raise RuntimeError(
            f"Could not parse issue number from response: {result.stdout}"
        ) from e
    finally:
        # Clean up temp file
        if body_file:
            with contextlib.suppress(OSError):
                os.unlink(body_file)


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
        logging.getLogger("autorepro.github").info(
            "Would run",
            extra={"cmd": cmd, "dry_run": True, "op": "add_issue_labels"},
        )
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
        logging.getLogger("autorepro.github").info(
            "Would run",
            extra={"cmd": cmd, "dry_run": True, "op": "add_issue_assignees"},
        )
        return 0

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return 0
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to add assignees: {e}") from e
