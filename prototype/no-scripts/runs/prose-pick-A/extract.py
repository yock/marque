import json, re, sys
S = sys.argv[1]
q = json.load(open(f"{S}/raw/queue.json"))
REF = re.compile(r"(?<![\w/])#(\d+)\b|https://gitea\.yock\.dev/yock/ping/issues/(\d+)(?!#issuecomment)")
REF_ANY = re.compile(r"https://gitea\.yock\.dev/([^/\s]+/[^/\s]+)/issues/(\d+)")

def refs(text):
    out = []
    for m in re.finditer(r"#(\d+)|https://gitea\.yock\.dev/([^/\s)]+/[^/\s)]+)/issues/(\d+)", text):
        if m.group(1):
            # skip the #NNN that is part of a URL fragment like #issuecomment-1
            out.append(int(m.group(1)))
        elif m.group(2) == "yock/ping":
            out.append(int(m.group(3)))
        else:
            out.append(("foreign", m.group(2), int(m.group(3))))
    return out

res = {}
for it in q:
    n = it["number"]; body = it["body"] or ""
    lines = body.splitlines()
    line_bb = None
    for l in lines:
        m = re.match(r"\s*\**Blocked by:?\**:?\s*(.*)", l, re.I)
        if m and not l.lstrip().startswith("#"):
            line_bb = m.group(1); break
    sec_bb = None; sec_parent = None
    cur = None; buf = {}
    for l in lines:
        h = re.match(r"^##\s+(.*?)\s*$", l)
        if h:
            cur = h.group(1).strip().lower(); buf[cur] = []; continue
        if cur is not None: buf[cur].append(l)
    if "blocked by" in buf: sec_bb = "\n".join(buf["blocked by"]).strip()
    if "parent" in buf: sec_parent = "\n".join(buf["parent"]).strip()
    po = re.search(r"Part of #(\d+)", body)
    res[n] = dict(
        title=it["title"],
        assignees=[a["login"] for a in (it.get("assignees") or [])],
        labels=[l["name"] for l in it["labels"]],
        line_raw=line_bb, sec_raw=sec_bb,
        line_refs=refs(line_bb) if line_bb is not None else None,
        sec_refs=(refs(sec_bb) if sec_bb is not None else None),
        partof=int(po.group(1)) if po else None,
        sec_parent=sec_parent,
        sec_parent_refs=refs(sec_parent) if sec_parent else None,
    )
json.dump(res, open(f"{S}/extract.json", "w"), indent=1)
