Read-only research for the codebase at {{MASTER}} (the main checkout). Change nothing; don't write files.

Ticket #{{ISSUE}} is about to be implemented. Get its text and comments with:
  {{API}} repos/{{REPO}}/issues/{{ISSUE}} | python3 -c 'import json,sys;print(json.load(sys.stdin)["body"])'
  {{API}} repos/{{REPO}}/issues/{{ISSUE}}/comments | python3 -c 'import json,sys;[print("--",c["created_at"],"\n",c["body"]) for c in json.load(sys.stdin)]'
For each issue it is blocked by (its `Blocked by:` line or `## Blocked by` section), read the LAST comment the same way: its resolution, what landed, names in code.

Its parent spec is split into files under {{SPECS}}/{{SPEC}}/ (index.txt lists them: body-NN-*.md are the spec body's sections; cNN.md are its comments in order, which amend the body, latest word wins). Find the spec sections the ticket names and any later comment that changes what this ticket builds (grep for the ticket number and its key terms).
{{EXPLORE_NOTES}}
Then explore the code under {{CODE}} for what the implementer will build on. Report, under 900 words, in this shape:
1. SPEC: file:line ranges of the exact spec sections the ticket depends on, and any later amendment that changes it (quote the changed sentence).
2. BLOCKERS LANDED: per blocker, the files/functions/types it added that this ticket uses.
3. CODE TO BUILD ON: existing files, structs, functions (with file:line) the ticket extends or calls; where similar behaviour already exists to copy the pattern from.
4. TEST PATTERNS: existing test files and test names that set up a comparable scenario to copy.
5. GAPS AND RISKS: anything the ticket assumes that does not exist yet; ambiguities; where its acceptance criteria don't fit the data or code; places it could collide with other open tickets.
Facts only, with file:line references; no implementation advice beyond naming where things go.
{{IN_FLIGHT}}
