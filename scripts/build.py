from pathlib import Path
from datetime import date, datetime
from html import escape, unescape
from urllib.parse import quote, urlparse, urljoin
from urllib.request import Request, urlopen
from html.parser import HTMLParser
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
        key=re.sub(r'\s+',' ',unescape(re.sub(r'<[^>]*>','',heading.group(1)))).strip().casefold() if heading else ''
        sections.append((key,piece))
    images_by_heading={}
    for item in assignments or []:
        if not isinstance(item,dict) or not item.get('image'): continue
        key=re.sub(r'\s+',' ',str(item.get('section_heading',''))).strip().casefold()
        if key: images_by_heading.setdefault(key,[]).append(item)
    # Inline markers take precedence over section-based placement. A marker may
    # occur in any section, regardless of the optional related-heading field.
    callouts_by_heading={}
    callouts_by_index={}
    callouts=callouts or []
    for i,item in enumerate(callouts,1):
        if not isinstance(item,dict): continue
        callouts_by_index[i]=item
        key=re.sub(r'\s+',' ',unescape(str(item.get('section_heading','')))).strip().casefold()
        # No heading supplied: attach to the final editorial section.
        # Explicit inline markers continue to take precedence.
        if not key and sections: key=sections[-1][0]
        callouts_by_heading.setdefault(key,[]).append((i,item))
    used_callouts=set()
    result=[]
    for key,section_html in sections:
        assigned=images_by_heading.pop(key,[])
        figures=[]
        placement='right'
        for item in assigned:
            placement=str(item.get('placement') or 'right') if len(assigned)==1 else 'right'
            caption=str(item.get('caption') or '').strip()
            caption_html=f'<figcaption>{escape(caption)}</figcaption>' if caption else ''
            figures.append(f'<figure class="editorial-figure" data-auto-fit="{"false" if item.get("auto_fit", True) is False else "true"}" data-max-height="{attr(item.get("max_height") or 0)}">{img(item.get("image"),item.get("alt_text") or caption)}{caption_html}</figure>')
        before=[]; after_heading=[]; after=[]; full=[]; side=[]
        # Resolve all inline markers in this section first, even when the
        # related heading was entered differently in the CMS.
        for marker_match in list(re.finditer(r'\[callout-(\d+)\]',section_html,re.I)):
            i=int(marker_match.group(1))
            item=callouts_by_index.get(i)
            if item is None or i in used_callouts: continue
            block=callout_markup(item)
            if not block: continue
            used_callouts.add(i)
            layout=str(item.get('layout') or 'text')
            token=marker_match.group(0)
            if layout=='side': side.append(block)
            elif layout=='full': full.append(block)
            else:
                section_html=section_html.replace(f'<p>{token}</p>',block)
                section_html=section_html.replace(token,block)
                continue
            section_html=section_html.replace(f'<p>{token}</p>','').replace(token,'')

        for i,item in callouts_by_heading.pop(key,[]):
            if i in used_callouts: continue
            block=callout_markup(item)
            if not block:continue
            used_callouts.add(i)
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
        before_markup=''.join(f'<div class="ptp-callout-text-column">{c}</div>' for c in before)
        result.append(before_markup+f'<section class="editorial-section{cls}"><div class="editorial-section-copy">{section_html}{"".join(after)}</div>{media}</section>'+''.join(f'<div class="ptp-callout-full">{c}</div>' for c in full))
    # Unmatched section names should not silently discard content.
    leftovers=[callout_markup(item) for i,item in callouts_by_index.items() if i not in used_callouts]
    return ''.join(result)+''.join(f'<div class="ptp-callout-text-column">{c}</div>' for c in leftovers if c)

