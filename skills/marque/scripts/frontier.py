#!/usr/bin/env python3
"""frontier.py [--config PATH] [--json]: the unblocked, unclaimed tickets in the ready queue, ranked.

The ticket format is the wayfinder skill's, with the tracker specifics in the target
repo's docs/agents/issue-tracker.md and triage-labels.md; that pair is this script's
contract. It reads:
  - `Part of #<spec>`              the parent spec (ranking only);
  - `Blocked by: #a, #b`           the top line, and
  - a `## Blocked by` section      listing `#n` items. Both forms are read and unioned.
  - labels: the ready label (the queue), the blocking label (waiting on the user);
  - assignees: a claimed ticket is not on the frontier.

A ticket is on the frontier when it is ready, unclaimed, not labelled blocking, and
every blocker it names is closed. Rank: most queued tickets it unblocks (transitively),
then spec number, then issue number.

Anything the script can't read with confidence is listed under READ BY HAND and never
silently decided: a top line and a section that disagree, no `Part of` line. A ticket
with no blocker declaration at all is listed once as a note (it may truly have none).

With a ledger (state.dir/ledger.tsv, optional), a frontier ticket whose ledger row
carries state.asked_marker is flagged ANSWERED: the user has returned it; read its
newest comments before briefing. Writes state.dir/logs/queue.json.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from symphony_lib import Project  # noqa: E402

TOP = re.compile(r"(?mi)^\s*Blocked by:(.*)$")
SECTION = re.compile(r"(?ms)^##+\s*Blocked by\s*\n(.*?)(?=^##+ |\Z)")
PART = re.compile(r"(?mi)^\s*Part of #(\d+)")
NUM = re.compile(r"#(\d+)")


def parse(it):
    b = it["body"]
    top = TOP.search(b)
    sec = SECTION.search(b)
    top_set = set(map(int, NUM.findall(top.group(1)))) if top else None
    sec_set = set(map(int, NUM.findall(sec.group(1)))) if sec else None
    it["blockers"] = sorted((top_set or set()) | (sec_set or set()))
    it["hand"] = []
    it["notes"] = []
    if top_set is not None and sec_set is not None and top_set != sec_set:
        it["hand"].append(f"Blocked by line {sorted(top_set)} and section {sorted(sec_set)} disagree "
                          "(both counted)")
    if top_set is None and sec_set is None:
        it["notes"].append("no blocker declaration")
    elif top_set is None:
        it["hand"].append(f"no `Blocked by:` line; section lists {sorted(sec_set)}")
    p = PART.search(b)
    it["spec"] = int(p.group(1)) if p else 0
    if not p:
        it["hand"].append("no `Part of #` line")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config")
    ap.add_argument("--json", action="store_true", help="print the ranked frontier as JSON")
    ap.add_argument("--limit", type=int, default=30, help="frontier lines to print (default 30)")
    a = ap.parse_args()
    pr = Project(a.config)

    queue = pr.open_issues(pr.ready)
    open_set = {i["number"] for i in pr.open_issues()}
    by_num = {i["number"]: i for i in queue}
    for it in queue:
        parse(it)
        it["open_blockers"] = [x for x in it["blockers"] if x in open_set]
        it["external"] = [x for x in it["open_blockers"] if x not in by_num]

    dependents = {k: set() for k in by_num}
    for it in queue:
        for x in it["open_blockers"]:
            if x in dependents:
                dependents[x].add(it["number"])

    def reach(k, seen):
        for d in dependents.get(k, ()):
            if d not in seen:
                seen.add(d)
                reach(d, seen)
        return seen

    for it in queue:
        it["fanout"] = len(reach(it["number"], set()))

    asked = set()
    if pr.ledger.is_file():
        for line in pr.ledger.read_text().splitlines():
            f = line.split("\t")
            if f and f[0].isdigit() and any(pr.asked_marker in x for x in f[1:]):
                asked.add(int(f[0]))

    waiting = [i for i in queue if pr.blocking in i["labels"]]
    front = [i for i in queue
             if not i["open_blockers"] and not i["assignees"] and pr.blocking not in i["labels"]]
    front.sort(key=lambda i: (-i["fanout"], i["spec"], i["number"]))
    ext = [i for i in queue if i["external"]]

    (pr.state / "logs").mkdir(parents=True, exist_ok=True)
    (pr.state / "logs/queue.json").write_text(json.dumps(queue, indent=1))

    if a.json:
        print(json.dumps([{k: i[k] for k in ("number", "title", "fanout", "spec", "comments", "hand")}
                          for i in front], indent=1))
        return

    for i in front:
        if i["number"] in asked:
            print(f"ANSWERED #{i['number']}: back from the user; read its newest comments before briefing")
    for i in waiting:
        print(f"WAITING ON THE USER #{i['number']} ({pr.blocking})")
    hand = [i for i in queue if i["hand"]]
    for i in hand:
        print(f"READ BY HAND #{i['number']}: " + "; ".join(i["hand"]))
    print(f"queue {len(queue)}  frontier {len(front)}  externally blocked {len(ext)}")
    for i in front[:a.limit]:
        note = f"  [{'; '.join(i['notes'])}]" if i["notes"] else ""
        print(f"#{i['number']:>5}  fan {i['fanout']:>3}  spec #{i['spec']:>4}  c{i['comments']}  "
              f"{i['title'][:90]}{note}")
    if ext:
        print("externally blocked:", ", ".join(
            f"#{i['number']}<-{'/'.join('#' + str(x) for x in i['external'])}" for i in ext))


if __name__ == "__main__":
    main()
