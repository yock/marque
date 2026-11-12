# How Matt Pocock's skills are distributed and composed

Research for ticket #3 (map #1). Question: how are Matt Pocock's skills distributed, installed and composed, and how could a third-party skill (symphony) join that ecosystem?

Sources, read 2026-11-12:

- **Upstream**: `https://github.com/mattpocock/skills` at commit `4ae2317ddb22b046e26455e4f9c9b3aaaf62212d` (2026-10-31), plugin version 1.3.2 (`.claude-plugin/plugin.json`, `package.json`). Below, `upstream:<path>` means `https://github.com/mattpocock/skills/blob/4ae2317ddb22b046e26455e4f9c9b3aaaf62212d/<path>`.
- **skills.sh CLI**: `https://github.com/vercel-labs/skills` at `e781cb4d` (2026-11-10). `vskills:<path>` means `https://github.com/vercel-labs/skills/blob/e781cb4d07433dfe1d19e924ed45cc61738c55ec/<path>`.
- **Local copies**: `~/.agents/skills/<name>/` on this machine, installed 2026-10-05 (from directory mtimes).

## 1. Install channels, and what goes where per harness

### The canonical install story

Upstream keeps one install wording in `upstream:.agents/install-block.md`, and `README.md` copies it word for word. The rule is "managed installs first", meaning installs that update themselves. skills.sh is the fallback, labelled "manual updates" (`upstream:.agents/install-block.md`, "Managed installs first"):

| Agent | Route | Updates itself? |
|---|---|---|
| Claude Code | `claude plugin install mattpocock-skills@claude-plugins-official` | Yes, by default |
| Codex | `codex plugin marketplace add mattpocock/skills` then `codex plugin add mattpocock-skills@mattpocock` | Yes, at startup |
| Copilot CLI / VS Code | `@mattpocock` marketplace / "Install Plugin From Source" | Yes, after a one-time `autoUpdate: true` (Copilot) / daily (VS Code) |
| Gemini CLI | `gemini skills install <repo> --path skills/engineering` (and again for `productivity`) | No |
| Everyone else, **OpenCode included** | `npx skills@latest add mattpocock/skills -a <agent>` (skills.sh) | No: `npx skills@latest update`, and re-run `add` to pick up new skills |

Sources: `upstream:.agents/install-block.md`, `upstream:README.md` ("Installation"). OpenCode is in the skills.sh `-a` list ("cursor, opencode, devin, windsurf, amp, pi"), and nowhere else.

**Pick one route per agent.** The plugin is "a managed, read-only bundle you subscribe to". skills.sh "writes files you own and edit", and installing both gives the user every skill twice (`upstream:.agents/install-block.md`, "The two routes are exclusive"; `upstream:README.md`).

**Only the promoted skills ship.** The plugin carries exactly the promoted buckets, `engineering/` and `productivity/`, listed one by one in `.claude-plugin/plugin.json`'s `skills` array. `misc/`, `in-progress/` and `deprecated/` stay out (`upstream:CLAUDE.md`; `upstream:.claude-plugin/plugin.json`). skills.sh serves every skill in the repo, non-promoted ones included (`upstream:CHANGELOG.md`, entry for #752: "all six were installable through skills.sh, which serves every skill in the repo"). The local install shows this: `~/.agents/skills/` holds in-progress skills such as `chief-of-staff`, `loop-me`, `writing-beats` and `setup-ts-deep-modules`.

### What an install puts where

**Claude Code (plugin).** The `claude-plugins-official` listing points at the repo's git URL with a **pinned sha**, and reads `.claude-plugin/plugin.json` directly. "A release reaches installed users when that pin moves, not the moment we tag" (`upstream:.agents/adr/0002-ship-as-a-claude-code-plugin.md`, "Update, 2026-08-05"). Every plugin component is namespaced under the plugin name, so the skills appear as `/mattpocock-skills:<skill>` (`https://code.claude.com/docs/en/plugins-reference.md`, `name` field: "Every component is namespaced under it"; `upstream:.out-of-scope/harness-name-collisions.md` gives `/mattpocock-skills:research` as the example). `.claude-plugin/marketplace.json` makes the repo its own single-plugin marketplace. It is now kept only as a fallback for forks and unreleased commits (ADR 0002, same update).

