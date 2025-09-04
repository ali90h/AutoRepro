# 📄 Section A - Technique 2: Remove Duplication

> Code Cleanup: Eliminate duplicate code patterns while maintaining AutoRepro's exact behavior
>

---

## 🎯 **TECHNIQUE 2: Remove Duplication** 🗑️

**Duration**: 3-4 days

**Priority**: High | **Risk**: Medium | **Impact**: High

### **Core Strategy**

Identify and eliminate duplicate code blocks by extracting reusable utilities, following the DRY (Don't Repeat Yourself) principle. Every extraction must preserve existing behavior exactly.

---

## **Phase 1: Duplication Discovery** (Day 1)

### **Target Duplication Areas in AutoRepro**

Based on the CLI tool architecture, expected duplicate patterns:

**🚨 HIGH PRIORITY (Core Logic Duplication)**:

- **CLI Argument Validation**: `-desc`/`-file` mutual exclusion logic
- **File I/O Operations**: Directory creation, atomic file writing
- **Process Execution**: `subprocess.run` with timeout handling
- **Error Handling**: Try/catch patterns around operations

**⚠️ MEDIUM PRIORITY (Utility Duplication)**:

- **JSON Operations**: Loading/saving JSON with error handling
- **Path Resolution**: Converting string paths to Path objects
- **Output Formatting**: Consistent formatting patterns

**📝 LOW PRIORITY (Display Duplication)**:

- **Progress Messages**: Similar status/progress outputs
- **Help Text Patterns**: Repeated CLI help formatting

### **Automated Detection Method**

```bash
# Find potential duplication patterns
mkdir -p analysis/duplication

# CLI validation patterns
echo "=== CLI VALIDATION PATTERNS ===" > analysis/duplication/findings.txt
grep -rn -A5 "if not.*desc.*and not.*file" autorepro/ >> analysis/duplication/findings.txt
grep -rn -A3 "args\.out.*and.*Path" autorepro/ >> analysis/duplication/findings.txt

# File I/O patterns
echo -e "\n=== FILE I/O PATTERNS ===" >> analysis/duplication/findings.txt
grep -rn -A5 "Path.*mkdir" autorepro/ >> analysis/duplication/findings.txt
grep -rn -A5 "open.*w.*" autorepro/ >> analysis/duplication/findings.txt

# Process execution patterns
echo -e "\n=== PROCESS EXECUTION ===" >> analysis/duplication/findings.txt
grep -rn -A8 "subprocess\.run" autorepro/ >> analysis/duplication/findings.txt

# Error handling patterns
echo -e "\n=== ERROR HANDLING ===" >> analysis/duplication/findings.txt
grep -rn -A5 "except.*Error" autorepro/ >> analysis/duplication/findings.txt
grep -rn -A3 "try:" autorepro/ >> analysis/duplication/findings.txt

```

### **Expected Findings**

**Estimated Duplications**:

- CLI validation logic: **5 locations** (plan, report, exec, pr commands)
- File operations: **8 locations** (atomic writes, directory creation)
- Process execution: **6 locations** (subprocess calls with timeout)
- JSON operations: **4 locations** (safe read/write patterns)
- Error handling: **10+ locations** (similar try/catch blocks)

**Total Expected**: 30+ duplicate code blocks

---

## **Phase 2: Extract Utility Functions** (Days 2-3)

### **Strategy: Create Focused Utility Modules**

Create specialized utility modules without changing existing code initially, then migrate incrementally.

### **Utility Module 1: CLI Validation**

**Target**: Eliminate repeated CLI argument validation

```python
# autorepro/utils/cli_validation.py - Core idea
class ArgumentValidator:
    @staticmethod
    def validate_desc_file_args(args) -> Optional[str]:
        """Validate mutually exclusive --desc/--file arguments.
        Returns error message if invalid, None if valid."""
        if not args.desc and not args.file:
            return "Error: Must provide --desc or --file"
        if args.desc and args.file:
            return "Error: Cannot use both --desc and --file"
        return None

    @staticmethod
    def validate_output_path(args) -> Optional[str]:
        """Validate output path is not a directory."""
        if args.out and Path(args.out).is_dir():
            return f"Error: Output path cannot be a directory: {args.out}"
        return None

```

**Usage Pattern**:

```python
# Before (repeated in multiple commands)
def plan_command(args):
    if not args.desc and not args.file:
        print("Error: Must provide --desc or --file")
        return 2
    if args.desc and args.file:
        print("Error: Cannot use both --desc and --file")
        return 2
    # ... rest of logic

# After (single line replacement)
def plan_command(args):
    if error := ArgumentValidator.validate_desc_file_args(args):
        print(error)
        return 2
    # ... rest of logic unchanged

```

### **Utility Module 2: File Operations**

**Target**: Consistent file I/O with error handling

```python
# autorepro/utils/file_ops.py - Core idea
class FileOperations:
    @staticmethod
    def ensure_directory(path: Path) -> None:
        """Ensure directory exists, create with parents if needed."""
        path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def atomic_write(path: Path, content: str) -> None:
        """Atomic file write using temp file + rename."""
        # Implementation ensures file is either fully written or unchanged
        pass

    @staticmethod
    def safe_read_json(path: Path, default=None) -> dict:
        """Read JSON file with fallback on error."""
        try:
            return json.loads(path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return default or {}

```

### **Utility Module 3: Process Execution**

**Target**: Consistent subprocess handling

```python
# autorepro/utils/process.py - Core idea
class ProcessRunner:
    @staticmethod
    def run_with_timeout(cmd: List[str], timeout: int = None) -> Tuple[int, str, str]:
        """Run command with consistent timeout and error handling.
        Returns (exit_code, stdout, stderr)."""
        try:
            result = subprocess.run(
                cmd, timeout=timeout, capture_output=True, text=True
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 124, "", f"Command timed out after {timeout} seconds"
        except Exception as e:
            return 1, "", str(e)

```

---

## **Phase 3: Incremental Migration** (Day 3-4)

### **Migration Strategy: One Module at a Time**

### **Step 1: Create and Test Utilities** (Day 3 Morning)

1. **Implement utility modules** with comprehensive unit tests
2. **Test utilities independently** - no existing code changes yet
3. **Validate utility behavior** matches expected patterns

### **Step 2: Replace Usage Incrementally** (Day 3 Afternoon - Day 4)

1. **One file at a time**: Replace duplicate patterns in single files
2. **Validate after each file**: All tests must pass
3. **Compare behavior**: CLI outputs must remain identical

### **Replacement Validation Protocol**

**Before Each Replacement**:

```bash
# Create baseline for the specific file being changed
autorepro plan --desc "test" --dry-run > baseline_plan_before.txt
pytest tests/test_cli.py::test_plan_command -v

```

**After Each Replacement**:

```bash
# Validate identical behavior
autorepro plan --desc "test" --dry-run > baseline_plan_after.txt
diff baseline_plan_before.txt baseline_plan_after.txt || echo "ALERT: Behavior changed"
pytest tests/test_cli.py::test_plan_command -v

```

### **High-Risk Replacement Areas**

1. **CLI Command Functions** (`cli.py`)
    - Risk: Changing argument validation behavior
    - Mitigation: Test all command variations before/after
2. **File Writing Operations** (multiple files)
    - Risk: Atomic write behavior differences
    - Mitigation: Test file creation, overwrite, and error scenarios
3. **Process Execution** (exec, report commands)
    - Risk: Different timeout or error handling
    - Mitigation: Test command execution with various scenarios

---

## **Testing Strategy - Duplication Removal**

### **Unit Tests for New Utilities**

```python
# tests/utils/test_cli_validation.py
class TestArgumentValidator:
    def test_valid_desc_only(self):
        args = Mock(desc="test", file=None)
        assert ArgumentValidator.validate_desc_file_args(args) is None

    def test_valid_file_only(self):
        args = Mock(desc=None, file="test.txt")
        assert ArgumentValidator.validate_desc_file_args(args) is None

    def test_missing_both(self):
        args = Mock(desc=None, file=None)
        error = ArgumentValidator.validate_desc_file_args(args)
        assert "Must provide --desc or --file" in error

    def test_both_provided(self):
        args = Mock(desc="test", file="test.txt")
        error = ArgumentValidator.validate_desc_file_args(args)
        assert "Cannot use both --desc and --file" in error

```

### **Integration Tests for Replaced Code**

```python
# tests/integration/test_duplication_removal.py
class TestDuplicationRemoval:
    def test_cli_commands_unchanged_behavior(self):
        """All CLI commands must behave identically after utility extraction."""
        test_scenarios = [
            # Test plan command with various argument combinations
            (["plan", "--desc", "test", "--dry-run"], 0),
            (["plan", "--desc", "test", "--file", "issue.txt"], 2),  # Should fail
            (["plan"], 2),  # Should fail - missing required args

            # Test other commands
            (["scan", "--json"], 0),
            (["init", "--dry-run"], 0),
        ]

        for cmd_args, expected_code in test_scenarios:
            result = subprocess.run(
                ["autorepro"] + cmd_args,
                capture_output=True, text=True
            )
            assert result.returncode == expected_code

    def test_file_operations_identical(self):
        """File operations must produce identical results."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Test devcontainer creation
            result1 = autorepro_init(tmp_dir, dry_run=False)
            result2 = autorepro_init(tmp_dir, dry_run=False)  # Should be idempotent

            # Files should be identical
            assert result1 == result2

    def test_error_messages_unchanged(self):
        """Error messages must remain exactly the same."""
        # Test invalid argument combinations
        result = subprocess.run(
            ["autorepro", "plan", "--desc", "test", "--file", "test.txt"],
            capture_output=True, text=True
        )
        assert "Cannot use both --desc and --file" in result.stderr

```

### **Performance Impact Testing**

```python
def test_utility_extraction_performance():
    """Utility extraction should not impact performance."""
    import time

    operations = [
        lambda: autorepro_scan(),
        lambda: autorepro_plan("test issue", dry_run=True),
        lambda: autorepro_init(dry_run=True)
    ]

    for operation in operations:
        # Measure performance multiple times
        times = []
        for _ in range(5):
            start = time.time()
            operation()
            times.append(time.time() - start)

        avg_time = sum(times) / len(times)
        baseline_time = get_baseline_performance(operation)

        # Should be within 10% of baseline
        assert avg_time <= baseline_time * 1.1

```

---

## **Risk Mitigation**

### **Critical Duplication Areas**

1. **CLI Validation Logic**
    - Risk: Different validation behavior breaks user experience
    - Mitigation: Exact string matching for error messages
2. **File I/O Patterns**
    - Risk: Atomic write implementation differences
    - Mitigation: Test file corruption scenarios, concurrent access
3. **Process Execution**
    - Risk: Timeout handling or exit code differences
    - Mitigation: Test various command execution scenarios

### **Safety Measures**

```bash
# Create safety branches for each utility extraction
git checkout -b extract-cli-validation
git checkout -b extract-file-operations
git checkout -b extract-process-execution

# Test each extraction independently
pytest tests/utils/ -v                    # Unit tests for utilities
pytest tests/integration/ -v              # Integration tests
pytest tests/test_cli.py -v              # Existing CLI tests

```

### **Rollback Criteria**

- Any test failures after utility replacement
- Performance degradation > 10%
- Changed CLI output or behavior
- User-visible error message changes

---

## **Success Criteria**

### **Functional Requirements**

- [ ]  Zero behavioral changes in CLI commands
- [ ]  All existing tests pass without modification
- [ ]  Error messages remain identical
- [ ]  File operations produce same results

### **Technical Requirements**

- [ ]  30+ duplicate code blocks eliminated
- [ ]  3+ reusable utility modules created
- [ ]  Code duplication reduced by >60%
- [ ]  Comprehensive unit tests for all utilities

### **Quality Requirements**

- [ ]  Utilities are well-documented and testable
- [ ]  Clear separation of concerns in utility modules
- [ ]  Consistent error handling patterns
- [ ]  Performance maintained within 10% of baseline

---

## **Deliverables**

1. **Utility Modules** (`autorepro/utils/`)
    - CLI validation utilities
    - File operation utilities
    - Process execution utilities
    - JSON handling utilities
2. **Refactored Core Code**
    - Duplicate patterns replaced with utility calls
    - Consistent error handling
    - Preserved interfaces and behavior
3. **Enhanced Test Suite**
    - Unit tests for all utility functions
    - Integration tests for refactored code
    - Performance regression tests
4. **Documentation**
    - Utility function reference
    - Best practices for using utilities
    - Refactoring notes and patterns

**Final Result**: A DRY codebase with reusable utilities that maintains identical behavior while being more maintainable and testable.
