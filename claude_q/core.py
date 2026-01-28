"""Core queue storage implementation for claude-q.

Provides file-based FIFO queue storage with fcntl locking for safe concurrent
access. Each topic is stored as a separate JSON file with an associated lock
file for coordination.

Examples
--------
Append and pop messages from a queue::

    store = QueueStore(default_base_dir())
    store.append("origin/main", "Follow up on tests")
    next_msg = store.pop_first("origin/main")

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
_MAX_FILENAME_LENGTH = 180
# Keep under filesystem limits, leave room for suffixes.


def _topic_to_filename(topic: str) -> str:
    """Return a safe filename component for a topic."""
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
    """Return current UTC time as an ISO 8601 string."""
    return dt.datetime.now(tz=dt.UTC).isoformat(timespec="seconds")


@dataclasses.dataclass(frozen=True)
class TopicPaths:
    """File paths for a topic's data and lock files."""

    data: Path
    lock: Path


class QueueStore:
    """File-based FIFO queue storage with fcntl locking.

    Notes
    -----
    Each topic is stored as a separate JSON file with messages in FIFO order.
    A dedicated lock file provides coordination for safe concurrent access.

    Parameters
    ----------
    base_dir : Path
        Directory where queue files are stored.

    """

    def __init__(self, base_dir: Path) -> None:
        """Initialise a queue store with a base directory.

        Parameters
        ----------
        base_dir : Path
            Directory where queue files are stored.

        """
        self.base_dir = base_dir

    def ensure_base_dir(self) -> None:
        """Create base directory if it does not exist.

        Notes
        -----
        Uses restricted permissions when possible.

        """
        self.base_dir.mkdir(parents=True, exist_ok=True)
        # Best-effort permissions tightening; don't explode on weird FS.
        with contextlib.suppress(OSError):
            self.base_dir.chmod(0o700)

    def paths_for_topic(self, topic: str) -> TopicPaths:
        """Get file paths for a topic's data and lock files.

        Parameters
        ----------
        topic : str
            Topic name.

        Returns
        -------
        TopicPaths
            Paths for the topic's data and lock files.

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

        Parameters
        ----------
        topic : str
            Topic to lock.
        exclusive : bool
            True for exclusive lock (write), False for shared (read).

        Yields
        ------
        None
            Context manager scope for the lock.

        """
        self.ensure_base_dir()
        paths = self.paths_for_topic(topic)
        # 'a+' so it exists; do not truncate.
        with paths.lock.open("a+", encoding="utf-8") as lf:
            try:
                lf.flush()
                lock_type = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
                fcntl.flock(lf.fileno(), lock_type)
                yield
            finally:
                # If something truly odd happens, we still want to close.
                with contextlib.suppress(OSError):
                    fcntl.flock(lf.fileno(), fcntl.LOCK_UN)

    # TODO(leynos): https://github.com/leynos/claude-q/issues/123
    def _load_messages_unlocked(  # noqa: C901
        self, topic: str
    ) -> list[dict[str, typ.Any]]:
        """Load messages from topic file without acquiring a lock."""
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

        match data:
            case {"messages": list() as messages}:
                msgs = messages
            case {"messages": _}:
                msg = (
                    f"corrupt queue file for topic {topic!r}: {paths.data} "
                    "(messages not a list)"
                )
                # TODO(leynos): https://github.com/leynos/claude-q/issues/123 - FIXME:
                # RuntimeError preferred for file corruption over TypeError.
                raise RuntimeError(msg)
            case list() as messages:
                # Back-compat: allow bare list.
                msgs = messages
            case _:
                msg = f"corrupt queue file for topic {topic!r}: {paths.data}"
                raise RuntimeError(msg)

        # Validate minimally.
        out: list[dict[str, typ.Any]] = []
        for m in msgs:
            match m:
                case {"uuid": _, "content": _}:
                    out.append(m)
                case _:
                    continue
        return out

    def _save_messages_unlocked(
        self, topic: str, messages: list[dict[str, typ.Any]]
    ) -> None:
        """Save messages to topic file without acquiring a lock."""
        paths = self.paths_for_topic(topic)
        self.ensure_base_dir()
        payload: dict[str, typ.Any] = {
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
            tmp_path.replace(paths.data)
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

        Parameters
        ----------
        topic : str
            Topic to append to.
        content : str
            Message content.

        Returns
        -------
        str
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

        Parameters
        ----------
        topic : str
            Topic to dequeue from.

        Returns
        -------
        dict[str, typing.Any] | None
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

        Parameters
        ----------
        topic : str
            Topic to peek at.

        Returns
        -------
        dict[str, typing.Any] | None
            The first message, or None if queue is empty.

        """
        with self.lock_topic(topic, exclusive=False):
            msgs = self._load_messages_unlocked(topic)
            return msgs[0] if msgs else None

    def get_by_uuid(self, topic: str, uid: str) -> dict[str, typ.Any] | None:
        """Get a specific message by UUID.

        Parameters
        ----------
        topic : str
            Topic containing the message.
        uid : str
            Message UUID.

        Returns
        -------
        dict[str, typing.Any] | None
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

        Parameters
        ----------
        topic : str
            Topic to list.

        Returns
        -------
        list[dict[str, typing.Any]]
            Messages in FIFO order.

        """
        with self.lock_topic(topic, exclusive=False):
            return list(self._load_messages_unlocked(topic))

    def delete_by_uuid(self, topic: str, uid: str) -> bool:
        """Delete a specific message by UUID.

        Parameters
        ----------
        topic : str
            Topic containing the message.
        uid : str
            Message UUID to delete.

        Returns
        -------
        bool
            True if the message was deleted, False if not found.

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

        Parameters
        ----------
        topic : str
            Topic containing the message.
        uid : str
            Message UUID to replace.
        content : str
            New content.

        Returns
        -------
        bool
            True if the message was replaced, False if not found.

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

    Returns
    -------
    Path
        Path to the queue storage directory.

    """
    # Prefer explicit env var, then XDG state, then ~/.local/state
    if p := os.environ.get("Q_DIR"):
        return Path(p).expanduser()
    if p := os.environ.get("XDG_STATE_HOME"):
        return Path(p).expanduser() / "q"
    return Path.home() / ".local" / "state" / "q"
