"""Claude Code hooks for claude-q integration.

Provides the prompt hook (enqueue via "=qput") and the stop hook (dequeue on
session end). These are intended to be wired into Claude Code's hook settings
to provide automatic queueing and retrieval of tasks.
"""

from __future__ import annotations
