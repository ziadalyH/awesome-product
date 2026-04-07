"""Proxy route that serves the upstream MkDocs site with injected AI suggestion UI."""

import httpx
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from bs4 import BeautifulSoup

router = APIRouter(tags=["proxy"])

DOCS_BASE = "https://openai.github.io/openai-agents-python"

EARLY_SCRIPT = """
(function(){
  /* Silence cross-origin history errors from MkDocs before its scripts run */
  ['pushState','replaceState'].forEach(function(m){
    var o=history[m].bind(history);
    history[m]=function(){try{o.apply(history,arguments);}catch(e){}};
  });

  /* Intercept link clicks in capture phase — runs before MkDocs registers its handlers */
  var BASE='https://openai.github.io/openai-agents-python/';
  document.addEventListener('click',function(e){
    var a=e.target.closest('a[href]');
    if(!a||!a.href) return;
    if(a.href.indexOf(BASE)===0){
      e.preventDefault();e.stopPropagation();
      var rel=a.href.replace(BASE,'').replace(/\\/$/,'');
      var hash='';
      var hi=rel.indexOf('#');
      if(hi>=0){hash=rel.slice(hi);rel=rel.slice(0,hi);}
      if(!rel&&hash){
        var el=document.querySelector(hash);
        if(el) el.scrollIntoView({behavior:'smooth',block:'start'});
      } else {
        window.parent.postMessage({type:'navigate',page:rel,hash:hash},'*');
      }
    }
  },true);

  /* ── Suggestion highlights + popups (rendered via postMessage) ── */
  function esc(s){
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  function buildPopup(sug){
    var ad=sug.status==='approved'?' disabled':'';
    var rd=sug.status==='rejected'?' disabled':'';
    return '<div class="ai-popup ai-popup--'+sug.status+'" data-sid="'+esc(sug.id)+'">'
      +'<div class="ai-popup__header">'
      +'<span class="ai-popup__title">&#x2726; AI Suggestion</span>'
      +'<span class="ai-badge ai-badge--'+sug.status+'">'+sug.status+'</span>'
      +'</div>'
      +'<p class="ai-popup__reason"><strong>Why:</strong> '+esc(sug.reason)+'</p>'
      +'<div class="ai-tabs">'
      +'<button class="ai-tab active" data-tab="suggested">Suggested</button>'
      +'<button class="ai-tab" data-tab="current">Current</button>'
      +'</div>'
      +'<pre class="ai-pre ai-pre--suggested">'+esc(sug.suggested_content)+'</pre>'
      +'<pre class="ai-pre ai-pre--current" style="display:none">'+esc(sug.current_content)+'</pre>'
      +'<textarea class="ai-textarea" style="display:none">'+esc(sug.suggested_content)+'</textarea>'
      +'<div class="ai-actions">'
      +'<button class="ai-btn ai-btn--ghost" data-action="edit">Edit</button>'
      +'<button class="ai-btn ai-btn--ghost" data-action="cancel-edit" style="display:none">Cancel</button>'
      +'<button class="ai-btn ai-btn--save" data-action="save-edit" style="display:none">Save</button>'
      +'<button class="ai-btn ai-btn--reject" data-action="reject"'+rd+'>Reject</button>'
      +'<button class="ai-btn ai-btn--approve" data-action="approve"'+ad+'>Approve</button>'
      +'</div>'
      +'</div>';
  }

  function renderSuggestions(suggestions){
    /* Remove previous renders */
    document.querySelectorAll('.ai-hl-wrap').forEach(function(w){
      var p=w.parentNode; while(w.firstChild) p.insertBefore(w.firstChild,w); p.removeChild(w);
    });

    var article=document.querySelector('article');
    if(!article||!suggestions.length) return;

    var first=null;
    suggestions.forEach(function(sug){
      var headings=Array.from(article.querySelectorAll('h1,h2,h3,h4'));
      var heading=headings.find(function(h){ return h.textContent.trim()===sug.section_title; });
      if(!heading) return;

      var level=parseInt(heading.tagName[1],10);
      var nodes=[heading];
      var nxt=heading.nextElementSibling;
      while(nxt){
        var m=/^H([1-4])$/.exec(nxt.tagName);
        if(m&&parseInt(m[1],10)<=level) break;
        nodes.push(nxt); nxt=nxt.nextElementSibling;
      }

      var wrap=document.createElement('div');
      wrap.className='ai-hl-wrap ai-hl-wrap--'+sug.status;
      wrap.id='ai-wrap-'+sug.id;
      heading.parentNode.insertBefore(wrap,heading);
      nodes.forEach(function(n){ wrap.appendChild(n); });

      /* Popup sits at the TOP of the highlighted block, above the heading */
      var popupDiv=document.createElement('div');
      popupDiv.innerHTML=buildPopup(sug);
      wrap.insertBefore(popupDiv.firstChild, wrap.firstChild);

      if(!first) first=wrap;
    });

    if(first) setTimeout(function(){ first.scrollIntoView({behavior:'smooth',block:'start'}); },150);
  }

  /* Messages from parent React */
  window.addEventListener('message',function(e){
    var d=e.data; if(!d) return;

    if(d.type==='loadSuggestions'){
      renderSuggestions(d.suggestions||[]);
      return;
    }
    if(d.type==='scrollTo'&&d.hash){
      var el=document.querySelector(d.hash);
      if(el) el.scrollIntoView({behavior:'smooth',block:'start'});
      return;
    }
    if(d.type==='updateCard'){
      var wrap=document.getElementById('ai-wrap-'+d.id);
      var popup=wrap&&wrap.querySelector('[data-sid]');
      if(!wrap||!popup) return;
      if(d.status){
        wrap.className='ai-hl-wrap ai-hl-wrap--'+d.status;
        popup.className='ai-popup ai-popup--'+d.status;
        var badge=popup.querySelector('.ai-badge');
        if(badge){ badge.className='ai-badge ai-badge--'+d.status; badge.textContent=d.status; }
        var ab=popup.querySelector('[data-action="approve"]');
        var rb=popup.querySelector('[data-action="reject"]');
        if(ab) ab.disabled=(d.status==='approved');
        if(rb) rb.disabled=(d.status==='rejected');
      }
      if(d.suggested_content!==undefined){
        var pre=popup.querySelector('.ai-pre--suggested');
        var ta=popup.querySelector('.ai-textarea');
        if(pre) pre.textContent=d.suggested_content;
        if(ta) ta.value=d.suggested_content;
      }
    }
  });

  /* Interaction delegation */
  document.addEventListener('click',function(e){
    var tab=e.target.closest('.ai-tab');
    if(tab){
      var popup=tab.closest('[data-sid]'); if(!popup) return;
      popup.querySelectorAll('.ai-tab').forEach(function(t){t.classList.remove('active');});
      tab.classList.add('active');
      popup.querySelectorAll('.ai-pre').forEach(function(p){p.style.display='none';});
      var p=popup.querySelector('.ai-pre--'+tab.dataset.tab); if(p) p.style.display='block';
      return;
    }
    var btn=e.target.closest('[data-action]');
    if(!btn||btn.disabled) return;
    var popup=btn.closest('[data-sid]'); if(!popup) return;
    var id=popup.dataset.sid;
    var action=btn.dataset.action;
    if(action==='approve'||action==='reject'){
      window.parent.postMessage({type:action,id:id},'*');
    } else if(action==='edit'){
      var pre=popup.querySelector('.ai-pre--suggested');
      var ta=popup.querySelector('.ai-textarea');
      var sb=popup.querySelector('[data-action="save-edit"]');
      var cb=popup.querySelector('[data-action="cancel-edit"]');
      if(pre) pre.style.display='none';
      if(ta){ta.style.display='block';ta.focus();}
      if(sb) sb.style.display='inline-block';
      if(cb) cb.style.display='inline-block';
      btn.style.display='none';
    } else if(action==='cancel-edit'){
      var pre=popup.querySelector('.ai-pre--suggested');
      var ta=popup.querySelector('.ai-textarea');
      var sb=popup.querySelector('[data-action="save-edit"]');
      var eb=popup.querySelector('[data-action="edit"]');
      if(pre) pre.style.display='block';
      if(ta) ta.style.display='none';
      if(sb) sb.style.display='none';
      btn.style.display='none';
      if(eb) eb.style.display='inline-block';
    } else if(action==='save-edit'){
      var ta=popup.querySelector('.ai-textarea');
      var content=ta?ta.value:'';
      window.parent.postMessage({type:'save_edit',id:id,content:content},'*');
      var pre=popup.querySelector('.ai-pre--suggested');
      var cb=popup.querySelector('[data-action="cancel-edit"]');
      var eb=popup.querySelector('[data-action="edit"]');
      if(pre){pre.textContent=content;pre.style.display='block';}
      if(ta) ta.style.display='none';
      btn.style.display='none';
      if(cb) cb.style.display='none';
      if(eb) eb.style.display='inline-block';
    }
  });
})();
"""

