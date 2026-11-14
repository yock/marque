# Tracker snippet: Local Markdown

Tickets as markdown files under `.scratch/<feature>/issues/`, no CLI. Best-effort until dogfooded. Paste the bullets that fill a gap into the project's Conventions; `<NN>-<slug>.md` is the ticket's file.

The scripts address it as `--backend local`. Each operation below is a file edit or a read.

- **List by label**: `grep -l '^Status: <label>' .scratch/<feature>/issues/*.md` (the `Status:` line carries the triage label).
- **Read an issue**: read `.scratch/<feature>/issues/<NN>-<slug>.md`.
- **Parent**: a `Part of <feature>/spec.md` line near the top of the ticket file; the spec is `.scratch/<feature>/spec.md`.
- **Blocking**: a `Blocked by: NN, NN` line near the top of the ticket file. An unblocked ticket has every named file reading `Status: resolved`.
- **Count open blockers**: `grep '^Blocked by:' <file>` then check each named file for `^Status: resolved`.
- **Assign / unassign**: set the file's `Status: claimed` (Marque's claim), or back to `Status: ready-for-agent` to unassign.
- **Comment**: append under the file's `## Comments` heading.
- **Apply / remove labels**: rewrite the `Status:` line.
- **Close**: post the resolution under `## Comments`, then set `Status: resolved`. The close probe: `grep -qx 'Status: resolved' <file>`.
- **Open a PR**: not available; local mode lands directly.
- **Merge a PR**: not available; local mode lands directly.
- **Read PR approval**: not available; local mode lands directly.
