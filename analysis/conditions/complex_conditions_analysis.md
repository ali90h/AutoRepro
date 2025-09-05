# Complex Conditions Analysis - Technique 5

## Complex Conditions Found

### 🔴 **HIGH PRIORITY** - Very Complex Logic

#### 1. **cli.py:859-860** - PR Update Operations Check
```python
# Current - Complex multi-condition check
if not (pr_config.update_if_exists or pr_config.comment or 
        pr_config.update_pr_body or pr_config.add_labels or pr_config.link_issue):
    return None

# Issues: 5 conditions with negated OR logic - hard to understand
# Strategy: Extract boolean variable with positive logic
```

#### 2. **cli.py:548** - Path Resolution Logic  
```python
# Current - Triple condition with mixed logic
if repo_path and not Path(out).is_absolute() and not print_to_stdout:
    out = str(repo_path / out)

# Issues: Mixed positive/negative conditions - confusing logic
# Strategy: Extract descriptive boolean variables
```

#### 3. **core/planning.py:166** - Rule Source Determination
```python
# Current - Nested condition in comprehension
(rule, "builtin" if ecosystem in builtin_rules and rule in builtin_rules[ecosystem] else "plugin")

# Issues: Complex nested lookup logic
# Strategy: Helper function for source determination  
```

### 🟡 **MEDIUM PRIORITY** - Multiple OR Conditions

#### 4. **cli.py:655** - Test-Related Keywords Detection
```python
# Current - Triple OR condition
if "test" in keywords or "tests" in keywords or "testing" in keywords:
    assumptions.append("Issue is related to testing")

# Strategy: Helper function for keyword set checking
```

#### 5. **cli.py:659** - Installation Keywords Detection  
```python
# Current - Double OR condition  
if "install" in keywords or "setup" in keywords:
    assumptions.append("Installation or setup may be involved")

# Strategy: Same helper function pattern
```

#### 6. **utils/plan_processing.py:94-98** - Duplicate Logic
```python
# Current - Repeated patterns
if "test" in keywords or "tests" in keywords or "testing" in keywords:
    assumptions.append("Issue is related to testing")
if "install" in keywords or "setup" in keywords:
    assumptions.append("Installation or setup may be involved")

# Issues: Exact duplication from cli.py
# Strategy: Extract to shared utility function
```

### 🟢 **LOW PRIORITY** - Simple Multi-Conditions

#### 7. **cli.py:588** - Directory Check
```python
if not print_to_stdout and out and os.path.isdir(out):
    
# Strategy: Extract boolean for clarity
```

#### 8. **cli.py:592** - File Exists Check
```python
if not print_to_stdout and os.path.exists(out) and not force:

# Strategy: Extract boolean variables
```

## Simplification Strategies

### **Strategy 1: Boolean Variable Extraction**
Convert complex conditions to descriptive boolean variables:
- `should_update_pr_path` instead of triple condition
- `needs_pr_update` instead of negated 5-way OR
- `is_test_related` instead of keyword OR chain

### **Strategy 2: Helper Functions**
Create utility functions for repeated logic:
- `has_keyword_variants(keywords, base_word)` for test/tests/testing patterns
- `determine_rule_source(ecosystem, rule, builtin_rules)` for source logic
- `should_apply_repo_path(repo_path, out_path, print_to_stdout)` for path logic

### **Strategy 3: Early Returns**
Replace negated complex conditions with positive early returns:
```python
# Instead of: if not (A or B or C or D or E):
if A or B or C or D or E:
    # handle the positive case
return default_case
```

### **Strategy 4: Keyword Set Utilities**
Create keyword checking utilities:
```python
def has_any_keyword_variant(keywords: set, variants: list[str]) -> bool:
    return any(variant in keywords for variant in variants)

# Usage:
TEST_KEYWORDS = ["test", "tests", "testing"]
if has_any_keyword_variant(keywords, TEST_KEYWORDS):
    ...
```

## Expected Benefits

### **Readability**
- Self-documenting boolean variable names
- Positive logic instead of complex negations
- Single responsibility per condition check

### **Maintainability** 
- Centralized keyword checking logic
- Easier to add new keyword variants
- Clear separation of concerns

### **Testability**
- Helper functions can be unit tested independently
- Boolean variables make test cases clearer
- Reduced cognitive complexity per function

## Risk Assessment

- **Risk Level**: Medium - Boolean logic changes require careful validation
- **Mitigation**: Comprehensive truth table testing for all combinations
- **Validation**: Before/after output comparison for all CLI commands