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

Every `uv` call in the Makefile goes through `scripts/uv_gate.py`, a copy of
the helper in
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
newer; with an older uv, running the tool once with `uvx` warms the cache.
`uv.lock` changes only through a manual `uv lock`; the gates never change it.

## YAML lint

`make lint` runs `yamllint --strict` over every Git-tracked `*.yml` and
`*.yaml` file, then `actionlint` over the workflows, which also runs
`shellcheck` over their `run:` scripts. Install yamllint 1.38.0, actionlint
1.7.12 and shellcheck 0.11.0 locally, as CI does through the shared
`install-yaml-lint` action, so results agree. Run the targets from the
repository root: yamllint resolves `.yamllint.yml`, which extends the estate
base `.yamllint-estate.yml` (copied verbatim, never edited here), against the
working directory. `.github/actionlint.yaml` declares the `ubicloud-*` runner
labels. `tests/yaml_lint/` judges the Makefile and workflow wiring against
fixtures and then the real files, pins the estate base, and runs the Make
targets with stand-in tools (and the real yamllint when installed) to prove the
tracked-files list and that a tool failure fails its target.
