# What each harness can do for an orchestrator

Research for issue #4 (map #1). The question: what do OpenCode, Claude Code and the Codex CLI offer that symphony's orchestrator relies on or could use? This feeds the decision on whether symphony ships as one portable skill plus optional per-harness plugins.

Sources were read on 2026-11-12. Docs are the vendors' current published pages. Source code is pinned to:

- OpenCode `anomalyco/opencode@1017760` (V2)
- Codex `openai/codex@c0cc9fc`

Claude Code is closed source, so its rows cite docs only. Every matrix cell links to its source; the labels are defined under [Sources](#sources).

## Capability matrix

| Capability | OpenCode (V2) | Claude Code | Codex CLI |
|---|---|---|---|
| **Background subagents** | The `subagent` tool always runs the child in the background and returns a `sessionID` at once ([OC-tools-src], [OC-subagent-src]). The published site still says "foreground or background" ([OC-tools]); the source at HEAD and its own docs say always background. | By default, a subagent spawned from the main conversation starts in the background ([CC-bg]). | `spawn_agent` returns an agent id, and the child runs while the parent keeps working ([CX-spec-wait]; [CX-subagents]). |
| **Woken when a subagent finishes** | **Yes.** The parent receives a `<subagent>` message each time the child goes idle, so it "can keep working or end its turn without waiting" ([OC-tools-src]). | **Yes.** A background subagent's result reaches Claude "as a completion notification in a later turn" ([CC-bg-results]). | **No.** The completion notice is injected into the parent thread *without starting a turn* (`inject_fragment_without_turn`, `trigger_turn: false`) ([CX-completion-src]). The parent has to stay in its turn and call `wait_agent` ([CX-spec-wait]). The docs say the main thread waits for all requested results ([CX-orchestration]). |
| **Background shell command that wakes you** (battery watcher, full suite) | Yes: `shell` with `background: true` notifies the session when the command finishes ([OC-tools]). | Yes: `run_in_background` creates background tasks, and `Monitor` streams output lines back to Claude ([CC-tools-bash], [CC-monitor]). | No documented wake. Long commands run through unified exec and are polled with `write_stdin` ([CX-hooks-tools]). |
| **Model per subagent** | Any configured provider and model. Set it per call with `model: "provider/model"` on the `subagent` tool ([OC-subagent-src]), or per agent with `model:` in the agent file ([OC-agents]). | Per call, only the aliases `sonnet`, `opus`, `haiku` or `fable`; a full model ID needs agent frontmatter. The order is call → frontmatter → `CLAUDE_CODE_SUBAGENT_MODEL` → main model. Claude models only ([CC-model]). | Per call, `model` on `spawn_agent` ([CX-spec-model]); also `[agents].default_subagent_model` or the custom agent's TOML. Only models from the parent's provider: a custom agent can't override `model_provider` ([CX-subagents]). The per-call fields can be hidden by config ([CX-spec-model]). |
| **Variant / effort per subagent** | `provider/model#variant`, validated against the model's variants ([OC-subagent-src], [OC-agents]). | `effort` per call or in frontmatter (`low` to `max`); it persists when the subagent is resumed ([CC-effort]). | `reasoning_effort` per call; `model_reasoning_effort` in the agent TOML or under `[agents]` ([CX-spec-model], [CX-subagents]). |
| **Resume a finished subagent with a follow-up** | Call `subagent` again with the `sessionID`, whether the child is running or finished; the model can be switched on resume ([OC-subagent-src]). Sessions are durable server records ([OC-plugin-sessions]). | `SendMessage` to the agent ID or name; the subagent resumes in the background with its full history and its per-call model ([CC-resume]). Built-in Explore and Plan are one-shot and can't be resumed ([CC-resume]). | `send_input` (v1) or `followup_task` (v2) to an existing agent; this triggers a turn if the agent is idle. `resume_agent` reopens a closed agent ([CX-spec-send], [CX-spec-resume]). Completed agents count toward the concurrency cap until closed ([CX-spec-close]). |
| **Git worktrees** | Code Mode `worktree_create/list/remove`, plus a `worktree.directory` config key ([OC-tools-wt], [OC-config-wt]). Plugins can supply a worktree strategy ([OC-plugin-wt]). | `claude --worktree`; `isolation: worktree` for subagents, which creates temporary worktrees under `.claude/worktrees/` with isolation checks; `WorktreeCreate` and `WorktreeRemove` hooks ([CC-worktrees], [CC-frontmatter]). | Worktrees are a desktop-app feature (`$CODEX_HOME/worktrees`, detached HEAD) ([CX-worktrees]). The CLI documents none. |
| **Writing to a worktree outside the launch dir** | `external_directory` is allowed by default ([OC-tools]). | Writes outside the working directories need approval unless the path is in `additionalDirectories` or a mode allows it ([CC-perm-dirs]). | The `workspace-write` sandbox writes only to the workspace plus `sandbox_workspace_write.writable_roots` ([CX-config-ref]). Subagents inherit the parent's sandbox ([CX-subagents]). |
| **Phone / desktop notifications** | Desktop: TUI `attention.notifications`, with a `subagent_done` sound ([OC-cli-alerts]). Phone: a `notify_phone` tool that pushes to the OpenCode iOS app when the session has a phone callback. I saw this tool in the session's tool catalog but found no public doc or source for it ([OC-notify-observed]). | `PushNotification` tool: a desktop notification locally, a phone push with Remote Control or in cloud sessions. Not available on Bedrock, Vertex or Foundry. There is also a `Notification` hook event ([CC-push], [CC-hooks-events]). | `notify = [program]` runs an external program on `agent-turn-complete`, and the TUI can emit notifications. The CLI has no built-in phone push ([CX-notify], [CX-notifications]). |
| **Skill discovery paths** | `~/.config/opencode/skills`, `~/.claude/skills`, `~/.agents/skills`; `.opencode/`, `.claude/` and `.agents/skills` from the cwd up to the project root; a `skills: [...]` config entry; HTTP catalogs ([OC-skills]). | `~/.claude/skills`; `.claude/skills` from the cwd up to the repo root; nested and `--add-dir` directories; the enterprise managed directory; synced claude.ai skills. **Not** `~/.agents/skills` ([CC-skills]). | `.agents/skills` from the cwd up to the repo root, `$HOME/.agents/skills`, `/etc/codex/skills`. Follows symlinks ([CX-skills]). |
| **Plugin / extension surface** | An npm or local package in **TypeScript/JS**. Its server part adds tools, agents, commands, skills, providers, models and worktree strategies, and can subscribe to events ([OC-plugins], [OC-plugin-server]). Hooks: prompt admission; model context, request and resolve; HTTP; retry; permission `evaluate`; shell `create.before`; tool `execute.before/after` ([OC-plugin-hooks]). It can create, prompt, wait on and switch the model of sessions directly ([OC-plugin-sessions]). It can also have TUI and GUI parts. | A plugin (`plugin.json`) bundles skills, commands, agents, hooks, MCP, LSP, executables, settings, output styles, channels and monitors ([CC-plugin-components]). Hooks are `command`, `http`, `mcp_tool`, `prompt` or `agent` handlers on about 30 events, including `PreToolUse` (can block), `SubagentStart/Stop`, `Notification`, `WorktreeCreate` and `Stop` ([CC-hooks-events]). Command handlers can be any language. **Mods** are in-process JS/TS handlers: they can rewrite or answer tool calls, override a subagent's model at `agent.spawn`, and add commands, tools and panes ([CC-mods], [CC-model]). | A plugin (`.codex-plugin/plugin.json`) bundles skills, MCP servers or apps, and hooks ([CX-skills-plugins], [CX-hooks-plugin]). Hooks are `command` (any language) or `mcp_tool` only; `prompt` and `agent` handlers aren't supported. Events: `PreToolUse` (block or rewrite), `PermissionRequest`, `PostToolUse`, `Pre/PostModelRequest`, `Pre/PostCompact`, `UserPromptSubmit`, `SubagentStart/Stop`, `Stop`, `Interrupt`, `SessionStart/End` ([CX-hooks]). There is no in-process plugin API. Custom agents are TOML in `~/.codex/agents/` or `.codex/agents/` ([CX-subagents]). |

## How symphony's loop degrades, per harness

Steps follow SKILL.md "The loop, per ticket", plus *Pacing* and the operations notifications. Steps handled by scripts, git and the tracker CLI (1 Pick, 3 Read, 4 Brief, 5 Claim and branch, 9 Land, 10 Recompute) work the same on all three harnesses and are omitted.

| Loop step | OpenCode | Claude Code | Codex CLI |
|---|---|---|---|
| **2 Explore**: read-only subagent on the implementer model | Full: the `explore` agent, or any agent with edit and shell denied, plus a per-call `model` ([OC-agents]). | Mostly full: the built-in Explore agent, or a custom one. The per-call model can only be an alias, so a pinned version or variant needs an agent definition ([CC-model]). | Degraded: "read-only" holds only by instruction. A custom agent can't get its own read-only sandbox; it inherits the parent's ([CX-subagents]). |
| **6 Dispatch**: background implementer on the chosen model; ledger gets the session ID | Full: any provider, model and variant per call, and the `sessionID` comes back immediately ([OC-subagent-src]). | Mostly full, with three limits. The cheaper model must be a Claude alias. The agent ID is documented as arriving on completion ([CC-resume]), so the ledger may get it late. Background subagents raise permission prompts in the main session, so unattended runs need a permissive mode or allow rules covering the worktree dirs ([CC-bg-perm], [CC-perm-dirs]). | **Degraded.** The model works (same provider only), but the orchestrator isn't woken on completion ([CX-completion-src]). It has to block in `wait_agent` inside one long turn, so "prepare the next brief while they work" and ending the turn don't work as on the others. The `workspace-write` sandbox also needs each worktree in `writable_roots`, or full access ([CX-config-ref]). |
| **7 Review**: failed review goes back to the same session | Full: `subagent` with the `sessionID`, model switchable ([OC-subagent-src]). | Full: `SendMessage` to the agent ID ([CC-resume]). Whether that ID survives an orchestrator `--resume` or crash is unverified. | Mostly full: `send_input` / `followup_task` / `resume_agent` ([CX-spec-send], [CX-spec-resume]). But the follow-up's result again arrives only via `wait_agent`, and completed agents occupy concurrency slots until `close_agent` ([CX-spec-close]). |
| **7 Review, stalls**: "session silent > 1 h" | Sessions are listable and waitable; a plugin could watch events ([OC-plugin-sessions]). | `/tasks` shows the running subagents ([CC-bg]). | `/subagents`, `list_agents` ([CX-subagents], [CX-spec-wait]). |
| **8 Integrate**: full suite in the background | Full ([OC-tools]). | Full ([CC-tools-bash]). | Degraded: no completion wake ([CX-hooks-tools]). The orchestrator polls or runs the suite in the foreground. |
| **Pacing**: battery watcher whose exit wakes you | Full ([OC-tools]). | Full (background Bash or `Monitor`) ([CC-monitor]). | Degraded, for the same reason: no wake. |
| **Notifications** (operations.md) | Phone via `notify_phone` when the session has a phone callback ([OC-notify-observed]). | Desktop via `PushNotification`; phone only with Remote Control, and not on third-party clouds ([CC-push]). | No agent-callable push. The user's own `notify` script fires only at turn end. Phone delivery means the skill calls a script of its own through the shell ([CX-notify]). |
| **Install**: README's two symlinks | `~/.agents/skills` (or `~/.claude/skills`) ([OC-skills]). | `~/.claude/skills` only ([CC-skills]). | `~/.agents/skills`, symlinks followed ([CX-skills]). The existing install already covers Codex. |

## What a per-harness plugin could add

- **OpenCode** (TS plugin):
  - The `tool.execute.before` and `permission evaluate` hooks could enforce the implementer rules (no push, no tracker writes, no main checkout) instead of only stating them in the brief ([OC-plugin-hooks]).
  - An `event.subscribe` listener could update the ledger when a child goes idle ([OC-plugin-server]).
  - A plugin tool could wrap landing as one guarded operation.
- **Claude Code**:
  - Shipped agent definitions could pin the implementer's full model ID and effort ([CC-frontmatter]).
  - `PreToolUse` hooks could enforce the implementer rules ([CC-hooks-events]). Hook input carries `agent_id` and `agent_type` inside subagents.
  - `SubagentStop` could update the ledger.
  - A mod's `agent.spawn` could force the implementer model ([CC-model]).
- **Codex**:
  - A plugin can ship skills and `command` hooks: `PreToolUse` to block or rewrite, `SubagentStop` for the ledger ([CX-hooks]).
  - Custom agent TOML pins the model and effort ([CX-subagents]). I didn't confirm whether a plugin can ship agents.
  - No plugin can make subagent completion start a parent turn. That limit is in core ([CX-completion-src]).

## Open points

- On Claude Code and Codex, I didn't verify whether a subagent ID stays resumable after the orchestrator session itself is resumed or restarted. OpenCode child sessions are durable server records.
- OpenCode's `notify_phone` has no public documentation. Its availability depends on a phone callback on the session or its parent.
- The published OpenCode site (foreground or background) disagrees with the V2 source and in-repo docs (always background). I took the source as authoritative.

## Sources

[OC-tools]: https://opencode.ai/docs/tools/
[OC-tools-wt]: https://opencode.ai/docs/tools/#worktrees
[OC-tools-src]: https://github.com/anomalyco/opencode/blob/101776024cc69bafb3f9dc90027ab4d1eab40a2a/services/site/src/docs/content/tools.mdx?plain=1#L208-L225
[OC-subagent-src]: https://github.com/anomalyco/opencode/blob/101776024cc69bafb3f9dc90027ab4d1eab40a2a/packages/core/src/tool/plugin/subagent.ts#L18-L56
[OC-agents]: https://opencode.ai/docs/agents/
[OC-config-wt]: https://opencode.ai/docs/config/#worktrees
[OC-cli-alerts]: https://opencode.ai/docs/cli/config/#alerts
[OC-skills]: https://opencode.ai/docs/skills/#discovery
[OC-plugins]: https://opencode.ai/docs/build/plugins/
[OC-plugin-server]: https://opencode.ai/docs/build/plugins/server/
[OC-plugin-sessions]: https://github.com/anomalyco/opencode/blob/101776024cc69bafb3f9dc90027ab4d1eab40a2a/services/site/src/docs/content/build/plugins/server.mdx?plain=1#L771-L836
[OC-plugin-hooks]: https://github.com/anomalyco/opencode/blob/101776024cc69bafb3f9dc90027ab4d1eab40a2a/services/site/src/docs/content/build/plugins/server.mdx?plain=1#L1367-L1838
[OC-plugin-wt]: https://opencode.ai/docs/build/plugins/server/#worktrees
[OC-notify-observed]: https://opencode.ai/docs/tools/ "not documented; observed as the notify_phone tool in an OpenCode session's tool catalog, 2026-11-12"
[CC-bg]: https://code.claude.com/docs/en/sub-agents#run-subagents-in-foreground-or-background
[CC-bg-results]: https://code.claude.com/docs/en/sub-agents#tools-permissions-and-results-of-background-subagents
[CC-bg-perm]: https://code.claude.com/docs/en/sub-agents#tools-permissions-and-results-of-background-subagents
[CC-model]: https://code.claude.com/docs/en/sub-agents#choose-a-model
[CC-effort]: https://code.claude.com/docs/en/sub-agents#choose-an-effort-level
[CC-resume]: https://code.claude.com/docs/en/sub-agents#resume-subagents
[CC-frontmatter]: https://code.claude.com/docs/en/sub-agents#supported-frontmatter-fields
[CC-worktrees]: https://code.claude.com/docs/en/worktrees
[CC-perm-dirs]: https://code.claude.com/docs/en/permissions#working-directories
[CC-tools-bash]: https://code.claude.com/docs/en/interactive-mode#how-backgrounding-works
[CC-monitor]: https://code.claude.com/docs/en/tools-reference#monitor-tool
[CC-push]: https://code.claude.com/docs/en/tools-reference
[CC-hooks-events]: https://code.claude.com/docs/en/hooks
[CC-skills]: https://code.claude.com/docs/en/skills#where-skills-live
[CC-plugin-components]: https://code.claude.com/docs/en/plugins/components
[CC-mods]: https://code.claude.com/docs/en/plugins/mods/overview
[CX-subagents]: https://learn.chatgpt.com/docs/agent-configuration/subagents
[CX-orchestration]: https://learn.chatgpt.com/docs/agent-configuration/subagents#orchestration-and-thread-controls
[CX-spec-send]: https://github.com/openai/codex/blob/c0cc9fc820f62e4dbdde68214dd6d792d6c8a7ee/codex-rs/core/src/tools/handlers/multi_agents_spec.rs#L190-L262
[CX-spec-resume]: https://github.com/openai/codex/blob/c0cc9fc820f62e4dbdde68214dd6d792d6c8a7ee/codex-rs/core/src/tools/handlers/multi_agents_spec.rs#L264-L284
[CX-spec-wait]: https://github.com/openai/codex/blob/c0cc9fc820f62e4dbdde68214dd6d792d6c8a7ee/codex-rs/core/src/tools/handlers/multi_agents_spec.rs#L286-L332
[CX-spec-close]: https://github.com/openai/codex/blob/c0cc9fc820f62e4dbdde68214dd6d792d6c8a7ee/codex-rs/core/src/tools/handlers/multi_agents_spec.rs#L336-L352
[CX-spec-model]: https://github.com/openai/codex/blob/c0cc9fc820f62e4dbdde68214dd6d792d6c8a7ee/codex-rs/core/src/tools/handlers/multi_agents_spec.rs#L120-L140
[CX-completion-src]: https://github.com/openai/codex/blob/c0cc9fc820f62e4dbdde68214dd6d792d6c8a7ee/codex-rs/core/src/agent/control.rs#L434-L567
[CX-hooks]: https://learn.chatgpt.com/docs/hooks
[CX-hooks-plugin]: https://learn.chatgpt.com/docs/hooks#plugin-bundled-hooks
[CX-hooks-tools]: https://learn.chatgpt.com/docs/hooks#tool-coverage
[CX-skills]: https://learn.chatgpt.com/docs/build-skills
[CX-skills-plugins]: https://learn.chatgpt.com/docs/skills-and-plugins
[CX-worktrees]: https://learn.chatgpt.com/docs/environments/git-worktrees
[CX-notify]: https://learn.chatgpt.com/docs/config-file/config-advanced#notifications
[CX-notifications]: https://learn.chatgpt.com/docs/notifications
[CX-config-ref]: https://learn.chatgpt.com/docs/config-file/config-reference

Labels used above:

- `OC-tools`: <https://opencode.ai/docs/tools/>
- `OC-tools-wt`: <https://opencode.ai/docs/tools/#worktrees>
- `OC-tools-src`: <https://github.com/anomalyco/opencode/blob/101776024cc69bafb3f9dc90027ab4d1eab40a2a/services/site/src/docs/content/tools.mdx?plain=1#L208-L225>
- `OC-subagent-src`: <https://github.com/anomalyco/opencode/blob/101776024cc69bafb3f9dc90027ab4d1eab40a2a/packages/core/src/tool/plugin/subagent.ts#L18-L56>
- `OC-agents`: <https://opencode.ai/docs/agents/>
- `OC-config-wt`: <https://opencode.ai/docs/config/#worktrees>
- `OC-cli-alerts`: <https://opencode.ai/docs/cli/config/#alerts>
- `OC-skills`: <https://opencode.ai/docs/skills/#discovery>
- `OC-plugins`: <https://opencode.ai/docs/build/plugins/>
- `OC-plugin-server`: <https://opencode.ai/docs/build/plugins/server/>
- `OC-plugin-sessions`: <https://github.com/anomalyco/opencode/blob/101776024cc69bafb3f9dc90027ab4d1eab40a2a/services/site/src/docs/content/build/plugins/server.mdx?plain=1#L771-L836>
- `OC-plugin-hooks`: <https://github.com/anomalyco/opencode/blob/101776024cc69bafb3f9dc90027ab4d1eab40a2a/services/site/src/docs/content/build/plugins/server.mdx?plain=1#L1367-L1838>
- `OC-plugin-wt`: <https://opencode.ai/docs/build/plugins/server/#worktrees>
- `OC-notify-observed`: <https://opencode.ai/docs/tools/> (not documented; observed as the notify_phone tool in an OpenCode session's tool catalog, 2026-11-12)
- `CC-bg`: <https://code.claude.com/docs/en/sub-agents#run-subagents-in-foreground-or-background>
- `CC-bg-results`: <https://code.claude.com/docs/en/sub-agents#tools-permissions-and-results-of-background-subagents>
- `CC-bg-perm`: <https://code.claude.com/docs/en/sub-agents#tools-permissions-and-results-of-background-subagents>
- `CC-model`: <https://code.claude.com/docs/en/sub-agents#choose-a-model>
- `CC-effort`: <https://code.claude.com/docs/en/sub-agents#choose-an-effort-level>
- `CC-resume`: <https://code.claude.com/docs/en/sub-agents#resume-subagents>
- `CC-frontmatter`: <https://code.claude.com/docs/en/sub-agents#supported-frontmatter-fields>
- `CC-worktrees`: <https://code.claude.com/docs/en/worktrees>
- `CC-perm-dirs`: <https://code.claude.com/docs/en/permissions#working-directories>
- `CC-tools-bash`: <https://code.claude.com/docs/en/interactive-mode#how-backgrounding-works>
- `CC-monitor`: <https://code.claude.com/docs/en/tools-reference#monitor-tool>
- `CC-push`: <https://code.claude.com/docs/en/tools-reference>
- `CC-hooks-events`: <https://code.claude.com/docs/en/hooks>
- `CC-skills`: <https://code.claude.com/docs/en/skills#where-skills-live>
- `CC-plugin-components`: <https://code.claude.com/docs/en/plugins/components>
- `CC-mods`: <https://code.claude.com/docs/en/plugins/mods/overview>
- `CX-subagents`: <https://learn.chatgpt.com/docs/agent-configuration/subagents>
- `CX-orchestration`: <https://learn.chatgpt.com/docs/agent-configuration/subagents#orchestration-and-thread-controls>
- `CX-spec-send`: <https://github.com/openai/codex/blob/c0cc9fc820f62e4dbdde68214dd6d792d6c8a7ee/codex-rs/core/src/tools/handlers/multi_agents_spec.rs#L190-L262>
- `CX-spec-resume`: <https://github.com/openai/codex/blob/c0cc9fc820f62e4dbdde68214dd6d792d6c8a7ee/codex-rs/core/src/tools/handlers/multi_agents_spec.rs#L264-L284>
- `CX-spec-wait`: <https://github.com/openai/codex/blob/c0cc9fc820f62e4dbdde68214dd6d792d6c8a7ee/codex-rs/core/src/tools/handlers/multi_agents_spec.rs#L286-L332>
- `CX-spec-close`: <https://github.com/openai/codex/blob/c0cc9fc820f62e4dbdde68214dd6d792d6c8a7ee/codex-rs/core/src/tools/handlers/multi_agents_spec.rs#L336-L352>
- `CX-spec-model`: <https://github.com/openai/codex/blob/c0cc9fc820f62e4dbdde68214dd6d792d6c8a7ee/codex-rs/core/src/tools/handlers/multi_agents_spec.rs#L120-L140>
- `CX-completion-src`: <https://github.com/openai/codex/blob/c0cc9fc820f62e4dbdde68214dd6d792d6c8a7ee/codex-rs/core/src/agent/control.rs#L434-L567>
- `CX-hooks`: <https://learn.chatgpt.com/docs/hooks>
- `CX-hooks-plugin`: <https://learn.chatgpt.com/docs/hooks#plugin-bundled-hooks>
- `CX-hooks-tools`: <https://learn.chatgpt.com/docs/hooks#tool-coverage>
- `CX-skills`: <https://learn.chatgpt.com/docs/build-skills>
- `CX-skills-plugins`: <https://learn.chatgpt.com/docs/skills-and-plugins>
- `CX-worktrees`: <https://learn.chatgpt.com/docs/environments/git-worktrees>
- `CX-notify`: <https://learn.chatgpt.com/docs/config-file/config-advanced#notifications>
- `CX-notifications`: <https://learn.chatgpt.com/docs/notifications>
- `CX-config-ref`: <https://learn.chatgpt.com/docs/config-file/config-reference>
