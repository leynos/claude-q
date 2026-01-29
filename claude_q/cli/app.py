"""Command-line interface for claude-q queues.

Provides the ``q`` CLI for enqueueing, inspecting, and managing topic-based
queues stored on disk. Subcommands include ``put``, ``readto``, ``get``,
``peek``, ``list``, ``del``, ``edit``, and ``replace`` with shared options such
as ``--dir`` for storage overrides.

Examples
--------
List messages for a topic::

    q list origin/main

Enqueue a message with the editor::

    q put origin/main

"""

from __future__ import annotations

import sys
from pathlib import (
    Path,  # noqa: TC003  # TODO(leynos): https://github.com/leynos/claude-q/issues/123 - Path required at runtime for CLI annotations.
)

import cyclopts

from claude_q import __version__
from claude_q.cli.helpers import (
    dequeue_with_poll,
    edit_text,
    read_stdin_text,
    split_topic_and_body,
    summarize,
    validate_topic,
)
from claude_q.core import QueueStore, default_base_dir

# Main CLI application
app = cyclopts.App(
    name="q",
    help="Topic-based queues (file-backed, flock-locked).",
    version=__version__,
    version_flags=["--version", "-V"],
)


@app.default
def main_help() -> None:
    """Show the help message when no command is specified."""
    app.parse_args(["--help"])


@app.command
def put(
    topic: str | None = None,
    *,
    base_dir: Path | None = None,
) -> int:
    """Open $EDITOR, enqueue message.

    If topic omitted, first line of editor content is treated as topic.

    Parameters
    ----------
    topic : str | None, optional
        Queue topic name.
    base_dir : Path | None, optional
        Storage directory (overrides Q_DIR and XDG_STATE_HOME).

    Returns
    -------
    int
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

    Parameters
    ----------
    topic : str | None, optional
        Queue topic name.
    base_dir : Path | None, optional
        Storage directory (overrides Q_DIR and XDG_STATE_HOME).

    Returns
    -------
    int
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

    Parameters
    ----------
    topic : str
        Queue topic name.
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
    store = QueueStore(base_dir or default_base_dir())
    topic_str = validate_topic(topic)
    msg = dequeue_with_poll(store, topic_str, block=block, poll=poll)
    if msg is None:
        return 1
    sys.stdout.write(str(msg.get("content", "")))
    sys.stdout.flush()
    return 0


@app.command
def peek(
    topic: str,
    uuid: str | None = None,
    *,
    base_dir: Path | None = None,
) -> int:
    """Print message without removing it.

    Parameters
    ----------
    topic : str
        Queue topic name.
    uuid : str | None, optional
        Message UUID (defaults to the first message).
    base_dir : Path | None, optional
        Storage directory (overrides Q_DIR and XDG_STATE_HOME).

    Returns
    -------
    int
        Exit code (0 if message found, 1 if not found).

    """
    store = QueueStore(base_dir or default_base_dir())
    topic_str = validate_topic(topic)

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

    Parameters
    ----------
    topic : str
        Queue topic name.
    quiet : bool, optional
        Only print UUIDs (no summaries).
    base_dir : Path | None, optional
        Storage directory (overrides Q_DIR and XDG_STATE_HOME).

    Returns
    -------
    int
        Exit code (0 on success).

    """
    store = QueueStore(base_dir or default_base_dir())
    topic_str = validate_topic(topic)

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

    Parameters
    ----------
    topic : str
        Queue topic name.
    uuid : str
        Message UUID.
    base_dir : Path | None, optional
        Storage directory (overrides Q_DIR and XDG_STATE_HOME).

    Returns
    -------
    int
        Exit code (0 if deleted, 1 if not found).

    """
    store = QueueStore(base_dir or default_base_dir())
    topic_str = validate_topic(topic)

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

    Parameters
    ----------
    topic : str
        Queue topic name.
    uuid : str
        Message UUID.
    base_dir : Path | None, optional
        Storage directory (overrides Q_DIR and XDG_STATE_HOME).

    Returns
    -------
    int
        Exit code (0 if replaced, 1 if not found).

    Notes
    -----
    Edits are performed after ``store.get_by_uuid`` and before
    ``store.replace_by_uuid``, so concurrent changes can cause edits to be
    discarded if the message changes in the meantime.

    """
    store = QueueStore(base_dir or default_base_dir())
    topic_str = validate_topic(topic)

    # Load current content (shared lock) then edit without holding any lock.
    message = store.get_by_uuid(topic_str, uuid)
    if message is None:
        return 1
    original = str(message.get("content", ""))

    edited = edit_text(original)

    ok = store.replace_by_uuid(topic_str, uuid, edited)
    if not ok:
        sys.stderr.write("q edit: message changed before replace; edits discarded\n")
        return 1
    return 0


@app.command
def replace(
    topic: str,
    uuid: str,
    *,
    base_dir: Path | None = None,
) -> int:
    """Replace message content from stdin.

    Parameters
    ----------
    topic : str
        Queue topic name.
    uuid : str
        Message UUID.
    base_dir : Path | None, optional
        Storage directory (overrides Q_DIR and XDG_STATE_HOME).

    Returns
    -------
    int
        Exit code (0 if replaced, 1 if not found).

    """
    store = QueueStore(base_dir or default_base_dir())
    topic_str = validate_topic(topic)

    body = read_stdin_text()
    ok = store.replace_by_uuid(topic_str, uuid, body)
    return 0 if ok else 1


def main() -> int:
    """Run the q CLI.

    Returns
    -------
    int
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
