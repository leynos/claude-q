"""Tests for claude_q.git_integration module."""

from __future__ import annotations

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
def test_get_first_remote_success(mock_git: mock.MagicMock) -> None:
    """Test getting first remote when remotes exist."""
    mock_git.__getitem__.return_value.return_value = "origin\nupstream\n"

    remote = get_first_remote()
    assert remote == "origin", "should return first remote name"


@mock.patch("claude_q.git_integration.git")
def test_get_first_remote_no_remotes(mock_git: mock.MagicMock) -> None:
    """Test getting first remote when no remotes exist."""
    mock_git.__getitem__.return_value.return_value = ""

    remote = get_first_remote()
    assert remote == "", "should return empty string when no remotes exist"


@mock.patch("claude_q.git_integration.git")
def test_get_first_remote_git_error(mock_git: mock.MagicMock) -> None:
    """Test getting first remote when git command fails."""
    mock_git.__getitem__.return_value.side_effect = Exception("git error")

    remote = get_first_remote()
    assert remote == "", "should return empty string on git error"


@mock.patch("claude_q.git_integration.git")
def test_get_current_branch_success(mock_git: mock.MagicMock) -> None:
    """Test getting current branch when on a branch."""
    mock_git.__getitem__.return_value.return_value = "main\n"

    branch = get_current_branch()
    assert branch == "main", "should return branch name"


@mock.patch("claude_q.git_integration.git")
def test_get_current_branch_detached_head(mock_git: mock.MagicMock) -> None:
    """Test getting current branch when in detached HEAD state."""
    mock_git.__getitem__.return_value.return_value = "HEAD\n"

    branch = get_current_branch()
    assert branch == "", "detached HEAD should return empty string"


@mock.patch("claude_q.git_integration.git")
def test_get_current_branch_empty(mock_git: mock.MagicMock) -> None:
    """Test getting current branch when result is empty."""
    mock_git.__getitem__.return_value.return_value = ""

    branch = get_current_branch()
    assert branch == "", "empty output should return empty string"


@mock.patch("claude_q.git_integration.git")
def test_get_current_branch_git_error(mock_git: mock.MagicMock) -> None:
    """Test getting current branch when git command fails."""
    mock_git.__getitem__.return_value.side_effect = Exception("git error")

    branch = get_current_branch()
    assert branch == "", "should return empty string on git error"


@mock.patch("claude_q.git_integration.git")
def test_is_in_git_worktree_true(mock_git: mock.MagicMock) -> None:
    """Test detecting when inside a git worktree."""
    mock_git.__getitem__.return_value.return_value = "true\n"

    assert is_in_git_worktree() is True, "should return True when inside worktree"


@mock.patch("claude_q.git_integration.git")
def test_is_in_git_worktree_false(mock_git: mock.MagicMock) -> None:
    """Test detecting when not inside a git worktree."""
    mock_git.__getitem__.return_value.return_value = "false\n"

    assert is_in_git_worktree() is False, "should return False when outside worktree"


@mock.patch("claude_q.git_integration.git")
def test_is_in_git_worktree_git_error(mock_git: mock.MagicMock) -> None:
    """Test detecting worktree when git command fails."""
    mock_git.__getitem__.return_value.side_effect = Exception("git error")

    assert is_in_git_worktree() is False, "should return False on git error"


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
