from pathlib import Path
from datetime import date, datetime
from html import escape
from urllib.parse import quote
import re, shutil, subprocess
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

def callout_markup(item):
    style=str(item.get('style') or 'quote')
    if style not in ('quote','highlight','statement'): style='quote'
    title=str(item.get('heading') or '').strip()
    body=str(item.get('text') or '').strip()
    credit=str(item.get('attribution') or '').strip()
    if not (title or body): return ''
    alignment=str(item.get('alignment') or 'left')
    if alignment not in ('left','center','right'): alignment='left'
    content=(f'<h3>{escape(title)}</h3>' if title else '')+(f'<div class="ptp-callout-text">{render_md(body)}</div>' if body else '')+(f'<p class="ptp-callout-credit">{escape(credit)}</p>' if credit else '')
    return f'<aside class="ptp-callout ptp-callout--{style} ptp-callout--{alignment}" aria-label="Featured text">{content}</aside>'

def render_section_images(body, assignments, callouts=None):
    """Section-linked images and callouts; exact inline markers such as [callout-1]."""
    html=render_md(body)
    pieces=re.split(r'(?=<h[23](?:\s[^>]*)?>)',html)
    sections=[]
    for piece in pieces:
        if not piece.strip(): continue
        heading=re.search(r'<h[23](?:\s[^>]*)?>(.*?)</h[23]>',piece,re.S)
        key=re.sub(r'\s+',' ',re.sub(r'<[^>]*>','',heading.group(1))).strip().casefold() if heading else ''
        sections.append((key,piece))
    images_by_heading={}
    for item in assignments or []:
        if not isinstance(item,dict) or not item.get('image'): continue
        key=re.sub(r'\s+',' ',str(item.get('section_heading',''))).strip().casefold()
        if key: images_by_heading.setdefault(key,[]).append(item)
    callouts_by_heading={}
    callouts=callouts or []
    for i,item in enumerate(callouts,1):
        if not isinstance(item,dict):continue
        key=re.sub(r'\s+',' ',str(item.get('section_heading',''))).strip().casefold()
        callouts_by_heading.setdefault(key,[]).append((i,item))
    result=[]
    for key,section_html in sections:
        assigned=images_by_heading.pop(key,[])
        figures=[]
        placement='right'
        for item in assigned:
            placement=str(item.get('placement') or 'right') if len(assigned)==1 else 'right'
            caption=str(item.get('caption') or '').strip()
            caption_html=f'<figcaption>{escape(caption)}</figcaption>' if caption else ''
            figures.append(f'<figure class="editorial-figure">{img(item.get("image"),item.get("alt_text") or caption)}{caption_html}</figure>')
        before=[]; after_heading=[]; after=[]; full=[]; side=[]
        for i,item in callouts_by_heading.pop(key,[]):
            block=callout_markup(item)
            if not block:continue
            marker=f'[callout-{i}]'
            if marker in section_html:
                section_html=section_html.replace(f'<p>{marker}</p>',block).replace(marker,block)
                continue
            layout=str(item.get('layout') or 'text')
            position=str(item.get('position') or 'after-heading')
            if layout=='side': side.append(block)
            elif layout=='full': full.append(block)
            elif position=='before-section': before.append(block)
            elif position=='after-section': after.append(block)
            else: after_heading.append(block)
        if after_heading:
            heading_match=re.search(r'</h[23]>',section_html)
            insert=heading_match.end() if heading_match else 0
            section_html=section_html[:insert]+''.join(after_heading)+section_html[insert:]
        cls=' editorial-section--'+placement if figures else ''
        media_items=figures+side
        media=f'<div class="editorial-section-media">{"".join(media_items)}</div>' if media_items else ''
        result.append(''.join(before)+f'<section class="editorial-section{cls}"><div class="editorial-section-copy">{section_html}{"".join(after)}</div>{media}</section>'+''.join(f'<div class="ptp-callout-full">{c}</div>' for c in full))
    # Unmatched section names should not silently discard content.
    leftovers=[callout_markup(item) for entries in callouts_by_heading.values() for _,item in entries]
    return ''.join(result)+''.join(f'<div class="ptp-callout-full">{c}</div>' for c in leftovers if c)

