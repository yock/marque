import json,re,sys,os
D=sys.argv[1]
q=json.load(open(D+'/raw/queue.json'))
REF=re.compile(r'(?:https?://gitea\.yock\.dev/yock/ping/issues/(\d+)|(?<![\w/])#(\d+))')
def refs(s): return [int(a or b) for a,b in REF.findall(s)]
out={}
for i in q:
    n=i['number']; b=i['body'] or ''
    lines=b.splitlines()
    L=set(); S=None; par=None; psec=None
    for ln in lines:
        m=re.match(r'^\s*\**Blocked by:?\**:?(.*)',ln,re.I)
        if m and not ln.lstrip().startswith('#'): L|=set(refs(m.group(1)))
    sec=None
    for ln in lines:
        h=re.match(r'^#{2,}\s*(.*)',ln)
        if h:
            t=h.group(1).strip().lower()
            sec='b' if t.startswith('blocked by') else 'p' if t.startswith('parent') else None
            if sec=='b' and S is None: S=set()
            if sec=='p' and psec is None: psec=[]
            continue
        if sec=='b': S|=set(refs(ln))
        if sec=='p' and ln.strip(): psec.append(ln)
    m=re.search(r'Part of #(\d+)',b)
    if m: par=int(m.group(1))
    if par is None and psec:
        r=refs(' '.join(psec)); par=r[0] if r else None
    out[n]=dict(L=sorted(L),S=None if S is None else sorted(S),parent=par,
        assignees=[a['login'] for a in (i.get('assignees') or [])],
        labels=[l['name'] for l in i['labels']],title=i['title'])
json.dump(out,open(D+'/raw/parsed.json','w'),indent=0)
allr=set()
for v in out.values(): allr|=set(v['L'])|set(v['S'] or [])
print(' '.join(map(str,sorted(allr))))
