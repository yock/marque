import json,sys
D=sys.argv[1]
P=json.load(open(D+'/raw/parsed.json')); P={int(k):v for k,v in P.items()}
st={int(l.split()[0]):l.split()[1] for l in open(D+'/raw/states.txt')}
WAIT={'blocking','needs-info'}
for n,v in P.items():
    v['blk']=sorted(set(v['L'])|set(v['S'] or []))
    v['open']=[b for b in v['blk'] if st.get(b)!='closed']
    v['claimed']=bool(v['assignees']); v['waiting']=bool(WAIT&set(v['labels']))
    v['front']=not v['claimed'] and not v['waiting'] and not v['open']
# fan-out: queued tickets reachable via open-blocker edges (reverse)
rev={}
for n,v in P.items():
    for b in v['open']: rev.setdefault(b,set()).add(n)
def fan(n):
    seen=set(); st_=[n]
    while st_:
        x=st_.pop()
        for y in rev.get(x,()):
            if y not in seen: seen.add(y); st_.append(y)
    return len(seen)
F=[(n,fan(n),v) for n,v in P.items() if v['front']]
F.sort(key=lambda t:(-t[1], t[2]['parent'] if t[2]['parent'] is not None else 10**9, t[0]))
o=['# Frontier\n']
for n,f,v in F: o.append(f"#{n} fan {f} parent {('#'+str(v['parent'])) if v['parent'] else '(none)'} {v['title']}")
o.append('\n# Blocked\n')
for n,v in sorted(P.items()):
    if v['open'] and not v['claimed'] and not v['waiting']: o.append(f"#{n} blocked by "+', '.join('#%d'%b for b in v['open']))
o.append('\n# Claimed\n')
for n,v in sorted(P.items()):
    if v['claimed']: o.append(f"#{n} ({','.join(v['assignees'])}) open blockers: {', '.join('#%d'%b for b in v['open']) or 'none'}")
o.append('\n# Waiting\n'); o+= [f"#{n}" for n,v in sorted(P.items()) if v['waiting']]
o.append('\n# Disagreements / missing parent\n')
for n,v in sorted(P.items()):
    if v['S'] is not None and v['L'] and set(v['L'])!=set(v['S']): o.append(f"#{n} DISAGREE line={v['L']} sec={v['S']}")
    if v['parent'] is None: o.append(f"#{n} NO PARENT")
counts=dict(queue=len(P),frontier=len(F),blocked=sum(1 for v in P.values() if v['open'] and not v['claimed'] and not v['waiting']),claimed=sum(v['claimed'] for v in P.values()),waiting=sum(v['waiting'] for v in P.values()))
o.append('\n'+json.dumps(counts))
print('\n'.join(o))
