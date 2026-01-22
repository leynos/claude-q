"""Command-line interface for claude-q using Cyclopts.

Provides both `q` and `git-q` entry points for topic-based queue management.
"""

from __future__ import annotations

import os
import re
import shlex
import sys
import tempfile
import time
from pathlib import Path

import cyclopts
from plumbum import local

from claude_q.core import QueueStore, default_base_dir
from claude_q.git_integration import GitError, derive_topic

# Version will be imported from __init__.py when needed
__version__ = "0.1.0"


def editor_cmd() -> list[str]:
    """Get editor command from environment variables.

    Checks VISUAL first, then EDITOR, defaults to vi.
    Supports editors with arguments like "code --wait".

    Returns:
        List of command parts [executable, *args].

    """
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi"
    try:
        return shlex.split(editor)
    except ValueError:
        return [editor]


def edit_text(initial: str = "") -> str:
    """Open text in editor, return edited content.

    Args:
        initial: Initial text to populate editor with.

    Returns:
        Edited text content.

    Raises:
        RuntimeError: If editor exits with non-zero status.

    """
    with tempfile.NamedTemporaryFile(
        "w+", encoding="utf-8", delete=False, prefix="q.", suffix=".txt"
    ) as tf:
        path = Path(tf.name)
        tf.write(initial)
        tf.flush()

    try:
        cmd = [*editor_cmd(), str(path)]
        # Use plumbum for subprocess management
        editor_bin = local[cmd[0]]
        result = editor_bin[cmd[1:]].run(retcode=None)
        if result[2] != 0:
            msg = f"editor exited with status {result[2]}: {' '.join(cmd)}"
            raise RuntimeError(msg)
        return path.read_text(encoding="utf-8")
    finally:
        path.unlink(missing_ok=True)


def split_topic_and_body(text: str) -> tuple[str, str]:
    """Split text into topic (first line) and body (rest).

    Args:
        text: Input text with topic on first line.

    Returns:
        Tuple of (topic, body).

    Raises:
        ValueError: If topic is empty.

    """
    if "\n" in text:
        first, rest = text.split("\n", 1)
    else:
        first, rest = text, ""
    topic = first.strip()
    if not topic:
        msg = "topic is empty"
        raise ValueError(msg)
    return topic, rest


def read_stdin_text() -> str:
    """Read all text from stdin without modification.

    Returns:
        stdin content as string.

    """
    return sys.stdin.read()


def summarize(content: str, width: int = 80) -> str:
    """Create a one-line summary of message content.

    Args:
        content: Message content to summarize.
        width: Maximum width of summary.

    Returns:
        Summarized content, possibly truncated with ellipsis.

    """
    lines = content.splitlines()
    first = lines[0] if lines else ""
    first = re.sub(r"\s+", " ", first.strip())
    if not first:
        first = "(empty)"

    more = len(lines) > 1
    # Reserve 1 char for ellipsis if needed.
    if len(first) > width:
        return first[: max(0, width - 1)] + "…"
    if more and len(first) <= width - 2:
        return first + " …"
    if more:
        return first[: max(0, width - 1)] + "…"
    return first


# Main CLI application
app = cyclopts.App(
    name="q",
    help="Topic-based queues (file-backed, flock-locked).",
    version=__version__,
    version_flags=["--version", "-V"],
)


@app.default
def main_help() -> None:
    """Show help message when no command is specified."""
    app.parse_args(["--help"])


@app.command
def put(
    topic: str | None = None,
    *,
    base_dir: Path | None = None,
) -> int:
    """Open $EDITOR, enqueue message.

    If topic omitted, first line of editor content is treated as topic.

    Args:
        topic: Queue topic name (optional).
        base_dir: Storage directory (overrides Q_DIR and XDG_STATE_HOME).

    Returns:
        Exit code (0 on success).

    """
    store = QueueStore(base_dir or default_base_dir())

    if topic:
        topic_str = topic.strip()
        if not topic_str:
            msg = "topic is empty"
            raise ValueError(msg)
        body = edit_text("")
    else:
        text = edit_text("")
        topic_str, body = split_topic_and_body(text)

    uid = store.append(topic_str, body)
    sys.stdout.write(uid + "\n")
    return 0


@app.command
def readto(
    topic: str | None = None,
    *,
    base_dir: Path | None = None,
) -> int:
    """Read stdin, enqueue message.

    If topic omitted, first line of stdin is treated as topic.

    Args:
        topic: Queue topic name (optional).
        base_dir: Storage directory (overrides Q_DIR and XDG_STATE_HOME).

    Returns:
        Exit code (0 on success).

    """
    store = QueueStore(base_dir or default_base_dir())
    text = read_stdin_text()

    if topic:
        topic_str = topic.strip()
        if not topic_str:
            msg = "topic is empty"
            raise ValueError(msg)
        body = text
    else:
        topic_str, body = split_topic_and_body(text)

    uid = store.append(topic_str, body)
    sys.stdout.write(uid + "\n")
    return 0


@app.command
def get(
    topic: str,
    *,
    block: bool = False,
    poll: float = 0.2,
    base_dir: Path | None = None,
) -> int:
    """Dequeue first message to stdout.

    Args:
        topic: Queue topic name.
        block: Block (poll) until a message exists.
        poll: Polling interval in seconds when --block is used.
        base_dir: Storage directory (overrides Q_DIR and XDG_STATE_HOME).

    Returns:
        Exit code (0 if message found, 1 if queue empty).

    """
    store = QueueStore(base_dir or default_base_dir())
    topic_str = topic.strip()
    if not topic_str:
        msg = "topic is empty"
        raise ValueError(msg)

    while True:
        msg = store.pop_first(topic_str)
        if msg is not None:
            sys.stdout.write(str(msg.get("content", "")))
            sys.stdout.flush()
            return 0

        if not block:
            return 1

        time.sleep(poll)


