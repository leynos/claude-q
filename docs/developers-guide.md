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
or a Git source is missing. Do not edit it: the concordat `uv-gate-baseline`
rule audits its digest. `make prepare` installs the locked environment, and the
gates that need it depend on it. A Git-sourced tool that is not cached yet
needs uv 0.11.28 or newer; with an older uv, run the tool once with `uvx` to
warm the cache. Run `uv lock` by hand to change `uv.lock`; the gates never do.
