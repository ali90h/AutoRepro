# Technique 6: Replace Temp with Query - Analysis

## Temporary Variable Categories

### 🟢 **DIRECT RETURNS** - High Priority, Low Risk

**Variables assigned and immediately returned - candidates for direct return**

1. **io/github.py:168** - JSON parsing result
   ```python
   # Current
   pr_data = json.loads(result.stdout)
   return pr_data
   
   # Target: Direct return
   return json.loads(result.stdout)
   ```
   - **Risk**: LOW - Simple transformation, no side effects
   - **Impact**: MEDIUM - Removes unnecessary variable

2. **io/github.py:641** - Issue number extraction  
   ```python
   # Current
   issue_number = int(issue_url.split("/")[-1])
   return issue_number
   
   # Target: Direct return
   return int(issue_url.split("/")[-1])
   ```
   - **Risk**: LOW - Pure calculation, no side effects
   - **Impact**: MEDIUM - Cleaner expression

3. **core/planning.py:58-60** - Text normalization
   ```python
   # Current
   text = re.sub(r"\s+", " ", text).strip()
   return text
   
   # Target: Direct return  
   return re.sub(r"\s+", " ", text).strip()
   ```
   - **Risk**: LOW - String manipulation, no side effects
   - **Impact**: MEDIUM - More direct expression

4. **core/planning.py:140-142** - Text truncation
   ```python
   # Current
   truncated = text[:60] + "…"
   return truncated
   
   # Target: Direct return
   return text[:60] + "…"
   ```
   - **Risk**: LOW - Simple string operation
   - **Impact**: MEDIUM - Cleaner code

5. **utils/repro_bundle.py:63-65** - Content formatting
   ```python
   # Current
   content_str = content_str.rstrip() + "\n"
   return content_str
   
   # Target: Direct return
   return content_str.rstrip() + "\n"
   ```
   - **Risk**: LOW - String manipulation
   - **Impact**: MEDIUM - Removes temporary

### 🟡 **INLINE EXPRESSIONS** - Medium Priority, Low Risk  

**Property access and simple calculations that could be inlined**

6. **cli.py:554** - Boolean flag assignment
   ```python
   # Current
   print_to_stdout = out == "-"
   # Used later in conditional logic
   
   # Target: Inline in usage
   if out == "-":  # Direct usage where needed
   ```
   - **Risk**: LOW - Simple boolean expression
   - **Impact**: LOW - May reduce readability if used multiple times

7. **Path resolution variables** - Various locations
   ```python
   # Current pattern
   repo_path = Path(repo).resolve()
   # Various property access patterns
   
   # Target: Consider inline vs helper method
   ```
   - **Risk**: MEDIUM - Path operations can have side effects
   - **Impact**: MEDIUM - Depends on usage frequency

### 🔴 **COMPLEX OPERATIONS** - Extract to Methods

**Multi-step operations that should become query methods**

8. **Configuration resolution patterns** - Multiple locations
   ```python
   # Complex multi-step configurations
   # Should become helper methods rather than inline
   ```
   - **Strategy**: Extract to helper methods
   - **Risk**: LOW - Improved organization
   - **Impact**: HIGH - Better maintainability

## Implementation Strategy

### Phase 1: Direct Returns (Low Risk)
1. Apply direct return replacements (#1-5)
2. Test each change immediately
3. Verify no behavior changes

### Phase 2: Inline Expressions (Medium Risk) 
1. Evaluate usage frequency of each variable
2. Inline single-use expressions
3. Keep multi-use variables for readability

### Phase 3: Method Extraction (High Value)
1. Identify complex operations 
2. Extract to descriptive helper methods
3. Create query-based property access

## Success Metrics
- [ ] 5+ direct return optimizations applied
- [ ] 2+ inline expressions optimized  
- [ ] 2+ complex operations extracted to methods
- [ ] All tests pass after each change
- [ ] No performance degradation
- [ ] Improved code readability