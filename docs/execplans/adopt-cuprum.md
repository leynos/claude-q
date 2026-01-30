# Replace subprocess and plumbum with cuprum

This ExecPlan is a living document. The sections `Constraints`, `Tolerances`,
`Risks`, `Progress`, `Surprises & Discoveries`, `Decision Log`, and
`Outcomes & Retrospective` must be kept up to date as work proceeds.

Status: DRAFT

PLANS.md is not present in this repository.

## Purpose / Big Picture

Replace all runtime usage of `subprocess` and `plumbum` with `cuprum` v0.1.0 so
command execution is centralized, typed, and allowlist-aware. Users should see
no behaviour changes: git-derived topics, editor launches, and hook outputs
remain identical, while developers gain a single execution path that is easier
to test and observe. Success is observable when all tests pass and the CLI and
hook flows behave the same as before (including exit codes and stdout/stderr).

## Constraints

- Use `cuprum` v0.1.0 for all command execution; do not leave any direct
  `subprocess` or `plumbum` usage in code, tests, or docs.
- Preserve public CLI behaviour and hook exit codes; do not change flags,
  prompts, or queue file formats.
- Keep Python compatibility at >=3.13 and follow repository tooling via
  Makefile targets.
- Documentation updates must follow the repo style guide and be formatted with
  `make fmt`.
- Do not change unrelated modules or refactor beyond what is required to
  switch execution backends.

## Tolerances (Exception Triggers)

- Scope: if replacing execution requires edits to more than 14 files or more
  than 450 net lines, stop and escalate.
- Dependencies: if any new external dependency beyond `cuprum` v0.1.0 is
  required, stop and escalate.
- Interface: if any public CLI or hook interface must change, stop and
  escalate.
- Capability: if cuprum cannot support required input/stdout handling without
  a behaviour change, stop and escalate with options.
- Iterations: if tests still fail after two fix attempts, stop and escalate.
- Ambiguity: if multiple valid catalogue/allowlist designs change behaviour,
  stop and request a decision.

## Risks

- Risk: `DEFAULT_CATALOGUE` may not include `git` or common editors, requiring
  a custom `ProgramCatalogue`. Severity: medium Likelihood: medium Mitigation:
  inspect cuprum catalogue and create a project-specific catalogue with
  explicit programs.
- Risk: cuprum's API for stdin input may differ from `subprocess.run`, which
  could affect `run_command` semantics. Severity: low Likelihood: low
  Mitigation: confirm whether input is used; adjust signatures only if unused
  or supported by cuprum.
- Risk: tests currently patch plumbum objects and will need rework, increasing
  churn. Severity: low Likelihood: medium Mitigation: introduce a small wrapper
  function to patch in tests rather than mocking cuprum internals.
- Risk: docs mention plumbum in multiple places, which may be missed.
  Severity: low Likelihood: medium Mitigation: run a repo-wide search for
  `plumbum` and `subprocess` strings and update all references.

## Progress

- [x] (2026-01-30 00:00Z) Drafted plan and identified current usage sites.
- [ ] Update tests to reflect cuprum-backed execution.
- [ ] Replace plumbum/subprocess usage in runtime code.
- [ ] Update documentation and dependency metadata.
- [ ] Run formatting, linting, typecheck, and tests.

## Surprises & Discoveries

- None yet.

## Decision Log

- Decision: introduce a small cuprum wrapper module to centralize command
  construction and make testing deterministic. Rationale: reduces duplication
  across git helpers and editor invocation while keeping call sites simple to
  update. Date/Author: 2026-01-30 (assistant)

## Outcomes & Retrospective

- Pending.

## Context and Orientation

Current command execution is split across two libraries:

- `claude_q/git_integration.py` uses `plumbum.cmd.git` for git metadata.
- `claude_q/hooks/_git_subprocess.py` uses `subprocess.run` to run git commands
  for hook contexts with explicit `cwd`.
- `claude_q/cli/helpers.py` uses `plumbum.local` to launch the user's editor.
- `tests/test_git_integration.py` patches the plumbum `git` object directly.
- Dependencies are declared in `pyproject.toml` and locked in `uv.lock`.
- Docs referencing plumbum include `README.md` and
  `docs/scripting-standards.md`.

Cuprum usage guidance and APIs are documented in `docs/cuprum-users-guide.md`.

## Plan of Work

Stage A: inventory and design (no code changes). Confirm cuprum catalogue
contents and decide whether to use `DEFAULT_CATALOGUE` or a project-specific
`ProgramCatalogue` for `git` and editor commands. Identify all plumbum and
subprocess references (code, tests, docs) and list the files to update.

Stage B: tests first. Update `tests/test_git_integration.py` to patch the new
cuprum wrapper rather than plumbum. If a new helper module is added, create
unit tests for its behaviour (success, non-zero exit, and error handling).
Confirm tests fail before implementation changes.

