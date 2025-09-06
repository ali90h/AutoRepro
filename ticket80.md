Priority 1: CLI Functions (autorepro/cli.py) - 9 violations

  A. cmd_plan() - PLR0913 (10 > 5 arguments)

  Change: Apply config object pattern (already has PlanConfig dataclass)

  def cmd_plan(config: PlanConfig | None = None, **kwargs) -> int:
      """Handle the plan command."""
      if config is None:
          # Create from kwargs for backward compatibility
          config = PlanConfig(
              desc=kwargs.get("desc"),
              file=kwargs.get("file"),
              out=kwargs.get("out", config.paths.default_plan_file),
              force=kwargs.get("force", False),
              max_commands=kwargs.get("max_commands", config.limits.max_plan_suggestions),
              format_type=kwargs.get("format_type", "md"),
              dry_run=kwargs.get("dry_run", False),
              repo=kwargs.get("repo"),
              strict=kwargs.get("strict", False),
              min_score=kwargs.get("min_score", config.limits.min_score_threshold),
          )

      try:
          validated_config = _prepare_plan_config(config)
          plan_data = _generate_plan_content(validated_config)
          return _output_plan_result(plan_data, validated_config)
      except ValueError as e:
          if "min-score" in str(e):
              return 1  # Strict mode failure
          else:
              return 2  # Configuration error
      except OSError:
          return 1  # File I/O error

  B. cmd_init() - C901 (16 complexity), PLR0911 (9 returns), PLR0912 (18 branches)

  Change: Apply extract method pattern

  @dataclass
  class InitConfig:
      """Configuration for init command operations."""
      force: bool = False
      out: str | None = None
      dry_run: bool = False
      repo: str | None = None
      repo_path: Path | None = None
      print_to_stdout: bool = False

  def _validate_init_repo_path(config: InitConfig) -> int | None:
      """Validate repo path for init command. Returns error code if invalid."""
      if config.repo is None:
          return None

      try:
          config.repo_path = Path(config.repo).resolve()
          if not config.repo_path.is_dir():
              print(f"Error: --repo path does not exist or is not a directory: {config.repo}", file=sys.stderr)
              return 2
          return None
      except (OSError, ValueError):
          print(f"Error: --repo path does not exist or is not a directory: {config.repo}", file=sys.stderr)
          return 2

  def _prepare_init_output_path(config: InitConfig) -> None:
      """Prepare output path for init command."""
      if config.out is None:
          if config.repo_path:
              config.out = str(config.repo_path / ".devcontainer" / "devcontainer.json")
          else:
              config.out = ".devcontainer/devcontainer.json"

      config.print_to_stdout = config.out == "-"
      if config.dry_run:
          config.print_to_stdout = True

  def _handle_init_stdout_output(devcontainer_config: dict) -> int:
      """Handle stdout output for init command."""
      import json
      json_content = json.dumps(devcontainer_config, indent=2, sort_keys=True)
      json_content = ensure_trailing_newline(json_content)
      print(json_content, end="")
      return 0

  def _validate_init_output_path(config: InitConfig) -> int | None:
      """Validate output path for init command. Returns error code if invalid."""
      if config.out and os.path.isdir(config.out):
          print(f"Error: Output path is a directory: {config.out}")
          return 2

      if config.out and os.path.exists(config.out) and not config.force:
          print(f"devcontainer.json already exists at {config.out}.")
          print("Use --force to overwrite or --out <path> to write elsewhere.")
          return 0

      return None

  def _execute_init_write(config: InitConfig, devcontainer_config: dict) -> int:
      """Execute devcontainer write operation."""
      log = logging.getLogger("autorepro")

      try:
          result_path, diff_lines = write_devcontainer(devcontainer_config, force=config.force, out=config.out)

          if config.force and diff_lines is not None:
              print(f"Overwrote devcontainer at {result_path}")
              if diff_lines:
                  print("Changes:")
                  for line in diff_lines:
                      print(line)
              else:
                  print("No changes.")
          else:
              print(f"Wrote devcontainer to {result_path}")
          return 0

      except DevcontainerExistsError as e:
          print(f"devcontainer.json already exists at {e.path}.")
          print("Use --force to overwrite or --out <path> to write elsewhere.")
          return 0
      except DevcontainerMisuseError as e:
          log.error(f"Error: {e.message}")
          return 2
      except (OSError, PermissionError) as e:
          log.error(f"Error: {e}")
          return 1

  def cmd_init(
      force: bool = False,
      out: str | None = None,
      dry_run: bool = False,
      repo: str | None = None,
  ) -> int:
      """Handle the init command."""
      config = InitConfig(force=force, out=out, dry_run=dry_run, repo=repo)

      # Validate repo path
      error = _validate_init_repo_path(config)
      if error is not None:
          return error

      # Prepare output path
      _prepare_init_output_path(config)

      # Get devcontainer configuration
      devcontainer_config = default_devcontainer()

      # Handle stdout output
      if config.print_to_stdout:
          return _handle_init_stdout_output(devcontainer_config)

      # Validate output path
      error = _validate_init_output_path(config)
      if error is not None:
          return error

      # Execute write operation
      return _execute_init_write(config, devcontainer_config)

  C. cmd_exec() - PLR0913 (12 arguments), PLR0911 (8 returns)

  Change: Already uses ExecConfig, just need to refactor function signature

  def cmd_exec(config: ExecConfig | None = None, **kwargs) -> int:
      """Handle the exec command."""
      if config is None:
          config = ExecConfig(
              desc=kwargs.get("desc"),
              file=kwargs.get("file"),
              repo=kwargs.get("repo"),
              index=kwargs.get("index", 0),
              timeout=kwargs.get("timeout", config.timeouts.default_seconds),
              env_vars=kwargs.get("env_vars"),
              env_file=kwargs.get("env_file"),
              tee_path=kwargs.get("tee_path"),
              jsonl_path=kwargs.get("jsonl_path"),
              dry_run=kwargs.get("dry_run", False),
              min_score=kwargs.get("min_score", config.limits.min_score_threshold),
              strict=kwargs.get("strict", False),
          )

      # Rest of function remains the same...
      # (Current implementation already properly handles returns)

  D. cmd_pr() - PLR0913 (22 arguments)

  Change: Already uses PrConfig, refactor function signature

  def cmd_pr(config: PrConfig | None = None, **kwargs) -> int:
      """Handle the pr command."""
      if config is None:
          config = PrConfig(
              desc=kwargs.get("desc"),
              file=kwargs.get("file"),
              title=kwargs.get("title"),
              body=kwargs.get("body"),
              repo_slug=kwargs.get("repo_slug"),
              update_if_exists=kwargs.get("update_if_exists", False),
              skip_push=kwargs.get("skip_push", False),
              ready=kwargs.get("ready", False),
              label=kwargs.get("label"),
              assignee=kwargs.get("assignee"),
              reviewer=kwargs.get("reviewer"),
              min_score=kwargs.get("min_score", config.limits.min_score_threshold),
              strict=kwargs.get("strict", False),
              comment=kwargs.get("comment", False),
              update_pr_body=kwargs.get("update_pr_body", False),
              link_issue=int(kwargs["link_issue"]) if kwargs.get("link_issue") else None,
              add_labels=kwargs.get("add_labels"),
              attach_report=kwargs.get("attach_report", False),
              summary=kwargs.get("summary"),
              no_details=kwargs.get("no_details", False),
              format_type=kwargs.get("format_type", "md"),
              dry_run=kwargs.get("dry_run", False),
          )

      try:
          validated_config = _prepare_pr_config(config)
          pr_number = _find_existing_pr(validated_config)

          if validated_config.dry_run:
              _handle_pr_dry_run(validated_config, pr_number)
              return 0

          return _execute_pr_operations(validated_config, pr_number)
      except ValueError:
          return 2  # Configuration error
      except (OSError, RuntimeError):
          return 1  # Runtime error

  E. main() - C901 (12 complexity), PLR0911 (8 returns), PLR0912 (13 branches)

  Change: Extract command dispatch to helper functions

  def _setup_logging(args) -> None:
      """Setup logging configuration based on args."""
      if hasattr(args, "quiet") and args.quiet:
          level = logging.ERROR
      elif hasattr(args, "verbose"):
          if args.verbose >= 2:
              level = logging.DEBUG
          elif args.verbose == 1:
              level = logging.INFO
          else:
              level = logging.WARNING
      else:
          level = logging.WARNING

      logging.basicConfig(level=level, format="%(message)s", stream=sys.stderr)

  def _dispatch_scan_command(args) -> int:
      """Dispatch scan command."""
      return cmd_scan(
          json_output=getattr(args, "json", False),
          show_scores=getattr(args, "show_scores", False),
      )

  def _dispatch_init_command(args) -> int:
      """Dispatch init command."""
      return cmd_init(
          force=args.force,
          out=args.out,
          dry_run=args.dry_run,
          repo=args.repo,
      )

  def _dispatch_plan_command(args) -> int:
      """Dispatch plan command."""
      return cmd_plan(
          desc=args.desc,
          file=args.file,
          out=args.out,
          force=args.force,
          max_commands=args.max,
          format_type=args.format,
          dry_run=args.dry_run,
          repo=args.repo,
          strict=args.strict,
          min_score=args.min_score,
      )

  def _dispatch_exec_command(args) -> int:
      """Dispatch exec command."""
      return cmd_exec(
          desc=args.desc,
          file=args.file,
          repo=args.repo,
          index=args.index,
          timeout=args.timeout,
          env_vars=args.env,
          env_file=args.env_file,
          tee_path=args.tee,
          jsonl_path=args.jsonl,
          dry_run=args.dry_run,
          min_score=args.min_score,
          strict=args.strict,
      )

  def _dispatch_pr_command(args) -> int:
      """Dispatch pr command."""
      return cmd_pr(
          desc=args.desc,
          file=args.file,
          title=args.title,
          body=args.body,
          repo_slug=args.repo_slug,
          update_if_exists=args.update_if_exists,
          skip_push=args.skip_push,
          ready=args.ready,
          label=args.label,
          assignee=args.assignee,
          reviewer=args.reviewer,
          min_score=args.min_score,
          strict=args.strict,
          comment=getattr(args, "comment", False),
          update_pr_body=getattr(args, "update_pr_body", False),
          link_issue=getattr(args, "link_issue", None),
          add_labels=getattr(args, "add_labels", None),
          attach_report=getattr(args, "attach_report", False),
          summary=getattr(args, "summary", None),
          no_details=getattr(args, "no_details", False),
          format_type=getattr(args, "format", "md"),
          dry_run=args.dry_run,
      )

  def main(argv: list[str] | None = None) -> int:
      parser = create_parser()
      try:
          args = parser.parse_args(argv)
      except SystemExit as e:
          code = e.code
          return code if isinstance(code, int) else (0 if code is None else 2)

      _setup_logging(args)
      log = logging.getLogger("autorepro")

      try:
          if args.command == "scan":
              return _dispatch_scan_command(args)
          elif args.command == "init":
              return _dispatch_init_command(args)
          elif args.command == "plan":
              return _dispatch_plan_command(args)
          elif args.command == "exec":
              return _dispatch_exec_command(args)
          elif args.command == "pr":
              return _dispatch_pr_command(args)

          parser.print_help()
          return 0

      except (OSError, PermissionError) as e:
          log.error(f"Error: {e}")
          return 1

  Priority 2: Other Complex Functions

  F. write_devcontainer() in autorepro/env.py

  Change: Extract method pattern to reduce complexity/statements

  def _validate_devcontainer_path(out: str | None) -> Path:
      """Validate and resolve output path for devcontainer."""
      if out is None:
          out_path = Path(".devcontainer/devcontainer.json")
      else:
          out_path = Path(out)

      if out_path.is_dir():
          raise DevcontainerMisuseError(f"Output path is a directory: {out_path}")

      return out_path.resolve()

  def _check_devcontainer_exists(out_path: Path, force: bool) -> tuple[bool, list[str] | None]:
      """Check if devcontainer exists and handle force mode."""
      if out_path.exists():
          if not force:
              raise DevcontainerExistsError(str(out_path))

          # Read existing content for diff
          try:
              with open(out_path, encoding="utf-8") as f:
                  existing_content = f.read()
              return True, existing_content.splitlines()
          except (OSError, json.JSONDecodeError):
              return True, None

      return False, None

  def _create_devcontainer_directories(out_path: Path) -> None:
      """Ensure parent directories exist for devcontainer."""
      parent_dir = out_path.parent
      if not parent_dir.exists():
          parent_dir.mkdir(parents=True, exist_ok=True)

  def _write_devcontainer_content(out_path: Path, content: dict) -> str:
      """Write devcontainer content to file."""
      json_content = json.dumps(content, indent=2, sort_keys=True)
      json_content = ensure_trailing_newline(json_content)

      FileOperations.atomic_write(out_path, json_content)
      return json_content

  def _compute_content_diff(existing_lines: list[str] | None, new_content: str) -> list[str]:
      """Compute diff between existing and new content."""
      if existing_lines is None:
          return []

      new_lines = new_content.splitlines()
      diff = list(unified_diff(
          existing_lines,
          new_lines,
          fromfile="existing",
          tofile="new",
          lineterm=""
      ))
      return diff

  def write_devcontainer(
      content: dict[str, str | dict[str, dict[str, str]]],
      force: bool = False,
      out: str | None = None,
  ) -> tuple[Path, list[str] | None]:
      """Write devcontainer configuration to file with atomic and idempotent behavior."""
      # Validate output path
      out_path = _validate_devcontainer_path(out)

      # Check if file exists and handle force mode
      file_exists, existing_lines = _check_devcontainer_exists(out_path, force)

      # Create parent directories
      _create_devcontainer_directories(out_path)

      # Write content
      new_content = _write_devcontainer_content(out_path, content)

      # Compute diff if file existed
      if file_exists and existing_lines is not None:
          diff_lines = _compute_content_diff(existing_lines, new_content)
          return out_path, diff_lines

      return out_path, None

  G. build_pr_body() in autorepro/pr.py

  Change: Extract method pattern

  def _extract_pr_title_from_content(plan_content: str, format_type: str) -> str:
      """Extract title from plan content for PR."""
      if format_type == "json":
          try:
              plan_data = json.loads(plan_content)
              return plan_data.get("title", "Reproduction Plan")
          except json.JSONDecodeError:
              return "Reproduction Plan"
      else:
          lines = plan_content.split("\n")
          title_line = next((line for line in lines if line.startswith("# ")), "# Reproduction Plan")
          return title_line[2:].strip()

  def _build_pr_header_section(title: str) -> list[str]:
      """Build PR header section."""
      return [
          f"## 🔄 {title}",
          "",
          "**Summary**: AutoRepro reproduction plan for this PR",
          "",
      ]

  def _build_pr_content_section(plan_content: str, format_type: str) -> list[str]:
      """Build PR content section with appropriate formatting."""
      content_lines = plan_content.strip().split("\n")
      should_use_details = len(content_lines) > 15

      if should_use_details:
          return [
              "<!-- autorepro:begin plan schema=1 -->",
              "<details>",
              "<summary>📋 Reproduction Plan (click to expand)</summary>",
              "",
              plan_content.rstrip(),
              "",
              "</details>",
              "<!-- autorepro:end plan -->",
          ]
      else:
          return [
              "<!-- autorepro:begin plan schema=1 -->",
              plan_content.rstrip(),
              "<!-- autorepro:end plan -->",
          ]

  def _build_pr_footer_section() -> list[str]:
      """Build PR footer section."""
      timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
      return [
          "",
          f"Generated by [AutoRepro](https://github.com/autorepro/autorepro) on {timestamp}",
          f"<!-- generated: {timestamp} -->",
      ]

  def build_pr_body(plan_content: str, format_type: str) -> str:
      """Build PR body from plan content."""
      title = _extract_pr_title_from_content(plan_content, format_type)

      header_lines = _build_pr_header_section(title)
      content_lines = _build_pr_content_section(plan_content, format_type)
      footer_lines = _build_pr_footer_section()

      all_lines = header_lines + content_lines + footer_lines
      return "\n".join(all_lines)

  H. process_plan_input() in autorepro/utils/plan_processing.py

  Change: Extract method pattern

  def _read_plan_input_content(desc_or_file: str | None, repo_path: Path) -> str:
      """Read input content from description or file."""
      if desc_or_file is None:
          raise ValueError("Input description or file is required")

      if desc_or_file.startswith("@"):
          # File input
          file_path = desc_or_file[1:]
          full_path = repo_path / file_path if not Path(file_path).is_absolute() else Path(file_path)

          try:
              with open(full_path, encoding="utf-8") as f:
                  return f.read()
          except OSError as e:
              raise OSError(f"Failed to read input file {file_path}: {e}") from e
      else:
          # Direct description
          return desc_or_file

  def _process_plan_keywords_and_languages(text: str, repo_path: Path) -> tuple[set[str], list[str]]:
      """Process text to extract keywords and detect languages."""
      normalized_text = normalize(text)
      keywords = extract_keywords(normalized_text)

      with temp_chdir(repo_path):
          detected_languages = detect_languages(".")

      lang_names = [lang for lang, _ in detected_languages]
      return keywords, lang_names

  def _generate_plan_command_suggestions(keywords: set[str], lang_names: list[str], min_score: int) -> list:
      """Generate command suggestions from keywords and languages."""
      return suggest_commands(keywords, lang_names, min_score)

  def _build_plan_assumptions(lang_names: list[str], keywords: set[str]) -> list[str]:
      """Build assumptions based on detected languages and keywords."""
      assumptions = []

      if lang_names:
          lang_list = ", ".join(lang_names)
          assumptions.append(f"Project uses {lang_list} based on detected files")
      else:
          assumptions.append("Standard development environment")

      if has_test_keywords(keywords):
          assumptions.append("Issue is related to testing")
      if has_ci_keywords(keywords):
          assumptions.append("Issue occurs in CI/CD environment")
      if has_installation_keywords(keywords):
          assumptions.append("Installation or setup may be involved")

      if not assumptions:
          assumptions.append("Issue can be reproduced locally")

      return assumptions

  def _build_plan_environment_needs(lang_names: list[str], repo_path: Path) -> list[str]:
      """Build environment needs based on detected languages."""
      needs = []

      # Check for devcontainer
      devcontainer_paths = [
          repo_path / ".devcontainer/devcontainer.json",
          repo_path / "devcontainer.json"
      ]

      if any(p.exists() for p in devcontainer_paths):
          needs.append("devcontainer: present")

      for lang in lang_names:
          if lang == "python":
              needs.append("Python 3.7+")
          elif lang in ("node", "javascript"):
              needs.append("Node.js 16+")
              needs.append("npm or yarn")
          elif lang == "go":
              needs.append("Go 1.19+")

      if not needs:
          needs.append("Standard development environment")

      return needs

  def process_plan_input(desc_or_file: str | None, repo_path: Path, min_score: int = 0) -> PlanData:
      """Process plan input and generate common plan components."""
      # Read input content
      text = _read_plan_input_content(desc_or_file, repo_path)
      normalized_text = normalize(text)

      # Process keywords and detect languages
      keywords, lang_names = _process_plan_keywords_and_languages(text, repo_path)

      # Generate suggestions
      suggestions = _generate_plan_command_suggestions(keywords, lang_names, min_score)

      # Build plan components
      title = normalized_text.split()[:8]
      title = " ".join(title).title() if title else "Issue Reproduction Plan"

      assumptions = _build_plan_assumptions(lang_names, keywords)
      needs = _build_plan_environment_needs(lang_names, repo_path)

      next_steps = [
          "Run the suggested commands in order of priority",
          "Check logs and error messages for patterns",
          "Review environment setup if commands fail",
          "Document any additional reproduction steps found",
      ]

      return PlanData(
          title=title,
          assumptions=assumptions,
          suggestions=suggestions,
          needs=needs,
          next_steps=next_steps,
          normalized_text=normalized_text,
          keywords=keywords,
          lang_names=lang_names,
      )

  Priority 3: Simple Argument Count Fixes

  I. _write_exec_output_logs() in autorepro/report.py

  Change: Create config object

  @dataclass
  class ExecOutputConfig:
      """Configuration for exec output logging."""
      log_path: Path
      jsonl_path: Path
      command_str: str
      index: int
      cwd: Path
      start_iso: str
      duration_ms: int
      exit_code: int
      timed_out: bool
      stdout_full: str
      stderr_full: str

  def _write_exec_output_logs(config: ExecOutputConfig) -> None:
      """Write execution output to log files."""
      # Implementation stays the same, just uses config.field instead of parameters

  J. render_sync_comment() in autorepro/sync.py

  Change: Already has SyncCommentConfig, just ensure backward compatibility

  # This function already has proper config object pattern with backward compatibility
  # No changes needed if already implemented in ticket #78

  K. safe_subprocess_run() in autorepro/utils/process.py

  Change: Create config object

  @dataclass
  class SubprocessConfig:
      """Configuration for subprocess execution."""
      cmd: str | list[str]
      cwd: str | Path | None = None
      env: dict | None = None
      timeout: int | None = None
      capture_output: bool = True
      text: bool = True
      check: bool = False

  def safe_subprocess_run(config: SubprocessConfig) -> subprocess.CompletedProcess:
      """Run subprocess with safe configuration."""
      return subprocess.run(
          config.cmd,
          cwd=config.cwd,
          env=config.env,
          timeout=config.timeout,
          capture_output=config.capture_output,
          text=config.text,
          check=config.check,
      )

  4. Step-by-Step Implementation Instructions

