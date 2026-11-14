# Harnesses

The skill speaks in neutral verbs. This file maps each one to **OpenCode**, **Claude Code** and **Codex**, naming the tool or setting that does the job, and then says what degrades on each. Facts are as of 2026-11 (#4's research); harnesses rename and move tools, so check a name against your harness's docs when it stops working.

Worktrees are not a harness feature here: Marque's own `git worktree add` creates them on every harness.

## The map

| Verb | OpenCode | Claude Code | Codex |
|---|---|---|---|
| **dispatch a background subagent** | `subagent`, always background; the `sessionID` comes back at once. | A Task subagent; it starts in the background by default. | `spawn_agent` returns an agent id, and the child runs while you work. |
| **resume the same session** | `subagent` again with its `sessionID`, running or finished; the model can change on resume. | `SendMessage` to the agent id. The built-in Explore and Plan agents are one-shot. | `send_input` (v1) or `followup_task` (v2); `resume_agent` reopens a closed agent, and `close_agent` frees a finished one's slot. |
| **push a notification** | `notify_phone`, when the session has a phone callback. | `PushNotification`: a desktop notification locally, a phone push with Remote Control. | No agent-callable push; a `notify` program runs at turn end. |
| **run a background command that wakes you** | `shell` with `background: true`; the session is notified when the command finishes. | Bash with `run_in_background`; `Monitor` streams output lines back. | None: long commands run through the unified exec and are polled with `write_stdin`. |
| **be woken when a subagent finishes** | A `<subagent>` message arrives each time a child goes idle. | The result reaches the orchestrator as a completion notification in a later turn. | None: the completion notice is injected without starting a turn. |
| **choose the model per subagent** | Any provider, `provider/model#variant` per call. | Per call, only the aliases `sonnet`, `opus`, `haiku` and `fable`, plus `effort`; a full model ID needs agent frontmatter. | `model` and `reasoning_effort` per call, from the parent's provider only. |
| **worktree write access** | `external_directory` is allowed by default; the subagent's permission config decides the rest. | `additionalDirectories`, or a permissive mode. | Every worktree in `sandbox_workspace_write.writable_roots`, or full access. |

**Explore** is this dispatch made read-only: OpenCode's `explore` agent, or any agent with edit and shell denied; Claude Code's built-in Explore agent; on Codex an agent, since a custom agent inherits the parent's sandbox and read-only holds by instruction only.
