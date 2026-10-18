'use client';
import { useCallback, useEffect, useState } from 'react';
import { ArrowRight, ShieldCheck } from 'lucide-react';
import { BarChart, Bar, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, LineChart, Line, ReferenceLine, ErrorBar, Legend } from 'recharts';
import { useDemo } from '@/lib/demo-context';
import { api, type Schemas } from '@/lib/api';
import { percent } from '@/lib/utils';
import { ErrorPanel, Loading, Caption, SectionLabel } from '@/components/shared/Primitives';
import { copy } from '@/lib/copy';
type TestAttackerResult = Schemas['TestAttackerResult'];
type BreakingPointResult = Schemas['BreakingPointResult'];
/** Stranger: test-attacker evasion per check-suite version, counts with Wilson 95% intervals. */
function EvChart({data}:{data:TestAttackerResult|null}){
  const plot=(data?.rows??[]).map(r=>({name:`Suite v${r.suite_version}`,evasion:r.evasion_rate*100,err:[(r.evasion_rate-r.ci95[0])*100,(r.ci95[1]-r.evasion_rate)*100],count:`${r.escaped} / ${r.attempted}`,ci:`${percent(r.ci95[0])} – ${percent(r.ci95[1])}`,fp:percent(r.fp_rate)}));
  return <div className="chart-frame"><SectionLabel>TEST ATTACKER / FAKE SITES NOT FLAGGED</SectionLabel>{plot.length?<ResponsiveContainer width="100%" height={260}><BarChart data={plot} margin={{top:10,right:8,bottom:15,left:0}}><CartesianGrid stroke="#2e2b34" strokeDasharray="3 4"/><XAxis dataKey="name" tick={{fontSize:11,fill:'#bfbac3'}}/><YAxis domain={[0,100]} tickFormatter={v=>`${v}%`}/><Tooltip contentStyle={{background:'#18151e',border:'1px solid #494151'}} content={({active,payload})=>active&&payload?.length?<div className="panel p-3 text-xs mono">{payload[0].payload.name} · ESCAPED {payload[0].payload.count}<br/>WILSON 95% {payload[0].payload.ci}<br/>FALSE ALARMS {payload[0].payload.fp}</div>:null}/><Bar dataKey="evasion" fill="#ad96fc" radius={[2,2,0,0]}><ErrorBar dataKey="err" width={8} stroke="#f0efe5"/></Bar></BarChart></ResponsiveContainer>:<div className="h-[260px] flex items-center text-sm text-[#958f9c]">Comparison appears after Probe runs the test attacker against each check-suite version.</div>}
    {plot.length>0&&<div className="flex flex-wrap gap-6 mono text-xs mt-2">{plot.map(p=><span key={p.name}>{p.name.toUpperCase()} / {p.count} ESCAPED</span>)}</div>}
    <div className={`pill mt-3 ${data?.never_seen_during_patching?'status-held':'status-untested'}`}>{data?.never_seen_during_patching?copy.heldout:'Test attacker independence not confirmed'}</div><Caption>Do the updated checks catch more fakes from an attacker that was never used to patch them?</Caption></div>;
}
/** Breaking Point: p-value as k undetected fake sites are added, before vs after patching. */
export function BreakingPointChart({before,after}:{before:BreakingPointResult|null;after:BreakingPointResult|null}){
  const index=new Map<number,{k:number;before?:number;after?:number}>();
  before?.curve.forEach(r=>index.set(r.k,{k:r.k,before:r.p}));
  after?.curve.forEach(r=>index.set(r.k,{...index.get(r.k),k:r.k,after:r.p}));
  const points=Array.from(index.values()).sort((a,b)=>a.k-b.k);
  const breakText=(r:BreakingPointResult|null)=>!r?'N/A':r.break_k===null?`> ${Math.max(...r.curve.map(c=>c.k))}`:String(r.break_k);
  return <div className="chart-frame"><SectionLabel>BREAKING POINT / P-VALUE BY FAKE SITES ADDED</SectionLabel>{points.length?<ResponsiveContainer width="100%" height={220}><LineChart data={points}><CartesianGrid stroke="#2e2b34" strokeDasharray="3 4"/><XAxis dataKey="k" stroke="#817e88"/><YAxis stroke="#817e88" domain={[0,'auto']}/><Tooltip contentStyle={{background:'#18151e',border:'1px solid #494151'}}/><Legend/><Line type="monotone" dataKey="before" name={`Suite v${before?.suite_version??0}`} stroke="#ad96fc" strokeWidth={2}/><Line type="monotone" dataKey="after" name={`Suite v${after?.suite_version??'N'}`} stroke="#d6ff48" strokeWidth={2}/><ReferenceLine y={0.05} stroke="#ff7782" strokeDasharray="6 4"/></LineChart></ResponsiveContainer>:<div className="h-[220px] flex items-center text-sm text-[#958f9c]">Waiting for breaking-point analysis.</div>}
    <div className="flex flex-wrap gap-6 mono text-xs mt-2"><span>FAKE SITES TO FLIP / BEFORE {breakText(before)}</span><span>AFTER {breakText(after)}</span></div><Caption>{copy.margin}</Caption></div>;
}
export function HardenView({next}:{next?:()=>void}){
  const {trialId,fakeDataRunId,suiteVersion,setSuiteVersion,damage,markMock,setStep}=useDemo();
  const [patch,setPatch]=useState<Schemas['PatchResult']|null>(null);const[heldout,setHeldout]=useState<TestAttackerResult|null>(null);
  const [curves,setCurves]=useState<{before:BreakingPointResult|null;after:BreakingPointResult|null}>({before:null,after:null});
  const [busy,setBusy]=useState(false);const[error,setError]=useState<unknown>(null);
  const run=useCallback(async()=>{if(!trialId||!fakeDataRunId)return;setBusy(true);setError(null);try{
    const h=await api.patch(trialId,fakeDataRunId,0);markMock(h);setPatch(h);
    const version=h.status==='accepted'?h.new_version:0;setSuiteVersion(version);
    const [stranger,bp0,bpN]=await Promise.allSettled([api.testAttacker(trialId,version===0?[0]:[0,version]),api.breakingPoint(trialId,0),api.breakingPoint(trialId,version)]);
    if(stranger.status==='fulfilled'){markMock(stranger.value);setHeldout(stranger.value)}else setError(stranger.reason);
    const ok=(r:PromiseSettledResult<BreakingPointResult>)=>{if(r.status==='fulfilled'){markMock(r.value);return r.value}setError(r.reason);return null};
    setCurves({before:ok(bp0),after:ok(bpN)});
  }catch(e){setError(e)}finally{setBusy(false)}},[trialId,fakeDataRunId,markMock,setSuiteVersion]);
  // Intentional one-shot on mount, not on every state update.
  useEffect(()=>{if(!trialId||!fakeDataRunId||patch)return;void run();/* eslint-disable-next-line react-hooks/exhaustive-deps */},[trialId,fakeDataRunId]);
  const accepted=patch?.status==='accepted';
  return <div>
    {!trialId||!fakeDataRunId?<div className="panel p-8 text-[#b0abb5]">Create a trial and run the fake site test first. The patch is built from that run&apos;s escaped fakes.</div>:<>
      <div className="panel p-6 mb-4" style={{background:'radial-gradient(ellipse at top right,#29204477,#0d0d10 66%)'}}><div className="flex flex-wrap gap-6 items-start justify-between"><div><SectionLabel>{patch?.created_by==='fallback'?'FALLBACK CHECK':'FACTORY DROID'} / NEW CHECK</SectionLabel><h3 className="text-3xl font-bold tracking-[-.05em]">An updated monitoring check.<br/><span style={{color:'#ad99fc'}}>Checked for false alarms.</span></h3><p className="text-sm text-[#aaa6b3] max-w-lg mt-3 leading-6">Probe only accepts a new check when it catches fake site records without causing too many false alarms on valid sites.</p></div><div className={`pill ${!patch?'status-untested':accepted?'status-held':'status-broken'}`}><ShieldCheck size={14}/>{!patch?'PENDING':accepted?'ACCEPTED':patch.status.toUpperCase()}</div></div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-8 border-t border-[#3d364b] pt-6"><div><div className="panel-heading">ESCAPED FAKES CAUGHT</div><div className="text-3xl font-bold mt-2">{patch?`${patch.caught} / ${patch.n_escaped}`:'N/A'}</div></div><div><div className="panel-heading">FALSE ALARMS / BEFORE</div><div className="text-3xl font-bold mt-2">{percent(patch?.fp_before)}</div></div><div><div className="panel-heading">FALSE ALARMS / AFTER</div><div className="text-3xl font-bold mt-2">{percent(patch?.fp_after)}</div></div><div><div className="panel-heading">CHECK SUITE</div><div className="text-3xl font-bold mt-2">v{suiteVersion}</div></div></div>
      {patch&&<details className="mt-6 border border-[#51445f] p-4"><summary className="mono text-xs cursor-pointer">VIEW NEW CHECK / {patch.check_name} ↘</summary><pre className="text-xs mt-4 overflow-auto text-[#c3baca] leading-5">{patch.check_source}</pre></details>}</div>
      {busy&&<Loading message="Checking the updated monitoring against a test attacker it has never seen..."/>}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 mt-4"><EvChart data={heldout}/><BreakingPointChart before={curves.before} after={curves.after}/></div>
      <div className="panel p-6 mt-4"><div className="flex flex-wrap items-center justify-between gap-3"><SectionLabel>DAMAGE / FIRST UNDETECTED FAKE</SectionLabel>{damage&&<span className={`pill ${damage.isMock?'status-untested':'status-held'}`}>{damage.isMock?'SAMPLE':'MEASURED'} · {damage.runId}</span>}</div><div className="flex gap-9 flex-wrap"><div><div className="panel-heading">TREATMENT EFFECT / REAL</div><div className="text-3xl font-bold mt-2">{damage?.effect_real.toFixed(3)??'N/A'}</div></div><ArrowRight size={22} color="#b9adcb"/><div><div className="panel-heading">EFFECT / WITH UNDETECTED FAKE</div><div className="text-3xl font-bold mt-2">{damage?.effect_with_fake.toFixed(3)??'N/A'}</div></div><div><div className="panel-heading">P-VALUE WITH FAKE</div><div className="text-3xl font-bold mt-2">{damage?.p_with_fake.toFixed(4)??'N/A'}</div></div></div><Caption>From the Impostor run&apos;s first escaped round; N/A when no fake escaped. No trial outcome is assumed until it is measured.</Caption></div>
      {error!=null&&<div className="mt-4"><ErrorPanel error={error} retry={run}/></div>}
      <button className="button-primary mt-7" onClick={()=>next?next():setStep(3)}>OPEN TREATMENT PRIVACY TEST <ArrowRight size={15}/></button>
    </>}
  </div>;
}
