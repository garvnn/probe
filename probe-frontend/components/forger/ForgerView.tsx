'use client';
import { useEffect, useRef, useState } from 'react';
import { ArrowRight, Play } from 'lucide-react';
import { api } from '@/lib/api';
import { useDemo } from '@/lib/demo-context';
import { AttackReplay } from './AttackReplay';
import { ErrorPanel, Loading } from '@/components/shared/Primitives';
/** The demo trial (DEMO_SEED 2026, scenario B); saved Impostor runs attack it. Used when Setup was skipped. */
const DEMO_TRIAL='tr_2026_B';
export function ForgerView({next}:{next?:()=>void}){
  const {trialId,setTrialId,fakeDataRunId,setFakeDataRunId,markMock,setStep}=useDemo();const [busy,setBusy]=useState(false);const[error,setError]=useState<unknown>(null);
  const start=async()=>{setBusy(true);setError(null);try{const result=await api.startFakeData(trialId??DEMO_TRIAL);markMock(result);if(!result.run_id)throw Error('POST /fake-data/runs did not return run_id');if(!trialId)setTrialId(result.trial_id);setFakeDataRunId(result.run_id)}catch(e){setError(e)}finally{setBusy(false)}};
  const started = useRef(false);
  useEffect(()=>{ if(!fakeDataRunId && !started.current){started.current=true; void start();} /* eslint-disable-next-line react-hooks/exhaustive-deps */},[]);
  return <div>
    {!fakeDataRunId&&!busy&&error==null&&<div className="panel p-8" style={{background:'radial-gradient(ellipse at 90% 15%,#3d246d55,transparent 60%),#0d0d10'}}><div className="mono text-xs text-[#bba9f3] mb-5">CHECK 01 / FAKE SITE RECORDS</div><h3 className="text-3xl font-bold tracking-[-.05em] max-w-xl">Can fabricated site records pass fraud monitoring?</h3><p className="text-sm text-[#aaa6b0] leading-6 mt-5 mb-8 max-w-xl">An LLM attacker writes code that fabricates a whole trial site. Sentinel scores it, tells the attacker which checks fired, and the attacker rewrites its code.</p><button className="button-purple" onClick={start}><Play size={16}/> START THE FAKE SITE TEST</button></div>}
    {busy&&<Loading message="Loading the attack run..."/>}
    {fakeDataRunId&&<AttackReplay runId={fakeDataRunId}/>}
    {error!=null&&<div className="mt-4"><ErrorPanel error={error} retry={start}/></div>}
    <div className="mt-6 flex gap-3 flex-wrap"><button disabled={!fakeDataRunId} className="button-primary" onClick={()=>next?next():setStep(2)}>CHECK THE IMPROVEMENT <ArrowRight size={16}/></button></div>
  </div>;
}
