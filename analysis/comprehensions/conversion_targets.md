# List/Dict Comprehension Conversion Targets Analysis

## Conversion Categories

### 🟢 **SAFE** - Simple, Direct Conversions
These are straightforward list building patterns with no side effects:

1. **core/planning.py:165** - `_collect_active_rules()`
   ```python
   # Current
   active_rules = []
   for ecosystem in ecosystems_to_include:
       if ecosystem in all_rules:
           for rule in all_rules[ecosystem]:
               source = "builtin" if ecosystem in builtin_rules and rule in builtin_rules[ecosystem] else "plugin"
               active_rules.append((rule, source))
   
   # Target: Nested comprehension
   ```

2. **core/planning.py:196** - Keyword filtering with conditions
   ```python
   # Current
   matched_keywords = []
   for keyword in rule.keywords:
       if keyword in keywords:
           matched_keywords.append(keyword)
   
   # Target: [keyword for keyword in rule.keywords if keyword in keywords]
   ```

3. **render/formats.py:42** - Token extraction (nested loops)
   ```python
   # Current - Complex nested pattern with filtering
   tokens = []
   for part in parts:
       part = part.strip()
       if part:
           words = part.split()
           for word in words:
               clean_token = "".join(c for c in word if c.isalnum() or c in "-_")
               if clean_token and not clean_token.isdigit():
                   tokens.append(clean_token)
   ```

4. **detect.py:277-280** - Language pattern matching
   ```python
   # Current
   results = []
   matches = []
   # Simple append patterns in loops
   ```

### 🟡 **REVIEW** - Complex Logic, Conditional Conversions  
These have multiple conditions or complex transformations:

5. **cli.py:676** - Environment needs generation
   ```python
   # Current - Multiple conditional branches
   needs = []
   for lang in lang_names:
       if lang == "python":
           needs.append("Python 3.7+")
           if "pytest" in keywords:
               needs.append("pytest package")
   # Complex nested conditions
   ```

6. **sync.py:70-72** - Link building with conditions
   ```python  
   # Current
   for link in links:
       header_lines.append(f"- {link}")
   # Target: Simple list comprehension
   ```

### 🔴 **SKIP** - Side Effects, Complex State Changes
These have logging, state changes, or complex logic:

7. **rules.py:88** - Plugin rule loading (has debug logging)
8. **report.py:49** - Environment line building (has exception handling)  
9. **pr.py** - Multiple patterns with complex formatting logic

## Dictionary Patterns

### 🟢 **SAFE** Dictionary Conversions

1. **cli.py:1144** - Environment variable parsing
   ```python
   # Current
   env_vars = {}
   for env_str in env_list:
       if "=" in env_str:
           key, value = env_str.split("=", 1)
           env_vars[key] = value
   
   # Target: Dict comprehension
   ```

2. **rules.py:104** - Rule copying patterns
   ```python
   # Current - Simple dictionary building
   rules = {}
   # Pattern: dict iteration and assignment
   ```

## Conversion Priority

### Phase 1 - Simple Filtering (Lines 1-3)
- `matched_keywords` filtering
- Simple `append()` in conditional loops
- Basic list building patterns

### Phase 2 - Dictionary Comprehensions (Lines 4-5)  
- Environment variable parsing
- Simple key-value mapping

### Phase 3 - Complex Nested (Lines 6-8)
- Multi-level nested loops
- Token extraction with cleaning
- Complex conditional logic

## Expected Benefits

- **Readability**: More concise, Pythonic code
- **Performance**: Potential 20-30% speedup for large lists
- **Maintainability**: Less code, fewer variables to track
- **Correctness**: Reduced chance of append() bugs