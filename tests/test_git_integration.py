r"""Tests for claude_q.git_integration.

Covers repository discovery, branch/remote parsing, and topic derivation. Git
interactions are mocked by patching the cuprum-backed command runner to return
fixed stdout or raise exceptions.

Examples
--------
Stub git command output::

    mock_run_sync.return_value = FakeResult(stdout="origin\\n")

"""

from __future__ import annotations

import dataclasses as dc
from unittest import mock

import pytest

from claude_q.git_integration import (
    GitError,
    derive_topic,
    get_current_branch,
    get_first_remote,
    is_in_git_worktree,
)


@dc.dataclass(frozen=True)
class FakeResult:
    """Minimal cuprum-like command result for git tests."""

    stdout: str
    ok: bool = True
    exit_code: int = 0


@mock.patch("claude_q.git_integration.run_sync")
@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (FakeResult(stdout="origin\nupstream\n"), "origin"),
        (FakeResult(stdout=""), ""),
        (FakeResult(stdout="origin\n", ok=False, exit_code=1), ""),
        (Exception("git error"), ""),
    ],
)
def test_get_first_remote_outputs(
    mock_run_sync: mock.MagicMock, result: FakeResult | Exception, expected: str
) -> None:
    """Test get_first_remote output cases."""
    match result:
        case Exception() as err:
            mock_run_sync.side_effect = err
        case _:
            mock_run_sync.return_value = result

    remote = get_first_remote()
    assert remote == expected, "should return expected remote output"


@mock.patch("claude_q.git_integration.run_sync")
@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (FakeResult(stdout="main\n"), "main"),
        (FakeResult(stdout="HEAD\n"), ""),
        (FakeResult(stdout=""), ""),
        (FakeResult(stdout="main\n", ok=False, exit_code=1), ""),
        (Exception("git error"), ""),
    ],
)
def test_get_current_branch_outputs(
    mock_run_sync: mock.MagicMock, result: FakeResult | Exception, expected: str
) -> None:
    """Test get_current_branch output cases."""
    match result:
        case Exception() as err:
            mock_run_sync.side_effect = err
        case _:
            mock_run_sync.return_value = result

    branch = get_current_branch()
    assert branch == expected, "should return expected branch output"


@mock.patch("claude_q.git_integration.run_sync")
@pytest.mark.parametrize(
    ("result", "expected_state"),
    [
        (FakeResult(stdout="true\n"), True),
        (FakeResult(stdout="false\n"), False),
        (FakeResult(stdout="true\n", ok=False, exit_code=1), False),
        (Exception("git error"), False),
    ],
)
def test_is_in_git_worktree_outputs(
    mock_run_sync: mock.MagicMock,
    result: FakeResult | Exception,
    expected_state: bool,  # noqa: FBT001
) -> None:
    """Test is_in_git_worktree output cases."""
    match result:
        case Exception() as err:
            mock_run_sync.side_effect = err
        case _:
            mock_run_sync.return_value = result

    assert is_in_git_worktree() is expected_state, (
        "should return expected worktree state"
    )


@mock.patch("claude_q.git_integration.is_in_git_worktree")
@mock.patch("claude_q.git_integration.get_current_branch")
@mock.patch("claude_q.git_integration.get_first_remote")
def test_derive_topic_remote_and_branch(
    mock_get_first_remote: mock.MagicMock,
    mock_get_current_branch: mock.MagicMock,
    mock_is_in_git_worktree: mock.MagicMock,
) -> None:
    """Test deriving topic when both remote and branch exist."""
    mock_is_in_git_worktree.return_value = True
    mock_get_first_remote.return_value = "origin"
    mock_get_current_branch.return_value = "feature"

    topic = derive_topic()
    assert topic == "origin:feature", "should combine remote and branch"


@mock.patch("claude_q.git_integration.is_in_git_worktree")
@mock.patch("claude_q.git_integration.get_current_branch")
@mock.patch("claude_q.git_integration.get_first_remote")
def test_derive_topic_remote_only(
    mock_get_first_remote: mock.MagicMock,
    mock_get_current_branch: mock.MagicMock,
    mock_is_in_git_worktree: mock.MagicMock,
) -> None:
    """Test deriving topic when only remote exists."""
    mock_is_in_git_worktree.return_value = True
    mock_get_first_remote.return_value = "origin"
    mock_get_current_branch.return_value = ""

    topic = derive_topic()
    assert topic == "origin", "should return remote when branch missing"


@mock.patch("claude_q.git_integration.is_in_git_worktree")
@mock.patch("claude_q.git_integration.get_current_branch")
@mock.patch("claude_q.git_integration.get_first_remote")
def test_derive_topic_branch_only(
    mock_get_first_remote: mock.MagicMock,
    mock_get_current_branch: mock.MagicMock,
    mock_is_in_git_worktree: mock.MagicMock,
) -> None:
    """Test deriving topic when only branch exists."""
    mock_is_in_git_worktree.return_value = True
    mock_get_first_remote.return_value = ""
    mock_get_current_branch.return_value = "feature"

    topic = derive_topic()
    assert topic == "feature", "should return branch when remote missing"


@mock.patch("claude_q.git_integration.is_in_git_worktree")
def test_derive_topic_not_in_worktree(
    mock_is_in_git_worktree: mock.MagicMock,
) -> None:
    """Test deriving topic when not in a git worktree."""
    mock_is_in_git_worktree.return_value = False

    with pytest.raises(GitError, match="not in a git worktree"):
        derive_topic()


@mock.patch("claude_q.git_integration.is_in_git_worktree")
@mock.patch("claude_q.git_integration.get_current_branch")
@mock.patch("claude_q.git_integration.get_first_remote")
def test_derive_topic_no_remote_or_branch(
    mock_get_first_remote: mock.MagicMock,
    mock_get_current_branch: mock.MagicMock,
    mock_is_in_git_worktree: mock.MagicMock,
) -> None:
    """Test deriving topic when neither remote nor branch exist."""
    mock_is_in_git_worktree.return_value = True
    mock_get_first_remote.return_value = ""
    mock_get_current_branch.return_value = ""

    with pytest.raises(GitError, match="cannot derive topic"):
        derive_topic()