**Codex (plugin).** Codex installs from the repo's own marketplace, and since 2026-10-07 reads `.claude-plugin/` when no `.codex-plugin/` exists. Codex **copies the plugin tree into its cache and drops symlinks** (`upstream:.agents/adr/0002-ship-as-a-claude-code-plugin.md`, "The constraint" and "Update, 2026-10-07", citing `https://github.com/openai/codex/blob/main/codex-rs/core-plugins/src/manifest.rs`). User-invoked skills carry `policy.allow_implicit_invocation: false` in `agents/openai.yaml` (`upstream:.agents/invocation.md`).

**skills.sh (OpenCode, Codex or Claude Code by choice).** `npx skills add` installs into the current project by default, or user-wide with `-g` (`vskills:README.md`; `vskills:docs/commands.md`, "Installation Scope"). It symlinks each agent's directory to one canonical copy by default. `--copy` makes an independent copy per agent instead (`vskills:docs/commands.md`, "Installation Methods"). Per-agent directories (`vskills:docs/agents.md`):

| Agent | Project | Global (`-g`) |
|---|---|---|
| OpenCode (`opencode`) | `.agents/skills/` | `~/.config/opencode/skills/` |
| Claude Code (`claude-code`) | `.claude/skills/` | `~/.claude/skills/` |
| Codex (`codex`) | `.agents/skills/` | `~/.agents/skills/` |

OpenCode itself also reads `.opencode/skills/`, `~/.agents/skills/`, `.claude/skills/` and `~/.claude/skills/` (`https://opencode.ai/docs/skills`), so `~/.agents/skills/` serves OpenCode and Codex alike. A project install records each skill in a root `skills-lock.json` (source, `skillPath`, `computedHash`) that can be committed and restored (`vskills:README.md`, "Lock File Content Hash"). This machine has examples in other projects, e.g. `/home/myockey/Work/homelab/skills-lock.json` with `"source": "mattpocock/skills"` and `"skillPath": "skills/engineering/..."`.

**Discovery.** skills.sh finds `SKILL.md` files up to three levels under the skill containers, so `skills/<category>/<name>/SKILL.md` works. It also reads skills listed in `.claude-plugin/marketplace.json` / `plugin.json` (`vskills:docs/creating-skills.md`, "Skill Discovery" and "Plugin Manifest Discovery"). One `.claude-plugin/` manifest therefore drives Claude Code, Codex, Copilot **and** skills.sh.

**Maintainer dev install.** `scripts/link-skills.sh` symlinks every non-deprecated, non-misc skill into `~/.claude/skills` and `~/.agents/skills`. It is "a dev-only script … not a supported installer" (`upstream:scripts/link-skills.sh`). Symphony's README uses the same method today (`/home/myockey/Work/symphony/README.md`, "Install").

## 2. How skills reference one another

**Two kinds of skill, by who can invoke them** (`upstream:.agents/invocation.md`; `upstream:README.md`, "Reference"):

- **User-invoked**: `disable-model-invocation: true` in the frontmatter, plus `policy.allow_implicit_invocation: false` in `agents/openai.yaml`. Only the human can fire one, by typing it. `setup-matt-pocock-skills`, `to-tickets`, `to-spec`, `implement-spec`, `wayfinder` and `triage` are all user-invoked (their frontmatter, `~/.agents/skills/*/SKILL.md`).
- **Model-invoked**: the model or the user can fire it, e.g. `tdd`, `grilling`, `domain-modeling`, `research`, `code-review`, `prototype`.