@app.command
def peek(
    topic: str,
    uuid: str | None = None,
    *,
    base_dir: Path | None = None,
) -> int:
    """Print message without removing it.

    Args:
        topic: Queue topic name.
        uuid: Message UUID (optional; defaults to first message).
        base_dir: Storage directory (overrides Q_DIR and XDG_STATE_HOME).

    Returns:
        Exit code (0 if message found, 1 if not found).

    """
    store = QueueStore(base_dir or default_base_dir())
    topic_str = topic.strip()
    if not topic_str:
        msg = "topic is empty"
        raise ValueError(msg)

    if uuid:
        message = store.get_by_uuid(topic_str, uuid)
    else:
        message = store.peek_first(topic_str)

    if message is None:
        return 1

    sys.stdout.write(str(message.get("content", "")))
    sys.stdout.flush()
    return 0


@app.command(name="list")
def list_cmd(
    topic: str,
    *,
    quiet: bool = False,
    base_dir: Path | None = None,
) -> int:
    """List messages with UUID and a summary.

    Args:
        topic: Queue topic name.
        quiet: Only print UUIDs (no summaries).
        base_dir: Storage directory (overrides Q_DIR and XDG_STATE_HOME).

    Returns:
        Exit code (0 on success).

    """
    store = QueueStore(base_dir or default_base_dir())
    topic_str = topic.strip()
    if not topic_str:
        msg = "topic is empty"
        raise ValueError(msg)

    msgs = store.list_messages(topic_str)
    for m in msgs:
        uid = str(m.get("uuid", ""))
        if quiet:
            sys.stdout.write(uid + "\n")
        else:
            summary = summarize(str(m.get("content", "")))
            sys.stdout.write(f"{uid} {summary}\n")
    return 0


@app.command(name="del")
def del_cmd(
    topic: str,
    uuid: str,
    *,
    base_dir: Path | None = None,
) -> int:
    """Delete message by UUID.

    Args:
        topic: Queue topic name.
        uuid: Message UUID.
        base_dir: Storage directory (overrides Q_DIR and XDG_STATE_HOME).

    Returns:
        Exit code (0 if deleted, 1 if not found).

    """
    store = QueueStore(base_dir or default_base_dir())
    topic_str = topic.strip()
    if not topic_str:
        msg = "topic is empty"
        raise ValueError(msg)

    ok = store.delete_by_uuid(topic_str, uuid)
    return 0 if ok else 1


@app.command
def edit(
    topic: str,
    uuid: str,
    *,
    base_dir: Path | None = None,
) -> int:
    """Open message in $EDITOR, then replace it.

    Args:
        topic: Queue topic name.
        uuid: Message UUID.
        base_dir: Storage directory (overrides Q_DIR and XDG_STATE_HOME).

    Returns:
        Exit code (0 if replaced, 1 if not found).

    """
    store = QueueStore(base_dir or default_base_dir())
    topic_str = topic.strip()
    if not topic_str:
        msg = "topic is empty"
        raise ValueError(msg)

    # Load current content (shared lock) then edit without holding any lock.
    message = store.get_by_uuid(topic_str, uuid)
    if message is None:
        return 1
    original = str(message.get("content", ""))

    edited = edit_text(original)

    ok = store.replace_by_uuid(topic_str, uuid, edited)
    return 0 if ok else 1


@app.command
def replace(
    topic: str,
    uuid: str,
    *,
    base_dir: Path | None = None,
) -> int:
    """Replace message content from stdin.

    Args:
        topic: Queue topic name.
        uuid: Message UUID.
        base_dir: Storage directory (overrides Q_DIR and XDG_STATE_HOME).

    Returns:
        Exit code (0 if replaced, 1 if not found).

    """
    store = QueueStore(base_dir or default_base_dir())
    topic_str = topic.strip()
    if not topic_str:
        msg = "topic is empty"
        raise ValueError(msg)

    body = read_stdin_text()
    ok = store.replace_by_uuid(topic_str, uuid, body)
    return 0 if ok else 1


def main() -> int:
    """Run the q CLI.

    Returns:
        Exit code.

    """
    try:
        result = app()
        return result if isinstance(result, int) else 0
    except ValueError as e:
        sys.stderr.write(f"q: {e}\n")
        return 2
    except RuntimeError as e:
        sys.stderr.write(f"q: {e}\n")
        return 2
    except KeyboardInterrupt:
        sys.stderr.write("\n")
        return 130


# Git-aware CLI application
git_app = cyclopts.App(
    name="git-q",
    help="Git-aware queue operations (derives topic from remote:branch).",
    version=__version__,
    version_flags=["--version", "-V"],
)


@git_app.default
def git_main_help() -> None:
    """Show help message when no command is specified."""
    git_app.parse_args(["--help"])


@git_app.command
def git_put(*, base_dir: Path | None = None) -> int:
    """Open $EDITOR, enqueue into git-derived topic.

    Args:
        base_dir: Storage directory (overrides Q_DIR and XDG_STATE_HOME).

    Returns:
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

    Args:
        base_dir: Storage directory (overrides Q_DIR and XDG_STATE_HOME).

    Returns:
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

    Args:
        block: Block (poll) until a message exists.
        poll: Polling interval in seconds when --block is used.
        base_dir: Storage directory (overrides Q_DIR and XDG_STATE_HOME).

    Returns:
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

    Returns:
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
