"""Shared helper utilities for Claude Code hook scripts.

Provides prompt parsing and output formatting helpers used by hook entry points
and their CLI wrappers.

Examples
--------
Format a dequeue reason for a hook response::

    from claude_q.hooks._common import format_dequeue_reason

    reason = format_dequeue_reason("origin/main", "Fix tests")

"""

from __future__ import annotations

import json
import sys

PREFIX = "=qput"


def block_with_message(message: str, *, use_exit2: bool = False) -> int:
    """Block the prompt with a message to the user.

    Parameters
    ----------
    message : str
        Message to display to the user.
    use_exit2 : bool, optional
        If True, use exit code 2 (stderr). Otherwise use JSON format.

    Returns
    -------
    int
        Exit code (0 for JSON mode, 2 for exit2 mode).

    """
    if use_exit2:
        sys.stderr.write(message + "\n")
        return 2

    output = {
        "decision": "block",
        "reason": message,
        "suppressOutput": True,
    }
    sys.stdout.write(json.dumps(output))
    sys.stdout.flush()
    return 0


def extract_qput_body(prompt: str, *, prefix: str = PREFIX) -> str | None:
    """Extract the message body from a =qput prompt.

    Parameters
    ----------
    prompt : str
        Raw prompt text.
    prefix : str, optional
        Prefix token to match.

    Returns
    -------
    str | None
        Extracted body string if the prompt matches the prefix, otherwise None.

    """
    stripped = prompt.lstrip()
    if not stripped.startswith(prefix):
        return None

    prefix_len = len(prefix)
    if len(stripped) > prefix_len and stripped[prefix_len] not in {
        " ",
        "\t",
        "\r",
        "\n",
    }:
        return None

    body = stripped[prefix_len:]
    if body.startswith((" ", "\t")):
        body = body[1:]
    elif body.startswith(("\r\n", "\n", "\r")):
        body = body.lstrip("\r\n")

    return body


def format_dequeue_reason(topic: str, content: str) -> str:
    """Format the reason message for a dequeued task.

    Parameters
    ----------
    topic : str
        Queue topic associated with the message.
    content : str
        Message content to include in the reason payload.

    Returns
    -------
    str
        Formatted reason text suitable for hook responses.

    """
    return (
        f"Dequeued a queued task from topic '{topic}'. "
        "Treat the following as the user's next prompt and "
        "complete it.\n\n"
        "--- BEGIN QUEUED MESSAGE ---\n"
        f"{content}\n"
        "--- END QUEUED MESSAGE ---\n"
    )
