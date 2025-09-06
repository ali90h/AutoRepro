# Add detection reasons to `autorepro scan`

## What / Why

This PR exposes **detection reasons** in `autorepro scan` so users can see which files/globs triggered each language detection. Previously, users would only know that a language was detected, but not which specific files caused the detection.

Key improvements:
- **Deterministic output**: Alphabetical ordering for both languages and reasons ensures consistent, predictable results
- **Root-only scan**: Non-recursive directory scanning focuses on project root indicators
- **Pure function design**: `detect_languages(path) -> list[tuple[str, list[str]]]` returns structured data with no side effects
- **Comprehensive language support**: Python, Node.js, Go, Rust, Java, C# with both exact filenames (`pyproject.toml`, `go.mod`) and glob patterns (`*.csproj`, `*.py`)

**Fixes #2**

## How I Tested

Ran the complete validation suite locally:

```bash
pre-commit clean && pre-commit run --all-files
pytest -q   # 29 tests passed
python -m black --check .
```

**Test Coverage:**
- Empty directory handling
- Single and multiple language detection
- Glob pattern matching (`*.csproj` → `App.csproj`)
- Alphabetical ordering verification (languages and reasons)
- CLI integration testing with `capsys` and `subprocess`
- Edge cases: subdirectories ignored, duplicate removal, mixed patterns

CI will run on this PR to validate the implementation across the full test matrix.

## Output Snippets

**Empty directory:**
```bash
$ autorepro scan
No known languages detected.
$ echo $?
0
```

**Single language (python):**
```bash
$ touch pyproject.toml
$ autorepro scan
Detected: python
- python  -> pyproject.toml
```

**Multiple languages (node + python):**
```bash
$ touch package.json pnpm-lock.yaml pyproject.toml
$ autorepro scan
Detected: node, python
- node  -> package.json, pnpm-lock.yaml
- python  -> pyproject.toml
```

**Glob match (C#):**
```bash
$ touch App.csproj
$ autorepro scan
Detected: csharp
- csharp  -> App.csproj
```

## Acceptance

- ✅ Output matches the examples above (header line + per-language details with `->`)
- ✅ Deterministic alphabetical ordering for both languages and reasons
- ✅ Exit code 0 on empty directory; no exceptions thrown
- ✅ Scan is root-only (non-recursive)
- ✅ CI: should be green on this PR (I will paste the Actions run URL once available)
