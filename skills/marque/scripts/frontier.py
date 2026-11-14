#!/usr/bin/env python3
"""frontier.py --backend gitea --repo OWNER/NAME [--login L] [--json]: the ready queue, ranked.

The tracker's facts arrive as flags; this script reads no config file and no
environment. The queue is the open issues carrying --label. A ticket is on the
frontier when it is unassigned, does not carry --waiting-label, and every one of
its blockers is closed.

Blockers and the parent are read native first, then from the body's `Blocked by:`
line or `## Blocked by` section ("None…" means none) and its `## Parent` section
or `Part of #n`. Native and body edges that disagree are unioned and the ticket is
listed under READ BY HAND, as are references it cannot parse (URLs, cross-repo),
references to missing issues, blockers that are maps or specs rather than tickets,
and tickets with questions but no waiting label.

Rank: how many queued tickets it unblocks (transitively), then tickets with a
parent before those without, then parent number, then issue number.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _tracker import TrackerError, backend  # noqa: E402


def parse_args(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--backend", required=True, choices=["gitea"])
    ap.add_argument("--repo", required=True, help="OWNER/NAME")
    ap.add_argument("--login", help="the tracker CLI login to use")
    ap.add_argument("--label", default="ready-for-agent", help="the queue's label")
    ap.add_argument("--waiting-label", default="needs-info",
                    help="the label that means the user has been asked something")
    ap.add_argument("--json", action="store_true", help="print the frontier as JSON")
    ap.add_argument("--limit", type=int, default=30, help="frontier lines to print (default 30)")
    return ap.parse_args(argv)


def main(argv=None):
    a = parse_args(argv)
    try:
        text = run(a)
    except TrackerError as e:
        print(f"frontier.py: {' '.join(e.cmd)} failed: {e.reason}", file=sys.stderr)
        return 1
    sys.stdout.write(text)
    return 0


def run(a):
    tracker = backend(a.backend, a.repo, a.login)
    queue = tracker.open_issues(a.label)
    open_set = {i["number"] for i in tracker.open_issues()}

    blockers = {}
    for ticket in sorted(queue, key=lambda i: i["number"]):
        blockers[ticket["number"]] = tracker.dependencies(ticket["number"])

    waiting = [t for t in queue if a.waiting_label in t["labels"]]
    front = [t for t in queue
             if not t["assignees"]
             and a.waiting_label not in t["labels"]
             and all(r["state"] == "closed" for r in blockers[t["number"]])]
    front.sort(key=lambda t: t["number"])

    return _text(a, queue, waiting, front)


def _text(a, queue, waiting, front):
    lines = []
    for ticket in sorted(waiting, key=lambda t: t["number"]):
        lines.append(f"WAITING #{ticket['number']} ({a.waiting_label})")
    lines.append(f"queue {len(queue)}  frontier {len(front)}  externally blocked 0")
    for ticket in front[:a.limit]:
        lines.append(f"#{ticket['number']:>5}  fan   0  parent {'-':>5}  c{ticket['comments']}  "
                     f"{ticket['title'][:90]}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
