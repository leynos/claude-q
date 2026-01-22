#!/usr/bin/env python3
"""Claude Code Stop hook.

- Compute queue topic from: first git remote + current branch
- Dequeue next message via: q get <topic>
- If a message exists, block stopping and feed it back to Claude as the reason.
- If not in a git context (or no topic), or queue empty, do nothing (allow stop).

Designed to be quiet and non-blocking.
"""

from __future__ import annotations

import json
import shutil
import subprocess  # noqa: S404
import sys
import typing as typ
from pathlib import Path


def _run(cmd: list[str], cwd: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        cmd,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def _git_first_remote(cwd: str) -> str:
    # Not all repos have remotes; that's fine.
    p = _run(["git", "remote"], cwd)
    if p.returncode != 0:
        return ""
    remotes = [ln.strip() for ln in p.stdout.splitlines() if ln.strip()]
    return remotes[0] if remotes else ""


def _git_branch(cwd: str) -> str:
    # Empty on detached HEAD.
    p = _run(["git", "branch", "--show-current"], cwd)
    if p.returncode != 0:
        return ""
    branch = p.stdout.strip()
    return "" if branch in {"", "HEAD"} else branch


def _topic(remote: str, branch: str) -> str:
    # “Comprising remote + branch”; fall back sensibly if one is missing.
    if remote and branch:
        return f"{remote}:{branch}"
    if remote:
        return remote
    if branch:
        return branch
    return ""


def main() -> int:
    """Run the stop hook to dequeue tasks."""
    try:
        payload: dict[str, typ.Any] = json.load(sys.stdin)
    except Exception:  # noqa: BLE001
        payload = {}

    # Stop payload *may* include cwd; if not, rely on process cwd.
    cwd = str(payload.get("cwd") or Path.cwd())

    q_path = shutil.which("q")
    if not q_path:
        return 0  # silently do nothing

    # Quick “am I in a git repo?” test
    if _run(["git", "rev-parse", "--is-inside-work-tree"], cwd).returncode != 0:
        return 0

    remote = _git_first_remote(cwd)
    branch = _git_branch(cwd)

    topic = _topic(remote, branch)
    if not topic:
        # “returns silently if neither can be determined”
        return 0

    # Never block the hook itself: no --block.
    p = _run([q_path, "get", topic], cwd)

    msg = (p.stdout or "").strip()
    if p.returncode != 0 or not msg:
        return 0  # queue empty or q signalled “no message”

    # Block stopping, and hand the dequeued text to Claude as the next instruction.
    out = {
        "decision": "block",
        "reason": (
            f"Dequeued a queued task from topic '{topic}'. "
            f"Treat the following as the user's next prompt and complete it.\n\n"
            f"--- BEGIN QUEUED MESSAGE ---\n{msg}\n--- END QUEUED MESSAGE ---\n"
        ),
    }
    sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
