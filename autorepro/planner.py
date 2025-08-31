"""AutoRepro planner module for generating reproduction plans from issue descriptions."""

import re
from typing import TypedDict

from .rules import get_rules


class CommandCandidate(TypedDict):
    """Type for command candidate with scoring metadata."""

    cmd: str
    score: int
    matched_keywords: list[str]
    detected_langs: list[str]
    bonuses: list[str]
    source: str


# Compiled regex patterns for keyword detection
KEYWORD_PATTERNS = {
    # Python keywords
    "pytest": re.compile(r"\bpytest\b"),
    "tox": re.compile(r"\btox\b"),
    "unittest": re.compile(r"\bunittest\b"),
    "poetry": re.compile(r"\bpoetry\b"),
    "pipenv": re.compile(r"\bpipenv\b"),
    # Node keywords (including multi-word phrases)
    "jest": re.compile(r"\bjest\b"),
    "vitest": re.compile(r"\bvitest\b"),
    "mocha": re.compile(r"\bmocha\b"),
    "playwright": re.compile(r"\bplaywright\b"),
    "cypress": re.compile(r"\bcypress\b"),
    "npm test": re.compile(r"\bnpm\s+test\b"),
    "pnpm test": re.compile(r"\bpnpm\s+test\b"),
    "yarn test": re.compile(r"\byarn\s+test\b"),
    # Go keywords
    "go test": re.compile(r"\bgo\s+test\b"),
    "gotestsum": re.compile(r"\bgotestsum\b"),
    # Electron keywords (including multi-word phrases)
    "electron": re.compile(r"\belectron\b"),
    "main process": re.compile(r"\bmain\s+process\b"),
    "renderer": re.compile(r"\brenderer\b"),
    "white screen": re.compile(r"\bwhite\s+screen\b"),
    # Future-prep: Rust keywords
    "cargo test": re.compile(r"\bcargo\s+test\b"),
    # Future-prep: Java keywords (looking for build tool indicators)
    "mvn": re.compile(r"\bmvn\b"),
    "maven": re.compile(r"\bmaven\b"),
    "gradle": re.compile(r"\bgradle\b"),
    "gradlew": re.compile(r"\bgradlew\b"),
}


def normalize(text: str) -> str:
    """
    Normalize text by lowercasing and removing light punctuation noise.

    Args:
        text: Raw input text to normalize

    Returns:
        Normalized text with consistent whitespace and minimal punctuation
    """
    if not text:
        return ""

    # Convert to lowercase
    text = text.lower()

    # Remove markdown noise and light punctuation
    # Remove: # * ` ~ " ' < > [ ] ( ) { }
    noise_chars = r'[#*`~"\'<>]'
    text = re.sub(noise_chars, " ", text)

    # Strip leading/trailing whitespace and collapse internal whitespace
    text = re.sub(r"\s+", " ", text.strip())

    return text


def extract_keywords(text: str) -> set[str]:
    """
    Extract keywords from normalized text using regex patterns.

    Args:
        text: Input text (should be normalized) to extract keywords from

    Returns:
        Set of matched keyword labels exactly as defined in KEYWORD_PATTERNS
    """
    if not text:
        return set()

    # Apply regex patterns to find matching keywords
    matched_keywords = set()
    for keyword_label, pattern in KEYWORD_PATTERNS.items():
        if pattern.search(text):
            matched_keywords.add(keyword_label)

    return matched_keywords


