"""Claude Code prompt hook for =qput interception.

When a user submits a prompt starting with "=qput", this hook:
1. Validates the prompt starts with exact "=qput" prefix (followed by
   space/newline/EOS)
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
from claude_q.hooks._common import PREFIX, block_with_message, extract_qput_body


def main() -> int:
    """Run the prompt hook.

    Reads JSON payload from stdin, checks for =qput prefix, enqueues if found.

    Returns
    -------
    int
        0 if allowing prompt or successfully blocked, 2 if blocking with error.

    """
    # Parse hook payload
    try:
        payload = json.load(sys.stdin)
    except Exception:  # noqa: BLE001  # TODO(leynos): https://github.com/leynos/claude-q/issues/123
        return 0  # Allow prompt on parse error

    prompt = str(payload.get("prompt") or "")
    body = extract_qput_body(prompt, prefix=PREFIX)
    if body is None:
        return 0  # Not a qput command - allow normally

    # Determine blocking mode (default to JSON for nicer UX)
    use_exit2 = os.environ.get("CLAUDE_QPUT_EXIT2", "") == "1"

    # Derive topic from git context
    try:
        topic = derive_topic()
    except GitError as e:
        return block_with_message(f"qput: {e}", use_exit2=use_exit2)

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
    except Exception as e:  # noqa: BLE001  # TODO(leynos): https://github.com/leynos/claude-q/issues/123 - QueueStore I/O errors.
        return block_with_message(
            f"qput: failed to enqueue to '{topic}': {e}",
            use_exit2=use_exit2,
        )

    # Block prompt and confirm to user
    return block_with_message(f"Queued to '{topic}'.", use_exit2=use_exit2)


if __name__ == "__main__":
    raise SystemExit(main())
