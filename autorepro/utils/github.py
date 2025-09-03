#!/usr/bin/env python3
"""
Common GitHub API utilities.
"""

from __future__ import annotations

import os
import subprocess
import tempfile


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

        subprocess.run(cmd, check=True, capture_output=True)
        return 0

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to update {context} comment: {e}") from e
    finally:
        # Clean up temp file
        try:
            os.unlink(body_file)
        except OSError:
            pass
