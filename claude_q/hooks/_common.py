"""Shared helper utilities for Claude Code hook scripts.

Provides prompt parsing and output formatting helpers used by hook entry points
and their CLI wrappers.
"""

from __future__ import annotations

import json
import sys

PREFIX = "=qput"


def block_with_message(message: str, *, use_exit2: bool = False) -> int:
    """Block the prompt with a message to the user.

    Args:
        message: Message to display to user.
        use_exit2: If True, use exit code 2 (stderr). Otherwise use JSON format.

    Returns:
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

    Args:
        prompt: Raw prompt text.
        prefix: Prefix token to match.

    Returns:
        Extracted body string if the prompt matches the prefix.
        Returns None when the prompt is not a qput command.

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
