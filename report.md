# AutoRepro Project Development Report

## Project Overview
AutoRepro is a developer tools project that transforms issue descriptions into clear reproducibility steps and a shareable framework. The project automatically detects repository technologies, generates ready-made devcontainers, and writes prioritized repro plans.

### MVP Scope
- **scan**: Detect languages/frameworks from file pointers
- **init**: Create an installer devcontainer
- **plan**: Derive execution plan from issue description (no execution)

### Long-term Vision
- Auto-generate failing tests
- Open Draft PRs containing reproducible tests
- Improve contribution quality and maintenance speed on GitHub

## Development Timeline

### Task 0: Project Bootstrap (CLI Skeleton + Tests + CI)
**Status**: ✅ Completed
**Started**: August 15, 2025
**Completed**: August 15, 2025
**PR**: https://github.com/ali90h/AutoRepro/pull/1
**Objective**: Set up complete Python project foundation with CLI interface, testing, and CI/CD

#### Technical Decisions Made:
- **Python Version**: 3.11 (project requirement)
- **CLI Framework**: argparse (standard library, lightweight)
- **Package Structure**: Flat autorepro/ layout
- **Build Tool**: pyproject.toml (modern Python standard)
- **Testing**: pytest with CLI behavior verification
- **CI/CD**: GitHub Actions with Python 3.11 on ubuntu-latest

#### File Structure Created:
```
autorepro/
├── README.md              # Project description and usage
├── LICENSE                # MIT License
├── .gitignore            # Python/venv/OS exclusions
├── pyproject.toml        # Package definition and CLI entry point
├── autorepro/
│   ├── __init__.py       # Package initialization
│   └── cli.py            # Command line interface
├── tests/
│   └── test_cli.py       # CLI behavior tests
└── .github/workflows/
    └── ci.yml            # CI/CD pipeline
```

#### Implementation Progress:
- [x] Project structure planning
- [x] Core files creation
- [x] Local development environment setup
- [x] Testing verification
- [x] CI/CD pipeline setup
- [x] PR creation and review
- [x] Professional code quality improvements
- [x] License standardization (Apache-2.0)
- [x] Version management system
- [x] Code formatting and linting setup
- [x] Comprehensive error handling tests

#### Key Features Implemented:
- **CLI Interface**: Full-featured CLI with proper argument parsing
  - `autorepro --help`: Comprehensive help system
  - `autorepro --version`: Version information display
  - Proper exit code handling (0 for success, 2 for errors)
- **Code Quality**: Professional development standards
  - Black code formatting (88 character line limit)
  - Ruff linting with comprehensive rule set
  - Pre-commit hooks for automated quality checks
- **Testing**: Comprehensive test coverage (12 tests, 100% pass rate)
  - Unit tests for help functionality and exit codes
  - Integration tests using subprocess simulation
  - Error handling tests for unknown options
  - Version flag testing
- **CI/CD**: Production-ready automation
  - GitHub Actions with Python 3.11
  - Pip caching for faster builds
  - Automated code quality checks before testing
  - CLI functionality verification

#### Professional Improvements Made:
1. **License Standardization**: Unified Apache-2.0 across all files
2. **Version Management**: Added `__version__` and `--version` flag
3. **Code Quality**: Implemented ruff + black with pre-commit hooks
4. **Enhanced Testing**: Added error behavior tests (exit code 2)
5. **Modern CI**: Updated to actions/setup-python@v5 with pip cache
6. **Terminology Consistency**: Fixed devcontainer references
7. **Metadata Completeness**: Full pyproject.toml with classifiers

#### Current CLI Output:
```
usage: autorepro [-h] [--version]

CLI for AutoRepro - transforms issues into repro steps

options:
  -h, --help  show this help message and exit
  --version   show program's version number and exit

AutoRepro automatically detects repository technologies, generates ready-made
devcontainers, and writes prioritized repro plans with explicit assumptions.

MVP commands (coming soon):
  scan    Detect languages/frameworks from file pointers
  init    Create a developer container
  plan    Derive execution plan from issue description

For more information, visit: https://github.com/ali90h/AutoRepro
```

#### Test Results:
```
============================== test session starts ==============================
platform darwin -- Python 3.11.13, pytest-8.4.1, pluggy-1.6.0
rootdir: /Users/ali/autorepro
configfile: pyproject.toml
testpaths: tests
collected 12 items

tests/test_cli.py ............                                           [100%]

============================== 12 passed in 0.35s ==============================
```

---

## Development Notes

### Design Philosophy:
- **Simplicity**: Start with minimal viable implementation
- **Transparency**: Clear command outputs and error messages
- **Automation**: Reduce manual reproduction steps
- **Extensibility**: Architecture supports future MVP commands

### Code Quality Standards:
- Modern Python packaging (pyproject.toml)
- Comprehensive testing coverage
- CI/CD automation
- Proper git workflow with PR reviews

---

### Pre-commit Installation Issue Resolution (August 16, 2025)
**Status**: ✅ Completed
**Issue**: Pre-commit hooks installation failure and code formatting conflicts

#### Problems Identified:
1. **Git hooks path conflict**: Global `core.hooksPath` setting prevented pre-commit installation
2. **Line length mismatch**: Black/Ruff used 100 chars, flake8 defaulted to 79 chars

#### Resolution:
1. **Removed global git hooks path**: `git config --global --unset-all core.hooksPath`
2. **Created `.flake8` configuration**: Set max-line-length to 100 to match other tools
3. **Successfully installed pre-commit hooks**: All tools now pass validation

