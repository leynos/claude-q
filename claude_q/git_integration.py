"""Git integration helpers for deriving queue topics from repository context."""

from __future__ import annotations

from plumbum.cmd import git


class GitError(Exception):
    """Raised when git operations fail or context is invalid."""


def get_first_remote() -> str:
    """Get the name of the first configured git remote.

    Returns:
        The first remote name, or empty string if no remotes exist or not in a
        git repo.

    """
    try:
        result = git["remote"]()
        remotes = [line.strip() for line in result.splitlines() if line.strip()]
    # TODO(leynos): https://github.com/leynos/claude-q/issues/123
    except Exception:  # noqa: BLE001
        return ""
    return remotes[0] if remotes else ""


def get_current_branch() -> str:
    """Get the name of the current git branch.

    Returns:
        The current branch name, or empty string if detached HEAD or not in a
        git repo.

    """
    try:
        branch = git["branch", "--show-current"]().strip()
    # TODO(leynos): https://github.com/leynos/claude-q/issues/123
    except Exception:  # noqa: BLE001
        return ""

    # "HEAD" or empty means detached HEAD
    if branch in {"", "HEAD"}:
        return ""
    return branch


def is_in_git_worktree() -> bool:
    """Check if current directory is inside a git worktree.

    Returns:
        True if inside a git worktree, False otherwise.

    """
    try:
        result = git["rev-parse", "--is-inside-work-tree"]().strip()
    # TODO(leynos): https://github.com/leynos/claude-q/issues/123
    except Exception:  # noqa: BLE001
        return False
    return result == "true"


def combine_topic(remote: str, branch: str) -> str:
    """Combine remote and branch into a topic string."""
    if remote and branch:
        return f"{remote}:{branch}"
    if remote:
        return remote
    if branch:
        return branch
    return ""


def derive_topic() -> str:
    """Derive a queue topic from the current git context.

    Returns:
        The derived topic string.

    Raises:
        GitError: If not in a git worktree or cannot derive a topic.

    """
    if not is_in_git_worktree():
        msg = "not in a git worktree (cannot derive topic)"
        raise GitError(msg)

    remote = get_first_remote()
    branch = get_current_branch()

    topic = combine_topic(remote, branch)
    if topic:
        return topic

    msg = "cannot derive topic (no remote and no branch)"
    raise GitError(msg)
