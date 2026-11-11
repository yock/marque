# symphony

An agent skill for orchestrating implementer agents through a wayfinder-format ticket
queue: pick the unblocked tickets, brief each with its design fixed, dispatch them to
parallel git worktrees, review, integrate, land and close. `SKILL.md` is the method;
`scripts/` and `templates/` are its tools.

## Install

Symlink the repo into the skills directories your harnesses read:

```sh
ln -s ~/Work/symphony ~/.agents/skills/symphony   # OpenCode and other agents
ln -s ~/Work/symphony ~/.claude/skills/symphony   # Claude Code
```

Requires Python 3.11+ and the tracker's CLI: `tea` (Gitea) or `gh` (GitHub).

## Per project

`docs/agents/symphony.toml` in the target repo (from `config.example.toml`), plus the
brief rules file it names: the project's build and test commands and the repo rules its
tests enforce, written to the implementer, with `{{WORKTREE}}`, `{{ISSUE}}`, `{{BRANCH}}`
filled in. The tracker conventions themselves stay in the repo's
`docs/agents/issue-tracker.md` and `triage-labels.md`.

## Scripts

| Script | Does |
|---|---|
| `scripts/frontier.py` | The ready, unclaimed, unblocked tickets, ranked by what they unblock; flags tickets it can't parse (`READ BY HAND`), tickets waiting on the user, and answered ones. |
| `scripts/split_spec.py N...` | A spec issue and its comments as greppable files under the state dir. |
| `scripts/brief.py brief N BRANCH` | Appends the filled brief tail to `briefs/N.md`. |
| `scripts/brief.py explore N SPEC` | Writes the read-only explore prompt for a ticket. |
| `scripts/battery.sh now \| watch MODE LOG` | Battery state; a watcher whose exit signals a threshold. |

## State

Per-effort state (`plan.md`, `ledger.tsv`, `briefs/`, `specs/`, `logs/`) lives in
`state.dir`, outside both repos and outside version control.
