# PROTOTYPE: symphony without scripts — comparison

Throwaway. Answers [Prototype: symphony without scripts](https://gitea.yock.dev/yock/symphony/issues/10).

## Setup (2026-11-12)

- **Queue:** Ping's live `ready-for-agent` queue, read-only: 103 tickets, 58 on the frontier. The
  queue was identical before and after the trials (`oracle-before.json` = `oracle-after.json`).
- **Oracle:** `oracle.py`, a throwaway script that reads native dependencies **and** both body forms
  and `## Parent`. Hand-checked where any run disagreed.
- **Scripted:** today's `frontier.py`, `split_spec.py` and `brief.py`, unchanged, run against a scratch copy
  of Ping's `symphony.toml` (`root/`), so Ping's live state dir was never written.
- **Prose:** `draft/SKILL.md` describes the three operations in prose. It reads tracker facts from
  `issue-tracker.md` and project rules from `AGENTS.md`, with no `symphony.toml`. Each trial was a
  fresh subagent (Opus, medium) with no access to the scripts. Pick was run 3 times (A, B, C) to
  check for variance.
- **Limitation:** Ping's queue has **no native dependencies** (all 99 blocked tickets declare their
  blockers in the body) and no `## Parent` sections. So this run couldn't show frontier.py's known
  native-blocking miss. All three prose runs did query `/dependencies` for all 103 tickets, as the
  draft says.

## Results

| operation | version | correct? | wall time | model tokens |
|---|---|---|---|---|
| pick | frontier.py | 58/58, order = oracle; 6 READ BY HAND | 5.6 s | ~1.5K to read its 5.7 KB output |
| pick | prose A/B/C | 58/58 each, 0 wrong, 0 missed; order = oracle except where parentless tickets fall in ties (draft didn't say) | 167 / 156 / 143 s | out 8.3–9.0K; new context 34–45K; cache reads 460–707K; 14–18 turns |
| split #591 | split_spec.py | 21 sections + 37 comments | 0.5 s | ~1K (index) |
| split #591 | prose | same files byte-for-byte (slugs and index sizes differ: bytes vs chars) | 34 s | out 2.8K; new 8.3K; reads 120K |
| brief #722 | brief.py | 0 placeholders | 0.05 s | ~0 |
| brief #722 | prose | **identical** to brief.py's output; found the rules file via Ping's AGENTS.md | 18 s | out 1.6K; new 8.3K; reads 96K |

## What it showed

1. **"Prose" pick and split were scripts written fresh each time.** Every pick run and the split run
   wrote throwaway Python (`classify.py`/`extract.py`, `parse.py`/`rank.py`, `parse.py`, `split.py`).
   Only the brief stayed in prose. Removing the script doesn't remove the code; it regenerates it on
   every run, at about 2.5 minutes and about 45K tokens per pick. A run recomputes the frontier after
   every landing (35+ in Ping's run), so that adds up to about 1.5 hours and 300K+ output tokens.
2. **Same correctness on this queue,** but prose has a new failure path: parallel `tea api` calls
   intermittently return "invalid username, password or token" (12, 20 and 34 calls in the three
   pick runs). All three noticed and retried. A run that missed it would read those blockers as
   open (or worse, as closed).
3. **Prose brought judgement the script lacks:** #966 asks the user questions but carries no waiting
   label; #411 is "blocked" by a wayfinder map (#77). frontier.py flagged neither (it notes #411
   under "externally blocked").
4. **The draft's gaps:** where parentless tickets rank (the script sorts them first as spec 0, prose
   put them last); whether a non-ticket reference (a map) is a blocker; whether a ready ticket that
   asks questions without the label is waiting.
5. **brief.py adds nothing over prose:** the output was identical, took 18 s and found the rules
   through AGENTS.md without `symphony.toml`.

## Verdict on which scripts earn their place

- **frontier: keep it as a shipped script, rewritten.** It should read native dependencies first and
  body forms as a fallback, read `## Parent`, use a fixed tie-break for parentless tickets, call the
  API sequentially and fail loudly on any error, and flag questions with no label and non-ticket
  blockers as read-by-hand. Prose costs about 30× the time, a full subagent's tokens per recompute,
  and a new silent-error path for no gain in correctness.
- **split: keep as a script** (small, deterministic, and the agent writes one anyway). The
  margin is small: prose produced the same files in 34 s.
- **brief.py: drop.** Make brief assembly a prose step with the template as an asset.
- **Python** was the language every agent reached for, unprompted.