def hex_to_rgba(color, opacity):
    color=str(color or '#ed398b').strip()
    if not re.fullmatch(r'#[0-9a-fA-F]{6}',color): color='#ed398b'
    try: alpha=max(0,min(100,float(opacity)))/100
    except (ValueError,TypeError): alpha=.12
    return f'rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},{alpha:g})'

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
    links=''.join(f'<a href="{attr(n.get("url","/"))}" class="{"active" if str(active).strip().casefold()==str(n.get("label","")).strip().casefold() else ""}" aria-current="{"page" if str(active).strip().casefold()==str(n.get("label","")).strip().casefold() else "false"}">{escape(str(n.get("label","")))}</a>' for n in nav if n.get('label'))
    social=social_links()
    navsocial=f'<div class="social-icons nav-social">{social}</div>' if setting('social_nav_enabled',True) and social else ''
    footsocial=f'<div class="social-icons footer-social">{social}</div>' if setting('social_footer_enabled',True) and social else ''
    favicon=f'<link rel="icon" href="{attr(setting("favicon"))}">' if setting('favicon') else ''
    logo=setting('logo','')
    brand=(img(logo,'Pink Triangle Portraits','brand-logo') if logo else '<span class="brand-mark" aria-hidden="true"></span><span>PINK<br>TRIANGLE<br>PORTRAITS</span>')
    variables={
      'navy':setting('nav_background','#062c3b'),'pink':setting('accent_color','#ed398b'),
      'ptp-callout-accent':setting('callout_accent','#ed398b'),'ptp-quote-rule':str(setting('callout_quote_rule',10))+'px',
      'ptp-statement-rule':str(setting('callout_statement_rule',2))+'px',
      'ptp-highlight-bg':hex_to_rgba(setting('callout_highlight_background','#ed398b'),setting('callout_highlight_opacity',12)),
      'ptp-highlight-text':setting('callout_highlight_text_color','#082d3b'),
      'ptp-highlight-heading-size':str(setting('callout_highlight_heading_size',26))+'px',
      'ptp-quote-font':str(setting('callout_quote_font_size',20))+'px',
      'ptp-statement-font':str(setting('callout_statement_font_size',21))+'px',
      'ptp-callout-spacing':str(setting('callout_spacing',26))+'px',
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
      'bio-name-font':str(setting('bio_name_font','Barlow Condensed')),
      'bio-name-size':str(setting('bio_name_size',62))+'px',
      'bio-name-weight':str(setting('bio_name_weight',900)),
      'bio-name-color':str(setting('bio_name_color','#ed398b')),
      'bio-name-line-height':str(setting('bio_name_line_height',1)),
      'bio-name-letter-spacing':str(setting('bio_name_letter_spacing',0))+'px',
      'bio-name-bottom-gap':str(setting('bio_name_bottom_gap',8))+'px',
      'bio-dates-font':str(setting('bio_dates_font','DM Sans')),
      'bio-dates-size':str(setting('bio_dates_size',20))+'px',
      'bio-dates-weight':str(setting('bio_dates_weight',400)),
      'bio-dates-color':str(setting('bio_dates_color','#082d3b')),
      'bio-dates-bottom-gap':str(setting('bio_dates_bottom_gap',8))+'px',
      'bio-details-font':str(setting('bio_details_font','DM Sans')),
      'bio-details-size':str(setting('bio_details_size',20))+'px',
      'bio-details-weight':str(setting('bio_details_weight',400)),
      'bio-details-color':str(setting('bio_details_color','#082d3b')),
      'bio-details-separator-gap':str(setting('bio_details_separator_gap',13))+'px',
      'bio-rule-width':str(setting('bio_rule_width',10))+'px',
      'bio-rule-top-gap':str(setting('bio_rule_top_gap',22))+'px',
      'bio-rule-bottom-gap':str(setting('bio_rule_bottom_gap',30))+'px',
      'bio-nav-font':str(setting('bio_nav_font','DM Sans')),
      'bio-nav-size':str(setting('bio_nav_size',20))+'px',
      'bio-nav-label-size':str(setting('bio_nav_label_size',12))+'px',
      'bio-nav-color':str(setting('bio_nav_color','#082d3b')),
      'bio-nav-rule-color':str(setting('bio_nav_rule_color','#a4b1b5')),
      'bio-nav-rule-width':str(setting('bio_nav_rule_width',1))+'px',
      'bio-nav-padding':str(setting('bio_nav_padding',24))+'px',
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
      'gallery-hover-text':setting('gallery_hover_text','#ffffff'),
      'gallery-spacing':str(max(0,min(100,int(setting('gallery_spacing',22) or 22))))+'px'
    }
    fonts=['Barlow Condensed','DM Sans','Caveat','Anton','Archivo Black','Oswald','Bebas Neue','Manrope','Montserrat','Outfit','Work Sans','Libre Baskerville','Playfair Display','Cormorant Garamond','Merriweather','Inter','Source Sans 3','Lato','Nunito Sans','Roboto','Poppins','Roboto Slab','Lora','Space Grotesk','Barlow','Archivo']
    selected={str(setting(k,default)) for k,default in [('nav_font','Barlow Condensed'),('heading_font','Barlow Condensed'),('body_font','DM Sans'),('display_font','Barlow Condensed'),('section_font','Barlow Condensed'),('label_font','Barlow Condensed'),('art_font','Barlow Condensed'),('research_font','DM Sans'),('biography_quote_font','DM Sans'),('footer_font','DM Sans'),('bio_name_font','Barlow Condensed'),('bio_dates_font','DM Sans'),('bio_details_font','DM Sans'),('bio_nav_font','DM Sans')]}
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
    subtitle_lines = str(subtitle or '').splitlines()
    subtitle_html = '<br class="desktop-subtitle-break">\n'.join(escape(line.strip()) for line in subtitle_lines)
    subtitle_markup = f'<p>{subtitle_html}</p>' if subtitle_html.strip() else ''
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
        p['_artwork_index']=j
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
    thumb=p.get('gallery_thumbnail') or p.get('image')
    return f'<a class="portrait-card" href="{artwork_link(p)}"><span class="portrait-image">{img(thumb,name)}<span class="portrait-hover-name" aria-hidden="true">{name}</span></span><span class="portrait-name">{name}<span aria-hidden="true"> ↗</span></span></a>'

gallery_people=list(dict.fromkeys(p['_person_slug'] for p in portraits))
gallery_art=[min((p for p in portraits if p['_person_slug']==ps),key=lambda p:p.get('_artwork_index',0)) for ps in gallery_people]
gallery_art=gallery_sort(gallery_art)
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
    event_text=f'<span class="section-label">{escape(str(setting("event_band_eyebrow","Exhibitions & talks")))}</span><h2>{escape(str(setting("event_band_heading","See the work in person")))}</h2><p>{escape(str(setting("event_band_description","Explore exhibitions, artist talks, and events featuring Pink Triangle Portraits.")))}</p>'
exhibition_home_image=setting('exhibitions_home_image','') or (next_event or {}).get('image','')
event_markup=f'<div class="event-band-copy">{event_text}<a class="button" href="/exhibitions/">{escape(str(setting("event_band_button_label","Exhibitions")))} →</a></div>'
if exhibition_home_image: event_markup+=f'<div class="event-band-visual">{img(exhibition_home_image,"Exhibitions and talks")}</div>'

hero_desktop=setting('hero_banner_desktop','') or setting('hero_banner','')
hero_mobile=setting('hero_banner_mobile','')
hero_source=f'<source media="(max-width:700px)" srcset="{attr(hero_mobile)}">' if hero_mobile else ''
hero_picture=(f'<picture class="hero-picture">{hero_source}<img src="{attr(hero_desktop or hero_mobile)}" alt="" loading="eager"></picture>' if (hero_desktop or hero_mobile) else hero_cards)
# Homepage hero text supports manual line breaks without changing its current defaults.
def hero_lines(value):
    return '<br>'.join(escape(part) for part in str(value or '').splitlines())
def safe_hero_spacing(key, default, lo, hi):
    try: value=int(setting(key,default))
    except (TypeError,ValueError): value=default
    return max(lo,min(hi,value))
hero_style=(f'--hero-copy-width:{safe_hero_spacing("hero_text_width",660,300,1000)}px;'
            f'--hero-eyebrow-gap:{safe_hero_spacing("hero_eyebrow_gap",14,0,90)}px;'
            f'--hero-title-gap:{safe_hero_spacing("hero_title_gap",14,0,90)}px;'
            f'--hero-tagline-gap:{safe_hero_spacing("hero_tagline_gap",22,0,90)}px')
