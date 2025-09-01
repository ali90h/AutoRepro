# AutoRepro

AutoRepro is a developer tools project that transforms issue descriptions into clear reproducibility steps and a shareable framework. Instead of wasting time wondering "How do I reproduce this?", AutoRepro automatically detects repository technologies, generates ready-made devcontainers, and writes prioritized repro plans (repro.md) with explicit assumptions and execution commands.

## Features

The current MVP scope includes six core commands:
- **scan**: Detect languages/frameworks from file pointers (✅ implemented)
- **init**: Create a developer container (✅ implemented)
- **plan**: Derive an execution plan from issue description (✅ implemented)
- **exec**: Execute the top plan command (✅ implemented)
- **report**: Combine plan + run log + environment metadata into zip artifact (✅ implemented)
- **pr**: Create Draft PR from reproduction plan (✅ implemented)

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
   python -m pip install -e .
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

# Execute the top suggested command
autorepro exec --desc "pytest failing"

# Execute with logging and timeout
autorepro exec --desc "build issues" --jsonl exec.log --timeout 60

# Dry-run to see what command would be executed
autorepro exec --desc "npm test problems" --dry-run

# Create comprehensive report bundle for CI/issue tracking
autorepro report --desc "pytest failing with timeout"

# Generate report with execution logs
autorepro report --desc "build errors" --exec --out /tmp/issue_report.zip

# Preview report contents without creating zip
autorepro report --desc "test failures" --out -

# JSON format report with custom timeout
autorepro report --desc "linting issues" --format json --exec --timeout 60

# Create Draft PR from reproduction plan
autorepro pr --desc "pytest failing on CI"

# Update existing draft PR with new content
autorepro pr --desc "pytest failing" --update-if-exists

# Create ready (non-draft) PR with custom base branch
autorepro pr --desc "build issues" --ready --base develop

# Create PR with labels and assignees
autorepro pr --desc "test failures" --label bug --label testing --assignee testuser
```

**Notes:**
- When using `--out -` (stdout): `--force` is ignored for `init` and `plan` commands, while `report` shows contents manifest instead of creating zip
- File paths in `--file` are resolved relative to current working directory first. If the file is not found and `--repo` is specified, it falls back to resolving relative to the repository directory
- `report` command success messages go to stderr (visible with `-v`), keeping stdout clean for pipes

### Scan Command

Detects repo languages and prints the reasons (marker files). Supports both text and JSON output formats with weighted scoring.

```bash
# Default text output - shows detected languages and reasons
$ autorepro scan
Detected: node, python
- node -> package.json
- python -> pyproject.toml

# Text output with scores
$ autorepro scan --show-scores
Detected: node, python
- node -> package.json
  Score: 3
- python -> pyproject.toml
  Score: 3

# JSON output with detailed scoring and reasoning
$ autorepro scan --json
{
  "root": "/absolute/path/to/project",
  "detected": ["node", "python"],
  "languages": {
    "node": {
      "score": 7,
      "reasons": [
        {
          "pattern": "package.json",
          "path": "./package.json",
          "kind": "config",
          "weight": 3
        },
        {
          "pattern": "pnpm-lock.yaml",
          "path": "./pnpm-lock.yaml",
          "kind": "lock",
          "weight": 4
        }
      ]
    },
    "python": {
      "score": 5,
      "reasons": [
        {
          "pattern": "pyproject.toml",
          "path": "./pyproject.toml",
          "kind": "config",
          "weight": 3
        },
        {
          "pattern": "*.py",
          "path": "./main.py",
          "kind": "source",
          "weight": 1
        }
      ]
    }
  }
}

