#!/usr/bin/env python3
"""PROTOTYPE oracle: ground-truth frontier for a Gitea repo's ready queue.
Reads native dependencies AND body forms (Blocked by: line, ## Blocked by section),
parent from `Part of #n` or a `## Parent` section. Writes snapshot JSON. Throwaway."""
import json, re, subprocess, sys, time

REPO, LOGIN, OUT = sys.argv[1], sys.argv[2], sys.argv[3]

def api(path):
    r = subprocess.run(["tea", "api", "--login", LOGIN, path], capture_output=True, text=True, check=True)
    return json.loads(r.stdout or "null")

def all_open(label=None):
    out, page = [], 1
    while True:
        q = f"repos/{REPO}/issues?state=open&type=issues&limit=50&page={page}" + (f"&labels={label}" if label else "")
        b = api(q) or []
        out += b
        if len(b) < 50:
            return out
        page += 1

t0 = time.time()
ready = all_open("ready-for-agent")
open_set = {i["number"] for i in all_open()}
TOP = re.compile(r"(?mi)^\s*Blocked by:(.*)$")
SEC = re.compile(r"(?ms)^##+\s*Blocked by\s*\n(.*?)(?=^##+ |\Z)")
PARENT_SEC = re.compile(r"(?ms)^##+\s*Parent\s*\n(.*?)(?=^##+ |\Z)")
PART = re.compile(r"(?mi)^\s*Part of #(\d+)")
# same-repo refs only: bare #n, or a URL into this repo's issues
REF = re.compile(r"(?<![\w/])#(\d+)|https?://[^\s)]*/" + re.escape(REPO) + r"/issues/(\d+)")

def refs(text):
    return {int(a or b) for a, b in REF.findall(text)}

rows = []
for i in ready:
    n, body = i["number"], i.get("body") or ""
    deps = api(f"repos/{REPO}/issues/{n}/dependencies") or []
    native = {d["number"] for d in deps if d.get("repository", {}).get("full_name", REPO) == REPO}
    native_open = {d["number"] for d in deps if d["state"] == "open"}
    top = TOP.search(body); sec = SEC.search(body)
    body_b = (refs(top.group(1)) if top else set()) | (refs(sec.group(1)) if sec else set())
    p = PART.search(body); ps = PARENT_SEC.search(body)
    parent = int(p.group(1)) if p else (min(refs(ps.group(1))) if ps and refs(ps.group(1)) else None)
    blockers = native | body_b
    open_b = sorted((native_open) | {x for x in body_b if x in open_set})
    rows.append(dict(number=n, title=i["title"], labels=[l["name"] for l in i["labels"]],
                     assignees=[a["login"] for a in i.get("assignees") or []],
                     native=sorted(native), body=sorted(body_b), parent=parent,
                     open_blockers=open_b, native_only=sorted(native - body_b), body_only=sorted(body_b - native)))

ready_nums = {r["number"] for r in rows}
dependents = {r["number"]: set() for r in rows}
for r in rows:
    for b in r["open_blockers"]:
        if b in dependents:
            dependents[b].add(r["number"])
def reach(k, seen):
    for d in dependents.get(k, ()):
        if d not in seen:
            seen.add(d); reach(d, seen)
    return seen
for r in rows:
    r["fanout"] = len(reach(r["number"], set()))
front = [r for r in rows if not r["open_blockers"] and not r["assignees"] and "blocking" not in r["labels"]]
front.sort(key=lambda r: (-r["fanout"], r["parent"] or 0, r["number"]))
json.dump(dict(taken=time.strftime("%Y-%m-%dT%H:%M:%S"), secs=round(time.time() - t0, 1), queue=rows,
               frontier=[r["number"] for r in front]), open(OUT, "w"), indent=1)
print(f"queue {len(rows)} frontier {len(front)}: " + " ".join(f"#{r['number']}(fan {r['fanout']})" for r in front))
print("native-only blockers on:", [r["number"] for r in rows if r["native_only"]])
print("body-only blockers on:", [r["number"] for r in rows if r["body_only"]])
print("no parent:", [r["number"] for r in rows if r["parent"] is None])