hero_eyebrow=escape(str(setting('hero_eyebrow','Art / History / Remembrance / Queer Joy')))
hero_heading=hero_lines(setting('hero_headline','PINK TRIANGLE PORTRAITS'))
hero_tagline=hero_lines(setting('hero_tagline','Giving color and dignity to those who had it stripped away.'))
hero_overlay=max(0,min(95,int(setting('hero_overlay_opacity',40))))/100
hero_buttons=[]
for enabled,label_key,url_key,default_label,default_url,kind in [
    ('hero_button_show','hero_button_text','hero_button_url','View the Portraits','/portraits/','primary'),
    ('hero_button_2_show','hero_button_2_text','hero_button_2_url','Exhibitions & Events','/exhibitions/','secondary')]:
    if setting(enabled,True) is not False:
        label=str(setting(label_key,default_label) or default_label)
        url=str(setting(url_key,default_url) or default_url)
        if url.startswith('/') or url.startswith('https://') or url.startswith('http://'):
            hero_buttons.append(f'<a class="button hero-cta hero-cta--{kind}" href="{attr(url)}">{escape(label)}</a>')
hero_actions='<div class="hero-actions">'+''.join(hero_buttons)+'</div>' if hero_buttons else ''

# Shared CMS collection for project press coverage; sorted newest first.
press=[]
for f in (ROOT/'content/press').glob('*.md') if (ROOT/'content/press').exists() else []:
    try: item=load(f)
    except (ValueError,yaml.YAMLError): continue
    if item.get('published',True) is False: continue
    item['_date']=str(item.get('date') or '')[:10]
    press.append(item)
press.sort(key=lambda p:p['_date'],reverse=True)
class _PressMeta(HTMLParser):
    def __init__(self):
        super().__init__(); self.image=''; self.logo=''
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=='meta':
            key=(a.get('property') or a.get('name') or '').lower()
            if key in ('og:image','twitter:image') and not self.image: self.image=a.get('content','')
        elif tag=='link':
            rel=a.get('rel','').lower()
            if 'apple-touch-icon' in rel or 'icon' in rel:
                if not self.logo or 'apple-touch-icon' in rel: self.logo=a.get('href','')

def press_auto_image(url):
    """Best-effort publication icon, with optional article image metadata.
    No paid services, and failures never interrupt the site build.
    """
    parsed=urlparse(url)
    if parsed.scheme not in ('https','http') or not parsed.hostname: return ('','')
    host=parsed.hostname
    icon=f'https://www.google.com/s2/favicons?domain={quote(host)}&sz=128'
    thumbnail=''
    try:
        req=Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; PTPPressPreview/1.0)'})
        with urlopen(req,timeout=3) as response:
            raw=response.read(180000).decode('utf-8','replace')
            resolved=response.geturl()
        meta=_PressMeta(); meta.feed(raw)
        if meta.image: thumbnail=urljoin(resolved,meta.image)
        if meta.logo: icon=urljoin(resolved,meta.logo)
    except Exception: pass
    return (icon,thumbnail)

press_images={}
for item in press:
    url=str(item.get('url') or '').strip()
    if url.startswith(('https://','http://')) and not item.get('logo') and not item.get('image'):
        press_images[url]=press_auto_image(url)

def press_card(item):
    title=escape(str(item.get('title') or 'Press feature'))
    publication=escape(str(item.get('publication') or ''))
    day=escape(item['_date'])
    summary=render_md(item.get('summary') or item.get('body') or '')
    url=str(item.get('url') or '').strip()
    link=(f'<a class="text-link" href="{attr(url)}" target="_blank" rel="noopener noreferrer">'
          +escape(str(item.get('link_label') or 'Read feature'))+' ↗</a>') if url.startswith(('https://','http://')) else ''
    # Manual logo > manual thumbnail > automatic publication icon > article metadata thumbnail.
    logo=str(item.get('logo') or '').strip()
    thumb=str(item.get('image') or '').strip()
    auto_icon,auto_thumb=press_images.get(url,('',''))
    chosen=logo or thumb or auto_icon or auto_thumb
    fallback=auto_thumb if chosen==auto_icon and auto_thumb and auto_thumb!=auto_icon else ''
    picture=''
    if chosen:
        alt=str(item.get('publication') or item.get('title') or 'Publication')
        # If a detected publication icon is unavailable, try the article thumbnail.
        image_html=img(chosen,alt,'press-card-image')
        if fallback:
            image_html=image_html.replace(' loading="lazy">',f' data-fallback-src="{attr(fallback)}" loading="lazy">')
        picture=f'<div class="press-card-visual">{image_html}</div>' 
    if item.get('hide_image') is True: picture=''
    return (f'<article class="press-card">'
            +f'<div class="press-card-copy"><p class="press-meta">{publication}{" · " if publication and day else ""}{day}</p>'
            +f'<h3>{title}</h3><div class="rich">{summary}</div>{link}</div>'
            +picture+'</article>')
press_project=('''<section id="press-media" class="container project-press"><div class="section-head"><div><span class="section-label">In the press</span><h2>Press &amp; Media</h2></div></div><div class="press-list">'''+''.join(map(press_card,press))+'''</div></section>''') if press else ''
press_home=(f'<section class="container home-press"><div class="section-head"><div><span class="section-label">Recognition &amp; coverage</span><h2>{escape(str(setting("home_press_heading","In the Press")))}</h2></div><a class="text-link" href="/the-project/#press-media">{escape(str(setting("home_press_link_label","All press & media")))} →</a></div><div class="press-list">'+''.join(map(press_card,press[:3]))+'</div></section>') if press else ''

