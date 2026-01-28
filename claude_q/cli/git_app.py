"""Git-aware CLI commands for claude-q.

Provides the ``git-q`` CLI with topic derivation from git context.

Examples
--------
Enqueue a message for the current repository::

    git-q readto

"""

from __future__ import annotations

import sys
import time
from pathlib import (
    Path,  # noqa: TC003  # TODO(leynos): https://github.com/leynos/claude-q/issues/123 - Path required at runtime for CLI annotations.
)

import cyclopts

from claude_q import __version__
from claude_q.cli.helpers import edit_text, read_stdin_text
from claude_q.core import QueueStore, default_base_dir
from claude_q.git_integration import GitError, derive_topic

# Git-aware CLI application
git_app = cyclopts.App(
    name="git-q",
    help="Git-aware queue operations (derives topic from remote:branch).",
    version=__version__,
    version_flags=["--version", "-V"],
)


@git_app.default
def git_main_help() -> None:
    """Show the help message when no command is specified.

    Returns
    -------
    None
        None.

    """
    git_app.parse_args(["--help"])


@git_app.command
def git_put(*, base_dir: Path | None = None) -> int:
    """Open $EDITOR, enqueue into git-derived topic.

    Parameters
    ----------
    base_dir : Path | None, optional
        Storage directory (overrides Q_DIR and XDG_STATE_HOME).

    Returns
    -------
    int
        Exit code (0 on success).

    """
    try:
        topic = derive_topic()
    except GitError as e:
        sys.stderr.write(f"git q: {e}\n")
        return 1

    store = QueueStore(base_dir or default_base_dir())
    body = edit_text("")
    uid = store.append(topic, body)
    sys.stdout.write(uid + "\n")
    return 0


@git_app.command
def git_readto(*, base_dir: Path | None = None) -> int:
    """Read stdin, enqueue into git-derived topic.

    Parameters
    ----------
    base_dir : Path | None, optional
        Storage directory (overrides Q_DIR and XDG_STATE_HOME).

    Returns
    -------
    int
        Exit code (0 on success).

    """
    try:
        topic = derive_topic()
    except GitError as e:
        sys.stderr.write(f"git q: {e}\n")
        return 1

    store = QueueStore(base_dir or default_base_dir())
    body = read_stdin_text()
    uid = store.append(topic, body)
    sys.stdout.write(uid + "\n")
    return 0


@git_app.command
def git_get(
    *,
    block: bool = False,
    poll: float = 0.2,
    base_dir: Path | None = None,
) -> int:
    """Dequeue from git-derived topic.

    Parameters
    ----------
    block : bool, optional
        Block (poll) until a message exists.
    poll : float, optional
        Polling interval in seconds when --block is used.
    base_dir : Path | None, optional
        Storage directory (overrides Q_DIR and XDG_STATE_HOME).

    Returns
    -------
    int
        Exit code (0 if message found, 1 if queue empty).

    """
    try:
        topic = derive_topic()
    except GitError as e:
        sys.stderr.write(f"git q: {e}\n")
        return 1

    store = QueueStore(base_dir or default_base_dir())

    while True:
        msg = store.pop_first(topic)
        if msg is not None:
            sys.stdout.write(str(msg.get("content", "")))
            sys.stdout.flush()
            return 0

        if not block:
            return 1

        time.sleep(poll)


def git_q_main() -> int:
    """Run the git-q CLI.

    Returns
    -------
    int
        Exit code.

    """
    try:
        result = git_app()
        return result if isinstance(result, int) else 0
    except ValueError as e:
        sys.stderr.write(f"git q: {e}\n")
        return 2
    except RuntimeError as e:
        sys.stderr.write(f"git q: {e}\n")
        return 2
    except GitError as e:
        sys.stderr.write(f"git q: {e}\n")
        return 1
    except KeyboardInterrupt:
        sys.stderr.write("\n")
        return 130
