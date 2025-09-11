Mypy Strictness Ratchet

Goal: incrementally enable stricter mypy checks on stable modules without blocking day-to-day work.

Baseline (repo-wide)
- Permissive: untyped defs allowed, return Any allowed, tests/scripts/examples excluded.
- Rationale: allows adoption without churn across the whole codebase.

Strict Allowlist (kept green in CI)
- [x] `autorepro.__init__`
- [x] `autorepro.core.__init__`
- [x] `autorepro.render.__init__`
- [x] `autorepro.io.__init__`
- [x] `autorepro.config.__init__`
- [x] `autorepro.render.formats`
- [x] `autorepro.report`

How to add a module to strict
1) Ensure the module has type annotations (no untyped defs) and no `Any` returns.
2) Add a section to `mypy.ini`:

```
[mypy-<module.dotted.path>]
disallow_untyped_defs = True
check_untyped_defs = True
warn_return_any = True
```

3) Run: `pre-commit run mypy --all-files` and fix any findings.
4) Submit PR with the config change and the fixes.

Candidate modules (next up)
- [ ] `autorepro/render/*` (other helpers)
- [ ] `autorepro/project_config.py`
- [ ] `autorepro/config/models.py`
- [ ] `autorepro/core/planning.py` (once signatures are finalized)
- [ ] `autorepro/rules.py`

Notes
- Tests, scripts, and examples remain excluded from mypy. Avoid moving production logic there.
- If third-party typing gaps arise, prefer `types-<pkg>` stubs or narrow `# type: ignore[...]` with error codes.
