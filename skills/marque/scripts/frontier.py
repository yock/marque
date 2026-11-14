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
and tickets with questions but no waiting label. A ticket it cannot parse is never
silently treated as unblocked: it stays off the frontier. Everything listed under
READ BY HAND still appears on the frontier when it is otherwise eligible.

Rank: how many queued tickets it unblocks (transitively), then tickets with a
parent before those without, then parent number, then issue number.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _tracker import BACKENDS, TrackerError, backend  # noqa: E402

TOP = re.compile(r"(?mi)^[ \t]*Blocked by:(.*)$")
SECTION = re.compile(r"(?ms)^#{2,}[ \t]*Blocked by[ \t]*\n(.*?)(?=^#{2,} |\Z)")
PARENT_SECTION = re.compile(r"(?ms)^#{2,}[ \t]*Parent[ \t]*\n(.*?)(?=^#{2,} |\Z)")
PART = re.compile(r"(?mi)^[ \t]*Part of #(\d+)")
NUM = re.compile(r"#(\d+)")
CROSS = re.compile(r"\b([\w.-]+/[\w.-]+)#(\d+)\b")
URL = re.compile(r"https?://\S+")
BULLETS = re.compile(r"^(?:\s*[-*+]\s*)+")
QUESTION = re.compile(r"(?mi)^#{1,6}\s*(open\s+)?questions?\b")
MAP_LABEL = "wayfinder:map"


class TicketReading:
    """One queued ticket after its native and body edges have been read."""

    def __init__(self, ticket):
        self.ticket = ticket
        self.number = ticket["number"]
        self.body_blockers = set()
        self.body_unparseable = []
        self.body_declared = False
        self.native = []
        self.blockers = set()        # same-repo numbers, native and body unioned
        self.unparseable = []        # raw references this repo cannot resolve
        self.missing = []            # same-repo numbers the tracker does not have
        self.open_blockers = []      # numbers, ascending, open or missing
        self.parent = None
        self.fanout = 0
        self.comment_bodies = []
        self.reasons = []

    @property
    def labels(self):
        return self.ticket["labels"]

    @property
    def comments(self):
        return self.ticket["comments"]


