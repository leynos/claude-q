"""Helper utilities for the claude-q CLI commands."""

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
