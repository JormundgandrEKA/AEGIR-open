"""The single page of the AutoRAN dashboard. Plain JavaScript, inline SVG, no external requests."""

HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>AutoRAN</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{--fg:#111;--bg:#fff;--rule:#111;--hair:#c4c4c4;--dim:#555;--acc:#0040ff;--bad:#b00020;--good:#0b6b2e;--warn:#9a6700;--soft:#f3f3f3;--pos:#b00020;--oth:#9a6700;--unl:#777;--neg:#0b6b2e}
*{box-sizing:border-box;border-radius:0}
html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:13px/1.4 "Segoe UI","Helvetica Neue",Arial,sans-serif}
.mono,.m{font-family:Consolas,"DejaVu Sans Mono","Courier New",monospace}
nav{display:flex;border-bottom:2px solid var(--rule);position:sticky;top:0;background:var(--bg);z-index:3;align-items:stretch}
nav b{padding:6px 12px;font:700 14px Consolas,monospace;letter-spacing:.05em;border-right:1px solid var(--rule)}
nav a{padding:6px 12px;border-right:1px solid var(--rule);cursor:pointer;color:var(--fg);text-decoration:none;font-weight:600}
nav a.on{background:var(--fg);color:var(--bg)}
nav span{margin-left:auto;padding:6px 12px;color:var(--dim);font:12px Consolas,monospace}
main{padding:12px 14px;max-width:1500px}
h2{font:700 12px Consolas,monospace;text-transform:uppercase;letter-spacing:.06em;margin:16px 0 6px;padding:2px 6px;background:var(--soft);border:1px solid var(--rule)}
h2:first-child{margin-top:0}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:0;border:1px solid var(--rule);margin-bottom:10px}
.tile{padding:8px 10px;border-right:1px solid var(--rule);border-bottom:1px solid var(--rule)}
.tile .v{font:700 24px Consolas,monospace;line-height:1.1}
.tile .l{font-size:11.5px;color:var(--dim)}
.tile .s{font:11px Consolas,monospace;color:var(--dim)}
.warn{border:1px solid var(--warn);border-left:6px solid var(--warn);background:#fff8e1;padding:4px 8px;margin:3px 0}
.bad{border-color:var(--bad);background:#fdeaec}
table{border-collapse:collapse;width:100%}
th,td{border:1px solid var(--hair);padding:2px 6px;text-align:left;vertical-align:top}
th{background:var(--soft);font:700 11.5px Consolas,monospace;position:sticky;top:34px}
td.n,th.n{text-align:right;font-family:Consolas,monospace}
tr.click{cursor:pointer}tr.click:hover{background:#eef3ff}
button,select,input{font:12.5px "Segoe UI",Arial,sans-serif;border:1px solid var(--rule);background:var(--bg);color:var(--fg);padding:3px 8px}
button{cursor:pointer}button:hover{background:var(--fg);color:var(--bg)}
button.on{background:var(--fg);color:var(--bg)}
input:focus,select:focus{outline:2px solid var(--acc)}
.bar{display:flex;height:14px;border:1px solid var(--rule);min-width:60px;background:#fff}
.bar i{display:block;height:100%}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:6px 0}
.chip{display:inline-block;border:1px solid var(--rule);padding:0 5px;font:11.5px Consolas,monospace;margin-right:3px;background:#fff}
.chip.pos{background:var(--pos);color:#fff;border-color:var(--pos)}.chip.neg{background:var(--neg);color:#fff;border-color:var(--neg)}
.chip.oth{background:var(--oth);color:#fff;border-color:var(--oth)}.chip.unl{background:var(--unl);color:#fff;border-color:var(--unl)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:0;border:1px solid var(--rule)}
.card{border-right:1px solid var(--rule);border-bottom:1px solid var(--rule);padding:6px 8px;cursor:pointer;min-height:96px;position:relative}
.card.cur{outline:2px solid var(--acc);outline-offset:-2px}
.card.wrong{background:#fdeaec;box-shadow:inset 6px 0 0 var(--bad)}
.card.unsure{background:#fff8e1;box-shadow:inset 6px 0 0 var(--warn)}
.card .k{position:absolute;right:6px;top:4px;font:700 11px Consolas,monospace;color:var(--dim)}
.card .t{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:92%}
.card .w{font:12.5px/1.35 Consolas,monospace;margin:4px 0;max-height:4.6em;overflow:hidden}
mark{background:#ffe066;padding:0 1px}
.q{font-weight:700;margin:2px 0}
.ci{position:relative;height:12px;background:#eee;border:1px solid var(--rule);min-width:140px}
.ci i{position:absolute;top:0;bottom:0;background:var(--acc);opacity:.35}
.ci b{position:absolute;top:-2px;bottom:-2px;width:2px;background:var(--fg)}
.ci u{position:absolute;top:-3px;bottom:-3px;width:0;border-left:2px dashed var(--bad)}
#drawer{position:fixed;top:34px;right:0;bottom:0;width:min(720px,96vw);background:var(--bg);border-left:2px solid var(--rule);overflow:auto;z-index:4;display:none;padding:10px 12px}
#drawer.open{display:block}
pre{white-space:pre-wrap;word-break:break-word;font:12.5px/1.4 Consolas,monospace;margin:0;max-height:30vh;overflow:auto;border:1px solid var(--hair);padding:4px 6px;background:#fafafa}
.kv{display:grid;grid-template-columns:150px 1fr;gap:1px 8px}.kv div:nth-child(odd){color:var(--dim)}
.small{font-size:11.5px;color:var(--dim)}
svg text{font:11px Consolas,monospace;fill:#111}
.heat td{text-align:right;font:11px Consolas,monospace;padding:1px 4px}
#fp{position:sticky;top:34px;z-index:2;background:var(--bg)}
.fpbox{border-bottom:2px solid var(--rule);padding:6px 14px 8px;max-height:45vh;overflow:auto;background:#fcfcfc}

.astro{margin:14px 0;padding:14px 16px;max-width:980px;border:5px solid transparent;border-radius:22px!important;background:linear-gradient(#fffaf0,#fff0fb) padding-box,linear-gradient(120deg,#ff5fa2,#ffb347,#fff35f,#5fe38a,#5fb8ff,#b07bff) border-box;font-family:"Comic Sans MS","Chalkboard SE","Comic Neue",cursive;position:relative;overflow:hidden}
.astro h2{margin:0 0 4px;border:0;font:700 22px "Comic Sans MS","Chalkboard SE",cursive;color:#7a1fa2;display:inline-block;transform-origin:left center;animation:wob 3.2s ease-in-out infinite}
.astro .small{font-family:inherit;color:#5a3a6a}
.astro .bubble{display:inline-block;background:#fff;border:3px dashed #b07bff;border-radius:18px!important;padding:6px 12px;margin:6px 0;font-weight:700;color:#4b1d6b;transform:rotate(-1deg)}
.astro svg text{font-family:"Comic Sans MS","Chalkboard SE",cursive}
.twk{animation:twk 1.8s ease-in-out infinite}.twk:nth-child(2n){animation-delay:.6s}.twk:nth-child(3n){animation-delay:1.1s}
@keyframes wob{0%,100%{transform:rotate(-1.5deg)}50%{transform:rotate(1.5deg) scale(1.03)}}
@keyframes twk{0%,100%{opacity:.25}50%{opacity:1}}
@media (prefers-reduced-motion:reduce){.astro h2,.twk{animation:none}}
.lgd{display:inline-block;margin:0 10px 2px 0;white-space:nowrap}.lgd i{display:inline-block;width:11px;height:11px;margin-right:4px;vertical-align:-1px}
.pres nav,.pres #fp{display:none}.pres main{font-size:16px}.pres .tile .v{font-size:30px}.pres .small{font-size:14px}#presx{position:fixed;top:8px;right:8px;z-index:9;display:none}.pres #presx{display:block}
</style></head><body>
<nav id="nav"><b>AutoRAN</b></nav>
<section id="fp" aria-label="Fetch status"></section>
<main id="main">Loading…</main>
<div id="drawer"></div>
<script>
"use strict";
const $=id=>document.getElementById(id);
function h(tag,attrs,...kids){const e=document.createElement(tag);
 for(const k in (attrs||{})){if(attrs[k]==null||attrs[k]===false)continue;if(k==='class')e.className=attrs[k];else if(k.startsWith('on'))e.addEventListener(k.slice(2),attrs[k]);else if(k==='html')e.innerHTML=attrs[k];else e.setAttribute(k,attrs[k]);}
 for(const c of kids.flat()){if(c==null||c===false)continue;e.append(c.nodeType?c:document.createTextNode(String(c)));}return e;}
const hasBridge=()=>!!(window.pywebview&&window.pywebview.api&&window.pywebview.api.call);
async function api(p,b,method){
 if(hasBridge()){const r=await window.pywebview.api.call(method||(b?'POST':'GET'),p,b||null);
  if(r.status!==200)throw new Error((r.data&&r.data.error)||('error '+r.status));return r.data;}
 const r=await fetch(p,{method:method||(b?'POST':'GET'),headers:{'Content-Type':'application/json'},body:b?JSON.stringify(b):undefined});
 const j=await r.json();if(!r.ok)throw new Error(j.error||r.status);return j;}
function waitBridge(){return new Promise(res=>{if(hasBridge())return res(true);window.addEventListener('pywebviewready',()=>res(true),{once:true});setTimeout(()=>res(hasBridge()),3000);});}
const fmt=n=>n==null?'-':Number(n).toLocaleString('en-US');
const pct=(x,d=1)=>x==null?'-':(100*x).toFixed(d)+'%';
const f3=x=>x==null?'-':Number(x).toFixed(3);
const COL={positive_recruitment:'var(--pos)',other_stop:'var(--oth)',unlabelled:'var(--unl)',negative_completed:'var(--neg)'};
const NAME={positive_recruitment:'recruitment failure',other_stop:'other stop',unlabelled:'no usable reason',negative_completed:'completed'};
const S={m:null,page:'overview',facets:null,audit:null,cleanOnly:false};

function ciBar(lo,hi,p,target){const w=(v)=>Math.max(0,Math.min(100,v*100))+'%';
 return h('div',{class:'ci',title:'95% interval '+f3(lo)+' to '+f3(hi)},h('i',{style:`left:${w(lo)};width:${(Math.max(0,hi-lo)*100)}%`}),h('b',{style:`left:${w(p)}`}),target!=null?h('u',{style:`left:${w(target)}`}):null);}
function stackBar(c,max){const tot=c.n||1,sc=(c.n/max)*100;
 const seg=(k,col)=>h('i',{style:`width:${(c[k]||0)/tot*100}%;background:${col}`,title:k+' '+(c[k]||0)});
 return h('div',{class:'bar',style:`width:${Math.max(sc,1.5)}%`},seg('pos','var(--pos)'),seg('other','var(--oth)'),seg('unl','var(--unl)'),seg('neg','var(--neg)'));}
function wilson(k,n){if(!n)return[0,1];const z=1.96,p=k/n,d=1+z*z/n,c=(p+z*z/(2*n))/d,hh=z*Math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d;return[Math.max(0,c-hh),Math.min(1,c+hh)];}

// ------------------------------------------------------------------ pages
const PAGES=[['start','Get started'],['overview','Overview'],['evidence','Evidence'],['coverage','Coverage'],['labels','Labels and rules'],['scorers','Scorers'],['browse','Browse'],['review','Review'],['simulate','Simulate'],['plots','Plots'],['run','Run'],['settings','Settings'],['about','About']];
function nav(){const n=$('nav');n.replaceChildren(h('b',null,'AutoRAN'));
 PAGES.filter(([k])=>S.empty?['start','run','settings','about'].includes(k):k!=='start').forEach(([k,l])=>n.append(h('a',{class:S.page===k?'on':'',href:'#'+k},l)));
 const m=S.m,g=S.gpu;n.append(h('span',{style:'cursor:pointer',title:'Open the GPU check',onclick:()=>{location.hash='#settings';}},(g&&g.cuda_available?'GPU '+g.device+' '+g.memory_gb+' GB':(g&&g.torch===null?'CPU only (click to check your GPU)':'CPU only'))+' · '+(m?fmt(m.pipeline.trials)+' trials · registry data '+(m.pipeline.data_timestamp||'?').slice(0,10):'')));}
async function go(){let k=(location.hash||'#overview').slice(1).split('?')[0];if(k==='gold'){k='review';S.reviewMode='cases';}S.page=PAGES.some(p=>p[0]===k)?k:'overview';if(S.empty&&!['start','run','settings','about'].includes(S.page))S.page='start';if(!S.empty&&S.page==='start')S.page='overview';nav();closeDrawer();
 const main=$('main');const ld=h('div',{class:'small'},'Loading…');main.replaceChildren(ld);
 try{if(S.timer){clearInterval(S.timer);S.timer=null;}await ({start,overview,evidence,coverage,labels,scorers,browse,review,simulate,plots,run,settings,about}[S.page])(main);ld.remove();}catch(e){main.replaceChildren(h('div',{class:'warn bad'},'Error: '+e.message));}}
window.addEventListener('hashchange',go);

async function overview(main){
 const m=S.m,p=m.pipeline,cov=m.coverage.class,L=m.labeller,A=S.audit;
 const c=k=>(cov[k]||{}).n||0, pos=c('positive_recruitment'), neg=c('negative_completed');
 const best=Object.entries(m.scorers).filter(([k])=>k!=='random').sort((a,b)=>(b[1].test.all.auroc||0)-(a[1].test.all.auroc||0))[0];
 const ie=L?L.ie_combos.test[L.choice_ie]:null;
 const pa=A.per_class.positive_recruitment;
 const tiles=[['Trials',fmt(p.trials),'all phases, started 2005+, completed or terminated'],
  ['Recruitment failures',fmt(pos),pct(pos/(pos+neg))+' of completed + failed'],['Completed',fmt(neg),'negatives'],
  ['Other stops',fmt(c('other_stop')),'safety, funding, efficacy…'],['No usable reason',fmt(c('unlabelled')),'excluded from the task'],
  ['Labeller precision',ie?pct(ie.precision):'-','recruitment failure, held-out curated test (target 90%); recall '+(ie?pct(ie.recall):'-')],
  ['Human-checked precision',pa&&pa.n?pct(pa.p):'none yet',pa&&pa.n?'95% '+pct(pa.lo)+' to '+pct(pa.hi)+' · '+pa.n+' checked':'use Review to measure it'],
  ['Best baseline AUROC',best?f3(best[1].test.all.auroc):'-',best?best[0]+' · clean subset '+f3(best[1].test.clean.auroc):''],
  ['Clean inputs',fmt(['first_version','never_updated','current_unchanged'].reduce((s,k)=>s+((m.coverage.input_state[k]||{}).n||0),0)),'first submissions, see About']];
 main.append(h('h2',null,'Overview'),h('div',{class:'tiles'},tiles.map(t=>h('div',{class:'tile'},h('div',{class:'l'},t[0]),h('div',{class:'v'},t[1]),h('div',{class:'s'},t[2])))));
 main.append(h('h2',null,'Warnings'));
 (m.warnings.length?m.warnings:['No warnings.']).forEach(w=>main.append(h('div',{class:'warn'+(m.warnings.length?'':' ')},w)));
 main.append(h('h2',null,'Supervisor progress'));
 main.append(h('div',null,`${fmt(A.cards)} cards checked in ${A.sheets} screens · ${A.seconds_per_card==null?'-':A.seconds_per_card+' s per card'} · canary catch rate ${A.canary_catch_rate==null?'-':pct(A.canary_catch_rate,0)} (${A.canaries_caught}/${A.canaries})`));
 main.append(h('div',{class:'row'},h('button',{onclick:()=>location.hash='review'},'Start a review screen'),h('button',{onclick:()=>location.hash='labels'},'Review rules'),h('button',{onclick:()=>location.hash='browse'},'Browse findings')));
 main.append(h('h2',null,'Pipeline health'));
 const runs=p.runs.map(r=>r.kind+' '+r.run+' ('+r.status+')').join(' · ');
 main.append(h('div',{class:'kv'},...[['Runs',runs],['Pages / requests',p.pages+' pages · '+fmt(p.requests_logged)+' requests logged · '+p.errors_logged+' errors'],['Registry data timestamp',p.data_timestamp||'-'],['Disk',fmt(p.disk_mb)+' MB'],['Metrics computed',p.computed],['Version',p.autoran_version]].flatMap(([a,b])=>[h('div',null,a),h('div',{class:'m'},b)])));}

function dimTable(dim,rows,sortBy){const max=Math.max(...rows.map(r=>r[1].n),1);
 const t=h('table',null,h('tr',null,h('th',null,dim.replace('_',' ')),h('th',{class:'n'},'trials'),h('th',{class:'n'},'recruit. failures'),h('th',{class:'n'},'rate'),h('th',null,''),h('th',{style:'width:45%'},'mix')));
 rows.slice(0,40).forEach(([g,c])=>{const den=(c.pos||0)+(c.neg||0),[lo,hi]=wilson(c.pos||0,den);
  t.append(h('tr',{class:'click',onclick:()=>{const q={area:'area',phase:'phase',sponsor_class:'sponsor_class',region:'region',input_state:'input_state',registration:'registration',stop_class:'stop_class',label_source:'label_source'}[dim];
    if(q){S.browseQ={[q]:g};location.hash='browse';}}},h('td',null,g||'(none)'),h('td',{class:'n'},fmt(c.n)),h('td',{class:'n'},fmt(c.pos||0)),
   h('td',{class:'n'},den?pct((c.pos||0)/den):'-'),h('td',{class:'small'},den>=30?pct(lo)+'–'+pct(hi):'few'),h('td',null,stackBar(c,max))));});return t;}
async function coverage(main){
 const m=S.m;main.append(h('h2',null,'Coverage'));
 const dims=['phase','area','year_band','sponsor_class','region','site_band','allocation','masking','purpose','input_state','registration','stop_class','label_source','status'];
 const sel=h('select',{onchange:()=>draw(sel.value)},dims.map(d=>h('option',{value:d},d.replace('_',' '))));
 const holder=h('div');main.append(h('div',{class:'row'},'Break down by',sel,h('span',{class:'small'},'bars: ',h('span',{class:'chip pos'},'recruitment failure'),h('span',{class:'chip oth'},'other stop'),h('span',{class:'chip unl'},'no reason'),h('span',{class:'chip neg'},'completed'),' · rate = failures among failures + completed · click a row to browse it')),holder);
 function draw(d){holder.replaceChildren(dimTable(d,Object.entries(m.coverage[d]||{})));}draw(dims[0]);}

async function labels(main){
 const m=S.m,L=m.labeller;if(!L){main.append('No labeller built yet.');return;}
 main.append(h('h2',null,'Stop-reason labeller: recruitment failure, measured on the held-out curated test'));
 const cm=L.ie_combos;
 main.append(h('div',{class:'small'},`Curated Open Targets texts (Apache-2.0, graded B-): ${L.sizes.train} train, ${L.sizes.dev} dev, ${L.sizes.test} frozen test. The mode in use is chosen on dev with a precision floor; the test numbers were not used to choose.`));
 const t=h('table',null,h('tr',null,h('th',null,'mode'),h('th',{class:'n'},'dev precision'),h('th',{class:'n'},'dev recall'),h('th',{class:'n'},'test precision'),h('th',{class:'n'},'test recall'),h('th',null,'')));
 const nm={rules:'rules only',nb:'text model only',and:'rules AND model agree',or:'rules OR model'};
 for(const k of ['rules','nb','and','or'])t.append(h('tr',{style:k===L.choice_ie?'background:#eef3ff;font-weight:600':''},h('td',null,nm[k]),h('td',{class:'n'},f3(cm.dev[k].precision)),h('td',{class:'n'},f3(cm.dev[k].recall)),h('td',{class:'n'},f3(cm.test[k].precision)),h('td',{class:'n'},f3(cm.test[k].recall)),h('td',null,k===L.choice_ie?'in use':'')));
 main.append(t,h('div',{class:'small'},`Rules and model disagree on ${fmt(L.disagree_count)} stopped trials (${pct(L.disagree_share)}); they are in Browse with “disagree only”.`));
 main.append(h('h2',null,'All 17 stop classes (rules, held-out test)'));
 const pc=L.rules.test.per_class,t2=h('table',null,h('tr',null,h('th',null,'class'),h('th',{class:'n'},'support'),h('th',{class:'n'},'precision'),h('th',{class:'n'},'recall'),h('th',{class:'n'},'F1'),h('th',{class:'n'},'in registry')));
 Object.entries(pc).sort((a,b)=>b[1].support-a[1].support).forEach(([k,v])=>t2.append(h('tr',{class:'click',onclick:()=>{S.browseQ={stop_class:k};location.hash='browse';}},h('td',null,k),h('td',{class:'n'},v.support),h('td',{class:'n'},f3(v.precision)),h('td',{class:'n'},f3(v.recall)),h('td',{class:'n'},f3(v.f1)),h('td',{class:'n'},fmt((m.coverage.stop_class[k]||{}).n||0)))));
 main.append(t2,h('div',{class:'small'},`macro-F1 ${f3(L.rules.test.macro_f1)} on the test part. Only recruitment failure drives the task; the other classes organise the “other stop” group.`));
 main.append(h('h2',null,'Review by rule: approve rules, not trials'));
 main.append(h('div',{class:'small'},'Each row is one pattern. “Registry fired” is how many stopped trials it matched. Open a rule to check a sample of its matches in one screen; the verdicts become a per-rule precision with an interval.'));
 const rules=await api('/api/rules');const t3=h('table',null,h('tr',null,h('th',null,'rule'),h('th',null,'class'),h('th',{class:'n'},'curated fired'),h('th',{class:'n'},'curated precision'),h('th',{class:'n'},'registry fired'),h('th',null,'registry check (95%)'),h('th',null,'')));
 rules.forEach(r=>{const rv=r.registry_review;t3.append(h('tr',null,h('td',{class:'m'},r.rule_id),h('td',null,r.class),h('td',{class:'n'},r.curated_fired),h('td',{class:'n'},r.curated_precision==null?'-':f3(r.curated_precision)),h('td',{class:'n'},fmt(r.registry_fired)),
  h('td',null,rv?h('div',{style:'display:flex;gap:6px;align-items:center'},ciBar(rv.lo,rv.hi,rv.p,0.9),h('span',{class:'small'},pct(rv.p,0)+' of '+rv.n)):h('span',{class:'small'},'not checked')),
  h('td',null,r.registry_fired?h('button',{onclick:()=>{S.reviewSet={source:'rule',rule:r.rule_id,class:'positive_recruitment'};location.hash='review';}},'Check 24'):'')));});
 main.append(t3);}

function rocSvg(curves){const W=260,H=260,P=28;const xy=(x,y)=>[P+x*(W-2*P),H-P-y*(H-2*P)];
 const ns='http://www.w3.org/2000/svg';
 const s=document.createElementNS(ns,'svg');s.setAttribute('viewBox',`0 0 ${W} ${H}`);s.setAttribute('width',W);s.setAttribute('height',H);s.setAttribute('style','border:1px solid var(--hair)');
 const ln=(x1,y1,x2,y2,st)=>{const e=document.createElementNS(ns,'line');e.setAttribute('x1',x1);e.setAttribute('y1',y1);e.setAttribute('x2',x2);e.setAttribute('y2',y2);e.setAttribute('style',st);s.append(e);};
 ln(P,H-P,W-P,H-P,'stroke:#111');ln(P,H-P,P,P,'stroke:#111');const [a,b]=[xy(0,0),xy(1,1)];ln(a[0],a[1],b[0],b[1],'stroke:#bbb;stroke-dasharray:3 3');
 curves.forEach(c=>{const e=document.createElementNS(ns,'polyline');e.setAttribute('points',c.pts.map(([x,y])=>xy(x,y).join(',')).join(' '));e.setAttribute('style',`fill:none;stroke:${c.col};stroke-width:2`);s.append(e);});
 [['false positive rate',W/2-40,H-8],['true positive rate',2,P-8]].forEach(([t,x,y])=>{const e=document.createElementNS(ns,'text');e.setAttribute('x',x);e.setAttribute('y',y);e.textContent=t;s.append(e);});return s;}
async function scorers(main){
 const m=S.m;main.append(h('h2',null,'Scorers: how well can the protocol alone predict recruitment failure?'));
 main.append(h('div',{class:'small'},'Scorers see input fields only (never status, stop reason, completion dates or actual enrolment). Test split is frozen by NCT hash (20%). Intervals are seeded bootstrap 95%. The base rate is low, so read AUPRC beside it. “Clean” = first submissions only; see About for why that is a different population.'));
 const t=h('table',null,h('tr',null,h('th',null,'scorer'),h('th',{class:'n'},'AUROC all'),h('th',null,'95%'),h('th',{class:'n'},'AUROC clean'),h('th',null,'95%'),h('th',{class:'n'},'AUPRC all'),h('th',{class:'n'},'base rate'),h('th',{class:'n'},'prec@5%'),h('th',{class:'n'},'prec@10%')));
 const names=Object.keys(m.scorers);
 names.forEach(k=>{const a=m.scorers[k].test.all,c=m.scorers[k].test.clean,ci=(a.ci||{}).auroc,cc=(c.ci||{}).auroc;
  t.append(h('tr',null,h('td',{class:'m'},k),h('td',{class:'n'},f3(a.auroc)),h('td',{class:'small'},ci?f3(ci[0])+'–'+f3(ci[1]):''),h('td',{class:'n'},f3(c.auroc)),h('td',{class:'small'},cc?f3(cc[0])+'–'+f3(cc[1]):'wide ('+c.positives+' pos)'),h('td',{class:'n'},f3(a.auprc)),h('td',{class:'n'},pct(a.base_rate)),h('td',{class:'n'},pct(a.precision_top5)),h('td',{class:'n'},pct(a.precision_top10))));});
 main.append(t);
 const cols={random:'#999',criteria_count:'#9a6700',logistic:'#0040ff',logistic_text:'#0b6b2e'};
 main.append(h('h2',null,'ROC (test, all trials)'),h('div',{class:'row'},rocSvg(names.filter(k=>m.scorers[k].test.all.roc).map(k=>({pts:m.scorers[k].test.all.roc,col:cols[k]||'#a0a'}))),
  h('div',null,names.map(k=>h('div',null,h('span',{class:'chip',style:`background:${cols[k]||'#a0a'};color:#fff`},k))))));
 const sel=h('select',{onchange:()=>draw(sel.value)},names.map(k=>h('option',{value:k},k)));const hold=h('div');
 main.append(h('h2',null,'Detail'),h('div',{class:'row'},'Scorer',sel),hold);
 function draw(k){const e=m.scorers[k].test;hold.replaceChildren();
  const cal=e.all.calibration||[];hold.append(h('div',{class:'q'},'Calibration (ten equal bins by score; scores that are probabilities should match the observed rate)'),
   h('table',null,h('tr',null,['bin','n','mean score','observed rate'].map(x=>h('th',{class:x==='bin'?'':'n'},x))),cal.map(r=>h('tr',null,h('td',null,r.bin),h('td',{class:'n'},r.n),h('td',{class:'n'},['logistic','logistic_text'].includes(k)?pct(r.mean_score,2):r.mean_score.toFixed(2)+' (not a probability)'),h('td',{class:'n'},pct(r.observed,2))))));
  for(const [t,key] of [['By therapeutic area','by_area'],['By phase','by_phase']]){const rows=(e.all[key]||e[key]||[]).filter(x=>x.positives>=10).slice(0,25);
   hold.append(h('div',{class:'q'},t+' (groups with at least 10 positives in the test split)'),h('table',null,h('tr',null,['group','trials','positives','AUROC'].map((x,i)=>h('th',{class:i?'n':''},x))),rows.map(r=>h('tr',null,h('td',null,r.group),h('td',{class:'n'},fmt(r.n)),h('td',{class:'n'},r.positives),h('td',{class:'n'},f3(r.auroc))))));}}
 draw(names[0]);}

// ------------------------------------------------------------------ browse + inspector
const FILTERS=[['class','Label',['positive_recruitment','negative_completed','other_stop','unlabelled']],['stop_class','Stop class',null],['area','Area',null],['phase','Phase',null],['sponsor_class','Sponsor',null],['region','Region',null],['input_state','Input state',null],['registration','Registration',null],['label_source','Label source',null],['status','Status',['COMPLETED','TERMINATED']],['split','Split',['train','dev','test']]];
async function browse(main){
 const f=S.facets;const q=Object.assign({},S.browseQ||{});S.browseQ=null;let page=0;
 main.append(h('h2',null,'Findings browser'));
 const form=h('div',{class:'row'});const ctl={};
 FILTERS.forEach(([k,l,vals])=>{const sel=h('select',{onchange:run},h('option',{value:''},l+': any'),(vals||f[k]||[]).filter(Boolean).map(v=>h('option',{value:v},v)));sel.value=q[k]||'';ctl[k]=sel;form.append(sel);});
 const text=h('input',{type:'text',placeholder:'search title, stop reason, NCT',size:'30',value:q.q||'',onkeydown:e=>{if(e.key==='Enter')run();}});
 const dis=h('label',null,h('input',{type:'checkbox',onchange:run}),' disagree only');const low=h('label',null,h('input',{type:'checkbox',onchange:run}),' low confidence (<0.8)');
 const aud=h('select',{onchange:run},h('option',{value:''},'audit: any'),h('option',{value:'1'},'checked'),h('option',{value:'0'},'not checked'));
 const sort=h('select',{onchange:run},h('option',{value:''},'sort: default'),h('option',{value:'conf'},'confidence, lowest first'),h('option',{value:'year'},'start year, newest'),Object.keys(S.m.scorers).map(k=>h('option',{value:k},'score: '+k)));
 form.append(text,dis,low,aud,sort,h('button',{onclick:run},'Search'));main.append(form);
 const info=h('div',{class:'small'}),tbl=h('div'),pager=h('div',{class:'row'});main.append(info,tbl,pager);
 async function run(reset){if(reset!==false&&typeof reset!=='number')page=0;const p=new URLSearchParams();
  for(const k in ctl)if(ctl[k].value)p.set(k,ctl[k].value);if(text.value)p.set('q',text.value);if(dis.firstChild.checked)p.set('disagree','1');if(low.firstChild.checked)p.set('conf_lt','0.8');
  if(aud.value)p.set('audited',aud.value);if(sort.value)p.set('sort',sort.value);p.set('page',page);
  info.textContent='Searching…';const d=await api('/api/trials?'+p);info.textContent=fmt(d.total)+' trials';
  const sc=Object.keys(S.m.scorers).filter(k=>k!=='random');
  const t=h('table',null,h('tr',null,h('th',null,'NCT'),h('th',null,'title'),h('th',null,'label'),h('th',null,'stop reason'),h('th',{class:'n'},'conf'),h('th',null,'phase'),h('th',{class:'n'},'yr'),sc.map(k=>h('th',{class:'n'},k)),h('th',null,'audit')));
  d.rows.forEach(r=>t.append(h('tr',{class:'click',onclick:()=>openTrial(r.nct)},h('td',{class:'m'},r.nct),h('td',null,(r.title||'').slice(0,70)),h('td',null,h('span',{class:'chip '+({positive_recruitment:'pos',negative_completed:'neg',other_stop:'oth',unlabelled:'unl'}[r.class])},NAME[r.class])),
   h('td',null,r.status==='TERMINATED'?(r.stop_class?r.stop_class+' · ':'')+(r.why_stopped||'').slice(0,60):''),h('td',{class:'n'},r.status==='TERMINATED'?r.conf.toFixed(2):''),h('td',null,r.phase),h('td',{class:'n'},r.year||''),sc.map(k=>h('td',{class:'n'},r.scores[k]==null?'':pct(r.scores[k],1))),h('td',null,r.audit||''))));
  tbl.replaceChildren(t);const last=Math.max(0,Math.ceil(d.total/d.size)-1);
  pager.replaceChildren(h('button',{onclick:()=>{page=Math.max(0,page-1);run(page);}},'‹ prev'),'page '+(page+1)+' of '+(last+1),h('button',{onclick:()=>{page=Math.min(last,page+1);run(page);}},'next ›'));}
 run();}

function highlight(raw,ev){const el=h('div',{class:'m'});if(!raw){el.append(h('span',{class:'small'},'(no stop reason given)'));return el;}
 if(ev){const i=raw.toLowerCase().indexOf(ev.toLowerCase());if(i>=0){el.append(raw.slice(0,i),h('mark',null,raw.slice(i,i+ev.length)),raw.slice(i+ev.length));return el;}el.append(raw,h('div',{class:'small'},'matched: '+ev));return el;}el.append(raw);return el;}
function closeDrawer(){$('drawer').classList.remove('open');}
async function openTrial(nct){const d=$('drawer');d.classList.add('open');d.replaceChildren('Loading…');
 let t;try{t=await api('/api/trial/'+nct);}catch(e){d.replaceChildren(h('div',{class:'warn bad'},e.message));return;}
 const klass=h('span',{class:'chip '+({positive_recruitment:'pos',negative_completed:'neg',other_stop:'oth',unlabelled:'unl'}[t.class])},NAME[t.class]);
 const aud=h('div',{class:'row'},'Is the label right?',...[['agree','A agree'],['disagree','D disagree'],['unsure','U unsure']].map(([v,l])=>h('button',{onclick:async()=>{await api('/api/submit',{class:t.class,source:'inspector',seconds:0,cards:[{nct:t.nct,verdict:v}]});t.audit=v;S.audit=await api('/api/audit-summary');openTrial(t.nct);}},l)),t.audit?h('span',{class:'chip'},'your verdict: '+t.audit):null);
 d.replaceChildren(h('div',{class:'row'},h('b',{class:'m'},t.nct),klass,h('button',{onclick:closeDrawer,style:'margin-left:auto'},'Close [Esc]')),
  h('div',{class:'q'},t.title),h('div',{class:'small'},(t.sponsor||'')+' · '+t.phase+' · '+(t.areas||[]).join(', ')+' · '+(t.region||'')),
  h('h2',null,'Label'),h('div',{class:'kv'},...[['Class',NAME[t.class]],['Stop class',t.stop_class||'-'],['Source / confidence',t.label_source+' · '+(t.status==='TERMINATED'?t.conf.toFixed(2):'-')],['Rules fired',(t.rules||[]).join(', ')||'-'],['Labeller agreement',t.disagree?'rules and model DISAGREE':'agree'],['Finer labels',t.tree?((t.tree.sublabels||[]).join(', ')||'-')+(t.tree.land_mine?' · flag: '+t.tree.land_mine:'')+(t.tree.withdrawn_kind?' · withdrawn: '+t.tree.withdrawn_kind:''):'-'],['Status',t.status]].flatMap(([a,b])=>[h('div',null,a),h('div',{class:'m'},b)])),
  h('div',{class:'q',style:'margin-top:6px'},'Registry stop reason'),highlight(t.why_stopped,t.evidence),aud,
  h('h2',null,'Caveats'),...(t.caveats.length?t.caveats:['None.']).map(c=>h('div',{class:'warn'},c)),
  h('h2',null,'Design and dates'),h('div',{class:'kv'},...[['Dates',Object.entries(t.dates).map(([k,v])=>k.replace('_',' ')+' '+(v||'-')).join(' · ')],['Enrolment',(t.enrollment_info.count==null?'-':t.enrollment_info.count)+' '+(t.enrollment_info.type||'').toLowerCase()],['Sites / countries',t.sites+' sites · '+(t.countries||[]).slice(0,6).join(', ')],['Design',t.allocation+' · '+t.masking+' · '+t.n_arms+' arms · '+t.n_primary+' primary outcomes'],['Conditions',(t.conditions||[]).join('; ')],['Input state',t.input_state+' · '+t.registration]].flatMap(([a,b])=>[h('div',null,a),h('div',{class:'m'},b)])),
  h('h2',null,'Scorers (input fields only)'),h('table',null,h('tr',null,h('th',null,'scorer'),h('th',{class:'n'},'score'),h('th',null,'top contributions')),Object.entries(t.scores||{}).map(([k,v])=>h('tr',null,h('td',{class:'m'},k),h('td',{class:'n'},pct(v,1)),h('td',{class:'small'},((t.explain||{})[k]||[]).map(e=>e.feature+(e.contribution==null?'':' '+(e.contribution>0?'+':'')+e.contribution)).join(' · '))))),
  h('h2',null,'Eligibility criteria'),h('details',null,h('summary',null,(t.elig.n_incl+t.elig.n_excl)+' criteria · '+t.elig.n_words+' words'),h('pre',null,t.eligibility_text||'(none)')),
  h('h2',null,'Provenance'),h('div',{class:'kv'},...[['Source',t.provenance.source],['Grade',t.provenance.grade],['Registry data date',t.provenance.data_timestamp||'-'],['Stored page',t.provenance.page+' #'+t.provenance.pos]].flatMap(([a,b])=>[h('div',null,a),h('div',{class:'m'},b)])),
  h('div',{class:'row'},h('a',{href:t.links.study,target:'_blank',rel:'noopener'},'registry record'),h('a',{href:t.links.history,target:'_blank',rel:'noopener'},'history page (opens in your browser)')));
}

// ------------------------------------------------------------------ supervisor review (exception-based)
const SOURCES=[['random','positive_recruitment','Random recruitment failures'],['uncertain','positive_recruitment','Least certain recruitment failures'],['random','other_stop','Random other stops'],['random','unlabelled','Random “no usable reason”'],['disagree','positive_recruitment','Rules vs model disagreements'],['suspect_negative','negative_completed','Completed with tiny enrolment (hidden failures?)'],['random','negative_completed','Random completed']];
async function review(main){
 const cfg=Object.assign({source:'random',class:'positive_recruitment',n:24},S.reviewSet||{});S.reviewSet=null;
 const mode=S.reviewMode||'screen';
 const tab=(m,l,about)=>h('button',{class:m===mode?'primary':'',title:about,onclick:()=>{S.reviewMode=m;S.page='x';go();}},l);
 main.append(h('h2',null,'Review'),h('div',{class:'row'},tab('screen','Scan a screen','Judge many labels at a glance and flag the exceptions. Measures precision.'),tab('cases','One case at a time','Give a yes / no / other verdict on each changed label, saved to a CSV. Measures how far a change can be trusted.')));
 if(mode==='cases'){window.__rv=null;await cases(main);return;}
 window.__gd=null;
 let cards=[],cur=0,t0=Date.now(),sheet=null;
 main.append(h('h3',null,'Scan a screen, flag the exceptions'));
 main.append(h('div',{class:'small'},'Every card counts as CORRECT unless you flag it. Click a card or press X to flag it wrong, U for unsure, J/K to move, O to open the trial, Enter to submit the screen and load the next. About one card in twelve is a deliberately wrong “canary”: flag it too, so the tool can show how closely screens are being read. Canaries never count toward precision.'));
 const src=h('select',{onchange:()=>{const [s,c]=src.value.split('|');cfg.source=s;cfg.class=c;if(s!=='rule')delete cfg.rule;load();}},SOURCES.map(([s,c,l])=>h('option',{value:s+'|'+c},l)));
 if(cfg.source==='rule')src.append(h('option',{value:'rule|'+cfg.class},'Rule: '+cfg.rule));src.value=cfg.source+'|'+cfg.class;
 const nsel=h('select',{onchange:()=>{cfg.n=+nsel.value;load();}},[12,24,36,48].map(n=>h('option',{value:n},n+' per screen')));nsel.value=cfg.n;
 main.append(h('div',{class:'row'},'Source',src,nsel,h('button',{onclick:()=>load()},'New screen'),h('span',{id:'rvinfo',class:'small'})));
 const stat=h('div',{id:'rvstat'}),qline=h('div',{class:'q',style:'margin:6px 0'}),grid=h('div',{class:'grid'}),bar=h('div',{class:'row'});main.append(stat,qline,grid,bar);
 async function load(){grid.replaceChildren(h('div',{class:'small',style:'padding:8px'},'Loading a screen…'));
  const p=new URLSearchParams({source:cfg.source,class:cfg.class,n:cfg.n});if(cfg.rule)p.set('rule',cfg.rule);
  sheet=await api('/api/sheet?'+p);cards=sheet.cards.map(c=>Object.assign(c,{v:'agree'}));cur=0;t0=Date.now();draw();await stats();}
 function draw(){grid.replaceChildren();
  cards.forEach((c,i)=>{const k=h('div',{class:'k'},i<9?i+1:'');
   grid.append(h('div',{class:'card '+(c.v==='disagree'?'wrong':c.v==='unsure'?'unsure':'')+(i===cur?' cur':''),onclick:()=>{cur=i;flag(i,'disagree');},ondblclick:()=>openTrial(c.nct)},k,
    h('div',{class:'t'},h('span',{class:'m'},c.nct+' '),c.title),
    h('div',null,h('span',{class:'chip '+({positive_recruitment:'pos',negative_completed:'neg',other_stop:'oth',unlabelled:'unl'}[c.class])},NAME[c.class]),c.stop_class?h('span',{class:'chip'},c.stop_class):null,h('span',{class:'small'},(c.label_source||'')+' '+(c.status==='TERMINATED'?c.conf.toFixed(2):''))),
    h('div',{class:'w'},c.status==='TERMINATED'?highlight(c.why_stopped,c.evidence):h('span',{class:'small'},'Completed · enrolment '+(c.enrollment==null?'?':c.enrollment)+' · '+c.phase)),
    h('div',{class:'small',style:'color:var(--bad);font-weight:700'},c.v==='disagree'?'FLAGGED WRONG':c.v==='unsure'?'flagged unsure':'')));});
  const n=cards.length,w=cards.filter(c=>c.v==='disagree').length,u=cards.filter(c=>c.v==='unsure').length;
  qline.textContent=sheet.question;
  bar.replaceChildren(h('button',{onclick:submit},'Submit screen [Enter]'),h('span',{class:'small'},`${n} cards · ${w} flagged wrong · ${u} unsure · population ${fmt(sheet.population)} · seed ${sheet.seed}`));}
 function flag(i,v){cards[i].v=cards[i].v===v?'agree':v;draw();}
 async function submit(){const sec=(Date.now()-t0)/1000;const body={class:sheet.class,source:sheet.source,rule:cfg.rule,seconds:sec,cards:cards.map(c=>({nct:c.nct,verdict:c.v}))};
  const r=await api('/api/submit',body);$('rvinfo').textContent=`recorded ${r.recorded} verdicts`+(r.canaries?` · canaries caught ${r.canaries_caught}/${r.canaries}`:'');S.audit=await api('/api/audit-summary');await load();}
 async function stats(){S.audit=await api('/api/audit-summary');const a=S.audit.per_class[cfg.class]||{agree:0,disagree:0,n:0};const [lo,hi]=wilson(a.agree,a.n);
  const target=0.03,hw=a.n?(hi-lo)/2:null;
  stat.replaceChildren(h('div',{class:'row',style:'border:1px solid var(--rule);padding:6px 8px'},
   h('div',null,h('div',{class:'small'},'Checked so far for '+NAME[cfg.class]),h('div',{class:'m',style:'font-size:20px;font-weight:700'},a.n?pct(a.p):'-'),h('div',{class:'small'},a.n+' judged · '+a.disagree+' wrong')),
   h('div',{style:'min-width:240px'},h('div',{class:'small'},'95% interval for precision (dashed = 90% target)'),a.n?ciBar(lo,hi,a.p,0.9):h('div',{class:'small'},'no checks yet'),h('div',{class:'small'},a.n?pct(lo)+' to '+pct(hi):'')),
   h('div',null,h('div',{class:'small'},'When to stop'),h('div',{class:'m',style:'font-weight:700;color:'+(hw!=null&&hw<=target?'var(--good)':'var(--warn)')},a.n?(hw<=target?'enough: ±'+(hw*100).toFixed(1)+' points':'keep going: ±'+(hw*100).toFixed(1)+' points'):'—'),h('div',{class:'small'},'target ±3 points')),
   h('div',null,h('div',{class:'small'},'Reviewer attention'),h('div',{class:'m',style:'font-weight:700'},S.audit.canary_catch_rate==null?'-':pct(S.audit.canary_catch_rate,0)+' canaries caught'),h('div',{class:'small'},S.audit.seconds_per_card==null?'':S.audit.seconds_per_card+' s per card'))));}
 window.__rv={flag:(v)=>flag(cur,v),move:(d)=>{cur=Math.max(0,Math.min(cards.length-1,cur+d));draw();const el=grid.children[cur];if(el)el.scrollIntoView({block:'nearest'});},open:()=>cards[cur]&&openTrial(cards[cur].nct),submit,pick:(i)=>{if(i<cards.length){cur=i;flag(i,'disagree');}}};
 await load();}


// ------------------------------------------------------------------ Simulate: risk model, tests, scenario core, protocol explorer
async function simulate(main){
 main.append(h('h2',null,'Simulate and test'));
 const d=await api('/api/sim'),rep=d.report;
 const tbl=(heads,rows,num)=>{const t=h('table',{style:'max-width:980px'},h('tr',null,heads.map((x,i)=>h('th',{class:(num||[]).includes(i)?'n':''},x))));rows.forEach(r=>t.append(h('tr',null,r.map((c,i)=>h('td',{class:(num||[]).includes(i)?'n':''},c==null?'':c)))));return t;};
 const ci=a=>a?f3(a[0])+' to '+f3(a[1]):'';
 const sec=(t,about)=>{main.append(h('h2',null,t));if(about)main.append(h('div',{class:'small',style:'max-width:900px;margin-bottom:4px'},about));};
 main.append(h('div',{class:'warn'},h('b',null,'Exploratory. '),'Everything here is association in registry data, with machine-made (silver) labels. It does not show that changing a protocol changes outcomes. The simulator is scenario analysis: it shows how the simulator responds, not real-world value. The sealed vault is never read.'));
 const info=h('span',{class:'small'},rep?('Last run: '+rep.finished+' · '+fmt(rep.rows_used)+' trials used · '+fmt(rep.vault_rows_excluded)+' sealed in the vault · '+rep.file):'Not run yet.');
 const poll=async()=>{const j=await api('/api/jobs');if(j.running){setTimeout(poll,2000);return;}S.page='x';go();};
 main.append(h('div',{class:'row'},h('button',{class:'primary',onclick:async()=>{await startStage('simulate','auto');setTimeout(poll,2500);}},'Run the tests (about 2 minutes)'),info));
 sec('Validation gates','A claim made before its gate is passed is exploratory wherever it appears.');
 main.append(tbl(['Gate','Claim it unlocks','Status','Note'],(d.gates||[]).map(g=>[g.gate,g.claim,h('span',{class:'chip '+(g.status==='passed'||g.status==='measured'?'neg':g.status==='pilot only'?'oth':'unl')},g.status),g.note])));
 if(!rep){main.append(h('div',{style:'margin-top:10px'},'No results yet. Press Run the tests.'));return;}
 const rp=rep.replay;
 sec('Headline: how well can registration-time facts predict recruitment failure?','Trained on trials that started up to 2014, scored on 2016 to 2018. Never the vault or the frozen test split. Prospectively registered trials are the headline because they are the realistic use. Retrospective registrations leak hindsight and score higher.');
 main.append(tbl(['Group','Trials','Failures','AUROC (95% interval)','AUPRC','Guessing level','Top 5%: precision (lift)','Calibration error','Who-runs-it only','Gain over that (95% interval)'],
  Object.entries(rp.groups).map(([k,v])=>[k,fmt(v.n),fmt(v.positives),f3(v.full.auroc)+' ('+ci(v.full.auroc_ci)+')',f3(v.full.auprc),f3(v.full.auprc_guessing_level),pct(v.full.top5.precision)+' ('+v.full.top5.lift+'x)',f3(v.full.ece),f3(v.who_runs_it_only.auroc),'+'+f3(v.gain_over_who_runs_it.auroc)+' ('+ci(v.gain_over_who_runs_it.ci)+')']),[1,2,3,4,5,6,7,8,9]));
 main.append(h('div',{class:'small'},'“Who-runs-it only” uses sites, sponsor class, start era and country. A protocol claim has to beat it. AUPRC is read against its guessing level, because at a low base rate most alarms are false.'));
 const cal=rp.calibration_prospective||[];
 if(cal.length){const mx=Math.max(...cal.map(c=>Math.max(c.pred,c.obs)))*1.1||0.1,W=220,sx=v=>10+v/mx*(W-20),sy=v=>W-10-v/mx*(W-20);
  const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('width',W);svg.setAttribute('height',W);svg.setAttribute('style','border:1px solid var(--hair);margin:6px 0');
  svg.innerHTML='<line x1="10" y1="'+(W-10)+'" x2="'+(W-10)+'" y2="10" stroke="#999" stroke-dasharray="3"/>'+cal.map(c=>'<circle cx="'+sx(c.pred)+'" cy="'+sy(c.obs)+'" r="4" fill="#0040ff"/>').join('');
  main.append(h('div',{class:'row'},svg,h('div',{class:'small',style:'max-width:520px'},'Calibration on prospective trials: each dot is a tenth of trials, predicted failure rate across, observed rate up. On the dashed line the stated risk is the true rate.')));}
 sec('By sponsor, phase and area (prospective trials)','Where the model is weak is as important as where it is strong.');
 main.append(tbl(['Stratum','Trials','Failures','AUROC','95% interval'],Object.entries(rp.by_stratum_prospective).map(([k,v])=>[k.replace('area=','area: ').replace('sponsor=','sponsor: ').replace('phase=','phase: '),fmt(v.n),fmt(v.positives),f3(v.auroc),ci(v.auroc_ci)]),[1,2,3]));
 if(rep.ledger)ledgerSection(main,rep.ledger,d.protocol_ledger);
 sec('Other ways to fail','One risk per super-label of the label tree, same split, silver labels. Counts decide whether to believe a row.');
 main.append(tbl(['Way to fail','Failures to learn from','Failures to test on','AUROC','95% interval','AUPRC','Guessing level'],Object.entries(rep.heads).map(([k,v])=>v.note?[k,fmt(v.train_positives),fmt(v.test_positives),'',v.note,'','']:[k,fmt(v.train_positives),fmt(v.test_positives),f3(v.auroc),ci(v.auroc_ci),f3(v.auprc),f3(v.guessing_level)]),[1,2,3,5,6]));
 const nc=rep.negative_controls;
 sec('Negative controls','If one fails there is leakage or a bug. Run with every new model.');
 main.append(tbl(['Control','Result','Expected','Verdict'],[
  ['Outcomes shuffled (8 times)','mean AUROC '+f3(nc.shuffled_labels.dev_auroc_mean)+' (range '+f3(nc.shuffled_labels.dev_auroc_range[0])+' to '+f3(nc.shuffled_labels.dev_auroc_range[1])+'); '+nc.shuffled_labels.terms_flagged_fdr+' terms and '+nc.shuffled_labels.interactions_kept_max+' interactions survived','about 0.5; none survive',h('span',{class:'chip '+(Math.abs(nc.shuffled_labels.dev_auroc_mean-0.5)<0.03&&nc.shuffled_labels.terms_flagged_fdr<=1?'neg':'pos')},Math.abs(nc.shuffled_labels.dev_auroc_mean-0.5)<0.03&&nc.shuffled_labels.terms_flagged_fdr<=1?'pass':'FAIL')],
  ['12 random columns',nc.random_columns.fake_flagged_fdr+' of 12 flagged','0 or 1',h('span',{class:'chip '+(nc.random_columns.fake_flagged_fdr<=1?'neg':'pos')},nc.random_columns.fake_flagged_fdr<=1?(nc.random_columns.fake_flagged_fdr===1?'pass (at the edge)':'pass'):'FAIL')],
  ['Placebo outcome (last digit of the NCT number)','AUROC '+f3(nc.placebo_outcome.dev_auroc),'about 0.5',h('span',{class:'chip '+(Math.abs(nc.placebo_outcome.dev_auroc-0.5)<0.03?'neg':'pos')},Math.abs(nc.placebo_outcome.dev_auroc-0.5)<0.03?'pass':'FAIL')]]));
 const rc=rep.recovery.by_label_noise;
 sec('Can it find effects we plant?','Known effects, and a hidden common cause, are planted into real trial factors. Label noise is the share of true failures the labeller missed.');
 main.append(tbl(['Label noise','Right direction','Planted effects found','Null factors wrongly flagged','Factors sharing a hidden cause flagged','Interactions found right','Interactions recalled'],Object.entries(rc).map(([q,v])=>[pct(+q,0),pct(v.sign_correct,0),pct(v.true_effects_found_fdr,0),pct(v.null_factors_flagged_fdr,0),pct(v.prime_mover_factors_flagged_fdr,0),pct(v.pair_precision,0),pct(v.pair_recall,0)]),[1,2,3,4,5,6]));
 main.append(h('div',{class:'small',style:'max-width:900px'},rep.recovery.reading+' Interactions are rarely recovered: treat any reported interaction as a hypothesis. Random label noise says nothing about systematic labeller bias.'));
 const sm=rep.simulator;
 sec('Simulator (scenario analysis)','A cheap stochastic core: sites open late, patients arrive at random rates, reviews and funding can end a trial. Tuned to published rates from Kasenda et al. 2014. It is not validated against real outcomes (gate G4).');
 const A=sm.calibration.achieved,T=sm.calibration.anchors,nm={recruitment_stop_rate:'Stopped for poor recruitment',any_stop_rate:'Stopped for any reason',median_fraction_at_recruitment_stop:'Median share of target reached when stopped for recruitment',industry_over_investigator_recruitment_stop:'Industry rate over investigator rate',piloted_recruitment_stop_rate_max:'Piloted trials stopped for recruitment (upper bound)'};
 main.append(tbl(['Published rate','Published','Simulator'],Object.keys(T).map(k=>[nm[k],f3(T[k]),f3(A[k])])));
 main.append(h('div',{class:'small'},'It reproduces four of the five. The any-stop rate is too high.'));
 main.append(h('div',{class:'warn',style:'margin-top:6px'},sm.scenario.label));
 main.append(tbl(['Change (same simulated trials, only this differs)','Stopped for recruitment','Relative change'],[['None (control)',pct(sm.scenario.control_recruitment_stop_rate),'']].concat(Object.entries(sm.scenario.levers).map(([k,v])=>[k,pct(v.recruitment_stop_rate),(v.relative_change>0?'+':'')+pct(v.relative_change,0)])),[1,2]));
 if(d.scaled)scaledSection(main,d.scaled);
 if(d.synthetic)syntheticSection(main,d.synthetic);
 if(d.backtest){const bt=d.backtest,b=bt.backtest_era_B,c=bt.calibration_era_A,eq=bt.extraction_quality_completed_trials['documents dated at or before the start'];
  sec('Simulator backtest (gate G4): '+bt.gate_G4_verdict,'The simulator is tuned on trials starting up to 2015, using each trial’s real planned size, sites, sponsor type and criteria count, then predicts which 2016 to 2018 trials failed to recruit. Planned sizes come from protocol documents dated at or before the trial start. Scored against the registry-factor model on the same trials.');
  main.append(tbl(['Predictor','AUROC on '+fmt(b.n)+' real trials ('+fmt(b.failures)+' failures)'],Object.entries(b.auroc).map(([k,v])=>[k,f3(v)]),[1]));
  main.append(h('div',{class:'small',style:'max-width:900px;margin-top:4px'},'Simulator minus registry factors: '+b.simulator_vs_registry.gain.toFixed(3)+' ('+ci(b.simulator_vs_registry.ci)+'). Adding the simulator to the registry factors: '+b.simulator_adds_to_registry.gain.toFixed(3)+' ('+ci(b.simulator_adds_to_registry.ci)+'). Tuned on era A it matches the overall rate ('+pct(c.simulated.rate)+' simulated, '+pct(c.observed.rate)+' observed) but ranks trials wrongly: its highest-risk eighth is predicted '+pct(b.calibration_simulator[b.calibration_simulator.length-1].pred,0)+' and observed '+pct(b.calibration_simulator[b.calibration_simulator.length-1].obs,1)+'. Bigger planned sizes were less likely to fail in the real data (AUROC '+f3(b.auroc['planned sample size alone (bigger = riskier)'])+' for bigger = riskier), the opposite of the simulator’s mechanism. The simulator stays a scenario tool.'));
  main.append(h('div',{class:'small',style:'max-width:900px;margin-top:4px'},'Planned sample size read from the protocol text, on completed trials with a dated-before-start document ('+fmt(eq.n)+'): correlation with registered enrolment '+eq.pearson_log10+' (log scale), median actual over planned '+eq.median_actual_over_planned+', '+pct(eq.share_within_25pct,0)+' within 25%, '+pct(eq.share_within_factor_2,0)+' within a factor of 2. Recruitment failures reached a median '+pct(bt.attainment_actual_over_planned.recruitment_failures[2],0)+' of the planned size (Kasenda: 41%).'));}
 const wi=rep.whatif;
 sec('Does the model agree with a simpler look? (level 1)',wi.reading);
 main.append(tbl(['Protocol choice','Trials with it','Model: change in risk if removed','Stratified observed change if removed','Same direction'],wi.rows.map(r=>[r.lever,fmt(r.n_with),(r.model_implied_change_if_removed*100).toFixed(2)+' pts',(r.stratified_observed_change_if_removed*100).toFixed(2)+' pts',h('span',{class:'chip '+(r.same_direction?'neg':'pos')},r.same_direction?'yes':'no')]),[1,2,3]));
 if(rep.effects){const ef=rep.effects;
  sec('Factor effects on recruitment failure','Adjusted for all other factors. Odds ratio above 1 means more failure. “Stable” = the 95% bootstrap interval excludes 1. Evidence level: '+ef.level+'.');
  main.append(tbl(['Factor','Odds ratio','95% interval','Stable','Failure rate with','Without','Trials with it'],ef.terms.filter(t=>t.support==null||t.support>=200).slice(0,30).map(t=>[t.term,f3(t.odds_ratio),t.lo==null?'':f3(t.lo)+' to '+f3(t.hi),t.stable==null?'':h('span',{class:'chip '+(t.stable?'neg':'')},t.stable?'stable':'not stable'),t.rate_with==null?'':pct(t.rate_with),t.rate_without==null?'':pct(t.rate_without),t.support==null?'':fmt(t.support)]),[1,4,5,6]));
  if(ef.interactions.length)main.append(h('div',{class:'small'},'Interactions kept because they improved the held-out fit: '+ef.interactions.join('; ')+'. Any that involve a start era describe change over time, not a protocol choice. Treat all of them as hypotheses.'));
  if(ef.clusters.groups.length){main.append(h('h3',null,'Factors that travel together'));main.append(h('div',{class:'small',style:'max-width:900px'},'A shared underlying cause (sponsor resources, institutional commitment) shows up as factors that appear together. The model cannot separate them.'));ef.clusters.groups.forEach(g=>main.append(h('div',{class:'small'},'· '+g.join(', '))));}}
 // protocol explorer
 const fg=await api('/api/sim/factors');
 sec('Try a protocol','Tick what the protocol has; anything not ticked counts as absent. Each choice starts at the most common value; the start era starts at 2015 to 2019, where outcomes are mature (trials that started recently have had little time to fail, so a recent era always looks safer than it is). The estimate is an association in registry data, not a forecast for one trial.');
 if(!fg.ready){main.append(h('div',{class:'small'},'The explorer needs the model saved by a run. Press Run the tests.'));return;}
 const pick={},ticks=new Set(),out=h('div',{style:'margin-top:8px;max-width:900px'});
 const form=h('div',{class:'row',style:'align-items:flex-start;gap:14px'});
 fg.pick_one.forEach(g=>{const sel=h('select',{onchange:()=>{pick[g.group]=sel.value||null;}},h('option',{value:''},'(not set)'),...g.options.map(o=>h('option',{value:o},o)));if(g.default){sel.value=g.default;pick[g.group]=g.default;}form.append(h('label',{class:'small'},g.group,h('br'),sel));});
 main.append(form);
 fg.tick.forEach(g=>main.append(h('details',null,h('summary',null,g.group),h('div',{class:'row'},...g.options.map(o=>h('label',{style:'margin-right:10px;white-space:nowrap'},h('input',{type:'checkbox',onchange:e=>{e.target.checked?ticks.add(o):ticks.delete(o);}}),' '+o))))));
 const lst=(t,rows,key)=>rows.length?h('div',null,h('b',null,t),...rows.map(r=>h('div',{class:'small'},'· '+r.factor+': '+(r.change_if_flipped>0?'+':'')+(r.change_if_flipped*100).toFixed(2)+' points if '+(r.present?'removed':'added')+' (alone)'+(r.modifiable?'':' · context, not a protocol choice')))):'';
 main.append(h('div',{class:'row'},h('button',{class:'primary',onclick:async()=>{
   const on=[...ticks,...Object.values(pick).filter(Boolean)];
   try{const r=await api('/api/sim/explain',{on});
    out.replaceChildren(h('div',{style:'font-size:20px;font-weight:700'},pct(r.risk,1)+' estimated chance of recruitment failure',h('span',{class:'small',style:'font-weight:400'},'  (all comparable trials: '+pct(r.base_rate,1)+')')),
     lst('Raising the risk',r.raising),lst('Lowering the risk',r.lowering),lst('Protective factors this protocol lacks',r.missing_protective),
     h('div',{class:'small',style:'margin-top:6px'},r.level+'. '+r.note));
   }catch(e){out.replaceChildren(h('div',{class:'warn bad'},e.message));}}},'Estimate')));
 main.append(out);
}


// ------------------------------------------------------------------ source ledger and the Astrology Corner
const KCOL={protocol:'#0040ff',who:'#7a3fb8',trend:'#00897b',hindsight:'#d9480f',incidental:'#8a8a8a',control:'#bdbdbd',joke:'#e0409a',doc:'#0b6b2e',derived:'#b45f06'};
const esc=t=>String(t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
function ledgerChart(rows,kinds,title,floors){
 const W=940,L=330,P=250,G=70,rh=21,top=44,H=top+rows.length*rh+34;
 const ctl=rows.filter(r=>r.kind==='control');
 let nfA=ctl.length?Math.max(...ctl.map(r=>r.alone_ci[1])):0.5, nfU=ctl.length?Math.max(...ctl.map(r=>Math.max(Math.abs(r.unique_ci[0]),Math.abs(r.unique_ci[1])))):0;
 if(floors){nfA=floors.alone;nfU=floors.unique;}
 const aLo=0.46,aHi=Math.max(0.7,...rows.map(r=>r.alone_ci[1]+0.01));
 const uLo=Math.min(-0.006,...rows.map(r=>r.unique_ci[0]-0.002)),uHi=Math.max(0.01,...rows.map(r=>r.unique_ci[1]+0.003));
 const xa=v=>L+(v-aLo)/(aHi-aLo)*P, xu=v=>L+P+G+(v-uLo)/(uHi-uLo)*P;
 let s='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 '+W+' '+H+'" width="'+W+'" style="max-width:100%;height:auto;border:1px solid var(--hair);background:#fff">';
 s+='<text x="'+L+'" y="16" font-size="12" font-weight="700">Alone: AUROC (0.5 = chance)</text><text x="'+(L+P+G)+'" y="16" font-size="12" font-weight="700">Unique: AUROC lost without it</text>';
 s+='<text x="'+L+'" y="30" font-size="10.5" fill="#666">grey band = the best a control family managed by luck</text>';
 s+='<rect x="'+xa(0.5)+'" y="'+top+'" width="'+Math.max(1,xa(nfA)-xa(0.5))+'" height="'+(rows.length*rh)+'" fill="#e9e9e9"/>';
 s+='<rect x="'+xu(-nfU)+'" y="'+top+'" width="'+Math.max(1,xu(nfU)-xu(-nfU))+'" height="'+(rows.length*rh)+'" fill="#e9e9e9"/>';
 s+='<line x1="'+xa(0.5)+'" x2="'+xa(0.5)+'" y1="'+top+'" y2="'+(top+rows.length*rh)+'" stroke="#111"/><line x1="'+xu(0)+'" x2="'+xu(0)+'" y1="'+top+'" y2="'+(top+rows.length*rh)+'" stroke="#111"/>';
 rows.forEach((r,i)=>{const y=top+i*rh+rh/2,c=KCOL[r.kind]||'#333';
  s+='<text x="'+(L-8)+'" y="'+(y+4)+'" font-size="11.5" text-anchor="end" fill="'+(r.constant_in_test?'#999':'#111')+'">'+esc(r.family.length>52?r.family.slice(0,50)+'…':r.family)+'</text>';
  if(r.constant_in_test){s+='<text x="'+(L+6)+'" y="'+(y+4)+'" font-size="10.5" fill="#999">no variation in this test set</text>';return;}
  s+='<rect x="'+xa(Math.min(0.5,r.alone_auroc))+'" y="'+(y-6)+'" width="'+Math.abs(xa(r.alone_auroc)-xa(0.5))+'" height="12" fill="'+c+'"><title>'+esc(r.family)+': alone '+r.alone_auroc.toFixed(3)+' ('+r.alone_ci[0].toFixed(3)+' to '+r.alone_ci[1].toFixed(3)+')</title></rect>';
  s+='<line x1="'+xa(r.alone_ci[0])+'" x2="'+xa(r.alone_ci[1])+'" y1="'+y+'" y2="'+y+'" stroke="#111" stroke-width="1.4"/>';
  s+='<rect x="'+xu(Math.min(0,r.unique_gain))+'" y="'+(y-6)+'" width="'+Math.max(1,Math.abs(xu(r.unique_gain)-xu(0)))+'" height="12" fill="'+c+'"><title>'+esc(r.family)+': unique '+r.unique_gain.toFixed(4)+' ('+r.unique_ci[0].toFixed(4)+' to '+r.unique_ci[1].toFixed(4)+')</title></rect>';
  s+='<line x1="'+xu(r.unique_ci[0])+'" x2="'+xu(r.unique_ci[1])+'" y1="'+y+'" y2="'+y+'" stroke="#111" stroke-width="1.4"/>';});
 s+='<text x="'+xa(0.5)+'" y="'+(H-14)+'" font-size="10" text-anchor="middle">0.5</text><text x="'+xa(aHi)+'" y="'+(H-14)+'" font-size="10" text-anchor="end">'+aHi.toFixed(2)+'</text>';
 s+='<text x="'+xu(0)+'" y="'+(H-14)+'" font-size="10" text-anchor="middle">0</text><text x="'+xu(uHi)+'" y="'+(H-14)+'" font-size="10" text-anchor="end">+'+uHi.toFixed(3)+'</text></svg>';
 const wrap=h('div');wrap.innerHTML=s;return wrap;}
function ledgerSection(main,ledger,pled){
 const sec=(t,a)=>{main.append(h('h2',null,t));if(a)main.append(h('div',{class:'small',style:'max-width:900px;margin-bottom:4px'},a));};
 sec('Where the information comes from','Every kind of source measured the same way, protocol choices and silly ones alike. Bars are AUROC with 95% intervals. Anything no taller than the grey band is not distinguishable from luck. Kept even when useless: trends are worth knowing about and correcting for.');
 const st=Object.keys(ledger.settings);let cur=st[0],grp='prospective (headline)';const holder=h('div');
 const bar=h('div',{class:'row'});
 const draw=()=>{bar.replaceChildren(...st.map(k=>h('button',{class:k===cur?'primary':'',onclick:()=>{cur=k;draw();}},k)),h('span',{class:'small'},' on '),...Object.keys(ledger.settings[cur].groups).map(g=>h('button',{class:g===grp?'primary':'',onclick:()=>{grp=g;draw();}},g)));
  const sv=ledger.settings[cur],gv=sv.groups[grp]||sv.groups[Object.keys(sv.groups)[0]];
  const rows=gv.rows.filter(r=>r.kind!=='joke').slice().sort((a,b)=>b.alone_auroc-a.alone_auroc);
  holder.replaceChildren(h('div',{class:'small'},'Train: '+sv.train+' · test: '+sv.test+' · '+fmt(gv.n)+' trials, '+fmt(gv.failures)+' failures · everything together: AUROC '+f3(gv.full_model_auroc)),ledgerChart(rows,ledger.kinds),
   h('div',{class:'small',style:'margin-top:4px'},...Object.entries(ledger.kinds).filter(([k])=>k!=='joke').map(([k,v])=>h('span',{class:'lgd'},h('i',{style:'background:'+KCOL[k]}),v))));};
 draw();main.append(bar,holder,h('div',{class:'small',style:'max-width:900px'},ledger.reading));
 if(pled)protocolLedger(main,pled);
 astroCorner(main,ledger);}
function astroCorner(main,ledger){
 const M=ledger.mercury,o=M.overall,box=h('div',{class:'astro'});
 const stars=[...Array(14)].map((_,i)=>'<text class="twk" x="'+(20+i*62+(i%3)*9)+'" y="'+(16+(i*37)%46)+'" font-size="'+(12+(i%4)*3)+'" fill="#e8b400">'+(i%2?'*':'+')+'</text>').join('');
 const planet='<g transform="translate(60,62)"><circle r="26" fill="url(#mg)" stroke="#7a1fa2" stroke-width="3"/><circle cx="-8" cy="-6" r="5" fill="#00000022"/><circle cx="9" cy="8" r="3.5" fill="#00000022"/><path d="M-44,30 C-20,60 30,60 50,26" fill="none" stroke="#e0409a" stroke-width="4" stroke-dasharray="7 5"/><path d="M50,26 l-12,-3 m12,3 l-3,12" stroke="#e0409a" stroke-width="4" fill="none"/></g>';
 const verdict=o.p<0.05?'The stars are ... mildly suspicious (p = '+o.p+')':'The stars say: ¯\\_(ツ)_/¯ (p = '+o.p+')';
 box.append(h('h2',null,'The Mercury Retrograde Report'));
 const hd=h('div');hd.innerHTML='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 110" width="900" style="max-width:100%;height:auto"><defs><radialGradient id="mg" cx="35%" cy="30%"><stop offset="0" stop-color="#ffe6a8"/><stop offset="1" stop-color="#d98a3d"/></radialGradient></defs>'+stars+planet+'<text x="130" y="58" font-size="16" fill="#4b1d6b" font-weight="700">"My trial started during a retrograde. Is that why it failed?"</text><text x="130" y="82" font-size="12.5" fill="#7a5a8a">Computed from the orbits of Mercury and Earth, not looked up. '+Math.round(100*M.share_of_trials_in_retrograde)+'% of trials start in one.</text></svg>';
 box.append(hd);
 box.append(h('div',{class:'bubble'},verdict));
 box.append(h('div',{style:'margin:4px 0'},'Started in a retrograde: ',h('b',null,pct(o.rate_retro,2)+' failed to recruit'),' ('+fmt(o.failures_retro)+' of '+fmt(o.n_retro)+'). Otherwise: ',h('b',null,pct(o.rate_not,2)),' ('+fmt(o.failures_not)+' of '+fmt(o.n_not)+'). Rate ratio ',h('b',null,o.rr+' ('+o.rr_ci[0]+' to '+o.rr_ci[1]+')'),'.'));
 const yrs=Object.entries(M.by_year),W=900,rowh=22,H=34+yrs.length*rowh+26,lo=0.4,hi=2.6,xs=v=>150+(Math.log(Math.max(lo,Math.min(hi,v)))-Math.log(lo))/(Math.log(hi)-Math.log(lo))*700;
 let s='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 '+W+' '+H+'" width="'+W+'" style="max-width:100%;height:auto"><text x="150" y="16" font-size="12" font-weight="700" fill="#4b1d6b">Each year on its own: rate ratio (retrograde / not), 1 = the planet does nothing</text>';
 s+='<line x1="'+xs(1)+'" x2="'+xs(1)+'" y1="26" y2="'+(H-22)+'" stroke="#b07bff" stroke-width="3" stroke-dasharray="6 5"/>';
 yrs.forEach(([y,v],i)=>{const yy=40+i*rowh,sig=v.p<0.05;
  s+='<text x="140" y="'+(yy+4)+'" font-size="12" text-anchor="end">'+y+'</text><line x1="'+xs(v.rr_ci[0])+'" x2="'+xs(v.rr_ci[1])+'" y1="'+yy+'" y2="'+yy+'" stroke="'+(sig?'#e0409a':'#8a6aa8')+'" stroke-width="3" stroke-linecap="round"/><circle cx="'+xs(v.rr)+'" cy="'+yy+'" r="'+(sig?7:5)+'" fill="'+(sig?'#e0409a':'#7a1fa2')+'" stroke="#fff" stroke-width="2"><title>'+y+': '+v.rr+' ('+v.rr_ci[0]+' to '+v.rr_ci[1]+'), p '+v.p+'</title></circle>'+(sig?'<text x="'+(xs(v.rr_ci[1])+10)+'" y="'+(yy+4)+'" font-size="12" fill="#e0409a">p '+v.p+' !</text>':'');});
 s+='<text x="'+xs(0.5)+'" y="'+(H-6)+'" font-size="10.5" text-anchor="middle">0.5</text><text x="'+xs(1)+'" y="'+(H-6)+'" font-size="10.5" text-anchor="middle">1</text><text x="'+xs(2)+'" y="'+(H-6)+'" font-size="10.5" text-anchor="middle">2</text></svg>';
 const ch=h('div');ch.innerHTML=s;box.append(ch);
 const jr=[];Object.entries(ledger.settings).forEach(([k,sv])=>{const g=sv.groups['prospective (headline)']||Object.values(sv.groups)[0];const r=g.rows.find(r=>r.kind==='joke');if(r)jr.push(k.split(' (')[0]+': AUROC '+r.alone_auroc.toFixed(3)+' ('+r.alone_ci[0].toFixed(3)+' to '+r.alone_ci[1].toFixed(3)+'), unique '+(r.unique_gain>=0?'+':'')+r.unique_gain.toFixed(4));});
 box.append(h('div',{class:'small',style:'margin-top:4px'},'As a predictor on prospective trials, the planet alone scores — '+jr.join(' · ')+'. Chance is 0.5.'));
 box.append(h('div',{class:'small',style:'margin-top:6px'},M.note+' Used nowhere in AutoRAN. It is here because it was asked for, and because it shows what luck looks like next to the real sources above.'));
 main.append(box);}
function protocolLedger(main,pl){
 main.append(h('h2',null,'Where the information comes from: protocol documents'));
 main.append(h('div',{class:'small',style:'max-width:900px'},pl.reading));
 const vs=Object.keys(pl.variants);let cur=vs[0];const holder=h('div'),bar=h('div',{class:'row'});
 const draw=()=>{bar.replaceChildren(...vs.map(k=>h('button',{class:k===cur?'primary':'',onclick:()=>{cur=k;draw();}},k)));
  const v=pl.variants[cur],rows=v.rows.slice().sort((a,b)=>b.alone_auroc-a.alone_auroc);
  holder.replaceChildren(h('div',{class:'small'},v.about+' · '+fmt(v.n)+' test documents, '+fmt(v.failures)+' failures · registry factors alone: AUROC '+f3(v.baseline_auroc)+' · registry plus every document family: '+f3(v.full_auroc)),ledgerChart(rows,pl.kinds));};
 draw();main.append(bar,holder);}


function scaledSection(main,sc){
 main.append(h('h2',null,'Scaled run: what sticks across ten test windows'));
 main.append(h('div',{class:'small',style:'max-width:900px;margin-bottom:4px'},'Ten rolling-origin sets: each is trained only on trials that started two or more years before its two-year test window (2008–09 up to 2017–18). Bar = mean unique gain across the sets, dots = each set. A family “sticks” (rule fixed in advance) when its unique gain is positive in at least 8 of 10 sets and above the 95th percentile of 30 random-number families. Overlapping families share credit, so a family that duplicates another can look empty here while being informative alone.'));
 let grp='prospective (headline)';const holder=h('div'),bar=h('div',{class:'row'});
 const draw=()=>{bar.replaceChildren(...Object.keys(sc.summary).map(g=>h('button',{class:g===grp?'primary':'',onclick:()=>{grp=g;draw();}},g)));
  const sm=sc.summary[grp],rows=sm.rows.slice().sort((a,b)=>b.mean_unique-a.mean_unique),per=sc.per_set_unique[grp];
  const W=940,L=370,P=380,rh=20,top=40,H=top+rows.length*rh+30;const all=Object.values(per).flat();
  const lo=Math.min(-0.006,...all)-0.001,hi=Math.max(0.012,...all)+0.001,xs=v=>L+(v-lo)/(hi-lo)*P;
  let s='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 '+W+' '+H+'" width="'+W+'" style="max-width:100%;height:auto;border:1px solid var(--hair);background:#fff">';
  s+='<text x="'+L+'" y="16" font-size="12" font-weight="700">Unique AUROC gain (mean of 10 sets; dots = each set)</text><text x="'+L+'" y="30" font-size="10.5" fill="#666">grey band: up to the 95th percentile of 30 random families ('+sm.noise_floor_unique_95th.toFixed(5)+')</text>';
  s+='<rect x="'+xs(Math.min(0,sm.noise_floor_unique_95th))+'" y="'+top+'" width="'+Math.max(1,Math.abs(xs(sm.noise_floor_unique_95th)-xs(0)))+'" height="'+(rows.length*rh)+'" fill="#e9e9e9"/><line x1="'+xs(0)+'" x2="'+xs(0)+'" y1="'+top+'" y2="'+(top+rows.length*rh)+'" stroke="#111"/>';
  const chipc={sticks:'#0b6b2e',suggestive:'#9a6700','not shown':'#999'};
  rows.forEach((r,i)=>{const y=top+i*rh+rh/2,c=KCOL[r.kind]||'#333';
   s+='<text x="'+(L-8)+'" y="'+(y+4)+'" font-size="11" text-anchor="end" fill="'+chipc[r.status]+'">'+esc(r.family.length>56?r.family.slice(0,54)+'…':r.family)+'</text>';
   s+='<rect x="'+xs(Math.min(0,r.mean_unique))+'" y="'+(y-5)+'" width="'+Math.max(1,Math.abs(xs(r.mean_unique)-xs(0)))+'" height="10" fill="'+c+'" opacity="'+(r.status==='sticks'?1:r.status==='suggestive'?0.6:0.3)+'"><title>'+esc(r.family)+': mean unique '+r.mean_unique+', positive in '+r.sets_positive+' of '+r.sets+' ('+r.status+'), alone '+r.mean_alone+'</title></rect>';
   (per[r.family]||[]).forEach(v=>{s+='<circle cx="'+xs(v)+'" cy="'+y+'" r="2.4" fill="#111" opacity=".55"/>';});
   s+='<text x="'+(L+P+10)+'" y="'+(y+4)+'" font-size="10.5" fill="'+chipc[r.status]+'">'+r.status+' · '+r.sets_positive+'/'+r.sets+'</text>';});
  s+='<text x="'+xs(0)+'" y="'+(H-10)+'" font-size="10" text-anchor="middle">0</text><text x="'+xs(hi)+'" y="'+(H-10)+'" font-size="10" text-anchor="end">+'+hi.toFixed(3)+'</text></svg>';
  const w=h('div');w.innerHTML=s;
  const m=sc.mlp[grp],tot=sc.sets.reduce((a,x)=>a+x.test_n,0),totf=sc.sets.reduce((a,x)=>a+x.test_failures,0);
  holder.replaceChildren(h('div',{class:'small'},fmt(tot)+' trial-tests in ten windows ('+fmt(totf)+' failures; trials in two overlapping windows count twice). A small neural network on the same inputs scored AUROC '+f3(m.network_mean)+' against '+f3(m.ridge_mean)+' for the ridge model, better in '+m.network_better_in_sets+' of '+m.sets+' sets: a bigger learner did not help.'),w);};
 draw();main.append(bar,holder);}
function syntheticSection(main,sy){
 main.append(h('h2',null,'Twelve synthetic protocols (capability check only)'));
 main.append(h('div',{class:'warn'},'Synthetic data written by the same model that analysed them. Four were designed to fail, four to be ordinary, four with risk engineered down. This shows whether the machinery reads the intended differences, not accuracy. Never mixed with real figures, never used in validation.'));
 const cat={weak:'chip pos',average:'chip oth',strong:'chip neg'},rows=sy.documents.slice().sort((a,b)=>b.stack_risk-a.stack_risk);
 const t=h('table',{style:'max-width:980px'},h('tr',null,['Document','Designed as','Registry-factor risk','Stack risk (registry + document families)','Checklist items present','Planned per site per month','Simulator stop probability (scenario)'].map(x=>h('th',null,x))));
 rows.forEach(d=>t.append(h('tr',null,h('td',{class:'m'},d.id),h('td',null,h('span',{class:cat[d.category]},d.category)),h('td',{class:'n'},pct(d.registry_factor_risk,1)),h('td',{class:'n'},pct(d.stack_risk,1)),h('td',{class:'n'},d.briel_distinct_items+' of 14'),h('td',{class:'n'},d.required_per_site_per_month),h('td',{class:'n'},pct(d.simulator_stop_probability,0)))));
 main.append(t);
 if(sy.reading)main.append(h('div',{class:'small',style:'max-width:900px;margin-top:4px'},sy.reading));}


// ------------------------------------------------------------------ Evidence: every local test in one place, with a factor combiner
const GCOL={registry:'#0040ff',baseline:'#8a8a8a',model:'#7a3fb8',documents:'#0b6b2e',simulator:'#b00020'};
function tableEl(heads,rows,num){const t=h('table',{style:'max-width:1000px'},h('tr',null,heads.map((x,i)=>h('th',{class:(num||[]).includes(i)?'n':''},x))));rows.forEach(r=>t.append(h('tr',null,r.map((c,i)=>h('td',{class:(num||[]).includes(i)?'n':''},c==null?'':c)))));return t;}
function svgBox(s){const w=h('div');w.innerHTML=s;return w;}
function saveFile(name,text,type){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{type:type}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),2000);}
function exportBar(holder,name,rows){return h('span',{class:'small'},h('button',{onclick:()=>{const s=holder.querySelector('svg');if(s)saveFile(name+'.svg',new XMLSerializer().serializeToString(s),'image/svg+xml');}},'Save chart (SVG)'),' ',rows?h('button',{onclick:()=>saveFile(name+'.csv',rows.map(r=>r.map(v=>'"'+String(v==null?'':v).replace(/"/g,'""')+'"').join(',')).join('\n'),'text/csv')},'Save table (CSV)'):'');}
function lineChart(o){
 const W=o.w||420,H=o.h||310,L=48,B=40,T=16,R=14,pw=W-L-R,ph=H-T-B,x0=o.xmin==null?0:o.xmin,x1=o.xmax==null?1:o.xmax,y0=o.ymin==null?0:o.ymin,y1=o.ymax==null?1:o.ymax;
 const X=v=>L+(v-x0)/(x1-x0)*pw,Y=v=>T+ph-(v-y0)/(y1-y0)*ph;
 let s='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 '+W+' '+H+'" width="'+W+'" style="max-width:100%;height:auto;border:1px solid var(--hair);background:#fff">';
 for(let i=0;i<=5;i++){const xv=x0+(x1-x0)*i/5,yv=y0+(y1-y0)*i/5;
  s+='<line x1="'+X(xv)+'" x2="'+X(xv)+'" y1="'+T+'" y2="'+(T+ph)+'" stroke="#eee"/><line x1="'+L+'" x2="'+(L+pw)+'" y1="'+Y(yv)+'" y2="'+Y(yv)+'" stroke="#eee"/>';
  s+='<text x="'+X(xv)+'" y="'+(H-22)+'" font-size="10" text-anchor="middle" fill="#555">'+xv.toFixed(x1-x0>2?0:2)+'</text><text x="'+(L-6)+'" y="'+(Y(yv)+3)+'" font-size="10" text-anchor="end" fill="#555">'+yv.toFixed(y1-y0>0.5?1:y1-y0>0.05?2:3)+'</text>';}
 s+='<text x="'+(L+pw/2)+'" y="'+(H-6)+'" font-size="11" text-anchor="middle">'+esc(o.xlab||'')+'</text><text transform="translate(12,'+(T+ph/2)+') rotate(-90)" font-size="11" text-anchor="middle">'+esc(o.ylab||'')+'</text>';
 (o.series||[]).forEach(se=>{if(o.points||se.points){se.pts.forEach(p=>{s+='<circle cx="'+X(p[0])+'" cy="'+Y(p[1])+'" r="'+(se.r||4)+'" fill="'+se.color+'" opacity=".85"/>';});}
  else{s+='<polyline fill="none" stroke="'+se.color+'" stroke-width="'+(se.w||2)+'"'+(se.dash?' stroke-dasharray="5 4"':'')+' points="'+se.pts.map(p=>X(p[0])+','+Y(p[1])).join(' ')+'"/>';}});
 (o.legend||[]).forEach((l,i)=>{s+='<rect x="'+(L+10)+'" y="'+(T+8+i*15)+'" width="10" height="3" fill="'+l.color+'"/><text x="'+(L+25)+'" y="'+(T+13+i*15)+'" font-size="10.5">'+esc(l.name)+'</text>';});
 return svgBox(s+'</svg>');}
function ladderChart(items){
 const W=940,L=420,P=420,rh=22,top=30,H=top+items.length*rh+26,lo=0.45,hi=0.85,X=v=>L+(Math.min(hi,Math.max(lo,v))-lo)/(hi-lo)*P;
 let s='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 '+W+' '+H+'" width="'+W+'" style="max-width:100%;height:auto;border:1px solid var(--hair);background:#fff"><text x="'+L+'" y="16" font-size="12" font-weight="700">AUROC (0.5 = chance, dashed)</text>';
 [0.5,0.6,0.7,0.8].forEach(v=>{s+='<line x1="'+X(v)+'" x2="'+X(v)+'" y1="'+top+'" y2="'+(top+items.length*rh)+'" stroke="'+(v===0.5?'#111':'#e6e6e6')+'"'+(v===0.5?' stroke-dasharray="4 3"':'')+'/><text x="'+X(v)+'" y="'+(H-8)+'" font-size="10" text-anchor="middle">'+v.toFixed(1)+'</text>';});
 items.forEach((it,i)=>{const y=top+i*rh+rh/2,c=GCOL[it.group]||'#333';
  s+='<text x="'+(L-8)+'" y="'+(y+4)+'" font-size="11.5" text-anchor="end">'+esc(it.label.length>64?it.label.slice(0,62)+'…':it.label)+'</text><rect x="'+X(0.5)+'" y="'+(y-6)+'" width="'+Math.max(1,X(it.auroc)-X(0.5))+'" height="12" fill="'+c+'"><title>'+esc(it.label)+': '+it.auroc.toFixed(3)+'</title></rect>';
  if(it.ci)s+='<line x1="'+X(it.ci[0])+'" x2="'+X(it.ci[1])+'" y1="'+y+'" y2="'+y+'" stroke="#111" stroke-width="1.4"/>';
  s+='<text x="'+(X(it.auroc)+6)+'" y="'+(y+4)+'" font-size="11" font-weight="700">'+it.auroc.toFixed(3)+'</text>';});
 return svgBox(s+'</svg>');}
function heatmap(c,labels){
 const n=c.families.length,cs=15,L=300,T=24,W=L+n*cs+20,H=T+n*cs+10;
 const col=v=>{if(v==null)return '#f4f4f4';const a=Math.min(1,Math.abs(v));return v>=0?'rgb('+Math.round(255-a*215)+','+Math.round(255-a*160)+',255)':'rgb(255,'+Math.round(255-a*170)+','+Math.round(255-a*210)+')';};
 let s='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 '+W+' '+H+'" width="'+W+'" style="max-width:100%;height:auto;border:1px solid var(--hair);background:#fff">';
 c.families.forEach((f,i)=>{s+='<text x="'+(L-6)+'" y="'+(T+i*cs+11)+'" font-size="9.5" text-anchor="end">'+esc(f.length>46?f.slice(0,44)+'…':f)+'</text><text x="'+(L+i*cs+cs/2)+'" y="'+(T-6)+'" font-size="8" text-anchor="middle">'+(i+1)+'</text>';
  c.matrix[i].forEach((v,j)=>{s+='<rect x="'+(L+j*cs)+'" y="'+(T+i*cs)+'" width="'+cs+'" height="'+cs+'" fill="'+col(v)+'"><title>'+esc(f)+' × '+esc(c.families[j])+': '+(v==null?'n/a':v)+'</title></rect>';});});
 return svgBox(s+'</svg>');}
function statCards(cards){return h('div',{class:'tiles'},cards.map(t=>h('div',{class:'tile'},h('div',{class:'l'},t.label),h('div',{class:'v'},t.fmt==='auc'?f3(t.value):t.fmt==='pct'?pct(t.value):t.fmt==='int'?fmt(t.value):t.fmt==='num'?f3(t.value):String(t.value)),h('div',{class:'s'},(t.ci?'95% '+f3(t.ci[0])+' to '+f3(t.ci[1])+' · ':'')+(t.note||'')))));}
function evSec(box,t,about){box.append(h('h2',null,t));if(about)box.append(h('div',{class:'small',style:'max-width:920px;margin-bottom:4px'},about));}

async function evidencePanel(main){
 let E;try{E=await api('/api/evidence');}catch(e){return;}
 if(!E.parts.run&&!E.parts.scaled_registry)return;
 const box=h('div',{style:'border:2px solid var(--rule);padding:8px 12px;margin:10px 0;max-width:1000px'});
 box.append(h('div',{class:'row'},h('b',{style:'font-size:15px'},'What the local tests have read'),h('span',{class:'small'},'exploratory · association, not cause · machine-made labels'),h('button',{class:'primary',onclick:()=>{S.evTab='summary';location.hash='evidence';}},'Open the evidence'),h('button',{onclick:()=>{S.evTab='combine';location.hash='evidence';}},'Combine factors')));
 box.append(statCards(E.headline.cards.slice(0,6)));
 if(E.headline.ladder.length)box.append(ladderChart(E.headline.ladder.slice(0,8)));
 E.headline.sentences.slice(0,3).forEach(t=>box.append(h('div',{class:'small',style:'margin-top:3px'},'· '+t)));
 const w=[...main.children].find(e=>e.tagName==='H2'&&e.textContent==='Warnings');
 if(w)main.insertBefore(box,w);else main.append(box);}

async function evidence(main){
 main.append(h('h2',null,'Evidence'));
 const E=await api('/api/evidence');
 if(!E.parts.run&&!E.parts.scaled_registry){main.append(h('div',null,'No test results yet. Open Simulate and press Run the tests, or run the local research scripts.'));return;}
 const tabs=[['summary','Summary'],['factors','Factors'],['combine','Combine factors'],['docs','Protocol documents'],['simulator','Simulator'],['checks','Checks'],['synthetic','Synthetic protocols'],['gates','Gates and files']];
 S.evTab=S.evTab||'summary';
 const bar=h('div',{class:'row'}),body=h('div');
 if(!$('presx')){document.body.append(h('button',{id:'presx',class:'primary',onclick:()=>document.body.classList.remove('pres')},'Exit presentation mode'));}
 const pres=h('button',{onclick:()=>document.body.classList.add('pres')},'Presentation mode (hides the menu, larger type)');
 main.append(h('div',{class:'warn'},h('b',null,'Exploratory. '),'Association in registry and protocol data with machine-made labels; nothing here shows that changing a protocol changes outcomes. The sealed vault and the frozen test split are never read.'),bar,body);
 const draw=()=>{bar.replaceChildren(...tabs.map(([k,l])=>h('button',{class:k===S.evTab?'primary':'',onclick:()=>{S.evTab=k;draw();}},l)),pres);body.replaceChildren();
  ({summary:sumTab,factors:facTab,combine:combTab,docs:docTab,simulator:simTab,checks:chkTab,synthetic:synTab,gates:gateTab}[S.evTab])(body,E).catch(e=>body.append(h('div',{class:'warn bad'},'Error: '+e.message)));};
 draw();}

async function sumTab(box,E){
 const H=E.headline;
 box.append(statCards(H.cards));
 evSec(box,'AUROC across the tests','Every score here is on held-out data. Bars start at chance (0.5). Whiskers are 95% intervals where the test gives one. Different rows use different cohorts (registry-wide, documents dated before the trial start, simulated trials), so compare within a colour, not across.');
 const lad=ladderChart(H.ladder);box.append(lad,exportBar(lad,'auroc-across-tests',[['test','auroc'],...H.ladder.map(x=>[x.label,x.auroc])]));
 evSec(box,'What the tests read');
 H.sentences.forEach(t=>box.append(h('div',{style:'margin:3px 0;max-width:920px'},'· '+t)));
 if(E.scaled_registry){evSec(box,'What stuck across ten windows (top families)','Mean unique AUROC gain over ten rolling windows, prospective trials. Green names stuck by the rule fixed in advance.');
  const sm=E.scaled_registry.summary['prospective (headline)'],rows=sm.rows.slice().sort((a,b)=>b.mean_unique-a.mean_unique).slice(0,12);
  const items=rows.map(r=>({label:r.family+(r.status==='sticks'?'  (sticks)':''),auroc:0.5+r.mean_unique*10,ci:null,group:r.status==='sticks'?'documents':'baseline'}));
  box.append(tableEl(['Family','Kind','Mean unique gain','Windows positive','Alone AUROC','Status'],rows.map(r=>[r.family,r.kind,'+'+r.mean_unique.toFixed(4),r.sets_positive+' of '+r.sets,f3(r.mean_alone),h('span',{class:'chip '+(r.status==='sticks'?'neg':r.status==='suggestive'?'oth':'unl')},r.status)]),[2,3,4]));
  box.append(h('div',{class:'row'},h('button',{onclick:()=>{S.evTab='factors';location.hash='evidence';}},'All factors'),h('button',{onclick:()=>{S.evTab='combine';location.hash='evidence';}},'Combine them')));}
 if(E.scaled_protocol){const v=E.scaled_protocol.variants.strict||Object.values(E.scaled_protocol.variants)[0];
  evSec(box,'Protocol-document families (documents dated at or before the trial start)','Gain over registry factors, sponsor identity and registry text, ten repeated five-fold partitions.');
  box.append(tableEl(['Family','Alone AUROC','Gain over baseline (95% interval)','Repeats positive','Status'],v.rows.slice().sort((a,b)=>b.gain_over_baseline-a.gain_over_baseline).slice(0,8).map(r=>[r.family.length>78?r.family.slice(0,76)+'…':r.family,f3(r.alone_auroc),(r.gain_over_baseline>=0?'+':'')+r.gain_over_baseline.toFixed(4)+' ('+r.gain_ci[0].toFixed(4)+' to '+r.gain_ci[1].toFixed(4)+')',r.repeats_positive_gain+' of '+r.repeats,h('span',{class:'chip '+(r.status==='sticks'?'neg':r.status==='suggestive'?'oth':'unl')},r.status)]),[1,2,3]));}
 evSec(box,'Where each result comes from','Everything above is read from files on this computer. The Gates and files tab lists them with their dates.');}

async function facTab(box,E){
 if(E.scaled_registry){evSec(box,'Registry factor families over ten windows');scaledSection(box,E.scaled_registry);
  const sc=E.scaled_registry,grp='prospective (headline)';
  evSec(box,'Ridge against a small neural network, window by window','Same inputs. A bigger learner did not help.');
  const wins=sc.sets.map((s,i)=>[i,s]);const ln=lineChart({w:520,xmin:0,xmax:wins.length-1,ymin:0.6,ymax:0.85,xlab:'test window (2008–09 … 2017–18)',ylab:'AUROC',series:[{name:'ridge',color:'#0040ff',pts:wins.map(([i,s])=>[i,s.mlp[grp].ridge])},{name:'network',color:'#b00020',pts:wins.map(([i,s])=>[i,s.mlp[grp].network])}],legend:[{name:'ridge',color:'#0040ff'},{name:'network',color:'#b00020'}]});
  box.append(ln,exportBar(ln,'ridge-vs-network',[['window','ridge','network'],...wins.map(([i,s])=>[s.window.join('-'),s.mlp[grp].ridge,s.mlp[grp].network])]));
  evSec(box,'Test volume per window');box.append(tableEl(['Window','Training trials (failures)','Test trials (failures)','Prospective test trials (failures)'],sc.sets.map(s=>[s.window.join('–'),fmt(s.train_n)+' ('+fmt(s.train_failures)+')',fmt(s.test_n)+' ('+fmt(s.test_failures)+')',fmt(s.test_prospective_n)+' ('+fmt(s.test_prospective_failures)+')'])));}
 if(E.run&&E.run.ledger)ledgerSection(box,E.run.ledger,null);
 if(E.run&&E.run.effects){const ef=E.run.effects;evSec(box,'Factor effects on recruitment failure','Adjusted odds ratios from one model; stable = the 95% bootstrap interval excludes 1. Evidence level: '+ef.level+'.');
  box.append(tableEl(['Factor','Odds ratio','95% interval','Stable','Failure rate with','Without','Trials with it'],ef.terms.filter(t=>t.support==null||t.support>=200).slice(0,30).map(t=>[t.term,f3(t.odds_ratio),t.lo==null?'':f3(t.lo)+' to '+f3(t.hi),t.stable==null?'':h('span',{class:'chip '+(t.stable?'neg':'')},t.stable?'stable':'not stable'),t.rate_with==null?'':pct(t.rate_with),t.rate_without==null?'':pct(t.rate_without),t.support==null?'':fmt(t.support)]),[1,4,5,6]));}
 const cr=await api('/api/evidence/correlation?setting=registry');
 if(cr&&cr.families){evSec(box,'Which factor families say the same thing','Correlation between families’ held-out scores (blue = move together, red = oppose, grey = constant in the test years). Overlap is why a family can look empty here while informative alone.');
  const hm=heatmap(cr);box.append(hm,exportBar(hm,'family-correlation',[['family',...cr.families],...cr.families.map((f,i)=>[f,...cr.matrix[i]])]));}}

async function combTab(box,E){
 const wb=E.workbench;
 if(!wb.registry&&!wb.protocol){box.append(h('div',null,'The factor combiner needs a workbench file from the local research scripts (workbench_registry.py, workbench_protocol.py).'));return;}
 let setting=wb.registry?'registry':'protocol',subset='prospective',base=true;const chosen=new Set();
 const fams=()=>wb[setting].families;
 const stick=()=>{if(setting==='registry'&&E.scaled_registry)return new Set(E.scaled_registry.summary['prospective (headline)'].rows.filter(r=>r.status==='sticks').map(r=>r.family));
  if(setting==='protocol'&&E.scaled_protocol){const v=E.scaled_protocol.variants.strict||Object.values(E.scaled_protocol.variants)[0];return new Set(v.rows.filter(r=>r.status==='sticks'&&r.kind!=='control').map(r=>r.family));}return new Set();};
 evSec(box,'Combine factors at will','Tick any families; they are fitted together on held-out data and scored. Registry: trained on starts to 2014, scored on 2016 to 2018. Documents: documents dated at or before the trial start, five-fold. Each family’s score is out of fold, so the combination is honest.');
 const ctl=h('div'),list=h('div'),out=h('div',{style:'margin-top:8px'});box.append(ctl,list,out);
 let timer=null;
 const schedule=()=>{clearTimeout(timer);timer=setTimeout(run,200);};
 const setSel=pred=>{chosen.clear();fams().forEach(f=>{if(pred(f))chosen.add(f.name);});drawList();schedule();};
 function drawCtl(){ctl.replaceChildren(h('div',{class:'row'},'Data',...[['registry','Registry factors'],['protocol','Protocol documents']].filter(([k])=>wb[k]).map(([k,l])=>h('button',{class:k===setting?'primary':'',onclick:()=>{setting=k;chosen.clear();stick().forEach(n=>chosen.add(n));drawCtl();drawList();schedule();}},l)),
   h('span',{class:'small'},' scored on '),...['prospective','all'].map(k=>h('button',{class:k===subset?'primary':'',onclick:()=>{subset=k;drawCtl();schedule();}},k==='prospective'?'prospective registrations':'all trials')),
   setting==='protocol'?h('label',{style:'margin-left:10px'},h('input',{type:'checkbox',checked:base?'checked':null,onchange:e=>{base=e.target.checked;schedule();}}),' include the registry baseline'):''),
  h('div',{class:'row'},'Presets',h('button',{onclick:()=>setSel(f=>stick().has(f.name))},'only what stuck'),h('button',{onclick:()=>setSel(f=>true)},'everything'),h('button',{onclick:()=>setSel(f=>f.kind==='protocol')},'protocol choices'),h('button',{onclick:()=>setSel(f=>f.kind==='who')},'who runs it'),
   h('button',{onclick:()=>setSel(f=>f.kind!=='hindsight')},'no hindsight'),h('button',{onclick:()=>setSel(f=>['control','joke','incidental'].includes(f.kind))},'silly ones only'),h('button',{onclick:()=>setSel(f=>false)},'clear')));}
 function drawList(){const byKind={};fams().forEach(f=>{(byKind[f.kind]=byKind[f.kind]||[]).push(f);});
  list.replaceChildren(...Object.entries(byKind).map(([k,fs])=>h('div',{style:'margin:3px 0'},h('span',{class:'small',style:'display:inline-block;min-width:130px;font-weight:700;color:'+(KCOL[k]||'#333')},k),...fs.map(f=>h('label',{style:'margin-right:14px;white-space:nowrap;display:inline-block'},h('input',{type:'checkbox',checked:chosen.has(f.name)?'checked':null,onchange:e=>{e.target.checked?chosen.add(f.name):chosen.delete(f.name);schedule();}}),' '+(f.name.length>70?f.name.slice(0,68)+'…':f.name))))));}
 async function run(){
  if(!chosen.size&&!(setting==='protocol'&&base)){out.replaceChildren(h('div',{class:'small'},'Tick at least one family.'));return;}
  out.replaceChildren(h('div',{class:'small'},'Fitting…'));
  let r;try{r=await api('/api/evidence/combine',{setting:setting,families:[...chosen],subset:subset,include_baseline:base});}catch(e){out.replaceChildren(h('div',{class:'warn bad'},e.message));return;}
  const ref=r.reference,b5=r.at_budget[1];
  out.replaceChildren(statCards([{label:'AUROC',value:r.auroc,fmt:'auc',ci:r.auroc_ci,note:r.n.toLocaleString()+' trials, '+r.failures+' failures'},{label:'AUPRC',value:r.auprc,fmt:'num',note:'guessing level '+r.base_rate.toFixed(3)},{label:'Precision in the top 5%',value:b5.precision,fmt:'pct',note:b5.lift+'x lift, recall '+pct(b5.recall)},
   {label:'Calibration error',value:r.ece,fmt:'num',note:'0 = stated risks are true rates'},{label:'All families together',value:ref.all_families_auroc,fmt:'auc',note:'for comparison'},{label:'Best single family',value:ref.best_single_auroc,fmt:'auc',note:ref.best_single_family.slice(0,40)}]));
  const roc=lineChart({xlab:'false positive rate',ylab:'true positive rate',series:[{name:'combination',color:'#0040ff',pts:r.roc,w:2.5},{name:'chance',color:'#999',dash:true,pts:[[0,0],[1,1]]}],legend:[{name:'ROC of this combination',color:'#0040ff'},{name:'chance',color:'#999'}]});
  const prm=Math.max(...r.pr.map(p=>p[1]),r.base_rate)*1.1;
  const prc=lineChart({xlab:'recall',ylab:'precision',ymax:prm,series:[{name:'combination',color:'#b00020',pts:r.pr,w:2.5},{name:'base rate',color:'#999',dash:true,pts:[[0,r.base_rate],[1,r.base_rate]]}],legend:[{name:'precision-recall',color:'#b00020'},{name:'guessing level',color:'#999'}]});
  const cm=Math.max(...r.calibration.map(c=>Math.max(c.pred,c.obs)))*1.1;
  const cal=lineChart({xlab:'predicted failure rate (tenths of trials)',ylab:'observed rate',xmax:cm,ymax:cm,points:true,series:[{name:'bins',color:'#0b6b2e',pts:r.calibration.map(c=>[c.pred,c.obs]),r:5},{name:'ideal',color:'#999',dash:true,pts:[[0,0],[cm,cm]],points:false}]});
  out.append(h('div',{style:'display:flex;flex-wrap:wrap;gap:12px;margin-top:8px'},h('div',null,h('div',{class:'small'},'ROC curve'),roc),h('div',null,h('div',{class:'small'},'Precision against recall'),prc),h('div',null,h('div',{class:'small'},'Calibration'),cal)),
   exportBar(roc,'combination-roc',[['family','weight','alone AUROC'],...Object.entries(r.weights).map(([k,v])=>[k,v,r.alone[k]])]));
  out.append(h('h3',null,'Review budget'),tableEl(['If you flag the riskiest','Trials flagged','Precision','Recall','Lift over guessing'],r.at_budget.map(x=>[pct(x.budget,0),fmt(x.flagged),pct(x.precision),pct(x.recall),x.lift+'x']),[1,2,3,4]));
  out.append(h('h3',null,'Weights in the combination'),tableEl(['Family','Weight','Alone AUROC'],Object.entries(r.weights).map(([k,v])=>[k,v.toFixed(3),r.alone[k]==null?'':f3(r.alone[k])]),[1,2]),h('div',{class:'small',style:'max-width:900px;margin-top:4px'},ref.setting+'. A weight is the family’s share in the combination, not a causal effect. Overlapping families share credit.'));}
 stick().forEach(n=>chosen.add(n));drawCtl();drawList();run();}

async function docTab(box,E){
 if(E.scaled_protocol){evSec(box,'Protocol-document source ledger (scaled)');
  const pl=E.scaled_protocol,vs=Object.keys(pl.variants);let cur=vs[0];const holder=h('div'),bar=h('div',{class:'row'});
  box.append(h('div',{class:'small',style:'max-width:920px'},pl.reading));
  const draw=()=>{bar.replaceChildren(...vs.map(k=>h('button',{class:k===cur?'primary':'',onclick:()=>{cur=k;draw();}},k)));
   const v=pl.variants[cur],rows=v.rows.slice().sort((a,b)=>b.alone_auroc-a.alone_auroc);
   const fl={alone:v.noise_floor_alone_95th,unique:Math.max(Math.abs(v.random_gain_range[0]),Math.abs(v.random_gain_range[1]))};
   holder.replaceChildren(h('div',{class:'small'},v.about+' '+fmt(v.n)+' documents, '+fmt(v.failures)+' failures · baseline (registry, sponsor identity, registry text) '+f3(v.baseline_auroc)+' · plus every document family '+f3(v.full_auroc)),ledgerChart(rows,pl.kinds,null,fl),
    tableEl(['Family','Alone AUROC (95%)','Gain over baseline (95%)','Unique (95%)','Repeats positive','Status'],rows.map(r=>[r.family.length>70?r.family.slice(0,68)+'…':r.family,f3(r.alone_auroc)+' ('+r.alone_ci[0].toFixed(3)+' to '+r.alone_ci[1].toFixed(3)+')',(r.gain_over_baseline>=0?'+':'')+r.gain_over_baseline.toFixed(4)+' ('+r.gain_ci[0].toFixed(4)+' to '+r.gain_ci[1].toFixed(4)+')',(r.unique_gain>=0?'+':'')+r.unique_gain.toFixed(4),r.repeats_positive_gain+' of '+r.repeats,h('span',{class:'chip '+(r.status==='sticks'?'neg':r.status==='suggestive'?'oth':'unl')},r.status)]),[1,2,3,4]));};
  draw();box.append(bar,holder);}
 const gt=(t,about,rows,heads)=>{evSec(box,t,about);box.append(tableEl(heads,rows,heads.map((_,i)=>i).slice(1)));};
 if(E.sponsor_identity){const s=E.sponsor_identity;gt('Does sponsor identity explain the text gain?','Strict cohort of '+fmt(s.n)+' documents, '+s.failures+' failures, five-fold.',Object.entries(s.auroc).map(([k,v])=>[k,f3(v)]),['Stack','AUROC']);
  box.append(h('div',{class:'small'},'Document text over registry plus sponsor identity: '+(s.text_gain_over_registry_plus_sponsor_identity.gain>=0?'+':'')+s.text_gain_over_registry_plus_sponsor_identity.gain.toFixed(4)+' ('+s.text_gain_over_registry_plus_sponsor_identity.ci.join(' to ')+')'));}
 if(E.text_kind)gt('Which kind of text carries the gain?','Gain over registry plus sponsor identity. Names removed, or only common, middle or rare vocabulary.',Object.entries(E.text_kind.variants).map(([k,v])=>[k,f3(v.auroc),(v.gain_over_baseline>=0?'+':'')+v.gain_over_baseline.toFixed(4),v.ci.join(' to ')]),['Text variant','AUROC','Gain','95% interval']);
 if(E.text_amend)gt('Is it amendment history?','Removing version and amendment wording, or splitting title page from body.',Object.entries(E.text_amend.variants).map(([k,v])=>[k,f3(v.auroc),(v.gain_over_baseline>=0?'+':'')+v.gain_over_baseline.toFixed(4),v.ci.join(' to ')]),['Text variant','AUROC','Gain','95% interval']);
 if(E.topic_baseline){const t=E.topic_baseline;gt('Do the registry’s own topic words absorb it?','Registry title, condition and MeSH words added to the baseline.',Object.entries(t.auroc).map(([k,v])=>[k,f3(v)]),['Stack','AUROC']);
  box.append(h('div',{class:'small'},'Document text over registry, sponsor identity and registry text: '+(t.document_text_gain_over_registry_plus_sponsor_plus_registry_text.gain>=0?'+':'')+t.document_text_gain_over_registry_plus_sponsor_plus_registry_text.gain.toFixed(4)+' ('+t.document_text_gain_over_registry_plus_sponsor_plus_registry_text.ci.join(' to ')+')'));}}

async function simTab(box,E){
 const run=E.run;
 if(run&&run.simulator){const sm=run.simulator;evSec(box,'Recruitment simulator: tuned to published rates (scenario analysis)','A cheap stochastic core, tuned to Kasenda et al. 2014. Not validated against real trials; see the backtest below.');
  const A=sm.calibration.achieved,T=sm.calibration.anchors,nm={recruitment_stop_rate:'Stopped for poor recruitment',any_stop_rate:'Stopped for any reason',median_fraction_at_recruitment_stop:'Median share of target reached when stopped for recruitment',industry_over_investigator_recruitment_stop:'Industry rate over investigator rate',piloted_recruitment_stop_rate_max:'Piloted trials stopped for recruitment (upper bound)'};
  box.append(tableEl(['Published rate','Published','Simulator'],Object.keys(T).map(k=>[nm[k],f3(T[k]),f3(A[k])]),[1,2]));
  box.append(h('div',{class:'warn'},sm.scenario.label),tableEl(['Change (same simulated trials)','Stopped for recruitment','Relative change'],[['None (control)',pct(sm.scenario.control_recruitment_stop_rate),'']].concat(Object.entries(sm.scenario.levers).map(([k,v])=>[k,pct(v.recruitment_stop_rate),(v.relative_change>0?'+':'')+pct(v.relative_change,0)])),[1,2]));}
 if(E.backtest){const bt=E.backtest,b=bt.backtest_era_B,c=bt.calibration_era_A,eq=bt.extraction_quality_completed_trials['documents dated at or before the start'];
  evSec(box,'Backtest on real trials (gate G4): '+bt.gate_G4_verdict,'Tuned on trials starting up to 2015 with their real planned size, sites, sponsor type and criteria; asked to predict which 2016 to 2018 trials failed to recruit.');
  const lad=ladderChart(Object.entries(b.auroc).map(([k,v])=>({label:k,auroc:v,group:k.startsWith('registry factors +')?'model':k.startsWith('registry')?'registry':k.startsWith('simulator')?'simulator':'baseline'})));
  box.append(lad,exportBar(lad,'simulator-backtest',[['predictor','auroc'],...Object.entries(b.auroc)]));
  const cal=lineChart({xlab:'simulated stop probability (eighths of trials)',ylab:'observed rate',xmax:Math.max(...b.calibration_simulator.map(x=>x.pred))*1.1,ymax:0.4,points:true,series:[{name:'bins',color:'#b00020',pts:b.calibration_simulator.map(x=>[x.pred,x.obs]),r:5}]});
  box.append(h('div',{style:'display:flex;flex-wrap:wrap;gap:12px'},h('div',null,h('div',{class:'small'},'Simulator calibration on real 2016–2018 trials'),cal),h('div',{class:'small',style:'max-width:520px'},'Tuned on era A it matches the overall rate ('+pct(c.simulated.rate)+' simulated, '+pct(c.observed.rate)+' observed) but ranks trials wrongly. Planned sample size read from protocol text, on completed trials with a document dated before the start ('+fmt(eq.n)+'): correlation with registered enrolment '+eq.pearson_log10+', median actual over planned '+eq.median_actual_over_planned+'; '+pct(eq.share_within_25pct,0)+' within 25%, '+pct(eq.share_within_factor_2,0)+' within a factor of 2. Recruitment failures reached a median '+pct(bt.attainment_actual_over_planned.recruitment_failures[2],0)+' of the planned size (Kasenda: 41%).')));}}

async function chkTab(box,E){
 const run=E.run;
 if(run&&run.negative_controls){const nc=run.negative_controls;evSec(box,'Negative controls','If one fails there is leakage or a bug.');
  box.append(tableEl(['Control','Result','Expected','Verdict'],[['Outcomes shuffled (8 times)','mean AUROC '+f3(nc.shuffled_labels.dev_auroc_mean)+' (range '+f3(nc.shuffled_labels.dev_auroc_range[0])+' to '+f3(nc.shuffled_labels.dev_auroc_range[1])+'); '+nc.shuffled_labels.terms_flagged_fdr+' terms survived','about 0.5',h('span',{class:'chip neg'},'pass')],['12 random columns',nc.random_columns.fake_flagged_fdr+' of 12 flagged','0 or 1',h('span',{class:'chip '+(nc.random_columns.fake_flagged_fdr<=1?'neg':'pos')},nc.random_columns.fake_flagged_fdr<=1?'pass (edge)':'FAIL')],['Placebo outcome (last digit of the NCT number)','AUROC '+f3(nc.placebo_outcome.dev_auroc),'about 0.5',h('span',{class:'chip neg'},'pass')]]));}
 if(E.scaled_registry){const sc=E.scaled_registry;evSec(box,'Noise floors','The 95th percentile of 30 random-number families added to the same model. It sits at about zero, which makes “above the floor” easy to meet; the rule also needs positive gain in 8 of 10 windows.');
  box.append(tableEl(['Subset','Unique gain, 95th percentile of noise','Alone AUROC, 95th percentile of noise','Range of random unique gains'],Object.entries(sc.summary).map(([g,v])=>[g,v.noise_floor_unique_95th.toFixed(5),f3(v.noise_floor_alone_95th),v.random_families_mean_unique_range.join(' to ')])));}
 if(run&&run.recovery){const rc=run.recovery.by_label_noise;evSec(box,'Can it find effects we plant?',run.recovery.reading);
  box.append(tableEl(['Label noise','Right direction','Planted effects found','Null factors flagged','Factors sharing a hidden cause flagged','Interactions right','Interactions recalled'],Object.entries(rc).map(([q,v])=>[pct(+q,0),pct(v.sign_correct,0),pct(v.true_effects_found_fdr,0),pct(v.null_factors_flagged_fdr,0),pct(v.prime_mover_factors_flagged_fdr,0),pct(v.pair_precision,0),pct(v.pair_recall,0)]),[1,2,3,4,5,6]));}
 if(run&&run.whatif){const wi=run.whatif;evSec(box,'Model against a stratified look (level 1)',wi.reading);
  box.append(tableEl(['Protocol choice','Trials with it','Model: change if removed','Stratified observed change','Same direction'],wi.rows.map(r=>[r.lever,fmt(r.n_with),(r.model_implied_change_if_removed*100).toFixed(2)+' pts',(r.stratified_observed_change_if_removed*100).toFixed(2)+' pts',h('span',{class:'chip '+(r.same_direction?'neg':'pos')},r.same_direction?'yes':'no')]),[1,2,3]));}
 if(run&&run.heads){evSec(box,'Other ways to fail','One risk per super-label, same split, machine-made labels.');
  box.append(tableEl(['Way to fail','Failures to learn from','Failures to test on','AUROC','95% interval','AUPRC','Guessing level'],Object.entries(run.heads).map(([k,v])=>v.note?[k,fmt(v.train_positives),fmt(v.test_positives),'',v.note,'','']:[k,fmt(v.train_positives),fmt(v.test_positives),f3(v.auroc),v.auroc_ci.join(' to '),f3(v.auprc),f3(v.guessing_level)]),[1,2,3,5,6]));}}

async function synTab(box,E){
 const sy=E.synthetic;if(!sy){box.append(h('div',null,'No synthetic-protocol analysis yet.'));return;}
 evSec(box,'Twelve synthetic protocols (capability check only)');
 box.append(h('div',{class:'warn'},'Synthetic data written by the same model that analysed them. Four were designed to fail, four to be ordinary, four with risk engineered down. This shows whether the machinery reads the intended differences, not accuracy. Never mixed with real figures, never used in validation.'));
 const cat={weak:'chip pos',average:'chip oth',strong:'chip neg'},rows=sy.documents.slice().sort((a,b)=>b.stack_risk-a.stack_risk);
 box.append(tableEl(['Document','Designed as','Design','Registry-factor risk','Stack risk','Checklist items (of 14)','Needed per site per month','Simulator stop probability'],rows.map(d=>[d.id,h('span',{class:cat[d.category]},d.category),d.design,pct(d.registry_factor_risk,1),pct(d.stack_risk,1),d.briel_distinct_items,d.required_per_site_per_month,pct(d.simulator_stop_probability,0)]),[3,4,5,6,7]));
 const pw=sy.pairwise_share_ordered_as_designed;
 evSec(box,'Share of document pairs ordered as designed','1.0 = every pair right, 0.5 = chance.');
 box.append(tableEl(['Score','Weak above strong','Weak above average','Average above strong'],Object.entries(pw).map(([k,v])=>[k,v[0].toFixed(2),h('b',null,v[1].toFixed(2)),v[2].toFixed(2)]),[1,2,3]));
 if(sy.reading)box.append(h('div',{class:'small',style:'max-width:920px;margin-top:6px'},sy.reading));}

async function gateTab(box,E){
 evSec(box,'Validation gates','A claim made before its gate is passed is exploratory wherever it appears.');
 box.append(tableEl(['Gate','Claim it unlocks','Status','Note'],E.gates.map(g=>[g.gate,g.claim,h('span',{class:'chip '+(g.status==='passed'||g.status==='measured'?'neg':g.status==='pilot only'?'oth':'unl')},g.status),g.note])));
 evSec(box,'How the data were kept honest','The sealed vault (a random tenth of trials by salted hash, plus every 2019 and 2020 start) is excluded from every run on this page and has not been looked at. The frozen test split is excluded from every exploratory run. Time-aware families use only trials that started at least three years earlier. Synthetic protocols are never mixed with real figures.');
 evSec(box,'Result files this page reads');
 box.append(tableEl(['File','Size (KB)','Written'],E.files.map(f=>[f.name,fmt(f.kb),new Date(f.modified*1000).toLocaleString()]),[1]));}

{const _ov=overview;overview=async function(main){await _ov(main);try{await evidencePanel(main);}catch(e){}};}

async function plots(main){
 main.append(h('h2',null,'Plots'));
 const d=await api('/api/plots');
 main.append(h('div',{class:'small'},'Built-in plots, and any plug-in you add: drop a .py file into the plugins folder (see the example in the About page), then press Refresh. Plots compute on the GPU when they can and on the CPU otherwise.'));
 const dev=h('select',null,['auto','cuda','cpu'].map(x=>h('option',{value:x},'compute: '+x)));
 const list=h('div'),out=h('div',{style:'margin-top:8px'});
 main.append(h('div',{class:'row'},dev,h('button',{onclick:()=>{S.page='x';go();}},'Refresh list'),h('span',{class:'small m'},'plugins folder: '+d.plugins_dir)),list,out);
 d.plugin_errors.forEach(e=>main.append(h('div',{class:'warn bad'},'Plug-in not loaded: '+e)));
 d.plots.forEach(pl=>list.append(h('div',{class:'row',style:'border-bottom:1px solid var(--hair);padding:3px 0'},
  h('button',{onclick:async()=>{out.replaceChildren(h('div',{class:'small'},'Rendering '+pl.name+'…'));
    try{const r=await api('/api/plot?name='+encodeURIComponent(pl.name)+'&device='+dev.value);
     if(r.error){out.replaceChildren(h('div',{class:'warn bad'},r.error),h('pre',null,r.trace||''));return;}
     out.replaceChildren(h('div',{class:'small m'},pl.name+' · '+r.seconds+' s · '+r.device+' · saved '+r.saved),h('img',{src:'data:image/png;base64,'+r.png,style:'max-width:100%;border:1px solid var(--rule);margin-top:4px'}));
    }catch(e){out.replaceChildren(h('div',{class:'warn bad'},e.message));}}},'Draw'),
  h('b',null,pl.name),h('span',{class:'chip'},pl.builtin?'built in':'plug-in'),h('span',{class:'small'},pl.description))));}

async function run(main){
 main.append(h('h2',null,'Run pipeline steps on this computer'));
 main.append(h('div',{class:'small'},'Each step runs here, in the background, on your CPU and (where it helps) your GPU. “auto” uses the GPU when one is available. Steps that touch the network are marked and use the polite shared rate limits. When a step finishes, press Reload data to see the new numbers.'));
 const dev=h('select',null,['auto','cuda','cpu'].map(x=>h('option',{value:x},'device: '+x)));
 const box=h('div'),logs=h('div');main.append(h('div',{class:'row'},dev,h('span',{id:'rnstat',class:'small'})),box,h('h2',null,'Jobs'),logs);
 async function draw(){const j=await api('/api/jobs');const st=await api('/api/status');
  box.replaceChildren(...Object.entries(j.stages).map(([k,v])=>h('div',{class:'row',style:'border-bottom:1px solid var(--hair);padding:3px 0'},
    h('button',{disabled:j.running?'disabled':null,onclick:async()=>{await startStage(k,dev.value);draw();}},v.label),
    v.network?h('span',{class:'chip'},'network'):null,h('span',{class:'small'},v.about))));
  document.getElementById('rnstat').replaceChildren(j.running?'a job is running…':'idle',st.stale?h('button',{style:'margin-left:10px',onclick:async()=>{await api('/api/reload',{},'POST');location.reload();}},'Reload data (new results are ready)'):'');
  logs.replaceChildren(...(j.items.length?j.items.slice().reverse():[{stage:'',state:'',log:['no jobs yet']}]).map(x=>h('div',{style:'margin-bottom:8px'},
    h('div',null,h('b',{class:'m'},x.stage?('#'+x.id+' '+x.stage):''),' ',h('span',{class:'chip '+(x.state==='done'?'neg':x.state==='failed'?'pos':'')},x.state),h('span',{class:'small'},x.seconds!=null?' '+x.seconds+' s · device '+x.device:(x.device?' device '+x.device:''))),
    h('pre',null,x.log.join('\n')))));
  if(!j.running&&S.timer){clearInterval(S.timer);S.timer=null;}}
 await draw();S.timer=setInterval(()=>{if(S.page==='run')draw();},1500);}

async function start(main){
 main.append(h('h2',null,'Welcome to AutoRAN'));
 main.append(h('div',null,'There is no trial data on this computer yet. AutoRAN does not ship with any: it downloads the registry data itself, then labels it, scores it and shows you the results. Everything runs locally.'));
 main.append(h('h2',null,'What the first run does'));
 ['Downloads every trial in scope from ClinicalTrials.gov (about 267 requests, 214 MB, about 11 minutes, always inside half of each limit). It can be stopped and resumed. No account or API key is needed.',
  'Downloads the Open Targets curated stop reasons (about 38 requests) that the labeller learns from. A Hugging Face token is optional and only raises the rate limit.',
  'Normalises, labels, categorises, scores and measures: a few minutes on a CPU, less with a GPU. The app then reloads and fills the other pages.'].forEach(x=>main.append(h('div',{class:'small',style:'margin:2px 0'},'· '+x)));
 main.append(h('div',{class:'warn'},'Requirements: an internet connection, about 2 GB of free disk space for the data, and permission to use the data under the providers’ terms (see About). Optional: set a contact email under Settings first, so the registry can reach you if your requests cause trouble.'));
 const go2=h('button',{class:'primary',onclick:async()=>{await startStage('run-all','auto');}},'Fetch everything and build (first run)');
 main.append(h('div',{class:'row',style:'margin-top:10px'},go2,h('a',{href:'#settings'},'Settings first'),h('a',{href:'#run'},'Pick individual steps')));
 main.append(h('div',{class:'small',style:'margin-top:8px'},'To try the pipeline quickly on a small sample instead, use the command line: autoran fetch --max-pages 2, then autoran labeller-data, autoran normalise --partial, label, categorize, score, metrics.'));}

// ------------------------------------------------------------------ Graphics card section of Settings
async function gpuSection(main){
 main.append(h('h2',null,'Graphics card (GPU)'));
 const box=h('div',{style:'border:1px solid var(--rule);padding:8px 10px;margin-bottom:10px'});main.append(box);
 let timer=null,confirmPlan=null;
 const dotc=s=>({ready:'green',found:'green',no_gpu:'green',incompatible:'yellow',not_found:'yellow'}[s]||'yellow');
 async function draw(){
  let st,info;
  try{st=await api('/api/gpu/check');info=await api('/api/gpu');}catch(e){box.replaceChildren(h('div',{class:'warn bad'},e.message));return;}
  const c=st.cache,v=c&&c.verdict,ins=st.install,busy=st.scan.state==='running'||ins.state==='running';
  box.replaceChildren();
  let state,text;
  if(info&&info.cuda_available){state='ready';text='Ready. AutoRAN is using PyTorch '+info.torch+' on your '+info.device+'.';}
  else if(st.scan.state==='running'){state='checking';text='Looking at your computer: the graphics card, the driver, and every Python for a usable PyTorch…';}
  else if(v){state=v.state;text=v.text;}
  else{state='unknown';text='Not checked yet.';}
  box.append(h('div',{style:'display:flex;gap:8px;align-items:center;font-weight:700'},fdot(state==='checking'||state==='unknown'?'yellow':dotc(state),12),text));
  if(c&&c.smi&&c.smi.gpu)box.append(h('div',{class:'small',style:'margin:4px 0 0 20px'},'Card: '+c.smi.gpu+', driver '+c.smi.driver+', '+Math.round(c.smi.memory_mb/1024)+' GB'+(c.smi.max_cuda?', supports CUDA up to '+c.smi.max_cuda:'')+'. CUDA itself comes inside PyTorch, so only the driver is needed.'));
  else if(c&&c.smi)box.append(h('div',{class:'small',style:'margin:4px 0 0 20px'},c.smi.why||''));
  if(c&&c.pythons&&c.pythons.length){const t=h('table',{style:'margin:8px 0;max-width:860px'},h('tr',null,['Python','PyTorch','Sees the GPU','Usable by this AutoRAN'].map(x=>h('th',null,x))));
   c.pythons.forEach(p=>{const same=p.tag===st.bundled_tag,use=p.torch&&same&&p.cuda_ok;t.append(h('tr',null,h('td',{title:p.exe},p.python+' ('+p.exe.split('\\').slice(-3,-1).join('\\')+')'),h('td',null,p.torch||'none'),h('td',null,p.torch?(p.cuda_ok?'yes':'no'):''),h('td',null,use?'yes':(p.torch?(same?'no: cannot see the GPU':'no: needs Python '+st.bundled_tag.slice(2,3)+'.'+st.bundled_tag.slice(3)):''))));});
   box.append(t);box.append(h('div',{class:'small'},'This AutoRAN runs on Python '+st.bundled_tag.slice(2,3)+'.'+st.bundled_tag.slice(3)+', so it can only borrow a PyTorch built for that version.'));}
  const row=h('div',{class:'row'});
  row.append(h('button',{onclick:async()=>{await api('/api/gpu/scan',{});schedule();draw();}},busy?'Checking…':'Check this computer'));
  const canInstall=v&&v.can_install&&(v.state==='not_found'||v.state==='incompatible');
  if(canInstall&&ins.state!=='running')row.append(h('button',{class:'primary',onclick:async()=>{const r=await api('/api/gpu/install',{dry_run:true});confirmPlan=r.plan;draw();}},'Install PyTorch for AutoRAN (about '+st.expected_gb+' GB)'));
  if(v&&!v.can_install&&(v.state==='not_found'||v.state==='incompatible')&&c&&c.smi&&c.smi.gpu)row.append(h('span',{class:'small'},'No Python with pip was found. Install Python 3.11 or newer from python.org (tick Add to PATH), then check again.'));
  box.append(row);
  if(confirmPlan){const p=confirmPlan;box.append(h('div',{style:'border:2px solid var(--acc);background:#f2f6ff;padding:8px 10px;margin:6px 0'},h('b',null,p.ok?'Install PyTorch for AutoRAN?':'Cannot install yet'),
   h('div',{style:'margin:4px 0'},p.ok?'Downloads about '+p.expected_gb+' GB from download.pytorch.org (the '+p.commands[0].index+' build for your driver) into '+p.target+', using Python '+p.python_version+' to run pip. It takes several minutes. Free disk space: '+p.free_gb+' GB. Nothing else on your computer is changed.':p.why),
   h('div',{class:'row'},p.ok?h('button',{onclick:async()=>{confirmPlan=null;await api('/api/gpu/install',{dry_run:false});schedule();draw();}},'Install'):null,h('button',{onclick:()=>{confirmPlan=null;draw();}},p.ok?'Not now':'Close'))));}
  if(ins.state!=='idle'){const col={running:'yellow',done:'green',failed:'red'}[ins.state];
   box.append(h('div',{style:'margin-top:8px'},fdot(col,10),' '+ins.message));
   box.append(h('div',{style:'height:8px;background:var(--soft);border:1px solid var(--hair);margin:4px 0;max-width:600px'},h('div',{style:'height:100%;width:'+Math.round(100*ins.progress)+'%;background:var(--acc)'})));
   if(ins.log&&ins.log.length)box.append(h('pre',{style:'max-height:12em'},ins.log.slice(-12).join('\n')));}
  if(!busy&&timer){clearInterval(timer);timer=null;try{S.gpu=await api('/api/gpu');nav();}catch(e){}}
 }
 function schedule(){if(!timer)timer=setInterval(()=>{if(S.page!=='settings'){clearInterval(timer);timer=null;return;}draw();},1500);}
 await draw();
 if(box.textContent.indexOf('Looking at your computer')>=0||box.textContent.indexOf('Installing PyTorch')>=0)schedule();
}

// ------------------------------------------------------------------ Review, second mode: one case at a time, yes / no / other, saved to a CSV
async function cases(main){
 const box=h('div');main.append(box);
 const pretty=c=>c.replace(/_/g,' ');
 const SUPERS={"Participants": ["Insufficient_Enrollment"], "Resources": ["Business_Administrative", "Logistics_Resources", "Study_Staff_Moved"], "Science": ["Study_Design", "Another_Study", "Insufficient_Data"], "Results": ["Negative", "Endpoint_Met", "Success", "Interim_Analysis"], "Harm and compliance": ["Safety_Sideeffects", "Regulatory", "Ethical_Reason"], "Outside events": ["Covid19"], "Uninformative": ["Invalid_Reason", "No_Context"]};
 const chip=(c,kind)=>h('span',{style:'display:inline-block;margin:2px 6px 2px 0;padding:2px 8px;border:2px solid '+(kind==='add'?'var(--good)':kind==='del'?'var(--bad)':'var(--hair)')+';'+(kind==='del'?'text-decoration:line-through;':'')+(kind==='add'?'font-weight:700;':'')},(kind==='add'?'+ ':kind==='del'?'− ':'')+pretty(c));
 let busy=false;
 async function act(path,body){if(busy)return;busy=true;try{const st=await api(path,body||{});draw(st);}catch(e){box.prepend(h('div',{class:'warn bad'},e.message));}finally{busy=false;}}
 function draw(st){
  box.replaceChildren();window.__gd=null;
  if(!st.sample){
   box.append(h('div',{style:'max-width:760px'},h('p',null,'Give a verdict on cases where AutoRAN changed its mind, plus some it is sure about. Each verdict is saved to a CSV you can open in a spreadsheet. Nothing about the labels changes.'),
    h('p',null,'A sample is 100 cases: the 70 the labeller is least sure about and 30 it is fairly sure about, mixed together. The card never says which is which.'),
    h('div',{class:'row'},h('button',{class:'primary',onclick:()=>{box.append(h('div',{class:'small'},'Drawing the sample… this reads every stopped trial and can take half a minute.'));act('/api/gold/draw',{n_concerning:70,n_control:30});}},'Draw 100 cases'))));
   return;}
  const done=st.done,n=st.n;
  box.append(h('div',{class:'row',style:'align-items:center;gap:14px'},h('b',null,done+' of '+n+' done'),
   h('div',{style:'flex:1;max-width:360px;height:8px;background:var(--soft);border:1px solid var(--hair)'},h('div',{style:'height:100%;width:'+Math.round(100*done/Math.max(1,n))+'%;background:var(--acc)'})),
   h('span',{class:'small'},'yes '+st.counts.yes+' · no '+st.counts.no+' · other '+st.counts.other),
   h('button',{disabled:done?null:'disabled',onclick:()=>act('/api/gold/undo')},'Undo last (Z)')));
  box.append(h('div',{class:'small',style:'margin:2px 0 10px'},'Saved to ',h('span',{class:'mono'},st.file)));
  const c=st.next;
  if(!c){
   const sm=st.summary||{};
   box.append(h('h3',null,'All done. Thank you.'));
   const t=h('table',{style:'max-width:620px'},h('tr',null,['Group','Cases','Yes','No','Other','Yes rate'].map(x=>h('th',null,x))));
   [['concern','The labeller was unsure'],['control','The labeller was sure']].forEach(([k,l])=>{const s=sm[k];if(s)t.append(h('tr',null,h('td',null,l),h('td',{class:'n'},s.n),h('td',{class:'n'},s.yes),h('td',{class:'n'},s.no),h('td',{class:'n'},s.other),h('td',{class:'n'},s.yes_rate==null?'':Math.round(100*s.yes_rate)+'%')));});
   const bl=sm.blind||{},op=sm.open||{},ow=sm.own_answer_matches_machine||{};
   if(bl.n||op.n)box.append(h('div',{class:'small',style:'margin:6px 0'},'Anchoring check: yes rate when you wrote your own answer first (blind) '+(bl.yes_rate==null?'-':Math.round(100*bl.yes_rate)+'%')+' of '+(bl.n||0)+', when you saw the machine’s first (open) '+(op.yes_rate==null?'-':Math.round(100*op.yes_rate)+'%')+' of '+(op.n||0)+'. Your own blind answer matched the machine’s exactly in '+(ow.rate==null?'-':Math.round(100*ow.rate)+'%')+' of '+(ow.n||0)+' cases. A much higher open yes rate suggests the machine’s answer is steering you.'));
   box.append(t,h('div',{class:'small'},'If the sure group is not nearly all yes, the labeller is overconfident. The CSV has every verdict, the before and after calls and the rules that changed.'),
    h('div',{class:'row'},h('button',{onclick:()=>{if(confirm('Draw a new sample of 100? Cases you already judged are skipped.'))act('/api/gold/draw',{n_concerning:70,n_control:30,seed:Date.now()%100000});}},'Draw another 100')));
   return;}
  if(c.blind&&!c.after){
   const own=new Set();
   const groups=h('div',null,...Object.entries(SUPERS).map(([sup,cs])=>h('div',{style:'margin:4px 0'},h('span',{class:'small',style:'display:inline-block;min-width:150px'},sup),...cs.map(k=>h('label',{style:'margin-right:12px;white-space:nowrap'},h('input',{type:'checkbox',onchange:e=>{e.target.checked?own.add(k):own.delete(k);}}),' '+pretty(k))))));
   box.append(h('div',{style:'border:2px solid var(--acc);padding:12px 14px;max-width:820px'},
    h('div',{class:'small'},'Blind case: the machine’s answer is hidden. Write your own first ('+c.nct_id+', '+c.status.toLowerCase()+')'),
    h('div',{style:'font-size:17px;line-height:1.45;margin:6px 0 12px'},c.why_stopped),
    h('div',{class:'small'},'Tick every reason the text gives. Tick nothing if it gives no usable reason.'),groups,
    h('div',{class:'row',style:'margin-top:10px'},h('button',{class:'primary',onclick:async()=>{if(busy)return;busy=true;try{await api('/api/gold/reveal',{item:c.item,own:[...own]});draw(await api('/api/gold'));}catch(e){box.prepend(h('div',{class:'warn bad'},e.message));}finally{busy=false;}}},'Lock my answer and show the machine’s'))));
   window.__gd=null;return;}
  const note=h('input',{type:'text',placeholder:'Optional note (why?)',style:'width:100%;max-width:640px;margin:6px 0'});
  const verdict=v=>{act('/api/gold/verdict',{item:c.item,verdict:v,note:note.value});};
  box.append(h('div',{style:'border:2px solid var(--rule);padding:12px 14px;max-width:820px'},
   h('div',{class:'small'},'Why the trial was stopped, as written in the registry ('+c.nct_id+', '+c.status.toLowerCase()+')'),
   h('div',{style:'font-size:17px;line-height:1.45;margin:6px 0 12px'},c.why_stopped),
   c.blind?h('div',{class:'small',style:'margin-bottom:6px'},'Your own answer, locked before you saw the machine’s: ',h('b',null,(c.own&&c.own.length)?c.own.map(pretty).join(', '):'no class')):'',
   h('div',{class:'small'},'Before (last run)'),h('div',null,c.before.length?c.before.map(x=>chip(x,c.removed.includes(x)?'del':'')):h('span',{class:'small'},'no class')),
   h('div',{class:'small',style:'margin-top:6px'},'After (now)'),h('div',null,c.after.length?c.after.map(x=>chip(x,c.added.includes(x)?'add':'')):h('span',{class:'small'},'no class')),
   (c.rules_added.length||c.rules_removed.length)?h('div',{class:'small mono',style:'margin-top:8px'},'Rules changed: ',c.rules_added.map(r=>'+'+r).concat(c.rules_removed.map(r=>'−'+r)).join('  ')):h('div',{class:'small',style:'margin-top:8px'},(c.added.length||c.removed.length)?'No rule changed. The difference comes from the statistical model (decided by: '+(c.source_after==='nb'?'the model':c.source_after)+'; before: '+(c.source_before==='nb'?'the model':c.source_before)+').':'No rule changed; the call is the same.'),
   (c.votes&&Object.keys(c.votes).length)?h('div',{class:'small',style:'margin-top:6px'},'Checks that agreed (of 6): '+Object.keys(c.votes).map(k=>pretty(k)+' '+(c.agree[k]||0)+' ('+Object.entries(c.votes[k]).filter(([d,v])=>v>=0.5).map(([d])=>d.replace('_',' ')).join(', ')+')').join(' · ')):'',
   (c.story&&c.story.edges&&c.story.edges.length)?h('div',{class:'small',style:'margin-top:4px'},'Cause and effect read from the text: '+c.story.edges.map(e=>pretty(e.cause)+' → '+pretty(e.effect)+' ('+e.via+')').join('; ')):'',
   (c.story&&c.story.not_about&&c.story.not_about.length)?h('div',{class:'small',style:'margin-top:4px'},'Said not to be the reason: '+c.story.not_about.map(pretty).join(', ')):'',
   (c.tree&&(c.tree.sublabels||[]).length)?h('div',{class:'small',style:'margin-top:4px'},'Finer labels: '+c.tree.sublabels.map(pretty).join(', ')+(c.tree.land_mine?' · flag: '+pretty(c.tree.land_mine):'')+(c.tree.withdrawn_kind?' · withdrawn: '+pretty(c.tree.withdrawn_kind):'')):'',
   note));
  box.append(h('div',{class:'row',style:'margin-top:10px;gap:10px'},
   h('button',{class:'primary',style:'min-width:120px;padding:10px 18px;font-size:15px',onclick:()=>verdict('yes')},'Yes (Y)'),
   h('button',{style:'min-width:120px;padding:10px 18px;font-size:15px',onclick:()=>verdict('no')},'No (N)'),
   h('button',{style:'min-width:120px;padding:10px 18px;font-size:15px',onclick:()=>verdict('other')},'Other (O)')));
  box.append(h('div',{class:'small',style:'margin-top:8px;max-width:760px'},h('b',null,'Yes'),': the After classification is right. ',h('b',null,'No'),': it is wrong. ',h('b',null,'Other'),': not wrong, but classified poorly (neither a good change nor a bad one). Keys: Y, N, O, and Z to undo.'));
  window.__gd={verdict,undo:()=>act('/api/gold/undo')};
 }
 draw(await api('/api/gold'));
}


async function settings(main){
 const a=await api('/api/settings');
 main.append(h('h2',null,'Settings'));
 await gpuSection(main);
 main.append(h('h2',null,'Your settings'));
 main.append(h('div',{class:'small'},'Saved for you only, in '+a.settings_file+' (outside the project, never committed). Nothing here is needed to run AutoRAN; each field is optional. Tokens and keys are stored encrypted for this Windows user and are not shown again, only whether one is set.'));
 const rows=[
  ['workspace','Workspace folder','Where data/ and state/ are kept. Empty = the AutoRAN folder ('+a.program_folder+'). Needs a restart. Currently using: '+a.active_workspace,'text'],
  ['history_dir','RAN history folder','Optional. RAN’s browser-collected trial histories (adds a few more clean inputs). Used at the next normalise.','text'],
  ['gpu_site','GPU pack folder (advanced)','Normally not needed: AutoRAN finds a usable PyTorch itself, or installs one (see the Graphics card section above). Only to point at a PyTorch folder yourself: a folder that contains torch/. Needs a restart.','text'],
  ['contact_email','Contact email','Optional. Added to the User-Agent of requests so a registry operator can reach you: '+a.user_agent,'text'],
  ['hf_token','Hugging Face token','Optional. Raises the rate limit of the Open Targets download (datasets-server.huggingface.co). ClinicalTrials.gov needs no key.','password'],
  ['ncbi_api_key','NCBI API key','Optional. AutoRAN’s own fetches do not use NCBI; the key is passed on to RAN’s NCBI client if you use RAN features.','password']];
 const inputs={},msg=h('div',{class:'small'});
 const t=h('table',null);
 rows.forEach(([k,l,d,type])=>{const secret=type==='password';
  const inp=h('input',{type:type,style:'width:100%;min-width:320px',placeholder:secret?(a[k].set?'set (leave empty to keep, type to replace)':'not set'):'',autocomplete:'off'});
  if(!secret)inp.value=a[k]||'';inputs[k]=[inp,secret];
  const clear=secret&&a[k].set?h('button',{onclick:async()=>{try{await api('/api/settings',{[k]:''});location.reload();}catch(e){msg.textContent=e.message;}}},'Clear'):null;
  t.append(h('tr',null,h('td',null,h('b',null,l)),h('td',null,inp,clear),h('td',{class:'small'},d)));});
 main.append(t);
 main.append(h('button',{class:'primary',onclick:async()=>{
   const body={};for(const k in inputs){const [inp,secret]=inputs[k];if(secret){if(inp.value.trim())body[k]=inp.value.trim();}else if(inp.value.trim()!==(a[k]||''))body[k]=inp.value.trim();}
   if(!Object.keys(body).length){msg.textContent='nothing changed';return;}
   try{await api('/api/settings',body);msg.textContent='Saved. Folder changes apply after you restart AutoRAN.';setTimeout(()=>location.reload(),900);}catch(e){msg.textContent='Not saved: '+e.message;}}},'Save'),' ',msg);
 main.append(h('h2',null,'Before you fetch'));
 ['Fetching downloads about 214 MB from clinicaltrials.gov at a pace well inside its limit; it takes about 11 minutes and can be stopped and resumed. No account or key is needed.',
  'The Open Targets stop-reason download comes from the Hugging Face dataset server; a token is optional.',
  'You are responsible for using registry data under the providers’ own terms (see About).'].forEach(x=>main.append(h('div',{class:'small',style:'margin:2px 0'},'· '+x)));}

async function about(main){
 const a=await api('/api/about'),m=S.m;main.append(h('h2',null,'About AutoRAN '+a.version));
 main.append(h('div',null,'AutoRAN labels clinical trials automatically for one question: could a protocol review have picked out, in advance, the trials that later failed to recruit? Its output is the silver set: large, machine-made, weakly labelled. Gold labels stay small and human-confirmed (RAN).'));
 main.append(h('h2',null,'Sources and grades (floor '+a.grade_floor+', enforced at export)'));
 const t=h('table',null,h('tr',null,['source','licence','grade','terms'].map(x=>h('th',null,x))));
 Object.values(a.sources.sources).forEach(s=>t.append(h('tr',null,h('td',null,s.label),h('td',null,s.licence),h('td',null,s.grade),h('td',{class:'small'},s.terms))));
 main.append(t,h('div',{class:'small'},'Refused (below the floor or out of scope): '+a.sources.refused.join('; ')));
 main.append(h('h2',null,'What AutoRAN cannot tell you'));
 ['Whether an amendment was avoidable or substantive: that is RAN plus human labellers.',
  'Under-enrolment in trials that completed: once the actual enrolment is posted, the planned figure is lost without version history. They are labelled “completed”.',
  'Anything about efficacy or safety.',
  'Causation. A scorer that predicts recruitment failure is consistent with spotting real protocol problems, but site, sponsor and funding effects also predict it. The baselines show how much of the signal is “easy”; a protocol-review engine has to beat them on clean inputs to claim more.',
  'Hindsight: current records may include changes made after the trial started. “Clean” inputs are first submissions (never updated after posting, or RAN browser-collected first versions). They are mostly small trials, so a clean-versus-all difference mixes contamination with a different kind of trial.',
  'The no-history route: ClinicalTrials.gov refuses scripted history access and AutoRAN does not work around it. Scaling clean inputs needs a supported channel; that decision is parked.'].forEach(x=>main.append(h('div',{class:'warn'},x)));
 main.append(h('h2',null,'How the review tools work'));
 ['Review screens treat every card as correct unless flagged, so a screen of 24 takes about a minute. That is faster, and more prone to inattention, than line-by-line review.',
  'Canary cards (about 1 in 12) are real curated stop reasons shown with a deliberately wrong class, mixed in without a marker. The share you flag is shown as “reviewer attention”. They never enter any precision.',
  'Review by rule samples the trials a rule matched, so one verdict screen speaks for thousands of trials.',
  'Precision is shown with a 95% Wilson interval and a “enough / keep going” signal at ±3 points. 200 checks give about ±7 points; 1,000 give about ±3.'].forEach(x=>main.append(h('div',{class:'small',style:'margin:2px 0'},'· '+x)));
 main.append(h('h2',null,'Add your own plot'));
 main.append(h('pre',null,"# plugins/my_plot.py   (next to the app; press Refresh on the Plots page)\nfrom autoran.plots import plot\n\n@plot('Failure rate by sponsor', 'Share that failed to recruit, by sponsor class')\ndef sponsor(ctx):\n    import matplotlib.pyplot as plt\n    df = ctx.task()                      # completed + failed trials, 0/1 column `fail`\n    fig, ax = plt.subplots(figsize=(7, 4))\n    df.groupby('sponsor_class')['fail'].mean().sort_values().plot.barh(ax=ax)\n    return fig\n\n# ctx.frame()  every trial, label, category and score (pandas)   ctx.metrics  the metrics file\n# ctx.device   a torch device or None                              ctx.torch, ctx.np  PyTorch and numpy"));
 main.append(h('h2',null,'Attribution'));
 main.append(h('div',{class:'small'},'Registry data: ClinicalTrials.gov (U.S. National Library of Medicine), processed '+((m.pipeline.data_timestamp)||'?')+'. Stored as dated snapshots; this is not current data. Modifications: limited field set, contact fields not requested, text normalised, labels and categories added by AutoRAN. Some registry text may be subject to third-party copyright. Curated stop reasons: Open Targets, clinical_trial_reason_to_stop, Apache License 2.0.'));}

document.addEventListener('keydown',e=>{
 if(['INPUT','TEXTAREA','SELECT'].includes((e.target.tagName||'')))return;
 if(e.key==='Escape'){closeDrawer();return;}
 if(S.page==='review'&&window.__gd){const k=e.key.toLowerCase();if(k==='y'){window.__gd.verdict('yes');e.preventDefault();}else if(k==='n'){window.__gd.verdict('no');e.preventDefault();}else if(k==='o'){window.__gd.verdict('other');e.preventDefault();}else if(k==='z'){window.__gd.undo();e.preventDefault();}return;}
 if(S.page==='review'&&window.__rv&&!$('drawer').classList.contains('open')){const r=window.__rv,k=e.key.toLowerCase();
  if(k==='x'){r.flag('disagree');e.preventDefault();}else if(k==='u'){r.flag('unsure');e.preventDefault();}else if(k==='j'||e.key==='ArrowDown'||e.key==='ArrowRight'){r.move(1);e.preventDefault();}
  else if(k==='k'||e.key==='ArrowUp'||e.key==='ArrowLeft'){r.move(-1);e.preventDefault();}else if(k==='o'){r.open();}else if(e.key==='Enter'){r.submit();e.preventDefault();}
  else if(/^[1-9]$/.test(e.key)){r.pick(+e.key-1);}}});

// ------------------------------------------------------------------ Fetch panel (always visible by default; collapses to a strip)
const FP={layout:lget('fp.layout','a'),hidden:lget('fp.hidden','0')==='1',data:null,alerted:{},t0:Date.now()/1000,confirm:null,toast:null,sched:{},lastStage:null,idleSince:null,pinned:false,err:null};
function lget(k,d){try{const v=localStorage.getItem(k);return v==null?d:v;}catch(e){return d;}}
function lput(k,v){try{localStorage.setItem(k,v);}catch(e){}}
const FCOL={green:'#2e8b3d',yellow:'#e0a100',red:'#c0192f'};
const NET_STAGES=['fetch-full','fetch-delta','labeller-data','run-all'];
function fdot(c,s){return h('span',{style:`display:inline-block;width:${s||10}px;height:${s||10}px;border-radius:50%;background:${FCOL[c]};vertical-align:middle`});}
function fpct(a,b){return b>0?Math.max(0,Math.min(100,Math.round(100*a/b))):0;}
function fmtS(s){return Math.floor(s/60)+':'+('0'+(s%60)).slice(-2);}
function fpAlerts(evs){
 let fresh=false;
 (evs||[]).slice().reverse().forEach(e=>{if(e.ts<FP.t0||FP.alerted['id'+e.ts+e.host])return;FP.alerted['id'+e.ts+e.host]=1;
  if(e.level!=='warn'&&e.level!=='error')return;
  FP.toast=e;FP.hidden=false;fresh=true;
  });
 return fresh;}
function fpQuota(x){const w=fpct(x.used,x.max),lp=fpct(x.line,x.max);return {w,lp};}
function fpProg(x){const p=x.progress;if(!p)return '';const q=fpct(p.done,p.total);return `<div style="display:flex;align-items:center;gap:8px;font-size:11.5px;color:var(--dim);margin-top:3px"><div style="flex:1;height:6px;background:var(--soft);border:1px solid var(--hair)"><div style="width:${q}%;height:100%;background:var(--acc)"></div></div><span>${p.done.toLocaleString()} of ${p.total.toLocaleString()} ${p.label}</span></div>`;}
function fpStatusText(x){if(x.cooldown_left)return 'Stopped '+fmtS(x.cooldown_left);if(x.hold_left>x.pause_left)return 'Waiting '+fmtS(x.hold_left)+' for the window to reset';if(x.pause_left)return 'Paused '+fmtS(x.pause_left);if(x.throttle<1)return 'Running at '+Math.round(x.throttle*100)+'% of normal';if(x.progress&&x.progress.done<x.progress.total)return 'Fetching';if(x.used>0)return 'Idle, '+x.used+' recent';return 'Idle';}
function fpBarsA(hs){return hs.map(x=>{const q=fpQuota(x),c=FCOL[x.colour];
 return `<div style="margin:0 0 12px"><div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px"><b>${x.label}</b><span class="small">${fdot(x.colour,9).outerHTML} ${fpStatusText(x)}</span></div>
 <div style="position:relative;height:16px;background:var(--soft);border:1px solid var(--rule)"><div style="position:absolute;left:0;top:0;bottom:0;width:${q.w}%;background:${c}"></div><div style="position:absolute;left:${q.lp}%;top:-3px;bottom:-3px;border-left:2px dashed var(--fg)"></div></div>
 <div style="position:relative;height:15px;font-size:11px;color:var(--dim)"><span style="position:absolute;left:${q.lp}%;transform:translateX(-50%)">auto-stop ${x.line}</span><span style="position:absolute;right:0">limit ${x.max}${x.verified?'':' (assumed)'}</span><span>${x.used} used, ${Math.round(x.window_s/60)>=1?'per '+(x.window_s>=120?Math.round(x.window_s/60)+' min':'minute'):'per second'}</span></div>${fpProg(x)}</div>`;}).join('');}
function fpBarsB(hs){return `<div style="display:grid;grid-template-columns:repeat(${Math.max(1,hs.length)},1fr);gap:12px">`+hs.map(x=>{const q=fpQuota(x),c=FCOL[x.colour];
 return `<div style="text-align:center"><b>${x.label}</b><div style="position:relative;height:120px;width:54px;margin:6px auto;background:var(--soft);border:1px solid var(--rule)"><div style="position:absolute;left:0;right:0;bottom:0;height:${q.w}%;background:${c}"></div><div style="position:absolute;left:-3px;right:-3px;bottom:${q.lp}%;border-top:2px dashed var(--fg)"></div></div><div class="small">limit ${x.max}, auto-stop ${x.line}</div><div>${fdot(x.colour,9).outerHTML} ${fpStatusText(x)}</div>${fpProg(x)}</div>`;}).join('')+'</div>';}
function fpArc(a0,a1){const p=a=>[60+47*Math.cos(Math.PI*(1-a)),60-47*Math.sin(Math.PI*(1-a))],s=p(a0),e=p(a1);return `M${s[0].toFixed(1)} ${s[1].toFixed(1)} A47 47 0 0 1 ${e[0].toFixed(1)} ${e[1].toFixed(1)}`;}
function fpBarsC(hs){return `<div style="display:grid;grid-template-columns:repeat(${Math.max(1,hs.length)},1fr);gap:12px">`+hs.map(x=>{const f=Math.min(1,x.used/x.max),lf=x.line/x.max,t=(a,r)=>[(60+r*Math.cos(Math.PI*(1-a))).toFixed(1),(60-r*Math.sin(Math.PI*(1-a))).toFixed(1)],t1=t(lf,38),t2=t(lf,56),c=FCOL[x.colour];
 return `<div style="text-align:center"><svg viewBox="0 0 120 72" width="100%" style="max-width:220px" role="img" aria-label="${x.label} quota"><path d="${fpArc(0,1)}" fill="none" stroke="#e6e6e6" stroke-width="12"/><path d="${fpArc(0,Math.max(f,0.001))}" fill="none" stroke="${c}" stroke-width="12"/><line x1="${t1[0]}" y1="${t1[1]}" x2="${t2[0]}" y2="${t2[1]}" stroke="#111" stroke-width="2"/><text x="60" y="56" text-anchor="middle" style="font-size:15px;font-weight:700">${x.used}</text><text x="60" y="68" text-anchor="middle" style="font-size:7px">of ${x.line} allowed</text></svg><b>${x.label}</b><div class="small">limit ${x.max}${x.verified?'':' (assumed)'}</div><div>${fdot(x.colour,9).outerHTML} ${fpStatusText(x)}</div>${fpProg(x)}</div>`;}).join('')+'</div>';}
async function fpRetry(host,force){try{const r=await api('/api/fetch/retry',{host:host,force:!!force});if(!r.ok&&!force){if(confirm('This source is in a cool-down after repeated errors. Retrying early can extend it. Retry anyway?'))return fpRetry(host,true);return;}
  if(FP.lastStage&&!(FP.data&&FP.data.jobs_running)){await api('/api/run',{stage:FP.lastStage,device:'auto'});}fpPoll();}catch(e){FP.err=e.message;fpRender();}}
function fpSchedule(host,mins){if(!mins)return;const at=Date.now()+mins*60000;FP.sched[host]={at:at,stage:FP.lastStage||'run-all'};fpRender();}
function fpTick(){const now=Date.now();Object.keys(FP.sched).forEach(k=>{const s=FP.sched[k];if(s&&now>=s.at){delete FP.sched[k];if(!(FP.data&&FP.data.jobs_running))startStage(s.stage,'auto',true);}});}
async function startStage(stage,device,skipConfirm){
 if(!skipConfirm&&NET_STAGES.includes(stage)){try{const est=await api('/api/fetch/estimate',{stage:stage});if(est.items&&est.items.length){FP.confirm={stage:stage,device:device||'auto',est:est};FP.hidden=false;fpRender();window.scrollTo(0,0);return;}}catch(e){}}
 try{FP.lastStage=stage;FP.confirm=null;await api('/api/run',{stage:stage,device:device||'auto'});FP.hidden=false;FP.idleSince=null;fpPoll();}catch(e){alert(e.message);}}
function fpRender(){
 const el=$('fp');if(!el)return;const d=FP.data;el.replaceChildren();
 if(!d){return;}
 const hl=d.headline,hs=d.hosts.filter(x=>x.used>0||x.progress||x.colour!=='green'||x.host==='clinicaltrials.gov'||x.host==='datasets-server.huggingface.co');
 const worst=d.hosts.some(x=>x.colour==='red')?'red':d.hosts.some(x=>x.colour==='yellow')?'yellow':'green';
 const box=h('div',{class:'fpbox'});
 const head=h('div',{style:'display:flex;align-items:center;gap:10px;flex-wrap:wrap'});
 head.append(h('b',{style:'font:700 12px Consolas,monospace;letter-spacing:.06em;text-transform:uppercase'},'Fetch'),fdot(worst,12),h('span',{style:'flex:1;font-weight:700'},hl.title));
 const mk=(t,fn,on)=>h('button',{class:on?'on':'',onclick:fn},t);
 if(!FP.hidden){[['a','Bars'],['b','Columns'],['c','Gauges']].forEach(x=>head.append(mk(x[1],()=>{FP.layout=x[0];lput('fp.layout',x[0]);fpRender();},FP.layout===x[0])));
}
 head.append(mk(FP.hidden?'Show':'Hide',()=>{FP.hidden=!FP.hidden;FP.pinned=!FP.hidden;lput('fp.hidden',FP.hidden?'1':'0');fpRender();}));
 box.append(head);
 if(FP.hidden){el.append(box);return;}
 box.append(h('div',{class:'small',style:'margin:2px 0 8px 22px'},hl.detail));
 if(FP.toast){const t=FP.toast;box.append(h('div',{style:`border:1px solid ${FCOL[t.level==='error'?'red':'yellow']};border-left:6px solid ${FCOL[t.level==='error'?'red':'yellow']};padding:4px 8px;margin:0 0 8px;background:#fff`},h('b',null,'New: '),t.text,' ',h('button',{onclick:()=>{FP.toast=null;fpRender();}},'Dismiss')));}
 if(FP.confirm){const c=FP.confirm,e=c.est;box.append(h('div',{style:'border:2px solid var(--acc);padding:8px 10px;margin:0 0 8px;background:#f2f6ff'},h('b',null,'Start this fetch?'),h('div',{style:'margin:4px 0'},e.text),h('div',{class:'small'},'Each source stays under '+Math.round(e.margin*100)+'% of its limit, so a second fetcher on this connection is safe. You can stop and resume at any time.'),
  h('div',{class:'row'},h('button',{onclick:()=>startStage(c.stage,c.device,true)},'Start'),h('button',{onclick:()=>{FP.confirm=null;fpRender();}},'Not now'))));}
 box.append(h('div',{html:(FP.layout==='b'?fpBarsB(hs):FP.layout==='c'?fpBarsC(hs):fpBarsA(hs))}));
 box.append(h('div',{class:'small',style:'border-top:1px solid var(--hair);padding-top:4px;margin-top:2px'},'Solid fill: requests in the current window. Dashed line: auto-stop, at '+Math.round((d.hosts[0]?d.hosts[0].margin:0.5)*100)+'% of the limit. Green: fine. Yellow: paused. Red: stopped after repeated errors.'));
 // notes: the persistent record, with actions on sources that need attention
 const trouble=d.hosts.filter(x=>x.colour!=='green');
 trouble.forEach(x=>{const col=FCOL[x.colour];const n=h('div',{style:`border:1px solid ${col};border-left:6px solid ${col};padding:5px 8px;margin-top:8px`});
  n.append(h('div',null,x.last_event?x.last_event.text:(x.label+': '+fpStatusText(x))));
  const a=h('div',{class:'row',style:'margin:4px 0 0'});a.append(h('button',{onclick:()=>fpRetry(x.host,false)},'Retry now'));
  const sel=h('select',{onchange:()=>{fpSchedule(x.host,+sel.value);}},h('option',{value:'0'},'Schedule retry…'),h('option',{value:'15'},'In 15 minutes'),h('option',{value:'60'},'In 1 hour'));a.append(sel);
  const s=FP.sched[x.host];if(s)a.append(h('span',{class:'small',style:'color:var(--good)'},'Will retry at '+new Date(s.at).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})+' (needs AutoRAN to stay open)'));
  n.append(a);box.append(n);});
 const evs=(d.events||[]).filter(e=>e.level!=='info').slice(0,5);
 if(evs.length){const lg=h('div',{style:'margin-top:8px'},h('div',{class:'small'},'Notes (kept on disk)'));evs.forEach(e=>lg.append(h('div',{class:'small',style:'padding:1px 0'},fdot(e.level==='error'?'red':'yellow',8),' '+new Date(e.ts*1000).toLocaleTimeString()+'  '+e.text)));box.append(lg);}
 if(FP.err)box.append(h('div',{class:'warn bad'},FP.err));
 el.append(box);}
async function fpPoll(){
 try{const d=await api('/api/fetch/status');FP.data=d;FP.err=null;const fresh=fpAlerts(d.events);
  const active=d.jobs_running||d.hosts.some(x=>x.progress&&x.progress.done<x.progress.total),calm=d.headline.colour==='green'&&!active;
  if(!calm||fresh){FP.idleSince=null;if(!FP.pinned&&(d.headline.colour!=='green'||active))FP.hidden=false;}                  // trouble or a running fetch opens the panel
  else if(!FP.idleSince)FP.idleSince=Date.now();
  else if(Date.now()-FP.idleSince>20000&&!FP.pinned&&!FP.confirm)FP.hidden=true;                                         // nothing to see for 20 s: collapse to the strip
  fpTick();fpRender();}catch(e){}}
function fpStart(){if(!$('fp'))return;fpPoll();setInterval(fpPoll,2000);}

async function boot(){
 const main=$('main');
 await waitBridge();
 if(hasBridge()){
  const box=h('div',{style:'padding:60px 20px;max-width:640px'},h('div',{class:'q',style:'font-size:20px'},'AutoRAN is starting'),h('div',{class:'m',id:'bootmsg',style:'margin-top:8px'},'Loading…'),
   h('div',{class:'small',style:'margin-top:6px'},'Reading 266,916 trials into memory on this computer. This takes about half a minute.'));
  main.replaceChildren(box);
  for(;;){const st=await api('/api/status');$('bootmsg').textContent=st.error?('Could not load: '+st.error):(st.message+' · '+st.seconds+' s');
   if(st.ready)break;if(st.error){box.append(h('div',{class:'warn bad',style:'margin-top:10px'},'Run the pipeline first (normalise, label, categorize, score, metrics) or check state/app.log.'),h('button',{onclick:()=>location.reload()},'Try again'));return;}
   await new Promise(r=>setTimeout(r,600));}}
 const st0=await api('/api/status');S.empty=!!st0.empty;
 if(S.empty){try{S.gpu=await api('/api/gpu');}catch(e){S.gpu=null;}go();return;}
 S.m=await api('/api/metrics');S.facets=await api('/api/facets');S.audit=await api('/api/audit-summary');
 try{S.gpu=await api('/api/gpu');}catch(e){S.gpu=null;}
 go();}
document.addEventListener('click',e=>{const a=e.target.closest&&e.target.closest('a[target=_blank]');if(a&&hasBridge()){e.preventDefault();api('/api/open',{url:a.href}).catch(()=>{});}});
boot();
fpStart();
</script></body></html>
"""
