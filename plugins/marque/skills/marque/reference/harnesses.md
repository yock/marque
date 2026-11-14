# Harnesses

The skill speaks in neutral verbs. This file maps each one to **OpenCode**, **Claude Code** and **Codex**, naming the tool or setting that does the job, and then says what degrades on each. Facts are as of 2026-11 (#4's research); harnesses rename and move tools, so check a name against your harness's docs when it stops working.

Worktrees are not a harness feature here: Marque's own `git worktree add` creates them on every harness. What differs is whether a background implementer may write in one — see [Permission setup](#permission-setup).

## The map

| Verb | OpenCode | Claude Code | Codex |
|---|---|---|---|
| **dispatch a background subagent** | `subagent`, always background; the `sessionID` comes back at once. | A Task subagent; it starts in the background by default. | `spawn_agent` returns an agent id, and the child runs while you work. |
| **resume the same session** | `subagent` again with its `sessionID`, running or finished; the model can change on resume. | `SendMessage` to the agent id. The built-in Explore and Plan agents are one-shot. | `send_input` (v1) or `followup_task` (v2); `resume_agent` reopens a closed agent, and `close_agent` frees a finished one's slot. |
| **push a notification** | `notify_phone`. | `PushNotification`. | No agent-callable push. |
| **run a background command that wakes you** | `shell` with `background: true`; the session is notified when the command finishes. | Bash with `run_in_background`; `Monitor` streams output lines back. | None: long commands run through the unified exec and are polled with `write_stdin`. |
| **be woken when a subagent finishes** | A `<subagent>` message arrives each time a child goes idle. | The result reaches the orchestrator as a completion notification in a later turn. | None: the completion notice is injected without starting a turn. |
| **choose the model per subagent** | Any provider, `provider/model#variant` per call. | Per call, only the aliases `sonnet`, `opus`, `haiku` and `fable`, plus `effort`; a full model ID needs agent frontmatter. | `model` and `reasoning_effort` per call, from the parent's provider only. |
| **worktree write access** | `external_directory` is allowed by default; the subagent's permission config decides the rest. | `additionalDirectories`, or a permissive mode. | Every worktree in `sandbox_workspace_write.writable_roots`, or full access. |

**Explore** is this dispatch made read-only: OpenCode's `explore` agent, or any agent with edit and shell denied; Claude Code's built-in Explore agent; on Codex an agent, since a custom agent inherits the parent's sandbox and read-only holds by instruction only.

## What degrades

**Codex.** No wake-up: the completion notice never starts a turn, so the orchestrator blocks in `wait_agent` inside one long turn. Dispatch, Integrate and Pacing degrade with it — the orchestrator cannot end its turn or prepare the next brief while implementers work, and a background command is polled or run in the foreground. A finished agent holds its concurrency slot until it is closed, so close each one as it lands. Explore degrades too: a subagent inherits the parent's sandbox, so read-only holds only by instruction.

**Claude Code.** Per call, `model` takes only the aliases above; pinning a full model ID or a variant means an agent definition in frontmatter. A background implementer's permissions must be settled up front (below), or its prompts surface in the main session, where nobody is there to answer. The agent id is documented to arrive on completion, so the ledger may record the session late. Dispatch degrades; the rest holds.

**OpenCode.** None found. Any provider's model and variant, the wake-up, resume, a background command and a phone push all work per call.

## Permission setup

The commission's last step points here. Before the first dispatch, confirm the harness lets a background implementer write in `<repo>/.marque/worktrees/` and run the build and the tests **without prompts**.

- **OpenCode:** external directories are allowed by default; the subagent's own permission config decides what it may run, so allow the implementer's shell and edit tools.
- **Claude Code:** name the worktree root in `additionalDirectories`, or run a permissive mode. Without either, each background write raises a prompt in the main session.
- **Codex:** list the worktree root in `sandbox_workspace_write.writable_roots`; otherwise `workspace-write` cannot write the worktree, and only full access would.

## Per-harness extras (not core)

Core steering happens **between turns**: stop, resume or redirect an implementer by resuming the same session. Messaging a running implementer mid-turn is a per-harness extra — OpenCode's `subagent` with the running `sessionID`, Claude Code's `SendMessage`, Codex's `send_input` are the channels it offers — and no step of the loop depends on one.

Plugins are extras too: a per-harness plugin can enforce the implementer rules in a hook, or update the ledger when a child stops. Extensions are the portable mechanism for changing a run (→ `reference/extensions.md`); the loop works without either.

## Phone push

OpenCode pushes to the OpenCode iOS app when the session has a phone callback. Claude Code's `PushNotification` reaches the desktop locally, and the phone only with Remote Control — not from third-party clouds. Codex has none: its `notify` program runs at turn end, so the notify channel falls back to chat, the default in `reference/extensions.md`.