Stage C: implementation. Add a cuprum wrapper module (see Interfaces section)
that builds `SafeCmd` instances and runs them synchronously with optional
`cwd`. Replace plumbum usage in `claude_q/git_integration.py` and
`claude_q/cli/helpers.py` with the wrapper. Replace subprocess usage in
`claude_q/hooks/_git_subprocess.py` with the same wrapper (or a git-specific
wrapper built on it). Keep return values and error semantics identical.

Stage D: dependency and documentation updates. Replace `plumbum` with
`cuprum==0.1.0` in `pyproject.toml`, regenerate `uv.lock`, and update docs to
reference cuprum instead of plumbum (including README and scripting standards).
Update any docstrings mentioning subprocess/plumbum.

Each stage ends with validation; do not proceed if the stage's validation fails.

## Concrete Steps

1. Inventory and catalogue check (run from repo root):

    rg "plumbum" -n
    rg "subprocess" -n
    python -c "import cuprum; print(cuprum.DEFAULT_CATALOGUE)"

    Use a REPL for the same inspection if preferred.

2. Update tests (stage B):

    - Modify `tests/test_git_integration.py` to patch the new cuprum wrapper
      function or class instead of `plumbum.cmd.git`.
    - Add new unit tests for the wrapper module if created.
    - Run tests and confirm expected failures before implementation changes.

3. Implement cuprum wrapper and replace usage (stage C):

    - Add new helper module and update imports in:
      - `claude_q/git_integration.py`
      - `claude_q/hooks/_git_subprocess.py`
      - `claude_q/cli/helpers.py`
    - Ensure `ExecutionContext(cwd=...)` is used where needed.
    - Preserve existing output parsing and error handling.

4. Update dependencies and docs (stage D):

    - Edit `pyproject.toml` to replace plumbum with `cuprum==0.1.0`.
    - Regenerate `uv.lock` using the project's lock workflow.
    - Update `README.md`, `docs/scripting-standards.md`, and any docstrings to
      reference cuprum.

5. Validate quality gates (use tee for logs):

    make fmt | tee /tmp/fmt-$(get-project)-$(git branch --show).out
    make markdownlint | tee /tmp/markdownlint-$(get-project)-$(git branch --show).out
    make nixie | tee /tmp/nixie-$(get-project)-$(git branch --show).out
    make lint | tee /tmp/lint-$(get-project)-$(git branch --show).out
    make typecheck | tee /tmp/typecheck-$(get-project)-$(git branch --show).out
    make test | tee /tmp/test-$(get-project)-$(git branch --show).out

## Validation and Acceptance

Quality criteria (what done means):

- Tests: `make test` passes; git integration tests use cuprum-backed mocks and
  cover success and failure branches.
- Lint/typecheck: `make lint` and `make typecheck` pass.
- Formatting: `make fmt`, `make markdownlint`, and `make nixie` pass.
- Behaviour: running the CLI and hooks still derives the same topic strings and
  opens the editor as before.

Acceptance checks:

- `claude_q/git_integration.py` and `claude_q/hooks/_git_subprocess.py` use
  cuprum with no direct `plumbum` or `subprocess` imports.
- `claude_q/cli/helpers.py` launches the editor via cuprum and preserves error
  messaging on non-zero exit.
- `pyproject.toml` lists `cuprum==0.1.0` and no `plumbum` dependency.
- Docs and README contain no references to plumbum, and any subprocess
  mentions reflect cuprum usage context.

## Idempotence and Recovery

All steps are repeatable. If a command fails, fix the underlying issue and
re-run the same stage. If formatting changes reflow unrelated files, keep the
changes together with the plan's commit to maintain consistency. If a cuprum
API gap is discovered, stop and escalate before changing behaviour.

## Artifacts and Notes

- Store command logs under `/tmp` using the naming convention in the concrete
  steps.
- Keep a short transcript of any failed cuprum prototype steps here once
  discovered.

## Interfaces and Dependencies

Create a thin wrapper module to isolate cuprum usage, for example:

- `claude_q/command_runner.py`:
  - `build_catalogue(programs: Iterable[Program]) -> ProgramCatalogue` using
    `ProjectSettings(name="claude-q", programs=…, documentation_locations=(
    "docs/cuprum-users-guide.md",), noise_rules=())`.
  - `run_sync(program: Program, args: Sequence[str], *, cwd: Path | None =
    None) -> CommandResult` that builds `SafeCmd` via `sh.make`, runs it with
    `ExecutionContext(cwd=...)`, and returns the result.

Call sites:

- `claude_q/git_integration.py` should call `run_sync(GIT, ["remote"])` and
  parse `result.stdout` with exit-code checks.
- `claude_q/hooks/_git_subprocess.py` should reuse the same wrapper but pass
  `cwd` explicitly.
- `claude_q/cli/helpers.py` should resolve the editor command, then call
  `run_sync(Program(editor_bin), editor_args + [file_path])` and handle
  non-zero exit codes.

Dependency updates:

- Replace `plumbum` with `cuprum==0.1.0` in `pyproject.toml` and regenerate
  `uv.lock`.

## Revision note

Initial draft created to guide cuprum migration and testing strategy.
