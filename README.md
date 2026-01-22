# claude-q

## Topic-based FIFO queues for Claude Code session continuity

`claude-q` provides simple, reliable task queuing that integrates
seamlessly with Claude Code. Queue tasks when you think of them, and
Claude automatically picks them up when ready—perfect for maintaining
context across sessions and managing async workflows.

## Why claude-q?

When working with Claude Code, you often think of tasks while in the
middle of something else:

- "I should refactor that module... but not now"
- "Need to add tests for this... after the current feature"
- "This would be a good time to update the docs"

Instead of interrupting your flow or forgetting these tasks, queue them
with `=qput` and let Claude handle them when the time is right.

## Quick Start

### Installation

```bash
# Install as a uv tool
uv tool install claude-q

# Install Claude Code hooks
q-install-hooks
```

### Basic Usage

```bash
# Queue a task (opens $EDITOR)
q put origin:main

# Or use git-aware commands (derives topic from repo)
git q put

# Quick inline queueing from Claude Code
=qput Refactor auth module to use async/await

# Dequeue and work on next task
q get origin:main

# List queued tasks
q list origin:main

# Block until a task is available
q get origin:main --block
```

## Features

### 🎯 Topic-Based Organization

Messages are organized by topics (typically `remote:branch`), keeping
your queues organized and context-aware.

```bash
# Different projects, different queues
q put origin:feature/auth "Implement JWT validation"
q put origin:main "Update changelog"

# Git-aware commands derive topic automatically
cd /path/to/project && git q put
```

### 🔐 Safe Concurrent Access

File-based storage with `fcntl` locking ensures safe concurrent access.
Multiple processes can read/write without conflicts.

### 🔄 Claude Code Integration

Claude automatically dequeues tasks when stopping, maintaining seamless
context across sessions:

1. Queue tasks with `=qput` during a session
2. End the Claude session
3. **Claude automatically dequeues and starts the next task**
4. Your workflow continues uninterrupted

### ⚡ Simple, Reliable

- **No daemons**: Pure Python, file-based storage
- **No databases**: JSON files in `~/.local/state/q/`
- **No network**: Everything local
- **No magic**: Straightforward FIFO semantics

## Commands

### Core Commands

#### `q put [topic]`

Enqueue a message. Opens `$EDITOR` for content. If topic is omitted,
first line becomes the topic.

```bash
# Specify topic
q put myproject "Implement feature X"

# Or let first line be the topic
q put
# Type in editor:
# myproject
# Implement feature X
```

#### `q readto <topic>`

Enqueue from stdin (hook-safe, no editor).

```bash
echo "Fix the tests" | q readto origin:main
```

#### `q get <topic> [--block] [--poll SECONDS]`

Dequeue first message. Returns exit code 1 if queue empty.

```bash
# Non-blocking
q get origin:main

# Block until message available
q get origin:main --block

# Custom poll interval
q get origin:main --block --poll 0.5
```

#### `q peek <topic> [uuid]`

View message without removing.

```bash
# Peek at first message
q peek origin:main

# Peek at specific message
q peek origin:main abc-123-def
```

#### `q list <topic> [-q|--quiet]`

List all messages with UUIDs and summaries.

```bash
# Full listing
q list origin:main

# UUIDs only
q list origin:main --quiet
```

#### `q del <topic> <uuid>`

Delete specific message by UUID.

```bash
q del origin:main abc-123-def
```

#### `q edit <topic> <uuid>`

Edit message in `$EDITOR`.

```bash
q edit origin:main abc-123-def
```

#### `q replace <topic> <uuid>`

Replace message content from stdin.

```bash
echo "New content" | q replace origin:main abc-123-def
```

### Git-Aware Commands

#### `git q put`

Enqueue with topic derived from git context (`remote:branch`).

```bash
cd /path/to/repo
git q put  # Topic automatically set to "origin:feature"
```

#### `git q readto`

Enqueue from stdin with git-derived topic.

```bash
echo "Task description" | git q readto
```

#### `git q get [--block]`

Dequeue from git-derived topic.

```bash
git q get
git q get --block
```

### Hook Management

#### `q-install-hooks [--dry-run] [--force] [--settings-path PATH]`

Install Claude Code hooks into `~/.claude/settings.json`.

```bash
# Preview installation
q-install-hooks --dry-run

# Install hooks
q-install-hooks

# Force overwrite existing hooks
q-install-hooks --force

# Custom settings location
q-install-hooks --settings-path ~/custom/settings.json
```

#### `q-uninstall-hooks [--dry-run] [--settings-path PATH]`

Remove Claude Code hooks.

```bash
# Preview removal
q-uninstall-hooks --dry-run

# Remove hooks
q-uninstall-hooks
```

## Claude Code Integration

### The `=qput` Prefix

From any Claude Code prompt, start with `=qput` to queue a task:

```text
=qput Refactor database connection pool
```

The message is queued and the prompt is blocked—Claude never sees it.
Perfect for capturing quick thoughts without context switching.

Multi-line tasks work too:

```text
=qput
Implement rate limiting for API:
- Add Redis backend
- Configure per-endpoint limits
- Add metrics
```

### Automatic Dequeue on Stop

When you end a Claude session, the stop hook automatically dequeues the
next task and feeds it back as your next prompt. Your workflow continues
seamlessly.

### Workflow Example

```bash
# During a session, you think of several tasks:
=qput Add error handling to user registration
=qput Write tests for authentication flow
=qput Update API documentation

# End the session
# Claude automatically dequeues "Add error handling..." and starts on it
# When that's done, end the session again
# Claude dequeues "Write tests..." and continues
# ... and so on
```

## Configuration

### Storage Location

Queues are stored in `${Q_DIR}` or `${XDG_STATE_HOME}/q/` or `~/.local/state/q/`.

Override with:

```bash
# Environment variable
export Q_DIR=~/my-queues
q put test-topic "message"

# Command-line flag
q --base-dir ~/my-queues put test-topic "message"
```

### Editor

Respects `$VISUAL` then `$EDITOR`, defaults to `vi`.

```bash
export EDITOR="code --wait"
q put mytopic  # Opens in VS Code
```

## Development

### Prerequisites

- Python 3.11+
- uv (recommended) or pip

### Setup

```bash
# Clone and install in development mode
git clone https://github.com/yourusername/claude-q
cd claude-q
uv sync --group dev

# Run tests
make test

# Run quality gates
make check-fmt lint typecheck
```

### Project Structure

```text
claude_q/
├── core.py              # QueueStore (file-based FIFO with locking)
├── cli.py               # Cyclopts-based CLI (q and git-q)
├── git_integration.py   # Git topic derivation
├── hooks/
│   ├── stop.py          # Claude Code stop hook (dequeue)
│   └── prompt.py        # Claude Code prompt hook (=qput)
└── installer/
    ├── install.py       # Hook installer (json5kit)
    └── uninstall.py     # Hook uninstaller
```

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions welcome! Please:

1. Run `make all` before submitting (format, lint, typecheck, test)
2. Add tests for new functionality
3. Update documentation as needed

## Acknowledgments

Built with:

- [Cyclopts](https://github.com/BrianPugh/cyclopts) - Modern Python CLI framework
- [Plumbum](https://github.com/tomerfiliba/plumbum) - Shell combinators for Python
- [json5kit](https://github.com/dpranke/pyjson5) - Lossless JSON editing

Inspired by the need for better task management in Claude Code workflows.
