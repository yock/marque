# Operations

## The ledger

The ledger is `ledger.tsv` in the state dir, one row per ticket, kept by `scripts/ledger.py --state-dir <dir>` — `get`, `set`, `list` and `recover`. The states and what each one means are in `ledger.py --help`: read them there, keep no second copy. Rows change through the script, never by hand while an agent may hold the file. A ticket waiting on the developer is `needs-info` (→ `reference/asking.md`).

## Retries and fallback

- A failed review goes back to the **same session** with specific findings: the file, the criterion, what to change. A round of findings is normal.
- The default ladder is two rounds at the normal variant, one at the strongest, then the orchestrator implements the ticket itself (ledger `orchestrator`), if the commission's fallback term allows; otherwise ask on the ticket.

## Stalls

A session silent for over **the stall hour** (default 1 hour, overridable only in `docs/agents/marque.md`), with no new commits and nothing running in its worktree, has stalled. Resume it with explicit finish steps, or take over integration. An implementer that ends its turn while its suite runs leaves work uncommitted: resume the same session.

## Integration details

- Merge conflicts are mostly additive (list entries, record fields, registrations). Take both, in a stable order.
- When a hunk splits a function, the shared closing tail goes between the halves.
- Where the project has a build step, a clean textual merge can still fail to build when one side changed a signature the other calls. Never run filtered tests after a failed build: stale output passes falsely.
- Positional constructs (row tables, tuples, positional constructor calls) can merge cleanly and still be wrong. Two branches each add a field, and one side's values land in the other side's fields. Check the merged order.
- When both sides only **appended** to a long file (tests, registries) and git interleaves the two blocks into several hunks, check whether one side only appended to the merge base; if so, the clean result is the other side's file plus that side's appended tail.
- After merging the target branch, run the tests of the areas the merge touched before the full suite: they fail fastest.
- A test from a ticket that landed after this branch forked can break on the branch's new default behaviour: fix it on the branch, as the branch's own sweep did for older tests.
- The developer lands on the target branch too. Right before landing, re-check that the branch contains the target. If the target has moved, merge it again and rerun the full suite: the record must name the tree that lands, whatever the change touched.

## Shared machine

Implementers and integration runs share one machine. If a project's full suite is heavy, suites take turns. The project's `AGENTS.md` says how, and the orchestrator's integration runs follow the same rule. The commission asks about it (→ `reference/commission.md` step 7). A paid run that the cap refuses falls back to the local runner under the same turn-taking rule.

## Runners and paid compute

Every paid run — an implementer's run, an integration run, an image build — reserves its worst case in `<state dir>/spend.tsv` before it starts. The run is refused when the spend so far plus that reservation would pass the commission's cap. A refused run falls back to the local runner, or exits 3 when the project's `## Runner` block says `local fallback: no`: there is nowhere else to run it.

At teardown the reservation is settled from the box's `started_at` and the confirmed stop, and a build from the wall time it took. A reservation nobody settled — a crashed run's — counts at its worst case until the sweep settles it. The ledger is append-only under a file lock, one row per reservation and settlement. Details → `reference/runners.md`.

## Never kill by name

Implementers and the orchestrator never kill processes by name or pattern: a name matches other agents' runs too. The brief tail says so to implementers.

## Landing

The guarded-landing rule and its reason are in `reference/landing.md`, enforced by `land.py`.

## Crash recovery

On restart, before anything else, run `ledger.py recover`. For each row it lists:

1. `git -C <worktree> status` and `git log <target>..HEAD`.
2. Stash uncommitted changes as `marque-<n>-recovery`; rebuild and run the suite.
3. Green → resume at review. Red or unclear → reset to the last green commit, or remove the worktree, unassign, and set the ledger to `queued`.
4. A `landing` row: re-run the same `land.py` command, which resumes from its journal.

## Notifications

The core events and the default channel are in `reference/extensions.md` (notify). Push a notification on each core event; a notify extension may add events and add or replace the channel, never drop a core one.

## Context management

- After a summary, read `plan.md`, then run `ledger.py recover`.
- Specs are split by `split_spec.py`; read only the named sections.
- Implementers get a short prompt pointing at the brief file, and their report is short.
- A landed ticket is finished: its ledger row and resolution comment hold all that matters.
