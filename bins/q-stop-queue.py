#!/usr/bin/env python3
"""Claude Code Stop hook.

- Compute queue topic from: first git remote + current branch
- Dequeue next message via: q get <topic>
- If a message exists, block stopping and feed it back to Claude as the reason.
- If not in a git context (or no topic), or queue empty, do nothing
  (allow stop).

Designed to be quiet and non-blocking.
"""

from __future__ import annotations

import json
import shutil
import sys
import typing as typ
from pathlib import Path

from claude_q.git_integration import GitError
from claude_q.hooks._common import format_dequeue_reason
from claude_q.hooks._git_subprocess import derive_topic, run_command


def main() -> int:
    """Run the stop hook to dequeue tasks.

    Parameters
    ----------
    None

    Returns
    -------
    int
        Exit code (0 for hook success or noop).

    """
    try:
        payload: dict[str, typ.Any] = json.load(sys.stdin)
    except Exception:  # noqa: BLE001  # TODO(leynos): https://github.com/leynos/claude-q/issues/123
        payload = {}

    # Stop payload *may* include cwd; if not, rely on process cwd.
    cwd = str(payload.get("cwd") or Path.cwd())

    q_path = shutil.which("q")
    if not q_path:
        return 0  # silently do nothing

    try:
        topic = derive_topic(cwd)
    except GitError:
        return 0

    # Never block the hook itself: no --block.
    p = run_command([q_path, "get", topic], cwd)

    msg = (p.stdout or "").strip()
    if p.returncode != 0 or not msg:
        return 0  # queue empty or q signalled "no message"

    # Block stopping, and hand the dequeued text to Claude as the next
    # instruction.
    out = {
        "decision": "block",
        "reason": format_dequeue_reason(topic, msg),
    }
    sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
