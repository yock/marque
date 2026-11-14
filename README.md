# Marque

**after `to-tickets`, Marque works your queue under your command.**

The developer commissions an orchestrator in their own harness, then works elsewhere: it picks the next unblocked ticket, briefs it with the design fixed, dispatches a cheaper implementer to a worktree, reviews the work, integrates it on the target branch and lands it. When a ticket is missing something, Marque asks on the ticket and moves on to the next one. It works down every ready ticket in the queue — across specs and standalone tickets, not one spec.

Three things make that delegation safe to grant:

- **Command.** The session is yours and stays yours. It runs while you're away and you can step into it at any moment: attended, not watched. There is no headless mode and no daemon.
- **Discipline.** The **commission** fixes authority, concurrency, landing mode, implementer model and budget before the first dispatch, and every question is settled on the ticket, never only in chat.
- **Scope.** The whole queue, recomputed after every landing, with the tickets that block each other ordered accordingly.

## How it differs

- **`implement-spec`** is the starter Marque grows from: one spec, context pointers, one review at the end. Marque keeps that shape and adds the queue, parallel implementers and the landing discipline.
- **Sandcastle** is the unattended, scripted road Marque doesn't take. Marque has no driver loop and no Node/TS runtime; the driver is the session you hold.
- **Nelson** plans missions in-session and is Claude-only.

Deliberately not done: unlimited fan-out, a batch merger agent, or defaulting to `--dangerously-skip-permissions`.

## Install

The public install address is the read-only GitHub mirror, [`yock/marque`](https://github.com/yock/marque); development happens on Gitea at the [Issues](#issues) link below.

**Claude Code:**

```sh
/plugin marketplace add yock/marque
/plugin install marque@marque
```

The skill appears as `/marque:marque`.

**Codex:**

```sh
codex plugin marketplace add yock/marque
# or, through skills.sh
npx skills add yock/marque -a codex
```

**OpenCode and other agents:**

```sh
npx skills add yock/marque -a <agent>
```

Add `-g` to install for every project rather than the current one.

## Requires

- **The setup files — required.** `docs/agents/issue-tracker.md` and the `## Agent skills` block in the target repo's `AGENTS.md` or `CLAUDE.md`. If either is missing, the commission stops and says **"run `/setup-matt-pocock-skills` first"**.
- **`to-tickets` — recommended, not required.** It is the usual ticket source; hand-written tickets in the same shape are accepted.
- **Python 3.9+**, standard library only. Marque never installs Matt's skills itself.
- **The tracker's CLI:** `tea` for Gitea, `gh` for GitHub, `glab` for GitLab. A local `.scratch/` tracker needs none.
- Compatible with `mattpocock/skills` 1.x. A 2.x is assumed to break it.

## Trackers

Gitea is the only backend tested by real runs. GitHub, GitLab and the local `.scratch/` tracker are best-effort until they have been dogfooded. Any other tracker works through `frontier.py --tickets-json`.

## Using it

Invoke the skill — `/marque:marque` in Claude Code, or your harness's equivalent — and it starts with the commission: `plugins/marque/skills/marque/reference/commission.md`. The commission checks the setup files, gap-checks the tracker doc against the operations Marque needs, names the account Marque acts as, settles the landing mode and records every term in `plan.md`. Then the loop begins.

Per-project overrides and extensions go in `docs/agents/marque.md`; per-user or per-machine ones in `~/.config/marque/marque.md`.

## Extensions

An extension is prose Marque reads and follows at one of five points — **commission**, **dispatch**, **brief**, **review**, **notify** — and it may add to or tighten the core, never loosen it. `examples/battery-pacing/` is the model extension: a user-level `marque.md` that slows dispatch as the battery falls, and the script it calls.

## Layout

```text
.claude-plugin/                          the marketplace, read by every harness
plugins/marque/                          the plugin: everything an install receives
plugins/marque/.claude-plugin/           the plugin manifest
plugins/marque/skills/marque/SKILL.md    the method
plugins/marque/skills/marque/scripts/    frontier.py, split_spec.py, land.py, ledger.py
plugins/marque/skills/marque/assets/     the explore and brief-tail templates
plugins/marque/skills/marque/reference/  commission, landing, asking, extensions, harnesses, operations, trackers/
examples/                                the worked extension
tests/                                   the suite
```

Only `plugins/marque/` ships. The development skills under `.agents/`, the docs and the tests stay in the repo.

Run the tests with `python3 -m unittest discover tests`.

## Pinning and releases

Releases are semver tags (`v0.1.0`, `v0.2.0`, …) with the version in `plugins/marque/.claude-plugin/plugin.json`. Pin one with `@v0.1.0` on skills.sh and `#v0.1.0` in a Claude marketplace:

```sh
npx skills add yock/marque@v0.1.0 -a codex
/plugin marketplace add yock/marque#v0.1.0
```

Installing without a version follows the default branch.

## Issues

Development and issues live on Gitea: <https://gitea.yock.dev/yock/marque/issues>. The GitHub mirror is read-only and takes no issues.

## License

MIT. See `LICENSE`.
