"""Git integration helpers for deriving queue topics from repository context.

These helpers wrap git queries and assemble queue topics based on the current
repository state. Callers typically use ``derive_topic`` to build a queue topic
string from ``get_first_remote`` and ``get_current_branch`` when inside a
worktree.

Examples
--------
Derive a topic for the current working directory::

    from claude_q.git_integration import derive_topic

    topic = derive_topic()

``derive_topic`` raises ``GitError`` when the repository context is missing.

"""

from __future__ import annotations

from plumbum.cmd import git


class GitError(Exception):
    """Raised when git operations fail or context is invalid.

    Notes
    -----
    Used by queue hooks and CLI helpers to signal missing git context.

    """


def get_first_remote() -> str:
    """Get the name of the first configured git remote.

    Returns
    -------
    str
        First remote name, or an empty string if none are available.

    """
    try:
        result = git["remote"]()
        remotes = [line.strip() for line in result.splitlines() if line.strip()]
    except Exception:  # noqa: BLE001  # TODO(leynos): https://github.com/leynos/claude-q/issues/123 - Plumbum raises varied exceptions.
        return ""
    return remotes[0] if remotes else ""


def get_current_branch() -> str:
    """Get the name of the current git branch.

    Returns
    -------
    str
        Current branch name, or an empty string if detached or unavailable.

    """
    try:
        branch = git["branch", "--show-current"]().strip()
        # "HEAD" or empty means detached HEAD
        return "" if branch in {"", "HEAD"} else branch  # noqa: TRY300  # TODO(leynos): https://github.com/leynos/claude-q/issues/123 - FIXME: intentional early return.
    except Exception:  # noqa: BLE001  # TODO(leynos): https://github.com/leynos/claude-q/issues/123 - Plumbum raises varied exceptions.
        return ""


def is_in_git_worktree() -> bool:
    """Check if current directory is inside a git worktree.

    Returns
    -------
    bool
        True if inside a git worktree, False otherwise.

    """
    try:
        result = git["rev-parse", "--is-inside-work-tree"]().strip()
    except Exception:  # noqa: BLE001  # TODO(leynos): https://github.com/leynos/claude-q/issues/123 - Plumbum raises varied exceptions.
        return False
    return result == "true"


def combine_topic(remote: str, branch: str) -> str:
    """Combine remote and branch into a topic string.

    Parameters
    ----------
    remote : str
        Remote name.
    branch : str
        Branch name.

    Returns
    -------
    str
        Topic string derived from the inputs.

    """
    if remote and branch:
        return f"{remote}:{branch}"
    if remote:
        return remote
    if branch:
        return branch
    return ""


def derive_topic() -> str:
    """Derive a queue topic from the current git context.

    Returns
    -------
    str
        Derived topic string.

    Raises
    ------
    GitError
        If not in a git worktree or cannot derive a topic.

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
