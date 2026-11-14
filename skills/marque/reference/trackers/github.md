# Tracker snippet: GitHub

GitHub issues through the `gh` CLI. Best-effort until dogfooded. Paste the bullets that fill a gap into the project's Conventions; `<owner>/<repo>` and `<login>` are the project's.

The scripts address it as `--backend github --repo <owner>/<repo> --login <gh user>`. Marque runs each `gh` call as that user by fetching the token once — `GH_TOKEN=$(gh auth token --user <login>) gh …` — and never touches `gh auth switch`, so the developer's own `gh` session is left alone.

- **List by label**: `gh issue list --state open --label "<label>" --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name]}]'`.
- **Read an issue**: `gh issue view <number> --json number,title,body,labels,comments`; `gh api repos/<owner>/<repo>/issues/<number>` for the raw body markdown.
- **Parent**: `gh issue edit <parent> --add-sub-issue <child>` (`gh` 2.94+), else the body's top line `Part of #<parent>`.
- **Blocking**: GitHub's native issue dependencies: `gh issue edit <child> --add-blocked-by <blocker>` (`gh` 2.94+); older `gh`, `gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`. An unblocked ticket has every blocker closed.
- **Count open blockers**: `gh api repos/<owner>/<repo>/issues/<number> --jq .issue_dependencies_summary.blocked_by` (open blockers only; 0 means startable).
- **Assign / unassign**: `gh issue edit <number> --add-assignee <login>` / `--remove-assignee <login>`.
- **Comment**: `gh issue comment <number> --body-file <path>`.
- **Apply / remove labels**: `gh issue edit <number> --add-label "<label>"` / `--remove-label "<label>"`.
- **Close**: post the resolution with **Comment**, then `gh issue close "$MARQUE_ISSUE"`. The close probe: `gh issue view "$MARQUE_ISSUE" --json state -q '.state == "CLOSED"' | grep -qx true`.
- **Open a PR**: `gh pr create --head marque-<number> --base <target> --title "<title>" --body-file <path>`, the body carrying `Closes #<number>`.
- **Merge a PR**: `gh pr merge <number> --merge` (or `--squash`, matching the project's merge style).
- **Read PR approval**: `gh pr view <number> --json reviewDecision,reviews` — approved when `reviewDecision` is `APPROVED`.
- **Orchestrator identity**: a plain Conventions line `**Orchestrator identity**: GH_TOKEN=<bot token>`; Marque passes it per call as above, and the doc's other identity stays the planning one.
