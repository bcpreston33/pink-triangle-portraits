from pathlib import Path
from datetime import date, datetime
from html import escape
from urllib.parse import quote
import re, shutil
import yaml
try:
    import markdown
    def markdown_html(text): return markdown.markdown(text, extensions=['extra','sane_lists'])
except ImportError:
    import mistune
    def markdown_html(text): return mistune.html(text)

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'dist'
if OUT.exists(): shutil.rmtree(OUT)
OUT.mkdir()
shutil.copytree(ROOT/'assets', OUT/'assets')

def load(path):
    raw=path.read_text(encoding='utf-8')
    match=re.match(r'\A---\s*\n(.*?)\n---\s*(?:\n|\Z)',raw,re.S)
    if not match: raise ValueError(f'Missing YAML frontmatter: {path}')
    data=yaml.safe_load(match.group(1)) or {}
    body=raw[match.end():].strip()
    if body and not data.get('body'): data['body']=body
    return data

def render_md(value):
    return markdown_html(str(value or ''))

def attr(value): return escape(str(value or ''),quote=True)
def slug(value): return re.sub(r'[^a-z0-9]+','-',str(value).lower()).strip('-')
def date_key(v):
    if isinstance(v,(date,datetime)): return v.isoformat()
    return str(v or '')
def img(path,alt='',cls=''):
    if not path:return ''
    return f'<img src="{attr(path)}" alt="{attr(alt)}" class="{attr(cls)}" loading="lazy">'

