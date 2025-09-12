This PR implements consistent, structured logging across the codebase and satisfies ticket #86.

Summary
- Central utility `autorepro/utils/logging.py` with JSON and key=value text formatters.
- CLI configured via `configure_logging()`; honors `AUTOREPRO_LOG_FORMAT=json`.
- Decorators enriched with structured context (`operation`, `args`, `result`, `duration_s`).
- Replaced non-CLI `print()` with logging in rules and GitHub integrations.
- Docs updated with logging guidance.

Acceptance Criteria
- All modules use consistent logging patterns.
- No print() statements except CLI user output.
- Appropriate log levels used (DEBUG/INFO/WARNING/ERROR).
- Context included across messages; structured format supported (JSON).

Changes
- add: `autorepro/utils/logging.py`
- refactor: `autorepro/cli.py` logging setup
- refactor: `autorepro/utils/decorators.py` adds structured context
- refactor: `autorepro/rules.py` plugin load error handling uses logging
- refactor: `autorepro/utils/github_api.py`, `autorepro/io/github.py` dry-run prints -> INFO logs
- docs: `CONTRIBUTING.md` logging section

Usage
- Default text logs (stderr): key=value with timestamps.
- Structured logs: set `AUTOREPRO_LOG_FORMAT=json` in environment.
- Add context: `logging.getLogger("autorepro").info("msg", extra={"operation": "plan"})`

Closes #86
