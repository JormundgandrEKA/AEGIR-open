"""The single HTML page of the labelling tool. Plain JS, no external requests.

Layout: record text on the left (before / after, structured and diffed); on the right the questions with
every option's definition printed beside it, and a notepad that is always on screen.
"""

HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>RAN labelling</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{--fg:#111;--bg:#fff;--rule:#111;--hair:#bbb;--dim:#555;--acc:#0040ff;--delbg:#ffe3e3;--del:#b00000;--insbg:#dff5df;--ins:#005a00;--soft:#f3f3f3;--sel:#111}
*{box-sizing:border-box;border-radius:0}
html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:13px/1.4 "Segoe UI","Helvetica Neue",Arial,sans-serif;display:flex}
.mono{font-family:Consolas,"DejaVu Sans Mono","Courier New",monospace}
main{flex:1;min-width:0;display:flex;flex-direction:column;height:100vh;overflow:auto;border-right:1px solid var(--rule)}
aside{width:460px;flex:none;height:100vh;display:flex;flex-direction:column}
.hdr{border-bottom:1px solid var(--rule);padding:4px 10px;display:flex;gap:14px;white-space:nowrap;overflow:hidden;font:12px Consolas,monospace}
.hdr .t{overflow:hidden;text-overflow:ellipsis;flex:1;font-family:"Segoe UI",Arial,sans-serif;font-weight:600}
.q{padding:8px 10px;border-bottom:1px solid var(--rule);font-weight:700;font-size:15px;line-height:1.35}
.legend{padding:3px 10px;border-bottom:1px solid var(--rule);font-size:11.5px;color:var(--dim);display:flex;gap:14px;flex-wrap:wrap}
.legend .d,.legend .i{padding:0 3px}
.cols{display:grid;grid-template-columns:1fr 1fr;border-bottom:1px solid var(--rule)}
.cols.stack{grid-template-columns:1fr}
.col{min-width:0;border-right:1px solid var(--rule)}.col:last-child{border-right:0}.stack .col{border-right:0;border-bottom:1px solid var(--rule)}
.col h3{margin:0;padding:3px 10px;font:700 11.5px Consolas,monospace;text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid var(--rule);background:var(--soft)}
.txt{padding:8px 12px 10px;font:13.5px/1.55 Consolas,"DejaVu Sans Mono",monospace;max-height:46vh;overflow:auto}
.line{white-space:pre-wrap;word-break:break-word;min-height:1.55em}
.line.blank{min-height:.6em;line-height:.6em}
.line.hd{font-weight:700;margin-top:.5em}
.line.bul{padding-left:1.6em;text-indent:-1.3em}
.line.gap{color:var(--dim);font-style:italic;font-size:12px;border-top:1px dotted var(--hair);border-bottom:1px dotted var(--hair);margin:4px 0}
.del{background:var(--delbg);color:var(--del);text-decoration:line-through}
.ins{background:var(--insbg);color:var(--ins);text-decoration:underline}
table{border-collapse:collapse;font:12.5px Consolas,monospace}
td,th{border:1px solid var(--rule);padding:2px 8px;text-align:left}th{background:var(--soft)}
td.del{background:var(--delbg)}td.ins{background:var(--insbg)}
.note{padding:6px 10px;border-bottom:1px solid var(--rule)}
.ctx{display:flex;gap:18px;flex-wrap:wrap;padding:5px 10px;border-bottom:1px solid var(--rule);font-size:12px}
.ctx b{font-family:Consolas,monospace}
a{color:var(--acc)}
/* sidebar */
.qs{flex:1;overflow:auto;min-height:0}
.sech{padding:3px 10px;background:var(--soft);border-bottom:1px solid var(--rule);font:700 11.5px Consolas,monospace;text-transform:uppercase;letter-spacing:.05em}
.grp{border-bottom:1px solid var(--rule)}
.grp.cur{outline:2px solid var(--acc);outline-offset:-2px}
.gl{padding:4px 10px 2px;font-weight:700}
.gl small{font-weight:400;color:var(--dim);margin-left:6px}
.opt{display:grid;grid-template-columns:22px 1fr;gap:0 6px;padding:3px 10px;cursor:pointer;border-top:1px solid var(--hair)}
.opt:hover{background:var(--soft)}
.opt .k{font:700 12px Consolas,monospace;color:var(--dim);text-align:center;border:1px solid var(--hair);height:19px;line-height:17px}
.opt .nm{font-weight:600}
.opt .df{grid-column:2;color:#333;font-size:12px;line-height:1.3}
.opt.sel{background:var(--sel);color:#fff}.opt.sel .df{color:#ddd}.opt.sel .k{color:#fff;border-color:#fff}
textarea{font:13px/1.4 Consolas,monospace;border:1px solid var(--rule);padding:4px;width:100%;background:var(--bg);color:var(--fg);resize:vertical}
textarea:focus,input:focus{outline:2px solid var(--acc)}
input[type=text]{font:13px Consolas,monospace;border:1px solid var(--rule);padding:3px;width:100%}
button{font:12.5px "Segoe UI",Arial,sans-serif;border:1px solid var(--rule);background:var(--bg);color:var(--fg);padding:3px 10px;cursor:pointer}
button:hover{background:var(--fg);color:var(--bg)}
.bar{display:flex;gap:6px;padding:6px 10px;align-items:center;flex-wrap:wrap;border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);position:sticky;bottom:0;background:var(--bg)}
#msg{color:var(--del);font:12px Consolas,monospace;width:100%}
.prov{padding:5px 10px;border-bottom:1px solid var(--rule)}
.prov .pt{white-space:pre-wrap;font:12.5px/1.45 Consolas,monospace;margin-top:3px;max-height:34vh;overflow:auto}
#pad{flex:none;border-top:2px solid var(--rule);display:flex;flex-direction:column;background:var(--bg)}
#pad.nudge .sech{background:#fff2a8}
#pad textarea{height:110px;border:0;border-top:1px solid var(--rule)}
#pad .sech{display:flex;justify-content:space-between}
#pad .sech span+span{font-weight:400;text-transform:none;letter-spacing:0;color:var(--dim)}
#help{display:none;position:fixed;inset:30px;background:var(--bg);border:2px solid var(--rule);padding:12px;overflow:auto;z-index:5}
#help pre{font:13px/1.5 Consolas,monospace}
#end{padding:30px;font-size:15px}
</style></head><body>
<main id="main"></main>
<aside>
 <div class="qs" id="qs"></div>
 <div id="pad"><div class="sech"><span>Notepad &mdash; kept, saved automatically [N]</span><span id="padst">empty</span></div>
  <textarea id="padtxt" placeholder="Notes on the tool, the task, or anything you want design to read. Add to it as you go: it stays here across cases and sessions."></textarea></div>
</aside>
<div id="help"><b>Keys</b><pre>
Up / Down   move between questions      1-9, 0   choose option (change types: toggle several)
Y  D  U     real change: yes / did not change / unsure
Enter       save and next               B / Backspace   back
X           skip (asks a reason)        P   reveal provisional label
F           full text / changed parts   L   side by side / stacked
N           jump to the notepad         Esc  leave a text box or close this
Q Q         finish the session (press twice; progress is saved as you go)       ?   this help
In a text box: Ctrl+Enter saves the case.
Reading the text: red struck-through = in the before version only; green underlined = in the after version only.
</pre><button onclick="document.getElementById('help').style.display='none'">Close</button></div>
<script>
"use strict";
const S={cases:[],done:{},drafts:{},defs:{},idx:0,ans:{},row:0,revealed:false,full:false,stack:false,lastInput:Date.now(),
 activeTotal:0,nextNudge:300,prov:null,skipOpen:false,timing:null,idle:false,quitArm:0,padCase:null};
const $=id=>document.getElementById(id);
function h(tag,attrs,...kids){const e=document.createElement(tag);
 for(const k in (attrs||{})){if(k==='class')e.className=attrs[k];else if(k.startsWith('on'))e.addEventListener(k.slice(2),attrs[k]);else e.setAttribute(k,attrs[k]);}
 for(const c of kids.flat()){if(c==null)continue;e.append(c.nodeType?c:document.createTextNode(String(c)));}return e;}
async function api(p,b){const r=await fetch(p,{method:b?'POST':'GET',headers:{'Content-Type':'application/json'},body:b?JSON.stringify(b):undefined});
 const j=await r.json();if(!r.ok)throw new Error(j.error||r.status);return j;}
const cur=()=>S.cases[S.idx];
function ev(type,extra){api('/api/event',Object.assign({type,case_id:cur()&&cur().case_id,t:new Date().toISOString()},extra||{})).catch(()=>{});}

function groups(){const d=S.defs,a=S.ans,rc=a.real_change,yes=rc==='yes';
 const g=[{k:'real_change',label:'1. Real change?',req:true,opts:d.real_change}];
 if(rc)d.change_groups.forEach((cg,i)=>{if(cg.id==='wording'||rc!=='no')
  g.push({k:'change_types',label:cg.label+(cg.id==='elig'?'  — choose all that apply':''),req:(cg.id==='elig'&&yes),multi:true,opts:cg.options});});
 if(yes){g.push({k:'avoidable',label:'3. Avoidable?',opts:d.avoidable});
  g.push({k:'cause',label:'4. Likely cause (optional, choose all that apply)',multi:true,opts:d.cause});
  g.push({k:'severity',label:'5. Severity',opts:d.severity});}
 if(S.revealed)g.push({k:'agree_with_provisional',label:'6. Agree with the provisional label?',opts:d.agree});
 g.push({k:'note',label:'Case note (optional)',text:true});
 return g;}
function isSel(g,v){return g.multi?(S.ans[g.k]||[]).includes(v):S.ans[g.k]===v;}
function setAns(g,v){const k=g.k;
 if(g.multi){const a=(S.ans[k]||[]).slice();const i=a.indexOf(v);if(i>=0)a.splice(i,1);else a.push(v);S.ans[k]=a;ev('input',{field:k,value:a.join(',')});S.timing.answer_changes++;draftSoon();return;}
 const had=S.ans[k]!==undefined&&S.ans[k]!==v;S.ans[k]=v;if(had)S.timing.answer_changes++;ev('input',{field:k,value:k==='note'?'(text)':v});
 if(k==='real_change'&&v!=='yes'){['avoidable','cause','severity'].forEach(x=>delete S.ans[x]);
  if(v==='no')S.ans.change_types=(S.ans.change_types||[]).filter(x=>x.startsWith('wording_'));}
 draftSoon();}
let draftTimer=null;
function draftSoon(){clearTimeout(draftTimer);draftTimer=setTimeout(()=>{const c=cur();if(c&&!S.done[c.case_id])api('/api/draft',{case_id:c.case_id,answers:S.ans}).catch(()=>{});},800);}
function input(){if(S.idle){S.idle=false;ev('idle_end');}S.lastInput=Date.now();
 if(S.timing&&!S.timing.first_input_at)S.timing.first_input_at=new Date().toISOString();}

// ---- text: lines with structure; changed parts only unless full ----
function toLines(ops){const lines=[[]];
 for(const [t,s] of ops){const parts=s.split('\n');parts.forEach((p,i)=>{if(i>0)lines.push([]);if(p!=='')lines[lines.length-1].push([t,p]);});}
 return lines;}
function lineKind(segs){const txt=segs.map(x=>x[1]).join('').trim();
 if(!txt)return 'blank';
 if(/^(•|\d+\.)\s/.test(txt))return 'bul';
 if(/^(inclusion|exclusion)\b/i.test(txt)||(/:$/.test(txt)&&txt.length<90))return 'hd';
 return '';}
function renderText(ops,full){const lines=toLines(ops),n=lines.length;
 const changed=lines.map(l=>l.some(x=>x[0]!=='eq'));
 const keep=lines.map((_,i)=>full||changed.slice(Math.max(0,i-2),i+3).some(Boolean)||n<=24);
 const box=h('div',{class:'txt'});let skipped=0;
 const flush=()=>{if(skipped){box.append(h('div',{class:'line gap'},'… '+skipped+' unchanged line'+(skipped>1?'s':'')+' …'));skipped=0;}};
 lines.forEach((segs,i)=>{if(!keep[i]){if(segs.length)skipped++;return;}flush();
  const k=lineKind(segs);const d=h('div',{class:'line '+k});
  segs.forEach(([t,s])=>{d.append(h('span',{class:t==='del'?'del':t==='ins'?'ins':''},s));});box.append(d);});
 flush();return box;}

function render(){
 const c=cur();if(!c)return;
 const m=$('main');m.replaceChildren();
 if(S.notice)m.append(h('div',{class:'note',style:'background:#fff2a8;font-size:11.5px'},S.notice));
 m.append(h('div',{class:'hdr'},h('span',null,c.case_id),h('span',null,c.nct_id),h('span',{class:'t'},c.title||''),
  h('span',null,c.phase||'-'),h('span',null,c.sponsor_class||'-'),h('span',null,'start '+(c.start||'-')),
  h('span',null,'primary completion '+(c.primary_completion||'-')),h('span',null,'case '+(S.idx+1)+' of '+S.cases.length+' · '+Object.keys(S.done).length+' labelled')));
 m.append(h('div',{class:'q'},c.question));
 m.append(h('div',{class:'legend'},h('span',null,h('span',{class:'del'},' red struck-through '),' only in BEFORE'),
  h('span',null,h('span',{class:'ins'},' green underlined '),' only in AFTER'),
  h('span',null,'[F] '+(S.full?'full text shown':'changed parts only')),h('span',null,'[L] '+(S.stack?'stacked':'side by side'))));
 const panels=c.panels||[{key:'text',label:'Text',changed:true,ops:c.ops}];
 const table=c.table||(c.agesex||[]).map(r=>({field:r.field.replace('_',' '),before:r.before,after:r.after,changed:r.before!==r.after}));
 const shown=panels.filter(p=>p.changed||S.full),hidden=panels.filter(p=>!p.changed&&!S.full).map(p=>p.label);
 shown.forEach(p=>m.append(h('div',{class:'cols'+(S.stack?' stack':'')},
  h('div',{class:'col'},h('h3',null,p.label+' · BEFORE · v'+c.a.version+' · '+c.a.date+(p.changed?'':' · unchanged')),renderText(p.ops.before,S.full)),
  h('div',{class:'col'},h('h3',null,p.label+' · AFTER · v'+c.b.version+' · '+c.b.date+(p.changed?'':' · unchanged')),renderText(p.ops.after,S.full)))));
 const anyTable=table.some(r=>r.changed);
 if(!shown.length&&!anyTable)m.append(h('div',{class:'note'},'No difference in any text field. Press F to see the full text.'));
 if(hidden.length)m.append(h('div',{class:'note',style:'color:#555'},'Unchanged (not shown): '+hidden.join(', ')+'. [F] shows them.'));
 if(table.length){const t=h('table',null,h('tr',null,h('th',null,'field'),h('th',null,'before'),h('th',null,'after')));
  table.forEach(r=>{t.append(h('tr',{style:r.changed?'':'color:#777'},h('td',null,r.field),h('td',{class:r.changed?'del':''},r.before||'-'),h('td',{class:r.changed?'ins':''},r.after||'-')));});
  m.append(h('div',{class:'note'},t));}
 (c.notes||[]).forEach(n=>m.append(h('div',{class:'note',style:'color:#8a4b00'},'Note: '+n)));
 m.append(h('div',{class:'ctx'},
  h('span',null,'Modules changed in v'+c.b.version+': ',h('b',null,(c.b.labels||[]).join(', ')||'-')),
  h('span',null,'Why stopped: ',h('b',null,c.why_stopped||'-')),
  h('a',{href:c.links.study,target:'_blank',rel:'noopener',onclick:()=>{S.timing.links_opened=true;ev('link_opened',{which:'study'});}},'registry record'),
  h('a',{href:c.links.history,target:'_blank',rel:'noopener',onclick:()=>{S.timing.links_opened=true;ev('link_opened',{which:'history'});}},'history page')));
 renderSide();}

function renderSide(){
 const q=$('qs');const keepTop=q.scrollTop;q.replaceChildren();
 q.append(h('div',{class:'sech'},'Questions · each option is defined beside it'));
 const gs=groups();S.row=Math.min(S.row,gs.length-1);
 gs.forEach((g,i)=>{const box=h('div',{class:'grp'+(i===S.row?' cur':'')},h('div',{class:'gl'},g.label,h('small',null,g.req?'required':'')));
  if(g.text){const ta=h('textarea',{rows:'2',id:'note'});ta.value=S.ans.note||'';
   ta.addEventListener('input',()=>{input();S.ans.note=ta.value;});
   ta.addEventListener('keydown',e=>{e.stopPropagation();if(e.key==='Escape'){ta.blur();e.preventDefault();}if(e.key==='Enter'&&e.ctrlKey){save();}});
   ta.addEventListener('focus',()=>{S.row=i;});box.append(h('div',{style:'padding:2px 10px 6px'},ta));}
  else g.opts.forEach(([v,name,def],j)=>box.append(h('div',{class:'opt'+(isSel(g,v)?' sel':''),onclick:()=>{input();S.row=i;pick(g,j);}},
    h('span',{class:'k'},(j+1)%10),h('span',{class:'nm'},name),h('span',{class:'df'},def))));
  q.append(box);});
 const c=cur();
 if(c.provisional_mode==='collapsed'){const b=h('div',{class:'prov'});
  if(S.revealed&&S.prov)b.append(h('b',null,'Provisional: '+S.prov.label+' ('+(S.prov.confidence||'?')+' confidence) — '+(S.prov.summary||S.prov.source)),h('div',{class:'pt'},S.prov.evidence));
  else b.append(h('button',{onclick:reveal},'[P] reveal the provisional label'));q.append(b);}
 q.append(h('div',{class:'bar'},h('button',{onclick:save},'Save & next [Enter]'),h('button',{onclick:startSkip},'Skip [X]'),
  h('button',{onclick:back},'Back [B]'),h('button',{onclick:()=>{$('help').style.display='block';}},'Keys [?]'),
  h('button',{onclick:quitNow},'Finish [Q Q]'),h('span',{id:'msg'},'')));
 if(S.skipOpen){const s=h('div',{class:'note'},'Skip reason: ',h('input',{type:'text',id:'skiptxt',maxlength:'200'}));q.append(s);const t=$('skiptxt');t.focus();
  t.addEventListener('keydown',e=>{e.stopPropagation();if(e.key==='Escape'){S.skipOpen=false;renderSide();}if(e.key==='Enter'){doSkip(t.value||'(no reason)');}});}
 q.scrollTop=keepTop;}

function pick(g,j){setAns(g,g.opts[j][0]);if(!g.multi){const n=groups();S.row=Math.min(S.row+1,n.length-1);}renderSide();}
function msg(t){const m=$('msg');if(m)m.textContent=t;}
function load(i){S.idx=i;const d=S.done[cur().case_id]||S.drafts[cur().case_id]||{};S.ans=JSON.parse(JSON.stringify(d));
 S.row=0;S.revealed=false;S.prov=null;S.full=false;S.skipOpen=false;
 S.timing={shown_at:new Date().toISOString(),first_input_at:null,provisional_revealed_at:null,saved_at:null,active_seconds:0,answer_changes:0,full_text_opened:false,links_opened:false};
 render();$('main').scrollTop=0;ev('case_shown');}
async function reveal(){input();if(S.revealed)return;
 const p=await api('/api/reveal',{case_id:cur().case_id,t:new Date().toISOString()});
 S.prov=p;S.revealed=true;S.timing.provisional_revealed_at=new Date().toISOString();renderSide();}
async function save(){input();const a=S.ans;
 if(!a.real_change)return msg('Answer question 1 first.');
 if(a.real_change==='yes'&&!(a.change_types&&a.change_types.length))return msg('Choose at least one change type (question 2).');
 if((a.change_types||[]).includes('other')&&!(a.note||'').trim())return msg('You chose "Other": describe it in the case note.');
 S.timing.saved_at=new Date().toISOString();
 try{await api('/api/save',{case_id:cur().case_id,answers:a,timing:S.timing});}catch(e){return msg(e.message);}
 S.done[cur().case_id]=JSON.parse(JSON.stringify(a));next();}
function next(){const n=S.cases.length;
 for(let k=1;k<=n;k++){const j=(S.idx+k)%n;if(!S.done[S.cases[j].case_id]&&!S.cases[j]._skipped)return load(j);}
 for(let k=1;k<=n;k++){const j=(S.idx+k)%n;if(!S.done[S.cases[j].case_id]){S.cases[j]._skipped=false;return load(j);}}
 $('main').replaceChildren(h('div',{id:'end'},'All cases done. Press Q twice to finish the session.'));}
function back(){input();if(S.idx>0)load(S.idx-1);}
function startSkip(){input();S.skipOpen=true;renderSide();}
function doSkip(reason){ev('skip',{reason,active_seconds:S.timing.active_seconds});cur()._skipped=true;S.skipOpen=false;next();}
async function quitNow(){await padSave(true);ev('quit');await api('/api/quit',{}).catch(()=>{});
 document.body.replaceChildren(h('div',{id:'end'},'Session ended. Your labels and notepad are saved. You can close this tab.'));S.ended=true;}

// ---- notepad: always on screen, autosaved, marks which case you were on ----
let padTimer=null,padLast='';
function padMark(){const c=cur();if(!c||S.padCase===c.case_id)return;S.padCase=c.case_id;
 const ta=$('padtxt');const pos=ta.selectionStart;const mark=(ta.value&&!ta.value.endsWith('\n')?'\n':'')+'['+c.case_id+' · '+c.nct_id+'] ';
 ta.value=ta.value.slice(0,pos)+mark+ta.value.slice(pos);ta.selectionStart=ta.selectionEnd=pos+mark.length;}
async function padSave(force){const t=$('padtxt').value;if(t===padLast&&!force)return;
 try{await api('/api/notepad',{text:t,case_id:cur()&&cur().case_id});padLast=t;$('padst').textContent='saved '+new Date().toLocaleTimeString();}catch(e){$('padst').textContent='not saved: '+e.message;}}
$('padtxt').addEventListener('input',()=>{input();padMark();$('padst').textContent='typing…';clearTimeout(padTimer);padTimer=setTimeout(()=>padSave(false),1500);
 $('pad').classList.remove('nudge');});
$('padtxt').addEventListener('blur',()=>padSave(false));
$('padtxt').addEventListener('keydown',e=>{e.stopPropagation();if(e.key==='Escape'){$('padtxt').blur();}});

// ---- timing: active only while input is recent (60 s) and the tab is visible ----
setInterval(()=>{if(S.ended||!S.timing)return;
 const active=!document.hidden&&(Date.now()-S.lastInput)<=60000;
 if(active){S.timing.active_seconds++;S.activeTotal++;
  if(S.activeTotal>=S.nextNudge){S.nextNudge=S.activeTotal+300;$('pad').classList.add('nudge');ev('prompt_shown',{kind:'notepad_nudge'});
   setTimeout(()=>{if($('pad').classList.contains('nudge')){$('pad').classList.remove('nudge');ev('prompt_dismissed',{why:'timeout'});}},20000);}}
 else if(!S.idle){S.idle=true;ev('idle_start');}},1000);
['mousemove','mousedown','scroll','touchstart'].forEach(t=>addEventListener(t,input,{passive:true}));
document.addEventListener('visibilitychange',()=>{if(document.hidden&&!S.idle){S.idle=true;ev('idle_start');}else if(!document.hidden)input();});

document.addEventListener('keydown',e=>{
 if(S.ended)return;const tag=(e.target.tagName||'');if(tag==='INPUT'||tag==='TEXTAREA')return;
 if(e.ctrlKey||e.metaKey||e.altKey)return;input();const k=e.key,K=k.toLowerCase(),gs=groups();
 if(K!=='q')S.quitArm=0;
 if(k==='ArrowDown'){S.row=Math.min(S.row+1,gs.length-1);renderSide();if(gs[S.row].text)$('note').focus();e.preventDefault();}
 else if(k==='ArrowUp'){S.row=Math.max(S.row-1,0);renderSide();e.preventDefault();}
 else if(k==='Enter'){save();e.preventDefault();}
 else if(k==='Backspace'||K==='b'){back();e.preventDefault();}
 else if(K==='x'){startSkip();e.preventDefault();}
 else if(K==='p'){if(cur().provisional_mode==='collapsed')reveal();}
 else if(K==='f'){S.full=!S.full;if(S.full)S.timing.full_text_opened=true;ev('full_text',{on:S.full});render();}
 else if(K==='l'){S.stack=!S.stack;render();}
 else if(K==='n'){$('padtxt').focus();padMark();e.preventDefault();}
 else if(K==='q'){if(Date.now()-S.quitArm<3000)quitNow();else{S.quitArm=Date.now();msg('Press Q again to finish the session.');}}
 else if(k==='?'){$('help').style.display='block';}
 else if(k==='Escape'){$('help').style.display='none';}
 else if(['y','d','u'].includes(K)){const g=gs[0];setAns(g,{y:'yes',d:'no',u:'unsure'}[K]);S.row=Math.min(1,gs.length-1);renderSide();}
 else if(/^[0-9]$/.test(k)){const g=gs[S.row];const j=(+k+9)%10;if(g&&g.opts&&j<g.opts.length){pick(g,j);e.preventDefault();}}
});

(async()=>{const st=await api('/api/state');S.cases=st.cases;S.notice=st.notice||'';S.done=st.done;S.drafts=st.drafts||{};S.defs=st.defs;
 $('padtxt').value=st.notepad||'';padLast=$('padtxt').value;if(padLast)$('padst').textContent='restored';
 document.title='RAN labelling · '+st.labeller;
 const first=S.cases.findIndex(c=>!S.done[c.case_id]);
 if(first<0){$('main').replaceChildren(h('div',{id:'end'},'All cases in this batch are labelled. Press Q twice to finish.'));return;}
 load(first);})();
</script></body></html>
"""