# Homepage spotlight selection is evaluated in the visitor's browser, so dates expire
# without a scheduled rebuild. CMS entries are the single source of truth.
def render_press_banner(screenshot_path, background_path, slug):
    """Compose one stable image, avoiding fragile browser positioning of laptop layers."""
    try:
        from PIL import Image, ImageOps
        from io import BytesIO
        def local_image(url):
            if not str(url).startswith('/assets/'): return None
            path=ROOT/str(url).lstrip('/')
            return Image.open(path).convert('RGBA') if path.is_file() else None
        shot=local_image(screenshot_path)
        if shot is None: return ''
        # Render a compact, self-contained laptop instead of enlarging/cropping
        # an external laptop asset. The screen and frame share exact coordinates.
        canvas=Image.new('RGBA',(1200,560),(237,56,140,255))
        bg=local_image(background_path)
        if bg is not None:
            canvas.alpha_composite(ImageOps.fit(bg,canvas.size,method=Image.Resampling.LANCZOS))
        from PIL import ImageDraw, ImageFilter
        d=ImageDraw.Draw(canvas)
        # The laptop extends below the fixed-height banner; the canvas crops it naturally.
        x0,y0,x1,y1=185,42,1015,705
        shadow=Image.new('RGBA',canvas.size,(0,0,0,0))
        sd=ImageDraw.Draw(shadow)
        sd.rounded_rectangle((x0+8,y0+12,x1+8,y1+12),radius=22,fill=(0,0,0,110))
        canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(15)))
        d=ImageDraw.Draw(canvas)
        d.rounded_rectangle((x0,y0,x1,y1),radius=21,fill='#15171b',outline='#5d6066',width=3)
        # A subtle screen bezel and top camera; no image extends outside the screen.
        sx0,sy0,sx1,sy1=x0+23,y0+31,x1-23,y1-20
        screen=ImageOps.fit(shot,(sx1-sx0,sy1-sy0),method=Image.Resampling.LANCZOS,centering=(0.5,0.0))
        canvas.alpha_composite(screen,(sx0,sy0))
        d=ImageDraw.Draw(canvas)
        d.ellipse((596,53,604,61),fill='#444950')
        target=OUT/'assets/generated-press'
        target.mkdir(parents=True,exist_ok=True)
        name=re.sub(r'[^a-z0-9-]+','-',slug.lower()).strip('-') or 'press'
        result=target/(name+'.png')
        canvas.convert('RGB').save(result,optimize=True)
        return '/assets/generated-press/'+result.name
    except Exception as exc:
        print(f'Warning: could not compose press banner {slug}: {exc}')
        return ''

def spotlight_picture(path, alt):
    return f'<div class="spotlight-image">{img(path, alt)}</div>' if path else ''

def spotlight_card(kind, heading, description, link, image='', meta='', start='', end='', label='', extra=''):
    href=link if str(link).startswith(('/', 'https://', 'http://')) else ''
    action=(f'<a class="text-link" href="{attr(href)}"'+(' target="_blank" rel="noopener noreferrer"' if href.startswith('http') else '')+f'>{escape(label or "Learn more")} →</a>') if href else ''
    return (f'<article class="spotlight-card spotlight-{attr(kind)}" data-kind="{attr(kind)}" data-start="{attr(start)}" data-end="{attr(end)}" {extra}>'
            +(spotlight_picture(render_press_banner(image, str(home_option('spotlight_press_background',home_option('spotlight_portrait_background','/assets/images/painted-background.jpg'))),heading) or image,heading) if kind=='press' and image else spotlight_picture(image,heading))
            +f'<div class="spotlight-copy"><span class="section-label">{escape(meta or kind.title())}</span><h2>{escape(str(heading))}</h2>'
            +(f'<p>{escape(str(description))}</p>' if description else '')+action+'</div></article>')

home_design=yaml.safe_load((ROOT/'content/settings/homepage.yml').read_text(encoding='utf-8')) or {} if (ROOT/'content/settings/homepage.yml').exists() else {}
def home_option(key, default):
    value=home_design.get(key,default)
    return default if value is None else value

spotlights=[]
# Each event is eligible starting N days before opening and until its end date.
for e in events:
    if e.get('homepage_feature',True) is False: continue
    start=e['_date'][:10]; end=e['_end'][:10]
    if not start or not end: continue
    spotlights.append(spotlight_card('exhibition',e.get('title','Exhibition'),e.get('location',''),e.get('link') or '/exhibitions/',e.get('image',''), 'Exhibitions & Events',start,end,str(home_option('spotlight_event_link_label','Event details'))))
for item in press:
    if item.get('homepage_feature',True) is False: continue
    pub=str(item.get('publication') or 'In the press')
    url=str(item.get('url') or '')
    logo=item.get('homepage_image') or item.get('logo') or item.get('image') or press_images.get(url,('',''))[0]
    spotlights.append(spotlight_card('press',item.get('title','Press feature'),item.get('summary',''),url or '/the-project/#press-media',logo,pub,item['_date'],item.get('homepage_until') or '', str(home_option('spotlight_press_link_label','Read feature')),f'data-days="{attr(item.get("homepage_days") or "")}" data-featured-priority="{str(item.get("homepage_priority",False)).lower()}"'))
if featured:
    spotlights.append(spotlight_card('portrait',featured.get('name','Latest portrait'),teaser,artwork_link(featured),featured.get('image',''),'The latest portrait','','',str(home_option('spotlight_portrait_link_label','Read their story'))))
else:
    spotlights.append(spotlight_card('portrait','The portraits','Explore the stories behind the artwork.','/portraits/','','The latest portrait'))
