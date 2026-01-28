"""Install claude-q hooks into Claude Code settings.

Uses json5kit to parse JSON5 settings and writes normalized output while
adding hook entries.
"""

from __future__ import annotations

import datetime as dt
import os
import shutil
import sys
from pathlib import Path

import cyclopts

from claude_q.installer.json5_helpers import dumps, loads

app = cyclopts.App(
    name="q-install-hooks",
    help="Install claude-q hooks into Claude Code settings",
)


def find_settings_file(settings_path: Path | None = None) -> Path:
    """Find Claude Code settings.json file.

    Args:
        settings_path: Optional explicit path to settings.json.

    Returns:
        Path to settings.json.

    Raises:
        FileNotFoundError: If settings.json cannot be found.

    """
    if settings_path:
        if not settings_path.exists():
            msg = f"Settings file not found: {settings_path}"
            raise FileNotFoundError(msg)
        return settings_path

    # Try XDG_CONFIG_HOME first
    xdg_config_env = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_env:
        xdg_config = Path(xdg_config_env).expanduser()
    else:
        xdg_config = Path.home() / ".config"

    candidates = [
        xdg_config / "claude" / "settings.json",
        Path.home() / ".claude" / "settings.json",
    ]

    for path in candidates:
        if path.exists():
            return path

    msg = (
        "Could not find Claude Code settings.json. "
        f"Searched: {', '.join(str(p) for p in candidates)}"
    )
    raise FileNotFoundError(msg)


def verify_hook_commands() -> list[str]:
    """Verify that hook command executables are available on PATH.

    Returns:
        List of warnings for missing executables.

    """
    return [
        f"Warning: '{cmd}' not found on PATH"
        for cmd in ["q-stop-hook", "q-prompt-hook"]
        if not shutil.which(cmd)
    ]


@app.default
# TODO(leynos): https://github.com/leynos/claude-q/issues/123
def install(  # noqa: C901, PLR0911
    *,
    settings_path: Path | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> int:
    """Install claude-q hooks into Claude Code settings.

    Creates backup before modifying settings.json.
    Operation is idempotent - safe to run multiple times.

    Args:
        settings_path: Path to settings.json (auto-detected if not specified).
        dry_run: Show what would be done without making changes.
        force: Overwrite existing hook entries if present.

    Returns:
        Exit code (0 on success, 1 on error).

    """
    try:
        settings_file = find_settings_file(settings_path)
    except FileNotFoundError as e:
        sys.stderr.write(f"Error: {e}\n")
        return 1

    sys.stdout.write(f"Found settings: {settings_file}\n")

    # Check if hook commands are available
    warnings = verify_hook_commands()
    if warnings and not force:
        for warning in warnings:
            sys.stderr.write(f"{warning}\n")
        sys.stderr.write("Use --force to install hooks anyway.\n")
        return 1
    for warning in warnings:
        sys.stdout.write(f"{warning}\n")

    if dry_run:
        sys.stdout.write("\n[DRY RUN] Would install hooks:\n")
        sys.stdout.write("  - stop: q-stop-hook\n")
        sys.stdout.write("  - userPromptSubmit: q-prompt-hook\n")
        return 0

    # Create timestamped backup
    timestamp = dt.datetime.now(tz=dt.UTC).strftime("%Y%m%d_%H%M%S")
    backup_path = settings_file.with_suffix(f".backup.{timestamp}.json")
    backup_path.write_text(
        settings_file.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    sys.stdout.write(f"Created backup: {backup_path}\n")

    # Parse with json5kit for JSON5 support
    try:
        with settings_file.open(encoding="utf-8") as f:
            settings = loads(f.read())
    # TODO(leynos): https://github.com/leynos/claude-q/issues/123
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"Error parsing settings.json: {e}\n")
        return 1

    # Ensure hooks object exists
    if "hooks" not in settings:
        settings["hooks"] = {}

    hooks = settings["hooks"]

    # Check for existing hooks
    has_stop = "stop" in hooks
    has_prompt = "userPromptSubmit" in hooks

    if (has_stop or has_prompt) and not force:  # noqa: PLR0916
        sys.stdout.write("\nHooks already configured:\n")
        if has_stop:
            sys.stdout.write(f"  stop: {hooks['stop']}\n")
        if has_prompt:
            prompt_hook = hooks["userPromptSubmit"]
            sys.stdout.write(f"  userPromptSubmit: {prompt_hook}\n")
        sys.stdout.write("\nUse --force to overwrite existing hooks.\n")
        return 1

    # Add or update hooks
    hooks["stop"] = {"command": "q-stop-hook", "enabled": True}
    hooks["userPromptSubmit"] = {"command": "q-prompt-hook", "enabled": True}

    # Write back with json5kit normalization
    try:
        with settings_file.open("w", encoding="utf-8") as f:
            f.write(dumps(settings))
    # TODO(leynos): https://github.com/leynos/claude-q/issues/123
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"Error writing settings.json: {e}\n")
        return 1

    sys.stdout.write("\nSuccessfully installed hooks:\n")
    sys.stdout.write("  - stop: q-stop-hook\n")
    sys.stdout.write("  - userPromptSubmit: q-prompt-hook\n")
    sys.stdout.write("\nRestart Claude Code to activate hooks.\n")
    return 0


def main() -> int:
    """Run the installer CLI.

    Returns:
        Exit code.

    """
    try:
        result = app()
        return result if isinstance(result, int) else 0
    # TODO(leynos): https://github.com/leynos/claude-q/issues/123
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"Error: {e}\n")
        return 1
    except KeyboardInterrupt:
        sys.stderr.write("\n")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
