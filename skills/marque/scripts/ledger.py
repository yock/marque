#!/usr/bin/env python3
"""ledger.py --state-dir DIR <command>: the queue's ledger, one row per ticket.

The ledger is DIR/ledger.tsv: a header row and then one tab-separated row per
ticket with the columns issue, state, branch, worktree, session, attempts, brief,
verdict, landed, note. It is kept by this script so it can't drift from its
schema.
"""
import argparse
import sys

STATES = [
    ("queued", "in the queue, not started"),
    ("exploring", "the read-only explore step is running"),
    ("briefed", "the brief is written; not dispatched yet"),
    ("running", "an implementer is working in the ticket's worktree"),
    ("review", "the orchestrator is reviewing the implementer's report and diff"),
    ("retry", "sent back to the same implementer session with review findings"),
    ("orchestrator", "the orchestrator is implementing the ticket itself (retries exhausted)"),
    ("landing", "the guarded landing is under way: merge, push, comment, close, clean-up"),
    ("awaiting-approval", "pr mode: the pull request is open, waiting for the developer's approval"),
    ("landed", "merged and closed; the `landed` column holds the merge commit"),
    ("needs-info", "questions are on the ticket, waiting for the developer"),
    ("blocked", "blocked by something outside the queue"),
    ("ready-for-human", "needs a human to implement it"),
    ("abandoned", "dropped; won't be done"),
]

EPILOG = """\
states, in order:
""" + "".join("  %-20s%s\n" % (state, meaning) for state, meaning in STATES) + """\

Crash recovery visits the in-flight states -- where a worktree, a session or a
half-done landing can be left behind. They are running, review, retry, orchestrator, landing.
awaiting-approval is not in flight: the PR waits on the tracker, and the normal
loop checks it every pass.
"""


def main():
    ap = argparse.ArgumentParser(
        description=__doc__.split("\n")[0],
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--state-dir", required=True, metavar="DIR")
    ap.parse_args()


if __name__ == "__main__":
    main()
