---
name: symphony
description: Orchestrate implementer agents through a wayfinder-format ticket queue — pick unblocked tickets, brief them with the design fixed, dispatch them in parallel worktrees, review, integrate, land and close them. Use when the user wants an agent to work down a ready-for-agent queue, run several implementers in parallel, act as orchestrator or dispatcher, or resume such a run after a context summary.
---

# Symphony: orchestrating a ticket queue

You are the **orchestrator**. Cheaper **implementer** agents each take one ticket in their own git worktree; you pick, brief, review, integrate, land and close. The tickets follow the wayfinder format (`Part of #<spec>`, `Blocked by:`, triage labels); the target repo's `docs/agents/issue-tracker.md` and `triage-labels.md` say how its tracker spells them.

Scripts are in this skill's `scripts/`, templates in `templates/`. All of them read the project's `docs/agents/symphony.toml` (see `config.example.toml`); run them from inside the target repo.

## Before the first ticket

1. **Config:** the target repo has `docs/agents/symphony.toml` (tracker, repo, login, labels, state dir, brief rules). If not, write it with the user from `config.example.toml`, and the project's brief rules file (build and test commands, repo rules the tests enforce).
2. **State dir** (`state.dir`, outside the repo): `plan.md` (this effort's decisions and the user's answers), `ledger.tsv`, `briefs/`, `specs/`, `logs/`. Create it; after any context summary, **re-read `plan.md` and the ledger first**. State lives there and on the tracker, never only in context.
3. **Agree with the user and write into `plan.md`:** the implementer model and variant; authority (land and close without asking?); fallback (may you implement yourself?); concurrency; any paid compute and its cap; pacing (battery). Learn the resolution-comment format from 3–4 recently closed tickets.
4. **Split the parent specs** the queue names: `scripts/split_spec.py <spec>...` (sections and comments as files; never read a large spec whole).
5. On laptops, start the battery watcher (see *Pacing*).

## The loop, per ticket

1. **Pick.** `scripts/frontier.py`: ready, unclaimed, not `blocking`, every blocker closed, ranked by how many queued tickets it unblocks. Act on its headers first:
   - `ANSWERED #n`: the user answered your questions; read the ticket's newest comments, they amend it.
   - `READ BY HAND #n`: the script couldn't parse the blockers or parent; read that ticket and decide yourself.
   - Skip tickets that collide with in-flight ones (same files, same spec part, tickets that name each other), and tickets needing a human or outward step (downloads, licences, accounts, review by eye): ask instead (*Asking the user*).
2. **Explore** (cheap, read-only): `scripts/brief.py explore <n> <spec> --in-flight "<in-flight tickets and their files>"`, then a read-only subagent on the implementer model, prompt "Read <file> and follow it exactly". It reports SPEC / BLOCKERS LANDED / CODE / TESTS / GAPS AND RISKS with file:line.
3. **Read** the ticket's *What to build* and criteria and the key spec lines yourself. Resolve each gap the explore found.
4. **Brief** `state.dir/briefs/<n>.md`, the ticket part, in your own words:
   - the ticket's text verbatim, the spec sources with later amendments already applied (the implementer gets the final wording);
   - what landed to build on (blockers' names in code, file:line);
   - **the design, fixed** wherever a seam is new or shared, or the explore found a gap: name the types, functions, enums, where state lives, what refuses what. Implementers build what is written; they invent badly at seams;
   - acceptance criteria, with any you add marked (added);
   - seams to test; the independent source of every expected value; collisions with in-flight tickets; slices in order.
   Then `scripts/brief.py brief <n> <branch>` appends the shared tail (worktree rules, project build and test rules, TDD workflow, test rules, self-check, report format).
5. **Claim and branch:** `git worktree add <worktree> -b <branch> <main>`; assign the ticket to the agents' user (the tracker docs give the command and login).
6. **Dispatch** a background subagent on the implementer model: "Implement ticket #n. Your brief is <path>: read it in full and follow it exactly. Work only in <worktree> (branch <branch>)." Ledger → `running` with the session ID.
7. **Review** the report: every criterion mapped to a test; expected values independent (no tautologies); questions it resolved itself. Read `git diff --stat`, then only the hunks that need judgement: changed tests outside the ticket's area, new seams, anything that reads ground truth it shouldn't, budgets. A failed review goes back to **the same session** with specific findings. See `reference/operations.md` for retries, stalls and fallback.
8. **Integrate:** fetch; merge the main branch into the ticket branch; resolve conflicts (mostly additive; when a hunk splits a function, the shared closing tail goes between the halves; watch for changed signatures that merge cleanly but don't compile); build; **only after a successful build** run the quick filtered tests; then the clean build and full suite in the background.
9. **Land** when green: main == origin, the branch contains main, the tree is clean → `git merge --no-ff` "Merge #n: <gist>"; push. Domain docs written while resolving go in as their own commit with the issue number. Post the resolution comment (the learned format; name follow-ups), close, remove the worktree and branch, ledger → `landed` with the hash. File follow-ups found in review as `needs-triage` with `Part of #<spec>`.
10. **Recompute the frontier** and fill the free slot.

Run up to the agreed number of implementers in parallel; prepare the next brief while they work.

## Asking the user

**Never ask a ticket's question only in chat** — it is lost at the next summary. **Every question posted for the user on a ticket gets the labels, however small** (a yes/no on a name included) and even when the ticket is blocked anyway: the labels are the user's work queue, and their removal is the user's signal that the answer is ready. `blocking` marks urgency: a question about work already underway (a started ticket, a landed ticket's follow-up, a parent spec that can't complete without it), as distinct from `ready-for-human` work still being planned. When saying what a question blocks, check the parent spec as well as the queue. Comment the questions on the ticket, numbered, each with a recommended answer, ending "reply 'all as recommended' or answer by number"; say what waits on it. Relabel ready → `ready-for-human` + `blocking`; unassign. In chat, name the ticket only. The user answers on the ticket and relabels it ready; `frontier.py` flags it `ANSWERED` (mark the ledger row with the configured `asked_marker`). The target repo's `docs/agents/issue-tracker.md` has the commands.

## Pacing

On a laptop the full suites drain the battery even on mains; a shutdown mid-run breaks worktrees. `scripts/battery.sh now` before each dispatch; `scripts/battery.sh watch run <state>/battery.log` in the background — its exit wakes you. Default policy: ≥ 60 % or charging, full concurrency; 40–60 % and falling, one fewer; < 40 %, dispatch nothing new (running agents finish and land); < 20 %, pause local builds and notify. Lower test parallelism with concurrency.

## Rules that held

- Implementers never touch the main checkout, push, merge, write to the tracker or edit domain docs; only you do.
- Every ticket is integration-tested on current main before it lands, even when a review passed.
- Facts on disk, not in context: long output to `logs/`, read only failures and the hunks that need judgement.
- A spec gap with no default: question on the ticket (*Asking the user*), not an invented behaviour.
- Main red after a landing: stop dispatching and fix main first. Three failures in a row across tickets: suspect the brief template, not the tickets.

See `reference/operations.md` for the ledger format, retries, stalls, crash recovery and notifications.
