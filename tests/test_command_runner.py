"""Tests for claude_q.command_runner."""

from __future__ import annotations

import typing as typ
from unittest import mock

from cuprum import Program

if typ.TYPE_CHECKING:
    from pathlib import Path

from claude_q.command_runner import RunOptions, build_catalogue, run_sync


def test_build_catalogue_includes_program() -> None:
    """Ensure custom catalogues allow the provided program."""
    program = Program("git")
    catalogue = build_catalogue((program,))
    assert program in catalogue.allowlist, "catalogue includes program"


def test_run_sync_builds_command_and_runs_with_cwd(tmp_path: Path) -> None:
    """Ensure run_sync wires catalogue, args, and cwd into cuprum."""
    program = Program("git")
    args = ["status"]
    cwd = tmp_path
    sentinel_result = mock.Mock()

    cmd = mock.Mock()
    cmd.run_sync.return_value = sentinel_result
    builder = mock.Mock(return_value=cmd)

    with (
        mock.patch(
            "claude_q.command_runner._builder_for",
            return_value=builder,
        ) as mock_builder,
        mock.patch("claude_q.command_runner.ExecutionContext") as mock_context,
    ):
        ctx = mock_context.return_value
        options = RunOptions(cwd=cwd)
        result = run_sync(program, args, options=options)

    assert result is sentinel_result, "returns the command result"
    assert mock_builder.call_args_list == [mock.call(program)], (
        "uses cached builder for the program"
    )
    assert builder.call_args_list == [mock.call(*args)], "builds command argv"
    assert mock_context.call_args_list == [mock.call(cwd=str(cwd))], (
        "builds execution context from cwd"
    )
    assert cmd.run_sync.call_args_list == [
        mock.call(context=ctx, echo=False, capture=True)
    ], "runs command with default echo/capture settings"
