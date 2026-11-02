#!/usr/bin/env python3
"""One-time migration: merge existing artwork into person records. Safe to rerun."""
from pathlib import Path
import yaml,re,shutil
root=Path(__file__).resolve().parents[1]
def load(p):
 s=p.read_text();m=re.match(r'\A---\s*\n(.*?)\n---\s*(?:\n|\Z)',s,re.S)
 if not m:raise ValueError(f'Invalid frontmatter: {p}')
 d=yaml.safe_load(m.group(1)) or {}; body=s[m.end():].strip()
 if body and not d.get('body'):d['body']=body
 return d
def save(p,d):
 p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text('---\n'+yaml.safe_dump(d,sort_keys=False,allow_unicode=True,width=1000).rstrip()+'\n---\n')
def slug(s):return re.sub(r'[^a-z0-9]+','-',str(s).lower()).strip('-')
people=root/'content/people';legacy=root/'content/artwork';backup=root/'content/artwork-legacy'; count=0
for f in sorted(legacy.glob('*.md')):
 a=load(f);key=slug(a.get('person') or f.stem);person_file=people/(key+'.md')
 p=load(person_file) if person_file.exists() else {'name':a.get('name',key),'body':''}
 if not isinstance(p.get('artworks'),list):p['artworks']=[]
 entry={k:v for k,v in a.items() if k in {'title','image','year','medium','dimensions','date','published','featured','display_order','summary'}}
 if not any(x.get('image')==entry.get('image') and x.get('title')==entry.get('title') for x in p['artworks']):
  p['artworks'].append(entry)
  p['artworks'].sort(key=lambda x:(int(x.get('display_order') or 100),str(x.get('title') or '')))
  save(person_file,p)
 backup.mkdir(parents=True,exist_ok=True)
 shutil.move(str(f),str(backup/f.name));count+=1
print(f'Migrated {count} legacy artwork records; originals backed up in content/artwork-legacy/')
