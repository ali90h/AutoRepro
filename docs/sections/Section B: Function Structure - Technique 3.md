# 📄 Section B: Function Structure - Technique 3

> Architectural Transformation: Break down large functions into focused, single-purpose components while preserving exact behavior
>

---

## 🎯 **TECHNIQUE 3: Split Large Functions** ✂️

**Duration**: 1.5 weeks

**Priority**: High | **Risk**: High | **Impact**: Very High

### **Core Strategy**

Decompose large, complex functions into smaller, focused functions following the Single Responsibility Principle. Each split must maintain identical external behavior and pass all existing tests.

---

## **Phase 1: Function Analysis & Prioritization** (Days 1-2)

### **Identify Large Functions in AutoRepro**

**Expected target functions** (based on CLI tool architecture):

**🚨 CRITICAL PRIORITY (>60 lines, CC >10)**:

- **`plan_command()`** in `cli.py` (~80 lines, CC ~15)
    - Responsibilities: validation, language detection, plan generation, output
- **`generate_plan()`** in `planner.py` (~70 lines, CC ~12)
    - Responsibilities: keyword extraction, command scoring, formatting
- **`detect_languages()`** in `detect.py` (~65 lines, CC ~10)
    - Responsibilities: file scanning, pattern matching, scoring

**⚠️ HIGH PRIORITY (>50 lines, CC >8)**:

- **`report_command()`** in `cli.py` (~55 lines, CC ~9)
- **`exec_command()`** in `cli.py` (~52 lines, CC ~8)
- **`create_devcontainer()`** in init logic (~48 lines, CC ~7)

### **Analysis Method**

```bash
# Find functions exceeding complexity/length thresholds
mkdir -p analysis/large_functions

# Complexity analysis
radon cc autorepro/ -s -n C > analysis/large_functions/high_complexity.txt
radon cc autorepro/ -a --total-average > analysis/large_functions/detailed_complexity.txt

# Length analysis
radon raw autorepro/ -s | grep -E "LOC: [5-9][0-9]|LOC: [0-9]{3}" > analysis/large_functions/long_functions.txt

# Function responsibility analysis (manual)
grep -rn "^def " autorepro/ > analysis/large_functions/all_functions.txt

```

### **Expected Findings**

- **Functions >50 lines**: 8-10 functions
- **Functions >60 lines**: 4-5 functions
- **High complexity (CC >10)**: 3-4 functions
- **Multiple responsibilities**: 6-8 functions

**Splitting Impact**: Reduce average function length from ~35 lines to ~20 lines, complexity from B-grade to A-grade.

---

## **Phase 2: Function Decomposition Strategy** (Days 3-8)

### **Decomposition Principles**

1. **Single Responsibility**: Each new function has one clear purpose
2. **Clear Interfaces**: Well-defined input/output with type hints
3. **Testability**: Each function can be unit tested independently
4. **Identical Behavior**: External function behavior remains unchanged
5. **Error Boundaries**: Consistent error handling at appropriate levels

### **Target 1: Split `plan_command()` Function** (Days 3-4)

**Current Structure Analysis**:

```python
def plan_command(args):
    # Lines 1-15: Argument validation
    # Lines 16-25: Repository path resolution
    # Lines 26-35: Language detection
    # Lines 36-45: Issue description processing
    # Lines 46-60: Plan generation
    # Lines 61-70: Output formatting
    # Lines 71-80: File writing and error handling

```

**Decomposition Strategy**:

```python
# After splitting - preserve exact external interface
def plan_command(args):
    """Main plan command entry point - behavior unchanged."""
    try:
        config = _prepare_plan_config(args)
        plan_data = _generate_plan_content(config)
        return _output_plan_result(plan_data, config)
    except PlanError as e:
        print(f"Error: {e}")
        return 1

def _prepare_plan_config(args) -> PlanConfig:
    """Extract and validate plan configuration from arguments."""
    # Lines 1-25 of original function
    # Returns structured config object

def _generate_plan_content(config: PlanConfig) -> PlanData:
    """Generate the actual reproduction plan."""
    # Lines 26-60 of original function
    # Returns plan data structure

def _output_plan_result(plan_data: PlanData, config: PlanConfig) -> int:
    """Output plan in requested format and location."""
    # Lines 61-80 of original function
    # Returns exit code

```

**Benefits of This Split**:

- **Single Responsibility**: Each function has one clear job
- **Testability**: Can test config preparation, plan generation, and output separately
- **Maintainability**: Easy to modify individual steps
- **Reusability**: Components can be used in other contexts

### **Target 2: Split `generate_plan()` Function** (Days 5-6)

**Current Structure**:

```python
def generate_plan(description, languages, max_suggestions, min_score):
    # Lines 1-15: Keyword extraction from description
    # Lines 16-30: Command template generation
    # Lines 31-50: Command scoring and ranking
    # Lines 51-70: Plan formatting and structure

```

