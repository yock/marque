# Tracker snippet: Gitea

Gitea issues through the `tea` CLI. Tested by real runs. Paste the bullets that fill a gap into the project's Conventions; `<owner>/<repo>` and `<login>` are the project's.

The scripts address it as `--backend gitea --repo <owner>/<repo>` and read as `tea`'s default login. The commands below carry `--login <login>`, which picks the `tea` login they act as; Marque runs them as the doc writes them. Gitea shares one index sequence between issues and PRs, so `#42` names exactly one of them.

- **List by label**: `tea issues ls --login <login> -o json -L "<label>" --state open`.
- **Read an issue**: `tea issues <number> --login <login> --comments`; for raw markdown, `tea api --login <login> 'repos/<owner>/<repo>/issues/<number>'` and `.../issues/<number>/comments`.
- **Parent**: the body's top line `Part of #<parent>` (Gitea has no sub-issues).
- **Blocking**: Gitea's native issue dependencies: `tea api --login <login> -X POST 'repos/<owner>/<repo>/issues/<child>/dependencies' -F index=<blocker> -f owner=<owner> -f repo=<repo>` (the `#number`). An unblocked ticket has every blocker closed.
- **Count open blockers**: `tea api --login <login> 'repos/<owner>/<repo>/issues/<number>/dependencies' | jq '[.[] | select(.state == "open")] | length'` (the endpoint lists closed blockers too; 0 means startable).
- **Assign / unassign**: `tea issues edit --login <login> <number> --add-assignees <login>` / `--remove-assignees <login>`.
- **Comment**: `tea comments add --login <login> <number> --description "$(cat <path>)"`.
- **Apply / remove labels**: `tea issues edit --login <login> <number> --add-labels "<label>"` / `--remove-labels "<label>"`.
- **Close**: post the resolution with **Comment**, then `tea issues close --login <login> "$MARQUE_ISSUE"` (it takes no closing comment). The close probe: `tea api --login <login> repos/<owner>/<repo>/issues/$MARQUE_ISSUE | jq -e '.state == "closed"'`.
- **Open a PR**: `tea pulls create --login <login> --head marque-<number> --base <target> --title "<title>" --description "$(cat <path>)"`, the description carrying `Closes #<number>`.
- **Merge a PR**: `tea pulls merge --login <login> <number>` (add `--style squash` to match the project's merge style).
- **Read PR approval**: `tea api --login <login> 'repos/<owner>/<repo>/pulls/<number>/reviews' | jq '[.[] | select(.state == "APPROVED")] | length > 0'` — Gitea has no one-approval verdict, so count the approved reviews.
