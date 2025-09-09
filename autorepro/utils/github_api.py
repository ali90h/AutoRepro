#!/usr/bin/env python3
"""
Common GitHub API utilities.
"""

from __future__ import annotations

import contextlib
import os
import tempfile

from .error_handling import SubprocessError
from .error_handling import safe_subprocess_run_simple as safe_subprocess_run


def update_comment(
    comment_id: int,
    body: str,
    gh_path: str = "gh",
    dry_run: bool = False,
    context: str = "comment",
) -> int:
    """
    Update an existing GitHub comment (issue or PR).

    Args:
        comment_id: Comment ID to update
        body: New comment body text
        gh_path: Path to gh CLI tool
        dry_run: If True, print command instead of executing
        context: Context for error messages ("issue" or "PR")

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

        safe_subprocess_run(
            cmd,
            capture_output=True,
            check=True,
            operation="update GitHub comment"
        )
        return 0

    except SubprocessError as e:
        raise RuntimeError(f"Failed to update {context} comment: {e.message}") from e
    finally:
        # Clean up temp file
        with contextlib.suppress(OSError):
            os.unlink(body_file)
