# Tracker snippet: GitLab

GitLab issues through the `glab` CLI. Best-effort until dogfooded. Paste the bullets that fill a gap into the project's Conventions; `<group>/<project>` and `<login>` are the project's. GitLab calls comments "notes" and pull requests "merge requests".

The scripts address it as `--backend gitlab --repo <group>/<project> [--host <host>]`; `--host` is for self-managed GitLab. Every `glab` call runs as `glab`'s signed-in account: choosing that account is the developer's business, and Marque never switches it.

- **List by label**: `glab issue list --opened --label "<label>" -F json`.
- **Read an issue**: `glab issue view <number> --comments`; `glab api projects/:id/issues/<number>` for the raw description markdown.
- **Parent**: the body's top line `Part of #<parent>`, linked with `glab issue create --linked-issues <parent> --link-type relates_to`.
- **Blocking**: GitLab's native blocking link, posted as a note: `glab issue note <child> --message "/blocked_by #<blocker>"` (Premium/Ultimate), else the body's top line `Blocked by: #<blocker>, #<blocker>`. An unblocked ticket has every blocker closed.
- **Count open blockers**: `glab api projects/:id/issues/<number>/links | jq '[.[] | select(.link_type == "is_blocked_by" and .state == "opened")] | length'` (0 means startable).
- **Assign / unassign**: `glab issue update <number> --assignee <login>` / `--unassignee <login>`.
- **Comment**: `glab issue note <number> --message "$(cat <path>)"`.
- **Apply / remove labels**: `glab issue update <number> --label "<label>"` / `--unlabel "<label>"`.
- **Close**: post the resolution with **Comment**, then `glab issue close "$MARQUE_ISSUE"`. The close probe: `glab issue view "$MARQUE_ISSUE" -F json | jq -e '.state == "closed"'`.
- **Open a PR**: `glab mr create --source-branch marque-<number> --target-branch <target> --title "<title>" --description "$(cat <path>)"`, the description carrying `Closes #<number>`.
- **Merge a PR**: `glab mr merge <number> --yes` (or `--squash`, matching the project's merge style).
- **Read PR approval**: `glab api projects/:id/merge_requests/<number>/approvals | jq -e '.approved'` (approvals are a Premium feature).
