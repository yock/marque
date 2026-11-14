# Landing

Landing merges an integrated, green ticket branch onto the target branch — directly, or through the ticket's pull request — then makes sure its ticket is closed. A ticket whose pull request is still open is not landed.

## Target branch and merge style

The target branch is a term of the commission: the repo's default branch unless the developer names another, and `docs/agents/marque.md` may override it. Merge style is `--no-ff`, unless the project's `AGENTS.md` states another convention; pass `--merge-style no-ff` or `--merge-style squash`. The merge message is `Merge #n: <gist>`.

## The guarded landing

Land through `land.py`, as one guarded unit. A hand-chained landing (`checks && merge …; comment; remove`) runs the steps after `;` even when a precondition fails, and so comments and closes a ticket whose merge never happened.

`land.py` enforces the six safeguards, core in both modes:

1. **Preconditions:** the target branch equals origin, the branch contains the target, the tree is clean, and the integration run's full suite is green.
2. **One guarded unit:** a failed precondition exits 3 with nothing changed.
3. **Resolution comment first:** write it to a file before the guarded part runs.
4. **Ledger `landing`** for the whole run.
5. **No force-push.**
6. **Worktree and branch removed only after the merge is confirmed on origin.**

## Direct mode

From the main checkout, with the target branch checked out:

```sh
scripts/land.py direct --issue N --branch marque-N \
  --worktree <repo>/.marque/worktrees/marque-N --target <target> \
  --gist "<the gist>" --state-dir <dir> \
  --suite-green <dir>/logs/full-suite-N.log --resolution <dir>/landing/N.md \
  --comment-cmd '<issue-tracker.md’s Comment on an issue: $MARQUE_ISSUE is the number, "$MARQUE_RESOLUTION" the body file>' \
  --close-cmd '<issue-tracker.md’s Close: $MARQUE_ISSUE is the number>'
```

The two commands come from the tracker doc and run as the orchestrator identity. Exit 0 means landed. Exit 3 is a failed precondition: fix it and re-run, nothing has changed. Exit 1 is a failed step mid-landing: fix the cause and re-run the same command, which resumes.

The resolution comment goes on the ticket, in the format learned from recent tickets, and names any follow-ups. After the merge, confirm the tracker closed the ticket; close it yourself if it didn't.

## pr mode

One pull request per ticket, never stacked, and a waiting PR is never rebased.

1. `land.py check` runs the preconditions and pushes the branch. Its flags: `land.py check --help`.
2. Open the PR with the tracker doc's command. Its body summarizes the ticket, links it and says `Closes #n`.
3. The orchestrator merges once the checks pass. Under the opt-in "the developer approves", it runs step 1 as `land.py check --await-approval` instead, which sets the ledger to `awaiting-approval`, and checks open approvals first on every pass; approvals land before new dispatches. A cap on waiting PRs (default: the concurrency) holds dispatch and fires a notify event, and dependents stay blocked until the PR lands. Reading approval state may need a convention gap-filled at commission.
4. `land.py finish` confirms the merge on origin, confirms the close, comments, cleans up and updates the ledger — clearing `awaiting-approval` to `landing`, then `landed`. Its flags: `land.py finish --help`.

## After a crash

`ledger.py recover` lists the `landing` rows. Re-run the same `land.py` command: it resumes from the step it reached.
