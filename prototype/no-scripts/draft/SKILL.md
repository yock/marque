<!-- PROTOTYPE, throwaway: "symphony without scripts". Only the three operations under test
(pick, split a spec, assemble a brief) are written here, as prose in place of frontier.py,
split_spec.py and brief.py. The rest of the loop is unchanged from symphony's SKILL.md. -->

# Marque (prose draft): pick, split, brief

Tracker facts (CLI, login, repo, labels, how to ask the user) come from the target repo's
`docs/agents/issue-tracker.md` and `triage-labels.md`; project rules from its `AGENTS.md`.
Read issues through the tracker's **raw REST passthrough** (`tea api` / `gh api`), never a CLI's
reflowed view: bodies come back verbatim and comments unclipped.

**Keep issue bodies out of your context.** A queue's bodies run to hundreds of KB. Fetch them to
files under the state dir and extract with `jq`/`grep`; read only what the extraction leaves.

## Pick

The **queue** is every open issue carrying the ready label. For each queued ticket work out:

- **Blockers**, the union of:
  1. **native dependencies**: `repos/<repo>/issues/<n>/dependencies` (Gitea) or the blocked-by
     relationship (GitHub). Check them even when the tracker doc says the tracker has none.
  2. a `Blocked by:` line, and
  3. a `## Blocked by` section (to-tickets' form; `None` there means none).
  Count only references into this repo (`#n`, or a URL to this repo's issue n). A blocker is
  cleared only when that issue is **closed**; a reference you can't resolve is open.
- **Parent**: `Part of #n`, or a `## Parent` section.
- **Claimed**: has an assignee. **Waiting on the user**: carries the label the tracker doc uses
  for that (for example `blocking` or `needs-info`).

The **frontier** is the queued tickets that are unclaimed, not waiting on the user, and whose
every blocker is closed. Rank it by **fan-out**: how many queued tickets it unblocks,
transitively, through open blockers; then parent number, then issue number.

List, apart from the ranking, every ticket you **read by hand**: one whose blocker forms disagree,
whose parent is missing, or whose references you couldn't resolve. Decide those yourself and say
how.

Done when every queued ticket has been classified (frontier, blocked by which open issues,
claimed, waiting) and the frontier is ranked. Write it to `<state>/logs/frontier.md`: the ranked
frontier as `#n fan F parent #p title`, then the read-by-hand list, then the counts.

## Split a spec

A parent spec can be several hundred KB with many amending comments. Before exploring a ticket,
put its parent spec on disk in `<state>/specs/<n>/`:

- `body-NN-<slug>.md`: the body cut at every `##` and `###` heading, in order (`body-00` is
  whatever precedes the first heading);
- `cNN.md`: each comment, 1-based, in order. Comments amend the body; the latest word wins;
- `index.txt`: the spec's `#n title`, then one line per file: name, size in bytes, first
  heading or first non-blank line.

Paginate comments until a short page. Done when the files' bytes add up to the body plus every
comment, and `index.txt` lists every file.

## Assemble a brief

Write the ticket part of `<state>/briefs/<n>.md` in your own words (see the loop). Then append,
after a `---` line, the **brief tail**: `templates/brief.md` below its own `---`, with
these placeholders filled:

| placeholder | value |
|---|---|
| `{{ISSUE}}` | the ticket number |
| `{{WORKTREE}}` | `<repo root>/.claude/worktrees/orch-<n>` unless the project says otherwise |
| `{{BRANCH}}` | the ticket's branch |
| `{{MASTER}}` | the main checkout's root |
| `{{PROJECT}}` | the repo root's directory name |
| `{{PROJECT_RULES}}` | the project's build, test and repo rules for implementers, with the placeholders above filled inside them too |

Done when `grep -c '{{' <brief>` prints 0 and the tail appears exactly once.
