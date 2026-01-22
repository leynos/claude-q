"""Git integration helpers for deriving queue topics from repository context."""

from __future__ import annotations

from plumbum.cmd import git


class GitError(Exception):
    """Raised when git operations fail or context is invalid."""


def get_first_remote() -> str:
    """Get the name of the first configured git remote.

    Returns:
        The first remote name, or empty string if no remotes exist or not in a git repo.

    """
    try:
        result = git["remote"]()
        remotes = [line.strip() for line in result.splitlines() if line.strip()]
        return remotes[0] if remotes else ""
    except Exception:  # noqa: BLE001
        return ""


def get_current_branch() -> str:
    """Get the name of the current git branch.

    Returns:
        The current branch name, or empty string if detached HEAD or not in a git repo.

    """
    try:
        branch = git["branch", "--show-current"]().strip()
        # "HEAD" or empty means detached HEAD
        return "" if branch in {"", "HEAD"} else branch  # noqa: TRY300
    except Exception:  # noqa: BLE001
        return ""


def is_in_git_worktree() -> bool:
    """Check if current directory is inside a git worktree.

    Returns:
        True if inside a git worktree, False otherwise.

    """
    try:
        result = git["rev-parse", "--is-inside-work-tree"]().strip()
        return result == "true"  # noqa: TRY300
    except Exception:  # noqa: BLE001
        return False


def derive_topic() -> str:
    """Derive a queue topic from the current git context.

    The topic is derived as follows:
    - If both remote and branch exist: "remote:branch"
    - If only remote exists: "remote"
    - If only branch exists: "branch"
    - Otherwise: empty string

    Returns:
        The derived topic, or empty string if no valid git context.

    Raises:
        GitError: If not in a git worktree or cannot derive a topic.

    """
    if not is_in_git_worktree():
        msg = "not in a git worktree (cannot derive topic)"
        raise GitError(msg)

    remote = get_first_remote()
    branch = get_current_branch()

    if remote and branch:
        return f"{remote}:{branch}"
    if remote:
        return remote
    if branch:
        return branch

    msg = "cannot derive topic (no remote and no branch)"
    raise GitError(msg)
