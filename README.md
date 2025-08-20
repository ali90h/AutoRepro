# AutoRepro

AutoRepro is a developer tools project that transforms issue descriptions into clear reproducibility steps and a shareable framework. Instead of wasting time wondering "How do I reproduce this?", AutoRepro automatically detects repository technologies, generates ready-made devcontainers, and writes prioritized repro plans (repro.md) with explicit assumptions and execution commands.

## Features

The current MVP scope includes three core commands:
- **scan**: Detect languages/frameworks from file pointers (✅ implemented)
- **init**: Create a developer container (✅ implemented)
- **plan**: Derive an execution plan from issue description (coming soon)

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
```

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
Wrote devcontainer to dev/devcontainer.json
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

## Exit Codes

AutoRepro uses standard exit codes to indicate success or failure:

- **0**: Success (including "already exists" and overwrite operations)
- **1**: Unexpected I/O or permission errors
- **2**: Misuse (e.g., `--out` points to a directory)

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
