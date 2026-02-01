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

from claude_q.command_runner import GIT, run_sync


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
    output = _run_git_output(["remote"])
    if output is None:
        return ""
    remotes = [line.strip() for line in output.splitlines() if line.strip()]
    return remotes[0] if remotes else ""


def get_current_branch() -> str:
    """Get the name of the current git branch.

    Returns
    -------
    str
        Current branch name, or an empty string if detached or unavailable.

    """
    output = _run_git_output(["branch", "--show-current"])
    if output is None:
        return ""
    branch = output.strip()
    # "HEAD" or empty means detached HEAD
    # TODO(leynos): https://github.com/leynos/claude-q/issues/123
    # Intentional early return.
    return "" if branch in {"", "HEAD"} else branch


def is_in_git_worktree() -> bool:
    """Check if current directory is inside a git worktree.

    Returns
    -------
    bool
        True if inside a git worktree, False otherwise.

    """
    output = _run_git_output(["rev-parse", "--is-inside-work-tree"])
    if output is None:
        return False
    return output.strip() == "true"


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


def _run_git_output(args: list[str]) -> str | None:
    """Run a git command and return stdout on success."""
    try:
        result = run_sync(GIT, args)
    except Exception:  # noqa: BLE001  # TODO(leynos): https://github.com/leynos/claude-q/issues/123 - Cuprum raises varied exceptions.
        return None
    if not result.ok:
        return None
    return result.stdout or ""


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
