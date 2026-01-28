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
from pathlib import Path

from plumbum import local


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


def read_stdin_text() -> str:
    """Read all text from stdin without modification.

    Returns
    -------
    str
        Stdin content.

    """
    return sys.stdin.read()


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
