# 📄 Section A: Configuration & Code Cleanup - Technique 1

> **Foundation Building**: Eliminate hard-coded values without changing AutoRepro's behavior
>

---

## 🎯 **TECHNIQUE 1: Avoid Hard Coding** 🔧

**Duration**: 1 week

**Priority**: High | **Risk**: Medium | **Impact**: High

### **Core Strategy**

Replace hard-coded values with a centralized configuration system while maintaining **identical external behavior**. Every change must be invisible to users and pass all existing tests.

---

## **Phase 1: Discovery & Analysis** (Day 1)

### **Identify Critical Hard-Coded Values**

**Expected findings in AutoRepro**:

**🚨 CRITICAL (Change behavior)**:

- `timeout=120` in subprocess calls
- `max_suggestions = 5` in plan generation
- `min_score = 2` in command filtering
- Detection weights: `{"lock": 4, "config": 3, "setup": 2, "source": 1}`

**⚠️ HIGH (User-visible)**:

- File paths: `".devcontainer"`, `"[repro.md](http://repro.md)"`, `"out/"`
- Docker versions: `"python3.11"`, `"node:20"`
- Error messages: `"Error: Must provide --desc or --file"`

**📝 MEDIUM (Configuration)**:

- Exit codes: `return 0`, `return 1`, `return 2`
- File extensions: `".py"`, `".js"`, `".json"`
- Default formats: `"md"`, `"json"`

### **Analysis Method**

```bash
# Automated scan to find all hard-coded values
grep -r "timeout.*=.*[0-9]" autorepro/     # Timeouts
grep -r "max.*=.*[0-9]" autorepro/         # Limits
grep -r "return [0-9]" autorepro/          # Exit codes
grep -r '"\.[a-z]*"' autorepro/            # File extensions
grep -r '".*Error:' autorepro/             # Error messages
```

**Expected Count**: ~60 hard-coded values across 8 categories

---

## **Phase 2: Configuration Architecture** (Days 2-3)

### **Design Principles**

1. **Backward Compatibility**: All defaults match current hard-coded values exactly
2. **Environment Override**: Support `AUTOREPRO_*` environment variables
3. **Type Safety**: Use dataclasses with validation
4. **Fail Fast**: Invalid config values cause startup errors, not runtime surprises

### **Configuration Structure**

```python
# Core idea - not full implementation
@dataclass
class AutoReproConfig:
    timeouts: TimeoutConfig      # All timeout values
    paths: PathConfig           # File and directory paths
    limits: LimitsConfig        # Numeric limits and thresholds
    detection: DetectionConfig  # Language detection parameters
    errors: ErrorConfig         # Exit codes and messages
    docker: DockerConfig        # Container configuration
```

### **Key Features**

- **Environment Variables**: `AUTOREPRO_TIMEOUT_DEFAULT=180`
- **Validation**: Reject invalid values at startup
- **Documentation**: Self-documenting with type hints
- **Testability**: Easy to mock and override in tests

---

## **Phase 3: Incremental Replacement** (Days 4-7)

### **Replacement Strategy - 3 Risk Levels**

### **Level 1: Safe Replacements** (Day 4)

**Target**: Display text, file extensions, non-critical paths

**Risk**: Very Low

**Example**:

```python
# Before
print("Created draft PR")

# After
from autorepro.config import config
print(config.errors.messages["pr_created"])
```

**Validation**: Text output identical, all tests pass

### **Level 2: Behavioral Replacements** (Days 5-6)

**Target**: Timeouts, limits, algorithm parameters

**Risk**: High

**Example**:

```python
# Before
[subprocess.run](http://subprocess.run)(cmd, timeout=120)
suggestions = suggestions[:5]

# After
[subprocess.run](http://subprocess.run)(cmd, timeout=config.timeouts.default_seconds)
suggestions = suggestions[:config.limits.max_plan_suggestions]
```

**Validation**: Exact same behavior with default config

### **Level 3: Critical Algorithm Values** (Day 7)

**Target**: Detection weights, scoring thresholds

**Risk**: Very High

**Example**:

```python
# Before (in [detect.py](http://detect.py))
weights = {"lock": 4, "config": 3, "setup": 2, "source": 1}

# After
weights = config.detection.weights
```

**Validation**: Identical detection results for all test cases

---

## **Testing Strategy - Behavior Preservation**

### **Pre-Replacement Tests**

```bash
# Create behavior baselines BEFORE any changes
autorepro scan --json > baseline_scan.json
autorepro plan --desc "pytest failing" --dry-run > baseline_plan.txt
autorepro init --dry-run > baseline_init.txt

# Performance baseline
time autorepro scan > baseline_performance.txt
```

### **Per-Change Validation**