def attr(value): return escape(str(value or ''),quote=True)
def slug(value): return re.sub(r'[^a-z0-9]+','-',str(value).lower()).strip('-')
def person_modified(slug_id):
    """Git commit time when this biography file was first added (stable across edits)."""
    path=f'content/people/{slug_id}.md'
    try:
        result=subprocess.run(['git','log','--diff-filter=A','--format=%ct','--',path],cwd=ROOT,capture_output=True,text=True,timeout=8)
        if result.returncode==0 and result.stdout.strip():
            stamps=[int(v) for v in result.stdout.split() if v.isdigit()]
            if stamps:return min(stamps)
    except (OSError,subprocess.TimeoutExpired): pass
    return 0

def date_key(v):
    if isinstance(v,(date,datetime)): return v.isoformat()
    return str(v or '')
def img(path,alt='',cls=''):
    if not path:return ''
    return f'<img src="{attr(path)}" alt="{attr(alt)}" class="{attr(cls)}" loading="lazy">'

def setting(name,default=''):
    return design.get(name,default)
def cssvar(name,value):
    return f'--{name}:{attr(value)};'
def display_order(p):
    try:return int(p.get('display_order',9999))
    except (TypeError,ValueError):return 9999

def gallery_sort(items):
    mode=str(setting('gallery_sort','custom'))
    if mode=='newest': return sorted(items,key=lambda p:p['_date'],reverse=True)
    if mode=='alphabetical': return sorted(items,key=lambda p:p.get('name','').casefold())
    if mode=='random':
        import random
        rng=random.Random(str(date.today()))
        shuffled=list(items);rng.shuffle(shuffled);return shuffled
    return sorted(items,key=lambda p:(display_order(p),p.get('name','').casefold()))

def artwork_link(p):
    return '/people/'+attr(p.get('_person_slug') or p['_slug'])+'/'

def rule_style(prefix):
    mode=setting(prefix+'_rule_type','solid')
    color=setting(prefix+'_rule_color','#ed398b')
    end=setting(prefix+'_rule_end','#ff842d')
    return f'linear-gradient(90deg,{color},{end})' if mode=='gradient' else color

def section_style(section):
    bg=setting(section+'_background','')
    return f' style="background-color:{attr(bg)}"' if bg else ''

settings_path=ROOT/'content/settings/site.yml'
# Merge individual CMS settings files. New values take precedence over legacy site.yml.
design=yaml.safe_load(settings_path.read_text(encoding='utf-8')) if settings_path.exists() else {}
design=design or {}
for settings_name in ('global','header','typography','homepage','gallery','biography','rules','footer','callouts'):
    settings_file=ROOT/'content/settings'/f'{settings_name}.yml'
    if settings_file.exists():
        settings_data=yaml.safe_load(settings_file.read_text(encoding='utf-8')) or {}
        design.update(settings_data)
def social_links():
    icons = {
        'instagram': '/assets/images/social-instagram-white.png',
        'bluesky': '/assets/images/social-bluesky-white.png',
        'tiktok': '/assets/images/social-tiktok-white.png',
    }
    return ''.join(
        f'<a href="{attr(setting(k+"_url"))}" target="_blank" rel="noopener noreferrer" aria-label="{k.title()}" title="{k.title()}"><img src="{v}" alt="" aria-hidden="true"></a>'
        for k,v in icons.items() if setting(k+'_url')
    )