**Dependencies are written as tool calls**, e.g. `Call the Skill tool with "grilling"`. Upstream doesn't use `../other-skill/FILE.md` links or bare `/skill` mentions. "Shared reference docs live inside the skill that owns them; other skills reach that material by calling the Skill tool with it, not by linking across folders." A step that needs two skills is two calls (`upstream:.agents/invocation.md`, "Dependencies between them"; `upstream:CHANGELOG.md` #878). A user-invoked skill **can't be called** by another skill. A user-invoked precondition is phrased as an instruction to the human (`upstream:CHANGELOG.md` #880).

**The setup dependency.** ADR 0001 splits dependents in two (`upstream:.agents/adr/0001-explicit-setup-pointer-only-for-hard-dependencies.md`):

- **Hard dependency** (`to-tickets`, `to-spec`, `triage`; in practice also `wayfinder` and `implement-spec`) carries the one-liner: "The issue tracker and triage label vocabulary should have been provided to you. If not, tell the user to run `/setup-matt-pocock-skills`" (`~/.agents/skills/to-tickets/SKILL.md`, `~/.agents/skills/to-spec/SKILL.md`, `~/.agents/skills/implement-spec/SKILL.md`, `~/.agents/skills/wayfinder/SKILL.md`).
- **Soft dependency** (`tdd`, `diagnosing-bugs`, `improve-codebase-architecture`) mentions "the project's domain glossary" and "ADRs" in passing and works without them.

**"Provided to you" means a pointer.** Skills don't hard-code `docs/agents/issue-tracker.md`. They follow the `## Agent skills` block that setup writes into `CLAUDE.md` / `AGENTS.md`, which the harness loads into context, to wherever the tracker doc lives. Wayfinder once hard-coded the path and was fixed to follow the pointer (`upstream:CHANGELOG.md` #472). The block format is in `~/.agents/skills/setup-matt-pocock-skills/SKILL.md`, step 4, and this repo's copy is in `/home/myockey/Work/symphony/AGENTS.md`.

**`ask-matt` is the router** over all user-reachable skills. Upstream keeps it in sync whenever a skill is added or changes its place in the flows (`upstream:CLAUDE.md`). Third-party skills aren't in it.

## 3. What `setup-matt-pocock-skills` writes, and how the templates get extended

### Outputs

All of these are written per repo and committed. "There is no user-level or global mode" (`upstream:docs/engineering/setup-matt-pocock-skills.md`, "Prerequisites"; `~/.agents/skills/setup-matt-pocock-skills/SKILL.md`, steps 3 and 4):

| File | Content | Condition |
|---|---|---|
| `docs/agents/issue-tracker.md` | Copied from a seed template: `issue-tracker-github.md`, `issue-tracker-gitlab.md` or `issue-tracker-local.md`. For **Other** (Jira, Linear, …), written from scratch from the user's one-paragraph description | always |
| `docs/agents/triage-labels.md` | Five-row table mapping each canonical role (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`) to the repo's label string | only if the `triage` skill is installed |
| `docs/agents/domain.md` | Domain doc rules: read `GLOSSARY.md` / `GLOSSARY-MAP.md` and `docs/adr/`, single- or multi-context layout | always |
| `## Agent skills` block | `### Issue tracker`, `### Triage labels`, `### Domain docs`, each a one-liner plus a `See docs/agents/…` pointer. Goes in `CLAUDE.md` if it exists, else `AGENTS.md`; if neither exists, setup asks | always |

Upstream additions not in the local copy: setup now creates missing triage labels on GitHub/GitLab, connects a git remote before writing a GitHub/GitLab tracker, and offers to `git mv` a legacy `CONTEXT.md` to `GLOSSARY.md` (`upstream:skills/engineering/setup-matt-pocock-skills/SKILL.md`; `upstream:CHANGELOG.md` #1197, #1228). The docs page still says "It doesn't [create labels]", so upstream's own docs disagree with its skill here (`upstream:docs/engineering/setup-matt-pocock-skills.md`, "It didn't create my triage labels").

### Template structure

Each tracker template has the same sections (`~/.agents/skills/setup-matt-pocock-skills/issue-tracker-{github,gitlab,local}.md`):

1. `## Conventions`: create / read / list / comment / label / close commands. Upstream's GitHub template also has "Make an issue a sub-issue of a parent", "Blocking" and "Count open blockers" here.
2. `## Pull requests as a triage surface` (GitHub/GitLab only): a flag, off by default, that `/triage` reads.
3. `## When a skill says "publish to the issue tracker"`.
4. `## When a skill says "fetch the relevant ticket"`.
5. `## Wayfinding operations`: Map, Child ticket, Blocking, Frontier query, Claim, Resolve.

### How "Wayfinding operations" gets there

**Wayfinder doesn't add it. It is part of each seed template, and setup copies the template whole.** The changelog entry that moved wayfinder onto the tracker says: "Wayfinder stays tracker-agnostic (GitHub, GitLab, local-markdown) behind a pointer in `docs/agents/issue-tracker.md`, and `setup-matt-pocock-skills` seeds the 'Wayfinding operations' section" (`upstream:CHANGELOG.md` #464). At run time, wayfinder only reads it: "Consult the tracker doc's 'Wayfinding operations' section for how _this_ repo expresses them … If no tracker has been provided, default to the local-markdown tracker" (`~/.agents/skills/wayfinder/SKILL.md`, "The Map").

So the seed templates are the only extension mechanism, and they live inside the setup skill's own folder. A skill outside upstream has **no hook** to add a section to `issue-tracker.md`. On the **Other** path, nobody adds a "Wayfinding operations" section unless the user or agent writes it. This repo's Gitea doc (`/home/myockey/Work/symphony/docs/agents/issue-tracker.md`) was written by hand in the GitHub template's shape, "Wayfinding operations" included. The upstream docs mention users doing this ("a Gitea CLI shaped like `gh`", `upstream:docs/engineering/setup-matt-pocock-skills.md`).

To refresh `docs/agents/` after a template change, re-run setup. Changelog entries say "Re-run `/setup-matt-pocock-skills` to refresh `docs/agents/issue-tracker.md`" (`upstream:CHANGELOG.md` #1187, #1188, #1228). A separate verify mode is out of scope (`upstream:.out-of-scope/setup-skill-verify-mode.md`).

## 4. The ticket format `to-tickets` publishes

The source is `~/.agents/skills/to-tickets/SKILL.md`, step 5, plus the upstream diff below.

### Real tracker (GitHub, GitLab, …)

- One issue per ticket, published **in dependency order (blockers first)** so edges can use real ids.
- **Blocking**: "Use the platform's native blocking relationship where it has one; otherwise set each ticket's 'Blocked by' to the blocking issues."
- **Parent** (upstream only): "If the source was an existing issue, make each ticket its sub-issue (tracker doc's operation)." This uses the GitHub sub-issue command from the template.
- **Label**: `ready-for-agent`, mapped through `triage-labels.md`, "unless instructed otherwise".
- "Do NOT close or modify any parent issue."
- Body (`<issue-template>`):

```markdown
## Parent

A reference to the parent issue on the tracker (if the source was an existing issue, otherwise omit this section).

## What to build

The end-to-end behaviour this ticket makes work, from the user's perspective, not layer-by-layer implementation.

## Acceptance criteria

- [ ] Criterion 1
- [ ] Criterion 2

## Blocked by

- A reference to each blocking ticket, or "None (can start immediately)".
```

Upstream adds to the `## Blocked by` bullet: "Omit this section when blockers were set as native edges" (`upstream:skills/engineering/to-tickets/SKILL.md`; `upstream:CHANGELOG.md` #1188).

How native blocking works on each tracker (from its seed template):

- **GitHub**: native issue dependencies. Upstream uses `gh issue create --blocked-by <n>,<n>` / `gh issue edit <child> --add-blocked-by <blocker>` (gh 2.94+), or `POST repos/<o>/<r>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`. Open blockers come from `.issue_dependencies_summary.blocked_by`. Without native dependencies, fall back to a `Blocked by: #<n>, #<n>` line at the top of the body. Parent: `gh issue create --parent <p>` / `gh issue edit <p> --add-sub-issue <child>`, falling back to `Part of #<parent>` at the top (`upstream:skills/engineering/setup-matt-pocock-skills/issue-tracker-github.md`).
- **GitLab**: the `/blocked_by #<n>` quick action posted as a note (Premium/Ultimate). On the free tier, a `Blocked by:` line instead (`~/.agents/skills/setup-matt-pocock-skills/issue-tracker-gitlab.md`).

### Local markdown

One file per ticket at `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01` in dependency order, never a combined file (`~/.agents/skills/to-tickets/SKILL.md`; `~/.agents/skills/setup-matt-pocock-skills/issue-tracker-local.md`):

```markdown
# <NN>: <Ticket title>

**What to build:** …

**Blocked by:** the numbers/titles of the tickets that gate this one, or "None (can start immediately)".

**Status:** ready-for-agent

- [ ] Acceptance criterion 1
```

### `to-tickets` vs. wayfinder tickets

`Part of #<map>` is the **wayfinder** child convention, and for to-tickets only the sub-issue fallback (`issue-tracker-gitlab.md`, `issue-tracker-github.md`, "Wayfinding operations"). to-tickets uses a `## Parent` heading. Wayfinder tickets carry only `wayfinder:<type>` labels, "never a triage label like `ready-for-agent`: they are decisions, not implementation work" (`upstream:skills/engineering/wayfinder/SKILL.md`, not yet in the local copy).

### Implication for symphony (not a decision)

`symphony/SKILL.md` says its tickets "follow the wayfinder format (`Part of #<spec>`, `Blocked by:`, triage labels)". `scripts/frontier.py` reads a `Part of #` line plus a `Blocked by:` top line and/or a `## Blocked by` section (`/home/myockey/Work/symphony/scripts/frontier.py:7-9,34-36`). It flags a ticket with "no `Part of #` line" for reading by hand (`frontier.py:59`). Current upstream to-tickets output on GitHub has `## Parent` and sub-issue links instead of `Part of #`, and **no** `## Blocked by` section when edges are native. For such a ticket, frontier.py as written lists it under READ BY HAND (no `Part of #`). It also records "no blocker declaration" and computes **no blockers**, so a ticket whose edges exist only natively looks unblocked (`frontier.py:52-59`). The same applies on any tracker where to-tickets uses native edges, Gitea included, since this repo's tracker doc names Gitea's native dependencies as canonical. Reading native dependencies and parent links per tracker is the gap.

## 5. Outside contributions and third-party skills

- **Curated, not open.** "This repo is the set of skills I use every day. It is curated" (`upstream:SCOPE.md`). An idea or feedback issue stays open only if it shows an **observed failure** from a real session **and** fits the philosophy. It must not be "a config option, a harness-specific branch, or a tweak to suit one person's workflow"; those "belong in your own `CLAUDE.md` / `AGENTS.md`, or in a fork (skills.sh gives you an editable copy)" (`upstream:SCOPE.md`, "The bar").
- **Pull requests are open to collaborators only.** Outsiders describe the fix in an issue. New-skill ideas and donated skills go to GitHub Discussions → Ideas, and so does support for another harness or tracker (`upstream:CONTRIBUTING.md`; `upstream:.github/ISSUE_TEMPLATE/config.yml`).
- **New skills are refused.** "This repo does not take proposals or contributions for new skills, including ones that arrive with a ready branch or a fork … if you can compose the behaviour from existing skills, it doesn't get a new skill … **You're very welcome to publish a skill yourself. skills.sh makes that straightforward, and nothing here needs to know about it.**" Examples cited include #1051 (a ready `/red-team` contribution) and #1166 (`upstream:.out-of-scope/new-skills.md`).
- **Only GitHub, GitLab and local markdown are supported trackers.** Any other tracker (Jira, Linear, Azure DevOps, …) goes through **Other**: "That file is yours. If you've refined a Jira or Linear workflow that works, keep it in your own repo or publish it, and point the setup at it" (`upstream:.out-of-scope/mainstream-issue-trackers-only.md`). By that reasoning, Gitea won't get a seed template upstream.
- **`misc/` is frozen**, and every issue against it is closed (`upstream:SCOPE.md`, "By bucket").
- **Names are not changed** to dodge collisions with harness built-ins. Plugin users use the namespaced form, and skills.sh users rename their own copy (`upstream:.out-of-scope/harness-name-collisions.md`).
- **AI-written issues**: one problem per issue, short, repro first, no pasted specs or rewritten `SKILL.md` (`upstream:CONTRIBUTING.md`).
- **No plugin or extension API** exists for third-party skills: no registry of companion skills, no hook into setup templates, no entry in `ask-matt`. A third party joins by publishing its own repo, installable through skills.sh and/or its own `.claude-plugin/` manifest. It then reads the `docs/agents/*.md` files setup leaves behind, as an ordinary consumer (sections 1 and 3 above).
- **Overlapping upstream work**: `implement-spec`, now promoted, already runs implementer subagents across the ticket frontier on one integration branch, then `code-review` (`~/.agents/skills/implement-spec/SKILL.md`; `upstream:CHANGELOG.md` #1120). The in-progress `software-factory` skill (user-invoked) is a vocabulary for designing agent systems that turn tickets into merged code, with a ticket-tracker survey that names Forgejo (`upstream:skills/in-progress/software-factory/SKILL.md`, `TICKET-TRACKERS.md`).

## 6. Where the local copies differ from upstream

Local `~/.agents/skills/` copies (installed 2026-10-05) compared with upstream `4ae2317` (`diff -r`):

| Skill | Local copy lacks |
|---|---|
| `setup-matt-pocock-skills/SKILL.md` | legacy `CONTEXT.md` → `GLOSSARY.md` rename offer; connecting a git remote for GitHub/GitLab; creating missing labels |
| `…/issue-tracker-github.md` | `--json` read; "Make an issue a sub-issue of a parent"; Blocking and "Count open blockers" moved into Conventions with `gh --blocked-by` flags; comment-then-close (`close --comment` silently drops the comment on an already-closed issue); "file issues only into the user's own repo, never `mattpocock/skills`" |
| `…/issue-tracker-gitlab.md` | `-O json` instead of `-F json`; child linked with `--linked-issues <map> --link-type relates_to`; frontier lists children through the map's links |
| `to-tickets/SKILL.md` | sub-issue of the source issue; omit `## Blocked by` when edges are native; "native blocking / sub-issue relationship" narrowed to "native blocking relationship" |
| `wayfinder/SKILL.md` | `wayfinder:` labels only (no `ready-for-agent`); real ids in cross-references; research branches pushed with no PR; fresh-context subagents; resolve by the type its label names |
| `implement-spec/SKILL.md`, `research/SKILL.md` | "start every subagent with a fresh context window" |
| `implement/SKILL.md` | fetch the referenced ticket; explicit Skill-tool calls for `tdd` / `code-review` |
| `to-spec`, `triage` | no difference |

This repo's hand-written Gitea `docs/agents/issue-tracker.md` follows the **older** GitHub template's shape: Blocking sits under "Wayfinding operations", and there is no sub-issue operation (`/home/myockey/Work/symphony/docs/agents/issue-tracker.md`).