spotlights.append(spotlight_card('project',home_option('spotlight_project_heading','Portraits to remember. Stories to keep alive.'),home_option('spotlight_project_description','Pink Triangle Portraits is an ongoing art and research project by Bry Sharland, honoring queer people persecuted by the Nazi regime.'),'/the-project/','','The project','','',home_option('spotlight_project_link_label','Learn about the project')))
# Site-wide visual options for the automatically selected homepage cards.
spotlight_background=str(home_option('spotlight_portrait_background','/assets/images/painted-background.jpg'))
spotlight_height=max(110,min(420,int(home_option('spotlight_visual_height',220) or 220)))
spotlight_border=max(0,min(24,int(home_option('spotlight_portrait_border',9) or 0)))
spotlight_shadow='1' if home_option('spotlight_portrait_shadow',True) else '0'
spotlight_browser='1' if home_option('spotlight_press_browser',True) else '0'
spotlight_laptop_size=max(70,min(190,int(home_option('spotlight_press_laptop_size',118) or 118)))
spotlight_laptop_vertical=max(-80,min(80,int(home_option('spotlight_press_laptop_vertical',12) or 0)))
spotlight_press_background=str(home_option('spotlight_press_background',spotlight_background) or spotlight_background)
spotlight_markup=''.join(spotlights)
spotlight_config=(f'style="--spotlight-visual-height:{spotlight_height}px;--spotlight-portrait-border:{spotlight_border}px;--spotlight-portrait-background:url({attr(spotlight_background)});--spotlight-press-background:url({attr(spotlight_press_background)});--spotlight-laptop-scale:{spotlight_laptop_size / 100:.2f};--spotlight-laptop-offset:{spotlight_laptop_vertical}px;" data-portrait-shadow="{spotlight_shadow}" data-press-browser="{spotlight_browser}" data-event-lead="{attr(home_option("spotlight_exhibition_lead_days",60))}" '
                  f'data-press-days="{attr(home_option("spotlight_press_days",90))}" '
                  f'data-press-enabled="{str(home_option("spotlight_press_enabled",True)).lower()}" '
                  f'data-events-enabled="{str(home_option("spotlight_exhibitions_enabled",True)).lower()}"')
# The browser chooses 2 or 3 eligible cards; the portrait is always included.
spotlight_script=r"""<script>
(function(){
 const root=document.querySelector('[data-spotlights]');if(!root)return;
 const cards=[...root.querySelectorAll('.spotlight-card')];
 const now=new Date();now.setHours(0,0,0,0);
 const parse=s=>/^\d{4}-\d{2}-\d{2}$/.test(s||'')?new Date(s+'T00:00:00'):null;
 const days=(n)=>{const d=new Date(now);d.setDate(d.getDate()+n);return d};
 const num=(v,f)=>Number.isFinite(Number(v))&&v!==''?Number(v):f;
 const candidates=[];
 cards.forEach((card,index)=>{
  const kind=card.dataset.kind;let valid=false,sort=0;
  const start=parse(card.dataset.start),end=parse(card.dataset.end);
  if(kind==='exhibition' && root.dataset.eventsEnabled!=='false' && start && end){
   valid=now<=end && start<=days(num(root.dataset.eventLead,60));sort=-start.getTime();
  } else if(kind==='press' && root.dataset.pressEnabled!=='false' && start){
   const expiry=end||new Date(start.getFullYear(),start.getMonth(),start.getDate()+num(card.dataset.days,num(root.dataset.pressDays,90)));
   valid=(now>=start && now<=expiry)||card.dataset.featuredPriority==='true';sort=start.getTime()+(card.dataset.featuredPriority==='true'?1e16:0);
  } else if(kind==='portrait'||kind==='project'){valid=true}
  if(valid)candidates.push({card,index,kind,sort});
 });
 const event=candidates.filter(x=>x.kind==='exhibition').sort((a,b)=>b.sort-a.sort)[0];
 const press=candidates.filter(x=>x.kind==='press').sort((a,b)=>b.sort-a.sort)[0];
 const portrait=candidates.find(x=>x.kind==='portrait');
 const project=candidates.find(x=>x.kind==='project');
 const selected=[event,press,portrait].filter(Boolean);
 if(selected.length<2 && project)selected.push(project);
 const keep=new Set(selected.map(x=>x.card));
 cards.forEach(card=>{card.hidden=!keep.has(card)});
 selected.forEach((x,i)=>{root.appendChild(x.card);x.card.classList.toggle('spotlight-first',i===0)});
 root.classList.toggle('spotlights-three',selected.length===3);
 root.classList.toggle('spotlights-two',selected.length===2);
 root.classList.add('spotlights-ready');
})();
</script>"""

home=f'''<section class="home-hero" style="min-height:{attr(setting('hero_height',500))}px;--hero-darkness:{hero_overlay};{hero_style}"><div class="home-portrait-strip">{hero_picture}</div><div class="home-hero-overlay"><div class="container"><span class="hero-eyebrow">{hero_eyebrow}</span><h1>{hero_heading}</h1><p>{hero_tagline}</p>{hero_actions}</div></div></section><section class="home-intro home-spotlights container"{section_style("intro")}><div class="spotlight-grid" data-spotlights {spotlight_config}>{spotlight_markup}</div></section>{spotlight_script}<section class="event-band" style="background-image:linear-gradient(90deg,rgba(4,28,40,.78),rgba(4,28,40,.12)),url('{attr(setting("paint_background","/assets/images/715931084-background-web.jpg"))}')"><div class="container event-grid">{event_markup}</div></section><section class="container gallery-preview"{section_style("gallery")}><div class="section-head"><div><span class="section-label">{escape(str(home_option("gallery_preview_eyebrow","Explore the portraits")))}</span><h2>{escape(str(home_option("gallery_preview_heading","Every person has a story.")))}</h2></div><a class="text-link" href="/portraits/">{escape(str(home_option("gallery_preview_link_label","Browse all portraits")))} →</a></div><div class="portrait-grid">{''.join(portrait_card(p) for p in [next(a for a in newest if a['_person_slug']==ps) for ps in dict.fromkeys(a['_person_slug'] for a in newest)][:5])}</div></section>{press_home}'''
write('',page('Home','Home',home))

