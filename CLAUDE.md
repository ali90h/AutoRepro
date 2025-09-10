# AutoRepro Project Context

## Project Overview
AutoRepro is a developer tool that transforms issue descriptions into clear reproducibility steps and shareable workspaces. It automatically detects repository technologies, generates devcontainers, and creates prioritized reproduction plans with explicit assumptions and execution commands.

**Core Mission**: Eliminate the "How do I reproduce this?" problem by automating the path from issue description to failing test and Draft PR.

## Architecture & Technology Stack

### Language & Runtime
- **Python 3.11+** (primary language)
- **CLI Framework**: Click for command-line interface
- **Package Management**: pip with pyproject.toml configuration
- **Testing**: pytest with golden test fixtures

### Project Structure
```
autorepro/
├── autorepro/          # Core package
│   ├── cli.py         # CLI entry points and command routing
│   ├── detect.py      # Language/framework detection logic
│   ├── env.py         # Environment metadata collection
│   ├── planner.py     # Reproduction plan generation
│   └── rules.py       # Command suggestion rules and scoring
├── tests/             # Test suite
│   ├── golden/        # Golden test fixtures
│   │   ├── plan/      # Plan command expected outputs
│   │   └── scan/      # Scan command expected outputs
│   └── test_*.py      # Unit and integration tests
├── scripts/
│   └── regold.py      # Golden test regeneration tool
└── pyproject.toml     # Project configuration
```

## Core Commands & Functionality

### 1. `scan` - Language Detection
- **Purpose**: Detect languages/frameworks from file indicators
- **Key Files**: `autorepro/detect.py`
- **Algorithm**: Weighted scoring (lock files=4, configs=3, setup=2, source=1)
- **Output**: Text or JSON with detected languages and reasons
- **Supported**: Python, Node.js, Go, Rust, Java, C#

### 2. `init` - DevContainer Setup
- **Purpose**: Create standardized development containers
- **Key Files**: `autorepro/cli.py` (init_cmd function)
- **Behavior**: Idempotent, atomic file writes
- **Default Stack**: Python 3.11, Node 20, Go 1.22

### 3. `plan` - Reproduction Planning
- **Purpose**: Generate structured reproduction plans from issue descriptions
- **Key Files**: `autorepro/planner.py`, `autorepro/rules.py`
- **Algorithm**:
  - Keyword extraction (filters stopwords, preserves dev terms)
  - Command scoring (language priors + keyword matches)
  - Plugin system for custom rules
- **Output**: Markdown or JSON with prioritized commands

### 4. `exec` - Command Execution
- **Purpose**: Execute suggested commands with logging
- **Features**: Timeout control, environment variables, JSONL logging
- **Integration**: Works with plan output for automated testing

### 5. `report` - Bundle Generation
- **Purpose**: Create ZIP artifacts for CI/issue tracking
- **Contents**: repro.md, ENV.txt, run.log (if executed), runs.jsonl
- **Use Case**: GitHub Actions, issue documentation

### 6. `pr` - GitHub PR Creation
- **Purpose**: Create Draft PRs from reproduction plans
- **Dependencies**: GitHub CLI (`gh`)
- **Features**: Auto-push, label assignment, update existing PRs

## Key Design Patterns

### Plugin System
- **Environment Variable**: `AUTOREPRO_PLUGINS`
- **Interface**: `provide_rules()` function returning language->rules mapping
- **Example**:
```python
from autorepro.rules import Rule

def provide_rules():
    return {
        "python": [Rule("pytest -k smoke", {"pytest", "smoke"}, 3, {"test"})],
        "node": [Rule("npm run test:unit", {"unit", "test"}, 2, {"test"})]
    }
```

### Command Scoring Algorithm
1. **Base Score**: Language match (2 points) + keyword matches (1 point each)
2. **Bonuses**: Direct command match (+3), specific flags (+1)
3. **Quality Gates**: `--min-score` filters, `--strict` mode fails if no good commands
4. **Plugin Priority**: Plugin commands win ties over built-in commands

### Exit Code Convention
- **0**: Success (including "already exists" scenarios)
- **1**: I/O errors or strict mode failures
- **2**: Misuse (invalid arguments, missing required options)
- **Special**: `exec` and `report --exec` return subprocess exit codes

