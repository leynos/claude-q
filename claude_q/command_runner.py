"""Cuprum-backed command execution helpers.

This module centralises cuprum usage so call sites do not need to rebuild
catalogues or wire execution contexts manually.

Examples
--------
Run a git command with a specific working directory::

    from pathlib import Path

    from cuprum import Program

    from claude_q.command_runner import run_sync

    result = run_sync(Program("git"), ["status"], cwd=Path("."))
    if not result.ok:
        raise RuntimeError(result.stderr or "git failed")

"""

from __future__ import annotations

import dataclasses as dc
import typing as typ
from functools import cache

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

    from cuprum import SafeCmd

CUPRUM_DOCS = ("docs/cuprum-users-guide.md",)
PROJECT_NAME = "claude-q"
GIT = Program("git")


@dc.dataclass(frozen=True)
class RunOptions:
    """Settings for running a cuprum command.

    Attributes
    ----------
    cwd : Path | str | None
        Working directory for the command.
    env : dict[str, str] | None
        Environment variable overrides for the command.
    tags : dict[str, str] | None
        Tags to attach to cuprum execution events.
    echo : bool
        Whether to echo output to the configured sinks.
    capture : bool
        Whether to capture stdout and stderr.
    context : ExecutionContext | None
        Optional prebuilt execution context.

    """

    cwd: Path | str | None = None
    env: dict[str, str] | None = None
    tags: dict[str, str] | None = None
    echo: bool = False
    capture: bool = True
    context: ExecutionContext | None = None


def build_catalogue(programs: typ.Iterable[Program]) -> ProgramCatalogue:
    """Create a project catalogue for the provided programs.

    Parameters
    ----------
    programs : typing.Iterable[Program]
        Programs to include in the allowlist for the catalogue.

    Returns
    -------
    ProgramCatalogue
        Catalogue containing a single project with the provided programs.

    """
    return _catalogue_for(tuple(programs))


@cache
def _catalogue_for(programs: tuple[Program, ...]) -> ProgramCatalogue:
    """Return a cached project catalogue for the provided programs."""
    project = ProjectSettings(
        name=PROJECT_NAME,
        programs=programs,
        documentation_locations=CUPRUM_DOCS,
        noise_rules=(),
    )
    return ProgramCatalogue(projects=(project,))


@cache
def _builder_for(program: Program) -> typ.Callable[..., SafeCmd]:
    """Return a cached cuprum builder for the provided program."""
    catalogue = _catalogue_for((program,))
    return sh.make(program, catalogue=catalogue)


def run_sync(
    program: Program,
    args: typ.Sequence[str],
    *,
    options: RunOptions | None = None,
) -> CommandResult:
    """Run a cuprum command synchronously and return the result.

    Parameters
    ----------
    program : Program
        Program to execute.
    args : typing.Sequence[str]
        Command arguments excluding the program name.
    options : RunOptions | None, optional
        Settings for the execution, including cwd/env/tags and echo/capture
        behavior.

    Returns
    -------
    CommandResult
        Result of the command execution.

    """
    builder = _builder_for(program)
    cmd = builder(*args)
    opts = options or RunOptions()
    context = opts.context
    if context is None:
        context_kwargs: dict[str, typ.Any] = {}
        if opts.cwd is not None:
            context_kwargs["cwd"] = str(opts.cwd)
        if opts.env is not None:
            context_kwargs["env"] = opts.env
        if opts.tags is not None:
            context_kwargs["tags"] = opts.tags
        context = ExecutionContext(**context_kwargs)
    return cmd.run_sync(context=context, echo=opts.echo, capture=opts.capture)
