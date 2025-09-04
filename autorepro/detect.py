"""Language detection logic for AutoRepro."""

import glob
import os
from pathlib import Path

from .config import config

# Language detection patterns: language -> list of file patterns
# MVP limitation: source-file globs may cause false positives in sparse repos
LANGUAGE_PATTERNS = {
    "csharp": ["*.csproj", "*.sln", "*.cs"],
    "go": ["go.mod", "go.sum", "*.go"],
    "java": ["pom.xml", "build.gradle", "*.java"],
    "node": ["package.json", "yarn.lock", "pnpm-lock.yaml", "npm-shrinkwrap.json"],
    "python": ["pyproject.toml", "setup.py", "requirements.txt", "*.py"],
    "rust": ["Cargo.toml", "Cargo.lock", "*.rs"],
}

# Weighted index table for scoring language detection
WEIGHTED_PATTERNS = {
    # Lock files (configurable weight)
    "pnpm-lock.yaml": {
        "weight": config.detection.weights["lock"],
        "kind": "lock",
        "language": "node",
    },
    "yarn.lock": {
        "weight": config.detection.weights["lock"],
        "kind": "lock",
        "language": "node",
    },
    "npm-shrinkwrap.json": {
        "weight": config.detection.weights["lock"],
        "kind": "lock",
        "language": "node",
    },
    "package-lock.json": {
        "weight": config.detection.weights["lock"],
        "kind": "lock",
        "language": "node",
    },
    "go.sum": {
        "weight": config.detection.weights["lock"],
        "kind": "lock",
        "language": "go",
    },
    "Cargo.lock": {
        "weight": config.detection.weights["lock"],
        "kind": "lock",
        "language": "rust",
    },
    # Config/manifest files (configurable weight)
    "pyproject.toml": {
        "weight": config.detection.weights["config"],
        "kind": "config",
        "language": "python",
    },
    "go.mod": {
        "weight": config.detection.weights["config"],
        "kind": "config",
        "language": "go",
    },
    "Cargo.toml": {
        "weight": config.detection.weights["config"],
        "kind": "config",
        "language": "rust",
    },
    "pom.xml": {
        "weight": config.detection.weights["config"],
        "kind": "config",
        "language": "java",
    },
    "package.json": {
        "weight": config.detection.weights["config"],
        "kind": "config",
        "language": "node",
    },
    # Setup/requirements files (configurable weight)
    "setup.py": {
        "weight": config.detection.weights["setup"],
        "kind": "setup",
        "language": "python",
    },
    "requirements.txt": {
        "weight": config.detection.weights["setup"],
        "kind": "setup",
        "language": "python",
    },
}

# Source file patterns with configurable weights
SOURCE_PATTERNS = {
    "*.py": {
        "weight": config.detection.weights["source"],
        "kind": "source",
        "language": "python",
    },
    "*.go": {
        "weight": config.detection.weights["source"],
        "kind": "source",
        "language": "go",
    },
    "*.rs": {
        "weight": config.detection.weights["source"],
        "kind": "source",
        "language": "rust",
    },
    "*.java": {
        "weight": config.detection.weights["source"],
        "kind": "source",
        "language": "java",
    },
    "*.cs": {
        "weight": config.detection.weights["source"],
        "kind": "source",
        "language": "csharp",
    },
    "*.js": {
        "weight": config.detection.weights["source"],
        "kind": "source",
        "language": "node",
    },
    "*.ts": {
        "weight": config.detection.weights["source"],
        "kind": "source",
        "language": "node",
    },
    "*.jsx": {
        "weight": config.detection.weights["source"],
        "kind": "source",
        "language": "node",
    },
    "*.tsx": {
        "weight": config.detection.weights["source"],
        "kind": "source",
        "language": "node",
    },
    "*.csproj": {
        "weight": config.detection.weights["config"],
        "kind": "config",
        "language": "csharp",
    },
    "*.sln": {
        "weight": config.detection.weights["config"],
        "kind": "config",
        "language": "csharp",
    },
    "build.gradle": {
        "weight": config.detection.weights["config"],
        "kind": "config",
        "language": "java",
    },
    "build.gradle.kts": {
        "weight": config.detection.weights["config"],
        "kind": "config",
        "language": "java",
    },
}


