# Technique 7: Decorator Pattern - Cross-Cutting Concerns Analysis

## Identified Cross-Cutting Concerns

### 🎯 **HIGH PRIORITY** - Widespread Patterns

#### 1. **Dry-Run Mode Handling** (18+ locations)
**Pattern**: Scattered `if dry_run:` checks throughout CLI commands
```python
# Current repeated pattern
if dry_run:
    print(f"Would run: {quoted_cmd}")
    return 0
# Actual execution code...
```

**Locations**:
- `cmd_plan()` - cli.py:561
- `cmd_pr()` - cli.py:1089, 1274, 1441
- `_handle_pr_dry_run()` - cli.py:901
- All CLI command functions have dry-run parameters

**Decorator Target**: `@dry_run_aware`

#### 2. **Error Handling & Return Codes** (15+ locations)  
**Pattern**: Consistent try/except blocks with specific return codes
```python
# Current repeated pattern  
try:
    # operation logic
    return 0
except (OSError, PermissionError):
    log.error(f"Error: {e}")
    return 1
except ValueError:
    return 2
```

**Locations**:
- All CLI command functions 
- Path validation (cli.py:542-551)
- File operations throughout

**Decorator Target**: `@handle_errors`

#### 3. **Configuration Validation** (10+ locations)
**Pattern**: Similar argument validation logic
```python
# Current repeated pattern
if not desc and not file:
    log.error("Error: Must provide either --desc or --file")
    return 2
    
if repo is not None:
    try:
        repo_path = Path(repo).resolve()
        if not repo_path.is_dir():
            raise ValueError(f"--repo path does not exist: {repo}")
    except (OSError, ValueError):
        # error handling...
```

**Locations**:
- `cmd_plan()` configuration extraction
- `cmd_pr()` configuration extraction  
- Path validation throughout

**Decorator Target**: `@validate_args`

#### 4. **Logging Setup** (10+ locations)
**Pattern**: Logger initialization in every command
```python
# Current repeated pattern
log = logging.getLogger("autorepro")
# logging calls throughout functions
```

**Locations**:
- `cmd_scan()` - cli.py:636
- `cmd_plan()` - cli.py:820  
- `cmd_pr()` - cli.py:871
- All major CLI functions

**Decorator Target**: `@log_operation`

### 🟡 **MEDIUM PRIORITY** - Improvement Opportunities

#### 5. **Output Formatting** (8+ locations)
**Pattern**: JSON vs text output handling
```python
# Current pattern
if format_type == "json":
    print(json.dumps(json_result, indent=2))
else:
    print("text output...")
```

**Decorator Target**: `@format_output`

#### 6. **Timing/Performance** (5+ locations) 
**Pattern**: Potential for execution timing (currently not implemented)
```python
# Target pattern
start_time = datetime.now()
# operation
duration = datetime.now() - start_time
log.info(f"Operation took {duration.total_seconds():.2f}s")
```

**Decorator Target**: `@time_execution`

## Decorator Architecture Design

### 🏗️ **Decorator Stack Architecture**

**Recommended Order** (innermost to outermost):
1. `@validate_args` - Check inputs first
2. `@dry_run_aware` - Skip execution if dry-run  
3. `@time_execution` - Measure actual operation time
4. `@handle_errors` - Catch and format errors
5. `@log_operation` - Log operation details
6. `@format_output` - Format final output

### 🎨 **Decorator Interface Design**

#### Core Decorators Module: `autorepro/utils/decorators.py`

```python
# Planned decorator signatures

@validate_args(required=['repo'], optional=['desc', 'file'])
@dry_run_aware(message_template="Would {operation}")  
@time_execution(log_threshold=1.0)
@handle_errors(default_return=1, error_mappings={ValueError: 2})
@log_operation(operation_name="plan generation")
@format_output(formats=['json', 'text'])
def cmd_plan(...):
    # Clean command logic only
```

### 🎯 **Target Functions for Decoration**

**CLI Commands** (5 functions):
- `cmd_scan()` - Language detection
- `cmd_plan()` - Plan generation  
- `cmd_pr()` - PR operations
- `cmd_exec()` - Command execution
- `cmd_version()` - Version info

**Configuration Functions** (2 functions):
- `_extract_plan_config()` - Plan configuration
- `_extract_pr_config()` - PR configuration

## Expected Benefits

### 📊 **Code Quality Improvements**
- **Remove 50+ lines** of duplicated error handling
- **Eliminate 18+ dry-run checks** scattered throughout
- **Centralize logging** setup and formatting
- **Consistent return codes** across all commands
- **Improved testability** through decorator isolation

### 🛡️ **Maintainability Benefits**
- **Single source of truth** for cross-cutting concerns
- **Easier to modify** error handling behavior
- **Consistent user experience** across commands  
- **Better separation of concerns** - business logic vs infrastructure

### 🚀 **Enhanced Features**
- **Automatic timing** for performance monitoring
- **Structured logging** with consistent formats
- **Graceful error handling** with appropriate exit codes
- **Professional CLI behavior** matching industry standards

## Implementation Risk Assessment

### 🟢 **LOW RISK**
- `@log_operation` - Pure additive functionality
- `@time_execution` - Non-invasive timing wrapper
- `@format_output` - Output formatting wrapper

### 🟡 **MEDIUM RISK**
- `@validate_args` - Requires careful argument mapping
- `@handle_errors` - Must preserve existing error behavior
- `@dry_run_aware` - Critical to preserve dry-run semantics

**Mitigation Strategy**: Implement and test each decorator individually before stacking