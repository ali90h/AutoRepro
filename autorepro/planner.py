"""AutoRepro planner module for generating reproduction plans from issue descriptions."""

import re
from typing import Any


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
    noise_chars = r'[#*`~"\'<>\[\](){}]'
    text = re.sub(noise_chars, " ", text)

    # Strip leading/trailing whitespace and collapse internal whitespace
    text = re.sub(r"\s+", " ", text.strip())

    return text


def extract_keywords(text: str) -> set[str]:
    """
    Extract keywords from normalized text using light heuristics.

    Args:
        text: Input text to extract keywords from

    Returns:
        Set of relevant keywords, filtered for stopwords and length
    """
    if not text:
        return set()

    # Basic English stopwords
    stopwords = {
        "the",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "can",
        "may",
        "this",
        "that",
        "these",
        "those",
        "i",
        "you",
        "he",
        "she",
        "it",
        "we",
        "they",
        "me",
        "him",
        "her",
        "us",
        "them",
        "my",
        "your",
        "his",
        "its",
        "our",
        "their",
        "a",
        "an",
        "as",
        "if",
        "so",
        "no",
        "not",
        "all",
        "any",
        "some",
        "from",
        "up",
        "out",
        "down",
        "off",
        "over",
        "under",
    }

    # Developer-shorthand terms to preserve
    dev_terms = {
        "pytest",
        "tox",
        "jest",
        "vitest",
        "playwright",
        "npm",
        "yarn",
        "pnpm",
        "go",
        "gotest",
        "make",
        "electron",
        "node",
        "python",
        "pyproject",
        "requirements",
        "package",
        "json",
        "test",
        "tests",
        "testing",
        "ci",
        "cd",
        "build",
        "run",
        "install",
        "setup",
        "config",
        "lint",
        "format",
    }

    # Tokenize on non-alphanumeric characters
    tokens = re.findall(r"\b[a-z0-9]+\b", text.lower())

    # Filter tokens: keep if length >= 2 and not a stopword, or if it's a dev term
    keywords = set()
    for token in tokens:
        if len(token) >= 2 and (token not in stopwords or token in dev_terms):
            keywords.add(token)

    return keywords