# No indicators found - empty results with exit code 0
$ autorepro scan --json
{
  "root": "/path/to/empty/project",
  "detected": [],
  "languages": {}
}
```

**Status:** `scan` is implemented with weighted scoring system and dual output formats (text/JSON).

**Scan Options:**
- `--json`: Output in JSON format with scores and detailed reasons
- `--show-scores`: Add score lines to text output (ignored with --json)

**Weighted Scoring System:**
- **Lock files (weight 4)**: `pnpm-lock.yaml`, `yarn.lock`, `npm-shrinkwrap.json`, `package-lock.json`, `go.sum`, `Cargo.lock`
- **Config/manifest files (weight 3)**: `pyproject.toml`, `go.mod`, `Cargo.toml`, `pom.xml`, `build.gradle*`, `*.csproj`, `*.sln`, `package.json`
- **Setup/requirements (weight 2)**: `setup.py`, `requirements.txt`
- **Source files (weight 1)**: `*.py`, `*.go`, `*.rs`, `*.java`, `*.cs`, `*.js`, `*.ts`, etc.

**Scan Behavior:**
- **Root-only**: Scans only the current directory (non-recursive)
- **Deterministic ordering**: Languages and reasons are sorted alphabetically
- **Score accumulation**: Multiple indicators for same language add their weights together
- **Exit code 0**: Always succeeds, even with no detections

**Supported Languages:**
- **C#**: `*.csproj`, `*.sln`, `*.cs`
- **Go**: `go.mod`, `go.sum`, `*.go`
- **Java**: `pom.xml`, `build.gradle`, `*.java`
- **Node.js**: `package.json`, `yarn.lock`, `pnpm-lock.yaml`, `npm-shrinkwrap.json`
- **Python**: `pyproject.toml`, `setup.py`, `requirements.txt`, `*.py`
- **Rust**: `Cargo.toml`, `Cargo.lock`, `*.rs`

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

# Output to stdout (ignores --force)
$ autorepro init --out -
{"name": "autorepro-dev", "features": {...}}

# Preview mode without creating files
$ autorepro init --dry-run
{"name": "autorepro-dev", "features": {...}}

# Execute on different repository
$ autorepro init --repo /path/to/project
Wrote devcontainer to /path/to/project/.devcontainer/devcontainer.json
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
{
  "title": "Linting Errors",
  "assumptions": ["Project uses python based on detected files"],
  "needs": {"devcontainer_present": false},
  "commands": [
    {
      "cmd": "pytest -q",
      "score": 6,
      "rationale": "matched keywords: pytest; detected langs: python; bonuses: direct: pytest (+3), lang: python (+2), specific (+1)",
      "matched_keywords": ["pytest"],
      "matched_langs": ["python"]
    }
  ],
  "next_steps": ["Run the suggested commands in order of priority", "Check logs and error messages for patterns"]
}

# JSON format to stdout (--out - ignores --force)
$ autorepro plan --desc "pytest failing" --format json --out -
{JSON output to stdout}

# JSON format to file
$ autorepro plan --desc "jest flaky" --format json --out repro.json
Wrote repro to repro.json

# JSON format with repository context
$ autorepro plan --repo ./some/project --format json --out -
{JSON output with language detection from specified project}

# Preview to stdout without creating files
$ autorepro plan --desc "pytest failing" --dry-run
# Issue Reproduction Plan

## Assumptions
- Project uses python based on detected files

## Candidate Commands
- `pytest -q` — matched: pytest (+3), lang: python (+2), specific (+1)
- `python -m pytest -q` — matched: pytest (+3), lang: python (+2)
...

# Output to stdout (ignores --force)
$ autorepro plan --desc "npm test issues" --out -
# Issue Reproduction Plan
...

# Execute on different repository
$ autorepro plan --desc "build failing" --repo /path/to/project
Wrote repro to /path/to/project/repro.md

# Quality gates: filter low-scoring commands
$ autorepro plan --desc "pytest failing" --min-score 3
repro.md

# Strict mode: fail if no high-quality suggestions
$ autorepro plan --desc "random issue" --min-score 5 --strict
no candidate commands above min-score=5

# Quality gates with JSON output
$ autorepro plan --desc "jest tests" --format json --min-score 4
{
  "title": "Jest Tests",
  "assumptions": [
    "Project uses node based on detected files",
    "Filtered 8 low-scoring command suggestions (min-score=4)"
  ],
  "commands": [
    {
      "cmd": "npx jest -w=1",
      "score": 6,
      "rationale": "matched keywords: jest; detected langs: node; bonuses: direct: jest (+3), lang: node (+2), specific (+1)"
    }
  ]
}
```

**Status:** `plan` is implemented with intelligent command suggestions and supports both markdown and JSON output formats.