def parse_args(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--backend", required=True, choices=BACKENDS)
    ap.add_argument("--repo", required=True, help="OWNER/NAME")
    ap.add_argument("--login",
                    help="tea login name / gh user / name of the env var holding the "
                         "GitLab token")
    ap.add_argument("--host", help="the tracker host, for gh and glab (gitea ignores it)")
    ap.add_argument("--label", default="ready-for-agent", help="the queue's label")
    ap.add_argument("--waiting-label", default="needs-info",
                    help="the label that means the user has been asked something")
    ap.add_argument("--json", action="store_true", help="print the frontier as JSON")
    ap.add_argument("--limit", type=int, default=30, help="frontier lines to print (default 30)")
    return ap.parse_args(argv)


def declares_none(text):
    """True when a declaration's text is `None…`, list bullets aside."""
    return BULLETS.sub("", text).strip().lower().startswith("none")


def scan(text):
    """The same-repo numbers and the unparseable references a declaration names."""
    urls = [m.group(0) for m in URL.finditer(text)]
    text = URL.sub(" ", text)
    raws = [m.group(0) for m in CROSS.finditer(text)] + urls
    return {int(n) for n in NUM.findall(CROSS.sub(" ", text))}, raws


def declaration(match):
    """A line or section's (numbers, raw references); (None, []) when absent."""
    if match is None:
        return None, []
    if declares_none(match.group(1)):
        return set(), []
    return scan(match.group(1))


def read_body(level):
    """Read the body's blocker and parent forms into `level`."""
    body = level.ticket["body"]
    top_numbers, top_raws = declaration(TOP.search(body))
    sec_numbers, sec_raws = declaration(SECTION.search(body))
    level.body_declared = top_numbers is not None or sec_numbers is not None
    level.body_blockers = (top_numbers or set()) | (sec_numbers or set())
    level.body_unparseable = top_raws + sec_raws
    if (top_numbers is not None and sec_numbers is not None
            and (top_numbers, top_raws) != (sec_numbers, sec_raws)):
        level.reasons.append(
            f"Blocked by line {sorted(top_numbers)} and section {sorted(sec_numbers)} disagree "
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


def merge_native(level, repo):
    """Union the native blockers into the body's, reporting a mismatch.

    Gitea's endpoint answers an empty list where there are no native edges; that is
    the hand-written style, not a disagreement with what the body declares.
    """
    native_numbers, native_raws = set(), []
    for ref in level.native:
        if ref["repo"] == repo:
            native_numbers.add(ref["number"])
        else:
            native_raws.append(ref["raw"])
    level.blockers = native_numbers | level.body_blockers
    level.unparseable = level.body_unparseable + native_raws
    if native_numbers and level.body_declared and native_numbers != level.body_blockers:
        level.reasons.append(
            f"native {sorted(native_numbers)} vs body {sorted(level.body_blockers)} "
            "(both counted)")


class Resolution:
    """The one place a ticket the queue did not list is fetched, cached by number."""

    def __init__(self, tracker, open_set, by_number, repo):
        self.tracker = tracker
        self.open_set = open_set
        self.by_number = by_number
        self.repo = repo
        self.fetched = {}

    def fetch(self, number):
        if number not in self.fetched:
            self.fetched[number] = self.tracker.issue(number)
        return self.fetched[number]

    def state(self, level, number):
        """`open`, `closed`, or `missing` for one of `level`'s blockers."""
        for ref in level.native:
            if (ref["number"] == number and ref["repo"] == self.repo
                    and ref["state"] in ("open", "closed")):
                return ref["state"]
        if number in self.open_set:
            return "open"
        issue = self.fetch(number)
        return "missing" if issue is None else issue["state"]

    def labels(self, number):
        if number in self.by_number:
            return self.by_number[number]["labels"]
        issue = self.fetch(number)
        return issue["labels"] if issue is not None else []


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
    tracker = backend(a.backend, a.repo, a.login, a.host)
    queue = tracker.open_issues(a.label)
    open_set = {i["number"] for i in tracker.open_issues()}
    by_number = {t["number"]: t for t in queue}

    levels = {}
    for ticket in sorted(queue, key=lambda t: t["number"]):
        level = TicketReading(ticket)
        level.native = tracker.dependencies(level.number) or []
        read_body(level)
        merge_native(level, a.repo)
        native_parent = tracker.native_parent(ticket)
        if native_parent is not None:
            level.parent = native_parent["number"]
        if level.comments:
            level.comment_bodies = tracker.comments(level.number)
        levels[level.number] = level

    resolution = Resolution(tracker, open_set, by_number, a.repo)
    find_open_blockers(levels, resolution)
    add_reasons(a, levels, resolution)
    _rank(levels)

    waiting = [lv for lv in levels.values() if a.waiting_label in lv.labels]
    hand = [lv for lv in levels.values() if lv.reasons]
    external = {lv.number: [b for b in lv.open_blockers if b not in by_number]
                for lv in levels.values()}
    front = [lv for lv in levels.values()
             if not lv.ticket["assignees"]
             and a.waiting_label not in lv.labels
             and not lv.open_blockers
             and not lv.unparseable]
    front.sort(key=_rank_key)

    if a.json:
        return json.dumps([{"number": lv.number, "title": lv.ticket["title"],
                            "fanout": lv.fanout, "parent": lv.parent,
                            "comments": lv.comments, "hand": lv.reasons}
                           for lv in front], indent=1) + "\n"
    return _text(a, queue, waiting, hand, front, external)


def find_open_blockers(levels, resolution):
    """Settle every blocker's state, asking the tracker once about any it can't tell."""
    for lv in levels.values():
        for number in sorted(lv.blockers):
            state = resolution.state(lv, number)
            if state == "open":
                lv.open_blockers.append(number)
            elif state == "missing":
                lv.missing.append(number)
                lv.open_blockers.append(number)


def add_reasons(a, levels, resolution):
    """Everything the orchestrator should read by hand, in a stable order."""
    parents = {lv.parent for lv in levels.values() if lv.parent is not None}
    for lv in levels.values():
        for raw in lv.unparseable:
            lv.reasons.append(f"unparseable reference {raw}, treated as open")
        for number in lv.missing:
            lv.reasons.append(f"reference #{number} not found, treated as open")
        if a.waiting_label not in lv.labels and has_questions(lv):
            lv.reasons.append(f"has questions but no {a.waiting_label} label")
        for number in lv.open_blockers:
            labels = resolution.labels(number)
            if MAP_LABEL in labels or number in parents:
                lv.reasons.append(f"blocked by #{number}, a map or spec, not a ticket")


def has_questions(level):
    """A questions heading in the body, or in the newest comment."""
    if QUESTION.search(level.ticket["body"]):
        return True
    newest = level.comment_bodies[-1]["body"] if level.comment_bodies else ""
    return bool(QUESTION.search(newest))


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


def _parent_text(parent):
    return f"#{parent:>4}" if parent is not None else f"{'-':>5}"


def _text(a, queue, waiting, hand, front, external):
    lines = []
    for lv in sorted(waiting, key=lambda x: x.number):
        lines.append(f"WAITING #{lv.number} ({a.waiting_label})")
    for lv in sorted(hand, key=lambda x: x.number):
        lines.append(f"READ BY HAND #{lv.number}: " + "; ".join(lv.reasons))
    ext = sorted((number for number in external if external[number]))
    lines.append(f"queue {len(queue)}  frontier {len(front)}  externally blocked {len(ext)}")
    for lv in front[:a.limit]:
        lines.append(f"#{lv.number:>5}  fan {lv.fanout:>3}  parent {_parent_text(lv.parent)}  "
                     f"c{lv.comments}  {lv.ticket['title'][:90]}")
    if ext:
        lines.append("externally blocked: " + ", ".join(
            f"#{number}<-{'/'.join('#' + str(b) for b in external[number])}" for number in ext))
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
