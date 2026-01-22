"""Core queue storage implementation for claude-q.

Provides file-based FIFO queue storage with fcntl locking for safe concurrent
access. Each topic is stored as a separate JSON file with an associated lock
file for coordination.
"""

from __future__ import annotations

import contextlib
import dataclasses
import datetime as dt
import fcntl
import hashlib
import json
import os
import tempfile
import typing as typ
import urllib.parse
import uuid
from pathlib import Path

if typ.TYPE_CHECKING:
    import collections.abc as cabc

_ALLOWED_TOPIC_CHARS = (
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
)
_MAX_FILENAME_LENGTH = 180  # Keep under filesystem limits, leave room for suffixes


def _topic_to_filename(topic: str) -> str:
    """Convert an arbitrary topic string into a safe filename component.

    We percent-encode everything except a conservative safe set.
    For very long topics we append a hash to keep filenames manageable.

    Args:
        topic: The topic string to encode.

    Returns:
        A safe filename component.

    Raises:
        ValueError: If the topic is empty after stripping.

    """
    t = topic.strip()
    if not t:
        msg = "topic is empty"
        raise ValueError(msg)

    safe = urllib.parse.quote(t, safe=_ALLOWED_TOPIC_CHARS)
    safe = safe.strip(".")  # avoid '.' or '..' shenanigans
    if not safe:
        safe = hashlib.sha256(t.encode("utf-8")).hexdigest()[:16]

    # Keep under common filesystem limits (255 bytes). Leave room for suffixes.
    if len(safe) > _MAX_FILENAME_LENGTH:
        h = hashlib.sha256(t.encode("utf-8")).hexdigest()[:16]
        safe = f"{safe[:150]}__{h}"
    return safe


def _utc_now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return dt.datetime.now(tz=dt.UTC).isoformat(timespec="seconds")


@dataclasses.dataclass(frozen=True)
class TopicPaths:
    """File paths for a topic's data and lock files."""

    data: Path
    lock: Path


