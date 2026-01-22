#!/usr/bin/env python3
"""Claude Code prompt hook for =qput interception."""

from __future__ import annotations

import json
import os
import shutil
import subprocess  # noqa: S404
import sys
import typing as typ
from pathlib import Path

PREFIX = "=qput"


def _run(
    cmd: list[str], cwd: str, *, input_text: str | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        cmd,
        cwd=cwd,
        text=True,
        input=input_text,
        capture_output=True,
        check=False,
    )


def _git_first_remote(cwd: str) -> str:
    p = _run(["git", "remote"], cwd)
    if p.returncode != 0:
        return ""
    remotes = [ln.strip() for ln in p.stdout.splitlines() if ln.strip()]
    return remotes[0] if remotes else ""


def _git_branch(cwd: str) -> str:
    p = _run(["git", "branch", "--show-current"], cwd)
    if p.returncode != 0:
        return ""
    b = p.stdout.strip()
    return "" if b in {"", "HEAD"} else b


def _topic(remote: str, branch: str) -> str:
    if remote and branch:
        return f"{remote}:{branch}"
    if remote:
        return remote
    if branch:
        return branch
    return ""


def _block(reason: str, *, exit2_mode: bool) -> int:
    """Block the prompt with a message.

    Two blocking modes:
    - JSON (exit 0): nicer UX, uses UserPromptSubmit decision control.
    - exit code 2 (stderr): more "primitive", but avoids stdout entirely.
    """
    if exit2_mode:
        sys.stderr.write(reason + "\n")
        return 2

    out = {
        "decision": "block",
        "reason": reason,
        "suppressOutput": True,
    }
    sys.stdout.write(json.dumps(out))
    return 0


def main() -> int:  # noqa: C901, PLR0911, PLR0914
    """Run the prompt hook to intercept =qput commands."""
    try:
        payload: dict[str, typ.Any] = json.load(sys.stdin)
    except Exception:  # noqa: BLE001
        payload = {}

    prompt = str(payload.get("prompt") or "")
    cwd = str(payload.get("cwd") or Path.cwd())

    # Only intercept exact prefix token (=qput followed by end/whitespace/newline).
    s = prompt.lstrip()
    if not s.startswith(PREFIX):
        return 0
    if len(s) > len(PREFIX) and s[len(PREFIX)] not in {" ", "\t", "\r", "\n"}:
        return 0  # e.g. "=qputty" should not match

    q_path = shutil.which("q")
    if not q_path:
        # Still squelch: user clearly intended a control message.
        return _block("qput: 'q' not found on PATH", exit2_mode=True)

    # Are we in a git worktree?
    if _run(["git", "rev-parse", "--is-inside-work-tree"], cwd).returncode != 0:
        return _block(
            "qput: not in a git worktree (cannot derive topic)", exit2_mode=True
        )

    remote = _git_first_remote(cwd)
    branch = _git_branch(cwd)
    topic = _topic(remote, branch)

    if not topic:
        return _block(
            "qput: cannot derive topic (no remote and no branch)", exit2_mode=True
        )

    # Extract message body: everything after "=qput" + optional leading whitespace.
    body = s[len(PREFIX) :]
    if body.startswith((" ", "\t")):
        body = body[1:]
    elif body.startswith(("\r\n", "\n", "\r")):
        body = body.lstrip("\r\n")

    if not body.strip():
        msg = (
            "qput: nothing to enqueue. "
            "Use '=qput <message>' or '=qput\\n<multi-line message>'."
        )
        return _block(msg, exit2_mode=True)

    # Enqueue without editor (hook-safe).
    p = _run([q_path, "readto", topic], cwd, input_text=body)
    if p.returncode != 0:
        err = (p.stderr or "").strip() or f"q readto failed (exit {p.returncode})"
        return _block(f"qput: failed to enqueue to '{topic}': {err}", exit2_mode=True)

    # Block so it never reaches Claude.
    # Default to JSON block (nice UX) unless you opt into exit2 mode.
    exit2_mode = os.environ.get("CLAUDE_QPUT_EXIT2", "") == "1"
    return _block(f"Queued to '{topic}'.", exit2_mode=exit2_mode)


if __name__ == "__main__":
    raise SystemExit(main())
