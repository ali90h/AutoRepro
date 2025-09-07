# Issue #85 Implementation Plan: Configuration Validation Methods

## Overview
Add comprehensive validation methods to configuration dataclasses to improve error handling, provide better user feedback, and catch configuration errors early before expensive operations.

## 1. Specific Files to Modify

**Core Files:**
- `autorepro/cli.py` - Add validation methods to `PrConfig`, `ExecConfig`, `InitConfig`, `PlanConfig`
- `autorepro/io/github.py` - Add validation methods to `GitHubPRConfig`, `IssueConfig`
- `autorepro/config/exceptions.py` - **NEW FILE** - Custom validation exceptions
- `tests/test_config_validation.py` - **NEW FILE** - Comprehensive validation tests

**Integration Files:**
- `autorepro/cli.py` - Update config instantiation to call validation
- `autorepro/io/github.py` - Update config usage to validate

## 2. Specific Code Changes

### A. Custom Exception Classes (NEW FILE)
Create `autorepro/config/exceptions.py`:
```python
class ConfigValidationError(ValueError):
    """Base class for configuration validation errors."""
    pass

class FieldValidationError(ConfigValidationError):
    """Individual field validation error."""
    pass

class CrossFieldValidationError(ConfigValidationError):
    """Cross-field validation error."""
    pass
```

### B. Add Validation Methods to Configuration Classes

**PrConfig validation:**
- Validate `desc` XOR `file` requirement
- Validate `repo_slug` format if provided
- Validate `min_score` range (>= 0)
- Validate `format_type` in allowed values
- Cross-validate enrichment flags compatibility

**GitHubPRConfig validation:**
- Validate `title` not empty
- Validate `base_branch` and `head_branch` format
- Validate `labels`/`assignees` format
- Validate `gh_path` executable exists

**ExecConfig validation:**
- Validate `desc` XOR `file` requirement
- Validate `timeout` > 0
- Validate `index` >= 0
- Validate file paths exist if provided

## 3. Complete Code Snippets

### Custom Exceptions:
```python
"""Configuration validation exceptions."""

class ConfigValidationError(ValueError):
    """Base class for configuration validation errors."""

    def __init__(self, message: str, field: str | None = None):
        self.field = field
        super().__init__(message)

class FieldValidationError(ConfigValidationError):
    """Individual field validation error."""
    pass

class CrossFieldValidationError(ConfigValidationError):
    """Cross-field validation error."""
    pass
```

### PrConfig Validation:
```python
def validate(self) -> None:
    """Validate PR configuration and raise descriptive errors."""
    # Mutual exclusivity validation
    if self.desc and self.file:
        raise CrossFieldValidationError(
            "Cannot specify both --desc and --file", field="desc,file"
        )

    if not self.desc and not self.file:
        raise CrossFieldValidationError(
            "Must specify either --desc or --file", field="desc,file"
        )

    # Field validation
    if self.min_score < 0:
        raise FieldValidationError(
            f"min_score must be non-negative, got: {self.min_score}",
            field="min_score"
        )

    if self.format_type not in ("md", "json"):
        raise FieldValidationError(
            f"format_type must be 'md' or 'json', got: {self.format_type}",
            field="format_type"
        )

    # Repo slug format validation
    if self.repo_slug and not re.match(r'^[^/]+/[^/]+$', self.repo_slug):
        raise FieldValidationError(
            f"repo_slug must be in format 'owner/repo', got: {self.repo_slug}",
            field="repo_slug"
        )
```

## 4. Step-by-step Implementation

1. **Create custom exceptions** - New `exceptions.py` with validation error classes
2. **Add validation methods** - Implement `validate()` for each config class
3. **Update instantiation points** - Call `validate()` after config creation
4. **Replace existing validation** - Refactor `_prepare_plan_config()` to use new system
5. **Add comprehensive tests** - Test all validation scenarios and error messages
6. **Update error handling** - Ensure validation errors are caught and reported properly

## 5. Testing Validation Plan

**Test Categories:**
- **Field validation**: Test each field's constraints individually
- **Cross-field validation**: Test mutual exclusivity and dependencies
- **Error message quality**: Verify helpful, specific error messages
- **Integration testing**: Test validation at config instantiation points
- **Backward compatibility**: Ensure existing valid configs still work

**Test Commands:**
```bash
# Run validation tests
pytest tests/test_config_validation.py -v

# Test integration
pytest tests/test_cli.py -k "config" -v

# Full regression test
pytest tests/ -q
```

The implementation provides proactive error detection with clear, actionable error messages while maintaining full backward compatibility.
