import json, re, sys, os
d = sys.argv[1]
q = json.load(open(os.path.join(d, 'queue.json')))
REF = re.compile(r'(?:https?://gitea\.yock\.dev/yock/ping/issues/(\d+))|(?<![\w/])#(\d+)\b')
OTHERURL = re.compile(r'https?://\S+/issues/\d+')
def refs(s):
    out = []
    for m in REF.finditer(s):
        out.append(int(m.group(1) or m.group(2)))
    return out
def section(body, name):
    lines = body.split('\n'); res = None
    for i, l in enumerate(lines):
        if re.match(r'^##\s+' + name + r'\s*$', l.strip(), re.I):
            res = []
            for l2 in lines[i+1:]:
                if re.match(r'^#{1,2}\s', l2): break
                res.append(l2)
            return '\n'.join(res)
    return None
out = {}
for it in q:
    n = it['number']; b = (it['body'] or '').replace('\r', '')
    lines = [l for l in b.split('\n') if re.match(r'^\s*\**Blocked by:?\**:?', l, re.I) and not l.strip().startswith('#')]
    line_refs = sorted(set(r for l in lines for r in refs(l)))
    sec = section(b, 'Blocked by')
    sec_refs = None if sec is None else sorted(set(refs(sec)))
    sec_none = sec is not None and re.search(r'\bnone\b', sec, re.I) is not None
    par_lines = [l for l in b.split('\n') if re.search(r'\bPart of\b', l)]
    par_line = sorted(set(r for l in par_lines for r in refs(l)))
    ps = section(b, 'Parent')
    par_sec = None if ps is None else sorted(set(refs(ps)))
    foreign = [u for u in OTHERURL.findall(b) if 'yock/ping/issues' not in u]
    out[n] = dict(line=line_refs if lines else None, nlines=len(lines), sec=sec_refs, sec_none=sec_none,
                  sec_text=(sec or '').strip()[:300], par_line=par_line, par_sec=par_sec,
                  par_text=(ps or '').strip()[:200], foreign=foreign[:5],
                  assignees=[a['login'] for a in (it.get('assignees') or [])],
                  labels=[l['name'] for l in it['labels']], title=it['title'])
json.dump(out, open(os.path.join(d, 'parsed.json'), 'w'), indent=1)
