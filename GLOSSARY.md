# Symphony

Symphony delegates a spec's implementation tickets to implementer agents and lands their work. It is the stage after wayfinding: a map's decisions define a spec, `to-tickets` splits the spec into implementation tickets, and symphony works them down.

## Language

**Spec**:
The written definition of a change, the parent of its implementation tickets. Usually the end product of a wayfinder map.
_Avoid_: PRD, plan

**Implementation ticket**:
One vertical slice of a spec, sized for one agent session, declaring the tickets that block it. Produced by `to-tickets`.
_Avoid_: wayfinder ticket, task

**Decision ticket**:
A wayfinder map's ticket, whose resolution is a decision rather than built work. Symphony does not consume these.
_Avoid_: implementation ticket

**Queue**:
The implementation tickets labelled ready for an agent.

**Frontier**:
The queued implementation tickets that are unclaimed and whose blockers are all closed.

**Orchestrator**:
The agent that picks, briefs, dispatches, reviews, integrates, lands and closes implementation tickets.
_Avoid_: dispatcher, manager

**Implementer**:
An agent that builds one implementation ticket in its own worktree and reports back; it never touches the tracker or the main branch.
_Avoid_: worker, subagent

**Brief**:
The file an implementer works from: the ticket, its spec sources, the design fixed at its seams, and the shared rules.
_Avoid_: prompt

**Landing**:
Merging an integrated, green ticket branch onto the main branch, then closing its ticket.
