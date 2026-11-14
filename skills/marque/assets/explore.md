<!--
The explore prompt. The orchestrator fills the placeholders below, removes this
comment and gives the result to a read-only explorer.

Placeholders:
  {{ISSUE}}         the ticket number
  {{MAIN_CHECKOUT}} the absolute path of the main checkout
  {{READ_ISSUE}}    the tracker doc's **Read an issue** command, with the
                    orchestrator's identity, the raw-markdown form where the
                    doc gives one, and `<number>` left in for the explorer to
                    substitute
  {{SPEC}}          the parent spec's number
  {{SPEC_DIR}}      the directory split_spec.py wrote that spec to
  {{EXPLORE_NOTES}} the explore notes from docs/agents/marque.md, or empty
  {{IN_FLIGHT}}     the in-flight tickets and the files they touch, or None.
-->

Read-only research for the repository at {{MAIN_CHECKOUT}} (the main checkout). Change nothing; don't write files.

Ticket #{{ISSUE}} is about to be implemented. Read the ticket and its comments with:

  {{READ_ISSUE}}

substituting {{ISSUE}} for `<number>`. Its blockers: the tracker's native blocking relation if the doc names one, else its `Blocked by:` line or `## Blocked by` section. Read each blocker's newest comment the same way: its resolution, what landed, names in code.

Its parent spec #{{SPEC}} is split into files under {{SPEC_DIR}}/ (index.txt lists them: body-NN-*.md are the spec body's sections; cNN.md are its comments in order, which amend the body, latest word wins). Find the spec sections the ticket names and any later comment that changes what this ticket builds (grep for the ticket number and its key terms).
{{EXPLORE_NOTES}}
Then explore the repository at {{MAIN_CHECKOUT}} for what the implementer will build on. Report, under 900 words, in this shape:
1. SPEC: file:line ranges of the exact spec sections the ticket depends on, and any later amendment that changes it (quote the changed sentence).
2. BLOCKERS LANDED: per blocker, the files/functions/types it added that this ticket uses.
3. CODE TO BUILD ON: existing files, structs, functions (with file:line) the ticket extends or calls; where similar behaviour already exists to copy the pattern from.
4. TEST PATTERNS: existing test files and test names that set up a comparable scenario to copy.
5. GAPS AND RISKS: anything the ticket assumes that does not exist yet; ambiguities; where its acceptance criteria don't fit the data or code; places it could collide with other open tickets.
Facts only, with file:line references; no implementation advice beyond naming where things go.
{{IN_FLIGHT}}
