"""Quarterly, free press-link monitor. Creates one GitHub issue per failing URL."""
import json
import os
import re
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, quote
from urllib.request import Request, urlopen
import yaml

ROOT=Path(__file__).resolve().parents[1]
API='https://api.github.com'
TOKEN=os.environ.get('GITHUB_TOKEN','')
REPO=os.environ.get('GITHUB_REPOSITORY','')
LABEL='press-link-check'

def request(url,method='GET',payload=None,headers=None,timeout=18):
    h={'User-Agent':'PTP-Press-Link-Monitor/1.0 (+GitHub Actions)',**(headers or {})}
    if TOKEN and url.startswith(API):h['Authorization']='Bearer '+TOKEN
    if payload is not None:
        payload=json.dumps(payload).encode();h['Content-Type']='application/json'
    req=Request(url,data=payload,headers=h,method=method)
    with urlopen(req,timeout=timeout) as resp:return resp.status,resp.read(500000)

def check(url):
    """Only explicit 404/410 is a confirmed missing page. Others are inconclusive."""
    for attempt in range(2):
        try:
            request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; PressLinkCheck/1.0)'})
            return 'ok','Available'
        except HTTPError as e:
            if e.code in (404,410):
                if attempt==0:time.sleep(2);continue
                return 'missing',f'HTTP {e.code}'
            if e.code in (401,403,429):return 'unknown',f'HTTP {e.code} (may block automated checks)'
            if attempt==0:time.sleep(2);continue
            return 'unknown',f'HTTP {e.code}'
        except (URLError,TimeoutError,ValueError) as e:
            if attempt==0:time.sleep(2);continue
            return 'unknown',str(e)[:120]
    return 'unknown','Unverified'

def api(path,method='GET',payload=None):
    status,raw=request(f'{API}/repos/{REPO}{path}',method,payload,{'Accept':'application/vnd.github+json'})
    return json.loads(raw) if raw else None

def main():
    if not TOKEN or not REPO:
        raise SystemExit('GITHUB_TOKEN and GITHUB_REPOSITORY are required')
    # Existing issues prevent repeat alerts each quarter.
    issues=api(f'/issues?state=open&per_page=100&labels={LABEL}')
    existing={m.group(1):issue for issue in issues if (m:=re.search(r'<!-- press-url: (.*?) -->',issue.get('body','')))}
    owner=REPO.split('/')[0]
    missing=0;unknown=0;checked=0
    for file in sorted((ROOT/'content/press').glob('*.md')):
        raw=file.read_text(encoding='utf-8')
        match=re.match(r'\A---\s*\n(.*?)\n---',raw,re.S)
        if not match:continue
        data=yaml.safe_load(match.group(1)) or {}
        if data.get('published',True) is False:continue
        url=str(data.get('url') or '').strip()
        if urlparse(url).scheme not in ('http','https'):continue
        checked+=1
        status,reason=check(url)
        if status=='unknown':
            unknown+=1;print(f'UNVERIFIED: {url} — {reason}');continue
        if status=='missing':
            missing+=1
            if url in existing:
                print('Already reported:',url);continue
            title=f'Press link needs review: {data.get("publication") or data.get("title") or file.stem}'
            body=(f'<!-- press-url: {url} -->\n'
                  f'@{owner} — a press article appears to be unavailable after two checks.\n\n'
                  f'**Article:** {data.get("title",file.stem)}\n\n'
                  f'**Publication:** {data.get("publication", "Not specified")}\n\n'
                  f'**URL:** {url}\n\n**Result:** {reason}\n\n'
                  f'Please confirm manually, then update the URL in **Pages CMS → Press & Media**. '
                  f'Close this issue when resolved. This is not proof the article was removed permanently.')
            api('/issues','POST',{'title':title,'body':body,'labels':[LABEL]})
            print('Created issue:',title)
        else:print('OK:',url)
    print(f'Checked {checked}; confirmed missing {missing}; inconclusive {unknown}')

if __name__=='__main__':main()
