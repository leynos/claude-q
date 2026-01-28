"""Claude Code stop hook for dequeuing tasks.

When Claude Code stops, this hook:
1. Derives topic from git remote and branch
2. Attempts to dequeue a message
3. If message exists, blocks stop and feeds it back as next prompt
4. If no message or not in git context, allows stop normally

Designed to be quiet and non-blocking - always exits 0.
"""

from __future__ import annotations

import json
import sys

from claude_q.core import QueueStore, default_base_dir
from claude_q.git_integration import GitError, derive_topic


def main() -> int:
    """Run the stop hook.

    Derives topic from git context and attempts to dequeue a message.

    Returns:
        Always 0 (hooks must not block on error).

    """
    # Try to derive git topic from current directory
    try:
        topic = derive_topic()
    except GitError:
        # Not in git context or cannot derive topic - allow stop
        return 0

    # Try to dequeue (non-blocking)
    store = QueueStore(default_base_dir())
    try:
        msg = store.pop_first(topic)
    except Exception:  # noqa: BLE001  # TODO(leynos): https://github.com/leynos/claude-q/issues/123
        # Any error (corrupt queue, etc.) - allow stop
        return 0

    if msg is None:
        # Queue empty - allow stop normally
        return 0

    # Message found - block stop and feed it back to Claude
    content = str(msg.get("content", ""))
    reason = (
        f"Dequeued a queued task from topic '{topic}'. "
        "Treat the following as the user's next prompt and "
        "complete it.\n\n"
        "--- BEGIN QUEUED MESSAGE ---\n"
        f"{content}\n"
        "--- END QUEUED MESSAGE ---\n"
    )
    output = {
        "decision": "block",
        "reason": reason,
    }
    sys.stdout.write(json.dumps(output))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
