<!--
The brief's shared tail. The orchestrator writes the ticket part of
briefs/<n>.md (the ticket, the sources with later amendments applied, the
design fixed, criteria, seams, collisions, slices), fills the placeholders
below, appends this file, and deletes this comment.

Placeholders:
  {{ISSUE}}           the ticket number
  {{PROJECT}}         the repository's name
  {{WORKTREE}}        the absolute path of the ticket's worktree
  {{BRANCH}}          the ticket branch
  {{TARGET}}          the target branch's name (the branch tickets land on)
  {{MAIN_CHECKOUT}}   the absolute path of the main checkout
  {{DOMAIN_DOCS}}     the project's domain docs, as named by its
                      docs/agents/domain.md or AGENTS.md (e.g. GLOSSARY.md,
                      docs/adr/)
  {{BRIEF_EXTENSION}} the project's brief extension, verbatim, or None.
-->

# How to do this work

You are implementing ticket **#{{ISSUE}}** in the `{{PROJECT}}` repository.
The ticket context above is complete. You don't need the issue tracker, and you must not use it.

## Where you work

- **Your worktree:** `{{WORKTREE}}`, on branch `{{BRANCH}}`. Every file you read or write and every command you run uses this path. Pass it as the working directory or use absolute paths.
- **Never touch** the main checkout (`{{MAIN_CHECKOUT}}`), the target branch `{{TARGET}}` (the branch tickets land on), any other worktree or branch. Work only on `{{BRANCH}}`: never push, merge, rebase or switch branches.
- **Never run the tracker's CLI.** The orchestrator owns the tracker.
- **Never edit {{DOMAIN_DOCS}}**, the project's domain docs. If you think one needs a change, say so in your report.

## Build and test

Read the build, test and repo rules in the project's `AGENTS.md` (or `CLAUDE.md`) and the docs it points to before you start, and run the full suite the way they say.

## Brief extension

{{BRIEF_EXTENSION}}

The brief extension adds to the rules above and never loosens them.

## Workflow

Work test-first, one vertical slice at a time:

1. Take the next behaviour from the **Seams to test** list above.
2. **Red:** write one test for it, at that seam, through the public interface. Build, run, and **watch it fail** for the right reason.
3. **Green:** write only enough code to make it pass. Don't build ahead for later tests.
4. Run the filtered tests. Everything that passed before still passes.
5. **Commit** (`#{{ISSUE}}: <what this slice does>`). Small commits: a lost machine loses at most one slice.
6. Next slice. Let what you learned change the next test.

When every criterion has a passing test, run the full suite once, then the self-check.

- **Never kill a process you didn't start**: no `pkill`, `killall` or `kill` by name or pattern. Other agents' builds and test runs share this machine, and a name matches theirs too. If a command of yours hangs, stop it by its own process id.
- **Run every build and test in the foreground and wait for it**, however long it takes; give the command a long timeout. Never run one in the background, and **never end your turn while a command is still running**: your session ends when you reply, and the work is then unfinished. Your final reply comes only after the full suite has finished and everything is committed.

## Test rules

- **Test behaviour, not structure.** A test calls the public interface and checks what a caller can observe. It survives a refactor that keeps the behaviour.
- **Only at the listed seams.** If you need a seam that isn't listed, say so in your report rather than inventing one.
- **No tautological tests.** The expected value must come from an independent source: a figure in the spec, a worked example, a reference value, a known literal. **Never** compute the expected value the way the code does. For numeric results, write the literal and a comment saying where it comes from. If you can't find an independent source, say so in your report.
- **Don't mock what the repo owns.** Fake only system boundaries: time, randomness (a fixed seed), files, the network.
- **No horizontal slicing.** Don't write all the tests first. One test, then its code, then the next.
- **No refactoring during the loop.** Note refactors you'd like in your report.
- **One behaviour per test**, named for what it shows, not how.
- Scripted scenarios: build the smallest setup that shows the behaviour, with a fixed seed.

## Self-check before your final commit

- [ ] Every acceptance criterion has a test that fails without the change and passes with it.
- [ ] Every expected value has an independent source.
- [ ] Nothing outside the ticket's scope changed (no drive-by fixes, no speculative options).
- [ ] The full suite passes.
- [ ] `git -C {{WORKTREE}} status` is clean: everything is committed on `{{BRANCH}}`.

## Your report (keep it under 300 words)

```
#{{ISSUE}}: done | partial | blocked
Commits: <sha  subject>, one per line
Criteria → tests: <criterion> → <test name>, one per line
Expected-value sources: <test> → <source>, where not obvious
Full suite: pass | <failing tests>
Not done / blocked: <what and why>
Questions: <spec ambiguities you resolved yourself, and how>
Suggested follow-ups: <refactors, domain-doc changes, out-of-scope bugs>
```

If you're blocked by a real ambiguity, stop, commit what's green, and report `blocked` with the question. Don't guess at behaviour the ticket doesn't define.
