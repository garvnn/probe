'use client';
import { useCallback, useEffect, useState } from 'react';
import { ArrowLeft, ArrowRight, Keyboard, RotateCcw } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useDemo, Step } from '@/lib/demo-context';
import { api } from '@/lib/api';
import { contractOf } from '@/lib/adapters';
import { copy } from '@/lib/copy';
import { ScreenShell } from './ScreenShell';
import { SetupView } from '@/components/setup/SetupView';
import { ForgerView } from '@/components/forger/ForgerView';
import { HardenView } from '@/components/harden/HardenView';
import { BlindView } from '@/components/blind/GuessWho';
import { ReportView } from '@/components/report/ReportView';
const routes=['/setup','/forger','/harden','/blind','/report'];
export function Stage({fixed}:{fixed?:Step}){
  const router=useRouter();
  const {step,setStep,trialId,setContract,markMock}=useDemo();const s=fixed===undefined?step:fixed;
  const [beat,setBeat]=useState(0);const [nonce,setNonce]=useState(0);
  // The report screen sets the contract from GET /report; refetching here would race it.
  useEffect(()=>{if(!trialId||s===4)return;api.getContract(trialId).then(v=>{markMock(v);setContract(contractOf(v))}).catch(()=>{});},[s,trialId,setContract,markMock]);
  const next=useCallback(()=>{if(s===3&&beat<2){window.dispatchEvent(new Event('probe:blind-next'));return}if(s<4){if(fixed===undefined)setStep((s+1) as Step);else router.push(routes[s+1]);setBeat(0)}},[s,beat,setStep,fixed,router]);
  const prev=useCallback(()=>{if(s===3&&beat>0){setBeat(v=>v-1);return}if(s>0){if(fixed===undefined)setStep((s-1) as Step);else router.push(routes[s-1]);setBeat(0)}},[s,beat,setStep,fixed,router]);
  useEffect(()=>{if(fixed!==undefined)return;const key=(e:KeyboardEvent)=>{
    const tag=(e.target as HTMLElement)?.tagName?.toLowerCase();if(['input','textarea','select'].includes(tag))return;
    if(e.key==='ArrowRight'||e.code==='Space'){e.preventDefault();next()}
    if(e.key==='ArrowLeft'){e.preventDefault();prev()}
    if(e.key.toLowerCase()==='r'){setNonce(n=>n+1)}
    if(e.key.toLowerCase()==='p'){window.dispatchEvent(new Event('probe:pause'))}
    if(e.key.toLowerCase()==='c'){window.dispatchEvent(new Event('probe:code'))}
    if(e.key==='Escape'){window.dispatchEvent(new Event('probe:close'))}
  };window.addEventListener('keydown',key);return()=>window.removeEventListener('keydown',key)},[fixed,next,prev]);
  return <main className="stage-head"><div className="stepper no-print">{copy.sections.map((label,i)=><button className={`step ${i===s?'current':i<s?'completed':''}`} key={label} onClick={()=>fixed===undefined?setStep(i as Step):router.push(routes[i])}><span className="step-num">0{i+1} / 05</span><span className="step-label">{label}</span></button>)}</div>
    <div key={`${s}-${nonce}`}><ScreenShell index={s}>{s===0?<SetupView next={next}/>:s===1?<ForgerView next={next}/>:s===2?<HardenView next={next}/>:s===3?<BlindView beat={beat} setBeat={setBeat} next={next}/>:<ReportView/>}</ScreenShell></div>
    <div className="stage-bottom no-print"><div className="flex items-center gap-2"><Keyboard size={15}/> <span>← / → NAVIGATE · SPACE NEXT · R RESTART · P PAUSE · C CODE · ESC CLOSE</span></div><div className="flex gap-2"><button className="button-secondary !min-h-[38px] !px-4" onClick={prev} disabled={s===0&&beat===0}><ArrowLeft size={15}/> BACK</button><button className="button-secondary !min-h-[38px] !px-4" onClick={()=>setNonce(n=>n+1)}><RotateCcw size={14}/></button><button className="button-primary !min-h-[38px] !px-4" onClick={next} disabled={s===4}>NEXT <ArrowRight size={15}/></button></div></div>
  </main>;
}
