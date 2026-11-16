# Commission

Agree the commission with the developer **before the first ticket**, and record it in `plan.md` (in the state dir). It settles what the tracker's doc must cover, which account Marque acts as, how finished tickets land, and which extensions apply. Nine steps, in order; the first can end it.

## 1. Setup check

The setup files are `docs/agents/issue-tracker.md` and a `## Agent skills` block in `AGENTS.md` or `CLAUDE.md`. If either is missing, stop and say: **"Run `/setup-matt-pocock-skills` first."** Nothing else happens.

## 2. Defaults

List these to the developer:

- **State dir:** `~/.local/share/marque/<repo-name>` — `plan.md`, `ledger.tsv`, `briefs/`, `specs/`, `logs/`, `landing/`.
- **Worktrees:** `<repo>/.marque/worktrees/marque-<n>` on branch `marque-<n>`.
- **Stall hour:** 1 hour.

`docs/agents/marque.md` is the **only** place to override them; a term agreed in chat does not move them. Make sure `.marque/` is git-ignored: propose the line `.marque/` for `.git/info/exclude`, and write it once the developer approves.

## 3. Tracker gap-check

`issue-tracker.md` is where tracker facts live; the scripts take them as `--backend`, `--repo` and `--host`. Read the doc, then check it against each operation Marque needs. Settle the landing mode (step 5) first if the developer hasn't named it: the **pr** rows apply only in `pr` mode, and **Read PR approval** only with "the developer approves".

| Operation | Needed for |
|---|---|
| List by label | the queue |
| Read an issue | explore, review |
| Parent | the ticket's spec |
| Blocking | edges between tickets |
| Count open blockers | a quick check by hand |
| Assign / unassign | the claim |
| Comment | questions, resolution comments |
| Apply / remove labels | `needs-info` and back |
| Close | landing, and the close probe |
| Open a PR | `pr` mode |
| Merge a PR | `pr` mode |
| Read PR approval | `pr` mode with "the developer approves" |

For a gap, open the project's tracker snippet — `reference/trackers/github.md`, `reference/trackers/gitlab.md`, `reference/trackers/gitea.md` or `reference/trackers/local.md` — take the smallest plain convention it offers, show it, and add it to the doc's Conventions **only with the developer's approval**. It reads as one plain convention bullet, never a Marque-branded section. A tracker outside those four works if its doc covers the same operations.

**Live check:** run the doc's read-only commands once on a real ticket — **Blocking** and **Count open blockers** on one ticket will do. Where the doc and the live tracker disagree, say so and offer the doc the fix. A doc claiming Gitea has no native dependencies while the tracker returns one is the case to expect.

## 4. Marque's account

Marque has no identity setting of its own. It runs the tracker doc's commands exactly as written, account flags included (such as `tea --login <name>`), and never adds, strips or rewrites one. The scripts read as the CLI's signed-in or default account. Never switch or log in the CLI's account.

Say once which account the doc's write commands act as: the one their account flag names, otherwise the CLI's signed-in or default account. That is **Marque's account**. If the scripts read as a different account, say that too. Leave any account flag or `**Orchestrator identity**` line in the doc as it is, and offer no change to it. Marque starts every comment and ticket body it writes with `> *Posted by Marque.*`.

**Claims.** A `ready-for-agent` ticket is claimed by assigning it to Marque's account, with a ledger row. The ledger decides: assigned **with** a ledger row is Marque's claim. Assigned **without** one, report "assigned, not in my ledger: yours, or orphaned?" and neither take it nor unassign it until the developer answers.

## 5. Terms

Agree every term with the developer and write this block to `plan.md`:

```markdown
## Commission

- **Implementer model**: <model> (<variant>)
- **Authority**: <land and close without asking? yes | no>
- **Fallback**: <may the orchestrator implement once the retries run out? yes | no>
- **Concurrency**: <n>
- **Paid compute**: <on | off> — runner <local | beam>, rate <amount per wall-minute, matching the account's tier>, cap <amount>, runner concurrency <n>, max wall time <seconds>
- **Target branch**: <branch> — the repo's default branch unless the developer names another
- **Landing mode**: <direct | pr>
- **Approval cap**: <n> — `pr` mode with "the developer approves"; default, the concurrency
- **Merge style**: <--no-ff | squash> — from AGENTS.md; default, `--no-ff`
- **Notifications**: <on | off>
- **Extensions**: <the approved list>
```

Landing terms beyond the block — the target branch, the modes and their safeguards — are in `reference/landing.md`.

The orchestrator passes the rate, cap and runner concurrency to `suite.py` as `--rate`, `--cap` and `--concurrency` (→ `reference/runners.md`).

For `pr` mode, recommend the forge's **branch must be up to date before merging** setting. With it, the forge never merges onto a target that moved after the integration run, so `finish`'s tree check (`reference/landing.md`) stays quiet.

## 6. `pr` with "the developer approves"

**Read PR approval** was gap-checked in step 3. Now decide whether the term is possible: Marque's account must differ from the account that approves. Ask whether it does. If Marque's account is also the approving account, the term is **impossible**: an account can't approve its own PR. Offer having the orchestrator merge once the checks pass. Otherwise the term stands, and while a PR waits for approval the ledger reads `awaiting-approval`.

## 7. Shared machine

If the project's full suite looks heavy, ask whether its `AGENTS.md` says how suites take turns. Don't impose a lock: the integration runs follow whatever rule it states.

For a heavy suite, also ask whether to declare a `## Runner` block in `docs/agents/marque.md` so integration runs go to a rented runner (→ `reference/runners.md`), and whether the suite can fall back to the local machine (`local fallback: no` if not).

## 8. Extensions

List the active **commission**, **dispatch**, **brief**, **review** and **notify** extensions from `docs/agents/marque.md` and `~/.config/marque/marque.md`: one line each, plus the scripts each would run. The developer approves them as part of the commission, and they go under **Extensions** in `plan.md`. A mid-run change needs re-approval. → `reference/extensions.md`

## 9. Harness permissions

Before the first dispatch, check that the harness lets background implementers write to their worktrees and run the build without prompts. → `reference/harnesses.md`

The commission is done when `plan.md` holds every term and the tracker doc covers every operation its landing mode needs. Then the loop begins.
