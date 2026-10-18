'use client';
import { useEffect, useMemo, useState } from 'react';
import { X, Code2, RotateCcw, Pause, Play, StepForward, AlertTriangle, ShieldAlert, Check, Bot, Target, Box, Coins } from 'lucide-react';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, ReferenceLine, Tooltip, XAxis, YAxis } from 'recharts';
import { useForgerStream, type RoundEvent } from '@/lib/useForgerStream';
import { api, type Schemas } from '@/lib/api';
import { useDemo } from '@/lib/demo-context';
import { diffLines } from '@/lib/diff';
import { copy, humanize } from '@/lib/copy';
import { Caption, ErrorPanel, SectionLabel } from '@/components/shared/Primitives';
type RunDetail = Schemas['FakeDataRunDetail'];
const fmt=(v:number|null|undefined,d=2)=>v===null||v===undefined||!Number.isFinite(v)?'N/A':v.toFixed(d);
const checkName=(c:string)=>humanize(c,copy.checkLabels);
type Verdict='error'|'escaped'|'detected';
const verdictOf=(r:RoundEvent):Verdict=>!r.ok?'error':r.escaped?'escaped':'detected';
const VERDICT={error:{label:'CODE FAILED',cls:'status-untested',color:'#8e8898'},escaped:{label:'NOT FLAGGED',cls:'status-broken',color:'#d6ff48'},detected:{label:'FLAGGED',cls:'status-held',color:'#a58bff'}} as const;
const roundNo=(r:RoundEvent)=>String(r.round+1).padStart(2,'0');
function Pill({verdict}:{verdict:Verdict}){const v=VERDICT[verdict];return <span className={`pill ${v.cls}`}>{verdict==='escaped'?<ShieldAlert size={11}/>:verdict==='detected'?<Check size={11}/>:<AlertTriangle size={11}/>} {v.label}</span>}
/** Header: who attacked what. A stand-in run carries its label; a real one says so. */
function RunHeader({run,status,rounds,controls}:{run:RunDetail|null;status:string;rounds:number;controls:React.ReactNode}){
  const real=run!==null&&run._mock!==true;
  const meta:[React.ReactNode,string,string][]=[[<Bot key="a" size={15}/>,'ATTACKER',run?`${run.attacker_model}${run.attacker_seed!=null?` · seed ${run.attacker_seed}`:''}`:'…'],[<Target key="t" size={15}/>,'TARGET',run?`Sentinel v${run.suite_version} · flag at ≥ ${fmt(run.threshold)}`:'…'],[<Box key="b" size={15}/>,'FAKE SITE',run?`${run.fake_site_id??'N/A'} · ${run.trial_id}`:'…'],[<Coins key="c" size={15}/>,'TOKENS',run?`${run.input_tokens.toLocaleString()} in · ${run.output_tokens.toLocaleString()} out`:'…']];
  return <div className="panel p-5 mb-4"><div className="flex flex-wrap items-center justify-between gap-4"><div className="flex items-center gap-3"><span className="signal"><span className="signal-dot"/></span><div><div className="panel-heading">// IMPOSTOR / ATTACK REPLAY</div><div className="mono text-xs text-[#aaa6ad] mt-2">{status.toUpperCase()} · ROUND {rounds} / {run?.rounds_done??'…'}{run?` · ${run.runner.replace(/Runner$/,'').toUpperCase()} SANDBOXES`:''}</div></div>{run&&<span className={`pill ${real?'status-held':'status-untested'}`}>{real?'REAL RUN':'STAND-IN · NOT A RESULT'}</span>}</div><div className="flex flex-wrap gap-2">{controls}</div></div>
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mt-5 pt-4 border-t border-[#29272e]">{meta.map(([icon,k,v])=><div key={k} className="min-w-0"><div className="panel-heading flex items-center gap-2" style={{color:'#9b87e8'}}>{icon}{k}</div><div className="mono text-xs mt-2 text-[#f0eee5] truncate" title={v}>{v}</div></div>)}</div>
    {run?.label&&!real&&<p className="mono text-[11px] text-[#9a92a1] mt-3">{run.label}</p>}</div>;
}
/** One slot per planned round; click to inspect. */
function Timeline({rounds,planned,selected,onSelect}:{rounds:RoundEvent[];planned:number;selected:number|null;onSelect:(i:number)=>void}){
  return <div className="grid gap-2 mb-4" style={{gridTemplateColumns:`repeat(${Math.max(planned,rounds.length,1)},minmax(0,1fr))`}}>{Array.from({length:Math.max(planned,rounds.length)},(_,i)=>{const r=rounds[i];const v=r?verdictOf(r):null;const sel=selected===i;
    return <button key={i} disabled={!r} onClick={()=>onSelect(i)} className="text-left px-2 py-3 border transition-colors" style={{borderColor:sel?'#f0efe5':v?VERDICT[v].color+'88':'#29272e',background:v==='escaped'?'#d6ff48':sel?'#231a3b':'#0d0d10',color:v==='escaped'?'#09090b':undefined,opacity:r?1:.45}} aria-label={r?`Round ${i+1}: ${VERDICT[v!].label}`:`Round ${i+1}: pending`}><div className="mono text-[10px]">R{String(i+1).padStart(2,'0')}</div><div className="mono text-sm font-bold mt-1">{!r?'·':v==='error'?'ERR':fmt(r.combined,1)}</div></button>})}</div>;
}
/** Per-check scores against the single suite threshold (combined = max). */
function CheckBars({round}:{round:RoundEvent}){
  const entries=Object.entries(round.scores??{});const top=Math.max(round.threshold*1.6,...entries.map(([,v])=>v),1);
  if(!entries.length)return <div className="mono text-xs text-[#8e8898]">No scores: the code did not produce a valid site.</div>;
  return <div className="space-y-3">{entries.map(([name,v])=>{const fired=v>=round.threshold;return <div key={name}><div className="flex justify-between text-xs mb-1"><span className="text-[#c7c1cd]">{checkName(name)}</span><span className="mono" style={{color:fired?'#ff878a':'#a3f0cc'}}>{fmt(v)} {fired?'FIRED':'PASSED'}</span></div><div className="relative h-[8px] bg-[#29272e]"><div style={{height:'100%',width:`${Math.min(100,v/top*100)}%`,background:fired?'#ff878a':'#a58bff',transition:'width .6s'}}/><div style={{position:'absolute',top:-4,bottom:-4,left:`${round.threshold/top*100}%`,borderLeft:'2px dashed #f0efe5'}}/></div></div>})}<div className="mono text-[10px] text-[#9994a0]">DASHED LINE / SUITE THRESHOLD {fmt(round.threshold)}</div></div>;
}
/** What Sentinel told the attacker: the fake site's value against the real-site 10th–90th percentile. */
function Diagnostics({round}:{round:RoundEvent}){
  const diags=round.diagnostics??[];if(!diags.length)return <p className="text-xs text-[#8e8898]">{round.escaped?'Nothing fired, so the attacker got no feedback.':'No per-measure detail in this round.'}</p>;
  return <div className="space-y-4">{diags.map(d=><div key={d.check}><div className="mono text-[11px] text-[#ff9fa4] mb-2">{checkName(d.check).toUpperCase()}</div>{d.measures.map(m=>{const [lo,hi]=m.real_sites_typical;const vals=[lo,hi,m.your_site].filter((x):x is number=>typeof x==='number'&&Number.isFinite(x));
    const min=Math.min(...vals),max=Math.max(...vals),pad=(max-min||1)*.2,a=min-pad,b=max+pad,pos=(x:number)=>`${(x-a)/(b-a)*100}%`;const out=m.position!=='within';
    return <div key={m.measure} className="mb-3"><div className="text-xs text-[#c7c1cd]">{m.measure}</div>{vals.length>0&&lo!=null&&hi!=null&&<div className="relative h-[16px] mt-2 bg-[#18161c]"><div title="Real sites, 10th–90th percentile" style={{position:'absolute',top:3,bottom:3,left:pos(lo),width:`calc(${pos(hi)} - ${pos(lo)})`,background:'#3d5a4c'}}/>{m.your_site!=null&&<div title="This fake site" style={{position:'absolute',top:0,bottom:0,left:pos(m.your_site),width:3,marginLeft:-1,background:out?'#ff878a':'#a3f0cc'}}/>}</div>}<div className="flex justify-between mono text-[10px] text-[#9994a0] mt-1"><span>FAKE <b style={{color:out?'#ff878a':'#a3f0cc'}}>{fmt(m.your_site)}</b> · {m.position.toUpperCase()}</span><span>REAL SITES {fmt(lo)}–{fmt(hi)}</span></div></div>})}</div>)}</div>;
}
function CodeModal({rounds,index,close}:{rounds:RoundEvent[];index:number;close:()=>void}){
  const cur=rounds[index],prev=index>0?rounds[index-1]:null;
  const lines=useMemo(()=>cur?.code?prev?.code?diffLines(prev.code,cur.code):cur.code.split('\n').map((text,i)=>({kind:'same' as const,text,newNo:i+1})):[],[cur,prev]);
  const added=lines.filter(l=>l.kind==='add').length,removed=lines.filter(l=>l.kind==='del').length;
  return <div className="modal-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)close()}} role="dialog" aria-modal="true" aria-label="Attacker code diff"><div className="modal"><div className="flex items-center justify-between p-5 border-b border-[#3b3740]"><div className="mono text-sm">// ATTACKER CODE / ROUND {cur?roundNo(cur):'?'}{prev?` VS ${roundNo(prev)}`:''} · <span style={{color:'#a3f0cc'}}>+{added}</span> <span style={{color:'#ff878a'}}>−{removed}</span>{cur?.attacker_model?` · ${cur.attacker_model}`:''}</div><button onClick={close} aria-label="Close code view"><X size={20}/></button></div>
    <div className="overflow-auto min-h-0 p-4">{lines.length?<pre className="text-xs leading-5">{lines.map((l,i)=><span key={i} style={{display:'block',background:l.kind==='add'?'#255f4555':l.kind==='del'?'#4a212670':undefined,color:l.kind==='del'?'#d9a3a8':undefined}}><span className="select-none inline-block w-10 text-right pr-3 text-[#6c6773]">{l.newNo??''}</span><span className="select-none inline-block w-4 text-[#8e8898]">{l.kind==='add'?'+':l.kind==='del'?'−':' '}</span>{l.text||' '}</span>)}</pre>:<p className="mono text-xs text-[#8e8898]">This round carries no code (mock fixtures don&apos;t; saved runs do).</p>}</div>
    <p className="mono text-[10px] p-4 text-[#9a92a1] border-t border-[#3b3740]">GREEN / ADDED SINCE LAST ROUND · RED / REMOVED · ESC TO CLOSE · CODE RAN ONLY IN AN ISOLATED SANDBOX</p></div></div>;
}
export function AttackReplay({runId}:{runId:string}){
  const {rounds,status,error,pause,resume,restart,step,buffered}=useForgerStream(runId);
  const {markMock,setDamage,observe}=useDemo();
  const [run,setRun]=useState<RunDetail|null>(null);const [runError,setRunError]=useState<unknown>(null);
  const [picked,setPicked]=useState<number|null>(null);const [showCode,setShowCode]=useState(false);
  useEffect(()=>{setRun(null);api.getFakeDataRun(runId).then(r=>{markMock(r);setRun(r)}).catch(setRunError)},[runId,markMock]);
  useEffect(()=>{rounds.forEach(markMock)},[rounds,markMock]);
  // Follow the newest round unless the presenter clicked one.
  const selected=picked!==null&&picked<rounds.length?picked:rounds.length?rounds.length-1:null;
  const sel=selected!==null?rounds[selected]:null;
  const escape=useMemo(()=>rounds.find(r=>r.escaped)??null,[rounds]);
  useEffect(()=>{if(!escape?.damage)return;const mock=escape._mock===true;
    setDamage({...escape.damage,runId,isMock:mock});
    // A measured escape breaks Data authenticity; mock rounds never change the contract.
    if(!mock)observe({name:'Data authenticity',status:'BROKEN',counterexample:`Fake site${run?.fake_site_id?` ${run.fake_site_id}`:''} accepted as authentic (round ${escape.round+1}, Sentinel v${run?.suite_version??0}${escape.attacker_model?`, ${escape.attacker_model}`:''})`});
  },[escape,runId,run,setDamage,observe]);
  useEffect(()=>{const p=()=>status==='paused'?resume():pause();const c=()=>setShowCode(true);const close=()=>setShowCode(false);window.addEventListener('probe:pause',p);window.addEventListener('probe:code',c);window.addEventListener('probe:close',close);return()=>{window.removeEventListener('probe:pause',p);window.removeEventListener('probe:code',c);window.removeEventListener('probe:close',close)}},[status,pause,resume]);
  const plot=useMemo(()=>rounds.map(r=>({round:r.round+1,combined:r.combined??undefined,escaped:r.escaped})),[rounds]);
  const threshold=run?.threshold??rounds[0]?.threshold??null;
  const controls=<><button className="button-secondary !min-h-[37px] !px-3" onClick={status==='paused'?resume:pause}>{status==='paused'?<Play size={13}/>:<Pause size={13}/>} {status==='paused'?'RESUME':'PAUSE'}</button><button className="button-secondary !min-h-[37px] !px-3" onClick={step} title="Reveal next buffered round"><StepForward size={13}/> STEP</button><button className="button-secondary !min-h-[37px] !px-3" onClick={()=>{setPicked(null);restart()}}><RotateCcw size={13}/> REPLAY</button><button className="button-secondary !min-h-[37px] !px-3" disabled={!sel?.code} onClick={()=>setShowCode(true)}><Code2 size={13}/> CODE</button></>;
  return <div>
    <RunHeader run={run} status={status} rounds={rounds.length} controls={controls}/>
    {runError!=null&&<div className="mb-4"><ErrorPanel error={runError}/></div>}
    <Timeline rounds={rounds} planned={run?.rounds_done??0} selected={selected} onSelect={setPicked}/>
    {escape&&<div className="mb-4 border border-[#d6ff48] p-6" style={{background:'radial-gradient(ellipse at 85% 0%,#d6ff4822,transparent 60%),#15160c'}}><div className="flex items-center gap-2 mono text-xs text-[#d6ff48] mb-3"><AlertTriangle size={18}/> {copy.counterexample} / DATA AUTHENTICITY / ROUND {roundNo(escape)}</div><div className="text-3xl md:text-4xl font-bold tracking-[-.055em]">The fraud checks accepted a fabricated site.</div><p className="text-sm text-[#c9c5b8] mt-3 max-w-2xl leading-6">Every Sentinel check scored below the flag line (highest {fmt(escape.combined)} vs threshold {fmt(escape.threshold)}). The attacker got there by rewriting its code after each round&apos;s feedback.</p>
      {escape.damage&&<div className="mt-5 flex flex-wrap gap-8">{([['TREATMENT EFFECT / REAL',fmt(escape.damage.effect_real,3)],['WITH THE FAKE SITE',fmt(escape.damage.effect_with_fake,3)],['P-VALUE / REAL',fmt(escape.damage.p_real,3)],['P-VALUE / WITH FAKE',fmt(escape.damage.p_with_fake,3)]] as const).map(([k,v])=><div key={k}><div className="panel-heading">{k}</div><div className="text-2xl font-bold mt-1">{v}</div></div>)}</div>}</div>}
    {rounds.length===0&&<div className="panel-dark min-h-[200px] flex flex-col items-center justify-center gap-4 mb-4"><Bot size={34} color="#8262fa"/><span className="mono text-sm text-[#9e99a7]">{status==='paused'?'REPLAY PAUSED · STEP OR RESUME':'Waiting for the first round…'}</span></div>}
    <div className="grid grid-cols-1 xl:grid-cols-[1.1fr_.9fr] gap-4">
      <div className="flex flex-col gap-4"><div className="chart-frame"><SectionLabel>HIGHEST CHECK SCORE BY ROUND</SectionLabel>{plot.length>0?<ResponsiveContainer width="100%" height={230}><LineChart data={plot} margin={{top:8,right:12,left:-8,bottom:0}}><CartesianGrid stroke="#2a2930" strokeDasharray="3 4"/><XAxis dataKey="round" stroke="#96939b" allowDecimals={false}/><YAxis stroke="#96939b" domain={[0,'auto']}/><Tooltip contentStyle={{background:'#1a1920',border:'1px solid #484151'}} formatter={(v:number)=>[fmt(v),'highest check score']} labelFormatter={l=>`Round ${l}`}/>{threshold!==null&&<ReferenceLine y={threshold} stroke="#ff7b89" strokeDasharray="7 6" label={{value:'FLAG LINE',fill:'#ff9fa4',fontSize:10,position:'insideTopLeft'}}/>}<Line dataKey="combined" stroke="#a58bff" strokeWidth={3} connectNulls isAnimationActive={false} dot={(p:{cx?:number;cy?:number;payload?:{escaped:boolean};index?:number})=>p.cx==null||p.cy==null?<g key={p.index}/>:<circle key={p.index} cx={p.cx} cy={p.cy} r={p.payload?.escaped?8:4} fill={p.payload?.escaped?'#d6ff48':'#a58bff'} stroke="#09090b" strokeWidth={2} style={{cursor:'pointer'}} onClick={()=>p.index!=null&&setPicked(p.index)}/>}/></LineChart></ResponsiveContainer>:<div className="h-[230px] flex items-center text-sm text-[#8f8d97]">Waiting for score data.</div>}<Caption>A site is flagged when any check reaches the line. Below it on every check means the fake passed.</Caption></div>
        {sel&&<div className="panel p-5"><SectionLabel>ROUND {roundNo(sel)} / SANDBOX</SectionLabel><div className="grid grid-cols-2 md:grid-cols-4 gap-4 mono text-xs"><div><div className="panel-heading">SANDBOX</div><div className="mt-2 truncate" title={sel.sandbox_id}>{sel.sandbox_id||'N/A'}</div></div><div><div className="panel-heading">ATTACKER WROTE</div><div className="mt-2">{fmt(sel.attacker_s,1)}s</div></div><div><div className="panel-heading">CODE RAN</div><div className="mt-2">{fmt(sel.runtime_s,1)}s</div></div><div><div className="panel-heading">EXECUTION</div><div className="mt-2" style={{color:sel.ok?'#a3f0cc':'#ff777b'}}>{sel.ok?'OK':'ERROR'}</div></div></div>{sel.error&&<pre className="mt-4 text-[11px] text-[#ff9fa4] whitespace-pre-wrap max-h-32 overflow-auto">{sel.error}</pre>}<p className="text-[#8f8b96] text-xs mt-4 leading-6">Attacker-written code runs only in an isolated sandbox, never on a laptop.</p></div>}
      </div>
      <div className="panel p-5">{sel?<><div className="flex items-center justify-between gap-3 mb-5"><SectionLabel>ROUND {roundNo(sel)} / SENTINEL VERDICT</SectionLabel><Pill verdict={verdictOf(sel)}/></div><CheckBars round={sel}/><div className="mt-6 pt-5 border-t border-[#29272e]"><SectionLabel>WHAT SENTINEL TOLD THE ATTACKER</SectionLabel><Diagnostics round={sel}/></div><button className="button-secondary mt-5 w-full" disabled={!sel.code} onClick={()=>setShowCode(true)}><Code2 size={15}/> {selected!==null&&selected>0?'SEE HOW THE CODE CHANGED':'VIEW ATTACKER CODE'}</button></>:<div className="text-sm text-[#8f8d97]">Round details appear as the replay runs.</div>}</div>
    </div>
    {error&&<div className="mt-4"><ErrorPanel error={new Error(error)} /></div>}
    <p className="mono text-[10px] text-[#8e8898] mt-3">{buffered} ROUNDS RECEIVED · CLICK A ROUND OR A CHART POINT TO INSPECT IT</p>
    {showCode&&selected!==null&&<CodeModal rounds={rounds} index={selected} close={()=>setShowCode(false)}/>}
  </div>;
}
