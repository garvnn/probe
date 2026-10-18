import { asObj, arr, str } from '@/lib/utils';
import { humanize } from '@/lib/copy';
export function RoleMatrix({source}:{source:unknown}){
  const data=asObj(source);
  const matrix=asObj(data.role_matrix || data.visibility_matrix || data.permissions);
  const roleRows=Object.entries(matrix).map(([role,fields])=>({role,fields:asObj(fields)}));
  const columns=Array.from(new Set(roleRows.flatMap(r=>Object.keys(r.fields))));
  if(!roleRows.length||!columns.length)return <div className="panel p-7"><div className="panel-heading">// ACCESS BOUNDARY</div><p className="text-[#a09da4] text-sm mt-5">Role visibility will appear when the trial endpoint supplies its role matrix. No field access is assumed.</p></div>;
  return <div className="panel p-5 overflow-auto"><div className="panel-heading mb-5">// WHO SEES WHAT</div><table className="w-full text-left" style={{minWidth:500}}><thead><tr><th className="mono text-xs text-[#8f8d93] font-normal pb-4">ROLE</th>{columns.map(c=><th key={c} className="mono text-[10px] text-[#9b96a3] font-normal pb-4 px-3">{humanize(c)}</th>)}</tr></thead><tbody>{roleRows.map(({role,fields})=><tr key={role} style={{background:role.toLowerCase().includes('coordinator')?'#231a3b':''}}><td className="p-3 text-sm font-bold">{humanize(role)}</td>{columns.map(c=><td className="p-3 mono text-xs" key={c} style={{color:fields[c]===true?'#a2f5c6':'#8d8594'}}>{fields[c]===true?'VISIBLE':fields[c]===false?'HIDDEN':str(fields[c],'N/A')}</td>)}</tr>)}</tbody></table></div>
}
