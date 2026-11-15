# Landing

Landing merges an integrated, green ticket branch onto the target branch — directly, or through the ticket's pull request — then makes sure its ticket is closed. A ticket whose pull request is still open is not landed.

## Target branch and merge style

The target branch is a term of the commission: the repo's default branch unless the developer names another, and `docs/agents/marque.md` may override it. Merge style is `--no-ff`, unless the project's `AGENTS.md` states another convention; pass `--merge-style no-ff` or `--merge-style squash`. The merge message is `Merge #n: <gist>`.

## The guarded landing

Land through `land.py`, as one guarded unit. A hand-chained landing (`checks && merge …; comment; remove`) runs the steps after `;` even when a precondition fails, and so comments and closes a ticket whose merge never happened.

`land.py` enforces the seven safeguards, core in both modes:

1. **Preconditions:** the target branch equals origin, the branch contains the target, the tree is clean, and a passing suite record for the branch's tree: an integration record under the state dir's `logs/`, whose `verdict` is `pass` and whose `tree` is `<branch>^{tree}`.
2. **One guarded unit:** a failed precondition exits 3 with nothing changed.
3. **Resolution comment first:** write it to a file before the guarded part runs.
4. **Ledger `landing`** for the whole run.
5. **No force-push.**
6. **Worktree and branch removed only after the merge is confirmed on origin.**
7. **The landed tree is the tested tree:** after the merge and before the push, the target's tree must equal the record's tree. A mismatch stops the landing (exit 1) before anything is pushed, and a resume checks it again.

## Direct mode

From the main checkout, with the target branch checked out:

```sh
scripts/land.py direct --issue N --branch marque-N \
  --worktree <repo>/.marque/worktrees/marque-N --target <target> \
  --gist "<the gist>" --state-dir <dir> \
  --suite-record <dir>/logs/full-suite-N.record --resolution <dir>/landing/N.md \
  --comment-cmd '<issue-tracker.md’s Comment on an issue: $MARQUE_ISSUE is the number, "$MARQUE_RESOLUTION" the body file>' \
  --close-cmd '<issue-tracker.md’s Close: $MARQUE_ISSUE is the number>'
```

The two commands come from the tracker doc and run as written. Exit 0 means landed. Exit 3 is a failed precondition: fix it and re-run, nothing has changed. Exit 1 is a failed step mid-landing: fix the cause and re-run the same command, which resumes.

The resolution comment goes on the ticket, in the format learned from recent tickets, and names any follow-ups. After the merge, confirm the tracker closed the ticket; close it yourself if it didn't.

## pr mode

One pull request per ticket, never stacked, and a waiting PR is never rebased.

1. `land.py check` runs the preconditions and pushes the branch. Its flags: `land.py check --help`.
2. Open the PR with the tracker doc's command. Its body summarizes the ticket, links it and says `Closes #n`.
3. The orchestrator merges once the checks pass. Under the opt-in "the developer approves", it runs step 1 as `land.py check --await-approval` instead, which sets the ledger to `awaiting-approval`, and checks open approvals first on every pass; approvals land before new dispatches. A cap on waiting PRs (default: the concurrency) holds dispatch and fires a notify event, and dependents stay blocked until the PR lands. Reading approval state may need a convention gap-filled at commission.
4. `land.py finish --suite-record <dir>/logs/full-suite-N.record` confirms the merge on origin, verifies the tree that landed, confirms the close, comments, cleans up and updates the ledger — clearing `awaiting-approval` to `landing`, then `landed`. Its flags: `land.py finish --help`.

**The tree that landed.** The forge does the merge, so `land.py` can't check the tree before the push. Instead, `finish` compares the tree of the merge commit on origin with the suite record's tree. On a mismatch (the forge merged onto a target that had moved), the landing still completes, and `finish` names both trees and exits **4**. A landing can't be undone, but it can be verified at once. On exit 4, the orchestrator runs the full suite on the target through `scripts/suite.py run --record <dir>/logs/target-N.record`, as a background command that wakes you, and handles the result under the target-red rule: if the suite is red, stop dispatching and fix the target first.

## After a crash

`ledger.py recover` lists the `landing` rows. Re-run the same `land.py` command: it resumes from the step it reached.
