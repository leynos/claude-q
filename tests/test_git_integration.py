r"""Tests for claude_q.git_integration module.

Exercises git topic derivation helpers using mocked plumbum calls.

Examples
--------
Stub git command output::

    mock_git.__getitem__.return_value.return_value = "origin\\n"

"""

from __future__ import annotations

import typing as typ
from unittest import mock

import pytest

from claude_q.git_integration import (
    GitError,
    derive_topic,
    get_current_branch,
    get_first_remote,
    is_in_git_worktree,
)


@mock.patch("claude_q.git_integration.git")
@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ("origin\nupstream\n", "origin"),
        ("", ""),
    ],
)
def test_get_first_remote_outputs(
    mock_git: mock.MagicMock, output: str, expected: str
) -> None:
    """Test get_first_remote output cases."""
    mock_git.__getitem__.return_value.return_value = output

    remote = get_first_remote()
    assert remote == expected, "should return expected remote output"


@mock.patch("claude_q.git_integration.git")
@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ("main\n", "main"),
        ("HEAD\n", ""),
        ("", ""),
    ],
)
def test_get_current_branch_outputs(
    mock_git: mock.MagicMock, output: str, expected: str
) -> None:
    """Test get_current_branch output cases."""
    mock_git.__getitem__.return_value.return_value = output

    branch = get_current_branch()
    assert branch == expected, "should return expected branch output"


@mock.patch("claude_q.git_integration.git")
@pytest.mark.parametrize(
    ("output", "expected_state"),
    [
        ("true\n", True),
        ("false\n", False),
    ],
)
def test_is_in_git_worktree_outputs(
    mock_git: mock.MagicMock, output: str, expected_state: object
) -> None:
    """Test is_in_git_worktree output cases."""
    mock_git.__getitem__.return_value.return_value = output

    assert is_in_git_worktree() is expected_state, (
        "should return expected worktree state"
    )


@mock.patch("claude_q.git_integration.git")
@pytest.mark.parametrize(
    ("func", "expected_value"),
    [
        (get_first_remote, ""),
        (get_current_branch, ""),
        (is_in_git_worktree, False),
    ],
)
def test_git_helpers_git_error(
    mock_git: mock.MagicMock,
    func: typ.Callable[[], str | bool],
    expected_value: object,
) -> None:
    """Test helper fallbacks when git command fails."""
    mock_git.__getitem__.return_value.side_effect = Exception("git error")

    assert func() == expected_value, "should return fallback on git error"


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
def test_derive_topic_not_in_worktree(mock_worktree: mock.MagicMock) -> None:
    """Test deriving topic when not in a git worktree."""
    mock_worktree.return_value = False

    with pytest.raises(GitError, match="not in a git worktree"):
        derive_topic()


@mock.patch("claude_q.git_integration.is_in_git_worktree")
@mock.patch("claude_q.git_integration.get_current_branch")
@mock.patch("claude_q.git_integration.get_first_remote")
def test_derive_topic_no_remote_or_branch(
    mock_remote: mock.MagicMock,
    mock_branch: mock.MagicMock,
    mock_worktree: mock.MagicMock,
) -> None:
    """Test deriving topic when neither remote nor branch exist."""
    mock_worktree.return_value = True
    mock_remote.return_value = ""
    mock_branch.return_value = ""

    with pytest.raises(GitError, match="cannot derive topic"):
        derive_topic()
