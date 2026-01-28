"""Tests for claude_q installer utilities."""

from __future__ import annotations

import json

# TODO(leynos): https://github.com/leynos/claude-q/issues/123
from pathlib import Path  # noqa: TC003

# TODO(leynos): https://github.com/leynos/claude-q/issues/123
import pytest  # noqa: TC002

from claude_q.installer import install as install_module
from claude_q.installer.install import find_settings_file
from claude_q.installer.uninstall import uninstall as uninstall_cmd


def test_find_settings_file_uses_xdg_config_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Find_settings_file should honor XDG_CONFIG_HOME when present."""
    xdg_config = tmp_path / "xdg"
    settings = xdg_config / "claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text("{}", encoding="utf-8")

    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config))

    found = find_settings_file()
    assert found == settings, "should return settings.json in XDG_CONFIG_HOME"


def test_install_requires_force_when_hooks_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Install should fail when hook commands are missing without --force."""
    settings = tmp_path / "settings.json"
    settings.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(install_module.shutil, "which", lambda _cmd: None)

    result = install_module.install(
        settings_path=settings,
        dry_run=True,
        force=False,
    )
    captured = capsys.readouterr()

    assert result == 1, "should return non-zero when hooks are missing"
    assert "Use --force" in captured.err, "should instruct user to use --force"


def test_install_with_force_writes_hooks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Install should proceed when --force is set even if hooks are missing."""
    settings = tmp_path / "settings.json"
    settings.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(install_module.shutil, "which", lambda _cmd: None)

    result = install_module.install(
        settings_path=settings,
        dry_run=False,
        force=True,
    )
    assert result == 0, "should succeed when --force is provided"

    data = json.loads(settings.read_text(encoding="utf-8"))
    assert "hooks" in data, "settings should include hooks after install"
    assert "stop" in data["hooks"], "stop hook should be installed"
    assert "userPromptSubmit" in data["hooks"], "prompt hook should be installed"

    backups = list(tmp_path.glob("settings.backup.*.json"))
    assert backups, "install should create a backup file"


def test_uninstall_dry_run_reports_actual_hooks(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Uninstall dry-run should report only existing hooks."""
    settings = tmp_path / "settings.json"
    payload = {
        "hooks": {
            "stop": {"command": "q-stop-hook", "enabled": True},
        }
    }
    settings.write_text(json.dumps(payload), encoding="utf-8")

    result = uninstall_cmd(settings_path=settings, dry_run=True)
    captured = capsys.readouterr()

    assert result == 0, "dry-run should succeed"
    assert "Would remove hooks" in captured.out, "dry-run should list hooks"
    assert "stop" in captured.out, "dry-run should include stop hook"
    assert "userPromptSubmit" not in captured.out, "missing hook should not be listed"
