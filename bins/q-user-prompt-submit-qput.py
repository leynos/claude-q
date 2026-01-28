#!/usr/bin/env python3
"""Claude Code prompt hook for =qput interception.

Intercepts prompts starting with "=qput" and enqueues the message body into the
git-derived queue for the current working directory. Intended to be invoked as
a Claude Code UserPromptSubmit hook, receiving JSON on stdin.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import typing as typ
from pathlib import Path

from claude_q.git_integration import GitError
from claude_q.hooks._common import PREFIX, block_with_message, extract_qput_body
from claude_q.hooks._git_subprocess import derive_topic, run_command


def main() -> int:
    """Run the prompt hook to intercept =qput commands."""
    try:
        payload: dict[str, typ.Any] = json.load(sys.stdin)
    except Exception:  # noqa: BLE001  # TODO(leynos): https://github.com/leynos/claude-q/issues/123
        payload = {}

    prompt = str(payload.get("prompt") or "")
    cwd = str(payload.get("cwd") or Path.cwd())

    # Only intercept exact prefix token (=qput followed by
    # end/whitespace/newline).
    body = extract_qput_body(prompt, prefix=PREFIX)
    if body is None:
        return 0

    q_path = shutil.which("q")
    # Errors always use exit2 (stderr) mode for visibility.
    if not q_path:
        return block_with_message("qput: 'q' not found on PATH", use_exit2=True)

    try:
        topic = derive_topic(cwd)
    except GitError as e:
        return block_with_message(f"qput: {e}", use_exit2=True)

    # Extract message body: everything after "=qput" + optional
    # leading whitespace.
    if not body.strip():
        msg = (
            "qput: nothing to enqueue. "
            "Use '=qput <message>' or '=qput\\n<multi-line message>'."
        )
        return block_with_message(msg, use_exit2=True)

    # Enqueue without editor (hook-safe).
    p = run_command([q_path, "readto", topic], cwd, input_text=body)
    if p.returncode != 0:
        err = (p.stderr or "").strip() or (f"q readto failed (exit {p.returncode})")
        return block_with_message(
            f"qput: failed to enqueue to '{topic}': {err}", use_exit2=True
        )

    # Block so it never reaches Claude.
    # Default to JSON block (nice UX) unless you opt into exit2 mode.
    exit2_mode = os.environ.get("CLAUDE_QPUT_EXIT2", "") == "1"
    return block_with_message(f"Queued to '{topic}'.", use_exit2=exit2_mode)


if __name__ == "__main__":
    raise SystemExit(main())