**Plan Behavior:**
- **Input options**: `--desc "text"` or `--file path.txt` (mutually exclusive, one required)
- **Language detection**: Uses `scan` results to weight command suggestions
- **Keyword extraction**: Filters stopwords while preserving dev terms (pytest, npm, tox, etc.)
- **Command scoring**: Combines language priors + keyword matches for ranking (plugin commands take precedence over built-in when tied)
- **Structured output**: Title, Assumptions, Environment/Needs, Candidate Commands (prioritized list), Next Steps
- **JSON format**: Includes parsed matched_keywords and matched_langs for each command, plus devcontainer_present boolean in needs

**Options:**
- `--desc TEXT`: Issue description text
- `--file PATH`: Path to file containing issue description (resolved relative to CWD; falls back to --repo if not found)
- `--out PATH`: Output path (default: repro.md)
- `--out -`: Output to stdout instead of creating a file (ignores --force)
- `--force`: Overwrite existing output file
- `--max N`: Maximum suggested commands (default: 5)
- `--format md|json`: Output format (default: md)
- `--min-score N`: Drop commands with score < N (default: 2)
- `--strict`: Exit with code 1 if no commands make the cut after filtering
- `--dry-run`: Display contents to stdout without writing files
- `--repo PATH`: Execute all logic on specified repository path

### Report Command

Creates comprehensive report bundles that combine reproduction plans, execution logs, and environment metadata into zip artifacts. Perfect for CI systems and issue tracking.

```bash
# Basic report generation
$ autorepro report --desc "pytest failing with timeout"
Report bundle created: out/repro_bundle.zip

# Custom output location
$ autorepro report --desc "build errors" --out /tmp/issue_123.zip

# JSON format report
$ autorepro report --desc "linting issues" --format json --out reports/lint_issue.zip

# Report with command execution
$ autorepro report --desc "test failures" --exec
# Creates zip with repro.md, ENV.txt, run.log, runs.jsonl

# Execute with custom command selection and timeout
$ autorepro report --desc "CI tests timeout" --exec --index 1 --timeout 300

# Preview contents without creating zip file
$ autorepro report --desc "build problems" --out -
CONTENTS:
- repro.md
- ENV.txt

# Preview with execution logs
$ autorepro report --desc "pytest issues" --exec --out -
CONTENTS:
- repro.md
- ENV.txt
- run.log
- runs.jsonl

# Strict mode - fail if no quality commands found
$ autorepro report --desc "random issue" --strict --min-score 5
no candidate commands above min-score=5
# Exit code: 1, no zip created

# Report from file input
$ autorepro report --file issue_description.txt --exec --out bug_report.zip

# Report with environment variables for execution
$ autorepro report --desc "env-dependent test" --exec --env "DEBUG=1" --env "TEST_ENV=ci"

# Load environment from file
$ autorepro report --desc "database tests" --exec --env-file .env.test
```

**Status:** `report` is implemented with comprehensive bundling and CI integration features.

**Report Bundle Contents:**
- **repro.md** or **repro.json**: Reproduction plan (based on --format)
- **ENV.txt**: Environment metadata (Python version, platform, scan synopsis)
- **run.log**: Command execution log (only with --exec)
- **runs.jsonl**: Structured execution metadata (only with --exec)

**Report Behavior:**
- **Strict mode**: When `--strict` and no commands ≥ min-score exist, prints error to stderr and exits code 1 without creating zip
- **Manifest preview**: `--out -` prints contents list to stdout without creating zip file
- **Sorted contents**: Files in zip are alphabetically ordered for consistency
- **Clean logging**: Success messages go to stderr (use `-v` to see), stdout stays clean for pipes

**Options:**
- `--desc TEXT`: Issue description text
- `--file PATH`: Path to file containing issue description
- `--repo PATH`: Execute all logic on specified repository path
- `--format md|json`: Output format for plan (default: md)
- `--out PATH`: Output zip file path (default: out/repro_bundle.zip)
- `--out -`: Preview contents manifest to stdout (no zip created)
- `--dry-run`: Show what would be packaged without creating zip file
- `--min-score N`: Drop commands with score < N (default: 2)
- `--strict`: Exit with code 1 if no commands make the cut after filtering
- `--exec`: Execute the best command before packaging
- `--index N`: Pick the N-th suggested command when using --exec (default: 0 = top)
- `--timeout N`: Command timeout in seconds when using --exec (default: 120)
- `--env KEY=VAL`: Set environment variable when using --exec (repeatable)
- `--env-file PATH`: Load environment variables from file when using --exec
- `--tee PATH`: Append full stdout/stderr to log file when using --exec
- `--jsonl PATH`: Append JSON line record per run when using --exec

