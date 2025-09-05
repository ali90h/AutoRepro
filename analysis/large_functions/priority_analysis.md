# Large Function Analysis - Priority Targets

## CRITICAL PRIORITY (Complexity F/E - Extremely High)

### 🚨 cmd_plan() in cli.py - COMPLEXITY: F (54)
- **Risk Level**: EXTREME - Main CLI entry point
- **Impact**: Very High - Core user functionality  
- **Lines**: ~240+ (estimated from LOC analysis)
- **Responsibilities**: Input validation, language detection, plan generation, output formatting
- **Priority**: #1 - Split immediately

### 🚨 cmd_pr() in cli.py - COMPLEXITY: F (42)  
- **Risk Level**: HIGH - PR integration functionality
- **Impact**: High - GitHub integration
- **Lines**: ~200+ (estimated)
- **Responsibilities**: PR creation, validation, GitHub API calls
- **Priority**: #2

### 🚨 cmd_exec() in cli.py - COMPLEXITY: E (35)
- **Risk Level**: HIGH - Command execution core
- **Impact**: High - Execution functionality 
- **Lines**: ~150+ (estimated)
- **Responsibilities**: Command parsing, execution, output handling
- **Priority**: #3

## HIGH PRIORITY (Complexity C/D)

### ⚠️ write_devcontainer() in env.py - COMPLEXITY: C (20)
- **Risk Level**: MEDIUM - Configuration management
- **Impact**: Medium - Init functionality
- **Lines**: ~150+ (estimated)
- **Responsibilities**: File creation, validation, diff generation
- **Priority**: #4

### ⚠️ _load_plugin_rules() in rules.py - COMPLEXITY: C (14)  
- **Risk Level**: MEDIUM - Plugin system
- **Impact**: Medium - Rule loading
- **Priority**: #5

### ⚠️ build_pr_body() in pr.py - COMPLEXITY: D (21)
- **Risk Level**: MEDIUM - PR formatting
- **Impact**: Medium - GitHub integration
- **Priority**: #6

### ⚠️ process_plan_input() in utils/plan_processing.py - COMPLEXITY: D (26)
- **Risk Level**: MEDIUM - Plan processing
- **Impact**: Medium - Core planning logic
- **Priority**: #7

## Target Splitting Strategy

### Phase 2A: Split cmd_plan() (Days 1-3)
**Current Structure** (~240 lines, CC: 54):
- Lines 1-30: Argument parsing and validation  
- Lines 31-60: Repository path resolution
- Lines 61-90: Language detection
- Lines 91-150: Plan generation and processing
- Lines 151-200: Output formatting (JSON/MD)
- Lines 201-240: File writing and error handling

**Proposed Split**:
```python
def cmd_plan(args):
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
    # Lines 1-60 of original function

def _generate_plan_content(config: PlanConfig) -> PlanData:
    """Generate the actual reproduction plan."""
    # Lines 61-150 of original function

def _output_plan_result(plan_data: PlanData, config: PlanConfig) -> int:
    """Output plan in requested format and location."""
    # Lines 151-240 of original function
```

### Phase 2B: Split cmd_pr() (Days 4-5)
### Phase 2C: Split cmd_exec() (Days 6-7)  
### Phase 2D: Split remaining high-priority functions (Days 8-10)

## Success Metrics

- **Target**: Reduce all functions to <50 lines
- **Complexity**: Improve average from B (5.0) to A (<4.0)
- **Maintainability**: Clear single responsibility for each function
- **Testability**: Enable focused unit testing
- **Behavior**: Zero regressions in CLI functionality