⏺ Phase 1: CLI Function Refactoring (autorepro/cli.py)

  1. Add InitConfig dataclass (after line 588)
  2. Refactor cmd_plan() - Apply config object pattern (lines 895-931)
  3. Refactor cmd_init() - Extract 5 helper functions (lines 933-1029)
  4. Refactor cmd_exec() - Apply config object pattern (lines 1326-1409)
  5. Refactor cmd_pr() - Apply config object pattern (lines 1572-1636)
  6. Refactor main() - Extract 6 dispatch functions (lines 1638-1704)

  Phase 2: Complex Function Refactoring

  1. autorepro/env.py - Refactor write_devcontainer() (lines 168+)
    - Extract 6 helper functions
    - Reduce from 56 to ~15 statements
  2. autorepro/pr.py - Refactor build_pr_body() (lines 51+)
    - Extract 4 helper functions
    - Reduce from 61 to ~10 statements
  3. autorepro/utils/plan_processing.py - Refactor process_plan_input() (lines 29+)
    - Extract 6 helper functions
    - Reduce from 63 to ~15 statements

  Phase 3: Simple Argument Fixes

  1. autorepro/report.py - Add ExecOutputConfig and refactor _write_exec_output_logs()
  2. autorepro/utils/process.py - Add SubprocessConfig and refactor safe_subprocess_run()

  Phase 4: Configuration Updates

  1. Update main() call sites - Ensure all command calls use new signatures
  2. Update pyproject.toml - Convert Ruff rules from warnings to errors
  3. Update baseline_metrics.txt - Document Phase 8 completion

  5. Testing Validation Plan