def collect_evidence(root: Path) -> dict[str, dict[str, object]]:
    """
    Collect weighted evidence for language detection in the root directory.

    Args:
        root: Directory path to scan for language indicators

    Returns:
        Dictionary mapping language names to their evidence:
        {
            "language_name": {
                "score": int,
                "reasons": [{"pattern": str, "path": str, "kind": str, "weight": int}]
            }
        }
    """
    evidence: dict[str, dict[str, object]] = {}
    root_path = Path(root)

    # Check exact filename matches in WEIGHTED_PATTERNS
    for filename, info in WEIGHTED_PATTERNS.items():
        file_path = root_path / filename
        if file_path.is_file():
            lang = str(info["language"])
            if lang not in evidence:
                evidence[lang] = {"score": 0, "reasons": []}

            evidence[lang]["score"] = evidence[lang]["score"] + info["weight"]  # type: ignore
            evidence[lang]["reasons"].append(  # type: ignore
                {
                    "pattern": filename,
                    "path": f"./{filename}",
                    "kind": info["kind"],
                    "weight": info["weight"],
                }
            )

    # Check glob patterns in SOURCE_PATTERNS
    for pattern, info in SOURCE_PATTERNS.items():
        if "*" in pattern:
            # Glob pattern
            search_pattern = str(root_path / pattern)
            for match in glob.glob(search_pattern):
                if os.path.isfile(match):
                    lang = str(info["language"])
                    basename = os.path.basename(match)

                    if lang not in evidence:
                        evidence[lang] = {"score": 0, "reasons": []}

                    # Only add weight once per pattern type, even if multiple files match
                    # Check if we already added this pattern
                    pattern_already_added = any(
                        reason["pattern"] == pattern
                        for reason in evidence[lang]["reasons"]  # type: ignore
                    )

                    if not pattern_already_added:
                        evidence[lang]["score"] = evidence[lang]["score"] + info["weight"]  # type: ignore
                        evidence[lang]["reasons"].append(  # type: ignore
                            {
                                "pattern": pattern,
                                "path": f"./{basename}",
                                "kind": info["kind"],
                                "weight": info["weight"],
                            }
                        )
        else:
            # Exact filename
            file_path = root_path / pattern
            if file_path.is_file():
                lang = str(info["language"])
                if lang not in evidence:
                    evidence[lang] = {"score": 0, "reasons": []}

                evidence[lang]["score"] = evidence[lang]["score"] + info["weight"]  # type: ignore
                evidence[lang]["reasons"].append(  # type: ignore
                    {
                        "pattern": pattern,
                        "path": f"./{pattern}",
                        "kind": info["kind"],
                        "weight": info["weight"],
                    }
                )

    return evidence


def detect_languages_with_scores(root: Path) -> list[str]:
    """
    Detect languages in the given directory path, returning just language names.

    Args:
        root: Directory path to scan for language indicators

    Returns:
        List of language names sorted alphabetically.
        Used for new JSON functionality.
    """
    evidence = collect_evidence(root)
    return sorted(evidence.keys())


def detect_languages(path: str) -> list[tuple[str, list[str]]]:
    """
    Detect languages in the given directory path.

    Args:
        path: Directory path to scan for language indicators

    Returns:
        List of (language, reasons) tuples, where reasons are matched filenames.
        Results are sorted alphabetically by language name.
        Reasons within each language are sorted alphabetically.
    """
    results = []

    for lang, patterns in LANGUAGE_PATTERNS.items():
        matches = []

        for pattern in patterns:
            if "*" not in pattern:
                # Exact filename - check if it exists
                file_path = os.path.join(path, pattern)
                if os.path.isfile(file_path):
                    matches.append(pattern)
            else:
                # Glob pattern - find all matches and collect basenames
                search_pattern = os.path.join(path, pattern)
                for match in glob.glob(search_pattern):
                    if os.path.isfile(match):
                        basename = os.path.basename(match)
                        matches.append(basename)

        # Remove duplicates and sort
        if matches:
            unique_matches = sorted(set(matches))
            results.append((lang, unique_matches))

    # Sort results by language name
    return sorted(results, key=lambda x: x[0])
