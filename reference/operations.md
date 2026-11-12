# Operations

## The ledger

`state.dir/ledger.tsv`, one row per ticket, tab-separated:

```
issue  state  branch  worktree  session  attempts  brief  verdict  landed  note
```

States: `queued` `exploring` `briefed` `running` `review` `retry` `landing` `landed` `opus` (the orchestrator implements) `needs-info` `blocked` `ready-for-human` `abandoned`. Put the user-question marker (`state.asked_marker`, default `QUESTIONS ON TICKET`) in a row's note when you post questions on its ticket, so `frontier.py` flags it `ANSWERED` when it comes back.

Update rows with a small script (read, split on tabs, set fields, write back); never hand-edit while an agent might.

## Retries and fallback

- A failed review goes back to the **same session** with specific findings: the file, the criterion, what to change. About half of tickets need one round.
- Agreed default: two rounds at the normal variant, one at the strongest, then the orchestrator implements (ledger → `opus`).
- **Stalls:** a session silent for over an hour, with no new commits and nothing running in its worktree, has stalled. Resume it with explicit finish steps, or take over integration yourself.
- An implementer that ends its turn while its suite runs in the background leaves work uncommitted: resume the same session.

## Integration details

- Merge conflicts are mostly additive (enum entries, records, struct fields, test registrations). Take both, in a stable order.
- A clean textual merge can still fail to compile when one side changed a signature the other side calls. The clean build catches it; never run filtered tests after a failed build — they run the previous binary and pass falsely.
- **Positional initializers** (C row tables built by macros, tuples, positional constructor calls) are the same hazard: two branches each append a field to the struct, the textual merge is clean or trivially additive, and one side's positional values now land in the other's fields. Check that each row macro lists values in the merged struct's field order; build with warnings visible (`excess elements in scalar initializer`, `braces around scalar initializer` are the tell).
- When both sides only **appended** to a long file (tests, registries) and git interleaves the two blocks into several hunks, check whether one side only appended to the merge base; if so, the clean result is the other side's file plus that side's appended tail.
- After merging main, run the tests of the areas the merge touched before the full suite: they fail fastest.
- A test from a ticket that landed after this branch forked can break on this branch's new default behaviour: fix it on the branch, as the branch's own sweep did for older tests.
- The user may land on main too. Always fetch and re-check that the branch contains main right before merging. If main moved past the branch only in docs (no code, build files or tests), merging the branch straight onto main needs no new test run; check that with `git diff --name-only`.

## Shared machine

Implementers and the orchestrator's integration runs share one machine. An implementer that kills test processes by name (`pkill ping_tests`) kills the orchestrator's integration shards too: they all end at the same second with "Subprocess terminated", no failure line and no OOM in the kernel log. The brief template forbids killing by name. When it happens anyway, rerun the integration; it isn't the branch's failure.

## Landing as one guarded script

Run a landing (preconditions, merge, push, comment, close, worktree and branch removal, ledger) as **one script under `set -e`**, or with every step inside one `if`. Never `checks && merge && … ; tea comments …; git worktree remove …`: when a precondition fails, the steps after the `;` still run. That once force-removed a worktree and marked a ticket landed while nothing had merged (the branch survived only because `git branch -d` refused an unmerged branch). Write the resolution comment to a file **before** the guarded part, so a failure can't leave it unwritten.

## Crash recovery

On restart, before anything else, for every ledger row in `running`, `review`, `retry` or `landing`:

1. `git -C <worktree> status` and `git log <main>..HEAD`.
2. Stash uncommitted changes (`orch-<n>-recovery`), rebuild, run the suite.
3. Green → resume at review. Red or unclear → reset to the last green commit, or remove the worktree, unassign, ledger → `queued`.
4. A `landing` row: check whether the merge reached main and origin, and whether the comment and close happened; finish what didn't.

## Notifications

Notify the user's phone (if available) when: the battery hits emergency; main is red; three failures in a row; a paid-compute cap refuses; a ticket goes `needs-info` or `ready-for-human`; the frontier is down to externally blocked tickets. A short summary every ten landings.

## Context management

- After a summary: `plan.md`, then the ledger, then the battery log's tail.
- Specs are split by `split_spec.py`; read only the named sections.
- Implementers get a short prompt pointing at the brief file; their report is short.
- A landed ticket is finished: its ledger row and resolution comment hold all that matters.
