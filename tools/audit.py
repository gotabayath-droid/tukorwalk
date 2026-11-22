#!/usr/bin/env python3
"""Link/asset audit: every internal href/src must resolve to a file or folder/index.html. Also checks ids, JSON-LD, titles."""
import os, re, sys, json, urllib.parse
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT)
bad=0; pages=[]
for dp,dn,fn in os.walk('.'):
    dn[:]=[d for d in dn if d not in('.git','node_modules')]
    pages+= [os.path.join(dp,f)[2:] for f in fn if f.endswith('.html')]
def resolve(page,ref):
    ref=ref.split('#')[0].split('?')[0]
    if not ref: return True
    ref=urllib.parse.unquote(ref)
    if ref.startswith('/'): t=ref[1:]
    else:
        parts=(os.path.dirname(page).split('/') if os.path.dirname(page) else [])
        for seg in ref.split('/'):
            if seg=='..':
                if not parts: return False   # escapes site root
                parts.pop()
            elif seg not in('','.'): parts.append(seg)
        t='/'.join(parts) + ('/' if ref.endswith('/') else '')
    if t=='' or t.endswith('/'): return os.path.isfile(os.path.join(t,'index.html'))
    return os.path.isfile(t) or os.path.isfile(os.path.join(t,'index.html'))
for p in sorted(pages):
    h=open(p,encoding='utf-8').read()
    for m in re.finditer(r'(?:href|src)="([^"]+)"',h):
        r=m.group(1)
        if re.match(r'(https?:|mailto:|tel:|data:|javascript:|#)',r): continue
        if not resolve(p,r): print('BROKEN',p,r); bad+=1
    ids=re.findall(r'\sid="([^"]+)"',h); d={i for i in ids if ids.count(i)>1}
    if d: print('DUP IDS',p,sorted(d)[:5]); bad+=1
    for j in re.findall(r'<script type="application/ld\+json">(.*?)</script>',h,re.S):
        try: json.loads(j)
        except Exception as e: print('BAD JSON-LD',p,e); bad+=1
    t=re.search(r'<title>(.*?)</title>',h,re.S); dsc=re.search(r'name="description" content="(.*?)"',h)
    if not t or not dsc: print('MISSING title/desc',p); bad+=1
    if len(re.findall(r'<h1[\s>]',h))!=1: print('H1 count',p,len(re.findall(r'<h1[\s>]',h)))
    if '<link rel="canonical"' not in h: print('NO CANONICAL',p); bad+=1
print('pages',len(pages),'problems',bad)