class QueueStore:
    """File-based FIFO queue storage with fcntl locking.

    Each topic is stored as a separate JSON file with messages in FIFO order.
    A dedicated lock file provides coordination for safe concurrent access.

    Args:
        base_dir: Directory where queue files are stored.

    """

    def __init__(self, base_dir: Path) -> None:
        """Initialize queue store with base directory."""
        self.base_dir = base_dir

    def ensure_base_dir(self) -> None:
        """Create base directory if it doesn't exist, with restricted permissions."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        # Best-effort permissions tightening; don't explode on weird FS.
        with contextlib.suppress(OSError):
            self.base_dir.chmod(0o700)

    def paths_for_topic(self, topic: str) -> TopicPaths:
        """Get file paths for a topic's data and lock files.

        Args:
            topic: The topic name.

        Returns:
            TopicPaths with data and lock file paths.

        """
        safe = _topic_to_filename(topic)
        return TopicPaths(
            data=(self.base_dir / f"{safe}.json"),
            lock=(self.base_dir / f"{safe}.lock"),
        )

    @contextlib.contextmanager
    def lock_topic(self, topic: str, *, exclusive: bool) -> cabc.Iterator[None]:
        """Lock a topic via its dedicated lock file.

        We lock the lock file (never replaced), so we can safely replace the
        data file atomically.

        Args:
            topic: The topic to lock.
            exclusive: True for exclusive lock (write), False for shared (read).

        Yields:
            None (context manager for locking).

        """
        self.ensure_base_dir()
        paths = self.paths_for_topic(topic)
        # 'a+' so it exists; do not truncate.
        with Path(paths.lock).open("a+", encoding="utf-8") as lf:
            try:
                lf.flush()
                lock_type = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
                fcntl.flock(lf.fileno(), lock_type)
                yield
            finally:
                # If something truly odd happens, we still want to close.
                with contextlib.suppress(OSError):
                    fcntl.flock(lf.fileno(), fcntl.LOCK_UN)

    def _load_messages_unlocked(  # noqa: C901
        self, topic: str
    ) -> list[dict[str, typ.Any]]:
        """Load messages from topic file without acquiring lock.

        Must be called while holding appropriate lock.

        Args:
            topic: The topic to load.

        Returns:
            List of message dictionaries.

        Raises:
            RuntimeError: If queue file is corrupt.

        """
        paths = self.paths_for_topic(topic)
        if not paths.data.exists():
            return []
        try:
            raw = paths.data.read_text(encoding="utf-8")
        except FileNotFoundError:
            return []
        if not raw.strip():
            return []
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            msg = f"corrupt queue file for topic {topic!r}: {paths.data}"
            raise RuntimeError(msg) from e

        if isinstance(data, dict) and "messages" in data:
            msgs = data["messages"]
        else:
            # Back-compat: allow bare list.
            msgs = data

        if not isinstance(msgs, list):
            msg = (
                f"corrupt queue file for topic {topic!r}: {paths.data} "
                "(messages not a list)"
            )
            raise RuntimeError(msg)  # noqa: TRY004
        # Validate minimally.
        out: list[dict[str, typ.Any]] = []
        for m in msgs:
            if not isinstance(m, dict):
                continue
            if "uuid" not in m or "content" not in m:
                continue
            out.append(m)
        return out

    def _save_messages_unlocked(
        self, topic: str, messages: list[dict[str, typ.Any]]
    ) -> None:
        """Save messages to topic file without acquiring lock.

        Must be called while holding exclusive lock.

        Args:
            topic: The topic to save.
            messages: List of message dictionaries to save.

        """
        paths = self.paths_for_topic(topic)
        self.ensure_base_dir()
        payload: cabc.MutableMapping[str, typ.Any] = {
            "version": 1,
            "topic": topic,
            "messages": messages,
        }
        # Atomic write: write temp then replace. We lock via lock file.
        tmp_fd, tmp_name = tempfile.mkstemp(
            prefix=paths.data.name + ".",
            suffix=".tmp",
            dir=str(self.base_dir),
        )
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            # Tighten permissions before replace (best-effort).
            with contextlib.suppress(OSError):
                tmp_path.chmod(0o600)
            Path(tmp_path).replace(paths.data)
        finally:
            # If replace failed, try to clean up.
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass

    # High-level operations (each takes responsibility for locking).

    def append(self, topic: str, content: str) -> str:
        """Append a message to the topic queue.

        Args:
            topic: The topic to append to.
            content: The message content.

        Returns:
            UUID of the created message.

        """
        msg = {
            "uuid": str(uuid.uuid4()),
            "created": _utc_now_iso(),
            "content": content,
        }
        with self.lock_topic(topic, exclusive=True):
            msgs = self._load_messages_unlocked(topic)
            msgs.append(msg)
            self._save_messages_unlocked(topic, msgs)
        return msg["uuid"]

    def pop_first(self, topic: str) -> dict[str, typ.Any] | None:
        """Remove and return the first message from the topic queue.

        Args:
            topic: The topic to dequeue from.

        Returns:
            The first message, or None if queue is empty.

        """
        with self.lock_topic(topic, exclusive=True):
            msgs = self._load_messages_unlocked(topic)
            if not msgs:
                return None
            msg = msgs.pop(0)
            self._save_messages_unlocked(topic, msgs)
            return msg

    def peek_first(self, topic: str) -> dict[str, typ.Any] | None:
        """Get the first message without removing it.

        Args:
            topic: The topic to peek at.

        Returns:
            The first message, or None if queue is empty.

        """
        with self.lock_topic(topic, exclusive=False):
            msgs = self._load_messages_unlocked(topic)
            return msgs[0] if msgs else None

    def get_by_uuid(self, topic: str, uid: str) -> dict[str, typ.Any] | None:
        """Get a specific message by UUID.

        Args:
            topic: The topic containing the message.
            uid: The message UUID.

        Returns:
            The message, or None if not found.

        """
        with self.lock_topic(topic, exclusive=False):
            msgs = self._load_messages_unlocked(topic)
            for m in msgs:
                if m.get("uuid") == uid:
                    return m
            return None

    def list_messages(self, topic: str) -> list[dict[str, typ.Any]]:
        """List all messages in a topic.

        Args:
            topic: The topic to list.

        Returns:
            List of all messages in FIFO order.

        """
        with self.lock_topic(topic, exclusive=False):
            return list(self._load_messages_unlocked(topic))

    def delete_by_uuid(self, topic: str, uid: str) -> bool:
        """Delete a specific message by UUID.

        Args:
            topic: The topic containing the message.
            uid: The message UUID to delete.

        Returns:
            True if message was deleted, False if not found.

        """
        with self.lock_topic(topic, exclusive=True):
            msgs = self._load_messages_unlocked(topic)
            new_msgs = [m for m in msgs if m.get("uuid") != uid]
            if len(new_msgs) == len(msgs):
                return False
            self._save_messages_unlocked(topic, new_msgs)
            return True

    def replace_by_uuid(self, topic: str, uid: str, content: str) -> bool:
        """Replace the content of a specific message.

        Args:
            topic: The topic containing the message.
            uid: The message UUID to replace.
            content: The new content.

        Returns:
            True if message was replaced, False if not found.

        """
        with self.lock_topic(topic, exclusive=True):
            msgs = self._load_messages_unlocked(topic)
            for m in msgs:
                if m.get("uuid") == uid:
                    m["content"] = content
                    m["updated"] = _utc_now_iso()
                    self._save_messages_unlocked(topic, msgs)
                    return True
            return False


def default_base_dir() -> Path:
    """Get default queue storage directory.

    Respects Q_DIR environment variable, then XDG_STATE_HOME,
    then falls back to ~/.local/state/q.

    Returns:
        Path to queue storage directory.

    """
    # Prefer explicit env var, then XDG state, then ~/.local/state
    if p := os.environ.get("Q_DIR"):
        return Path(p).expanduser()
    if p := os.environ.get("XDG_STATE_HOME"):
        return Path(p).expanduser() / "q"
    return Path.home() / ".local" / "state" / "q"
