r"""Helper utilities for the claude-q CLI commands.

Provides editor invocation, stdin handling, topic parsing, and summary helpers
shared across CLI entry points.

Examples
--------
Split editor text into topic and body::

    from claude_q.cli.helpers import split_topic_and_body

    topic, body = split_topic_and_body("topic\\nbody")

"""

from __future__ import annotations

import os
import re
import shlex
import sys
import tempfile
import time
import typing as typ
from pathlib import Path

from cuprum import Program

from claude_q.command_runner import run_sync

if typ.TYPE_CHECKING:
    from claude_q.core import QueueStore


def editor_cmd() -> list[str]:
    """Get editor command from environment variables.

    Checks VISUAL first, then EDITOR, defaults to vi.
    Supports editors with arguments like "code --wait".

    Returns
    -------
    list[str]
        Command parts in ``[executable, *args]`` form.

    """
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi"
    try:
        tokens = shlex.split(editor)
    except ValueError:
        return ["vi"]
    return tokens or ["vi"]


def edit_text(initial: str = "") -> str:
    """Open text in editor, return edited content.

    Parameters
    ----------
    initial : str, optional
        Initial text to populate the editor with.

    Returns
    -------
    str
        Edited text content.

    Raises
    ------
    RuntimeError
        If the editor exits with a non-zero status.

    """
    with tempfile.NamedTemporaryFile(
        "w+", encoding="utf-8", delete=False, prefix="q.", suffix=".txt"
    ) as tf:
        path = Path(tf.name)
        tf.write(initial)
        tf.flush()

    try:
        cmd = [*editor_cmd(), str(path)]
        program = Program(cmd[0])
        result = run_sync(program, cmd[1:])
        if not result.ok:
            msg = f"editor exited with status {result.exit_code}: {' '.join(cmd)}"
            raise RuntimeError(msg)
        return path.read_text(encoding="utf-8")
    finally:
        path.unlink(missing_ok=True)


def split_topic_and_body(text: str) -> tuple[str, str]:
    """Split text into topic (first line) and body (rest).

    Parameters
    ----------
    text : str
        Input text with the topic on the first line.

    Returns
    -------
    tuple[str, str]
        Tuple of ``(topic, body)``.

    Raises
    ------
    ValueError
        If the topic is empty.

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


def validate_topic(topic: str) -> str:
    """Validate and normalise a topic string.

    Parameters
    ----------
    topic : str
        Raw topic string.

    Returns
    -------
    str
        Normalised topic string.

    Raises
    ------
    ValueError
        If the topic is empty after trimming.

    """
    topic_str = topic.strip()
    if not topic_str:
        msg = "topic is empty"
        raise ValueError(msg)
    return topic_str


def read_stdin_text() -> str:
    """Read all text from stdin without modification.

    Returns
    -------
    str
        Stdin content.

    """
    return sys.stdin.read()


def dequeue_with_poll(
    store: QueueStore,
    topic: str,
    *,
    block: bool,
    poll: float,
) -> dict[str, typ.Any] | None:
    """Dequeue a message, optionally polling until one exists.

    Parameters
    ----------
    store : QueueStore
        Queue storage instance.
    topic : str
        Queue topic name.
    block : bool
        Whether to poll until a message exists.
    poll : float
        Poll interval in seconds when blocking.

    Returns
    -------
    dict[str, typing.Any] | None
        Dequeued message, or None when no message is available.

    """
    while True:
        msg = store.pop_first(topic)
        if msg is not None:
            return msg
        if not block:
            return None
        time.sleep(poll)


def summarize(content: str, width: int = 80) -> str:
    """Create a one-line summary of message content.

    Parameters
    ----------
    content : str
        Message content to summarise.
    width : int, optional
        Maximum width of summary.

    Returns
    -------
    str
        Summarised content, possibly truncated with ellipsis.

    """
    lines = content.splitlines()
    first = lines[0] if lines else ""
    first = re.sub(r"\s+", " ", first.strip())
    if not first:
        first = "(empty)"

    more = len(lines) > 1
    return _format_summary_line(first, more=more, width=width)


def _format_summary_line(first: str, *, more: bool, width: int) -> str:
    """Return a width-limited summary line."""
    if len(first) > width:
        return first[: max(0, width - 1)] + "…"
    if more:
        if len(first) <= width - 2:
            return first + " …"
        return first[: max(0, width - 1)] + "…"
    return first
