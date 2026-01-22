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
    assert store.base_dir == tmp_queue_dir


def test_append_creates_message(queue_store: QueueStore) -> None:
    """Test appending a message creates valid UUID."""
    msg_uuid = queue_store.append("test-topic", "Hello, world!")
    # Verify it's a valid UUID
    assert uuid.UUID(msg_uuid)


def test_append_and_pop(queue_store: QueueStore) -> None:
    """Test basic enqueue/dequeue cycle."""
    content = "Test message"
    queue_store.append("test-topic", content)

    msg = queue_store.pop_first("test-topic")
    assert msg is not None
    assert msg["content"] == content
    assert "uuid" in msg
    assert "created" in msg


def test_pop_empty_queue(queue_store: QueueStore) -> None:
    """Test popping from empty queue returns None."""
    msg = queue_store.pop_first("empty-topic")
    assert msg is None


def test_fifo_order(queue_store: QueueStore) -> None:
    """Test messages are dequeued in FIFO order."""
    messages = ["first", "second", "third"]
    for content in messages:
        queue_store.append("fifo-topic", content)

    # Dequeue and verify order
    for expected in messages:
        msg = queue_store.pop_first("fifo-topic")
        assert msg is not None
        assert msg["content"] == expected

    # Queue should be empty now
    assert queue_store.pop_first("fifo-topic") is None


def test_peek_first(queue_store: QueueStore) -> None:
    """Test peeking at first message without removing it."""
    content = "Peek me"
    queue_store.append("peek-topic", content)

    # Peek should return message
    msg1 = queue_store.peek_first("peek-topic")
    assert msg1 is not None
    assert msg1["content"] == content

    # Peeking again should return same message
    msg2 = queue_store.peek_first("peek-topic")
    assert msg2 is not None
    assert msg2["uuid"] == msg1["uuid"]

    # Message should still be in queue
    msg3 = queue_store.pop_first("peek-topic")
    assert msg3 is not None
    assert msg3["uuid"] == msg1["uuid"]


def test_peek_empty_queue(queue_store: QueueStore) -> None:
    """Test peeking at empty queue returns None."""
    msg = queue_store.peek_first("empty-peek")
    assert msg is None


def test_get_by_uuid(queue_store: QueueStore) -> None:
    """Test retrieving message by UUID."""
    content1 = "Message 1"
    content2 = "Message 2"

    uuid1 = queue_store.append("uuid-topic", content1)
    uuid2 = queue_store.append("uuid-topic", content2)

    # Retrieve by UUID
    msg1 = queue_store.get_by_uuid("uuid-topic", uuid1)
    assert msg1 is not None
    assert msg1["content"] == content1

    msg2 = queue_store.get_by_uuid("uuid-topic", uuid2)
    assert msg2 is not None
    assert msg2["content"] == content2


def test_get_by_uuid_nonexistent(queue_store: QueueStore) -> None:
    """Test retrieving nonexistent UUID returns None."""
    msg = queue_store.get_by_uuid("uuid-topic", str(uuid.uuid4()))
    assert msg is None


def test_list_messages(queue_store: QueueStore) -> None:
    """Test listing all messages in a topic."""
    messages = ["msg1", "msg2", "msg3"]
    for content in messages:
        queue_store.append("list-topic", content)

    all_msgs = queue_store.list_messages("list-topic")
    assert len(all_msgs) == len(messages)

    # Verify order and content
    for i, expected in enumerate(messages):
        assert all_msgs[i]["content"] == expected


def test_list_empty_queue(queue_store: QueueStore) -> None:
    """Test listing empty queue returns empty list."""
    msgs = queue_store.list_messages("empty-list")
    assert msgs == []


def test_delete_by_uuid(queue_store: QueueStore) -> None:
    """Test deleting message by UUID."""
    content1 = "Keep me"
    content2 = "Delete me"

    uuid1 = queue_store.append("del-topic", content1)
    uuid2 = queue_store.append("del-topic", content2)

    # Delete second message
    result = queue_store.delete_by_uuid("del-topic", uuid2)
    assert result is True

    # Verify only first message remains
    msgs = queue_store.list_messages("del-topic")
    assert len(msgs) == 1
    assert msgs[0]["uuid"] == uuid1


def test_delete_nonexistent_uuid(queue_store: QueueStore) -> None:
    """Test deleting nonexistent UUID returns False."""
    result = queue_store.delete_by_uuid("del-topic", str(uuid.uuid4()))
    assert result is False


