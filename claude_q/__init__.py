"""claude-q: Topic-based FIFO queues for Claude Code.

Provides file-backed, lock-protected queue operations with git integration
for seamless Claude Code session continuity.
"""

from __future__ import annotations

from claude_q.core import QueueStore, default_base_dir

__version__ = "0.1.0"
__all__ = ["QueueStore", "__version__", "default_base_dir"]
