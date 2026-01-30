"""CLI entry points for claude-q.

Provides the console-script entry points for running the ``q`` and ``git-q``
command suites programmatically.

Examples
--------
Invoke the CLI entry points directly::

    from claude_q.cli import main, git_q_main

    main()

Run the CLI from the command line (via console scripts)::

    q --help
    git-q --help

"""

from __future__ import annotations

from claude_q.cli.app import app, main
from claude_q.cli.git_app import git_app, git_q_main

__all__ = ["app", "git_app", "git_q_main", "main"]