def test_replace_by_uuid(queue_store: QueueStore) -> None:
    """Test replacing message content by UUID."""
    original = "Original content"
    updated = "Updated content"

    msg_uuid = queue_store.append("replace-topic", original)

    # Replace content
    result = queue_store.replace_by_uuid("replace-topic", msg_uuid, updated)
    assert result is True

    # Verify content was updated
    msg = queue_store.get_by_uuid("replace-topic", msg_uuid)
    assert msg is not None
    assert msg["content"] == updated
    assert "updated" in msg


def test_replace_nonexistent_uuid(queue_store: QueueStore) -> None:
    """Test replacing nonexistent UUID returns False."""
    result = queue_store.replace_by_uuid("replace-topic", str(uuid.uuid4()), "new")
    assert result is False


def test_multiple_topics_isolated(queue_store: QueueStore) -> None:
    """Test that different topics are isolated from each other."""
    queue_store.append("topic1", "Message for topic 1")
    queue_store.append("topic2", "Message for topic 2")

    # Each topic should have exactly one message
    msgs1 = queue_store.list_messages("topic1")
    msgs2 = queue_store.list_messages("topic2")

    assert len(msgs1) == 1
    assert len(msgs2) == 1
    assert msgs1[0]["content"] == "Message for topic 1"
    assert msgs2[0]["content"] == "Message for topic 2"


def test_topic_name_encoding(queue_store: QueueStore) -> None:
    """Test that special characters in topic names are handled correctly."""
    # Test various special characters
    special_topics = [
        "topic with spaces",
        "topic/with/slashes",
        "topic:with:colons",
        "topic@with@ats",
        "topic#with#hashes",
    ]

    for topic in special_topics:
        queue_store.append(topic, f"Message for {topic}")
        msg = queue_store.pop_first(topic)
        assert msg is not None
        assert msg["content"] == f"Message for {topic}"


def test_long_topic_name(queue_store: QueueStore) -> None:
    """Test handling of very long topic names."""
    long_topic = "a" * 300  # Longer than typical filesystem limits

    queue_store.append(long_topic, "Message for long topic")
    msg = queue_store.pop_first(long_topic)
    assert msg is not None
    assert msg["content"] == "Message for long topic"


def test_persistence(tmp_queue_dir: Path) -> None:
    """Test that messages persist across QueueStore instances."""
    # Create store and add message
    store1 = QueueStore(tmp_queue_dir)
    content = "Persistent message"
    msg_uuid = store1.append("persist-topic", content)

    # Create new store instance and verify message still exists
    store2 = QueueStore(tmp_queue_dir)
    msg = store2.get_by_uuid("persist-topic", msg_uuid)
    assert msg is not None
    assert msg["content"] == content


def test_empty_content_allowed(queue_store: QueueStore) -> None:
    """Test that empty content is allowed."""
    msg_uuid = queue_store.append("empty-content", "")
    msg = queue_store.get_by_uuid("empty-content", msg_uuid)
    assert msg is not None
    assert msg["content"] == ""


def test_multiline_content(queue_store: QueueStore) -> None:
    """Test handling of multiline content."""
    content = "Line 1\nLine 2\nLine 3"
    queue_store.append("multiline", content)

    msg = queue_store.pop_first("multiline")
    assert msg is not None
    assert msg["content"] == content


def test_unicode_content(queue_store: QueueStore) -> None:
    """Test handling of Unicode content."""
    content = "Hello 世界 🌍 مرحبا"
    queue_store.append("unicode", content)

    msg = queue_store.pop_first("unicode")
    assert msg is not None
    assert msg["content"] == content


def test_default_base_dir() -> None:
    """Test default_base_dir function returns valid path."""
    base_dir = default_base_dir()
    assert isinstance(base_dir, Path)
    # Should contain 'q' in the path
    assert "q" in str(base_dir)


def test_queue_file_format(tmp_queue_dir: Path) -> None:
    """Test that queue files use expected JSON format."""
    store = QueueStore(tmp_queue_dir)
    store.append("format-test", "Test content")

    # Find the queue file
    paths = store.paths_for_topic("format-test")
    assert paths.data.exists()

    # Parse and verify format
    with paths.data.open(encoding="utf-8") as f:
        data = json.load(f)

    assert "version" in data
    assert "topic" in data
    assert "messages" in data
    assert data["version"] == 1
    assert data["topic"] == "format-test"
    assert isinstance(data["messages"], list)
    assert len(data["messages"]) == 1


def test_empty_topic_name_raises(queue_store: QueueStore) -> None:
    """Test that empty topic name raises ValueError."""
    with pytest.raises(ValueError, match="topic is empty"):
        queue_store.append("", "content")

    with pytest.raises(ValueError, match="topic is empty"):
        queue_store.append("   ", "content")