def suggest_commands(keywords: set[str], detected_langs: list[str]) -> list[tuple[str, int, str]]:
    """
    Suggest commands based on keywords and detected languages.

    Args:
        keywords: Set of extracted keywords
        detected_langs: List of detected languages from detect_languages()

    Returns:
        List of (command, score, rationale) tuples sorted by descending score
    """
    suggestions = []

    # Language-specific command mappings with base scores
    lang_commands = {
        "python": [
            ("pytest -q", 20, "Python testing with pytest"),
            ("python -m pytest -q", 18, "Python testing via module"),
            ("tox -q", 15, "Python multi-environment testing"),
        ],
        "node": [
            ("npm test -s", 20, "Node.js npm test runner"),
            ("npx jest --silent", 18, "Jest testing framework"),
            ("npx vitest run", 15, "Vitest testing framework"),
            ("npx playwright test", 12, "Playwright end-to-end testing"),
        ],
        "javascript": [
            ("npm test -s", 20, "JavaScript npm test runner"),
            ("npx jest --silent", 18, "Jest testing framework"),
            ("npx vitest run", 15, "Vitest testing framework"),
        ],
        "go": [
            ("go test ./...", 20, "Go testing all packages"),
            ("go test -v ./...", 15, "Go verbose testing"),
        ],
    }

    # Keyword-specific boost mappings
    keyword_boosts = {
        "pytest": {"pytest -q": 10, "python -m pytest -q": 8},
        "jest": {"npx jest --silent": 10},
        "vitest": {"npx vitest run": 10},
        "playwright": {"npx playwright test": 10},
        "tox": {"tox -q": 10},
        "test": {"pytest -q": 5, "npm test -s": 5, "go test ./...": 5},
        "tests": {"pytest -q": 5, "npm test -s": 5, "go test ./...": 5},
        "testing": {"pytest -q": 3, "npm test -s": 3, "go test ./...": 3},
        "ci": {"pytest -q": 3, "npm test -s": 3, "go test ./...": 3, "tox -q": 5},
        "npm": {"npm test -s": 8},
        "yarn": {"npm test -s": 5},  # fallback to npm
        "pnpm": {"npm test -s": 5},  # fallback to npm
        "python": {"pytest -q": 5, "python -m pytest -q": 5},
        "node": {"npm test -s": 5, "npx jest --silent": 3},
        "go": {"go test ./...": 8},
        "build": {"npm test -s": 2, "go test ./...": 2},
        "install": {"npm test -s": 1, "pytest -q": 1},
    }

    # Collect all unique commands with base scores
    command_scores: dict[str, dict[str, Any]] = {}

    # Add language-based commands
    for lang in detected_langs:
        lang_key = lang.lower()
        if lang_key in lang_commands:
            for cmd, base_score, _ in lang_commands[lang_key]:
                if cmd not in command_scores:
                    command_scores[cmd] = {
                        "score": base_score,
                        "rationale_parts": [f"detected {lang}"],
                    }
                else:
                    command_scores[cmd]["score"] += base_score // 2
                    command_scores[cmd]["rationale_parts"].append(f"detected {lang}")

    # Apply keyword boosts
    for keyword in keywords:
        if keyword in keyword_boosts:
            for cmd, boost in keyword_boosts[keyword].items():
                if cmd in command_scores:
                    command_scores[cmd]["score"] += boost
                    command_scores[cmd]["rationale_parts"].append(f'keyword "{keyword}"')
                else:
                    # Add new command based on keyword alone
                    command_scores[cmd] = {
                        "score": boost,
                        "rationale_parts": [f'keyword "{keyword}"'],
                    }

    # Add conservative defaults if no strong signals
    if not command_scores:
        command_scores["pytest -q"] = {"score": 5, "rationale_parts": ["conservative default"]}
        command_scores["npm test -s"] = {"score": 5, "rationale_parts": ["conservative default"]}

    # Build final suggestions with rationales
    for cmd, data in command_scores.items():
        score = data["score"]
        rationale = f"Score {score}: " + ", ".join(data["rationale_parts"])
        suggestions.append((cmd, score, rationale))

    # Sort by descending score, then alphabetically by command for ties
    suggestions.sort(key=lambda x: (-x[1], x[0]))

    return suggestions


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
        title: Title for the reproduction document
        assumptions: List of assumptions made
        commands: List of (command, score, rationale) tuples
        needs: List of environment/dependency needs
        next_steps: List of next steps to take

    Returns:
        Formatted markdown string
    """
    lines = []

    # Title
    lines.append(f"# {title}")
    lines.append("")

    # Assumptions section
    lines.append("## Assumptions")
    lines.append("")
    if assumptions:
        for assumption in assumptions:
            lines.append(f"- {assumption}")
    else:
        lines.append("- None specified")
    lines.append("")

    # Environment/Needs section
    lines.append("## Environment / Needs")
    lines.append("")
    if needs:
        for need in needs:
            lines.append(f"- {need}")
    else:
        lines.append("- Standard development environment")
    lines.append("")

    # Steps section with table
    lines.append("## Steps (ranked)")
    lines.append("")
    lines.append("| Score | Command | Why |")
    lines.append("|-------|---------|-----|")

    if commands:
        for cmd, score, rationale in commands:
            # Escape pipe characters in command and rationale for markdown table
            cmd_escaped = cmd.replace("|", "\\|")
            rationale_escaped = rationale.replace("|", "\\|")
            lines.append(f"| {score} | `{cmd_escaped}` | {rationale_escaped} |")
    else:
        lines.append("| - | No commands suggested | - |")

    lines.append("")

    # Next Steps section
    lines.append("## Next Steps")
    lines.append("")
    if next_steps:
        for step in next_steps:
            lines.append(f"- {step}")
    else:
        lines.append("- Run the suggested commands and analyze results")
        lines.append("- Review logs for error patterns")
        lines.append("- Adjust environment if needed")
    lines.append("")

    return "\n".join(lines)
