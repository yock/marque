import json, re, sys, glob, os
S = sys.argv[1]
raw = os.path.join(S, "raw")
issue = json.load(open(os.path.join(raw, "issue.json")))
comments = []
for f in sorted(glob.glob(os.path.join(raw, "c-*.json")), key=lambda p: int(re.search(r"c-(\d+)", p).group(1))):
    comments += json.load(open(f))

def slug(h):
    s = re.sub(r"[^a-z0-9]+", "-", h.lower()).strip("-")
    return s[:40].strip("-") or "x"

body = issue["body"]
lines = body.splitlines(keepends=True)
parts, cur, fence = [], [], None
for ln in lines:
    st = ln.lstrip()
    m = re.match(r"(`{3,}|~{3,})", st)
    if m:
        if fence is None: fence = m.group(1)[0] * len(m.group(1))
        elif st.startswith(fence): fence = None
    if fence is None and not m and re.match(r"#{2,3} ", ln):
        parts.append(cur); cur = []
    cur.append(ln)
parts.append(cur)

files = []
for i, p in enumerate(parts):
    text = "".join(p)
    if i == 0:
        name = "body-00-preamble.md"
    else:
        name = f"body-{i:02d}-{slug(p[0].lstrip('#').strip())}.md"
    files.append((name, text))
for i, c in enumerate(comments, 1):
    files.append((f"c{i:02d}.md", c["body"]))

def first(t):
    ls = [l.strip() for l in t.splitlines() if l.strip()]
    for l in ls:
        if l.startswith("#"): return l
    return ls[0] if ls else "(blank)"

idx = [f"#{issue['number']} {issue['title']}"]
for name, text in files:
    with open(os.path.join(S, name), "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    idx.append(f"{name}\t{len(text.encode())}\t{first(text)[:100]}")
open(os.path.join(S, "index.txt"), "w").write("\n".join(idx) + "\n")
print(len(parts), len(comments))
