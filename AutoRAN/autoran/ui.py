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
</style></head><body>
<nav id="nav"><b>AutoRAN</b></nav>
<main id="main">Loading…</main>
<div id="drawer"></div>
<script>
"use strict";
const $=id=>document.getElementById(id);
function h(tag,attrs,...kids){const e=document.createElement(tag);
 for(const k in (attrs||{})){if(k==='class')e.className=attrs[k];else if(k.startsWith('on'))e.addEventListener(k.slice(2),attrs[k]);else if(k==='html')e.innerHTML=attrs[k];else e.setAttribute(k,attrs[k]);}
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
const PAGES=[['start','Get started'],['overview','Overview'],['coverage','Coverage'],['labels','Labels and rules'],['scorers','Scorers'],['browse','Browse'],['review','Review'],['plots','Plots'],['run','Run'],['settings','Settings'],['about','About']];
function nav(){const n=$('nav');n.replaceChildren(h('b',null,'AutoRAN'));
 PAGES.filter(([k])=>S.empty?['start','run','settings','about'].includes(k):k!=='start').forEach(([k,l])=>n.append(h('a',{class:S.page===k?'on':'',href:'#'+k},l)));
 const m=S.m,g=S.gpu;n.append(h('span',null,(g&&g.cuda_available?'GPU '+g.device+' '+g.memory_gb+' GB':(g&&g.torch===null?'CPU only (no GPU pack, see Settings)':'CPU only'))+' · '+(m?fmt(m.pipeline.trials)+' trials · registry data '+(m.pipeline.data_timestamp||'?').slice(0,10):'')));}
async function go(){const k=(location.hash||'#overview').slice(1).split('?')[0];S.page=PAGES.some(p=>p[0]===k)?k:'overview';if(S.empty&&!['start','run','settings','about'].includes(S.page))S.page='start';if(!S.empty&&S.page==='start')S.page='overview';nav();closeDrawer();
 const main=$('main');const ld=h('div',{class:'small'},'Loading…');main.replaceChildren(ld);
 try{if(S.timer){clearInterval(S.timer);S.timer=null;}await ({start,overview,coverage,labels,scorers,browse,review,plots,run,settings,about}[S.page])(main);ld.remove();}catch(e){main.replaceChildren(h('div',{class:'warn bad'},'Error: '+e.message));}}
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
  h('h2',null,'Label'),h('div',{class:'kv'},...[['Class',NAME[t.class]],['Stop class',t.stop_class||'-'],['Source / confidence',t.label_source+' · '+(t.status==='TERMINATED'?t.conf.toFixed(2):'-')],['Rules fired',(t.rules||[]).join(', ')||'-'],['Labeller agreement',t.disagree?'rules and model DISAGREE':'agree'],['Status',t.status]].flatMap(([a,b])=>[h('div',null,a),h('div',{class:'m'},b)])),
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
 let cards=[],cur=0,t0=Date.now(),sheet=null;
 main.append(h('h2',null,'Review: scan a screen, flag the exceptions'));
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
    h('button',{disabled:j.running?'disabled':null,onclick:async()=>{try{await api('/api/run',{stage:k,device:dev.value});}catch(e){alert(e.message);}draw();}},v.label),
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
 ['Downloads every trial in scope from ClinicalTrials.gov (about 267 requests, 214 MB, a little under an hour at the polite rate limit of 40 requests a minute). It can be stopped and resumed. No account or API key is needed.',
  'Downloads the Open Targets curated stop reasons (about 38 requests) that the labeller learns from. A Hugging Face token is optional and only raises the rate limit.',
  'Normalises, labels, categorises, scores and measures: a few minutes on a CPU, less with a GPU. The app then reloads and fills the other pages.'].forEach(x=>main.append(h('div',{class:'small',style:'margin:2px 0'},'· '+x)));
 main.append(h('div',{class:'warn'},'Requirements: an internet connection, about 2 GB of free disk space for the data, and permission to use the data under the providers’ terms (see About). Optional: set a contact email under Settings first, so the registry can reach you if your requests cause trouble.'));
 const go2=h('button',{class:'primary',onclick:async()=>{try{await api('/api/run',{stage:'run-all',device:'auto'});location.hash='#run';}catch(e){alert(e.message);}}},'Fetch everything and build (first run)');
 main.append(h('div',{class:'row',style:'margin-top:10px'},go2,h('a',{href:'#settings'},'Settings first'),h('a',{href:'#run'},'Pick individual steps')));
 main.append(h('div',{class:'small',style:'margin-top:8px'},'To try the pipeline quickly on a small sample instead, use the command line: autoran fetch --max-pages 2, then autoran labeller-data, autoran normalise --partial, label, categorize, score, metrics.'));}

async function settings(main){
 const a=await api('/api/settings');
 main.append(h('h2',null,'Settings'));
 main.append(h('div',{class:'small'},'Saved for you only, in '+a.settings_file+' (outside the project, never committed). Nothing here is needed to run AutoRAN; each field is optional. Tokens and keys are stored encrypted for this Windows user and are not shown again, only whether one is set.'));
 const rows=[
  ['workspace','Workspace folder','Where data/ and state/ are kept. Empty = the AutoRAN folder ('+a.program_folder+'). Needs a restart. Currently using: '+a.active_workspace,'text'],
  ['aegir_tool','RAN folder (tool)','The folder that contains aegir_ran/. Only needed when running from source and RAN is not next to AutoRAN. Needs a restart.','text'],
  ['history_dir','RAN history folder','Optional. RAN’s browser-collected trial histories (adds a few more clean inputs). Used at the next normalise.','text'],
  ['gpu_site','GPU pack folder','Optional, for the small AutoRAN.exe, which has no PyTorch inside. A folder that contains torch/ (a site-packages, or a folder made with pip install --target gpu_pack torch). A gpu_pack folder next to the exe is found automatically. Needs a restart.','text'],
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
 ['Fetching downloads about 214 MB from clinicaltrials.gov at 40 requests a minute; it takes a little under an hour and can be stopped and resumed. No account or key is needed.',
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
 if(S.page==='review'&&window.__rv&&!$('drawer').classList.contains('open')){const r=window.__rv,k=e.key.toLowerCase();
  if(k==='x'){r.flag('disagree');e.preventDefault();}else if(k==='u'){r.flag('unsure');e.preventDefault();}else if(k==='j'||e.key==='ArrowDown'||e.key==='ArrowRight'){r.move(1);e.preventDefault();}
  else if(k==='k'||e.key==='ArrowUp'||e.key==='ArrowLeft'){r.move(-1);e.preventDefault();}else if(k==='o'){r.open();}else if(e.key==='Enter'){r.submit();e.preventDefault();}
  else if(/^[1-9]$/.test(e.key)){r.pick(+e.key-1);}}});

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
</script></body></html>
"""
