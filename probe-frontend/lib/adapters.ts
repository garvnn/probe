import { asObj, arr, pick, str } from './utils';
import type { ContractProperty } from './demo-context';
import { copy } from './copy';
/** Adapters only read received backend data. Missing values remain missing. */
export function contractOf(payload:unknown): ContractProperty[] {
  const source=Array.isArray(payload)?payload:arr(pick(payload,'contract','properties','items'));
  return source.map((v):ContractProperty=>{
    const o=asObj(v);const name=str(pick(o,'name','property','key')).replaceAll('_',' ');
    const raw=str(pick(o,'status','state'),'UNTESTED').toUpperCase();
    return {name:copy.properties.find(p=>p.toLowerCase()===name.toLowerCase())||name,status:raw==='HELD'?'HELD':raw==='BROKEN'?'BROKEN':'UNTESTED',counterexample:str(pick(o,'counterexample','evidence','detail'))};
  });
}
export function records(payload:unknown,...keys:string[]):unknown[]{
  if(Array.isArray(payload))return payload;
  for(const key of keys){const v=pick(payload,key);if(Array.isArray(v))return v;}
  return [];
}
export function idOf(data:unknown,...keys:string[]):string {return str(pick(data,...keys));}
export function numericEntries(data:unknown):{name:string,value:number}[]{return Object.entries(asObj(data)).filter(([,v])=>typeof v==='number').map(([name,value])=>({name,value:value as number}));}