for route in ['the-project','the-history','about-the-artist','contact','shop']:
    file=ROOT/'content/pages'/f'{route}.md'
    if not file.exists():continue
    data=load(file)
    title=str(data.get('title',route.title()))
    supporting=data.get('supporting_images') or []
    callouts=data.get('callouts') or []
    body=render_section_images(data.get('body'),supporting,callouts)
    content=heading('Pink Triangle Portraits',title,data.get('subtitle',''),data.get('hero_image',''),data.get('hero_mobile_image',''))+(f'<div class="container editorial-with-images rich">{body}</div>' if body.strip() else '')

    if route == 'the-project':
        # Project-only editorial sidebar. Existing page body and callouts remain independent.
        if data.get('project_sidebar_enabled', True) is not False:
            side_image=str(data.get('project_sidebar_image') or '').strip()
            side_heading=str(data.get('project_sidebar_heading') or '').strip()
            side_body=str(data.get('project_sidebar_body') or '').strip()
            side_callout=str(data.get('project_sidebar_callout') or '').strip()
            show_press=data.get('project_sidebar_press_enabled',True) is not False
            press_title=str(data.get('project_sidebar_press_heading') or 'Press & Media').strip()
            press_intro=str(data.get('project_sidebar_press_intro') or '').strip()
            press_limit=data.get('project_sidebar_press_limit',0)
            try: press_limit=max(0,min(30,int(press_limit or 0)))
            except (TypeError,ValueError): press_limit=0
            visible_press=press[:press_limit] if press_limit else press
            sidebar_parts=[]
            if side_image: sidebar_parts.append(f'<div class="project-side-art">{img(side_image,str(data.get("project_sidebar_image_alt") or "Abstract painted artwork"))}</div>')
            if side_heading: sidebar_parts.append(f'<h2 class="project-side-heading">{escape(side_heading)}</h2>')
            if side_body: sidebar_parts.append(f'<div class="project-side-rich rich">{render_md(side_body)}</div>')
            if side_callout: sidebar_parts.append(f'<aside class="project-side-note rich">{render_md(side_callout)}</aside>')
            if show_press and visible_press:
                font=str(data.get('project_press_title_font') or 'DM Sans')
                if font not in ('DM Sans','Barlow Condensed','Georgia'): font='DM Sans'
                try: title_size=max(14,min(32,int(data.get('project_press_title_size') or 19)))
                except (TypeError,ValueError): title_size=19
                try: title_weight=int(data.get('project_press_title_weight') or 600)
                except (TypeError,ValueError): title_weight=600
                if title_weight not in (400,500,600,700,800,900): title_weight=600
                try: image_width=max(55,min(180,int(data.get('project_press_image_width') or 95)))
                except (TypeError,ValueError): image_width=95
                try: rule_gap=max(8,min(45,int(data.get('project_press_rule_spacing') or 18)))
                except (TypeError,ValueError): rule_gap=18
                rule_color=str(data.get('project_press_rule_color') or '#d7d7d7')
                if not re.fullmatch(r'#[0-9a-fA-F]{6}',rule_color): rule_color='#d7d7d7'
                sidebar_parts.append(f'<section id="press-media" class="project-side-press {"press-images-hidden" if data.get("project_press_show_images",True) is False else ""}" style="--press-title-font:{attr(font)};--press-title-size:{title_size}px;--press-title-weight:{title_weight};--press-image-width:{image_width}px;--press-rule-spacing:{rule_gap}px;--press-rule-color:{rule_color}"><div class="section-head"><div><span class="section-label">In the press</span><h2>{escape(press_title)}</h2></div></div>'+(f'<div class="rich project-press-intro">{render_md(press_intro)}</div>' if press_intro else '')+'<div class="press-list">'+''.join(map(press_card,visible_press))+'</div></section>')
            if sidebar_parts:
                content=heading('Pink Triangle Portraits',title,data.get('subtitle',''),data.get('hero_image',''),data.get('hero_mobile_image',''))+f'<div class="container project-two-column"><div class="project-main editorial-with-images rich">{body}</div><aside class="project-sidebar" aria-label="Project features and press">{"".join(sidebar_parts)}</aside></div>'
        else:
            content += press_project

    if route == 'contact':
        def contact_show(key): return data.get(key, True) is not False
        def contact_box(kind, title, body, extra=''):
            return f'<aside class="ptp-contact-{kind}" aria-label="{attr(title)}"><h2>{escape(title)}</h2><div class="rich">{render_md(body)}</div>{extra}</aside>'
        contact_cards=[]
        if contact_show('contact_research_visible'):
            contact_cards.append(contact_box('research',data.get('contact_research_heading') or 'Looking for Historical Sources?',data.get('contact_research_text') or 'Bry may be able to help with research.', '<a class="text-link" href="#ptp-contact-title">Ask about research →</a>'))
        if contact_show('contact_social_visible'):
            socials=''.join(f'<a href="{attr(setting(k+"_url"))}" target="_blank" rel="noopener noreferrer">{escape(k.title())}</a>' for k in ('instagram','bluesky','tiktok') if setting(k+'_url'))
            contact_cards.append(contact_box('social',data.get('contact_social_heading') or 'Follow the Project',data.get('contact_social_text') or '',f'<div class="ptp-social-links">{socials}</div>'))
        if data.get('contact_card_order') == 'social_first': contact_cards.reverse()
        intro=render_md(data.get('contact_intro') or 'For exhibition inquiries, collaborations, support, or questions about the project, please use the form below.')
        form_title=escape(str(data.get('contact_form_heading') or 'Get in Touch'))
        form_html='<form id="ptp-contact-form" class="ptp-contact-form" action="https://formspree.io/f/mbggejvn" method="POST" accept-charset="UTF-8"><div class="ptp-contact-fields"><label for="ptp-name">Name <span aria-hidden="true">*</span></label><input id="ptp-name" name="name" type="text" autocomplete="name" required maxlength="150"><label for="ptp-email">Email <span aria-hidden="true">*</span></label><input id="ptp-email" name="email" type="email" autocomplete="email" required maxlength="254"><label for="ptp-subject">Subject <span aria-hidden="true">*</span></label><input id="ptp-subject" name="subject" type="text" required maxlength="200"><label for="ptp-message">Message <span aria-hidden="true">*</span></label><textarea id="ptp-message" name="message" rows="7" required maxlength="10000"></textarea></div><div class="ptp-contact-honeypot" aria-hidden="true"><label for="ptp-website">Leave this field empty</label><input id="ptp-website" type="text" name="_gotcha" tabindex="-1" autocomplete="off"></div><button class="button ptp-contact-submit" type="submit">Send message</button><p id="ptp-contact-status" class="ptp-contact-status" role="status" aria-live="polite"></p><noscript><p>JavaScript is disabled. You can still submit this form; Formspree will handle the response.</p></noscript></form>'
        form_html=form_html.replace('Send message</button>',escape(str(data.get('contact_button_text') or 'Send message'))+'</button>')
        left=f'<div class="ptp-contact-main"><div class="ptp-contact-intro"><h2 id="ptp-contact-title">{form_title}</h2><div class="rich">{intro}</div></div>{form_html if contact_show("contact_form_visible") else ""}</div>'
        right=f'<div class="ptp-contact-sidebar">{"".join(contact_cards)}</div>' if contact_cards else ''
        content += f'<section class="container ptp-contact-layout" style="--contact-side-width:{max(20,min(50,int(data.get("contact_sidebar_width") or 35)))}%">{left}{right}</section>'
    write(route,page(title,title,content))