### PR Command (Draft PR Bootstrap)

Automatically creates GitHub Draft PRs from reproduction plans using the GitHub CLI. Streamlines the process from issue description to structured PR ready for review.

```bash
# Basic Draft PR creation
$ autorepro pr --desc "pytest failing on CI"
Created draft PR from branch feature/fix-tests

# Update existing draft PR from same branch
$ autorepro pr --desc "updated reproduction steps" --update-if-exists
Updated draft PR #42

# Ready PR (not draft) with custom base branch
$ autorepro pr --desc "build system issues" --ready --base develop
Created ready PR from branch fix/build-system

# PR with labels and team assignment
$ autorepro pr --desc "flaky test in CI" --label bug --label testing --assignee devteam --reviewer maintainer

# Custom title and body from file
$ autorepro pr --desc "issue description" --title "fix: resolve test flakiness" --body pr-template.md

# JSON format source with custom repository
$ autorepro pr --desc "memory leak investigation" --format json --repo-slug owner/repo

# Testing mode - see what would happen without creating PR
$ autorepro pr --desc "test issue" --dry-run
Would run: gh pr create --title "chore(repro): Test Issue [draft]" --body-file /tmp/body.md --base main --head feature-branch --draft

# Skip pushing for testing environments
$ autorepro pr --desc "local test" --skip-push --dry-run
```

**Status:** `pr` is implemented with full GitHub CLI integration for automated PR workflows.

**PR Creation Process:**
1. **Repository Detection**: Automatically detects GitHub repository from git remotes
2. **Plan Generation**: Creates reproduction plan internally if not using custom title/body
3. **Branch Management**: Ensures current branch exists on origin (pushes if needed)
4. **PR Creation**: Uses GitHub CLI to create structured Draft PR
5. **Update Support**: Can update existing draft PRs from the same branch

**Generated PR Structure:**
- **Title**: `chore(repro): <PlanTitle> [draft]` (no `[draft]` suffix when `--ready`)
- **Body**: Structured markdown with plan title, assumptions, and top 3 candidate commands
- **Footer Note**: References CI artifact availability (from T-015 report integration)

**PR Behavior:**
- **Draft by Default**: Creates draft PRs unless `--ready` specified
- **Auto-Push**: Pushes current branch to origin unless `--skip-push` used
- **Update Mode**: `--update-if-exists` updates existing draft PR instead of creating new
- **Error Recovery**: Provides helpful error messages with suggested fixes

**Options:**
- `--desc TEXT`: Issue description text
- `--file PATH`: Path to file containing issue description
- `--repo PATH`: Execute all logic on specified repository path
- `--title TEXT`: Custom PR title (default: auto-generated from plan)
- `--body FILE|-`: Custom PR body file or stdin (default: auto-generated from plan)
- `--format md|json`: Source format for auto-generating PR body (default: md)
- `--base BRANCH`: Target branch for PR (default: main)
- `--draft`: Create as draft PR (default: true)
- `--ready`: Create as ready PR (not draft)
- `--update-if-exists`: Update existing draft PR from same branch instead of creating new
- `--label LABEL`: Add label to PR (repeatable)
- `--assignee USER`: Assign user to PR (repeatable)
- `--reviewer USER`: Request review from user (repeatable)
- `--gh PATH`: Path to gh CLI tool (default: gh from PATH)
- `--repo-slug owner/repo`: Repository slug to bypass git remote detection
- `--skip-push`: Skip pushing branch to origin (useful for testing)
- `--min-score N`: Drop commands with score < N (default: 2)
- `--strict`: Exit with code 1 if no commands make the cut after filtering
- `--dry-run`: Show GitHub CLI commands without executing

**Testing Setup (Local/Offline):**

For development and CI testing without real GitHub integration:

