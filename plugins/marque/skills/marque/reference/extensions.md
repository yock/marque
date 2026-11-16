# Extensions

An **extension** is prose the orchestrator reads and follows at a named point in the loop. It may name a script or a skill you supply. It is not code with a calling contract: that would need a driver loop or a runtime, and it would not be portable across harnesses. Per-harness plugins are a separate thing, not this mechanism.

## Where an extension lives

Two optional files, each with a `## <point>` section per point it covers:

- **Per project:** `docs/agents/marque.md` — the same file that holds the overrides.
- **Per user or machine:** `~/.config/marque/marque.md`.

Where both cover the same point, the project's text applies after the user's. Marque reads these two files and nothing else: there is no registry, and a skill installed in the harness is not discovered as an extension.

## Approval

Before the first ticket, the orchestrator lists the active extensions — one line each, with the scripts each would run — and the developer approves the list as part of the commission. The approved list goes in `plan.md`. An extension that changes mid-run takes effect only after the developer re-approves it. Nothing activates silently.

## The five points

### commission

Before the first ticket: extra terms to agree, watchers to start.

### dispatch

Before each dispatch. It may hold the dispatch or lower concurrency (pacing).

### brief

Extra rules for the brief's shared tail, beyond the project rules from `AGENTS.md`.

### review

Extra checks the review must pass.

### notify

Extra events, and extra or replacement channels.

**Core events**, sent on every run:

- the target branch is red;
- three failures in a row;
- a paid-compute cap refusing;
- a ticket going `needs-info` or `ready-for-human`;
- the frontier down to externally blocked tickets;
- a summary every ten landings.

The default channel is the harness's push, where it has one, otherwise chat. A notify extension may add events and add or replace the channel; every core event still goes out. Turning notifications off entirely is a term of the commission.

Pick, integrate and land have no extension points. Landing variants are commission or `marque.md` options, never free-form extensions, because the landing safeguards are core. The integrate point still has none: runner configuration (the `## Runner` block) is an override in `docs/agents/marque.md`, not an extension (→ `reference/runners.md`).

## Add or tighten, never loosen

An extension may only add to or tighten the core, never loosen it.

- **dispatch** may hold work; it stays within the commission's concurrency.
- **review** may add gates; it keeps the orchestrator's review and the integration test.
- **brief** may add rules; implementers still leave the tracker, the target branch and the domain docs alone.
- **notify** may change the channel; questions still go on the ticket.

Where an extension conflicts with core a–h, the orchestrator ignores that part, tells the developer, and notes it in `plan.md`.

## The worked example

`examples/battery-pacing/` is the model: a sample `~/.config/marque/marque.md` with `## commission`, `## dispatch` and `## notify` sections, and the `battery.sh` they call.
