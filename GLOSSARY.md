# Marque

Marque delegates implementation tickets to implementer agents and lands their work, under the command of a developer who holds its session. It is the stage after wayfinding: a map's decisions define a spec, `to-tickets` splits the spec into implementation tickets, and Marque works down every ready ticket in the queue, whichever spec it came from.

## Language

**Spec**:
The written definition of a change, the usual parent of its implementation tickets. Usually the end product of a wayfinder map.
_Avoid_: PRD, plan

**Implementation ticket**:
A ticket specified fully enough to be built in isolation in one agent session, declaring the tickets that block it. Usually a vertical slice of a spec produced by `to-tickets`, either self-contained or pointing at the issues that carry its detail; any other fully specified ticket, such as a triaged bug fix, counts too.
_Avoid_: wayfinder ticket, task

**Decision ticket**:
A wayfinder map's ticket, whose resolution is a decision rather than built work. Marque does not consume these.
_Avoid_: implementation ticket

**Queue**:
The implementation tickets labelled ready for an agent. The label is someone's claim that a ticket is ready; the orchestrator verifies it and may refer the ticket back to the developer, naming what it finds missing.

**Frontier**:
The queued implementation tickets that are unclaimed and whose blockers are all closed.

**Developer**:
The human who holds the orchestrator's session, grants its commission, answers its questions, and can step in to steer or stop it at any time.
_Avoid_: user, operator, admiral

**Commission**:
The authority the developer grants the orchestrator for one run: what it may do without asking, and the limits it works within.
_Avoid_: settings, config, plan

**Extension**:
Instructions the developer adds at one of the orchestrator's fixed extension points, for a project or a machine. An extension may add to or tighten the orchestrator's method, never loosen it.
_Avoid_: plugin, hook, override

**Marque's account**:
The tracker account Marque's writes act as: the one the tracker doc's commands name with an account flag, otherwise the CLI's signed-in account. Marque has no identity setting of its own.
_Avoid_: orchestrator identity, bot identity

**Orchestrator**:
The agent that picks, briefs, dispatches, reviews, integrates, lands and closes implementation tickets, within its commission.
_Avoid_: dispatcher, manager

**Implementer**:
An agent that builds one implementation ticket in its own worktree and reports back; it never touches the tracker or the main branch.
_Avoid_: worker, subagent

**Brief**:
The file an implementer works from: the ticket, its relevant sources, the design fixed at its seams, and the shared rules.
_Avoid_: prompt

**Landing**:
Merging an integrated, green ticket branch onto the target branch, directly or through the ticket's pull request, then making sure its ticket is closed. The target branch is a term of the commission, the repo's main branch unless the developer names another. A ticket whose pull request is still open is not landed.
_Avoid_: shipping, merging (for the whole act)
