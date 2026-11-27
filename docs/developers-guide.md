# Developers' guide

## Markdown formatting and lint

`make fmt` rewrites the Markdown files Git tracks, plus untracked files it does
not ignore, with `mdtablefix --in-place`, then runs `markdownlint-cli2 --fix`.
`make check-fmt` runs `mdtablefix --check` over the same selection with the
same rewrite flags (`MDTABLEFIX_SELECT` and `MDTABLEFIX_RULES` in the
`Makefile`). `make markdownlint` lints the Markdown files selected by the glob
and the ignore rules in `.markdownlint-cli2.jsonc`. Both `mdtablefix` (0.6.1 or
later) and `markdownlint-cli2` must be on `PATH`. Continuous Integration (CI)
installs `mdtablefix` 0.6.1 through the shared `install-mdtablefix` action and
lints through the pinned `markdownlint-cli2-action`. `.markdownlint-cli2.jsonc`
holds the rules, the ignores and `"gitignore": true`.

## Running uv through the helper

Every `uv` call in the Makefile except the spelling builder's goes through
`scripts/uv_gate.py`, a copy of the helper in
[shared-actions](https://github.com/leynos/shared-actions/tree/main/uv_gate).
It cleans the environment, uses the global uv cache, runs offline first, and
goes online at most once, only when uv proves a cache entry, a managed Python
or a Git source is missing. The copy is vendored byte for byte and is never
edited in place: the concordat `uv-gate-baseline` rule audits its digest, so
the repository's file-length and scripting-stack conventions do not apply to
it, and Ruff excludes it. `make prepare` installs the locked environment, and
every gate that runs the project depends on it. A caller's `UV=/path/to/uv` is
honoured by putting that uv's directory on `PATH`, so the executable must be
named `uv`. A Git-sourced tool that is not cached yet needs uv 0.11.28 or
newer; with an older uv, running the tool once with `uvx` warms the cache. The
one exception is `make spelling`, which runs `uv tool run` directly: the
concordat `spelling-config-baseline` rule requires the builder at a release
tag, which the helper's SHA-only pin check refuses, so that call does not get
the helper's environment cleaning or offline-first policy. `uv.lock` changes
only through a manual `uv lock`; the gates never change it.

## YAML lint

`make lint` runs `make yamllint` and `make actionlint` as prerequisites.
`make yamllint` runs `yamllint --strict` over every tracked `.yml` and `.yaml`
file, reading `.yamllint.yml`, which extends the estate base
`.yamllint-estate.yml` (a verbatim copy of the concordat canon; do not edit
it). The base ignores Helm chart templates (`**/charts/**/templates/`), so a
tracked file there is passed to yamllint but not checked, and a local `ignore`
in `.yamllint.yml` replaces that entry rather than adding to it. Run it from
the repository root, because yamllint resolves `extends` against the current
directory. `make actionlint` checks the GitHub Actions workflows, accepting the
runner labels in `.github/actionlint.yaml`, and runs ShellCheck over their Bash
and `sh` `run:` scripts when it is on `PATH` (it skips PowerShell steps).

Install the tools locally at the versions CI uses:
`uv tool install yamllint==1.38.0`, and the `actionlint` 1.7.12 and
`shellcheck` 0.11.0 release binaries (a package manager's builds can differ and
change what the lint reports). CI installs the same pinned versions with the
`install-yaml-lint` action of `leynos/shared-actions` before it runs
`make lint`. The `YAMLLINT` and `ACTIONLINT` variables name the commands when
they are not on `PATH`.
