"""Cuprum-backed command execution helpers."""

from __future__ import annotations

import typing as typ

from cuprum import (
    CommandResult,
    ExecutionContext,
    Program,
    ProgramCatalogue,
    ProjectSettings,
    sh,
)

if typ.TYPE_CHECKING:
    from pathlib import Path

CUPRUM_DOCS = ("docs/cuprum-users-guide.md",)
PROJECT_NAME = "claude-q"
GIT = Program("git")


def build_catalogue(programs: typ.Iterable[Program]) -> ProgramCatalogue:
    """Create a project catalogue for the provided programs."""
    program_list = tuple(programs)
    project = ProjectSettings(
        name=PROJECT_NAME,
        programs=program_list,
        documentation_locations=CUPRUM_DOCS,
        noise_rules=(),
    )
    return ProgramCatalogue(projects=(project,))


def run_sync(
    program: Program,
    args: typ.Sequence[str],
    *,
    cwd: Path | str | None = None,
) -> CommandResult:
    """Run a cuprum command synchronously and return the result."""
    catalogue = build_catalogue((program,))
    cmd = sh.make(program, catalogue=catalogue)(*args)
    context = ExecutionContext(cwd=str(cwd) if cwd is not None else None)
    return cmd.run_sync(context=context)
