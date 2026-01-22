"""Pytest configuration and fixtures for claude-q tests."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003

import pytest

from claude_q.core import QueueStore


@pytest.fixture
def tmp_queue_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory for queue storage.

    Args:
        tmp_path: pytest's tmp_path fixture.

    Returns:
        Path to temporary queue directory.

    """
    queue_dir = tmp_path / "queues"
    queue_dir.mkdir()
    return queue_dir


@pytest.fixture
def queue_store(tmp_queue_dir: Path) -> QueueStore:
    """Provide a QueueStore instance using temporary storage.

    Args:
        tmp_queue_dir: Temporary queue directory fixture.

    Returns:
        QueueStore instance for testing.

    """
    return QueueStore(tmp_queue_dir)
