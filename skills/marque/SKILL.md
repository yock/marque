---
name: marque
description: Orchestrate implementer agents through a ticket queue — pick unblocked tickets, brief them with the design fixed, dispatch them in parallel worktrees, review, integrate, land and close each one. Use when the developer wants an agent to work down a ready-for-agent queue, run several implementers in parallel, act as orchestrator, or resume a run after a context summary.
disable-model-invocation: true
---

# Marque: orchestrating a ticket queue

You are the **orchestrator**. Cheaper **implementer** agents each take one ticket in their own worktree; you pick, brief, dispatch, review, integrate, land and close. The developer holds your session and can steer, stop or redirect you at any time. The tickets follow the wayfinder format — `Part of #<spec>`, declared blockers, triage labels — and the target repo's `docs/agents/issue-tracker.md` and `triage-labels.md` say how its tracker spells them.

Scripts are in this skill's `scripts/`, templates in `assets/`, references in `reference/`. Tracker facts — backend, repo, orchestrator identity, comment/close/assign/relabel commands — live only in `issue-tracker.md`, reach the scripts as `--backend`, `--repo` and `--login`, and run as the orchestrator identity. Project rules come from the repo's `AGENTS.md` (or `CLAUDE.md`).

## Core

Extensions may add to or tighten these; none may loosen them.

- **a.** The developer holds the session and can steer, stop or redirect it.
- **b.** Work comes from a tracker queue. The frontier is computed from declared blocking: native dependencies first, then description header lines. Inference from the ticket text applies only to tickets that declare nothing; you report each edge you infer, and inference never overrides a declared edge.
- **c.** A per-ticket brief, built from the ticket and its relevant sources, with the design fixed at its seams.
- **d.** The orchestrator reviews every ticket, and the review gates landing.
- **e.** Each ticket is integrated on the current target branch and landed one at a time.
- **f.** Questions go on the ticket and are labelled, never only in chat. `ready-for-agent` is someone's claim of readiness, not a verdict: do your own analysis and refer a ticket back, naming what you believe is missing. Never invent a missing behaviour.
- **g.** State lives on disk and survives context summaries.
- **h.** Implementers never touch the tracker, the target branch or the domain docs.

## Before the first ticket

- **State dir:** `~/.local/share/marque/<repo-name>`, overridable in `docs/agents/marque.md`. It holds `plan.md`, `ledger.tsv`, `briefs/`, `specs/`, `logs/` and `landing/`. Create it. After any context summary, read `plan.md`, then run `ledger.py --state-dir <dir> recover`.
- **Commission:** agree it with the developer and record it in `plan.md` — authority, landing mode, concurrency, implementer model and variant, fallback, paid compute and its cap. Then apply the **commission** extensions. → `reference/commission.md`
- **Specs:** split the parent specs the queue names with `split_spec.py --backend B --repo O/N [--login L] --state-dir <dir> SPEC...`; read only the sections a ticket names.

## The loop, per ticket

1. **Pick.** Run `frontier.py --backend B --repo O/N [--login L]`: it prints `WAITING` and `READ BY HAND` lines, then the ranked frontier. Read a `READ BY HAND` ticket and decide it yourself. Skip tickets that collide with in-flight ones (same files, same spec part, tickets that name each other). A ticket back in the queue whose ledger row is `needs-info` has been answered: read its newest comments, which amend it. When your analysis finds a `ready-for-agent` ticket missing something, ask (`reference/asking.md`).
2. **Explore.** Fill `assets/explore.md` and **dispatch a background subagent** with it — read-only, on the implementer model. Ledger `exploring`.
3. **Brief.** Write `briefs/<n>.md`: the ticket verbatim; its sources with later amendments already applied; what landed to build on, by name and file:line; **the design, fixed** at every new or shared seam (types, functions, where state lives, what refuses what); the criteria, added ones marked; the seams to test and the independent source of each expected value; collisions with in-flight tickets; the slices in order. Fill `assets/brief-tail.md` and append it, with the **brief** extensions. Ledger `briefed`.
4. **Claim.** `git worktree add <repo>/.marque/worktrees/marque-<n> -b marque-<n> <target>`; assign the ticket to the orchestrator identity.
5. **Dispatch.** Apply the **dispatch** extensions, then **dispatch a background subagent**: "Implement ticket #n. Your brief is <path>: read it in full and follow it exactly. Work only in <worktree> (branch <branch>)." Ledger `running` with the session.
6. **Review.** The review gates landing. Check the report — every criterion mapped to a test, expected values independent, questions it resolved itself — then `git diff --stat` and the hunks needing judgement (changed tests outside the ticket's area, new seams, anything reading ground truth it shouldn't). A failed review goes back: **resume the same session** with the file, the criterion and what to change. Ledger `retry`. Retries, stalls and fallback → `reference/operations.md`.
7. **Integrate.** Fetch, merge the current target branch into the ticket branch, resolve conflicts, build, run the touched tests, then the full suite as a **background command that wakes you**, its log in `logs/`. Conflict details → `reference/operations.md`.
8. **Land** from a green full suite: write the resolution comment to a file, then `land.py direct …` or pr mode's `check` … `finish`. The calls, the target branch and the safeguards → `reference/landing.md`. File follow-ups found in review as `needs-triage` with `Part of #<spec>`.
9. **Recompute** the frontier and fill the free slot. Run up to the commission's concurrency; prepare the next brief while implementers work.

## Asking

A question goes on the ticket, never only in chat: numbered, each with a recommended answer, and the ticket relabelled `needs-info`. The developer's relabel back to `ready-for-agent` is the answer. → `reference/asking.md`

## Notify

On the core events — target branch red, three failures in a row, a paid-compute cap refusing, a ticket going `needs-info` or `ready-for-human`, the frontier down to externally blocked tickets — **push a notification**. Send a short summary every ten landings. Apply the **notify** extensions. → `reference/operations.md`

## Rules that held

- Implementers never touch the main checkout, push, merge, write to the tracker or edit domain docs; only you do.
- Every ticket is integration-tested on the current target branch before it lands, even when a review passed.
- Facts on disk, not in context: long output to `logs/`, read only failures and the hunks that need judgement.
- A spec gap with no default: question on the ticket (`reference/asking.md`), not an invented behaviour.
- The target branch red after a landing: stop dispatching and fix it first. Three failures in a row across tickets: suspect the brief template, not the tickets.

## Reference

- `reference/commission.md` — agreeing the commission: setup check, tracker gap-check, identity, landing mode, extension approval.
- `reference/extensions.md` — the five extension points: commission, dispatch, brief, review, notify.
- `reference/harnesses.md` — the verbs (dispatch a background subagent, resume the same session, push a notification, run a background command that wakes you) per harness.
- `reference/operations.md` — retries, stalls, integration details, crash recovery, notifications, context management.
- `reference/landing.md` — the guarded landing, direct and pr modes.
- `reference/asking.md` — questions on the ticket and the answer signal.
