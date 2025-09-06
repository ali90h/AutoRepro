# Implementation Plan: Issue #4 - `init` Command

**Issue**: [T-002 — `init`: idempotent + `--force` / `--out`](https://github.com/ali90h/AutoRepro/issues/4)

## Problem Restatement

Implement an `init` command for the AutoRepro CLI that creates a default `devcontainer.json` file with idempotent behavior, force overwrite capability, and custom output path support.

## Goals

1. **Primary**: Create a working `init` command that generates standardized devcontainer configurations
2. **Secondary**: Establish CLI command extension patterns for future MVP commands (`scan`, `plan`)
3. **Quality**: Maintain test coverage and code quality standards

## Scope (Minimal Changes)

### Files to Modify:
- `autorepro/cli.py`: Add subparser for `init` command and implementation
- `tests/test_cli.py`: Add comprehensive test coverage for `init` command

### Files to Create:
- None (keeping minimal - embedded devcontainer template)

## API/CLI Changes

### Command Interface:
```bash
autorepro init [OPTIONS]
```

### Arguments:
- `--force`: Overwrite existing devcontainer.json (default: False)
- `--out PATH`: Custom output path (default: .devcontainer/devcontainer.json)

### Behavior:
- **Default**: Creates `.devcontainer/devcontainer.json` in current directory
- **Idempotent**: Refuses to overwrite existing files without `--force`
- **Path Creation**: Creates parent directories as needed
- **Validation**: Checks write permissions and path validity

### Exit Codes:
- `0`: Success (file created or already exists with same content)
- `1`: File exists and no `--force` flag provided
- `2`: Invalid arguments or path issues
- `3`: Permission denied or filesystem errors

## Acceptance Criteria

1. **Happy Path**: `autorepro init` creates `.devcontainer/devcontainer.json` with default template
2. **Idempotent**: Running twice without `--force` returns exit code 1 with helpful message
3. **Force Overwrite**: `autorepro init --force` overwrites existing file
4. **Custom Path**: `autorepro init --out custom/path.json` creates file at specified location
5. **Directory Creation**: Creates parent directories if they don't exist
6. **Error Handling**: Clear error messages for permission issues, invalid paths
7. **Content Validation**: Generated devcontainer contains Python 3.11, Node 20, Go 1.22

## Test Plan

### Unit Tests (pytest with mocking):
```python
class TestInitCommand:
    def test_init_creates_default_devcontainer(self, tmp_path)
    def test_init_idempotent_behavior_without_force(self, tmp_path)
    def test_init_force_flag_overwrites_existing(self, tmp_path)
    def test_init_custom_output_path(self, tmp_path)
    def test_init_creates_parent_directories(self, tmp_path)
    def test_init_permission_denied_error(self, tmp_path)
    def test_init_invalid_path_error(self, tmp_path)
    def test_init_devcontainer_content_validation(self, tmp_path)
```

### Integration Tests (subprocess):
```python
class TestInitIntegration:
    def test_init_cli_success_via_subprocess(self, tmp_path)
    def test_init_cli_force_flag_via_subprocess(self, tmp_path)
    def test_init_cli_custom_out_via_subprocess(self, tmp_path)
    def test_init_cli_error_handling_via_subprocess(self, tmp_path)
```

### Test Fixtures:
- `tmp_path`: Pytest built-in for isolated filesystem testing
- `expected_devcontainer_content`: JSON template validation

## Implementation Strategy

### Phase 1: Core Command Structure
1. Add subparsers to `create_parser()` in `cli.py`
2. Add `init` subcommand with `--force` and `--out` arguments
3. Create `handle_init()` function with basic file creation logic
4. Update `main()` to route to init handler

### Phase 2: Devcontainer Template
1. Embed JSON template directly in code (minimal approach)
2. Template includes:
   - Python 3.11 feature
   - Node 20 feature
   - Go 1.22 feature
   - Post-creation command for venv setup
   - Appropriate metadata (name: "autorepro-dev")

### Phase 3: Error Handling & Edge Cases
1. File existence checking with appropriate exit codes
2. Parent directory creation with error handling
3. Permission validation
4. Path normalization and validation

### Phase 4: Testing
1. Unit tests with mocked filesystem operations
2. Integration tests with real file operations in tmp_path
3. Error condition testing
4. Content validation tests

## Risks & Open Questions

### Technical Risks:
- **Path Handling**: Cross-platform path handling (Windows vs Unix)
- **Permissions**: Complex permission scenarios in CI environments
- **Template Maintenance**: Keeping devcontainer features current

### Design Questions:
1. **Template Location**: Embed in code vs external file?
   - **Decision**: Embed in code for minimal surface area
2. **Default Path**: `.devcontainer/devcontainer.json` vs `devcontainer.json`?
   - **Decision**: `.devcontainer/devcontainer.json` (standard convention)
3. **Content Updates**: How to handle template changes over time?
   - **Decision**: Version in code, address in future issues

### Mitigation Strategies:
- Use `pathlib.Path` for cross-platform compatibility
- Comprehensive error handling with clear user messages
- Test on both Unix and Windows in CI (future enhancement)

## Low-Risk Quick Wins

None identified - the implementation requires core command structure changes that should be done atomically.

## Next Steps

1. **Implementation**: Follow the 4-phase implementation strategy
2. **Testing**: Ensure 100% test coverage for new functionality
3. **Documentation**: Update CLI help text and README (future task)
4. **CI Validation**: Verify tests pass in GitHub Actions environment

## Estimated Effort

- **Development**: 2-3 hours
- **Testing**: 1-2 hours
- **Integration & Validation**: 30 minutes
- **Total**: ~4-6 hours

This plan prioritizes minimal surface area, reversibility, and maintainability while delivering the full requirements specified in Issue #4.
