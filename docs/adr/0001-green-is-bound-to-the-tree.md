# Green is bound to the tree it tested

`land.py` used to accept a suite log whose mtime was later than the branch tip's commit time. That presumes the log is for the tip, and the presumption fails when a commit lands while the suite runs or when a remote runner's log arrives late. A branch is now green only when a passing **suite record** names the tree being landed (`<branch>^{tree}`). The record is written by Marque's suite wrapper, which notes the tree before the suite starts and refuses a dirty worktree. Only records from the orchestrator's integration step count, never an implementer's. The mtime check is removed, not kept as a fallback, because two definitions of green would be a loosening of the core.

## Consequences

- Every integration run goes through the wrapper.
- The docs-only exception in operations (land without a rerun when the target moved only in docs) cannot be expressed as a tree match, so it is reconsidered with this change.
- Speculative integration (testing B on `target + A` before A lands) becomes expressible: the record stays valid when A lands, as long as the tree that lands equals the tree that was tested. Adopting it would still change core rule e ("integrated on the current target branch"), so it is deferred, not decided.
