const toggle=document.querySelector('.menu-toggle');
const nav=document.querySelector('#main-nav');
if(toggle&&nav){toggle.addEventListener('click',()=>{const open=nav.classList.toggle('open');toggle.setAttribute('aria-expanded',String(open));toggle.setAttribute('aria-label',open?'Close menu':'Open menu');toggle.textContent=open?'×':'☰';});document.addEventListener('click',e=>{if(!e.target.closest('.site-header')){nav.classList.remove('open');toggle.setAttribute('aria-expanded','false');toggle.textContent='☰';}});}
const search=document.querySelector('#portrait-search');
if(search){const cards=[...document.querySelectorAll('.searchable .portrait-card')];const count=document.querySelector('#result-count');const empty=document.querySelector('#empty-search');const update=()=>{const q=search.value.trim().toLocaleLowerCase();let shown=0;cards.forEach(card=>{const match=card.textContent.toLocaleLowerCase().includes(q);card.hidden=!match;if(match)shown++;});count.textContent=shown+' portrait'+(shown===1?'':'s');empty.hidden=shown>0;};search.addEventListener('input',update);update();}
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
