# AutoRepro

AutoRepro is a developer tools project that transforms issue descriptions into clear reproducibility steps and a shareable framework. Instead of wasting time wondering "How do I reproduce this?", AutoRepro automatically detects repository technologies, generates ready-made devcontainers, and writes prioritized repro plans (repro.md) with explicit assumptions and execution commands.

## Features

The current MVP scope includes three core commands:
- **scan**: Detect languages/frameworks from file pointers (✅ implemented)
- **init**: Create a developer container (✅ implemented)
- **plan**: Derive an execution plan from issue description (✅ implemented)

The project targets multilingualism (initially Python/JS/Go) and emphasizes simplicity, transparency, and automated testing. The ultimate goal is to produce tests that automatically fail and open Draft PRs containing them, improving contribution quality and speeding up maintenance on GitHub.

## Installation

### Local Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/ali90h/AutoRepro.git
   cd AutoRepro
   ```

2. **Create a Python 3.11 virtual environment:**
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install the package in editable mode:**
   ```bash
   pip install -e .
   ```

## Usage

### Running AutoRepro

```bash
# Display help and available commands
autorepro --help

# Scan current directory for language/framework indicators
autorepro scan

# Create a devcontainer.json file
autorepro init

# Generate a reproduction plan from issue description
autorepro plan --desc "tests failing with pytest"

# Dry-run mode (outputs to stdout without creating files)
autorepro plan --desc "npm test issues" --dry-run

# Output to stdout instead of file (--out - ignores --force)
autorepro plan --desc "build problems" --out -

# Work with repository in different directory
autorepro plan --desc "CI failing" --repo /path/to/project

# Limit number of suggested commands
autorepro plan --desc "test failures" --max 3

# Read issue description from file
autorepro plan --file issue.txt

# Read file with repository context
autorepro plan --file issue.txt --repo /path/to/project
```

**Notes:**
- When using `--out -` (stdout), the `--force` flag is ignored for both `init` and `plan` commands.
- File paths in `--file` are resolved relative to current working directory first. If the file is not found and `--repo` is specified, it falls back to resolving relative to the repository directory.

### Scan Command

Detects repo languages and prints the reasons (marker files).

```bash
# Example output when multiple languages are detected
$ autorepro scan
Detected: node, python
- node -> package.json
- python -> pyproject.toml

# Example output when no languages are detected
$ autorepro scan
No known languages detected.
```

**Status:** `scan` is implemented and prints per-language detection reasons (deterministic order; root-only).

**Scan Behavior:**
- **Root-only**: Scans only the current directory (non-recursive)
- **Deterministic ordering**: Languages and reasons are sorted alphabetically
- **Detection patterns**: Uses both exact filenames and glob patterns to identify technologies

**Supported Languages:**
- **C#**: `*.csproj`, `*.sln`, `*.cs`
- **Go**: `go.mod`, `go.sum`, `*.go`
- **Java**: `pom.xml`, `build.gradle`, `*.java`
- **Node.js**: `package.json`, `yarn.lock`, `pnpm-lock.yaml`, `npm-shrinkwrap.json`
- **Python**: `pyproject.toml`, `setup.py`, `requirements.txt`, `*.py`
- **Rust**: `Cargo.toml`, `Cargo.lock`, `*.rs`

**Known limitations (MVP):**
- Source-file globs (e.g., `*.py`, `*.go`) may cause false positives in sparse repos; prefer root indicators (config/lockfiles).
- Future direction: weight/score reasons and down-rank raw source globs in favor of strong root indicators (tracked on the roadmap).

### Init Command

Creates a devcontainer.json file with default configuration (Python 3.11, Node 20, Go 1.22). The command is idempotent and provides atomic file writes.

```bash
# Create default devcontainer (first time)
$ autorepro init
Wrote devcontainer to .devcontainer/devcontainer.json

# Run again - idempotent behavior (exit code 0)
$ autorepro init
devcontainer.json already exists at .devcontainer/devcontainer.json.
Use --force to overwrite or --out <path> to write elsewhere.

# Force overwrite existing file with changes
$ autorepro init --force
Overwrote devcontainer at .devcontainer/devcontainer.json
Changes:
~ postCreateCommand: "old command" -> "python -m venv .venv && source .venv/bin/activate && python -m pip install -e ."

