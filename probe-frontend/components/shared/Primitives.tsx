'use client';
import React from 'react';
import { AlertTriangle, RefreshCw, LoaderCircle } from 'lucide-react';
import { ApiError } from '@/lib/api';
import { useDemo } from '@/lib/demo-context';
import { copy } from '@/lib/copy';
export function MockBadge(){const {isMock}=useDemo();if(!isMock)return null;return <div className="no-print" style={{position:'fixed',bottom:17,right:18,zIndex:79,background:'#d6ff48',color:'#09090b',font:'bold 15px ui-monospace,monospace',padding:'12px 18px',boxShadow:'0 0 0 3px #09090b'}}>● SAMPLE DATA: NOT A LIVE RESULT</div>}
export function Loading({message='Loading the test...'}:{message?:string}){return <div className="panel flex items-center gap-4 p-7 text-sm text-[#b7b6b6]" role="status"><LoaderCircle size={20} className="animate-spin text-[#a48cff]"/>{message}</div>}
export function ErrorPanel({error,retry}:{error:unknown;retry?:()=>void}){const e=error instanceof ApiError?error:null;return <div className="panel p-6" role="alert" style={{borderColor:'#6e373c'}}><div className="flex items-start gap-3"><AlertTriangle className="text-[#ff777b] shrink-0" size={19}/><div><b style={{fontSize:16}}>{e?.status===501?'Not built yet':e?.status===0?'Backend unavailable':'Unable to load this stage'}</b><p className="text-sm text-[#a9a7aa] mt-2 leading-6">{e?.message || (error instanceof Error?error.message:String(error))}</p>{e?.owner&&<p className="mono text-xs mt-2">OWNER: {e.owner}</p>}{retry&&<button className="button-secondary mt-5" onClick={retry}><RefreshCw size={14}/> RETRY</button>}</div></div></div>}
export function StatNumber({value,caption,accent}:{value:string;caption:string;accent?:string}){return <div><div className="big-stat" style={{color:accent}}>{value}</div><div className="stat-caption">{caption}</div></div>}
export function Caption({children}:{children:React.ReactNode}){return <p style={{font:'12px/1.65 ui-monospace,monospace',color:'#aaa7ad',marginTop:16,maxWidth:650}}>{children}</p>}
export function SectionLabel({children}:{children:React.ReactNode}){return <div className="panel-heading mb-4">// {children}</div>}
export function DemoDisclaimer(){return <div className="mono micro" style={{color:'#96929b',marginTop:16}}>{copy.warning}</div>}
