"""Tests for claude_q.core module."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from claude_q.core import QueueStore, default_base_dir


def test_queue_store_init(tmp_queue_dir: Path) -> None:
    """Test QueueStore initialization."""
    store = QueueStore(tmp_queue_dir)
    assert store.base_dir == tmp_queue_dir, "base_dir should match provided path"


def test_append_creates_message(queue_store: QueueStore) -> None:
    """Test appending a message creates valid UUID."""
    msg_uuid = queue_store.append("test-topic", "Hello, world!")
    # Verify it's a valid UUID
    assert uuid.UUID(msg_uuid), "append should return a valid UUID"


def test_append_and_pop(queue_store: QueueStore) -> None:
    """Test basic enqueue/dequeue cycle."""
    content = "Test message"
    queue_store.append("test-topic", content)

    msg = queue_store.pop_first("test-topic")
    assert msg is not None, "pop_first should return a message after append"
    assert msg["content"] == content, "message content should match appended content"
    assert "uuid" in msg, "message should include uuid"
    assert "created" in msg, "message should include created timestamp"


def test_pop_empty_queue(queue_store: QueueStore) -> None:
    """Test popping from empty queue returns None."""
    msg = queue_store.pop_first("empty-topic")
    assert msg is None, "pop_first should return None for empty queue"


def test_fifo_order(queue_store: QueueStore) -> None:
    """Test messages are dequeued in FIFO order."""
    messages = ["first", "second", "third"]
    for content in messages:
        queue_store.append("fifo-topic", content)

    # Dequeue and verify order
    for expected in messages:
        msg = queue_store.pop_first("fifo-topic")
        assert msg is not None, "pop_first should return a message for queued item"
        assert msg["content"] == expected, "messages should be dequeued in order"

    # Queue should be empty now
    assert queue_store.pop_first("fifo-topic") is None, (
        "queue should be empty after all messages dequeued"
    )


def test_peek_first(queue_store: QueueStore) -> None:
    """Test peeking at first message without removing it."""
    content = "Peek me"
    queue_store.append("peek-topic", content)

    # Peek should return message
    msg1 = queue_store.peek_first("peek-topic")
    assert msg1 is not None, "peek_first should return a message when queued"
    assert msg1["content"] == content, "peek_first should not alter content"

    # Peeking again should return same message
    msg2 = queue_store.peek_first("peek-topic")
    assert msg2 is not None, "peek_first should return message on repeated calls"
    assert msg2["uuid"] == msg1["uuid"], "peek_first should not remove message"

    # Message should still be in queue
    msg3 = queue_store.pop_first("peek-topic")
    assert msg3 is not None, "pop_first should return the queued message"
    assert msg3["uuid"] == msg1["uuid"], "peek_first should not remove message"


def test_peek_empty_queue(queue_store: QueueStore) -> None:
    """Test peeking at empty queue returns None."""
    msg = queue_store.peek_first("empty-peek")
    assert msg is None, "peek_first should return None for empty queue"


def test_get_by_uuid(queue_store: QueueStore) -> None:
    """Test retrieving message by UUID."""
    content1 = "Message 1"
    content2 = "Message 2"

    uuid1 = queue_store.append("uuid-topic", content1)
    uuid2 = queue_store.append("uuid-topic", content2)

    # Retrieve by UUID
    msg1 = queue_store.get_by_uuid("uuid-topic", uuid1)
    assert msg1 is not None, "get_by_uuid should return message for valid uuid"
    assert msg1["content"] == content1, "content should match expected message"

    msg2 = queue_store.get_by_uuid("uuid-topic", uuid2)
    assert msg2 is not None, "get_by_uuid should return message for valid uuid"
    assert msg2["content"] == content2, "content should match expected message"


def test_get_by_uuid_nonexistent(queue_store: QueueStore) -> None:
    """Test retrieving nonexistent UUID returns None."""
    msg = queue_store.get_by_uuid("uuid-topic", str(uuid.uuid4()))
    assert msg is None, "get_by_uuid should return None for missing uuid"


def test_list_messages(queue_store: QueueStore) -> None:
    """Test listing all messages in a topic."""
    messages = ["msg1", "msg2", "msg3"]
    for content in messages:
        queue_store.append("list-topic", content)

    all_msgs = queue_store.list_messages("list-topic")
    assert len(all_msgs) == len(messages), "list_messages should return all items"

    # Verify order and content
    for i, expected in enumerate(messages):
        assert all_msgs[i]["content"] == expected, (
            "list_messages should preserve FIFO order"
        )


def test_list_empty_queue(queue_store: QueueStore) -> None:
    """Test listing empty queue returns empty list."""
    msgs = queue_store.list_messages("empty-list")
    assert msgs == [], "list_messages should return empty list for empty queue"


def test_delete_by_uuid(queue_store: QueueStore) -> None:
    """Test deleting message by UUID."""
    content1 = "Keep me"
    content2 = "Delete me"

    uuid1 = queue_store.append("del-topic", content1)
    uuid2 = queue_store.append("del-topic", content2)

    # Delete second message
    result = queue_store.delete_by_uuid("del-topic", uuid2)
    assert result is True, "delete_by_uuid should return True when deleting"

    # Verify only first message remains
    msgs = queue_store.list_messages("del-topic")
    assert len(msgs) == 1, "only one message should remain after deletion"
    assert msgs[0]["uuid"] == uuid1, "remaining message should be the first"


def test_delete_nonexistent_uuid(queue_store: QueueStore) -> None:
    """Test deleting nonexistent UUID returns False."""
    result = queue_store.delete_by_uuid("del-topic", str(uuid.uuid4()))
    assert result is False, "delete_by_uuid should return False when missing"


def test_replace_by_uuid(queue_store: QueueStore) -> None:
    """Test replacing message content by UUID."""
    original = "Original content"
    updated = "Updated content"

    msg_uuid = queue_store.append("replace-topic", original)

    # Replace content
    result = queue_store.replace_by_uuid("replace-topic", msg_uuid, updated)
    assert result is True, "replace_by_uuid should return True when replacing"

    # Verify content was updated
    msg = queue_store.get_by_uuid("replace-topic", msg_uuid)
    assert msg is not None, "get_by_uuid should return updated message"
    assert msg["content"] == updated, "content should be updated"
    assert "updated" in msg, "updated timestamp should be set"


def test_replace_nonexistent_uuid(queue_store: QueueStore) -> None:
    """Test replacing nonexistent UUID returns False."""
    result = queue_store.replace_by_uuid("replace-topic", str(uuid.uuid4()), "new")
    assert result is False, "replace_by_uuid should return False when missing"


def test_multiple_topics_isolated(queue_store: QueueStore) -> None:
    """Test that different topics are isolated from each other."""
    queue_store.append("topic1", "Message for topic 1")
    queue_store.append("topic2", "Message for topic 2")

    # Each topic should have exactly one message
    msgs1 = queue_store.list_messages("topic1")
    msgs2 = queue_store.list_messages("topic2")

    assert len(msgs1) == 1, "topic1 should contain one message"
    assert len(msgs2) == 1, "topic2 should contain one message"
    assert msgs1[0]["content"] == "Message for topic 1", "topic1 content should match"
    assert msgs2[0]["content"] == "Message for topic 2", "topic2 content should match"


@pytest.mark.parametrize(
    "topic",
    [
        "topic with spaces",
        "topic/with/slashes",
        "topic:with:colons",
        "topic@with@ats",
        "topic#with#hashes",
    ],
)
def test_topic_name_encoding(queue_store: QueueStore, topic: str) -> None:
    """Test that special characters in topic names are handled correctly."""
    queue_store.append(topic, f"Message for {topic}")
    msg = queue_store.pop_first(topic)
    assert msg is not None, "pop_first should return message for special topic"
    assert msg["content"] == f"Message for {topic}", (
        "special topic content should match"
    )


def test_long_topic_name(queue_store: QueueStore) -> None:
    """Test handling of very long topic names."""
    long_topic = "a" * 300  # Longer than typical filesystem limits

    queue_store.append(long_topic, "Message for long topic")
    msg = queue_store.pop_first(long_topic)
    assert msg is not None, "pop_first should return message for long topic"
    assert msg["content"] == "Message for long topic", "long topic content should match"


def test_persistence(tmp_queue_dir: Path) -> None:
    """Test that messages persist across QueueStore instances."""
    # Create store and add message
    store1 = QueueStore(tmp_queue_dir)
    content = "Persistent message"
    msg_uuid = store1.append("persist-topic", content)

    # Create new store instance and verify message still exists
    store2 = QueueStore(tmp_queue_dir)
    msg = store2.get_by_uuid("persist-topic", msg_uuid)
    assert msg is not None, "message should persist across store instances"
    assert msg["content"] == content, "persisted content should match"


def test_empty_content_allowed(queue_store: QueueStore) -> None:
    """Test that empty content is allowed."""
    msg_uuid = queue_store.append("empty-content", "")
    msg = queue_store.get_by_uuid("empty-content", msg_uuid)
    assert msg is not None, "get_by_uuid should return message for empty content"
    assert msg["content"] == "", "empty content should be preserved"


def test_multiline_content(queue_store: QueueStore) -> None:
    """Test handling of multiline content."""
    content = "Line 1\nLine 2\nLine 3"
    queue_store.append("multiline", content)

    msg = queue_store.pop_first("multiline")
    assert msg is not None, "pop_first should return message for multiline content"
    assert msg["content"] == content, "multiline content should be preserved"


def test_unicode_content(queue_store: QueueStore) -> None:
    """Test handling of Unicode content."""
    content = "Hello 世界 🌍 مرحبا"
    queue_store.append("unicode", content)

    msg = queue_store.pop_first("unicode")
    assert msg is not None, "pop_first should return message for Unicode content"
    assert msg["content"] == content, "Unicode content should be preserved"


def test_default_base_dir() -> None:
    """Test default_base_dir function returns valid path."""
    base_dir = default_base_dir()
    assert isinstance(base_dir, Path), "default_base_dir should return a Path"
    # Should contain 'q' in the path
    assert "q" in str(base_dir), "default_base_dir should include 'q' component"


def test_queue_file_format(tmp_queue_dir: Path) -> None:
    """Test that queue files use expected JSON format."""
    store = QueueStore(tmp_queue_dir)
    store.append("format-test", "Test content")

    # Find the queue file
    paths = store.paths_for_topic("format-test")
    assert paths.data.exists(), "queue data file should exist after append"

    # Parse and verify format
    with paths.data.open(encoding="utf-8") as f:
        data = json.load(f)

    assert "version" in data, "queue file should include version"
    assert "topic" in data, "queue file should include topic"
    assert "messages" in data, "queue file should include messages"
    assert data["version"] == 1, "queue file version should be 1"
    assert data["topic"] == "format-test", "queue file topic should match"
    assert isinstance(data["messages"], list), "messages should be a list"
    assert len(data["messages"]) == 1, "should contain one message"


def test_empty_topic_name_raises(queue_store: QueueStore) -> None:
    """Test that empty topic name raises ValueError."""
    with pytest.raises(ValueError, match="topic is empty"):
        queue_store.append("", "content")

    with pytest.raises(ValueError, match="topic is empty"):
        queue_store.append("   ", "content")
