'use client';
import { useCallback, useEffect, useState } from 'react';
import { ArrowRight, FlaskConical, ShieldCheck, Database } from 'lucide-react';
import { api } from '@/lib/api';
import { useDemo } from '@/lib/demo-context';
import { contractOf } from '@/lib/adapters';
import { asObj, pick, str, isMock } from '@/lib/utils';
import { ContractPanel } from '@/components/shared/ContractPanel';
import { Loading, ErrorPanel, DemoDisclaimer, SectionLabel } from '@/components/shared/Primitives';
import { RoleMatrix } from './RoleMatrix';
export function SetupView({next}:{next?:()=>void}){
  const {scenario,setScenario,trialId,setTrialId,contract,setContract,markMock,setStep}=useDemo();
  const [trial,setTrial]=useState<unknown>(null);const[busy,setBusy]=useState(false);const[error,setError]=useState<unknown>(null);
  const fetchTrial=useCallback(async(id:string)=>{const [t,c]=await Promise.all([api.getTrial(id),api.getContract(id)]);setTrial(t);setContract(contractOf(c),isMock(c));markMock(t)},[setContract,markMock]);
  useEffect(()=>{if(!trialId)return;fetchTrial(trialId).catch(setError)},[trialId,fetchTrial]);
  const launch=async()=>{setBusy(true);setError(null);try{const created=await api.createTrial(scenario);markMock(created);const o=asObj(created);const id=str(pick(o,'trial_id','id'));if(!id)throw Error('POST /trials did not return trial_id');setTrialId(id);await fetchTrial(id);}catch(e){setError(e)}finally{setBusy(false)}};
  const go=()=>{if(next)next();else setStep(1)};
  const o=asObj(trial);const counts=[['SITES',pick(o,'sites','n_sites')],['PATIENTS',pick(o,'n_patients','patients')],['ENDPOINT',pick(o,'endpoint','primary_endpoint')]];
  return <div>
    <div className="grid grid-cols-1 lg:grid-cols-[1.25fr_.75fr] gap-4"><ContractPanel contract={contract}/><div className="panel p-6 flex flex-col justify-between"><div><SectionLabel>SIMULATED TRIAL SETUP</SectionLabel><div className="mono text-xs text-[#9d98a1] mb-4">FICTIONAL DRUG / SIMULATED TRIAL</div><div style={{fontSize:39,letterSpacing:'-.065em',fontWeight:700}}>PRB-101<span style={{color:'#9374ee'}}>.</span></div><p className="text-sm text-[#aba8ad] mt-3">Type 2 diabetes · HbA1c change at week 24</p></div><div className="mt-8"><div className="panel-heading mb-3">CHOOSE A TRIAL SCENARIO</div><div className="tabs"><button className={`tab ${scenario==='A'?'active':''}`} onClick={()=>setScenario('A')} disabled={!!trialId}>A / DRUG HAS AN EFFECT</button><button className={`tab ${scenario==='B'?'active':''}`} onClick={()=>setScenario('B')} disabled={!!trialId}>B / DRUG HAS NO EFFECT</button></div><div className="text-xs text-[#918c98] mt-4 leading-5">Scenario B checks whether fake site records could make a drug with no real benefit look effective. Demo seed: 2026.</div></div></div></div>
    <div className="my-5 grid grid-cols-1 md:grid-cols-3 gap-3">{counts.map(([label,value],i)=><div key={String(label)} className="panel px-6 py-5 flex items-center gap-5">{i===0?<Database size={19} color="#9173ed"/>:i===1?<FlaskConical size={19} color="#9173ed"/>:<ShieldCheck size={19} color="#9173ed"/>}<div><div className="panel-heading">{String(label)}</div><div className="font-bold text-xl mt-2">{value===undefined?(i===2?'HbA1c / WK24':'N/A'):typeof value==='object'?JSON.stringify(value):String(value)}</div></div></div>)}</div>
    <RoleMatrix source={trial}/>
    <div className="flex flex-wrap items-center gap-3 mt-6">{!trialId?<button onClick={launch} disabled={busy} className="button-primary">{busy?'GENERATING TRIAL…':'CREATE SIMULATED TRIAL'} <ArrowRight size={16}/></button>:<button onClick={go} className="button-purple">START FAKE SITE TEST <ArrowRight size={16}/></button>}{trialId&&<span className="mono text-xs text-[#aaa5b0]">TRIAL ID / {trialId}</span>}</div>
    {busy&&<div className="mt-4"><Loading message="Creating a simulated trial and its five checks..."/></div>}{error!=null&&<div className="mt-4"><ErrorPanel error={error} retry={launch}/></div>}
    <DemoDisclaimer/>
  </div>
}
