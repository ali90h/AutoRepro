#!/usr/bin/env python3
"""
AutoRepro core planning logic - pure functions for plan generation.
"""

from __future__ import annotations

import re

# Import from the rules module for now - this will be moved to core as well
from ..rules import get_rules

# Compiled regex patterns for keyword detection - conservative set matching original behavior
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
    "npm test": re.compile(r"\bnpm\s+test\b"),
    "yarn test": re.compile(r"\byarn\s+test\b"),
    "pnpm test": re.compile(r"\bpnpm\s+test\b"),
    # Go keywords
    "go test": re.compile(r"\bgo\s+test\b"),
    "gotestsum": re.compile(r"\bgotestsum\b"),
    # Electron keywords (multi-word phrases)
    "main process": re.compile(r"\bmain\s+process\b"),
    "white screen": re.compile(r"\bwhite\s+screen\b"),
    "electron": re.compile(r"\belectron\b"),
}


def normalize(text: str) -> str:
    """
    Normalize text by removing special characters and converting to lowercase.

    Args:
        text: Input text to normalize

    Returns:
        Normalized text with only alphanumeric characters, spaces, and common punctuation
    """
    if not text:
        return ""

    # Convert to lowercase
    text = text.lower()

    # Remove special characters but keep alphanumeric, spaces, hyphens, underscores, dots
    text = re.sub(r"[^\w\s.-]", " ", text)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


def _extract_regex_keywords(text: str) -> set[str]:
    """Extract keywords using regex patterns."""
    matched_keywords = set()
    for keyword_label, pattern in KEYWORD_PATTERNS.items():
        if pattern.search(text):
            matched_keywords.add(keyword_label)
    return matched_keywords


def _collect_plugin_keywords() -> set[str]:
    """Collect all keywords from plugin rules."""
    all_rules = get_rules()
    plugin_keywords = set()
    for ecosystem_rules in all_rules.values():
        for rule in ecosystem_rules:
            plugin_keywords.update(rule.keywords)
    return plugin_keywords


def _extract_plugin_keywords(text: str, plugin_keywords: set[str]) -> set[str]:
    """Extract plugin keywords from text using word boundary matching."""
    matched_keywords = set()
    text_words = text.lower().split()

    for keyword in plugin_keywords:
        # Handle multi-word keywords
        if " " in keyword:
            if keyword.lower() in text.lower():
                matched_keywords.add(keyword)
        else:
            if keyword.lower() in text_words:
                matched_keywords.add(keyword)

    return matched_keywords


def extract_keywords(text: str) -> set[str]:
    """
    Extract keywords from normalized text using regex patterns and plugin keywords.

    Args:
        text: Input text (should be normalized) to extract keywords from

    Returns:
        Set of matched keyword labels from KEYWORD_PATTERNS and plugin rules
    """
    if not text:
        return set()

    # Extract keywords using helper functions
    regex_keywords = _extract_regex_keywords(text)
    plugin_keywords = _collect_plugin_keywords()
    matched_plugin_keywords = _extract_plugin_keywords(text, plugin_keywords)

    return regex_keywords | matched_plugin_keywords


def safe_truncate_60(text: str) -> str:
    """
    Safely truncate text to 60 Unicode code points with ellipsis.

    Args:
        text: Input text to truncate

    Returns:
        Truncated text ending with ellipsis if longer than 60 characters
    """
    if not text:
        return text

    # Strip leading/trailing whitespace first
    text = text.strip()

    if len(text) <= 60:
        return text

    # Truncate to 60 Unicode code points and append ellipsis
    truncated = text[:60] + "…"

    return truncated


def _determine_ecosystems_to_include(keywords: set[str]) -> set[str]:
    """Determine which ecosystems to include based on keywords."""
    ecosystems_to_include = {"python", "node", "go", "electron"}

    # Add Rust if Rust keywords present
    rust_keywords = {"cargo test"}
    if rust_keywords.intersection(keywords):
        ecosystems_to_include.add("rust")

    # Add Java if Java keywords present
    java_keywords = {"mvn", "maven", "gradle", "gradlew"}
    if java_keywords.intersection(keywords):
        ecosystems_to_include.add("java")

    return ecosystems_to_include


def _collect_active_rules(
    ecosystems_to_include: set[str], all_rules: dict, builtin_rules: dict
) -> list[tuple]:
    """Collect active rules from included ecosystems with source tracking."""
    active_rules = []
    for ecosystem in ecosystems_to_include:
        if ecosystem in all_rules:
            for rule in all_rules[ecosystem]:
                # Check if rule is from plugin or builtin
                is_builtin = ecosystem in builtin_rules and rule in builtin_rules[ecosystem]
                source = "builtin" if is_builtin else "plugin"
                active_rules.append((rule, source))
    return active_rules


def _calculate_rule_score(
    rule, keywords: set[str], detected_langs: list[str], all_rules: dict
) -> dict:
    """Calculate score for a single rule."""
    ecosystem_mapping = {
        "python": "python",
        "javascript": "node",
        "node": "node",
        "go": "go",
        "electron": "electron",
        "rust": "rust",
        "java": "java",
    }

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
    if (matched_keywords or detected_ecosystems) and rule.weight > 0:
        score += 1
        bonuses_applied.append("specific (+1)")

    return {
        "score": score,
        "matched_keywords": sorted(matched_keywords),
        "detected_langs": detected_ecosystems,
        "bonuses": bonuses_applied,
    }


def _build_rationale(candidate: dict) -> str:
    """Build detailed rationale for a command candidate."""
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

    return "; ".join(rationale_parts) if rationale_parts else "no matches"


def _sort_candidates(candidates: list[dict]) -> list[dict]:
    """Sort candidates with enhanced tie-breaking."""
    candidates.sort(
        key=lambda c: (
            -c["score"],  # Higher score first
            -len(c["matched_keywords"]),  # Most matching words first
            0 if c["source"] == "plugin" else 1,  # Plugin precedes built-in when tied
            c["cmd"],  # Alphabetical order for final tie-breaking
        )
    )
    return candidates


def suggest_commands(
    keywords: set[str], detected_langs: list[str], min_score: int = 2
) -> list[tuple[str, int, str]]:
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
    # Get all rules from registry (built-in + plugins)
    from ..rules import BUILTIN_RULES

    all_rules = get_rules()

    # Use helper functions to break down the complexity
    ecosystems_to_include = _determine_ecosystems_to_include(keywords)
    active_rules = _collect_active_rules(ecosystems_to_include, all_rules, BUILTIN_RULES)

    # Calculate scores for each rule
    command_candidates = []
    for rule, source in active_rules:
        score_data = _calculate_rule_score(rule, keywords, detected_langs, all_rules)

        # Store command candidate with source info
        candidate = {"cmd": rule.cmd, "source": source, **score_data}
        command_candidates.append(candidate)

    # Filter candidates by min_score
    relevant_candidates = [c for c in command_candidates if c["score"] >= min_score]

    # Sort candidates using helper function
    relevant_candidates = _sort_candidates(relevant_candidates)

    # Build final suggestions with detailed rationales
    return [
        (candidate["cmd"], candidate["score"], _build_rationale(candidate))
        for candidate in relevant_candidates
    ]