**Decomposition Strategy**:

```python
def generate_plan(description, languages, max_suggestions, min_score):
    """Generate reproduction plan - external interface unchanged."""
    keywords = _extract_keywords(description)
    commands = _generate_candidate_commands(keywords, languages)
    scored_commands = _score_and_rank_commands(commands, min_score)
    return _format_plan_output(scored_commands[:max_suggestions])

def _extract_keywords(description: str) -> List[str]:
    """Extract relevant keywords from issue description."""

def _generate_candidate_commands(keywords: List[str], languages: List[str]) -> List[Command]:
    """Generate candidate commands based on keywords and languages."""

def _score_and_rank_commands(commands: List[Command], min_score: int) -> List[Command]:
    """Score commands and return ranked list above threshold."""

def _format_plan_output(commands: List[Command]) -> Dict:
    """Format commands into final plan structure."""

```

### **Target 3: Split `detect_languages()` Function** (Days 7-8)

**Current Structure**:

```python
def detect_languages(repo_path):
    # Lines 1-15: File system scanning
    # Lines 16-30: Pattern matching against file types
    # Lines 31-45: Score calculation for each language
    # Lines 46-65: Result formatting and sorting

```

**Decomposition Strategy**:

```python
def detect_languages(repo_path):
    """Detect languages in repository - interface unchanged."""
    files = _scan_repository_files(repo_path)
    matches = _match_language_patterns(files)
    scores = _calculate_language_scores(matches)
    return _format_detection_results(scores)

```

---

## **Phase 3: Validation & Testing** (Days 9-10)

### **Critical Validation Strategy**

**Before Any Function Splitting**:

```bash
# Create comprehensive behavioral baselines
autorepro plan --desc "pytest failing" --dry-run > baseline_plan_full.txt
autorepro plan --desc "pytest failing" --format json > baseline_plan_json.txt
autorepro scan --json > baseline_scan_full.json
autorepro scan --show-scores > baseline_scan_scores.txt

# Test all command variations
test_cases=(
    "plan --desc 'npm test' --dry-run"
    "plan --desc 'build errors' --format json --dry-run"
    "plan --file issue.txt --dry-run"
    "scan --json"
    "scan --show-scores"
)

for test_case in "${test_cases[@]}"; do
    echo "Baseline: $test_case"
    autorepro $test_case > "baseline_$(echo $test_case | tr ' ' '_').txt"
done

```

### **During Function Splitting - Incremental Validation**

**After Each Function Split**:

```python
class TestFunctionSplitting:
    def test_plan_command_identical_behavior(self):
        """plan_command must produce identical results after splitting."""
        test_scenarios = [
            ("pytest failing", "md", True),    # dry-run markdown
            ("npm test issues", "json", True), # dry-run json
            ("build problems", "md", False),   # actual file creation
        ]

        for desc, fmt, dry_run in test_scenarios:
            # Test with new split functions
            result = run_plan_command(desc, format=fmt, dry_run=dry_run)
            baseline = load_baseline_result(desc, fmt, dry_run)

            # Must be byte-for-byte identical
            assert result.returncode == baseline.returncode
            assert result.stdout == baseline.stdout
            assert result.stderr == baseline.stderr

    def test_generate_plan_identical_output(self):
        """generate_plan must produce identical plan structures."""
        test_inputs = [
            ("pytest tests failing", ["python"], 5, 2),
            ("npm build errors", ["node"], 3, 1),
            ("go mod issues", ["go"], 5, 2),
        ]

        for desc, langs, max_sug, min_score in test_inputs:
            result = generate_plan(desc, langs, max_sug, min_score)
            baseline = load_baseline_plan(desc, langs, max_sug, min_score)

            # Plan structure must be identical
            assert result == baseline

    def test_detect_languages_identical_results(self):
        """Language detection must produce identical results."""
        test_repos = [
            "test_repos/python_project",
            "test_repos/node_project",
            "test_repos/mixed_project"
        ]

        for repo_path in test_repos:
            result = detect_languages(repo_path)
            baseline = load_baseline_detection(repo_path)

            # Detection must be identical
            assert result["detected"] == baseline["detected"]
            assert result["languages"] == baseline["languages"]

```

### **Function-Level Unit Testing**

```python
# New unit tests for extracted functions
class TestExtractedPlanFunctions:
    def test_prepare_plan_config_validation(self):
        """Test plan config preparation with various argument combinations."""
        # Test valid configurations
        args = Mock(desc="test", file=None, format="md", dry_run=True)
        config = _prepare_plan_config(args)
        assert config.description == "test"
        assert config.format_type == "md"

        # Test invalid configurations
        args = Mock(desc=None, file=None)
        with pytest.raises(ValidationError):
            _prepare_plan_config(args)

    def test_extract_keywords_consistency(self):
        """Test keyword extraction produces consistent results."""
        test_descriptions = [
            "pytest tests are failing with timeout errors",
            "npm build command fails with dependency issues",
            "go mod tidy shows module not found errors"
        ]

        for desc in test_descriptions:
            keywords = _extract_keywords(desc)
            # Should extract relevant tech keywords
            assert any(kw in ["pytest", "npm", "go"] for kw in keywords)

            # Should be deterministic
            keywords2 = _extract_keywords(desc)
            assert keywords == keywords2

```