```bash
# Setup fake GitHub remote with local bare repo
git init --bare /tmp/fake-origin.git
git remote add origin /tmp/fake-origin.git
git remote set-url --push origin /tmp/fake-origin.git
git remote set-url origin https://github.com/owner/repo.git  # fake fetch URL

# Create fake gh CLI tool
mkdir -p /tmp/fakebin
cat > /tmp/fakebin/gh << 'EOF'
#!/bin/bash
echo "Fake gh called with: $@" >&2
case "$1 $2" in
  "pr list") echo '[]' ;;
  "pr create") echo "https://github.com/owner/repo/pull/123" ;;
  "pr edit") echo "Updated PR #123" ;;
  *) exit 1 ;;
esac
EOF
chmod +x /tmp/fakebin/gh

# Test with fake environment
PATH="/tmp/fakebin:$PATH" autorepro pr --desc "test issue" --repo-slug owner/repo --skip-push --dry-run
```

**Error Messages & Recovery:**

The PR command provides helpful error messages with suggested solutions:

```bash
# Repository detection failure
Failed to detect GitHub repository: Unable to parse GitHub URL
Try: git remote add origin https://github.com/owner/repo.git
Or use: --repo-slug owner/repo to specify manually

# Push failure
Push to origin failed: Permission denied
Try: git push -u origin feature-branch
Or check: gh auth status
Or use: --skip-push for testing without pushing

# Branch not on remote with --skip-push
Branch feature-branch does not exist on origin
Push required: git push -u origin feature-branch
Or remove --skip-push to auto-push
```

## Extending Rules

AutoRepro supports extending command suggestions via plugins loaded through the `AUTOREPRO_PLUGINS` environment variable:

**Plugin packages:** `AUTOREPRO_PLUGINS="pkg.module1,pkg.module2"`
**Direct file paths:** `AUTOREPRO_PLUGINS="/path/to/plugin.py,other_plugin.py"`
**Debug errors:** `AUTOREPRO_PLUGINS_DEBUG=1` (shows import failures instead of silent ignore)

**Example plugin (`custom_rules.py`):**
```python
from autorepro.rules import Rule

def provide_rules():
    return {
        "python": [Rule("pytest -k smoke", {"pytest", "smoke"}, 3, {"test"})],
        "node": [Rule("npm run test:unit", {"unit", "test"}, 2, {"test"})]
    }
```

Usage: `AUTOREPRO_PLUGINS="custom_rules.py" autorepro plan --desc "smoke tests failing"`

## Exit Codes

AutoRepro uses standard exit codes to indicate success or failure:

- **0**: Success (including "already exists" and overwrite operations)
- **1**: Unexpected I/O or permission errors, or strict failure (no commands ≥ min-score with --strict)
- **2**: Misuse (e.g., `--out` points to a directory, missing --desc/--file)

**Special cases:**
- `exec` command: Returns the subprocess exit code on successful execution
- `report --exec`: Returns the subprocess exit code while still creating the zip bundle (unless strict mode prevents execution)

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run tests with verbose output
pytest -v

# Run golden tests specifically
pytest tests/test_golden_plan.py tests/test_golden_scan.py
```

### Golden Tests

Golden tests ensure that `plan` and `scan` commands produce consistent outputs. These tests compare actual command outputs against stored "golden" fixture files.

**Location:** `tests/golden/`
- `plan/`: Contains `.desc.txt` input files and `.expected.md`/`.expected.json` output files
- `scan/`: Contains `.expected.txt`/`.expected.json` output files for different project configurations

**Updating Golden Files:**

Use the `scripts/regold.py` tool to regenerate expected outputs:

```bash
# Preview changes (dry run)
python scripts/regold.py

# Actually update golden files
python scripts/regold.py --write
```

**Important:** Always review changes carefully before committing updated golden files. The regold tool regenerates outputs based on current implementation, so verify that changes are intentional.

### Project Structure

```
autorepro/
├── autorepro/
│   ├── __init__.py
│   ├── cli.py
│   ├── detect.py
│   ├── env.py
│   └── planner.py
├── tests/
│   ├── test_cli.py
│   ├── test_detect.py
│   ├── test_init.py
│   ├── test_init_diff.py
│   ├── test_plan_cli.py
│   └── test_plan_core.py
└── .github/workflows/ci.yml
```

## Requirements

- Python >= 3.11
- pytest (for development)

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Contributing

This project is in early development. More contribution guidelines will be available as the project evolves.