# Permanent QR destination used on printed materials. Never redirect or remove this route.
qr_file=ROOT/'content/pages/qr.md'
qr_data=load(qr_file) if qr_file.exists() else {}
qr_links=[]
for key,label in [('instagram','Instagram'),('bluesky','Bluesky'),('tiktok','TikTok')]:
    if qr_data.get('show_'+key,True) and setting(key+'_url'):
        qr_links.append(f'<a class="qr-social-button" href="{attr(setting(key+"_url"))}" target="_blank" rel="noopener noreferrer"><img src="/assets/images/social-{key}-white.png" alt="" aria-hidden="true"><span>{escape(str(qr_data.get(key+"_label") or label))}</span><span class="qr-arrow" aria-hidden="true">↗</span></a>')
qr_gallery='<a class="qr-gallery-button" href="/portraits/">'+escape(str(qr_data.get('gallery_label') or 'Explore the Portrait Gallery'))+'</a>' if qr_data.get('show_gallery',True) else ''
qr_logo=qr_data.get('logo_image') or setting('logo_image','')
qr_logo_html=img(qr_logo,'Pink Triangle Portraits logo') if qr_logo else '<div class="qr-wordmark">PINK TRIANGLE<br>PORTRAITS</div>'
qr_html=f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="index,follow"><title>Follow Pink Triangle Portraits</title><link rel="stylesheet" href="/assets/site.css"><style>:root{{--qr-accent:{attr(qr_data.get('accent_color') or '#ed398b')};--qr-bg:{attr(qr_data.get('background_color') or '#ffffff')};}}</style></head><body class="qr-landing"><main class="qr-wrap"><a href="/" class="qr-logo-link" aria-label="Visit Pink Triangle Portraits">{qr_logo_html}</a><h1>{escape(str(qr_data.get('heading') or 'Follow the Project'))}</h1><p>{escape(str(qr_data.get('intro') or 'Discover new portraits, stories, exhibitions, and project updates.'))}</p><div class="qr-social-list">{''.join(qr_links)}</div>{qr_gallery}<a class="qr-home" href="/">Visit Pink Triangle Portraits</a></main></body></html>"""
write('qr',qr_html)

# Date-aware exhibitions: all items are emitted once, then categorized on each visit.
exhibitions_file=ROOT/'content/pages/exhibitions.md'
exhibitions_data=load(exhibitions_file) if exhibitions_file.exists() else {}
# The legacy Follow the project block is rendered as a designed sidebar card,
# not as a narrow continuation of the historical exhibition list.
exhibitions_body=str(exhibitions_data.get('body') or '')
exhibitions_body=re.sub(r'(?ims)^#{2,4}\s+Follow the project\s*$.*?(?=^#{2,4}\s+|\Z)', '', exhibitions_body).rstrip()
exhibitions_html=render_md(exhibitions_body)
year_heading=re.compile(r'<h([2-4])>\s*(20\d{2})\s*</h\1>',re.I)
match_years=list(year_heading.finditer(exhibitions_html))
intro_html=exhibitions_html[:match_years[0].start()] if match_years else exhibitions_html
legacy=[]
for i,m in enumerate(match_years):
    end=match_years[i+1].start() if i+1<len(match_years) else len(exhibitions_html)
    legacy.append((int(m.group(2)),exhibitions_html[m.end():end]))
event_items=[]
for e in events:
    if not e['_date']:continue
    start=e['_date']; end=max(e['_end'],start)
    photo=img(e.get('image'),e.get('title',''),'event-cover') if e.get('image') else ''
    body=(f'<span class="section-label">{escape(start)}'+(f' – {escape(end)}' if end!=start else '')+'</span>'
         +f'<h3>{escape(str(e.get("title","")))}</h3>'
         +''.join(f'<p class="event-detail"><strong>{label}:</strong> {escape(str(e.get(field)))}</p>' for field,label in [('venue','Venue'),('address','Address'),('reception','Opening reception'),('hours','Gallery hours')] if e.get(field))
         +(f'<p>{escape(str(e.get("location","")))}</p>' if e.get('location') else '')
         +f'<div class="rich">{render_md(e.get("body"))}</div>'
         +(f'<p><a class="text-link" href="{attr(e["link"])}">Event details ↗</a></p>' if e.get('link') else ''))
    event_items.append(f'<article class="exhibition-entry" data-start="{attr(start)}" data-end="{attr(end)}" data-year="{attr(start[:4])}" data-featured="{str(e.get('featured',False)).lower()}" data-order="{attr(e.get('featured_order',10))}"><div class="exhibition-entry-copy">{body}</div><div class="exhibition-entry-image">{photo}</div></article>')
legacy_html=''.join(f'<section class="exhibition-legacy-year" data-year="{y}"><div>{body}</div></section>' for y,body in legacy)
featured_enabled=exhibitions_data.get('exhibitions_featured_enabled',True) is not False
featured_heading=escape(str(exhibitions_data.get('exhibitions_featured_heading') or 'Featured & Upcoming'))
featured_empty=escape(str(exhibitions_data.get('exhibitions_featured_empty') or 'New exhibitions will be announced here.'))
follow_enabled=exhibitions_data.get('exhibitions_follow_enabled',True) is not False
follow_title=escape(str(exhibitions_data.get('exhibitions_follow_heading') or 'Follow the Project'))
follow_text=escape(str(exhibitions_data.get('exhibitions_follow_text') or 'Follow the project for updates on upcoming shows, new portraits, and the incredible stories of queer history behind them.'))
follow_color=str(exhibitions_data.get('exhibitions_follow_background') or '#082d3c')
featured_color=str(exhibitions_data.get('exhibitions_featured_background') or '#fff0f6')
# Only allow hex colors in inline CSS; otherwise fall back to safe defaults.
if not re.fullmatch(r'#[0-9a-fA-F]{6}',follow_color):follow_color='#082d3c'
if not re.fullmatch(r'#[0-9a-fA-F]{6}',featured_color):featured_color='#fff0f6'
follow_links=''.join(f'<a class="exhibitions-follow-link" href="{attr(setting(key+"_url"))}" target="_blank" rel="noopener noreferrer"><img src="/assets/images/social-{key}-white.png" alt="" aria-hidden="true"><span>{label}</span></a>' for key,label in [('instagram','Instagram'),('bluesky','Bluesky'),('tiktok','TikTok')] if setting(key+'_url'))
follow_card=(f'<section class="exhibitions-follow-card" style="--exhibitions-follow-bg:{attr(follow_color)}"><div class="exhibitions-follow-kicker">PINK TRIANGLE PORTRAITS</div><h2>{follow_title}</h2><div class="exhibitions-follow-accent"></div><p>{follow_text}</p><div class="exhibitions-follow-links">{follow_links}</div></section>') if follow_enabled else ''

exhibition_content=(f'<div class="container exhibitions-editorial rich exhibitions-redesign">'
    +(f'<div class="exhibitions-intro">{intro_html}</div>' if intro_html.strip() else '')
    +f'<div class="exhibitions-columns{"" if (featured_enabled or follow_enabled) else " exhibitions-no-sidebar"}">'
    +'<div class="exhibitions-history">'
    +'<section id="exhibitions-upcoming" class="exhibition-group" hidden><h2>Upcoming Exhibitions</h2><div class="exhibition-group-items"></div></section>'
    +'<section id="exhibitions-current" class="exhibition-group" hidden><div class="exhibition-group-items"></div></section>'
    +'<section id="exhibitions-past" class="exhibition-group" hidden><h2>Past Exhibitions</h2><div class="exhibition-group-items"></div></section></div>'
    +(f'<aside class="exhibitions-sidebar"><section class="exhibitions-featured" style="--exhibitions-featured-bg:{attr(featured_color)}"><h2>{featured_heading}</h2><div id="exhibitions-featured-list"></div><p id="exhibitions-featured-empty">{featured_empty}</p></section>{follow_card}</aside>' if featured_enabled else (f'<aside class="exhibitions-sidebar">{follow_card}</aside>' if follow_enabled else ''))
    +'</div><div id="exhibition-event-source" hidden>'+''.join(event_items)+'</div>'
    +'<div id="exhibition-legacy-source" hidden>'+legacy_html+'</div></div>')
write('exhibitions',page('Exhibitions',str(exhibitions_data.get('title') or 'Exhibitions'),
    heading('Pink Triangle Portraits',str(exhibitions_data.get('title') or 'Exhibitions'),
        exhibitions_data.get('subtitle',''),exhibitions_data.get('hero_image',''),
        exhibitions_data.get('hero_mobile_image',''))+exhibition_content))

search=f'''<section class="container portraits-list"><div class="search-tools"><label for="portrait-search">Search by name</label><input id="portrait-search" type="search" placeholder="Find a portrait…" autocomplete="off"><span id="result-count" aria-live="polite"></span></div><div class="portrait-grid searchable">{cards}</div><p id="empty-search" hidden>No matching portraits.</p></section>'''
write('portraits',page('The Portraits','The Portraits',heading('The collection','The Portraits','Explore the artwork and the lives behind each portrait.',load(ROOT / 'content/pages/portraits.md').get('hero_image','') if (ROOT / 'content/pages/portraits.md').exists() else '',load(ROOT / 'content/pages/portraits.md').get('hero_mobile_image','') if (ROOT / 'content/pages/portraits.md').exists() else '')+(f'<section class="container editorial-copy portraits-intro rich">{render_md(load(ROOT / "content/pages/portraits.md").get("body"))}</section>' if (ROOT / 'content/pages/portraits.md').exists() else '')+search))

person_slugs=list(dict.fromkeys(p['_person_slug'] for p in portraits))
for i,person_slug in enumerate(person_slugs):
    person=people[person_slug]
    artworks=sorted((p for p in portraits if p['_person_slug']==person_slug),key=lambda p:p.get('_artwork_index',0))
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
    content=f'''<div class="container portrait-breadcrumb"><a href="/portraits/">← All portraits</a></div><section class="container person-detail">{left}<article class="portrait-bio"><h1>{escape(name)}</h1><p class="years">{escape(str(person.get('years','')))}</p>{artwork_meta}<div class="accent-rule"></div><div class="rich">{bio}</div></article></section><nav class="container prev-next bio-editorial-nav" aria-label="Browse portraits"><a class="bio-nav-previous" href="/people/{prev['_slug']}/"><span class="bio-nav-label">← Previous portrait</span><span class="bio-nav-name">{escape(str(prev.get('name','Previous')))}</span></a><a class="bio-nav-all" href="/portraits/">All Portraits</a><a class="bio-nav-next" href="/people/{nxt['_slug']}/"><span class="bio-nav-label">Next portrait →</span><span class="bio-nav-name">{escape(str(nxt.get('name','Next')))}</span></a></nav>'''
    write('people/'+person_slug,page(name,'The Portraits',content,desc=person.get('summary','')))
# old portrait routes redirect to shared person page
for p in portraits:
    dest='/people/'+p['_person_slug']+'/'
    write('portraits/'+p['_slug'],f'<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url={attr(dest)}"><link rel="canonical" href="{attr(dest)}"><a href="{attr(dest)}">Read biography</a>')
print(f'Built {len(portraits)} artworks, {len(person_slugs)} people and {len(events)} events')
