"""CLI entry points for claude-q.

Provides the top-level CLI apps used by the console script entry points.

Examples
--------
Import the entry points for programmatic invocation::

    from claude_q.cli import main, git_q_main

    main()

"""

from __future__ import annotations

from claude_q.cli.app import app, main
from claude_q.cli.git_app import git_app, git_q_main

__all__ = ["app", "git_app", "git_q_main", "main"]
