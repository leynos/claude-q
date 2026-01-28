"""Uninstall claude-q hooks from Claude Code settings.

Uses json5kit to parse JSON5 settings and writes normalized output while
removing hook entries.

Examples
--------
Remove hook entries from settings.json::

    q-uninstall-hooks

"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import (
    Path,  # noqa: TC003  # TODO(leynos): https://github.com/leynos/claude-q/issues/123 - Path required for CLI annotations.
)

import cyclopts

from claude_q.installer.install import find_settings_file
from claude_q.installer.json5_helpers import dumps, loads

app = cyclopts.App(
    name="q-uninstall-hooks",
    help="Uninstall claude-q hooks from Claude Code settings",
)


@app.default
# TODO(leynos): https://github.com/leynos/claude-q/issues/123
def uninstall(  # noqa: C901, PLR0911, PLR0912, PLR0915
    *,
    settings_path: Path | None = None,
    dry_run: bool = False,
) -> int:
    """Uninstall claude-q hooks from Claude Code settings.

    Creates backup before modifying settings.json.
    Operation is idempotent - safe to run multiple times.

    Parameters
    ----------
    settings_path : Path | None, optional
        Path to settings.json (auto-detected if not specified).
    dry_run : bool, optional
        Show what would be done without making changes.

    Returns
    -------
    int
        Exit code (0 on success, 1 on error).

    """
    try:
        settings_file = find_settings_file(settings_path)
    except FileNotFoundError as e:
        sys.stderr.write(f"Error: {e}\n")
        return 1

    sys.stdout.write(f"Found settings: {settings_file}\n")

    try:
        with settings_file.open(encoding="utf-8") as f:
            settings = loads(f.read())
    except Exception as e:  # noqa: BLE001  # TODO(leynos): https://github.com/leynos/claude-q/issues/123
        sys.stderr.write(f"Error parsing settings.json: {e}\n")
        return 1

    # Check if hooks exist
    match settings.get("hooks"):
        case None:
            sys.stdout.write("\nNo hooks configured - nothing to remove.\n")
            return 0
        case dict() as hooks:
            pass
        case _:
            sys.stderr.write("Error: settings.json hooks must be an object.\n")
            return 1
    has_stop = "stop" in hooks
    has_prompt = "userPromptSubmit" in hooks

    if dry_run:
        if not has_stop and not has_prompt:
            sys.stdout.write("\nNo claude-q hooks found - nothing to remove.\n")
            return 0
        sys.stdout.write("\n[DRY RUN] Would remove hooks:\n")
        if has_stop:
            sys.stdout.write("  - stop\n")
        if has_prompt:
            sys.stdout.write("  - userPromptSubmit\n")
        return 0

    if not has_stop and not has_prompt:
        sys.stdout.write("\nNo claude-q hooks found - nothing to remove.\n")
        return 0

    # Create timestamped backup
    timestamp = dt.datetime.now(tz=dt.UTC).strftime("%Y%m%d_%H%M%S")
    backup_path = settings_file.with_suffix(f".backup.{timestamp}.json")
    backup_path.write_text(
        settings_file.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    sys.stdout.write(f"Created backup: {backup_path}\n")

    # Remove hooks
    removed = []
    if has_stop:
        del hooks["stop"]
        removed.append("stop")
    if has_prompt:
        del hooks["userPromptSubmit"]
        removed.append("userPromptSubmit")

    # Clean up empty hooks object
    if not hooks:
        del settings["hooks"]

    # Write back with json5kit normalization
    try:
        with settings_file.open("w", encoding="utf-8") as f:
            f.write(dumps(settings))
    except Exception as e:  # noqa: BLE001  # TODO(leynos): https://github.com/leynos/claude-q/issues/123
        sys.stderr.write(f"Error writing settings.json: {e}\n")
        return 1

    sys.stdout.write("\nSuccessfully removed hooks:\n")
    for hook in removed:
        sys.stdout.write(f"  - {hook}\n")
    sys.stdout.write("\nRestart Claude Code to deactivate hooks.\n")
    return 0


def main() -> int:
    """Run the uninstaller CLI.

    Returns
    -------
    int
        Exit code.

    """
    try:
        result = app()
        return result if isinstance(result, int) else 0
    except Exception as e:  # noqa: BLE001  # TODO(leynos): https://github.com/leynos/claude-q/issues/123
        sys.stderr.write(f"Error: {e}\n")
        return 1
    except KeyboardInterrupt:
        sys.stderr.write("\n")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