# Force overwrite with no changes
$ autorepro init --force
Overwrote devcontainer at .devcontainer/devcontainer.json
No changes.

# Custom output location
$ autorepro init --out dev/devcontainer.json
Wrote devcontainer at dev/devcontainer.json

# Output to stdout (ignores --force)
$ autorepro init --out -
{"name": "autorepro-dev", "features": {...}}

# Preview mode without creating files
$ autorepro init --dry-run
{"name": "autorepro-dev", "features": {...}}

# Execute on different repository
$ autorepro init --repo /path/to/project
Wrote devcontainer at /path/to/project/.devcontainer/devcontainer.json
```

**Status:** `init` is implemented with idempotent behavior and proper exit codes.

**Init Behavior:**
- **Idempotent**: Won't overwrite existing files without `--force` flag (returns exit code 0)
- **Atomic writes**: Uses temporary file + rename for safe file creation
- **Directory creation**: Automatically creates parent directories as needed
- **Exit codes**: 0=success/exists, 1=I/O errors, 2=misuse (e.g., --out points to directory)

**Options:**
- `--force`: Overwrite existing devcontainer.json file
- `--out PATH`: Custom output path (default: .devcontainer/devcontainer.json)
- `--out -`: Output to stdout instead of creating a file (ignores --force)
- `--dry-run`: Display contents to stdout without writing files
- `--repo PATH`: Execute all logic on specified repository path

### Plan Command

Generates structured reproduction plans from issue descriptions, combining keyword analysis with project language detection to suggest prioritized commands.

```bash
# Generate plan from description
$ autorepro plan --desc "pytest tests failing on CI"
repro.md

# Generate plan from file
$ autorepro plan --file issue.txt
repro.md

# Custom output path
$ autorepro plan --desc "npm test issues" --out my_plan.md
my_plan.md

# Overwrite existing plan
$ autorepro plan --desc "build failing" --force
repro.md

# Limit number of suggested commands
$ autorepro plan --desc "tests timeout" --max 3
repro.md

# JSON format output
$ autorepro plan --desc "linting errors" --format json
repro.md  # Contains JSON format

# Preview to stdout without creating files
$ autorepro plan --desc "pytest failing" --dry-run
# Issue Reproduction Plan

## Assumptions
...

# Output to stdout (ignores --force)
$ autorepro plan --desc "npm test issues" --out -
# Issue Reproduction Plan
...

# Execute on different repository
$ autorepro plan --desc "build failing" --repo /path/to/project
Wrote repro to /path/to/project/repro.md
```

**Status:** `plan` is implemented with intelligent command suggestions and markdown output.

**Plan Behavior:**
- **Input options**: `--desc "text"` or `--file path.txt` (mutually exclusive, one required)
- **Language detection**: Uses `scan` results to weight command suggestions
- **Keyword extraction**: Filters stopwords while preserving dev terms (pytest, npm, tox, etc.)
- **Command scoring**: Combines language priors + keyword matches for ranking
- **Structured output**: Title, Assumptions, Environment/Needs, Steps table, Next Steps

**Options:**
- `--desc TEXT`: Issue description text
- `--file PATH`: Path to file containing issue description
- `--out PATH`: Output path (default: repro.md)
- `--out -`: Output to stdout instead of creating a file (ignores --force)
- `--force`: Overwrite existing output file
- `--max N`: Maximum suggested commands (default: 5)
- `--format md|json`: Output format (default: md)
- `--dry-run`: Display contents to stdout without writing files
- `--repo PATH`: Execute all logic on specified repository path

## Exit Codes

AutoRepro uses standard exit codes to indicate success or failure:

- **0**: Success (including "already exists" and overwrite operations)
- **1**: Unexpected I/O or permission errors
- **2**: Misuse (e.g., `--out` points to a directory, missing --desc/--file)

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run tests with verbose output
pytest -v
```

### Project Structure

```
autorepro/
├── README.md              # This file
├── LICENSE                # Apache-2.0
├── pyproject.toml         # Package configuration
├── autorepro/             # Main package
│   ├── __init__.py
│   └── cli.py            # Command line interface
├── tests/                 # Test suite
│   └── test_cli.py
└── .github/workflows/     # CI/CD
    └── ci.yml
```

## Requirements

- Python >= 3.11
- pytest (for development)

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Contributing

This project is in early development. More contribution guidelines will be available as the project evolves.