def page(title,active,content,desc=''):
    nav=list(design.get('navigation') or [{'label':a,'url':u} for a,u in [('Home','/'),('The Project','/the-project/'),('The Artist','/about-the-artist/'),('The History','/the-history/'),('The Portraits','/portraits/'),('Exhibitions','/exhibitions/'),('Shop','/shop/'),('Contact','/contact/')]])
    links=''.join(f'<a href="{attr(n.get("url","/"))}" class="{"active" if active==n.get("label") else ""}">{escape(str(n.get("label","")))}</a>' for n in nav if n.get('label'))
    social=social_links()
    navsocial=f'<div class="social-icons nav-social">{social}</div>' if setting('social_nav_enabled',True) and social else ''
    footsocial=f'<div class="social-icons footer-social">{social}</div>' if setting('social_footer_enabled',True) and social else ''
    favicon=f'<link rel="icon" href="{attr(setting("favicon"))}">' if setting('favicon') else ''
    logo=setting('logo','')
    brand=(img(logo,'Pink Triangle Portraits','brand-logo') if logo else '<span class="brand-mark" aria-hidden="true"></span><span>PINK<br>TRIANGLE<br>PORTRAITS</span>')
    variables={
      'navy':setting('nav_background','#062c3b'),'pink':setting('accent_color','#ed398b'),
      'ptp-callout-accent':setting('callout_accent','#ed398b'),'ptp-quote-rule':str(setting('callout_quote_rule',10))+'px',
      'ptp-statement-rule':str(setting('callout_statement_rule',2))+'px','ptp-highlight-bg':setting('callout_highlight_background','#eeeeee'),
      'ptp-callout-font':str(setting('callout_font_size',26))+'px','ptp-callout-spacing':str(setting('callout_spacing',26))+'px',
      'ink':setting('text_color','#082d3b'),'paper':setting('page_background','#fffdfb'),
      'max':str(setting('content_width',1280))+'px',
      'nav-text':setting('nav_text_color','#ffffff'),
      'nav-font':setting('nav_font','Barlow Condensed'),'heading-font':setting('heading_font','Barlow Condensed'),
      'body-font':setting('body_font','DM Sans'),'nav-size':str(setting('nav_font_size',17))+'px',
      'social-icon-gap':str(setting('social_icon_gap',6))+'px','social-icon-mobile-gap':str(setting('social_icon_mobile_gap',5))+'px','interior-rule-width':str(setting('interior_rule_width',10))+'px','research-rule-width':str(setting('research_rule_width',10))+'px','panel-rule-width':str(setting('panel_rule_width',10))+'px','hero-eyebrow-rule-width':str(setting('hero_eyebrow_rule_width',10))+'px','nav-gap':str(setting('nav_gap',22))+'px','logo-width':str(setting('logo_width',190))+'px',
      'button-bg':setting('button_color','#ed398b'),'button-text':setting('button_text_color','#071f2c'),
      'callout-rule':rule_style('callout'),'callout-width':str(setting('callout_rule_width',7))+'px',
      'callout-gap':str(setting('callout_gap',20))+'px',
      'divider-rule':rule_style('divider'),'divider-height':str(setting('divider_rule_width',4))+'px',
      'section-gap':str(setting('section_spacing',75))+'px',
      'nav-rule':rule_style('nav'),'nav-rule-width':str(setting('nav_rule_width',10))+'px','footer-rule-width':str(setting('footer_rule_width',10))+'px',
      'paint-image':f'url("{setting("paint_background","/assets/images/715931084-background-web.jpg")}")',
      'paint-opacity':str(max(0,min(100,int(setting('paint_opacity',70))))/100),
      'brush-primary':setting('brush_accent_color','#ed398b'),
      'brush-secondary':setting('brush_accent_secondary','#ff842d'),
      'gallery-hover-overlay':f'rgba({int(str(setting("gallery_hover_color","#a81864")).lstrip("#")[0:2],16)},{int(str(setting("gallery_hover_color","#a81864")).lstrip("#")[2:4],16)},{int(str(setting("gallery_hover_color","#a81864")).lstrip("#")[4:6],16)},{max(0,min(100,int(setting("gallery_hover_opacity",88))))/100})',
      'display-font':setting('display_font',setting('heading_font','Barlow Condensed')),
      'section-font':setting('section_font',setting('heading_font','Barlow Condensed')),
      'label-font':setting('label_font',setting('heading_font','Barlow Condensed')),
      'art-font':setting('art_font',setting('heading_font','Barlow Condensed')),
      'research-font':setting('research_font',setting('body_font','DM Sans')),
      'bio-quote-font':setting('biography_quote_font',setting('body_font','DM Sans')),
      'bio-quote-size':str(setting('biography_quote_size',22))+'px',
      'bio-quote-weight':str(setting('biography_quote_weight','500')),
      'bio-quote-style':setting('biography_quote_style','italic'),
      'bio-quote-color':setting('biography_quote_color','#082d3b'),
      'bio-quote-bg':setting('biography_quote_background','#fff0f7'),
      'bio-quote-rule':setting('biography_quote_rule_color','#ed398b'),
      'bio-quote-rule-width':str(setting('biography_quote_rule_width',5))+'px',
      'bio-quote-padding':str(setting('biography_quote_padding',22))+'px',
      'bio-quote-spacing':str(setting('biography_quote_spacing',28))+'px',
      'footer-font':setting('footer_font',setting('body_font','DM Sans')),
      'display-size':str(setting('display_size',112))+'px',
      'display-mobile-size':str(setting('display_mobile_size',62))+'px',
      'section-size':str(setting('section_size',54))+'px',
      'body-size':str(setting('body_size',17))+'px',
      'interior-header-height':str(max(220,min(650,float(setting('interior_header_height',350) or 350))))+'px',
      'page-title-line-height':str(max(0.7,min(2.5,float(setting('page_title_line_height',1.05) or 1.05)))),
      'page-tagline-line-height':str(max(0.7,min(2.5,float(setting('page_tagline_line_height',1.15) or 1.15)))),
      'body-leading':str(setting('body_leading',1.75)),
       'paragraph-spacing':str(setting('paragraph_spacing',28))+'px',
       'section-heading-spacing':str(setting('section_heading_spacing',55))+'px',
      'label-size':str(setting('label_size',18))+'px',
      'art-title-size':str(setting('art_title_size',28))+'px',
      'art-details-size':str(setting('art_details_size',16))+'px',
      'research-heading-size':str(setting('research_heading_size',26))+'px',
      'research-body-size':str(setting('research_body_size',16))+'px',
      'footer-size':str(setting('footer_size',16))+'px',
      'heading-color':setting('heading_color',setting('text_color','#082d3b')),
      'section-color':setting('section_color',setting('text_color','#082d3b')),
      'body-color':setting('body_color',setting('text_color','#082d3b')),
      'label-color':setting('label_color',setting('accent_color','#ed398b')),
      'art-color':setting('art_color',setting('text_color','#082d3b')),
      'research-color':setting('research_color',setting('text_color','#082d3b')),
      'research-bg':setting('research_background','#fff0f7'),
      'footer-color':setting('footer_color','#ffffff'),
      'display-weight':str(setting('display_weight',900)),
      'section-weight':str(setting('section_weight',900)),
      'body-weight':str(setting('body_weight',400)),
      'nav-weight':str(setting('nav_weight',800)),
      'label-weight':str(setting('label_weight',800)),
      'display-tracking':str(setting('display_tracking',0))+'px',
      'nav-tracking':str(setting('nav_tracking',0.7))+'px',
      'label-tracking':str(setting('label_tracking',2))+'px',
      'gallery-hover-text':setting('gallery_hover_text','#ffffff')
    }
    fonts=['Barlow Condensed','DM Sans','Caveat','Anton','Archivo Black','Oswald','Bebas Neue','Manrope','Montserrat','Outfit','Work Sans','Libre Baskerville','Playfair Display','Cormorant Garamond','Merriweather','Inter','Source Sans 3','Lato','Nunito Sans','Roboto','Poppins','Roboto Slab','Lora','Space Grotesk','Barlow','Archivo']
    selected={str(setting(k,default)) for k,default in [('nav_font','Barlow Condensed'),('heading_font','Barlow Condensed'),('body_font','DM Sans'),('display_font','Barlow Condensed'),('section_font','Barlow Condensed'),('label_font','Barlow Condensed'),('art_font','Barlow Condensed'),('research_font','DM Sans'),('biography_quote_font','DM Sans'),('footer_font','DM Sans')]}
    families='&'.join('family='+quote(f)+':wght@400;500;600;700;800;900' for f in fonts if f in selected)
    font_link=f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?{families}&display=swap">' if families else ''
    styles=''.join(cssvar(k,v) for k,v in variables.items())
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="{attr(desc or 'Pink Triangle Portraits, an art and historical remembrance project by Bry Sharland')}"><title>{escape(title)} | Pink Triangle Portraits</title>{favicon}{font_link}<link rel="stylesheet" href="/assets/site.css"><style>:root{{{styles}}}</style></head><body><header class="site-header"><div class="nav-wrap"><a class="brand" href="/" aria-label="Pink Triangle Portraits home">{brand}</a><button class="menu-toggle" aria-controls="main-nav" aria-expanded="false" aria-label="Open menu">☰</button><nav id="main-nav" aria-label="Main navigation">{links}</nav>{navsocial}</div></header><main>{content}</main><footer><div class="container foot-grid"><div><b>PINK TRIANGLE PORTRAITS</b><p>Giving color and dignity to those who had it stripped away.</p></div><div><a class="footer-shop-button" href="{attr(setting('shop_url','https://www.pinktriangleportraits.com/'))}">Visit the shop</a><p>Artwork and research by Bry Sharland</p>{footsocial}</div></div></footer><script src="/assets/site.js" defer></script></body></html>'''

def write(route,html):
    target=OUT/route/'index.html' if route else OUT/'index.html'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(html,encoding='utf-8')

def heading(kicker,title,subtitle='',hero='',hero_mobile=''):
    """One unified interior banner: image behind the text on desktop."""
    subtitle_markup=f'<p>{escape(subtitle)}</p>' if subtitle else ''
    image_markup=''
    if hero or hero_mobile:
        mobile_source=f'<source media="(max-width:700px)" srcset="{attr(hero_mobile)}">' if hero_mobile else ''
        image_markup=(f'<div class="interior-header-media"><picture>{mobile_source}'
                      f'<img src="{attr(hero or hero_mobile)}" alt="" loading="eager"></picture></div>')
    banner_class=' interior-hero--image' if image_markup else ''
    return (f'<section class="interior-hero{banner_class}">{image_markup}'
            f'<div class="container interior-inner"><div class="interior-heading-copy">'
            f'<div class="eyebrow">{escape(kicker)}</div><h1>{escape(title)}</h1>{subtitle_markup}'
            f'</div></div></section>')

people={}
for f in (ROOT/'content/people').glob('*.md'):
    p=load(f);p['_slug']=slug(f.stem);people[p['_slug']]=p
portraits=[]
for person_slug, person in people.items():
    for j, artwork in enumerate(person.get('artworks') or []):
        if not isinstance(artwork,dict) or artwork.get('published') is False: continue
        p=dict(artwork)
        p['_slug']=person_slug+'-'+str(j+1)
        p['_date']=date_key(p.get('date'))
        p['_person_slug']=person_slug
        p['name']=person.get('name','Untitled')
        p['display_order']=p.get('display_order',person.get('display_order',100))
        portraits.append(p)
# Backwards compatibility: old artwork records remain visible until migration is run.
# If a person has migrated artworks, do not duplicate their legacy artwork records.
for folder in ['artwork','portraits']:
    for f in (ROOT/'content'/folder).glob('*.md'):
        p=load(f)
        if p.get('published') is False:continue
        p['_slug']=slug(f.stem)
        p['_date']=date_key(p.get('date'))
        p['_person_slug']=slug(p.get('person','')) if p.get('person') else p['_slug']
        if p['_person_slug'] not in people:
            people[p['_person_slug']]={'_slug':p['_person_slug'],'name':p.get('name','Untitled'),'years':p.get('years',''),'body':p.get('body',''),'sources':p.get('sources','')}
        if people[p['_person_slug']].get('artworks'): continue
        p['name']=people[p['_person_slug']].get('name',p.get('name','Untitled'))
        portraits.append(p)
portraits=gallery_sort(portraits)
# Featured person: explicit person-level override first; otherwise newest created
# biography record. A batch import commits many records at once, so the tie-break
# is deterministic and can be replaced using the override checkbox.
newest=sorted(portraits,key=lambda p:p['_date'],reverse=True)
unique_people=list(dict.fromkeys(p['_person_slug'] for p in portraits))
ranked_people=sorted(unique_people,key=lambda ps:(person_modified(ps),ps),reverse=True)
overrides=[ps for ps in ranked_people if people.get(ps,{}).get('homepage_override')]
selected_person=(overrides or ranked_people or [None])[0]
featured=next((p for p in portraits if p['_person_slug']==selected_person),None)

def portrait_card(p):
    name=escape(str(p.get('name','Untitled')))
    return f'<a class="portrait-card" href="{artwork_link(p)}"><span class="portrait-image">{img(p.get("image"),name)}<span class="portrait-hover-name" aria-hidden="true">{name}</span></span><span class="portrait-name">{name}<span aria-hidden="true"> ↗</span></span></a>'

gallery_people=list(dict.fromkeys(p['_person_slug'] for p in portraits))
gallery_art=[next(p for p in portraits if p['_person_slug']==ps) for ps in gallery_people]
cards=''.join(portrait_card(p) for p in gallery_art)
hero_cards=''.join(img(p.get('image'),p.get('name','')) for p in newest[:6])
if featured:
    f=featured
    teaser=str(people.get(f['_person_slug'],{}).get('homepage_teaser') or '').strip()
    if not teaser:
        teaser=re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',render_md(people.get(f['_person_slug'],{}).get('body','')))).strip()[:200]
    featured_markup=f'<div class="feature-art">{img(f.get("image"),f.get("name",""))}</div><div class="feature-copy"><span class="section-label">The latest portrait</span><h2>{escape(str(f.get("name","")))}</h2><p>{escape(teaser)}</p><a class="text-link" href="{artwork_link(f)}">Read their story →</a></div>' 
else: featured_markup='<p>Add a portrait in <code>content/portraits</code> to populate this section.</p>'

events=[]
for f in (ROOT/'content/events').glob('*.md'):
    e=load(f)
    if e.get('published') is False: continue
    e['_date']=date_key(e.get('date'))
    e['_end']=date_key(e.get('end_date')) or e['_date']
    events.append(e)
events.sort(key=lambda e:e['_date'])
today=date.today().isoformat()
upcoming=sorted([e for e in events if e['_end']>=today],key=lambda e:e['_date'])
past=sorted([e for e in events if e['_end']<today],key=lambda e:e['_date'],reverse=True)
next_event=upcoming[0] if upcoming else None

def event_card(e,large=False):
    image_markup=img(e.get('image'),e.get('title',''),'event-cover')
    details=f'<div><span class="section-label">{escape(e["_date"])}</span><h2>{escape(str(e.get("title","")))}</h2><p>{escape(str(e.get("location","")))}</p><div class="rich">{render_md(e.get("body"))}</div>'
    if e.get('link'): details+=f'<p><a class="text-link" href="{attr(e["link"])}">Event details ↗</a></p>'
    return f'<article class="event-card{" event-card-featured" if large else ""}">{image_markup}{details}</div></article>'

if next_event:
    ev=next_event
    event_text=f'<span class="section-label">Upcoming exhibition or talk</span><h2>{escape(str(ev.get("title","")))}</h2><p>{escape(ev["_date"])} · {escape(str(ev.get("location","")))}</p>'
else:
    event_text='<span class="section-label">Exhibitions & talks</span><h2>See the work in person</h2><p>Explore exhibitions, artist talks, and events featuring Pink Triangle Portraits.</p>'
exhibition_home_image=setting('exhibitions_home_image','') or (next_event or {}).get('image','')
event_markup=f'<div class="event-band-copy">{event_text}<a class="button" href="/exhibitions/">Exhibitions →</a></div>'
if exhibition_home_image: event_markup+=f'<div class="event-band-visual">{img(exhibition_home_image,"Exhibitions and talks")}</div>'

hero_desktop=setting('hero_banner_desktop','') or setting('hero_banner','')
hero_mobile=setting('hero_banner_mobile','')
hero_source=f'<source media="(max-width:700px)" srcset="{attr(hero_mobile)}">' if hero_mobile else ''
hero_picture=(f'<picture class="hero-picture">{hero_source}<img src="{attr(hero_desktop or hero_mobile)}" alt="" loading="eager"></picture>' if (hero_desktop or hero_mobile) else hero_cards)
hero_eyebrow=escape(str(setting('hero_eyebrow','Art / History / Remembrance / Queer Joy')))
hero_heading=escape(str(setting('hero_headline','PINK TRIANGLE PORTRAITS'))).replace('\n',' ')
hero_tagline=escape(str(setting('hero_tagline','Giving color and dignity to those who had it stripped away.')))
hero_overlay=max(0,min(95,int(setting('hero_overlay_opacity',40))))/100
home=f'''<section class="home-hero" style="min-height:{attr(setting('hero_height',500))}px;--hero-darkness:{hero_overlay}"><div class="home-portrait-strip">{hero_picture}</div><div class="home-hero-overlay"><div class="container"><span class="hero-eyebrow">{hero_eyebrow}</span><h1>{hero_heading}</h1><p>{hero_tagline}</p></div></div></section><section class="home-intro container"{section_style("intro")}><div><span class="section-label">The project</span><h2>Portraits to remember.<br>Stories to keep alive.</h2><p>Pink Triangle Portraits is an ongoing art and research project by Bry Sharland, honoring queer people persecuted by the Nazi regime.</p><a class="button" href="/the-project/">Learn about the project →</a></div><div class="feature-area">{featured_markup}</div></section><section class="event-band"><div class="container event-grid">{event_markup}</div></section><section class="container gallery-preview"{section_style("gallery")}><div class="section-head"><div><span class="section-label">Explore the portraits</span><h2>Every person has a story.</h2></div><a class="text-link" href="/portraits/">Browse all portraits →</a></div><div class="portrait-grid">{''.join(portrait_card(p) for p in [next(a for a in newest if a['_person_slug']==ps) for ps in dict.fromkeys(a['_person_slug'] for a in newest)][:5])}</div></section>'''
write('',page('Home','Home',home))

for route in ['the-project','the-history','about-the-artist','contact','shop']:
    file=ROOT/'content/pages'/f'{route}.md'
    if not file.exists():continue
    data=load(file)
    title=str(data.get('title',route.title()))
    supporting=data.get('supporting_images') or []
    callouts=data.get('callouts') or []
    body=render_section_images(data.get('body'),supporting,callouts)
    content=heading('Pink Triangle Portraits',title,data.get('subtitle',''),data.get('hero_image',''),data.get('hero_mobile_image',''))+f'<div class="container editorial-with-images rich">{body}</div>'

    write(route,page(title,title,content))

featured_event=(next_event or None)
featured_event_markup=('<div class="container exhibition-feature"><span class="section-label">Current & upcoming</span>'+event_card(featured_event,True)+'</div>') if featured_event else '<div class="container exhibition-feature"><span class="section-label">Current & upcoming</span><p>No upcoming events have been announced yet.</p></div>'
other_upcoming=[e for e in upcoming if e is not featured_event]
upcoming_markup=('<section class="container exhibition-list"><h2>More upcoming events</h2>'+''.join(event_card(e) for e in other_upcoming)+'</section>') if other_upcoming else ''
past_markup='<section class="container exhibition-list"><h2>Previous exhibitions & talks</h2>'+(''.join(event_card(e) for e in past) if past else '<p>Past exhibitions and talks will appear here.</p>')+'</section>'
exhibitions_copy=ROOT/'content/pages/exhibitions.md'
exhibitions_intro=render_md(load(exhibitions_copy).get('body')) if exhibitions_copy.exists() else ''
write('exhibitions',page('Exhibitions','Exhibitions',heading('On view','Exhibitions & Talks','Past and upcoming events.',load(exhibitions_copy).get('hero_image','') if exhibitions_copy.exists() else '',load(exhibitions_copy).get('hero_mobile_image','') if exhibitions_copy.exists() else '')+(f'<section class="container editorial-copy rich">{exhibitions_intro}</section>' if exhibitions_intro else '')+featured_event_markup+upcoming_markup+past_markup))

search=f'''<section class="container portraits-list"><div class="search-tools"><label for="portrait-search">Search by name</label><input id="portrait-search" type="search" placeholder="Find a portrait…" autocomplete="off"><span id="result-count" aria-live="polite"></span></div><div class="portrait-grid searchable">{cards}</div><p id="empty-search" hidden>No matching portraits.</p></section>'''
write('portraits',page('The Portraits','The Portraits',heading('The collection','The Portraits','Explore the artwork and the lives behind each portrait.',load(ROOT / 'content/pages/portraits.md').get('hero_image','') if (ROOT / 'content/pages/portraits.md').exists() else '',load(ROOT / 'content/pages/portraits.md').get('hero_mobile_image','') if (ROOT / 'content/pages/portraits.md').exists() else '')+(f'<section class="container editorial-copy rich">{render_md(load(ROOT / "content/pages/portraits.md").get("body"))}</section>' if (ROOT / 'content/pages/portraits.md').exists() else '')+search))

person_slugs=list(dict.fromkeys(p['_person_slug'] for p in portraits))
for i,person_slug in enumerate(person_slugs):
    person=people[person_slug]
    artworks=[p for p in portraits if p['_person_slug']==person_slug]
    name=str(person.get('name','Untitled'))
    prev=people[person_slugs[(i-1)%len(person_slugs)]]
    nxt=people[person_slugs[(i+1)%len(person_slugs)]]
    lead=artworks[0]
    artwork_data=[]
    for a in artworks:
        parts=[str(a.get(k) or '').strip() for k in ['medium','dimensions'] if str(a.get(k) or '').strip()]
        artwork_data.append({'image':str(a.get('image') or ''),'details':'<span class="artwork-separator" aria-hidden="true">|</span>'.join(escape(part) for part in parts),'alt':name})
    first=artwork_data[0]
    thumbs=''
    if len(artwork_data)>1:
        buttons=''.join(f'<button type="button" class="artwork-thumb{" is-selected" if j==0 else ""}" aria-label="View painting {j+1} of {attr(name)}" aria-pressed="{str(j==0).lower()}" data-image="{attr(a["image"])}" data-details="{attr(a["details"])}" data-alt="{attr(a["alt"])}">{img(a["image"],a["alt"])}</button>' for j,a in enumerate(artwork_data))
        thumbs=f'<div class="artwork-thumbnails" role="group" aria-label="Choose a painting of {attr(name)}">{buttons}</div>'
    main_art=f'<figure class="person-artwork"><div class="main-artwork-image">{img(first["image"],first["alt"],"selected-artwork-image")}</div>{thumbs}</figure>'
    artwork_meta=f'<div class="portrait-artwork-meta" aria-live="polite"><div class="selected-artwork-details"{"" if first["details"] else " hidden"}>{first["details"]}</div></div>'
    bio=render_md(person.get('body'))
    sources=render_md(person.get('sources'))
    thanks=render_md(person.get('special_thanks'))
    research=''
    if sources or thanks:
        research='<section class="research-callout" aria-label="Further reading and acknowledgments"><div class="research-callout-inner">'
        if sources: research+=f'<div class="research-part"><h2>Further Reading &amp; Sources</h2><div class="rich">{sources}</div></div>'
        if thanks: research+=f'<div class="research-part"><h2>Special Thanks</h2><div class="rich">{thanks}</div></div>'
        research+='</div></section>'
    left=f'<div class="person-artworks">{main_art}{research}</div>'
    content=f'''<div class="container portrait-breadcrumb"><a href="/portraits/">← All portraits</a></div><section class="container person-detail">{left}<article class="portrait-bio"><h1>{escape(name)}</h1><p class="years">{escape(str(person.get('years','')))}</p>{artwork_meta}<div class="accent-rule"></div><div class="rich">{bio}</div></article></section><nav class="container prev-next"><a href="/people/{prev['_slug']}/">← {escape(str(prev.get('name','Previous')))}</a><a href="/portraits/">All portraits ▦</a><a href="/people/{nxt['_slug']}/">{escape(str(nxt.get('name','Next')))} →</a></nav>'''
    write('people/'+person_slug,page(name,'The Portraits',content,desc=person.get('summary','')))
# old portrait routes redirect to shared person page
for p in portraits:
    dest='/people/'+p['_person_slug']+'/'
    write('portraits/'+p['_slug'],f'<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url={attr(dest)}"><link rel="canonical" href="{attr(dest)}"><a href="{attr(dest)}">Read biography</a>')
print(f'Built {len(portraits)} artworks, {len(person_slugs)} people and {len(events)} events')