def suggest_commands(
    keywords: set[str], detected_langs: list[str], min_score: int = 2
) -> list[tuple[str, int, str]]:  # type: ignore
    """
    Suggest commands based on keywords and detected languages using precise scoring rules.

    Scoring Rules:
    - +3 for direct tool/framework match (keyword present for a command)
    - +2 if language is detected for the same ecosystem
    - +1 for more specific/stable spellings of a command
    - Tie-breaker: alphabetical sorting by command string

    Args:
        keywords: Set of extracted keywords from regex-based extraction
        detected_langs: List of detected languages from detect_languages()

    Returns:
        List of (command, score, rationale) tuples sorted by (-score, command)
    """
    # Map detected languages to ecosystems
    ecosystem_mapping = {
        "python": "python",
        "javascript": "node",
        "node": "node",
        "go": "go",
        "electron": "electron",
        "rust": "rust",
        "java": "java",
    }

    # Get all rules from registry (built-in + plugins)
    from .rules import BUILTIN_RULES

    all_rules = get_rules()

    # Determine which ecosystems to include (MVP + conditional)
    ecosystems_to_include = {"python", "node", "go", "electron"}

    # Add Rust if Rust keywords present
    rust_keywords = {"cargo test"}
    if rust_keywords.intersection(keywords):
        ecosystems_to_include.add("rust")

    # Add Java if Java keywords present
    java_keywords = {"mvn", "maven", "gradle", "gradlew"}
    if java_keywords.intersection(keywords):
        ecosystems_to_include.add("java")

    # Collect active rules from included ecosystems with source tracking
    active_rules = []
    for ecosystem in ecosystems_to_include:
        if ecosystem in all_rules:
            for rule in all_rules[ecosystem]:
                # Check if rule is from plugin or builtin
                is_builtin = ecosystem in BUILTIN_RULES and rule in BUILTIN_RULES[ecosystem]
                source = "builtin" if is_builtin else "plugin"
                active_rules.append((rule, source))

    # Calculate scores for each rule
    command_candidates: list[CommandCandidate] = []

    for rule, source in active_rules:
        score = 0
        matched_keywords = []
        detected_ecosystems = []
        bonuses_applied = []

        # +3 for direct tool/framework match
        for keyword in rule.keywords:
            if keyword in keywords:
                score += 3
                matched_keywords.append(keyword)
                bonuses_applied.append(f"direct: {keyword} (+3)")

        # +2 if language is detected for the same ecosystem
        for lang in detected_langs:
            lang_key = lang.lower()
            if lang_key in ecosystem_mapping:
                ecosystem = ecosystem_mapping[lang_key]
                # Find which ecosystem this rule belongs to by checking all_rules
                for eco, rules in all_rules.items():
                    if rule in rules and eco == ecosystem:
                        score += 2
                        detected_ecosystems.append(lang)
                        bonuses_applied.append(f"lang: {lang} (+2)")
                        break

        # Only apply bonuses if there are matches
        if matched_keywords or detected_ecosystems:
            # +1 for more specific/stable spellings (weight > 0)
            if rule.weight > 0:
                score += 1
                bonuses_applied.append("specific (+1)")

        # Store command candidate
        command_candidates.append(
            {
                "cmd": rule.cmd,
                "score": score,
                "matched_keywords": sorted(matched_keywords),
                "detected_langs": detected_ecosystems,
                "bonuses": bonuses_applied,
                "source": source,
            }
        )

    # Filter candidates by min_score
    relevant_candidates = [c for c in command_candidates if c["score"] >= min_score]

    # Sort with plugin priority and enhanced tie-breaking
    relevant_candidates.sort(
        key=lambda c: (
            -c["score"],  # Higher score first
            0 if c["source"] == "plugin" else 1,  # Plugin first in case of tie
            -len(c["matched_keywords"]),  # More matching keywords first
            c["cmd"],  # Alphabetical order for final tie-breaking
        )
    )

    # Build final suggestions with detailed rationales
    suggestions = []
    for candidate in relevant_candidates:
        # Build detailed rationale
        rationale_parts = []
        if candidate["matched_keywords"]:
            kw_list = ", ".join(candidate["matched_keywords"])
            rationale_parts.append(f"matched keywords: {kw_list}")
        if candidate["detected_langs"]:
            lang_list = ", ".join(candidate["detected_langs"])
            rationale_parts.append(f"detected langs: {lang_list}")
        if candidate["bonuses"]:
            bonus_list = ", ".join(candidate["bonuses"])
            rationale_parts.append(f"bonuses: {bonus_list}")

        rationale = "; ".join(rationale_parts) if rationale_parts else "no matches"
        suggestions.append((candidate["cmd"], candidate["score"], rationale))

    return suggestions


