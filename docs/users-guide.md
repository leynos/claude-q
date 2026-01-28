# claude-q Users' Guide

claude-q provides topic-based FIFO queues that integrate with Claude Code. It
supports queuing tasks for later and automatically resuming them in future
sessions.

## Core concepts

- A "topic" is a queue name.
- Each topic stores messages in FIFO order.
- Topics are derived automatically when using git-aware commands.

## Command-line usage

The `q` command operates on explicit topics:

- `q put [topic]` opens `$EDITOR` and enqueues a message. If no topic is
  supplied, the first line of the editor text is treated as the topic.
- `q readto [topic]` reads from stdin and enqueues the message.
- `q get <topic>` dequeues the first message. With `--block`, polling continues
  until a message exists.
- `q peek <topic> [uuid]` prints a message without removing it.
- `q list <topic>` lists messages with UUIDs and summaries.
- `q del <topic> <uuid>` deletes a message by UUID.
- `q edit <topic> <uuid>` edits a message using `$EDITOR`.
- `q replace <topic> <uuid>` replaces content from stdin.

The `git-q` command derives the topic from the current git repository's
`remote:branch` and exposes the same core actions:

- `git-q put`
- `git-q readto`
- `git-q get` (use `--block` to poll)

## Hook installation

Claude Code hooks can automatically enqueue and dequeue messages.

### Install hooks

Run:

```bash
q-install-hooks
```

By default, the installer looks for `settings.json` in:

- `$XDG_CONFIG_HOME/claude/settings.json`
- `~/.claude/settings.json`

If hook executables are missing from `PATH`, installation fails unless the
`--force` flag is used.

### Dry run

To preview changes without writing:

```bash
q-install-hooks --dry-run
```

### Uninstall hooks

Run:

```bash
q-uninstall-hooks
```

The `--dry-run` flag shows which hooks would be removed based on the current
settings file.

## Hook behaviour

- `q-prompt-hook` intercepts prompts starting with `=qput` and queues the
  remainder of the message.
- `q-stop-hook` dequeues a message for the derived topic and feeds it back to
  Claude Code as the next prompt.

## Configuration

The queue storage directory defaults to:

- `$Q_DIR` when set
- `$XDG_STATE_HOME/q` when set
- `~/.local/state/q` otherwise

The `--dir` flag overrides the base directory for a single command.
