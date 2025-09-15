"""Language detection logic for AutoRepro."""

import fnmatch
import glob
import os
from dataclasses import dataclass
from pathlib import Path

from .config import config


@dataclass
class EvidenceReason:
    """Configuration for adding evidence reasons."""

    pattern: str
    path: str
    kind: str
    weight: int


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


def _ensure_evidence_entry(
    evidence: dict[str, dict[str, object]], language: str
) -> None:
    """Ensure evidence entry exists for the given language."""
    if language not in evidence:
        evidence[language] = {"score": 0, "reasons": []}


def _add_evidence_reason(
    evidence: dict[str, dict[str, object]],
    language: str,
    reason: EvidenceReason,
) -> None:
    """Add a reason to the evidence for the given language."""
    _ensure_evidence_entry(evidence, language)
    evidence[language]["score"] = evidence[language]["score"] + reason.weight  # type: ignore
    evidence[language]["reasons"].append(  # type: ignore
        {
            "pattern": reason.pattern,
            "path": reason.path,
            "kind": reason.kind,
            "weight": reason.weight,
        }
    )


def _check_pattern_already_added(
    evidence: dict[str, dict[str, object]], language: str, pattern: str
) -> bool:
    """Check if pattern was already added for the given language."""
    if language not in evidence:
        return False
    return any(
        reason["pattern"] == pattern
        for reason in evidence[language]["reasons"]  # type: ignore
    )


def _process_weighted_patterns(
    evidence: dict[str, dict[str, object]], root_path: Path
) -> None:
    """Process exact filename matches from WEIGHTED_PATTERNS."""
    for filename, info in WEIGHTED_PATTERNS.items():
        file_path = root_path / filename
        if file_path.is_file():
            lang = str(info["language"])
            _add_evidence_reason(
                evidence,
                lang,
                EvidenceReason(
                    pattern=filename,
                    path=f"./{filename}",
                    kind=str(info["kind"]),
                    weight=(
                        int(info["weight"])
                        if isinstance(info["weight"], int | str)
                        else 0
                    ),
                ),
            )


def _process_source_patterns(
    evidence: dict[str, dict[str, object]], root_path: Path
) -> None:
    """Process SOURCE_PATTERNS for both glob patterns and exact filenames."""
    for pattern, info in SOURCE_PATTERNS.items():
        lang = str(info["language"])
        if "*" in pattern:
            _process_glob_pattern(evidence, root_path, pattern, info, lang)
        else:
            _process_exact_filename(evidence, root_path, pattern, info, lang)


def _process_glob_pattern(
    evidence: dict[str, dict[str, object]],
    root_path: Path,
    pattern: str,
    info: dict[str, object],
    lang: str,
) -> None:
    """Process a single glob pattern."""
    search_pattern = str(root_path / pattern)
    for match in glob.glob(search_pattern):
        if os.path.isfile(match):
            basename = os.path.basename(match)
            # Only add weight once per pattern type, even if multiple files match
            if not _check_pattern_already_added(evidence, lang, pattern):
                _add_evidence_reason(
                    evidence,
                    lang,
                    EvidenceReason(
                        pattern=pattern,
                        path=f"./{basename}",
                        kind=str(info["kind"]),
                        weight=(
                            int(info["weight"])
                            if isinstance(info["weight"], int | str)
                            else 0
                        ),
                    ),
                )


def _process_exact_filename(
    evidence: dict[str, dict[str, object]],
    root_path: Path,
    pattern: str,
    info: dict[str, object],
    lang: str,
) -> None:
    """Process an exact filename pattern."""
    file_path = root_path / pattern
    if file_path.is_file():
        _add_evidence_reason(
            evidence,
            lang,
            EvidenceReason(
                pattern=pattern,
                path=f"./{pattern}",
                kind=str(info["kind"]),
                weight=(
                    int(info["weight"]) if isinstance(info["weight"], int | str) else 0
                ),
            ),
        )