def safe_truncate_60(text: str) -> str:
    """
    Safely truncate text to 60 Unicode code points, appending … if truncated.

    Args:
        text: Input text to truncate

    Returns:
        Text truncated to ≤60 Unicode code points with trailing whitespace trimmed.
        Appends … if truncation occurred.
    """
    if not text:
        return ""

    # Trim trailing whitespace first
    text = text.rstrip()

    # If text is 60 chars or less, return as-is
    if len(text) <= 60:
        return text

    # Truncate to 60 Unicode code points and append ellipsis
    truncated = text[:60] + "…"

    return truncated


def build_repro_json(
    title: str,
    assumptions: list[str],
    commands: list[tuple[str, int, str]],  # (cmd, score, rationale)
    needs: list[str],
    next_steps: list[str],
) -> dict:
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
    # Parse devcontainer status from needs list
    devcontainer_present = False
    for need in needs:
        if "devcontainer" in need.lower() and "present" in need.lower():
            devcontainer_present = True
            break

    # Process commands to extract matched keywords and languages
    processed_commands = []
    for cmd, score, rationale in commands:
        # Parse rationale conservatively
        matched_keywords = []
        matched_langs = []

        # Extract matched keywords (tokens following "matched keywords:" up to next semicolon)
        if "matched keywords:" in rationale:
            parts = rationale.split("matched keywords:")
            if len(parts) > 1:
                # Get text after "matched keywords:" - handle multiple possibilities
                rest_of_text = parts[1]

                # Find the end of the matched section (before next semicolon)
                # Look for patterns like "; detected langs:" or ";" to determine end
                end_markers = ["; detected langs:", "; bonuses:", ";"]
                matched_section = rest_of_text
                for marker in end_markers:
                    if marker in matched_section:
                        matched_section = matched_section.split(marker)[0]
                        break

                # Split by commas first to handle multiple keywords
                keyword_parts = matched_section.split(",")
                for part in keyword_parts:
                    # Clean each part and extract words
                    part = part.strip()
                    if part:
                        # Split by spaces to handle multi-word keywords like "npm test"
                        tokens = part.split()
                        # Keep simple word characters, dashes, underscores, spaces for multi-word
                        for token in tokens:
                            clean_token = "".join(c for c in token if c.isalnum() or c in "-_")
                            if clean_token and not clean_token.isdigit():  # Skip pure numbers
                                matched_keywords.append(clean_token)

        # Extract matched languages (tokens following "detected langs:" up to next semicolon)
        if "detected langs:" in rationale:
            parts = rationale.split("detected langs:")
            if len(parts) > 1:
                # Get text after "detected langs:" - handle multiple possibilities
                rest_of_text = parts[1]

                # Find the end of the lang section (before next semicolon)
                end_markers = ["; bonuses:", ";"]
                lang_section = rest_of_text
                for marker in end_markers:
                    if marker in lang_section:
                        lang_section = lang_section.split(marker)[0]
                        break

                # Split by commas first to handle multiple languages
                lang_parts = lang_section.split(",")
                for part in lang_parts:
                    # Clean each part and extract words
                    part = part.strip()
                    if part:
                        # Split by spaces to handle multi-word if needed
                        tokens = part.split()
                        for token in tokens:
                            clean_token = "".join(c for c in token if c.isalnum() or c in "-_")
                            if clean_token and not clean_token.isdigit():  # Skip pure numbers
                                matched_langs.append(clean_token)

        processed_commands.append(
            {
                "cmd": cmd,
                "score": score,
                "rationale": rationale,
                "matched_keywords": matched_keywords,
                "matched_langs": matched_langs,
            }
        )

    # Build JSON object with fixed key order (preserve insertion order)
    # Note: schema fields removed to maintain backward compatibility with golden tests
    return {
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
