# Issue tracker: Gitea

Issues and specs for this repo live as Gitea issues on `gitea.yock.dev`, repo `yock/marque`. Use the [`tea`](https://gitea.com/gitea/tea) CLI for all operations.

**Always pass `--login gitea.yock.dev`** (the developer's account, user `yock`; the orchestrator's is under Conventions). `tea` infers the repo from the `origin` remote when run inside a clone; pass `-r yock/marque` when running elsewhere.

## Conventions

- **Orchestrator identity**: --login yockbot
- **Create an issue**: `tea issues create --login gitea.yock.dev -t "..." --description "$(cat body.md)"`. Write multi-line bodies to a file first. Add `-L label1,label2` to label at creation.
- **Read an issue**: `tea issues <number> --login gitea.yock.dev --comments`. For machine-readable, raw-markdown output use the API: `tea api --login gitea.yock.dev 'repos/{owner}/{repo}/issues/<number>'` and `.../issues/<number>/comments`.
- **List issues**: `tea issues ls --login gitea.yock.dev -o json -L <label> --state open` (`--limit`/`--page` to paginate; default limit is 30).
- **Make an issue a sub-issue of a parent**: Gitea has no sub-issues. Put `Part of #<parent>` at the top of the child body.
- **Blocking**: Gitea's **native issue dependencies**, the canonical, UI-visible representation. Add an edge with `tea api --login gitea.yock.dev -X POST 'repos/{owner}/{repo}/issues/<child>/dependencies' -F index=<blocker> -f owner=yock -f repo=marque` (the `#number`, not a database id). Don't also write a `Blocked by` line in the body. A ticket is unblocked when every blocker is closed.
- **Count open blockers**: `tea api --login gitea.yock.dev 'repos/{owner}/{repo}/issues/<n>/dependencies' | jq '[.[] | select(.state == "open")] | length'` (0 means startable). The endpoint lists closed blockers too, so always filter on `state`.
- **Comment on an issue**: `tea comments add --login gitea.yock.dev <number> --description "$(cat body.md)"`. Write multi-line bodies to a file first.
- **Apply / remove labels**: `tea issues edit --login gitea.yock.dev <number> --add-labels "..."` / `--remove-labels "..."` (comma-separated). A label must exist on the repo first: `tea labels create --login gitea.yock.dev --name <label> --color <hex>`.
- **Close**: `tea issues close --login gitea.yock.dev <number>`. It takes no closing comment, so post the explanation first with `tea comments add`, then close.
- **Pull requests**: `tea pulls create`, `tea pulls <number>`, `tea pulls merge`, etc. Gitea shares one index sequence between issues and PRs (like GitHub), so `#42` refers to exactly one of them.

File issues only into `yock/marque`. Never file into `mattpocock/skills` (the repo these skills come from).

## Pull requests as a triage surface

**PRs as a request surface: no.** _(Set to `yes` if this repo treats external pull requests as feature requests; `/triage` reads this flag.)_

When set to `yes`, PRs run through the same labels and states as issues:

- **Read a PR**: `tea pulls <number> --login gitea.yock.dev` and `tea api --login gitea.yock.dev 'repos/{owner}/{repo}/pulls/<number>.diff'` for the diff.
- **List external PRs for triage**: `tea pulls ls --login gitea.yock.dev -o json`, then keep only PRs whose author is not a repo collaborator/owner.
- **Comment / label / close**: `tea comments add`, `tea pulls edit --add-labels`/`--remove-labels`, `tea pulls close`.

## When a skill says "publish to the issue tracker"

Create a Gitea issue.

## When a skill says "fetch the relevant ticket"

Read it as in **Read an issue** above.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a single issue with **child** issues as tickets.

- **Map**: a single issue labelled `wayfinder:map`, holding the Notes / Decisions-so-far / Fog body. `tea issues create --login gitea.yock.dev -L wayfinder:map ...`.
- **Child ticket**: an issue with `Part of #<map>` at the top of its body (see **Make an issue a sub-issue of a parent**). Labels: `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`). Once claimed, the ticket is assigned to the driving dev.
- **Blocking**: see **Blocking** under Conventions.
- **Frontier query**: list the map's open children (`tea issues ls --login gitea.yock.dev -o json --state open`, keeping those whose body starts `Part of #<map>`), drop any with an open blocker (see **Count open blockers**) or an assignee; first in map order wins.
- **Claim**: `tea issues edit --login gitea.yock.dev <n> --add-assignees yock`, the session's first write.
- **Resolve**: `tea comments add --login gitea.yock.dev <n> --description "<answer>"`, then `tea issues close --login gitea.yock.dev <n>`, then append a context pointer (gist + link) to the map's Decisions-so-far.
