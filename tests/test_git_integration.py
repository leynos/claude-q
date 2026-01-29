r"""Tests for claude_q.git_integration.

Covers repository discovery, branch/remote parsing, and topic derivation. Git
interactions are mocked by patching the plumbum ``git`` command object to return
fixed stdout or raise exceptions.

Examples
--------
Stub git command output::

    mock_git.__getitem__.return_value.return_value = "origin\\n"

"""

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
@pytest.mark.parametrize(
    ("result", "expected"),
    [
        ("origin\nupstream\n", "origin"),
        ("", ""),
        (Exception("git error"), ""),
    ],
)
def test_get_first_remote_outputs(
    mock_git: mock.MagicMock, result: str | Exception, expected: str
) -> None:
    """Test get_first_remote output cases."""
    match result:
        case Exception() as err:
            mock_git.__getitem__.return_value.side_effect = err
        case _:
            mock_git.__getitem__.return_value.return_value = result

    remote = get_first_remote()
    assert remote == expected, "should return expected remote output"


@mock.patch("claude_q.git_integration.git")
@pytest.mark.parametrize(
    ("result", "expected"),
    [
        ("main\n", "main"),
        ("HEAD\n", ""),
        ("", ""),
        (Exception("git error"), ""),
    ],
)
def test_get_current_branch_outputs(
    mock_git: mock.MagicMock, result: str | Exception, expected: str
) -> None:
    """Test get_current_branch output cases."""
    match result:
        case Exception() as err:
            mock_git.__getitem__.return_value.side_effect = err
        case _:
            mock_git.__getitem__.return_value.return_value = result

    branch = get_current_branch()
    assert branch == expected, "should return expected branch output"


@mock.patch("claude_q.git_integration.git")
@pytest.mark.parametrize(
    ("result", "expected_state"),
    [
        ("true\n", True),
        ("false\n", False),
        (Exception("git error"), False),
    ],
)
def test_is_in_git_worktree_outputs(
    mock_git: mock.MagicMock,
    result: str | Exception,
    expected_state: bool,  # noqa: FBT001
) -> None:
    """Test is_in_git_worktree output cases."""
    match result:
        case Exception() as err:
            mock_git.__getitem__.return_value.side_effect = err
        case _:
            mock_git.__getitem__.return_value.return_value = result

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
