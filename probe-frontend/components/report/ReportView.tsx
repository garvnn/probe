'use client';
import { useCallback, useEffect, useState } from 'react';
import { Printer, ShieldAlert } from 'lucide-react';
import { api, type Schemas } from '@/lib/api';
import { useDemo } from '@/lib/demo-context';
import { contractOf } from '@/lib/adapters';
import { ContractPanel } from '@/components/shared/ContractPanel';
import { BreakingPointChart } from '@/components/harden/HardenView';
import { ErrorPanel, Loading, Caption } from '@/components/shared/Primitives';
import { copy, humanize } from '@/lib/copy';
import { isMock } from '@/lib/utils';
export function ReportView(){
  const {trialId,contract,setContract,markMock}=useDemo();const[report,setReport]=useState<Schemas['Report']|null>(null);const[busy,setBusy]=useState(false);const[error,setError]=useState<unknown>(null);
  const load=useCallback(async()=>{if(!trialId)return;setBusy(true);setError(null);try{const p=await api.getReport(trialId);markMock(p);setReport(p);setContract(contractOf(p.contract),isMock(p))}catch(e){setError(e)}finally{setBusy(false)}},[trialId,markMock,setContract]);
  useEffect(()=>{if(trialId)void load();/* eslint-disable-next-line react-hooks/exhaustive-deps */},[trialId]);
  return <div>{!trialId?<div className="panel p-8">Begin with Trial Setup to create a report.</div>:<>
    <div className="flex items-center justify-between gap-3 flex-wrap border-b border-[#3d3941] pb-5 mb-6"><div><div className="mono text-[#a88bf8] text-xs">TEST RESULTS / {trialId}</div><p className="text-[#a7a5a9] text-sm mt-2">Simulated clinical trial · Probe Report, organized by the Integrity Contract</p></div><button className="button-primary no-print" onClick={()=>window.print()} disabled={!report}><Printer size={16}/> PRINT / EXPORT PDF</button></div>
    {busy&&<Loading message="Loading trial test results..."/>}{error!=null&&<ErrorPanel error={error} retry={load}/>}
    {report&&<><div className="grid grid-cols-1 lg:grid-cols-[1.1fr_.9fr] gap-4"><ContractPanel contract={contract}/><div className="grid grid-cols-1 gap-3">{report.headlines.map(h=><div className="panel p-6" key={h.label}><div className="panel-heading">{h.label.toUpperCase()}</div><div className="text-[42px] font-bold tracking-[-.06em] mt-4">{h.before}<span className="text-[#9a7dff]"> → </span>{h.after}</div><Caption>Before → after Probe&apos;s fixes.</Caption></div>)}</div></div>
      <div className="mt-6"><BreakingPointChart before={report.breaking_point_v0} after={report.breaking_point_vN}/></div>
      <div className="mt-6 panel"><div className="flex items-center justify-between flex-wrap gap-4 p-6 border-b border-[#323037]"><h3 className="text-2xl font-bold tracking-[-.05em]">What we found</h3><span className="mono text-xs text-[#aaa5af]">PROPERTY / COUNTEREXAMPLE / STATUS</span></div>{contract.map(f=><div className="grid grid-cols-1 md:grid-cols-[.9fr_1.8fr_.6fr] gap-4 p-5 border-b border-[#323037]" key={f.name}><div className="font-bold">{humanize(f.name)}</div><div className="text-xs text-[#aaa6ad] leading-5">{f.counterexample||'No counterexample found'}{f.observed&&<span className="pill status-held ml-2">MEASURED</span>}</div><div className="mono text-xs">{copy.status[f.status.toLowerCase() as keyof typeof copy.status]}</div></div>)}</div>
      <div className="mt-6 panel p-6"><h3 className="text-2xl font-bold tracking-[-.05em] mb-4">What we changed and retested</h3>{report.fixes.length?<ul className="space-y-2">{report.fixes.map(f=><li key={f} className="text-sm text-[#c7c1cd] leading-6">↳ {f}</li>)}</ul>:<p className="text-sm text-[#a7a2ab]">No fixes in the returned report.</p>}</div>
      <div className="flex items-start gap-3 mt-6 mono text-[11px] leading-6 text-[#aaa3ae]"><ShieldAlert size={16} className="shrink-0 mt-1"/>This is a pre-launch stress test of a semi-synthetic trial. This report is not a regulatory approval or a fraud check for real trials. No patient records were changed.</div>
    </>}
  </>}</div>;
}
