import json, sys
S = sys.argv[1]
ex = {int(k): v for k, v in json.load(open(f"{S}/extract.json")).items()}
state = {}
for l in open(f"{S}/refstate.tsv"):
    f = l.rstrip("\n").split("\t"); state[int(f[0])] = f[1]
WAIT = {"blocking", "needs-info"}
queue = set(ex)
blockers = {n: sorted(set(x for x in (v["line_refs"] or []) + (v["sec_refs"] or []) if isinstance(x, int))) for n, v in ex.items()}
openb = {n: [b for b in bs if state.get(b, "open") != "closed"] for n, bs in blockers.items()}
# reverse edges: b -> tickets in queue that list b as an open blocker
rev = {}
for n, bs in openb.items():
    for b in bs: rev.setdefault(b, set()).add(n)
def fan(n):
    seen, st = set(), [n]
    while st:
        x = st.pop()
        for y in rev.get(x, ()):
            if y in queue and y not in seen: seen.add(y); st.append(y)
    seen.discard(n); return len(seen)
parent = {n: v["partof"] for n, v in ex.items()}
cls = {}
for n, v in ex.items():
    if v["assignees"]: cls[n] = ("claimed", ",".join(v["assignees"]))
    elif WAIT & set(v["labels"]): cls[n] = ("waiting", ",".join(WAIT & set(v["labels"])))
    elif openb[n]: cls[n] = ("blocked", " ".join(f"#{b}" for b in openb[n]))
    else: cls[n] = ("frontier", "")
# also note claimed tickets that are also blocked
front = [n for n in cls if cls[n][0] == "frontier"]
INF = 10**9
front.sort(key=lambda n: (-fan(n), parent[n] if parent[n] else INF, n))
out = {"frontier": [dict(n=n, fan=fan(n), parent=parent[n], title=ex[n]["title"]) for n in front],
       "cls": {n: [cls[n][0], cls[n][1], " ".join(f"#{b}" for b in openb[n])] for n in sorted(cls)},
       "fanall": {n: fan(n) for n in sorted(queue)}}
json.dump(out, open(f"{S}/classified.json", "w"), indent=1)
for r in out["frontier"]: print(f"#{r['n']} fan {r['fan']} parent #{r['parent']} {r['title']}")
from collections import Counter
print(Counter(c[0] for c in cls.values()))
for n in sorted(cls):
    if cls[n][0] in ("claimed", "waiting"): print(n, cls[n], "open blockers:", openb[n])