⏺ Pre-Implementation Validation:

  # Capture current test status
  python -m pytest tests/ -v > test_results_before.txt
  python -m pytest tests/ -x --tb=short  # Quick fail check

  # Capture current Ruff violations
  ruff check autorepro/ --select=PLR0915,PLR0913,C901,PLR0912,PLR0911 > violations_before.txt

  # Verify current violation count
  grep -c "Found" violations_before.txt  # Should be 22

  During Implementation (After Each Phase):

  # Phase 1: CLI functions
  python -m pytest tests/ -k "test_cli" -v
  ruff check autorepro/cli.py --select=PLR0915,PLR0913,C901,PLR0912,PLR0911

  # Phase 2: Complex functions
  python -m pytest tests/ -k "env or pr or plan_processing" -v
  ruff check autorepro/env.py autorepro/pr.py autorepro/utils/plan_processing.py --select=C901,PLR0912,PLR0915

  # Phase 3: Simple fixes
  python -m pytest tests/ -v  # Full test suite
  ruff check autorepro/ --select=PLR0913

  Post-Implementation Validation:

  # Complete violation elimination check
  ruff check autorepro/ --select=PLR0915,PLR0913,C901,PLR0912,PLR0911
  # Expected: "All checks passed!"

  # Full test suite
  python -m pytest tests/ -v
  # Expected: All 540 tests pass

  # Functional CLI testing
  python -m autorepro --help
  python -m autorepro scan --help
  python -m autorepro plan --help
  python -m autorepro exec --help
  python -m autorepro pr --help

  # Integration tests
  python -m autorepro scan --json
  python -m autorepro plan --desc "test issue" --dry-run
  python -m autorepro init --dry-run

  Critical Validation Areas:

  1. All CLI commands - Behavior unchanged
  2. Argument parsing - No regressions in parameter handling
  3. Error handling - Exit codes preserved
  4. Config object compatibility - Backward compatibility maintained
  5. Complex function logic - Core business logic intact

⏺ Immediate Post-Completion Tasks:

  1. Code Quality Enforcement
    - Convert Ruff warning rules to errors in pyproject.toml
    - Add pre-commit hooks to prevent regression
    - Update CI/CD to enforce zero violations
  2. Documentation Updates
    - Update baseline_metrics.txt with Phase 8 completion
    - Document refactoring patterns used
    - Create developer guide for future refactoring
