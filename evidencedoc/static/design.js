'use strict';
// One saturated color per category, shared by boxes, entity markers and graph nodes.
Object.assign(categoryColors,{person:'#a979ff',organization:'#a9e943',date:'#00cfb0',money:'#ffc02e',percentage:'#ff793e',address:'#e27bff',identifier:'#ff4e90',contact:'#29bfff',location:'#ff9838',quantity:'#40dba5',term:'#73a2ff',other:'#bdced6'});
let readerSizing='comfortable';
applyZoom=function(){const canvas=$('document-canvas'),img=$('page-image'),ratio=(img.naturalWidth||595)/(img.naturalHeight||842);const comfortable=Math.max(150,Math.min(canvas.clientWidth-64,570));const base=readerSizing==='page'?Math.max(120,Math.min(canvas.clientWidth-64,(canvas.clientHeight-48)*ratio)):comfortable;$('page-stage').style.width=(base*state.zoom/100+48)+'px';$('zoom-fit').textContent=state.zoom===100?(readerSizing==='page'?'Fit page':'Reading size'):state.zoom+'%';$('zoom-out').disabled=state.busy||!state.result||state.zoom<=75;$('zoom-in').disabled=state.busy||!state.result||state.zoom>=300;};
$('zoom-fit').title='Switch between comfortable reading size and whole-page overview';
$('zoom-fit').onclick=()=>{readerSizing=readerSizing==='comfortable'?'page':'comfortable';explicitFocus=null;state.zoom=100;applyZoom();$('document-canvas').scrollTo({left:0,top:0});};
// Keep the clicked occurrence and wait for page loading/layout before centering.
let sourceFocus=null;
focusSource=function(bbox){
  if(!state.result||!Array.isArray(bbox)||bbox.length!==4||!bbox.every(n=>Number.isFinite(n)&&n>=0&&n<=1)||bbox[2]<=bbox[0]||bbox[3]<=bbox[1])return;
  readerSizing='comfortable';
  explicitFocus=bbox;
  const target=sourceFocus={bbox,document:state.result.document.id,page:state.page};
  const canvas=$('document-canvas'),img=$('page-image');
  const base=Math.max(150,Math.min(canvas.clientWidth-64,570));
  const ratio=(img.naturalWidth||595)/(img.naturalHeight||842);
  const fitWidth=(canvas.clientWidth-80)/(base*(bbox[2]-bbox[0]));
  const fitHeight=(canvas.clientHeight-80)/(base/ratio*(bbox[3]-bbox[1]));
  state.zoom=Math.round(Math.max(100,Math.min(250,fitWidth*100,fitHeight*100))/5)*5;
  applyZoom();
  clearTimeout(focusTimer);
  focusTimer=setTimeout(()=>{
    if(sourceFocus!==target||explicitFocus!==bbox||state.result?.document.id!==target.document||state.page!==target.page||!img.complete||!img.naturalWidth)return;
    const wr=$('page-wrap').getBoundingClientRect(),cr=canvas.getBoundingClientRect();
    canvas.scrollTo({
      left:Math.max(0,canvas.scrollLeft+wr.left-cr.left+(bbox[0]+bbox[2])/2*wr.width-canvas.clientWidth/2),
      top:Math.max(0,canvas.scrollTop+wr.top-cr.top+(bbox[1]+bbox[3])/2*wr.height-canvas.clientHeight/2),
      behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'
    });
  },320);
};
$('page-image').onload=()=>{
  applyZoom();
  if(sourceFocus&&explicitFocus===sourceFocus.bbox&&state.result?.document.id===sourceFocus.document&&state.page===sourceFocus.page)focusSource(sourceFocus.bbox);
};
focusEvidence=function(){
  const evidence=selectedField()?displayEvidence(selectedField()):[];
  focusSource(evidence.find(s=>s.page===state.page)?.bbox);
};
const sourceRenderPage=renderPage;
renderPage=function(){
  sourceRenderPage();
  $('overlays').querySelectorAll('[data-source-bbox]:not([data-box-entity])').forEach(b=>{
    b.onclick=()=>focusSource(b.dataset.sourceBbox.split(',').map(Number));
  });
};
const sourceGoPage=goPage;
goPage=function(page){explicitFocus=null;sourceFocus=null;clearTimeout(focusTimer);sourceGoPage(page);};
const refinedAdopt=adoptResult;
adoptResult=function(r){readerSizing='comfortable';refinedAdopt(r);};
// A balanced information hierarchy: category, value, role and source page.
renderEntities=function(){if(!studio.atlas)return;const rows=filteredEntities();$('entity-count').innerHTML=`<span><strong>${rows.length}</strong> entities</span><span>Click to inspect source ${icon('arrow')}</span>`;$('entity-list').innerHTML=rows.length?rows.map(e=>`<button class="field-card entity-card ${e.id===studio.entity?'active':''}" data-entity="${e.id}" aria-pressed="${e.id===studio.entity}" style="--entity-color:${categoryColors[e.category]}"><div class="entity-leading"><span class="entity-category-mark">${icon(e.category==='person'?'file':e.category==='date'?'clock':e.category==='organization'?'layers':'scan')}</span></div><div class="entity-main"><div class="entity-card-heading"><span class="entity-meta">${esc(label(e.category))}</span><span class="entity-pages">${[...new Set(e.evidence.map(s=>s.page))].map(p=>'p. '+p).join(' · ')}</span></div><div class="field-value">${esc(e.value)}</div><div class="entity-role">${esc(label(e.role))}</div></div><span class="entity-open">${icon('external')}</span></button>`).join(''):'<div class="empty-findings"><h3>No matching entities</h3><p>Try another category or search.</p></div>';$('entity-list').querySelectorAll('[data-entity]').forEach(b=>b.onclick=()=>selectEntity(b.dataset.entity));};
// All built-in examples are unchanged public-source PDFs with a source manifest.
async function openPublicDocument(name,discover=false){if(state.busy||studio.labBusy)return;const filename=name+'.pdf';const saved=state.library.find(d=>d.filename===filename);if(saved&&saved.mode==='nvidia'&&!discover){await loadResult(saved.id);return;}await run(()=>api('/api/public-documents/'+encodeURIComponent(name)+'?discover='+discover,{method:'POST'}));}
$('start-sample').textContent='Explore a public document →';$('start-sample').onclick=()=>openPublicDocument('nvidia-fy2026');
$('fault-test').onclick=null;
document.querySelectorAll('[data-public]').forEach(b=>b.onclick=()=>{closeDialog('upload-dialog');openPublicDocument(b.dataset.public,true);});
// Real-source lab, with hypotheses stated separately from observed model outcomes.
document.querySelector('#studio-lab .section-intro p').textContent='Remove selected evidence from a copy of a real document. Ask again. Inspect the result.';
document.querySelector('#studio-lab .lab-layout').insertAdjacentHTML('beforebegin',`<section class="real-lab-guide"><div><span class="eyebrow">REAL DOCUMENTS · ACTUAL MODEL CALLS</span><h3>Does the answer depend on its evidence?</h3><p>Choose a published source below. We select the relevant field and its citations; you run the experiment.</p></div><div class="real-lab-examples"><button id="lab-nvidia" data-lab-public="nvidia-fy2026"><span class="example-number">01</span><span><strong>NVIDIA earnings report</strong><small>Withhold the dividend payment date</small></span>${icon('arrow')}</button><button id="lab-tcmb" data-lab-public="tcmb-2025-24"><span class="example-number">02</span><span><strong>Central bank decision</strong><small>Withhold the decision date</small></span>${icon('arrow')}</button></div></section><p id="lab-hypothesis" class="lab-hypothesis" hidden></p>`);
const labCases={'nvidia-fy2026':{field:'dividend_payment_date',text:'The published dividend date is April 1, 2026. Withhold its cited regions. Hypothesis: a fresh extraction should abstain if no remaining source supports this date.'},'tcmb-2025-24':{field:'karar_tarihi',text:'The published decision date is 17 Nisan 2025. Withhold its cited region. Hypothesis: the date should be withdrawn if no other unmasked evidence supports it.'}};
document.querySelectorAll('[data-lab-public]').forEach(b=>b.onclick=async()=>{if(state.busy||studio.labBusy)return;await openPublicDocument(b.dataset.labPublic);switchStudio('lab');const choice=labCases[b.dataset.labPublic];const field=[choice.field,...(b.dataset.labPublic==='tcmb-2025-24'?['decision_date']:[])].find(f=>[...$('lab-field').options].some(o=>o.value===f));if(field){$('lab-field').value=field;renderLabSelection();$('lab-hypothesis').hidden=false;$('lab-hypothesis').textContent=choice.text;}});
const realPrepareLab=prepareLab;
prepareLab=function(){realPrepareLab();$('lab-hypothesis').hidden=true;};
const realLabSelection=renderLabSelection;
renderLabSelection=function(){realLabSelection();$('lab-hypothesis').hidden=true;};
$('lab-field').onchange=renderLabSelection;
const realLabRun=$('lab-run').onclick;
$('lab-run').onclick=async()=>{document.querySelectorAll('[data-lab-public]').forEach(b=>b.disabled=true);try{await realLabRun();}finally{document.querySelectorAll('[data-lab-public]').forEach(b=>b.disabled=false);}};
// Source links are provenance, not cosmetic badges.
const existingRender=render;
render=function(){existingRender();if(!state.result)return;const source=(state.config?.public_documents||[]).find(p=>p.sha256===state.result.document.sha256);$('source-origin')?.remove();if(source){const a=document.createElement('a');a.id='source-origin';a.href=source.source_url;a.target='_blank';a.rel='noreferrer';a.textContent='Original source ↗';document.querySelector('.document-meta').append(a);}};
