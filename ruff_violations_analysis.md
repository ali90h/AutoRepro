# Ruff Violations Analysis - Ticket #72

## Summary Statistics
- **Total Violations**: 43 across 9 files
- **Most Critical File**: cli.py (18 violations - 42% of total)
- **Primary Issues**: Complex functions with too many branches, statements, arguments

## Violations by Type

### PLR0915 (too-many-statements > 50): 7 violations
1. `cli.py:62` - `create_parser` (69 statements)
2. `cli.py:601` - `_generate_plan_content` (91 statements) ⭐ **CRITICAL**
3. `cli.py:977` - `cmd_exec` (127 statements) ⭐ **CRITICAL**
4. `env.py:168` - `write_devcontainer` (56 statements)
5. `pr.py:51` - `build_pr_body` (61 statements)
6. `report.py:127` - `maybe_exec` (99 statements) ⭐ **CRITICAL**
7. `utils/plan_processing.py:29` - `process_plan_input` (63 statements)

### PLR0913 (too-many-arguments > 5): 8 violations
1. `cli.py:544` - `_prepare_plan_config` (10 args)
2. `cli.py:825` - `cmd_plan` (10 args)
3. `cli.py:977` - `cmd_exec` (12 args) ⭐ **CRITICAL**
4. `cli.py:1204` - `_prepare_pr_config` (22 args) ⭐ **CRITICAL**
5. `cli.py:1380` - `cmd_pr` (22 args) ⭐ **CRITICAL**
6. `io/github.py:319` - `create_or_update_pr` (11 args)
7. `io/github.py:586` - `create_issue` (6 args)
8. `sync.py:24` - `render_sync_comment` (7 args)
9. `utils/process.py:176` - `safe_subprocess_run` (7 args)

### C901 (complex-structure > 10): 10 violations
1. `cli.py:601` - `_generate_plan_content` (complexity: 26) ⭐ **CRITICAL**
2. `cli.py:853` - `cmd_init` (complexity: 16)
3. `cli.py:977` - `cmd_exec` (complexity: 30) ⭐ **CRITICAL**
4. `cli.py:1312` - `_handle_pr_dry_run` (complexity: 15)
5. `cli.py:1348` - `_execute_pr_operations` (complexity: 11)
6. `cli.py:1443` - `main` (complexity: 12)
7. `io/github.py:319` - `create_or_update_pr` (complexity: 13)
8. `pr.py:51` - `build_pr_body` (complexity: 17)
9. `report.py:127` - `maybe_exec` (complexity: 22) ⭐ **CRITICAL**
10. `rules.py:59` - `_load_plugin_rules` (complexity: 11)
11. `utils/plan_processing.py:29` - `process_plan_input` (complexity: 18)

### PLR0912 (too-many-branches > 12): 10 violations
1. `cli.py:601` - `_generate_plan_content` (31 branches) ⭐ **CRITICAL**
2. `cli.py:853` - `cmd_init` (18 branches)
3. `cli.py:977` - `cmd_exec` (33 branches) ⭐ **CRITICAL**
4. `cli.py:1312` - `_handle_pr_dry_run` (14 branches)
5. `cli.py:1443` - `main` (13 branches)
6. `env.py:168` - `write_devcontainer` (18 branches)
7. `io/github.py:319` - `create_or_update_pr` (14 branches)
8. `pr.py:51` - `build_pr_body` (20 branches)
9. `report.py:127` - `maybe_exec` (23 branches) ⭐ **CRITICAL**
10. `utils/plan_processing.py:29` - `process_plan_input` (21 branches)

### PLR0911 (too-many-return-statements > 6): 8 violations
1. `cli.py:853` - `cmd_init` (9 returns)
2. `cli.py:977` - `cmd_exec` (14 returns) ⭐ **CRITICAL**
3. `cli.py:1443` - `main` (8 returns)
4. `report.py:127` - `maybe_exec` (10 returns) ⭐ **CRITICAL**

## Priority Refactor Plan

### Phase 1: Critical Functions (Immediate)
**Target**: Functions with multiple violations and high complexity

1. **`cmd_exec` (cli.py:977)** - 5 violations total
   - 127 statements, 33 branches, 14 returns, 12 args, complexity 30
   - **Strategy**: Split into multiple functions by responsibility
   - Extract validation, execution, and result handling

2. **`_generate_plan_content` (cli.py:601)** - 3 violations total
   - 91 statements, 31 branches, complexity 26
   - **Strategy**: Extract sub-functions for different plan generation steps

3. **`maybe_exec` (report.py:127)** - 4 violations total
   - 99 statements, 23 branches, 10 returns, complexity 22
   - **Strategy**: Split execution flow and result processing

### Phase 2: High-Arguments Functions (Next)
**Target**: Functions with excessive parameter counts

1. **`_prepare_pr_config` (cli.py:1204)** - 22 arguments
   - **Strategy**: Group related parameters into config objects

2. **`cmd_pr` (cli.py:1380)** - 22 arguments
   - **Strategy**: Use config object pattern

### Phase 3: Medium-Complexity Functions
**Target**: Functions with 1-2 violations each

1. `cmd_init`, `build_pr_body`, `create_or_update_pr`
2. `process_plan_input`, `write_devcontainer`

### Phase 4: Simple Arguments/Statements
**Target**: Easier fixes with lower risk

1. Functions with 6-11 arguments
2. Functions with 50-70 statements

## Refactoring Strategies by Violation Type

### PLR0913 (too-many-arguments)
- **Config Objects**: Group related parameters
- **Builder Pattern**: For complex function calls
- **Dependency Injection**: Pass fewer, higher-level objects

### C901/PLR0912 (complex-structure/too-many-branches)
- **Extract Methods**: Pull out logical sub-operations
- **Strategy Pattern**: Replace conditional logic
- **Early Returns**: Reduce nesting depth

### PLR0915 (too-many-statements)
- **Extract Methods**: Create smaller focused functions
- **Decompose by Responsibility**: Split mixed concerns
- **Helper Functions**: Move reusable code

### PLR0911 (too-many-return-statements)
- **Result Objects**: Return structured results instead of multiple exit points
- **Exception Handling**: Use exceptions for error cases
- **State Machines**: For complex flow control

## Implementation Plan

1. **Phase 1A**: Tackle `cmd_exec` function (highest impact)
2. **Phase 1B**: Refactor `_generate_plan_content`
3. **Phase 1C**: Simplify `maybe_exec`
4. **Phase 2**: Address high-argument functions
5. **Phase 3**: Medium complexity cleanup
6. **Phase 4**: Final argument/statement cleanup

**Success Metrics:**
- Reduce violations from 43 → target of <20
- No function >15 complexity, >8 arguments, >40 statements
- All tests continue passing
- CLI behavior unchanged
