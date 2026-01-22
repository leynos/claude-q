"""Claude Code prompt hook for =qput interception.

When a user submits a prompt starting with "=qput", this hook:
1. Validates the prompt starts with exact "=qput" prefix (followed by space/newline/EOS)
2. Derives topic from git remote and branch
3. Enqueues the message (without the =qput prefix)
4. Blocks the prompt so it doesn't reach Claude

This enables quick task queuing without opening an editor.

Example:
    =qput Implement feature X
    =qput
    Implement multi-line
    feature Y

Designed to be quiet - uses JSON output format for blocking.

"""

from __future__ import annotations

import json
import os
import sys

from claude_q.core import QueueStore, default_base_dir
from claude_q.git_integration import GitError, derive_topic

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


def main() -> int:  # noqa: C901, PLR0911
    """Run the prompt hook.

    Reads JSON payload from stdin, checks for =qput prefix, enqueues if found.

    Returns:
        0 if allowing prompt or successfully blocked, 2 if blocking with error.

    """
    # Parse hook payload
    try:
        payload = json.load(sys.stdin)
    except Exception:  # noqa: BLE001
        return 0  # Allow prompt on parse error

    prompt = str(payload.get("prompt") or "")

    # Check for exact prefix match (=qput followed by end/whitespace/newline)
    stripped = prompt.lstrip()
    if not stripped.startswith(PREFIX):
        return 0  # Not a qput command - allow normally

    # Verify it's the exact token, not "=qputty" or similar
    prefix_len = len(PREFIX)
    if len(stripped) > prefix_len and stripped[prefix_len] not in {
        " ",
        "\t",
        "\r",
        "\n",
    }:
        return 0  # Not exact match - allow normally

    # Determine blocking mode (default to JSON for nicer UX)
    use_exit2 = os.environ.get("CLAUDE_QPUT_EXIT2", "") == "1"

    # Derive topic from git context
    try:
        topic = derive_topic()
    except GitError as e:
        return block_with_message(f"qput: {e}", use_exit2=use_exit2)

    # Extract message body: everything after "=qput" + optional leading whitespace
    body = stripped[prefix_len:]
    if body.startswith((" ", "\t")):
        body = body[1:]
    elif body.startswith(("\r\n", "\n", "\r")):
        body = body.lstrip("\r\n")

    if not body.strip():
        return block_with_message(
            "qput: nothing to enqueue. "
            "Use '=qput <message>' or '=qput\\n<multi-line message>'.",
            use_exit2=use_exit2,
        )

    # Enqueue the message
    store = QueueStore(default_base_dir())
    try:
        store.append(topic, body)
    except Exception as e:  # noqa: BLE001
        return block_with_message(
            f"qput: failed to enqueue to '{topic}': {e}",
            use_exit2=use_exit2,
        )

    # Block prompt and confirm to user
    return block_with_message(f"Queued to '{topic}'.", use_exit2=use_exit2)


if __name__ == "__main__":
    raise SystemExit(main())