def _should_ignore_path(  # noqa: C901, PLR0912
    path: Path, root: Path, ignore_patterns: list[str], respect_gitignore: bool
) -> bool:
    """
    Check if a path should be ignored based on ignore patterns and gitignore rules.

    Args:
        path: Path to check
        root: Root directory for relative path calculation
        ignore_patterns: List of ignore patterns (glob-style)
        respect_gitignore: Whether to respect .gitignore rules

    Returns:
        True if path should be ignored, False otherwise
    """
    # Convert to relative path for pattern matching
    try:
        rel_path = path.relative_to(root)
        rel_path_str = str(rel_path)
    except ValueError:
        # Path is not relative to root, ignore it
        return True

    # Check against ignore patterns
    for pattern in ignore_patterns:
        if fnmatch.fnmatch(rel_path_str, pattern) or fnmatch.fnmatch(
            str(path.name), pattern
        ):
            return True

    # Check .gitignore if requested
    if respect_gitignore:
        # Enhanced .gitignore support with negation patterns
        gitignore_path = root / ".gitignore"
        if gitignore_path.exists():
            try:
                ignored = False
                with open(gitignore_path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            # Handle negation patterns (!)
                            if line.startswith("!"):
                                negation_pattern = line[1:]  # Remove the !
                                if negation_pattern.endswith("/"):
                                    dir_pattern = negation_pattern.rstrip("/")
                                    # Check if file is in negated directory
                                    if fnmatch.fnmatch(
                                        rel_path_str, dir_pattern + "/*"
                                    ) or fnmatch.fnmatch(
                                        rel_path_str, dir_pattern + "/**/*"
                                    ):
                                        ignored = False  # Un-ignore this file
                                else:
                                    # Regular negation pattern
                                    if fnmatch.fnmatch(
                                        rel_path_str, negation_pattern
                                    ) or fnmatch.fnmatch(
                                        rel_path_str, "**/" + negation_pattern
                                    ):
                                        ignored = False  # Un-ignore this file
                            else:
                                # Regular ignore patterns
                                # Handle directory patterns (ending with /)
                                if line.endswith("/"):
                                    dir_pattern = line.rstrip("/")
                                    # Check if file is in ignored directory
                                    path_parts = rel_path_str.split("/")
                                    if (
                                        len(path_parts) > 1
                                        and path_parts[0] == dir_pattern
                                    ):
                                        ignored = True
                                    # Also check full directory path matching
                                    elif fnmatch.fnmatch(
                                        rel_path_str, dir_pattern + "/*"
                                    ) or fnmatch.fnmatch(
                                        rel_path_str, dir_pattern + "/**/*"
                                    ):
                                        ignored = True
                                else:
                                    # Regular file pattern
                                    if fnmatch.fnmatch(
                                        rel_path_str, line
                                    ) or fnmatch.fnmatch(rel_path_str, "**/" + line):
                                        ignored = True

                return ignored
            except (OSError, UnicodeDecodeError):
                # Ignore errors reading .gitignore
                pass

    return False


def _collect_files_with_depth(  # noqa: C901, PLR0912
    root: Path,
    depth: int | None = None,
    ignore_patterns: list[str] | None = None,
    respect_gitignore: bool = False,
) -> dict[str, list[Path]]:
    """
    Collect files organized by pattern, respecting depth and ignore rules.

    Args:
        root: Root directory to scan
        depth: Maximum depth to scan (None for unlimited, 0 for root only)
        ignore_patterns: List of glob patterns to ignore
        respect_gitignore: Whether to respect .gitignore rules

    Returns:
        Dictionary mapping patterns to lists of matching file paths
    """
    if ignore_patterns is None:
        ignore_patterns = []

    # Collect all patterns we need to match
    all_patterns = {}

    # Add WEIGHTED_PATTERNS (exact filenames)
    for filename, info in WEIGHTED_PATTERNS.items():
        all_patterns[filename] = info

    # Add SOURCE_PATTERNS (both globs and exact files)
    for pattern, info in SOURCE_PATTERNS.items():
        all_patterns[pattern] = info

    # Organize results by pattern
    results: dict[str, list[Path]] = {pattern: [] for pattern in all_patterns.keys()}

    # Use rglob to find all files
    if depth == 0:
        # Only scan root directory
        scan_paths = [p for p in root.iterdir() if p.is_file()]
    else:
        # Use rglob for recursive scanning
        scan_paths = list(root.rglob("*"))
        # Filter by depth if specified
        if depth is not None:
            filtered_paths = []
            for p in scan_paths:
                if p.is_file():
                    rel_path = p.relative_to(root)
                    # Count directory depth (not including the filename)
                    dir_depth = len(rel_path.parts) - 1
                    if dir_depth <= depth:
                        filtered_paths.append(p)
            scan_paths = filtered_paths
        else:
            scan_paths = [p for p in scan_paths if p.is_file()]

    # Filter out ignored paths
    scan_paths = [
        p
        for p in scan_paths
        if not _should_ignore_path(p, root, ignore_patterns, respect_gitignore)
    ]

    # Match files against patterns
    for file_path in scan_paths:
        filename = file_path.name

        # Check exact filename matches (WEIGHTED_PATTERNS)
        if filename in all_patterns:
            results[filename].append(file_path)

        # Check glob patterns (SOURCE_PATTERNS with *)
        for pattern in all_patterns:
            if "*" in pattern and fnmatch.fnmatch(filename, pattern):
                results[pattern].append(file_path)

    return results


def _collect_files_sample(
    pattern_files: dict[str, list[Path]], root: Path, show_count: int = 5
) -> dict[str, list[str]]:
    """
    Collect sample files for each language with stable ordering.

    Args:
        pattern_files: Dictionary mapping patterns to file lists
        root: Root directory for relative path calculation
        show_count: Maximum number of sample files per language

    Returns:
        Dictionary mapping language names to lists of sample file paths
    """
    language_files: dict[str, set[Path]] = {}

    # Collect all files per language
    all_patterns = {**WEIGHTED_PATTERNS, **SOURCE_PATTERNS}

    for pattern, file_list in pattern_files.items():
        if pattern in all_patterns and file_list:
            lang = str(all_patterns[pattern]["language"])
            if lang not in language_files:
                language_files[lang] = set()
            language_files[lang].update(file_list)

    # Convert to relative paths and create stable ordering
    result: dict[str, list[str]] = {}
    for lang, files in language_files.items():
        # Convert to relative paths and sort for stable ordering
        rel_paths = []
        for file_path in files:
            try:
                rel_path = f"./{file_path.relative_to(root)}"
                rel_paths.append(rel_path)
            except ValueError:
                # Skip files that can't be made relative
                continue

        # Sort for stable ordering and limit to show_count
        rel_paths.sort()
        result[lang] = rel_paths[:show_count]

    return result


def collect_evidence(  # noqa: C901
    root: Path,
    depth: int | None = None,
    ignore_patterns: list[str] | None = None,
    respect_gitignore: bool = False,
    show_files_sample: int | None = None,
) -> dict[str, dict[str, object]]:
    """
    Collect weighted evidence for language detection with enhanced filtering.

    Args:
        root: Directory path to scan for language indicators
        depth: Maximum depth to scan (None for unlimited, 0 for root only)
        ignore_patterns: List of glob patterns to ignore
        respect_gitignore: Whether to respect .gitignore rules
        show_files_sample: Number of sample files to include per language (None to exclude)

    Returns:
        Dictionary mapping language names to their evidence:
        {
            "language_name": {
                "score": int,
                "reasons": [{"pattern": str, "path": str, "kind": str, "weight": int}],
                "files_sample": [list of sample file paths] (when show_files_sample is provided)
            }
        }
    """
    evidence: dict[str, dict[str, object]] = {}
    root_path = Path(root)

    if ignore_patterns is None:
        ignore_patterns = []

    # Collect files with filtering
    pattern_files = _collect_files_with_depth(
        root_path, depth, ignore_patterns, respect_gitignore
    )

    # Process WEIGHTED_PATTERNS (exact filenames)
    for filename, info in WEIGHTED_PATTERNS.items():
        if filename in pattern_files and pattern_files[filename]:
            # Use first matching file for the path
            file_path = pattern_files[filename][0]
            rel_path = f"./{file_path.relative_to(root_path)}"

            lang = str(info["language"])
            _add_evidence_reason(
                evidence,
                lang,
                EvidenceReason(
                    pattern=filename,
                    path=rel_path,
                    kind=str(info["kind"]),
                    weight=(
                        int(info["weight"])
                        if isinstance(info["weight"], int | str)
                        else 0
                    ),
                ),
            )

    # Process SOURCE_PATTERNS
    for pattern, info in SOURCE_PATTERNS.items():
        lang = str(info["language"])

        if "*" in pattern:
            # Glob pattern
            if pattern in pattern_files and pattern_files[pattern]:
                # Only add weight once per pattern, even if multiple files match
                if not _check_pattern_already_added(evidence, lang, pattern):
                    # Use first matching file for the path
                    file_path = pattern_files[pattern][0]
                    rel_path = f"./{file_path.relative_to(root_path)}"

                    _add_evidence_reason(
                        evidence,
                        lang,
                        EvidenceReason(
                            pattern=pattern,
                            path=rel_path,
                            kind=str(info["kind"]),
                            weight=(
                                int(info["weight"])
                                if isinstance(info["weight"], int | str)
                                else 0
                            ),
                        ),
                    )
        else:
            # Exact filename (already handled in WEIGHTED_PATTERNS section above)
            pass

    # Add files_sample if requested
    if show_files_sample is not None:
        files_sample = _collect_files_sample(
            pattern_files, root_path, show_files_sample
        )
        for lang in evidence:
            if lang in files_sample:
                evidence[lang]["files_sample"] = files_sample[lang]

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