```python
# After each configuration replacement
class TestConfigurationReplacement:
    def test_identical_cli_behavior(self):
        """All CLI outputs must be identical"""
        test_commands = [
            ["scan", "--json"],
            ["plan", "--desc", "test", "--dry-run"],
            ["init", "--dry-run"],
            ["--help"]
        ]

        for cmd in test_commands:
            result = [subprocess.run](http://subprocess.run)(["autorepro"] + cmd, capture_output=True, text=True)
            # Compare with baseline results
            assert result.returncode == expected_returncode
            assert result.stdout == expected_stdout
            assert result.stderr == expected_stderr

    def test_environment_variable_override(self):
        """Environment variables should change behavior correctly"""
        # Test that AUTOREPRO_TIMEOUT_DEFAULT=60 actually uses 60 seconds
        env = os.environ.copy()
        env["AUTOREPRO_TIMEOUT_DEFAULT"] = "60"

        # Verify config reflects the change
        with patch.dict(os.environ, env):
            from autorepro.config import config
            assert config.timeouts.default_seconds == 60

    def test_detection_algorithm_unchanged(self):
        """Language detection must produce identical results"""
        test_repos = ["python_project", "node_project", "mixed_project"]

        for repo in test_repos:
            result = run_scan_on_test_repo(repo)
            baseline = load_baseline_scan(repo)

            # Detection results must be identical
            assert result["detected"] == baseline["detected"]
            assert result["languages"] == baseline["languages"]
```

### **Golden File Testing**

```python
def test_plan_generation_unchanged():
    """Plan generation output must be byte-for-byte identical"""
    test_descriptions = [
        "pytest tests failing",
        "npm build errors",
        "go mod tidy issues",
        "docker build failing"
    ]

    for desc in test_descriptions:
        result = autorepro_plan(desc, format="json")
        baseline = load_golden_plan(desc)

        # Must be exactly identical
        assert result == baseline
```

### **Performance Testing**

```python
def test_performance_not_regressed():
    """Configuration system must not slow down operations"""
    import time

    operations = [
        lambda: autorepro_scan(),
        lambda: autorepro_plan("test issue"),
        lambda: autorepro_init(dry_run=True)
    ]

    for operation in operations:
        start = time.time()
        operation()
        duration = time.time() - start

        # Should be within 10% of baseline performance
        baseline_duration = get_baseline_duration(operation)
        assert duration <= baseline_duration * 1.1
```

---

## **Risk Mitigation**

### **High-Risk Areas in AutoRepro**

1. **Language Detection Algorithm** ([`detect.py`](http://detect.py))
    - Risk: Changing weights breaks detection accuracy
    - Mitigation: Extensive testing on diverse repositories
2. **Plan Generation Logic** ([`planner.py`](http://planner.py))
    - Risk: Score thresholds affect command selection
    - Mitigation: Golden file comparison for all scenarios
3. **CLI Argument Processing** ([`cli.py`](http://cli.py))
    - Risk: Error messages or exit codes change
    - Mitigation: Exact string matching tests

### **Rollback Strategy**

```bash
# Each phase gets its own branch for easy rollback
git checkout -b config-phase1-safe-replacements
git checkout -b config-phase2-behavioral-changes
git checkout -b config-phase3-critical-algorithms

# Tag stable points
git tag config-working-checkpoint-1
```

### **Validation Gates**

- **After each file**: All existing tests must pass
- **After each phase**: Full regression testing
- **Before merge**: Performance benchmarking

---

## **Success Criteria**

### **Functional Requirements**

- [ ]  Zero behavioral changes from user perspective
- [ ]  All existing tests pass without modification
- [ ]  CLI help, error messages, and outputs identical
- [ ]  Performance within 5% of baseline

### **Technical Requirements**

- [ ]  50+ hard-coded values replaced with configuration
- [ ]  Environment variable support for all critical values
- [ ]  Type-safe configuration with validation
- [ ]  Comprehensive test coverage for config system

### **Quality Requirements**

- [ ]  Configuration documented with examples
- [ ]  Invalid configurations fail fast with clear errors
- [ ]  Easy to add new configuration values in future

---

## **Deliverables**

1. **Configuration System** (`autorepro/config/`)
    - Type-safe dataclass models
    - Environment variable loading
    - Validation and error handling
2. **Updated Core Code**
    - All hard-coded values replaced
    - Consistent config usage patterns
    - Preserved behavior and interfaces
3. **Test Suite Enhancements**
    - Configuration validation tests
    - Behavioral preservation tests
    - Environment override tests
4. **Documentation**
    - Configuration reference guide
    - Environment variable list
    - Migration notes for developers

**Final Result**: A flexible, configurable AutoRepro that behaves identically to the original but can be customized through environment variables and config files.

[Section A,Technique 2](https://www.notion.so/Section-A-Technique-2-2647decfc30c80dfa515f53d9f58aeca?pvs=21)

[Section B: Function Structure - Technique 3](https://www.notion.so/Section-B-Function-Structure-Technique-3-2647decfc30c8067bfdedb87196ed293?pvs=21)
