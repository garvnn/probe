'use client';
import { motion } from 'framer-motion';
import { copy } from '@/lib/copy';
import { ContractProperty, useDemo } from '@/lib/demo-context';
export function ContractPanel({contract,small=false}:{contract:ContractProperty[];small?:boolean}){
  const {contractIsMock}=useDemo();const anyMock=contractIsMock&&contract.some(c=>!c.observed);
  return <div className="panel" style={{padding:small?19:30}}>
    <div className="flex items-center justify-between gap-3 pb-3"><span className="panel-heading">// FIVE THINGS WE CHECK</span><span className="mono text-xs text-[#8471c5]">{anyMock?<span title="Unmeasured rows come from a mock fixture" style={{color:'#d6ff48'}}>SAMPLE · </span>:null}05 / CHECKS</span></div>
    {copy.properties.map((name,i)=>{
      const found=contract.find(v=>v.name.toLowerCase().replaceAll('_',' ')===name.toLowerCase());
      const status=found?.status||'UNTESTED';
      return <motion.div layout key={name} className="property-row" initial={{opacity:0,y:10}} animate={{opacity:1,y:0}} transition={{delay:i*.055}}>
        <div style={{minWidth:0}}><div className="flex items-center gap-3"><span className="mono text-xs text-[#77747c]">0{i+1}</span><span className="name" style={{fontSize:small?12:undefined}}>{name}</span></div>{!small&&status==='BROKEN'&&found?.counterexample&&<p className="detail">↳ {found.counterexample}</p>}{found?.observed&&<span className="mono" style={{fontSize:9,color:'#a3f0cc'}}>MEASURED</span>}</div>
        <span className={`pill status-${status.toLowerCase()}`} style={{fontSize:small?9:undefined}}><span className="dot"/>{copy.status[status.toLowerCase() as keyof typeof copy.status] || status}</span>
      </motion.div>
    })}
  </div>;
}