#### Technical Details:
- Flake8 doesn't support pyproject.toml natively, requiring separate `.flake8` config
- Unified 100-character line length across all formatting tools (black, ruff, flake8)
- Pre-commit hooks now active for automatic code quality enforcement

#### Current Tool Configuration:
- **Black**: 100 chars (pyproject.toml)
- **Ruff**: 100 chars (pyproject.toml)
- **Flake8**: 100 chars (.flake8 file)
- **Pre-commit**: Installed and functional

---

### CI Pre-commit Hook Failure Analysis (August 16, 2025)
**Status**: 🔧 Patch Proposed
**Issue**: GitHub Actions CI failing due to yanked `types-pkg-resources` dependency in mypy hook

#### Root Cause Analysis:
The mypy pre-commit hook was configured with `additional_dependencies: [types-all]`, which depends on `types-pkg-resources`. This package was yanked from PyPI in August 2024 with the message "Use types-setuptools instead," causing installation failures during hook environment setup.

#### Error Details:
```
ERROR: Could not find a version that satisfies the requirement types-pkg-resources (from types-all)
ERROR: No matching distribution found for types-pkg-resources
```

#### Investigation Findings:
1. **Yanked Package**: `types-pkg-resources` was removed from PyPI as part of setuptools integration improvements
2. **Project Scope**: AutoRepro is a simple CLI tool using only standard library modules (argparse, sys)
3. **Unnecessary Dependency**: `types-all` provides external type stubs not needed for this project
4. **Missing CI Step**: Pre-commit hooks weren't validated in CI workflow

#### Proposed Solution (Minimal Patch):
```diff
# Remove problematic dependency from .pre-commit-config.yaml
- additional_dependencies: [types-all]

# Add pre-commit validation to CI workflow
+ - name: Run pre-commit hooks
+   run: |
+     pre-commit run --all-files
```

#### Rationale:
- **Minimal & Reversible**: Simple removal rather than complex dependency replacement
- **Sufficient Scope**: Standard library type checking doesn't require external type stubs
- **Preventive**: CI integration catches similar issues early
- **Maintains Quality**: mypy still provides valuable type checking without external stubs

#### Technical Context:
- `pkg_resources` types are now included in setuptools directly (≥71.1)
- Modern Python projects migrate from `pkg_resources` to `importlib.resources/metadata`
- `types-all` was a transitional package that's no longer necessary for simple projects

#### Patch Applied (August 16, 2025):
**Files Modified**:
- `.pre-commit-config.yaml`: Removed `additional_dependencies: [types-all]` from mypy hook
- `.github/workflows/ci.yml`: Added pre-commit validation step after dependency installation

**Summary**: Applied minimal fix to resolve yanked dependency issue while maintaining type checking capabilities. The removed `types-all` dependency was unnecessary for this standard library CLI project.

**Rationale**: Eliminates CI failure root cause without complex replacements, adds preventive CI validation, and maintains code quality standards. Solution is reversible if future type stub requirements emerge.

---

### Scan Command Implementation (August 16, 2025)
**Status**: 🔧 Patch Proposed
**Feature**: Implement `autorepro scan` command with detection reasons

#### Implementation Overview:
Created a complete language detection system that identifies technologies based on file patterns and provides explicit reasons for each detection.

#### New Files Created:
- **`autorepro/detect.py`**: Core detection logic with `detect_languages()` API
- **`tests/test_detect.py`**: Comprehensive tests for detection logic (10 test cases)
- **`tests/test_scan_cli.py`**: CLI integration tests (6 test cases)

#### Modified Files:
- **`autorepro/cli.py`**: Added subcommand support and `scan` command implementation
- **`README.md`**: Updated with scan command documentation and examples

#### API Design:
```python
def detect_languages(path: str) -> List[Tuple[str, List[str]]]
```
- **Pure function**: No side effects, returns structured data
- **Deterministic ordering**: Languages and reasons sorted alphabetically
- **Root-only scanning**: Non-recursive directory scanning
- **Mixed pattern support**: Both exact filenames and glob patterns

#### Supported Languages:
- **Python**: `pyproject.toml`, `setup.py`, `requirements.txt`, `*.py`
- **Node.js**: `package.json`, `yarn.lock`, `pnpm-lock.yaml`, `npm-shrinkwrap.json`
- **Go**: `go.mod`, `go.sum`, `*.go`
- **Rust**: `Cargo.toml`, `Cargo.lock`, `*.rs`
- **Java**: `pom.xml`, `build.gradle`, `*.java`
- **C#**: `*.csproj`, `*.sln`, `*.cs`

#### CLI Output Format:
```bash
$ autorepro scan
Detected: node, python
- node  -> package.json, pnpm-lock.yaml
- python  -> pyproject.toml, requirements.txt
```

#### Technical Decisions:
- **Alphabetical ordering**: Ensures deterministic, predictable output
- **Exact vs glob patterns**: Handles both `pyproject.toml` (exact) and `*.py` (glob) patterns
- **Basename collection**: For globs, collects actual matched filenames, not patterns
- **Pure function design**: Detection logic is testable and reusable
- **Comprehensive testing**: 16 total test cases covering edge cases and CLI integration

#### Branch Strategy:
- **Target branch**: `feat/scan-reasons`
- **Feature scope**: Complete scan command implementation
- **Testing coverage**: Unit tests for detection logic + CLI integration tests

---

*This report is updated after each major development milestone.*

---

### File Organization Notes
**Note**: The original `pr.md` file containing the PR description has been relocated to the project root for better GitHub integration and visibility during pull request workflows.
