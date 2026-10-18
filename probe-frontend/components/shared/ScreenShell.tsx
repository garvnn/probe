'use client';
import React from 'react';
import { useDemo } from '@/lib/demo-context';
import { copy } from '@/lib/copy';
import { ContractPanel } from './ContractPanel';
import { MockBadge } from './Primitives';
export function ScreenShell({index,children,aside=true}:{index:number;children:React.ReactNode;aside?:boolean}){
  const {contract}=useDemo();return <div className="screen stage-grid">
    <section className="stage-main"><div className="screen-kicker"><span style={{color:'#9372ff'}}>0{index+1}/</span><span>PROBE / {copy.shortSections[index]}</span></div>
      <h1 className="screen-title">{['Set up the\nsimulated trial.','Can fake site\nrecords pass?','Did monitoring\nimprove?','Can staff guess\nwho got the drug?','Your clinical trial\ntest results.'][index].split('\n').map((line,i)=><React.Fragment key={i}>{i>0&&<br/>}{line}</React.Fragment>)}</h1>
      <p className="screen-description">{copy.sectionNotes[index]}</p>{children}</section>
    {aside&&<aside className="stage-side"><div style={{position:'sticky',top:101}}><ContractPanel contract={contract} small/><div className="panel p-5 mt-4"><div className="panel-heading mb-3">// ABOUT THIS TEST</div><p className="text-xs text-[#a4a1a6] leading-6">{copy.warning}</p></div></div></aside>}
    <MockBadge/>
  </div>;
}
