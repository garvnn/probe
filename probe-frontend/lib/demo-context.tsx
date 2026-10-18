'use client';
import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';

export type Scenario = 'A' | 'B';
export type Step = 0 | 1 | 2 | 3 | 4;
export type ContractProperty = { name: string; status: 'UNTESTED' | 'HELD' | 'BROKEN'; counterexample?: string };
/** `damage` of the latest escaped fake-data round (RoundEvent.damage); shown again on the Patch screen. */
export type RoundDamage = { effect_real: number; effect_with_fake: number; p_with_fake: number };
export type DemoState = {
  trialId: string | null; scenario: Scenario; step: Step; fakeDataRunId: string | null;
  suiteVersion: number; damage: RoundDamage | null; contract: ContractProperty[]; isMock: boolean;
};
type DemoContextType = DemoState & {
  setTrialId: (v: string | null) => void; setScenario: (v: Scenario) => void;
  setStep: (v: Step) => void; setFakeDataRunId: (v: string | null) => void;
  setSuiteVersion: (v: number) => void; setDamage: (v: RoundDamage | null) => void; setContract: (v: ContractProperty[]) => void;
  markMock: (payload: unknown) => void; restart: () => void;
};
const initial: DemoState = { trialId: null, scenario: 'B', step: 0, fakeDataRunId: null, suiteVersion: 0, damage: null, contract: [], isMock: false };
const Ctx = createContext<DemoContextType | null>(null);
export function DemoProvider({ children }: { children: React.ReactNode }) {
  const [s, setS] = useState<DemoState>(initial);
  const set = useCallback(<K extends keyof DemoState>(key: K, val: DemoState[K]) => setS(prev => ({ ...prev, [key]: val })), []);
  const setTrialId = useCallback((v:string|null)=>set('trialId',v),[set]);
  const setScenario = useCallback((v:Scenario)=>set('scenario',v),[set]);
  const setStep = useCallback((v:Step)=>set('step',v),[set]);
  const setFakeDataRunId = useCallback((v:string|null)=>set('fakeDataRunId',v),[set]);
  const setSuiteVersion = useCallback((v:number)=>set('suiteVersion',v),[set]);
  const setDamage = useCallback((v:RoundDamage|null)=>set('damage',v),[set]);
  const setContract = useCallback((v:ContractProperty[])=>set('contract',v),[set]);
  const markMock = useCallback((payload:unknown)=>{
    if (payload && typeof payload === 'object' && '_mock' in payload && payload._mock === true) set('isMock',true);
  },[set]);
  const restart = useCallback(()=>setS(initial),[]);
  const value = useMemo<DemoContextType>(() => ({...s,setTrialId,setScenario,setStep,setFakeDataRunId,setSuiteVersion,setDamage,setContract,markMock,restart}),
  [s,setTrialId,setScenario,setStep,setFakeDataRunId,setSuiteVersion,setDamage,setContract,markMock,restart]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
export function useDemo() { const x = useContext(Ctx); if (!x) throw new Error('DemoProvider missing'); return x; }
