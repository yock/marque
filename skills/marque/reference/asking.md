# Asking

## When

Ask when the ticket has a gap with no default to fall back on:

- a seam you can't fix without the developer;
- a step that needs a human or an outward action: downloads, licences, accounts, review by eye;
- `ready-for-agent` turning out not to be ready — say what you believe is missing.

Never invent the missing behaviour.

## How

Comment on the ticket.

**First line: the urgency.** "Blocks work underway" — a started ticket, a landed ticket's follow-up, a parent spec that can't complete without it — or "Still being planned".

Then the questions, numbered, each with a recommended answer, ending "reply 'all as recommended' or answer by number". Say what waits on it, checking the parent spec as well as the queue.

Relabel `ready-for-agent` → `needs-info` through `triage-labels.md` (the canonical names if that file is absent), unassign, and set the ledger row to `needs-info`. The label and assignee commands are in `issue-tracker.md`, run as the orchestrator identity. In chat, name the ticket only.

## The answer signal

The developer answers on the ticket and relabels it `ready-for-agent`. It reappears on the frontier while its ledger row still reads `needs-info`; read its newest comments, which amend it.

`ready-for-human` keeps its own meaning: the ticket needs a human implementation. It isn't for questions.
