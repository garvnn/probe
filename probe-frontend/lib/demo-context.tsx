'use client';
import React, { createContext, useCallback, useContext, useLayoutEffect, useMemo, useRef, useState } from 'react';

export type Scenario = 'A' | 'B';
export type Step = 0 | 1 | 2 | 3 | 4;
/** `observed`: set by the frontend from a measured (non-mock) result, e.g. a real Impostor escape. */
export type ContractProperty = { name: string; status: 'UNTESTED' | 'HELD' | 'BROKEN'; counterexample?: string; observed?: boolean };
/** `damage` of the latest escaped fake-data round (RoundEvent.damage); shown again on the Patch screen. */
export type RoundDamage = { effect_real: number; effect_with_fake: number; p_with_fake: number; p_real?: number | null; runId: string; isMock: boolean };
export type DemoState = {
  trialId: string | null; scenario: Scenario; step: Step; fakeDataRunId: string | null;
  suiteVersion: number; damage: RoundDamage | null; contract: ContractProperty[]; contractIsMock: boolean;
  observed: ContractProperty[]; isMock: boolean;
};
type DemoContextType = Omit<DemoState, 'observed'> & {
  setTrialId: (v: string | null) => void; setScenario: (v: Scenario) => void;
  setStep: (v: Step) => void; setFakeDataRunId: (v: string | null) => void;
  setSuiteVersion: (v: number) => void; setDamage: (v: RoundDamage | null) => void;
  setContract: (v: ContractProperty[], isMock?: boolean) => void; observe: (p: ContractProperty) => void;
  markMock: (payload: unknown) => void; resetMock: () => void; restart: () => void;
};
const initial: DemoState = { trialId: null, scenario: 'B', step: 0, fakeDataRunId: null, suiteVersion: 0, damage: null, contract: [], contractIsMock: false, observed: [], isMock: false };
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
  const setContract = useCallback((v:ContractProperty[],isMock=false)=>setS(prev=>({...prev,contract:v,contractIsMock:isMock})),[]);
  const observe = useCallback((p:ContractProperty)=>setS(prev=>({...prev,observed:[...prev.observed.filter(o=>o.name!==p.name),{...p,observed:true}]})),[]);
  // The MOCK badge is per screen: ScreenShell resets it on mount, and each screen marks its own payloads.
  const markMock = useCallback((payload:unknown)=>{
    if (payload && typeof payload === 'object' && '_mock' in payload && payload._mock === true) set('isMock',true);
  },[set]);
  const resetMock = useCallback(()=>set('isMock',false),[set]);
  const restart = useCallback(()=>setS(initial),[]);
  // Observed properties come from measured runs and win over a fetched (possibly mock) contract.
  const contract = useMemo(()=>{
    const merged = s.contract.map(c=>s.observed.find(o=>o.name===c.name)??c);
    return [...merged, ...s.observed.filter(o=>!merged.some(c=>c.name===o.name))];
  },[s.contract,s.observed]);
  const value = useMemo<DemoContextType>(() => ({...s,contract,setTrialId,setScenario,setStep,setFakeDataRunId,setSuiteVersion,setDamage,setContract,observe,markMock,resetMock,restart}),
  [s,contract,setTrialId,setScenario,setStep,setFakeDataRunId,setSuiteVersion,setDamage,setContract,observe,markMock,resetMock,restart]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
export function useDemo() { const x = useContext(Ctx); if (!x) throw new Error('DemoProvider missing'); return x; }
/**
 * One screen's MOCK-badge scope. Clears the badge on mount (layout effect, before children fetch) and drops
 * markMock calls after unmount, so a slow response from the screen you just left can't badge this one.
 */
export function MockScope({ children }: { children: React.ReactNode }) {
  const parent = useDemo(); const { markMock: mark, resetMock } = parent; const alive = useRef(true);
  useLayoutEffect(() => { alive.current = true; resetMock(); return () => { alive.current = false; }; }, [resetMock]);
  const markMock = useCallback((payload: unknown) => { if (alive.current) mark(payload); }, [mark]);
  const value = useMemo(() => ({ ...parent, markMock }), [parent, markMock]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