## Common Development Tasks

### Running Tests
```bash
# All tests
pytest

# Specific test categories
pytest tests/test_golden_plan.py  # Plan golden tests
pytest tests/test_cli.py -k scan   # Scan command tests

# With coverage
pytest --cov=autorepro --cov-report=term-missing
```

### Updating Golden Tests
```bash
# Preview changes
python scripts/regold.py

# Apply updates
python scripts/regold.py --write
```

### Testing Plugin Development
```bash
# Create plugin file
echo 'def provide_rules(): return {"python": []}' > my_plugin.py

# Test with plugin
AUTOREPRO_PLUGINS=my_plugin.py autorepro plan --desc "test issue"

# Debug plugin loading
AUTOREPRO_PLUGINS_DEBUG=1 autorepro plan --desc "test issue"
```

## Important Implementation Details

### File Resolution Logic
- `--file` paths resolve relative to CWD first
- Falls back to `--repo` directory if not found
- Enables flexible issue description file handling

### Idempotent Operations
- `init` won't overwrite without `--force`
- Returns exit code 0 for "already exists"
- Atomic writes using temp file + rename

### Output Flexibility
- `--out -` sends to stdout for piping
- `--dry-run` previews without writing
- JSON format available for programmatic use

### GitHub Integration
- Auto-detects repository from git remotes
- Pushes branch if needed (unless `--skip-push`)
- Structured PR body with top 3 commands

## Current Limitations & Roadmap

### Current MVP Scope
- ✅ Language detection (scan)
- ✅ DevContainer generation (init)
- ✅ Reproduction planning (plan)
- ✅ Command execution (exec)
- ✅ Report bundling (report)
- ✅ Draft PR creation (pr)

### Future Enhancements
- [ ] Automatic failing test generation
- [ ] More language support (Ruby, PHP, etc.)
- [ ] Advanced CI integration
- [ ] Interactive mode for plan refinement
- [ ] Multi-command execution chains

## Key Files to Understand

1. **`autorepro/cli.py`**: Entry point, command routing, argument parsing
2. **`autorepro/planner.py`**: Core planning logic, markdown/JSON generation
3. **`autorepro/rules.py`**: Command database, scoring system
4. **`autorepro/detect.py`**: Language detection patterns and weights
5. **`tests/golden/`**: Expected outputs for regression testing

## Environment Variables

- `AUTOREPRO_PLUGINS`: Comma-separated plugin modules/files
- `AUTOREPRO_PLUGINS_DEBUG`: Show plugin import errors (default: silent)
- Standard git/GitHub environment variables for PR creation

## Quick Command Reference

```bash
# Detect project languages
autorepro scan --json

# Create devcontainer
autorepro init --force

# Generate reproduction plan
autorepro plan --desc "pytest failing" --format json

# Execute top command
autorepro exec --desc "test failures" --timeout 300

# Create report bundle
autorepro report --desc "CI issues" --exec --out report.zip

# Create GitHub PR
autorepro pr --desc "flaky tests" --label bug --assignee maintainer
```

## Testing & CI

### GitHub Actions Workflow
- Python 3.11 on Ubuntu latest
- Runs full test suite on PR/push
- Golden test validation
- Code coverage reporting

### Local Development Setup
```bash
# Clone and setup
git clone https://github.com/ali90h/AutoRepro.git
cd AutoRepro
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install pytest  # For testing

# Verify installation
autorepro --version
autorepro scan
```

## Contributing Guidelines

1. **Code Style**: Follow existing patterns in codebase
2. **Testing**: Add tests for new features, update golden tests if needed
3. **Exit Codes**: Maintain consistent exit code convention
4. **Documentation**: Update README.md and docstrings
5. **Commits**: Clear, descriptive commit messages

## Debugging Tips

- Use `-v` flag for verbose output
- Check `~/.autorepro/` for cached data (if implemented)
- `AUTOREPRO_PLUGINS_DEBUG=1` for plugin issues
- `--dry-run` to preview operations
- `--out -` to inspect outputs without file creation

## Contact & Resources

- **Repository**: https://github.com/ali90h/AutoRepro
- **Author**: Ali Nazzal
- **License**: Apache 2.0
- **Issues**: GitHub Issues for bug reports and features
