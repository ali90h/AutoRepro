#!/usr/bin/env python3
"""
AutoRepro rendering layer - string and JSON formatting functions.
"""

from __future__ import annotations

from typing import Any

from .. import __version__


def _parse_devcontainer_status(needs: list[str]) -> bool:
    """Check if devcontainer is present in needs list."""
    return any("devcontainer" in need.lower() and "present" in need.lower() for need in needs)


def _extract_section_from_rationale(
    rationale: str, start_marker: str, end_markers: list[str]
) -> str:
    """Extract a section from rationale text between markers."""
    if start_marker not in rationale:
        return ""

    parts = rationale.split(start_marker)
    if len(parts) <= 1:
        return ""

    rest_of_text = parts[1]
    section = rest_of_text

    for marker in end_markers:
        if marker in section:
            section = section.split(marker)[0]
            break

    return section.strip()


def _extract_tokens_from_text(text: str) -> list[str]:
    """Extract clean tokens from text, splitting on commas and spaces."""
    tokens: list[str] = []
    if not text:
        return tokens

    # Split by commas first
    parts = text.split(",")
    for part in parts:
        part = part.strip()
        if part:
            # Split by spaces for multi-word tokens
            words = part.split()
            for word in words:
                clean_token = "".join(c for c in word if c.isalnum() or c in "-_")
                if clean_token and not clean_token.isdigit():
                    tokens.append(clean_token)

    return tokens


def _extract_matched_keywords(rationale: str) -> list[str]:
    """Extract matched keywords from rationale text."""
    section = _extract_section_from_rationale(
        rationale, "matched keywords:", ["; detected langs:", "; bonuses:", ";"]
    )
    return _extract_tokens_from_text(section)


def _extract_matched_languages(rationale: str) -> list[str]:
    """Extract matched languages from rationale text."""
    section = _extract_section_from_rationale(rationale, "detected langs:", ["; bonuses:", ";"])
    return _extract_tokens_from_text(section)


def _process_commands(commands: list[tuple[str, int, str]]) -> list[dict[str, Any]]:
    """Process commands to extract matched keywords and languages."""
    return [
        {
            "cmd": cmd,
            "score": score,
            "rationale": rationale,
            "matched_keywords": _extract_matched_keywords(rationale),
            "matched_langs": _extract_matched_languages(rationale),
        }
        for cmd, score, rationale in commands
    ]


def build_repro_json(
    title: str,
    assumptions: list[str],
    commands: list[tuple[str, int, str]],  # (cmd, score, rationale)
    needs: list[str],
    next_steps: list[str],
) -> dict[str, Any]:
    """
    Build a reproduction JSON object with standardized structure.

    Args:
        title: Title for the reproduction document
        assumptions: List of assumptions made
        commands: List of (command, score, rationale) tuples
        needs: List of environment/dependency needs (includes devcontainer status)
        next_steps: List of next steps to take

    Returns:
        JSON object with fixed key order containing title, assumptions, needs,
        commands, and next_steps. Commands include parsed matched_keywords and
        matched_langs from rationales.
    """
    # Parse devcontainer status and process commands using helper functions
    devcontainer_present = _parse_devcontainer_status(needs)
    processed_commands = _process_commands(commands)

    # Build JSON object with fixed key order (preserve insertion order)
    return {
        "schema_version": 1,
        "tool": "autorepro",
        "tool_version": __version__,
        "title": title,
        "assumptions": assumptions,
        "needs": {"devcontainer_present": devcontainer_present},
        "commands": processed_commands,
        "next_steps": next_steps,
    }


def build_repro_md(
    title: str,
    assumptions: list[str],
    commands: list[tuple[str, int, str]],
    needs: list[str],
    next_steps: list[str],
) -> str:
    """
    Build a reproduction markdown document with standardized structure.

    Args:
        title: Title for the reproduction document (will be safely truncated to 60 chars)
        assumptions: List of assumptions made (defaults provided if empty)
        commands: List of (command, score, rationale) tuples (sorted by score desc, alphabetical)
        needs: List of environment/dependency needs (includes devcontainer status)
        next_steps: List of next steps to take (defaults provided if empty)

    Returns:
        Formatted markdown string with canonical sections
    """
    # Import safe_truncate_60 from core layer
    from ..core.planning import safe_truncate_60

    lines = []

    # Title - safely truncated to 60 characters
    safe_title = safe_truncate_60(title)
    lines.append(f"# {safe_title}")
    lines.append("")

    # Assumptions section - with defaults if empty
    lines.append("## Assumptions")
    lines.append("")
    if assumptions:
        for assumption in assumptions:
            lines.append(f"- {assumption}")
    else:
        # Default assumptions when none provided
        lines.append("- OS: Linux (CI runner) — editable")
        lines.append("- Python 3.11 / Node 20 unless otherwise stated")
        lines.append(
            "- Network available for package mirrors; real network tests may be isolated later"
        )
    lines.append("")

    # Candidate Commands section - one line per command
    lines.append("## Candidate Commands")
    lines.append("")
    if commands:
        # Sort by score desc, then alphabetically by command for deterministic output
        sorted_commands = sorted(commands, key=lambda x: (-x[1], x[0]))
        for cmd, _, rationale in sorted_commands:
            lines.append(f"- `{cmd}` — {rationale}")
    else:
        lines.append("No commands suggested")
    lines.append("")

    # Needed Files/Env section - including devcontainer status
    lines.append("## Needed Files/Env")
    lines.append("")
    if needs:
        for need in needs:
            lines.append(f"- {need}")
    else:
        lines.append("- Standard development environment")
    lines.append("")

    # Next Steps section - with canonical defaults if empty
    lines.append("## Next Steps")
    lines.append("")
    if next_steps:
        for step in next_steps:
            lines.append(f"- {step}")
    else:
        # Default next steps when none provided
        lines.append("- Run the highest-score command")
        lines.append("- If it fails: switch to the second")
        lines.append("- Record brief logs in report.md")
    lines.append("")

    return "\n".join(lines)
