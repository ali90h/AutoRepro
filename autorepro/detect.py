"""Language detection logic for AutoRepro."""

import glob
import os

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
