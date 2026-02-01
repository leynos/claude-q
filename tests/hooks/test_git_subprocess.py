"""Tests for claude_q.hooks._git_subprocess."""

from __future__ import annotations

import dataclasses as dc
import typing as typ
from unittest import mock

import pytest

from claude_q.command_runner import RunOptions
from claude_q.hooks import _git_subprocess

if typ.TYPE_CHECKING:
    from pathlib import Path


@dc.dataclass(frozen=True)
class FakeResult:
    """Minimal cuprum-like command result for hook helpers."""

    stdout: str = ""
    ok: bool = True
    exit_code: int = 0


def test_run_command_rejects_input_text(tmp_path: Path) -> None:
    """Ensure stdin text is rejected for hook helpers."""
    with pytest.raises(ValueError, match="stdin input"):
        _git_subprocess.run_command(["git", "status"], str(tmp_path), input_text="hi")


def test_run_command_rejects_empty_cmd(tmp_path: Path) -> None:
    """Ensure empty commands are rejected."""
    with pytest.raises(ValueError, match="must not be empty"):
        _git_subprocess.run_command([], str(tmp_path))


def test_run_command_rejects_non_git_cmd(tmp_path: Path) -> None:
    """Ensure non-git commands are rejected."""
    with pytest.raises(ValueError, match="only git commands"):
        _git_subprocess.run_command(["echo", "hi"], str(tmp_path))


def test_run_command_executes_git_command() -> None:
    """Ensure git commands are delegated to the runner."""
    sentinel = FakeResult(stdout="ok")
    with mock.patch(
        "claude_q.hooks._git_subprocess.run_sync",
        return_value=sentinel,
    ) as mock_run:
        result = _git_subprocess.run_command(["git", "status"], "/repo")

    assert result is sentinel, "returns command result"
    mock_run.assert_called_once_with(
        _git_subprocess.GIT,
        ["status"],
        options=RunOptions(cwd="/repo"),
    )
