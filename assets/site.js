const toggle=document.querySelector('.menu-toggle');
const nav=document.querySelector('#main-nav');
if(toggle&&nav){toggle.addEventListener('click',()=>{const open=nav.classList.toggle('open');toggle.setAttribute('aria-expanded',String(open));toggle.setAttribute('aria-label',open?'Close menu':'Open menu');toggle.textContent=open?'×':'☰';});document.addEventListener('click',e=>{if(!e.target.closest('.site-header')){nav.classList.remove('open');toggle.setAttribute('aria-expanded','false');toggle.textContent='☰';}});}
// Live portrait filtering. Explicit display control avoids legacy display:block rules.
const search=document.querySelector('#portrait-search');
if(search){
  const cards=Array.from(document.querySelectorAll('.portrait-grid.searchable .portrait-card'));
  const count=document.querySelector('#result-count');
  const empty=document.querySelector('#empty-search');
  const normalize=value=>(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase().trim();
  const names=[...new Set(cards.map(card=>card.querySelector('.portrait-name')?.textContent.replace('↗','').trim()||'').filter(Boolean))].sort((a,b)=>a.localeCompare(b));
  const suggestions=document.createElement('datalist');
  suggestions.id='portrait-name-suggestions';
  names.forEach(name=>{const option=document.createElement('option');option.value=name;suggestions.appendChild(option);});
  search.after(suggestions);
  search.setAttribute('list',suggestions.id);
  const update=()=>{
    const query=normalize(search.value);
    let shown=0;
    cards.forEach(card=>{
      const name=card.querySelector('.portrait-name')?.textContent||card.textContent;
      const matches=normalize(name).includes(query);
      card.hidden=!matches;
      if(matches){card.style.removeProperty('display');shown++;}
      else{card.style.setProperty('display','none','important');}
    });
    if(count)count.textContent=shown+' '+(shown===1?'person':'people');
    if(empty)empty.hidden=shown!==0;
  };
  search.addEventListener('input',update);
  search.addEventListener('change',update);
  update();
}
const copy=document.querySelector('.copy-link');if(copy){copy.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(location.href);copy.textContent='Link copied';}catch(e){copy.textContent='Copy from address bar';}});}

// Keep artwork information alongside the biography, synchronized with thumbnails.
document.querySelectorAll('.artwork-thumbnails').forEach(group=>{
  const section=group.closest('.person-detail');if(!section)return;
  const main=section.querySelector('.selected-artwork-image');
  const details=section.querySelector('.selected-artwork-details');
  group.querySelectorAll('.artwork-thumb').forEach(button=>button.addEventListener('click',()=>{
    main.src=button.dataset.image;main.alt=button.dataset.alt||'Portrait';
    details.innerHTML=button.dataset.details||'';details.hidden=!button.dataset.details;
    group.querySelectorAll('.artwork-thumb').forEach(b=>{const selected=b===button;b.classList.toggle('is-selected',selected);b.setAttribute('aria-pressed',String(selected));});
  }));
});

// Submit the contact form without leaving the site; retain standard POST fallback.
(function(){
  const form=document.getElementById('ptp-contact-form');
  if(!form)return;
  const status=document.getElementById('ptp-contact-status');
  const button=form.querySelector('button[type="submit"]');
  form.addEventListener('submit',async function(event){
    if(!window.fetch || !window.FormData)return;
    event.preventDefault();
    if(!form.reportValidity())return;
    button.disabled=true;
    status.dataset.state='';
    status.textContent='Sending your message…';
    try{
      const response=await fetch(form.action,{method:'POST',body:new FormData(form),headers:{Accept:'application/json'}});
      if(!response.ok)throw new Error('Submission failed');
      form.reset();
      status.dataset.state='success';
      status.textContent='Thank you! Your message has been sent.';
    }catch(error){
      status.dataset.state='error';
      status.textContent='Your message could not be sent. Please try again.';
    }finally{button.disabled=false;}
  });
})();

// Keep supporting images from stretching editorial sections far beyond their copy.
// Width is reduced proportionally, never cropped. Per-image CMS toggle opts out.
(()=>{
  const sections=[...document.querySelectorAll('.editorial-section')];
  if(!sections.length)return;
  let queued=false;
  function fit(){
    queued=false;
    const desktop=window.matchMedia('(min-width:701px)').matches;
    sections.forEach(section=>{
      const copy=section.querySelector('.editorial-section-copy');
      const media=section.querySelector('.editorial-section-media');
      if(!copy||!media)return;
      const figures=[...media.querySelectorAll('.editorial-figure[data-auto-fit="true"]')];
      figures.forEach(f=>{f.style.removeProperty('max-width');f.style.removeProperty('width');});
      if(!desktop||section.classList.contains('editorial-section--full')||figures.length!==1||media.children.length!==1)return;
      const figure=figures[0], img=figure.querySelector('img');
      if(!img||!img.complete||!img.naturalWidth||!img.naturalHeight)return;
      const caption=figure.querySelector('figcaption');
      const captionHeight=caption?caption.getBoundingClientRect().height+12:0;
      const explicit=Number(figure.dataset.maxHeight)||0;
      const copyHeight=copy.getBoundingClientRect().height;
      let available=Math.max(100,copyHeight-captionHeight);
      if(explicit>0)available=Math.min(available,explicit);
      const mediaWidth=media.getBoundingClientRect().width;
      const imageHeightAtFullWidth=mediaWidth*img.naturalHeight/img.naturalWidth;
      if(imageHeightAtFullWidth>available){
        figure.style.maxWidth=Math.max(1,Math.min(mediaWidth,available*img.naturalWidth/img.naturalHeight))+'px';
      }
    });
  }
  function schedule(){if(queued)return;queued=true;requestAnimationFrame(fit);}
  window.addEventListener('resize',schedule,{passive:true});
  document.querySelectorAll('.editorial-section-media img').forEach(img=>img.addEventListener('load',schedule));
  if(document.fonts?.ready)document.fonts.ready.then(schedule);
  schedule();
})();

// Open external website links in a separate tab. Internal and anchor links stay here.
(function(){
  document.querySelectorAll('a[href]').forEach(link=>{
    const href=link.getAttribute('href');
    if(!href || href.startsWith('#'))return;
    try{
      const url=new URL(href,window.location.href);
      if(!['http:','https:'].includes(url.protocol))return;
      const host=url.hostname.toLowerCase().replace(/^www\./,'');
      const local=window.location.hostname.toLowerCase().replace(/^www\./,'');
      const isInternal=host===local || host==='pinktriangleportraits.com';
      if(isInternal)return;
      link.setAttribute('target','_blank');
      link.setAttribute('rel',[...new Set((link.getAttribute('rel')||'').split(/\s+/).filter(Boolean).concat(['noopener','noreferrer']))].join(' '));
    }catch(error){/* Leave malformed URLs unchanged. */}
  });
})();
