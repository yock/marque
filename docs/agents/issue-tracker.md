# Issue tracker: Gitea

Issues and specs for this repo live as Gitea issues on `gitea.yock.dev`, repo `yock/symphony`. Use the [`tea`](https://gitea.com/gitea/tea) CLI for all operations.

**Always pass `--login yockbot`** (the account agents act as). `tea` infers the repo from the `origin` remote when run inside a clone; pass `-r yock/symphony` when running elsewhere.

## Conventions

- **Create an issue**: `tea issues create --login yockbot -t "..." --description-file - <<'EOF' ... EOF`. Add `-L label1,label2` to label at creation.
- **Read an issue**: `tea issues <number> --login yockbot --comments`. For machine-readable output use the API: `tea api --login yockbot 'repos/{owner}/{repo}/issues/<number>'` and `.../issues/<number>/comments`.
- **List issues**: `tea issues ls --login yockbot -o json -L <label> --state open` (`--limit`/`--page` to paginate; default limit is 30).
- **Comment on an issue**: `tea comments add --login yockbot <number> --description "..."`. For multi-line bodies, write the body to a file first and pass `--description "$(cat file)"`.
- **Apply / remove labels**: `tea issues edit --login yockbot <number> --add-labels "..."` / `--remove-labels "..."` (comma-separated). A label must exist on the repo first: `tea labels create --login yockbot --name <label> --color <hex>`.
- **Close**: `tea issues close --login yockbot <number>`. It takes no closing comment, so post the explanation first with `tea comments add`, then close.
- **Pull requests**: `tea pulls create`, `tea pulls <number>`, `tea pulls merge`, etc. Gitea shares one index sequence between issues and PRs (like GitHub), so `#42` refers to exactly one of them.

## Pull requests as a triage surface

**PRs as a request surface: no.** _(Set to `yes` if this repo treats external pull requests as feature requests; `/triage` reads this flag.)_

When set to `yes`, PRs run through the same labels and states as issues:

- **Read a PR**: `tea pulls <number> --login yockbot` and `tea api --login yockbot 'repos/{owner}/{repo}/pulls/<number>.diff'` for the diff.
- **List external PRs for triage**: `tea pulls ls --login yockbot -o json`, then keep only PRs whose author is not a repo collaborator/owner.
- **Comment / label / close**: `tea comments add`, `tea pulls edit --add-labels`/`--remove-labels`, `tea pulls close`.

## When a skill says "publish to the issue tracker"

Create a Gitea issue.

## When a skill says "fetch the relevant ticket"

Run `tea issues <number> --login yockbot --comments`.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a single issue with **child** issues as tickets.

- **Map**: a single issue labelled `wayfinder:map`, holding the Notes / Decisions-so-far / Fog body. `tea issues create --login yockbot -L wayfinder:map ...`.
- **Child ticket**: an issue carrying `Part of #<map>` at the top of its description and labels `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`). Once claimed, the ticket is assigned to the driving dev.
- **Blocking**: Gitea's **native issue dependencies**, the canonical, UI-visible representation. Add one with `tea api --login yockbot -X POST 'repos/{owner}/{repo}/issues/<child>/dependencies' -F index=<blocker> -f owner=yock -f repo=symphony`. List a ticket's blockers with `tea api --login yockbot 'repos/{owner}/{repo}/issues/<child>/dependencies'`. A ticket is unblocked when every blocker is closed.
- **Frontier query**: `tea issues ls --login yockbot -o json --state open` scoped to the map's children; drop any with an open dependency (per the dependencies endpoint) or an assignee; first in map order wins.
- **Claim**: `tea issues edit --login yockbot <n> --add-assignees yockbot`, the session's first write.
- **Resolve**: `tea comments add --login yockbot <n> --description "<answer>"`, then `tea issues close --login yockbot <n>`, then append a context pointer (gist + link) to the map's Decisions-so-far.