SUGGESTION_CSS = """
.ai-hl-wrap { transition: border-left .2s, background .2s; }
.ai-hl-wrap--pending  { border-left: 4px solid #EAB308; padding-left: 1rem; margin-left: -1.2rem; background: rgba(234,179,8,.06); }
.ai-hl-wrap--approved { border-left: 4px solid #22C55E; padding-left: 1rem; margin-left: -1.2rem; background: rgba(34,197,94,.06); }
.ai-hl-wrap--rejected { border-left: 4px solid #EF4444; padding-left: 1rem; margin-left: -1.2rem; background: rgba(239,68,68,.06); opacity: .65; }

.ai-popup {
  background: #FAFAF9; border: 1px solid #E7E5E4; border-radius: 10px;
  padding: .875rem 1rem; margin-bottom: 1rem;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  box-shadow: 0 2px 10px rgba(0,0,0,.1); font-size: 13px; position: relative; z-index: 10;
}
.ai-popup--pending  { background: #FFFBEB; border-color: #FDE68A; }
.ai-popup--approved { background: #F0FDF4; border-color: #BBF7D0; }
.ai-popup--rejected { background: #FEF2F2; border-color: #FECACA; }

.ai-popup__header { display:flex; align-items:center; justify-content:space-between; margin-bottom:.5rem; }
.ai-popup__title  { font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:.05em; color:#6B7280; }

.ai-badge { font-size:11px; padding:2px 9px; border-radius:9999px; font-weight:500; }
.ai-badge--pending  { background:#FEF3C7; color:#D97706; }
.ai-badge--approved { background:#D1FAE5; color:#059669; }
.ai-badge--rejected { background:#FEE2E2; color:#DC2626; }

.ai-popup__reason        { color:#4B5563; margin:0 0 .75rem; line-height:1.5; }
.ai-popup__reason strong { font-weight:600; color:#374151; }

.ai-tabs { display:flex; gap:4px; margin-bottom:8px; }
.ai-tab  { padding:4px 12px; font-size:12px; border-radius:6px; border:1px solid #E5E7EB; background:white; color:#6B7280; cursor:pointer; font-weight:500; }
.ai-tab.active { background:#111827; color:white; border-color:#111827; }

.ai-pre {
  font-family:ui-monospace,SFMono-Regular,monospace; font-size:12px;
  background:white; border:1px solid #E5E7EB; border-radius:6px;
  padding:10px; overflow:auto; max-height:180px;
  white-space:pre-wrap; color:#374151; line-height:1.5; margin:0 0 .75rem;
}
.ai-textarea {
  font-family:ui-monospace,SFMono-Regular,monospace; font-size:12px;
  width:100%; min-height:110px; border:1px solid #93C5FD; border-radius:6px;
  padding:10px; resize:vertical; line-height:1.5; margin-bottom:.75rem;
  box-sizing:border-box; background:white;
}
.ai-actions { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
.ai-btn     { padding:5px 13px; font-size:12px; border-radius:6px; cursor:pointer; font-weight:500; border:none; transition:opacity .15s,background .15s; }
.ai-btn:disabled                   { opacity:.38; cursor:default; }
.ai-btn--ghost                     { background:white; border:1px solid #D1D5DB; color:#374151; }
.ai-btn--ghost:hover:not(:disabled){ background:#F9FAFB; }
.ai-btn--approve                   { background:#16A34A; color:white; }
.ai-btn--approve:hover:not(:disabled){ background:#15803D; }
.ai-btn--reject                    { background:white; border:1px solid #FCA5A5; color:#DC2626; }
.ai-btn--reject:hover:not(:disabled){ background:#FEF2F2; }
.ai-btn--save                      { background:#2563EB; color:white; }
.ai-btn--save:hover:not(:disabled) { background:#1D4ED8; }
"""


