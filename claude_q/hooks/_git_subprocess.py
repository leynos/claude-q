"""Subprocess-based git helpers for hook wrappers.

Uses subprocess to query git state for a specific working directory.
"""

from __future__ import annotations

# TODO(leynos): https://github.com/leynos/claude-q/issues/123
import subprocess  # noqa: S404

from claude_q.git_integration import GitError, combine_topic


def run_command(
    cmd: list[str],
    cwd: str,
    *,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess command and capture output.

    Args:
        cmd: Command arguments.
        cwd: Working directory to run in.
        input_text: Optional stdin text.

    Returns:
        CompletedProcess containing stdout/stderr/returncode.

    """
    return subprocess.run(  # noqa: S603
        cmd,
        cwd=cwd,
        text=True,
        input=input_text,
        capture_output=True,
        check=False,
    )


def get_first_remote(cwd: str) -> str:
    """Get the first git remote for the repository at cwd."""
    result = run_command(["git", "remote"], cwd)
    if result.returncode != 0:
        return ""
    remotes = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return remotes[0] if remotes else ""


def get_current_branch(cwd: str) -> str:
    """Get the current branch name for the repository at cwd."""
    result = run_command(["git", "branch", "--show-current"], cwd)
    if result.returncode != 0:
        return ""
    branch = result.stdout.strip()
    return "" if branch in {"", "HEAD"} else branch


def is_in_git_worktree(cwd: str) -> bool:
    """Return True when cwd is inside a git worktree."""
    result = run_command(["git", "rev-parse", "--is-inside-work-tree"], cwd)
    return result.returncode == 0 and result.stdout.strip() == "true"


def derive_topic(cwd: str) -> str:
    """Derive a queue topic from the git context at cwd.

    Raises:
        GitError: If not in a worktree or no usable remote/branch exists.

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
