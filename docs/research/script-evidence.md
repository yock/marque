# What the scripts earn: evidence from real runs

Research for [#5](https://gitea.yock.dev/yock/symphony/issues/5) (map #1). The question: for each script and template, what does it give the orchestrator that an agent following prose operations can't do reliably or cheaply (determinism, token cost, correctness traps, speed)? And where do the scripts' assumptions diverge from what `to-tickets` and `wayfinder` publish?

## Sources

- **The one real run:** ping, 2026-11-10 to 11-12. Its config `~/Work/ping/docs/agents/symphony.toml` names `state.dir = ~/.local/share/symphony/ping`, a symlink to `~/.local/share/ping-orchestrator/`. No other `docs/agents/symphony.toml` exists under `~/Work/*`, so this is the only state dir. It holds `plan.md` (237 lines), `ledger.tsv` (156 rows), `briefs/` (40), `explore/` (11), `specs/` (5 specs), `logs/` (136 files, including `queue.json`), `battery.log` (1,945 samples), and `bin/`, which holds the run's scripts from before symphony existed (`frontier.py`, `split-spec.py`, `battery-watch.sh`, `battery-now.sh`).
- **symphony history:** `88ccfff` (extraction from the ping run, 2026-11-11 12:18) through `4f9be3b`. **No script has changed since `88ccfff`.** Every rule added later is prose: `ebdf77a`, `7c23b7e` (SKILL.md, asking the user), `a768105`, `d58bec9`, `4f9be3b` (operations.md and templates/brief.md).
- **Publishers:** `~/.agents/skills/to-tickets/SKILL.md`, `~/.agents/skills/wayfinder/SKILL.md`, and the two repos' `docs/agents/issue-tracker.md`.
- **Live tracker reads (read-only):** `tea api --login yockbot …/dependencies` on yock/ping and yock/symphony, and the server's version (Gitea 1.27.3).

The state dir was only read. I did not run `frontier.py` because it writes `logs/queue.json` into the state dir; I analysed the copy it last wrote (2026-11-11 20:38, which has the `hand` and `notes` fields only the symphony version writes).

## Summary

| Piece | What it earns | Strength |
|---|---|---|
| `frontier.py` | Token cost (about 213 KB of ticket bodies reduced to a ranked page), a deterministic transitive fan-out rank, union of two blocker forms with a READ BY HAND list | **Strong**, but it reads the wrong place for blockers on any tracker that follows wayfinder or to-tickets |
| `split_spec.py` | Specs of 124–556 KB (one about 760 KB) become files you can grep with a 2.5–5.5 KB index, from raw markdown not tea's reflowed text; a fixed layout the explore prompt depends on | **Strong**; small and deterministic |
| `brief.py` | Fills placeholders, splices the project's rules, guards against leftover placeholders, a missing ticket part and a doubled tail | **Weak**: the run did the same with a `sed` pipeline and `grep -c '{{'` and produced 0 leftovers either way |
| `symphony_lib.py` | Finds the config and calls tracker REST (gitea or github), with paging | Only plumbing for the above; its config repeats facts the tracker docs already hold |
| `templates/brief.md` | The rules each implementer must follow, several of them added after failures | **Strong** as text; doesn't need a script |
| `templates/explore.md` | A fixed-shape, read-only explore prompt for a cheap model | **Strong** as text; repeats frontier's blocker assumption |
| `battery.sh` | Pacing on a laptop | Out of scope for the published form |

## Per script

### frontier.py

**What it does** (`scripts/frontier.py:1-23`): pages every open issue with the ready label and every open issue at all. It parses `Part of #n`, the top `Blocked by:` line and any `## Blocked by` section, taking the union of the two blocker forms (`frontier.py:34-58`). It keeps ready, unassigned tickets without the `blocking` label whose blockers are all closed. It ranks them by transitive fan-out, then spec number, then issue number (`frontier.py:79-103`), and prints a short page with READ BY HAND, WAITING and ANSWERED headers.

**Token cost.** In the last `queue.json`, 119 queued tickets had 212,992 characters of body between them, about 53K tokens at 4 characters per token. The printed frontier is at most `--limit 30` lines (`frontier.py:68`), around 1–2K tokens. SKILL.md has the orchestrator recompute the frontier after every landing (`SKILL.md` loop step 10). The run landed 35+ tickets (`plan.md`, "State at 2026-11-11 evening"). Re-reading the queue by hand at each landing would have cost on the order of 1.8M tokens across the run (an estimate: 35 × 53K, ignoring the second listing of all open issues).

**Determinism and correctness.**
- The rank is a transitive closure over the dependency graph (`reach()`, `frontier.py:84-91`). The highest fan-outs were 7 and 8, so a ticket unblocked up to 8 queued tickets downstream. Working that out by eye over 119 tickets is error-prone, and two passes could give different answers.
- **Two blocker forms really occur.** Of the 119 queued ping tickets, 105 carry both the `Blocked by:` line and the `## Blocked by` section, 9 only the line, 1 only the section (#954, a follow-up filed by the user's ruling), and 4 neither. A prose rule saying "read the `Blocked by:` line" (ping's own tracker doc says exactly that, in `~/Work/ping/docs/agents/issue-tracker.md` under "Wayfinding operations") would miss #954's blocker. The pre-symphony `bin/frontier.py` had this bug: it read only the top line with an unanchored `re.search(r"Blocked by:([^\n]*)")`.
- **Holds moved onto the tracker.** The old script hard-coded `HELD = {"881": "897"}` (`~/.local/share/ping-orchestrator/bin/frontier.py`). Commit `88ccfff` dropped that, and `plan.md` records that "the #881 hold now lives on the tracker (`Blocked by: #383, #897`), not in the script". That is the right lesson, and it applies to native dependencies too (see the divergences below).
- **READ BY HAND did its job.** The last run flagged 5 of 119: #430, #577, #583 and #962 had no `Part of #`, and #954 had a section without the line. Nothing was silently decided.
- **The ANSWERED feature never fired.** It needs the orchestrator to put `state.asked_marker` ("QUESTIONS ON TICKET") in the ledger note when it asks (`frontier.py:93-98`, `reference/operations.md` "The ledger"). The ledger has **0** rows with the marker. The two answered tickets, #666 and #763, carry a hand-written `ANSWERED 2026-11-11: …` note instead (`ledger.tsv`). The label round trip (`ready-for-human` + `blocking` → back to ready) is what actually brought them back. This feature relies on a prose discipline that wasn't kept, so drop it or derive it from the tracker (for example, a comment by a non-agent user newer than the agent's question).
- **Traps it still has:**
  - A blocker counts as closed whenever its number isn't in the open issue set (`frontier.py:74-75`). A typo, a deleted issue or an open pull request (`open_issues` filters PRs out, `symphony_lib.py:96`) all read as "closed".
  - `NUM = #(\d+)` reads `other/repo#12` as local #12 and ignores a full issue URL.
  - It writes a 258 KB `logs/queue.json` on every run, so it is not read-only.

**Speed.** Two REST listings, paged at 50 (`symphony_lib.py:86-99`): seconds. Done by hand, it would take dozens of `tea` calls and their output in context.

**Verdict.** It earns its place on token cost and on a deterministic rank. It must read native blocking, though (next section), or it is wrong on exactly the trackers its publishers target.

### split_spec.py

**What it does** (`scripts/split_spec.py:1-10`): fetches one issue and all its comments through raw REST and writes `body-NN-<slug>.md` per `##`/`###` section, `cNN.md` per comment, and `index.txt`.

**Token cost.** The split specs on disk are #94 at 124 KB, #117 at 152 KB, #130 at 180 KB, #365 at 460 KB and #591 at 556 KB. Their `index.txt` files run 2.5–5.5 KB. `plan.md` says "Never read #365 (≈760 KB) whole" and "Spec #591's parts are comments c01–c08 (30–60 KB each); grep their `###` headings and read only the named subsection". `specs/591/index.txt` confirms it: c01 is 60,795 B and c08 is 33,870 B, while the 28 later "Input from …" comments that amend values are 0.2–3.2 KB each.

**Correctness.**
- It reads raw markdown from the API. `tea issues` reflows bodies, `tea issues` without `--comments` drops comments silently, and `tea comments ls` clips comment bodies to about 100 characters in every output format (`~/Work/ping/docs/agents/issue-tracker.md`, "Conventions"). An agent following prose has to know all three traps. The script makes them irrelevant.
- Comments are numbered in order, matching the "latest word wins" rule the explore template relies on (`templates/explore.md`).

**Shared layout.** The explore prompt points the cheap model at `{{SPECS}}/{{SPEC}}/index.txt` (`templates/explore.md`). The split is what makes "find the named section" a grep for a cheap model rather than a 500 KB read.

**Verdict.** It earns its place: 54 lines, deterministic, and the largest token saving in the toolkit. A prose version ("fetch the raw body to a file, split on headings") is possible, but every orchestrator would write it slightly differently, and the explorer depends on the layout.

### brief.py

**What it does** (`scripts/brief.py:1-12`):
- `brief N BRANCH` appends `templates/brief.md` below its `---` line, with placeholders filled and the project's `brief.rules` spliced in at `{{PROJECT_RULES}}`, to `briefs/N.md`. It refuses if the ticket part is missing or the tail is already there, and fails on any leftover `{{…}}` (`brief.py:28-31,73-86`).
- `explore N SPEC` writes the filled explore prompt.

**Evidence.**
- All 40 briefs have exactly one `# How to do this work` tail and **0** leftover `{{`. Only 10 of them (#763, #666, #690, #700, #737, #665, #703, #736, #797, #717, all written after 2026-11-11 12:18) postdate `brief.py`.
- The first 30 were produced by the prose method in `plan.md` ("`sed … | sed '1,/^---$/d' >> briefs/N.md`. Check `grep -c '{{'` is 0"), with the same result.
- The tail is 5.8–7.2 KB of a 12–19 KB brief (#606: 5,810 B; #717: 7,208 B). Neither method puts it through the orchestrator's context: both append it with a shell pipeline. So `brief.py` saves no tokens over the sed line.
- Its real addition is project portability: it splices `docs/agents/symphony-brief.md` (3,468 B in ping, commit `0560191d`), which replaced ping-specific text that had been hard-coded in the old `brief-template.md` (diff of `~/.local/share/ping-orchestrator/brief-template.md` against `templates/brief.md`).

**Verdict.** Weak. The guards are worth a line of prose ("append the template and the project's brief rules; `grep -c '{{'` must be 0; the ticket part comes first"). A tiny optional helper is fine, but nothing in the run shows that prose failed here.

### symphony_lib.py

**What it does:** finds the config (`--config`, `$SYMPHONY_CONFIG`, or by walking up the directory tree, `symphony_lib.py:26-35`) and calls `tea api` or `gh api` with paging (`symphony_lib.py:68-117`).

**Evidence:** the plumbing worked across the 10 post-extraction briefs and the frontier runs. Two costs show up:
1. `symphony.toml` repeats facts the target repo's `docs/agents/issue-tracker.md` and `triage-labels.md` already own: repo, login, label names (`~/Work/ping/docs/agents/symphony.toml` against `~/Work/ping/docs/agents/issue-tracker.md`). Two places for one fact can drift.
2. Tracker support is limited to `gitea` and `github` (`symphony_lib.py:46-47`), while `to-tickets` also targets Linear and local files (`to-tickets/SKILL.md:60-63`).

**Verdict:** it survives only as long as the other scripts do.

## Templates

### templates/brief.md

This is where rules born of failures live. The template is what the cheap implementer actually reads:

- **No background commands, and no reply while one is running.** Added after Flash on #606 "ended its turn while its ctest ran in the background, leaving uncommitted work" (`plan.md`, Pilot notes; carried into `88ccfff`).
- **Never kill a process you didn't start.** `d58bec9`, after integration shards died at once. `4f9be3b` later found the real cause was systemd-oomd, not pkill, but kept the rule.
- **Full suites take turns under `flock`.** Added to the project's brief rules (ping `e7789e0d`) and to `reference/operations.md` (`4f9be3b`).
- **The size-guard comment is not to be edited by implementers** ("every ticket conflicted there"). This is in `plan.md` from 2026-11-11 and now sits in ping's brief rules, not in the shared tail.

Each was a one-paragraph prose change. None needed a script change, which is evidence that the template's value is its text, not the renderer.

### templates/explore.md

The `plan.md` pilot notes record that briefing cost "a lot of Opus context on code exploration (#606, #821 each took ~10 tool calls of greps)". The fix was a read-only explorer on the cheap model with a fixed five-part report (SPEC, BLOCKERS LANDED, CODE, TESTS, GAPS AND RISKS). There are 11 explore prompts in `explore/` (2.2–2.7 KB each), and ledger notes such as #722's show what they found ("HOLD until #665 and #736 land … Explore ses_…").

It earns its place as text. It also tells the explorer to find blockers in "its `Blocked by:` line or `## Blocked by` section", which is the same assumption as frontier's, with the same divergence.

## battery.sh (briefly)

The run used it heavily: 1,945 samples in `battery.log`. A `run` watcher exit (LOW 39) paused dispatch and switched to `watch wait` (`plan.md`, "Battery LOW 39 %"). It is machine pacing, out of scope for the published form per the ticket's framing.

## Not scripted, and it shows: the ledger

`reference/operations.md` says to update rows "with a small script", but none ships, and the ledger has drifted from its documented schema:
- The states `blocked-ext` and `held` are not in the documented state list.
- #665's session column holds `explore:ses_…` and its notes run past 200 characters.
- `ANSWERED` is hand-written where `asked_marker` was expected.

This is evidence for the converse question: prose discipline drifts on structured state. If anything is added, a ledger helper earns more than `brief.py` does.

## Where the scripts' assumptions diverge from what's actually published

| Script assumes | to-tickets publishes | wayfinder publishes | Consequence |
|---|---|---|---|
| Blockers as body text: a `Blocked by: #a, #b` line and/or a `## Blocked by` section (`frontier.py:34-36`) | "Use the platform's **native** blocking / sub-issue relationship where it has one; otherwise set each ticket's 'Blocked by'" (`to-tickets/SKILL.md:63`). The `## Blocked by` section is in the issue template (`:99-101`) | "Blocking uses the tracker's **native** dependency relationship … Only a tracker that lacks native blocking falls back to a body convention" (`wayfinder/SKILL.md:69`) | **On Gitea and GitHub, frontier.py is blind to blockers.** Observed live: yock/symphony's own map tickets carry native Gitea dependencies (#12 ← 11, 3, 2; #11 ← 10, 6, 8, 4; #10 ← 7, 5; #9 ← 6, 3; #8 ← 6, 4; #7 ← 3; #6 ← 2), and #12's body has only `Part of #1` and `## Question`. frontier.py would list all of them as unblocked, with only a "no blocker declaration" note (`frontier.py:52-53`) |
| Gitea has no native dependencies | (n/a) | (n/a) | ping's tracker doc says "Gitea has no native issue dependencies" (`~/Work/ping/docs/agents/issue-tracker.md`, Wayfinding operations; last changed `df4fe6ea`). The server is Gitea 1.27.3 and `GET repos/{o}/{r}/issues/{n}/dependencies` works. symphony's own tracker doc (`7779d95`) uses it. The run worked only because ping's tickets were written in the body-text convention: native dependencies on ping #717 were `[]`, while its body has `Blocked by: #715, #614` |
| Parent as a `Part of #<spec>` line (`frontier.py:36`); a missing one goes to READ BY HAND and ranks as spec 0 (`frontier.py:55-57`) | A `## Parent` **section** holding "a reference to the parent issue" (`to-tickets/SKILL.md:86-88`), or the native sub-issue relationship | Child issues of the map. The *how* is tracker-specific (`wayfinder/SKILL.md:21,25`). Both repos' tracker docs spell it `Part of #<map>` at the top | A to-tickets ticket without a `Part of` line lands every time in READ BY HAND with spec 0, and the ranking's spec order is lost. In ping, 105 of 119 tickets had both forms, because ping's tickets came from a generator that wrote both |
| A `## Blocked by` section without a top line is suspicious (READ BY HAND, `frontier.py:54-55`) | The section **is** the fallback form; there is no top line (`to-tickets/SKILL.md:99-101`) | (n/a) | Every to-tickets fallback ticket is flagged READ BY HAND, including those whose section says "None (can start immediately)": that parses as an empty set, not as no section, so it is flagged as "section lists []" |
| Blocker references are `#n` in the same repo (`NUM`, `frontier.py:37`) | "A reference to each blocking ticket": an id, title or URL | Native links can cross repos | A full URL is ignored, `owner/other#12` is read as local #12, and anything not in the open set reads as closed (`frontier.py:74`) |
| Tracker is gitea or github (`symphony_lib.py:46`) | GitHub, Linear, … or local `.scratch/<slug>/issues/NN-*.md` files (`to-tickets/SKILL.md:62-63`) | Local markdown is the default when no tracker is configured (`wayfinder/SKILL.md:25`) | No path for Linear or local tickets. The local template's `**Blocked by:**` (bold, with "None (can start immediately)") would not match `^\s*Blocked by:` |
| The explorer reads blockers from the body (`templates/explore.md`) | As above | As above | The explorer won't read the resolutions of blockers that exist only as native links |

Not verified here: the exact GitHub REST endpoints for issue dependencies and sub-issues. The divergence holds whatever they are, since `frontier.py` makes no dependency or sub-issue call at all.

## What this suggests for the published form

1. **Keep a frontier helper**, rewritten to read blockers the way the publishers write them:
   - native dependencies first (Gitea `/issues/{n}/dependencies`, GitHub's equivalent);
   - then the body forms (`## Blocked by`, the `Blocked by:` line, the bold local form) as fallbacks;
   - the parent from `## Parent`, the native parent, or `Part of #`.
   Keep READ BY HAND for real disagreements only. Treat "not open" as closed only after confirming the number exists and is an issue. This is where a script beats prose: a 119-ticket queue, a transitive rank, and a recompute after every landing.
2. **Keep the spec splitter.** It is the largest token saving, avoids the `tea` reflow and comment traps, and gives the explorer a fixed layout.
3. **Demote `brief.py` to prose** (or a trivial optional helper). Keep both templates as the real assets: they are where the failure-driven rules live.
4. **Drop the ANSWERED flag** or derive it from the tracker. It never fired in the run.
5. **Get tracker facts from the repo's tracker docs**, not from a second config, or at least check that the two agree.
6. **Consider a ledger helper**: the ledger is where prose drifted.
