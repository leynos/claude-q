"""Tests for claude_q.command_runner."""

from __future__ import annotations

import typing as typ
from unittest import mock

from cuprum import Program

if typ.TYPE_CHECKING:
    from pathlib import Path

from claude_q.command_runner import build_catalogue, run_sync


def test_build_catalogue_includes_program() -> None:
    """Ensure custom catalogues allow the provided program."""
    program = Program("git")
    catalogue = build_catalogue((program,))
    assert program in catalogue.allowlist


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
            "claude_q.command_runner.build_catalogue",
            return_value="catalogue",
        ) as mock_build,
        mock.patch(
            "claude_q.command_runner.sh.make", return_value=builder
        ) as mock_make,
        mock.patch("claude_q.command_runner.ExecutionContext") as mock_context,
    ):
        ctx = mock_context.return_value
        result = run_sync(program, args, cwd=cwd)

    assert result is sentinel_result
    mock_build.assert_called_once_with((program,))
    mock_make.assert_called_once_with(program, catalogue="catalogue")
    builder.assert_called_once_with(*args)
    mock_context.assert_called_once_with(cwd=str(cwd))
    cmd.run_sync.assert_called_once_with(context=ctx)
