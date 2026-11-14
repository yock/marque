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
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _tracker import TrackerError, backend  # noqa: E402

TOP = re.compile(r"(?mi)^[ \t]*Blocked by:(.*)$")
SECTION = re.compile(r"(?ms)^#{2,}[ \t]*Blocked by[ \t]*\n(.*?)(?=^#{2,} |\Z)")
PARENT_SECTION = re.compile(r"(?ms)^#{2,}[ \t]*Parent[ \t]*\n(.*?)(?=^#{2,} |\Z)")
PART = re.compile(r"(?mi)^[ \t]*Part of #(\d+)")
NUM = re.compile(r"#(\d+)")
CROSS = re.compile(r"\b([\w.-]+/[\w.-]+)#(\d+)\b")
URL = re.compile(r"https?://\S+")
BULLETS = re.compile(r"^(?:\s*[-*+]\s*)+")


class Level:
    """One queued ticket after its native and body edges have been read."""

    def __init__(self, ticket):
        self.ticket = ticket
        self.number = ticket["number"]
        self.body_blockers = set()
        self.body_declared = False
        self.native = []
        self.blockers = set()
        self.open_blockers = []
        self.parent = None
        self.fanout = 0
        self.reasons = []

    @property
    def labels(self):
        return self.ticket["labels"]

    @property
    def comments(self):
        return self.ticket["comments"]


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


def declares_none(text):
    """True when a declaration's text is `None…`, list bullets aside."""
    return BULLETS.sub("", text).lower().startswith("none")


def scan(text):
    """The same-repo numbers a declaration names (URLs and cross-repo refs excluded)."""
    return {int(n) for n in NUM.findall(CROSS.sub(" ", URL.sub(" ", text)))}


def read_body(level):
    """Read the body's blocker and parent forms into `level`."""
    body = level.ticket["body"]
    top = TOP.search(body)
    section = SECTION.search(body)
    top_set = set() if top and declares_none(top.group(1)) else (scan(top.group(1)) if top else None)
    sec_set = (set() if section and declares_none(section.group(1))
               else (scan(section.group(1)) if section else None))
    level.body_declared = top is not None or section is not None
    level.body_blockers = (top_set or set()) | (sec_set or set())
    if top_set is not None and sec_set is not None and top_set != sec_set:
        level.reasons.append(
            f"Blocked by line {sorted(top_set)} and section {sorted(sec_set)} disagree "
            "(both counted)")

    part = PART.search(body)
    parent_section = PARENT_SECTION.search(body)
    sec_parent = NUM.search(parent_section.group(1)) if parent_section else None
    from_section = int(sec_parent.group(1)) if sec_parent else None
    from_part = int(part.group(1)) if part else None
    if from_section is not None and from_part is not None and from_section != from_part:
        level.reasons.append(f"## Parent says #{from_section} and Part of says #{from_part} "
                             "disagree (both counted); using ## Parent")
    level.parent = from_section if from_section is not None else from_part


def merge_native(level, native):
    """Union the native blockers into the body's, reporting a mismatch.

    Gitea's endpoint answers an empty list where there are no native edges; that is
    the hand-written style, not a disagreement with the body.
    """
    native_numbers = {ref["number"] for ref in native} if native is not None else set()
    level.native = native or []
    level.blockers = native_numbers | level.body_blockers
    if native_numbers and level.body_declared and native_numbers != level.body_blockers:
        level.reasons.append(
            f"native {sorted(native_numbers)} vs body {sorted(level.body_blockers)} "
            "(both counted)")


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
    by_number = {t["number"]: t for t in queue}

    levels = {}
    for ticket in sorted(queue, key=lambda t: t["number"]):
        level = Level(ticket)
        read_body(level)
        merge_native(level, tracker.dependencies(level.number))
        level.open_blockers = [b for b in sorted(level.blockers)
                               if _is_open(level, b, open_set)]
        levels[level.number] = level

    waiting = [lv for lv in levels.values() if a.waiting_label in lv.labels]
    hand = [lv for lv in levels.values() if lv.reasons]
    external = {lv.number: [b for b in lv.open_blockers if b not in by_number]
                for lv in levels.values()}
    _rank(levels)

    front = [lv for lv in levels.values()
             if not lv.ticket["assignees"]
             and a.waiting_label not in lv.labels
             and not lv.open_blockers]
    front.sort(key=_rank_key)

    return _text(a, queue, waiting, hand, front, external)


def _rank(levels):
    """Each ticket's fan-out: the queued tickets that transitively wait on it."""
    dependents = {number: set() for number in levels}
    for lv in levels.values():
        for blocker in lv.open_blockers:
            if blocker in dependents:
                dependents[blocker].add(lv.number)

    def reach(number, seen):
        for dependent in dependents[number]:
            if dependent not in seen:
                seen.add(dependent)
                reach(dependent, seen)
        return len(seen)

    for lv in levels.values():
        lv.fanout = reach(lv.number, set())


def _rank_key(lv):
    """Fan-out first, then parented before parentless, then parent and number."""
    return (-lv.fanout, lv.parent is None, lv.parent or 0, lv.number)


def _is_open(level, number, open_set):
    for ref in level.native:
        if ref["number"] == number and ref["state"] in ("open", "closed"):
            return ref["state"] == "open"
    return number in open_set


def _parent_text(parent):
    return f"#{parent:>4}" if parent is not None else f"{'-':>5}"


def _text(a, queue, waiting, hand, front, external):
    lines = []
    for lv in sorted(waiting, key=lambda x: x.number):
        lines.append(f"WAITING #{lv.number} ({a.waiting_label})")
    for lv in sorted(hand, key=lambda x: x.number):
        lines.append(f"READ BY HAND #{lv.number}: " + "; ".join(lv.reasons))
    ext = sorted((lv for lv in external if external[lv]), key=lambda x: x)
    lines.append(f"queue {len(queue)}  frontier {len(front)}  externally blocked {len(ext)}")
    for lv in front[:a.limit]:
        lines.append(f"#{lv.number:>5}  fan {lv.fanout:>3}  parent {_parent_text(lv.parent)}  "
                     f"c{lv.comments}  {lv.ticket['title'][:90]}")
    if ext:
        lines.append("externally blocked: " + ", ".join(
            f"#{lv}<-{'/'.join('#' + str(b) for b in external[lv])}" for lv in ext))
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