---

## **Testing Strategy - Function Splitting**

### **Behavioral Preservation Tests**

```python
def test_no_behavioral_regression():
    """Complete CLI behavior must remain unchanged."""
    # Test every CLI command and option combination
    original_behaviors = load_pre_split_baselines()

    for command_test in original_behaviors:
        current_result = run_cli_command(command_test.args)

        assert current_result.exit_code == command_test.expected_exit_code
        assert current_result.stdout == command_test.expected_stdout
        assert current_result.stderr == command_test.expected_stderr

```

### **Golden File Validation**

```python
def test_golden_files_unchanged():
    """All golden test files must remain identical."""
    if os.path.exists("tests/golden"):
        # Regenerate golden files with split functions
        subprocess.run(["python", "scripts/regold.py"])

        # Check for any changes
        git_diff = subprocess.run(
            ["git", "diff", "tests/golden/"],
            capture_output=True, text=True
        )

        if git_diff.stdout:
            pytest.fail(f"Golden files changed:\n{git_diff.stdout}")

```

### **Performance Impact Testing**

```python
def test_function_splitting_performance():
    """Function splitting should not degrade performance."""
    import time

    performance_tests = [
        ("plan generation", lambda: autorepro_plan("test issue")),
        ("language detection", lambda: autorepro_scan()),
        ("devcontainer creation", lambda: autorepro_init(dry_run=True))
    ]

    for test_name, operation in performance_tests:
        # Measure current performance
        times = []
        for _ in range(10):
            start = time.time()
            operation()
            times.append(time.time() - start)

        avg_time = sum(times) / len(times)
        baseline_time = get_baseline_performance(test_name)

        # Should be within 15% of baseline (allowing for slight overhead)
        assert avg_time <= baseline_time * 1.15, f"{test_name} performance regressed"

```

---

## **Risk Mitigation**

### **Highest Risk Function Splits**

1. **`plan_command()` in cli.py**
    - Risk: Main CLI entry point, any change affects user experience
    - Mitigation: Extensive CLI testing, argument parsing validation
2. **`detect_languages()` in detect.py**
    - Risk: Core algorithm, affects language detection accuracy
    - Mitigation: Golden file testing on diverse repository types
3. **`generate_plan()` in planner.py**
    - Risk: Core business logic, affects plan quality
    - Mitigation: Plan output comparison, scoring validation

### **Split Strategy Safety Measures**

```bash
# Each major function gets its own branch
git checkout -b split-plan-command
git checkout -b split-generate-plan
git checkout -b split-detect-languages

# Incremental commits within each split
git commit -m "Extract _prepare_plan_config function"
git commit -m "Extract _generate_plan_content function"
git commit -m "Extract _output_plan_result function"

# Tag working states
git tag plan-command-split-working

```

### **Rollback Criteria**

- Any existing test failures
- CLI behavior changes
- Performance degradation >15%
- Golden file changes
- Integration test failures

---

## **Success Criteria**

### **Functional Requirements**

- [ ]  Zero behavioral changes in all CLI commands
- [ ]  All existing tests pass without modification
- [ ]  Golden files remain identical
- [ ]  Performance within 15% of baseline

### **Technical Requirements**

- [ ]  No functions >50 lines remaining
- [ ]  Average cyclomatic complexity reduced from B to A grade
- [ ]  All large functions split following SRP
- [ ]  New functions have clear, single responsibilities

### **Quality Requirements**

- [ ]  All extracted functions have unit tests
- [ ]  Clear function names describing single purpose
- [ ]  Well-defined interfaces with type hints
- [ ]  Comprehensive error handling maintained

---

## **Deliverables**

1. **Refactored Core Functions**
    - Split plan_command into 3-4 focused functions
    - Split generate_plan into 4-5 specialized functions
    - Split detect_languages into 3-4 scanning functions
    - All other large functions decomposed
2. **Enhanced Test Coverage**
    - Unit tests for all extracted functions
    - Integration tests validating combined behavior
    - Performance regression tests
3. **Improved Code Structure**
    - Clear separation of concerns
    - Reusable function components
    - Better error handling boundaries
    - Enhanced maintainability
4. **Documentation**
    - Function responsibility documentation
    - Code organization improvements
    - Testing strategy documentation

**Final Result**: A well-structured codebase with focused, single-purpose functions that maintain identical external behavior while being significantly more maintainable and testable.
