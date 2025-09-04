# AutoRepro GitHub Copilot Instructions

**ALWAYS follow these instructions first** and only fallback to additional search and context gathering if the information in these instructions is incomplete or found to be in error.

AutoRepro is a Python CLI tool that transforms issue descriptions into clear reproducibility steps and shareable development environments. It automatically detects repository technologies, generates devcontainers, and writes prioritized reproduction plans.

## Core Development Setup

### Bootstrap Environment
```bash
# Create and activate Python virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install package in editable mode with development dependencies
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```
**Timing**: Installation takes ~15 seconds. NEVER CANCEL this process.
**Network Issues**: If pip install fails with timeouts, this is common in CI environments. The code should still work with existing installations.

### Essential Commands Overview
AutoRepro provides 5 core commands:
- `autorepro scan`: Detect languages/frameworks in repository
- `autorepro init`: Create devcontainer.json configuration
- `autorepro plan`: Generate reproduction plan from issue description
- `autorepro exec`: Execute the top suggested command from a plan
- `autorepro pr`: Create GitHub Draft PR from reproduction plan

## Build and Test

### Running Tests
```bash
# Run full test suite (383 tests)
pytest
# OR with verbose output
pytest -v
```
**Timing**: Tests take ~14 seconds. NEVER CANCEL. Set timeout to 30+ minutes for safety.

### Linting and Formatting
```bash
# Run linting (fast)
ruff check .

# Check code formatting
black --check .

# Format code
black .

# Run ruff with auto-fix
ruff check . --fix
```
**Timing**: Linting takes <1 second. Formatting takes ~1 second.

### Pre-commit Hooks
```bash
# Install pre-commit hooks (first time only)
pre-commit install

# Run all pre-commit hooks
pre-commit run --all-files
```
**Note**: Pre-commit setup may timeout due to network issues in CI environments. This is expected and not a blocker for development.

## Validation Scenarios

### CRITICAL: Always Test These Scenarios After Changes

1. **Basic CLI Functionality**:
   ```bash
   autorepro --help
   autorepro --version
   autorepro scan
   ```

2. **Plan Generation Workflow**:
   ```bash
   # Test plan generation
   autorepro plan --desc "pytest tests failing" --dry-run

   # Test with file input
   echo "npm test issues" > test_issue.txt
   autorepro plan --file test_issue.txt --dry-run
   rm test_issue.txt
   ```

3. **Language Detection**:
   ```bash
   # Test scanning in current repo (should detect Python)
   autorepro scan

   # Test JSON output format
   autorepro scan --json
   ```

4. **Devcontainer Generation**:
   ```bash
   # Test devcontainer creation without writing files
   autorepro init --dry-run
   ```

5. **Execution Workflow**:
   ```bash
   # Test command selection without execution
   autorepro exec --desc "python version check" --dry-run
   ```

### End-to-End Validation
After making changes, ALWAYS run this complete validation:
```bash
# 1. Install and test CLI
python -m pip install -e ".[dev]"
autorepro --version

# 2. Run tests
pytest

# 3. Lint code
ruff check .
black --check .

# 4. Test core functionality
autorepro scan
autorepro plan --desc "test issue" --dry-run
autorepro init --dry-run
```

### Manual User Workflow Testing
Test these complete scenarios that a real user would perform:

**Scenario 1: Python Developer New to Repo**
```bash
# Simulate discovering a Python project
autorepro scan
autorepro init --dry-run
autorepro plan --desc "pytest tests are failing with ImportError" --out repro.md
cat repro.md  # Verify output format and content
rm repro.md
```

**Scenario 2: Node.js Issue Investigation**
```bash
# Test detection in mixed environment
echo '{"name": "test"}' > package.json
autorepro scan  # Should detect both python and node
autorepro plan --desc "npm test failing on CI" --dry-run
rm package.json
```

**Scenario 3: Command Execution Workflow**
```bash
# Test command selection and execution preview
autorepro exec --desc "build failures" --dry-run
autorepro exec --desc "linting errors" --index 1 --dry-run  # Test second command
```

## Development Workflow

### Making Changes
1. **Create feature branch**: Work on focused changes
2. **Install in development mode**: `python -m pip install -e ".[dev]"`
3. **Run tests frequently**: `pytest` after each significant change
4. **Validate CLI**: Test commands with `--dry-run` first
5. **Check formatting**: `black --check .` and `ruff check .`
6. **Golden test updates**: Use `python scripts/regold.py --write` if output formats change

