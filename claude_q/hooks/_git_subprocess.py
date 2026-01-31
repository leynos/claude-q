"""Cuprum-based git helpers for hook wrappers.

Uses cuprum to query git state for a specific working directory, matching the
behaviour of the CLI helpers. Intended for hook wrappers that need git context
without importing the main CLI. Exposes ``run_command``, ``get_first_remote``,
``get_current_branch``, ``is_in_git_worktree``, and ``derive_topic``.

Examples
--------
Call helpers with an explicit working directory::

    from claude_q.hooks._git_subprocess import derive_topic

    topic = derive_topic("/repo")

"""

from __future__ import annotations

import typing as typ

from claude_q.command_runner import GIT, RunOptions, run_sync
from claude_q.git_integration import GitError, combine_topic

if typ.TYPE_CHECKING:
    from cuprum import CommandResult


def run_command(
    cmd: list[str],
    cwd: str,
    *,
    input_text: str | None = None,
) -> CommandResult:
    """Run a command and capture output.

    Parameters
    ----------
    cmd : list[str]
        Command arguments.
    cwd : str
        Working directory to run in.
    input_text : str | None, optional
        Optional stdin text.

    Returns
    -------
    CommandResult
        Completed process with stdout/stderr/exit_code.

    Raises
    ------
    ValueError
        If stdin input is provided or the command is not a git invocation.

    """
    if input_text is not None:
        msg = "stdin input is not supported by the cuprum runner"
        raise ValueError(msg)
    if not cmd:
        msg = "command list must not be empty"
        raise ValueError(msg)
    if cmd[0] != "git":
        msg = "only git commands are supported by this helper"
        raise ValueError(msg)
    return run_sync(GIT, cmd[1:], options=RunOptions(cwd=cwd))


def get_first_remote(cwd: str) -> str:
    """Get the first git remote for the repository at cwd.

    Parameters
    ----------
    cwd : str
        Working directory containing the repository.

    Returns
    -------
    str
        First remote name, or an empty string if unavailable.

    """
    result = run_command(["git", "remote"], cwd)
    if not result.ok:
        return ""
    stdout = result.stdout or ""
    remotes = [line.strip() for line in stdout.splitlines() if line.strip()]
    return remotes[0] if remotes else ""


def get_current_branch(cwd: str) -> str:
    """Get the current branch name for the repository at cwd.

    Parameters
    ----------
    cwd : str
        Working directory containing the repository.

    Returns
    -------
    str
        Current branch name, or an empty string if detached/unavailable.

    """
    result = run_command(["git", "branch", "--show-current"], cwd)
    if not result.ok:
        return ""
    branch = (result.stdout or "").strip()
    return "" if branch in {"", "HEAD"} else branch


def is_in_git_worktree(cwd: str) -> bool:
    """Return True when cwd is inside a git worktree.

    Parameters
    ----------
    cwd : str
        Working directory to inspect.

    Returns
    -------
    bool
        True when inside a git worktree.

    """
    result = run_command(["git", "rev-parse", "--is-inside-work-tree"], cwd)
    stdout = result.stdout or ""
    return result.ok and stdout.strip() == "true"


def derive_topic(cwd: str) -> str:
    """Derive a queue topic from the git context at cwd.

    Parameters
    ----------
    cwd : str
        Working directory containing the repository.

    Returns
    -------
    str
        Derived topic string.

    Raises
    ------
    GitError
        If not in a worktree or no usable remote/branch exists.

    """
    if not is_in_git_worktree(cwd):
        msg = "not in a git worktree (cannot derive topic)"
        raise GitError(msg)

    remote = get_first_remote(cwd)
    branch = get_current_branch(cwd)
    topic = combine_topic(remote, branch)
    if not topic:
        msg = "cannot derive topic (no remote and no branch)"
        raise GitError(msg)
    return topic