def page(title,active,content,desc=''):
    nav=[('Home','/'),('The Project','/the-project/'),('The History','/the-history/'),('The Portraits','/portraits/'),('Exhibitions','/exhibitions/'),('Shop','/shop/'),('Contact','/contact/')]
    links=''.join(f'<a href="{url}" class="{"active" if active==label else ""}">{label}</a>' for label,url in nav)
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="{attr(desc or 'Pink Triangle Portraits, an art and historical remembrance project by Bry Sharland')}"><title>{escape(title)} | Pink Triangle Portraits</title><link rel="stylesheet" href="/assets/site.css"></head><body><header class="site-header"><div class="nav-wrap"><a class="brand" href="/" aria-label="Pink Triangle Portraits home"><span class="brand-mark" aria-hidden="true"></span><span>PINK<br>TRIANGLE<br>PORTRAITS</span></a><button class="menu-toggle" aria-controls="main-nav" aria-expanded="false" aria-label="Open menu">☰</button><nav id="main-nav" aria-label="Main navigation">{links}</nav></div></header><main>{content}</main><footer><div class="container foot-grid"><div><b>PINK TRIANGLE PORTRAITS</b><p>Giving color and dignity to those who had it stripped away.</p></div><div><a href="https://www.pinktriangleportraits.com/">Current project website</a><p>Artwork and research by Bry Sharland</p></div></div></footer><script src="/assets/site.js" defer></script></body></html>'''

def write(route,html):
    target=OUT/route/'index.html' if route else OUT/'index.html'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(html,encoding='utf-8')

def heading(kicker,title,subtitle='',hero=''):
    bg=f' style="--hero-image:url(\'{attr(hero)}\')"' if hero else ''
    return f'<section class="interior-hero"{bg}><div class="container interior-inner"><div class="eyebrow">{escape(kicker)}</div><h1>{escape(title)}</h1><p>{escape(subtitle)}</p></div><div class="paint-swipe" aria-hidden="true"></div></section>'

portraits=[]
for f in (ROOT/'content/portraits').glob('*.md'):
    p=load(f)
    if p.get('published') is False: continue
    p['_slug']=slug(f.stem)
    p['_date']=date_key(p.get('date'))
    portraits.append(p)
portraits.sort(key=lambda p:(p['_date'],p.get('name','')),reverse=True)
# The newest featured-flag portrait wins; otherwise newest published portrait.
featured=next((p for p in portraits if p.get('featured')),portraits[0] if portraits else None)

def portrait_card(p):
    name=escape(str(p.get('name','Untitled')))
    return f'<a class="portrait-card" href="/portraits/{p["_slug"]}/"><span class="portrait-image">{img(p.get("image"),name)}</span><span class="portrait-name">{name}<span aria-hidden="true"> ↗</span></span></a>'

cards=''.join(portrait_card(p) for p in portraits)
hero_cards=''.join(img(p.get('image'),p.get('name','')) for p in portraits[:6])
if featured:
    f=featured
    featured_markup=f'<div class="feature-art">{img(f.get("image"),f.get("name",""))}</div><div class="feature-copy"><span class="section-label">Featured portrait</span><h2>{escape(str(f.get("name","")))}</h2><p>{escape(str(f.get("summary", "")))}</p><a class="text-link" href="/portraits/{f["_slug"]}/">Read their story →</a></div>'
else: featured_markup='<p>Add a portrait in <code>content/portraits</code> to populate this section.</p>'

events=[]
for f in (ROOT/'content/events').glob('*.md'):
    e=load(f)
    if e.get('published') is False: continue
    e['_date']=date_key(e.get('date'))
    events.append(e)
events.sort(key=lambda e:e['_date'])
future=[e for e in events if e['_date']>=date.today().isoformat()]
next_event=future[0] if future else None
if next_event:
    ev=next_event
    event_markup=f'<div><span class="section-label">Upcoming event</span><h2>{escape(str(ev.get("title","")))}</h2><p>{escape(ev["_date"])} · {escape(str(ev.get("location","")))}</p><div class="rich light">{render_md(ev.get("body"))}</div>{f"<a class=\"button\" href=\"{attr(ev.get('link'))}\">Event details ↗</a>" if ev.get("link") else ""}</div>{img(ev.get("image"),ev.get("title",""),"event-photo")}'
else:
    event_markup='<div><span class="section-label">Exhibitions & talks</span><h2>See the work in person</h2><p>Upcoming exhibitions and events will appear here automatically when published.</p><a class="button" href="/exhibitions/">Exhibitions →</a></div>'

home=f'''<section class="home-hero"><div class="home-portrait-strip">{hero_cards}</div><div class="home-hero-overlay"><div class="container"><span class="hero-eyebrow">Art / History / Remembrance / Queer Joy</span><h1>PINK TRIANGLE<br>PORTRAITS</h1><p>Giving color and dignity to those who had it stripped away.</p><a class="button" href="/portraits/">Explore the portraits →</a></div></div></section><section class="home-intro container"><div><span class="section-label">The project</span><h2>Portraits to remember.<br>Stories to keep alive.</h2><p>Pink Triangle Portraits is an ongoing art and research project by Bry Sharland, honoring queer people persecuted by the Nazi regime.</p><a class="button" href="/the-project/">Learn about the project →</a></div><div class="feature-area">{featured_markup}</div></section><section class="event-band"><div class="container event-grid">{event_markup}</div></section><section class="container gallery-preview"><div class="section-head"><div><span class="section-label">Explore the portraits</span><h2>Every person has a story.</h2></div><a class="text-link" href="/portraits/">Browse all portraits →</a></div><div class="portrait-grid">{''.join(portrait_card(p) for p in portraits[:5])}</div></section>'''
write('',page('Home','Home',home))

for route in ['the-project','the-history','about-the-artist','contact','shop']:
    file=ROOT/'content/pages'/f'{route}.md'
    if not file.exists():continue
    data=load(file)
    title=str(data.get('title',route.title()))
    body=render_md(data.get('body'))
    content=heading('Pink Triangle Portraits',title,data.get('subtitle',''),data.get('hero_image',''))+f'<section class="container editorial"><article class="rich">{body}</article><aside class="side-panel"><span class="section-label">Explore further</span><h3>Stories worth remembering</h3><p>Discover the people and historical context behind the portraits.</p><a class="text-link" href="/portraits/">Browse portraits →</a></aside></section>'
    write(route,page(title,title,content))

exhibition_items=''.join(f'<article class="event-card">{img(e.get("image"),e.get("title",""))}<div><span class="section-label">{escape(e["_date"])}</span><h2>{escape(str(e.get("title","")))}</h2><p>{escape(str(e.get("location","")))}</p><div class="rich">{render_md(e.get("body"))}</div></div></article>' for e in events)
write('exhibitions',page('Exhibitions','Exhibitions',heading('On view','Exhibitions & Talks','Past and upcoming events.')+f'<section class="container exhibition-list">{exhibition_items or "<p>Upcoming exhibitions will be listed here.</p>"}</section>'))

search=f'''<section class="container portraits-list"><div class="search-tools"><label for="portrait-search">Search by name</label><input id="portrait-search" type="search" placeholder="Find a portrait…" autocomplete="off"><span id="result-count" aria-live="polite"></span></div><div class="portrait-grid searchable">{cards}</div><p id="empty-search" hidden>No matching portraits.</p></section>'''
write('portraits',page('The Portraits','The Portraits',heading('The collection','The Portraits','Explore the artwork and the lives behind each portrait.')+search))

for i,p in enumerate(portraits):
    name=str(p.get('name','Untitled'))
    prev=portraits[(i-1)%len(portraits)]
    nxt=portraits[(i+1)%len(portraits)]
    meta=''.join(f'<div><span class="section-label">{label}</span><p>{escape(str(p.get(key,"")))}</p></div>' for label,key in [('Life dates','years'),('Medium','medium'),('Dimensions','dimensions'),('Artwork year','year')] if p.get(key))
    bio=render_md(p.get('body'))
    sources=render_md(p.get('sources'))
    content=f'''<div class="container portrait-breadcrumb"><a href="/portraits/">← All portraits</a></div><section class="container portrait-detail"><div class="portrait-art">{img(p.get('image'),name)}</div><div class="portrait-bio"><span class="section-label">The portraits / Biography</span><h1>{escape(name)}</h1>{f'<p class="years">{escape(str(p.get("years")))}</p>' if p.get('years') else ''}<div class="accent-rule"></div><div class="rich">{bio}</div>{f'<div class="sources"><h2>Sources & Further Reading</h2><div class="rich">{sources}</div></div>' if sources else ''}</div><aside class="portrait-meta">{meta}<div><span class="section-label">Share this portrait</span><button class="copy-link" type="button">Copy page link</button></div></aside></section><nav class="container prev-next" aria-label="Portrait navigation"><a href="/portraits/{prev['_slug']}/">← {escape(str(prev.get('name','Previous')))}</a><a href="/portraits/">All portraits ▦</a><a href="/portraits/{nxt['_slug']}/">{escape(str(nxt.get('name','Next')))} →</a></nav>'''
    write('portraits/'+p['_slug'],page(name,'The Portraits',content,desc=p.get('summary','')))

print(f'Built {len(portraits)} portraits and {len(events)} published events in {OUT}')