### Testing Different Scenarios
```bash
# Test in external directory
cd /tmp && mkdir test_project && cd test_project
echo "print('hello')" > test.py
/path/to/autorepro/.venv/bin/autorepro scan
/path/to/autorepro/.venv/bin/autorepro plan --desc "python issues" --dry-run
```

### Plugin Development
AutoRepro supports plugins via `AUTOREPRO_PLUGINS` environment variable:
```bash
# Test with custom plugin
AUTOREPRO_PLUGINS="demo_plugin.py" autorepro plan --desc "custom test"
```

## Important Project Files

### Core Implementation
- `autorepro/cli.py`: Main CLI interface and command handling
- `autorepro/detect.py`: Language/framework detection logic
- `autorepro/planner.py`: Reproduction plan generation
- `autorepro/rules.py`: Command suggestion rules

### Configuration Files
- `pyproject.toml`: Package configuration, dependencies, tool settings
- `.github/workflows/ci.yml`: CI pipeline with quality checks
- `.pre-commit-config.yaml`: Pre-commit hooks configuration
- `.devcontainer/devcontainer.json`: Development container setup

### Testing
- `tests/`: All test modules
- `tests/golden/`: Golden test fixtures for consistent output validation
- `scripts/regold.py`: Tool to regenerate golden test files

## Common Commands Reference

### CLI Usage Patterns
```bash
# Generate markdown plan
autorepro plan --desc "issue description" --out repro.md

# Generate JSON plan
autorepro plan --desc "issue description" --format json --out repro.json

# Execute with timeout and logging
autorepro exec --desc "build issues" --timeout 60 --jsonl exec.log

# Create PR (requires GitHub CLI)
autorepro pr --desc "test failing" --dry-run
```

### Quality Checks (Mirror CI Pipeline)
```bash
# Run full quality pipeline
pytest --cov=autorepro --cov-branch
ruff check .
black --check .
autorepro --help && autorepro --version
python scripts/regold.py --write && git diff --exit-code
```

## Troubleshooting

### Common Issues
1. **Command timeouts**: Default timeout is 120 seconds. Increase with `--timeout N`
2. **No commands found**: Use `--min-score 1` to see lower-scored suggestions
3. **File not found**: Check that `--file` paths are relative to current directory
4. **GitHub CLI missing**: Install `gh` for `autorepro pr` functionality
5. **Network timeouts during install**: Common in CI environments, retry or use existing installation

### Development Environment Issues
- **Python version**: Requires Python 3.11+ (currently tested with 3.12.3)
- **Virtual environment**: Always use `.venv` to isolate dependencies
- **Import errors**: Reinstall with `python -m pip install -e ".[dev]"`
- **Test failures**: Run `pytest -v` to see detailed output
- **Plugin errors**: Use `AUTOREPRO_PLUGINS_DEBUG=1` to see plugin import failures

### Debugging Command Suggestions
```bash
# See how commands are scored
autorepro plan --desc "your issue" --format json --out -

# Test with lower score threshold
autorepro plan --desc "your issue" --min-score 1 --dry-run

# Check language detection first
autorepro scan --json
```

## Timing Expectations

**NEVER CANCEL these operations** - they are expected to take time:
- **Package installation**: ~15 seconds (set timeout: 300+ seconds)
- **Full test suite**: ~14 seconds (set timeout: 1800+ seconds for safety)
- **Linting**: <1 second
- **Pre-commit setup**: May timeout due to network, this is normal
- **Golden test regeneration**: ~5 seconds

## Repository Structure Quick Reference

```
autorepro/
├── autorepro/          # Main package code
│   ├── cli.py         # CLI entry point and commands
│   ├── detect.py      # Language detection
│   ├── planner.py     # Plan generation
│   └── rules.py       # Command rules
├── tests/             # Test suite (383 tests)
│   ├── golden/        # Golden test fixtures
│   └── test_*.py      # Test modules
├── scripts/           # Development tools
│   └── regold.py      # Regenerate golden files
├── .github/workflows/ # CI pipeline
└── pyproject.toml     # Package configuration
```

Always validate your changes thoroughly using the scenarios above before committing.