@router.get("/proxy/docs")
async def proxy_docs(page: str = ""):
    """Fetch a documentation page from the upstream site and inject suggestion UI.

    Resolves relative asset URLs via a ``<base>`` tag, injects ``EARLY_SCRIPT``
    (cross-origin navigation fix + suggestion overlay JS) and ``SUGGESTION_CSS``
    into the page ``<head>``, then returns the modified HTML.

    Args:
        page: Relative page path (e.g. ``"tools"``); empty string for the index.
    """
    url = f"{DOCS_BASE}/{page}/" if page else f"{DOCS_BASE}/"

    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})

    soup = BeautifulSoup(resp.text, "html.parser")

    # Resolve all relative asset URLs to the live docs site
    base_tag = soup.new_tag("base", href=f"{DOCS_BASE}/")
    if soup.head:
        soup.head.insert(0, base_tag)

    # Inject early script into head — must run before MkDocs registers its listeners
    script = soup.new_tag("script")
    script.string = EARLY_SCRIPT
    if soup.head:
        soup.head.append(script)

    # Suggestion highlight + popup CSS
    style = soup.new_tag("style")
    style.string = SUGGESTION_CSS + "\n.md-content__inner { padding-bottom: 6rem !important; }"
    if soup.head:
        soup.head.append(style)

    return HTMLResponse(content=str(soup))
