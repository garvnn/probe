'use client';
import Link from 'next/link';
import Image from 'next/image';
import { useEffect, useState } from 'react';
import { usePathname } from 'next/navigation';
import { ArrowUpRight, Menu, X, ChevronDown } from 'lucide-react';
const menu=[
 {group:'TRIAL AND DEMO',items:[['Trial Setup','/setup'],['Five Trial Checks','/setup'],['Live Demo','/demo']]},
 {group:'CHECK FOR RISKS',items:[['Fake Site Test','/forger'],['Treatment Privacy Test','/blind']]},
 {group:'RESULTS AND REVIEW',items:[['Monitoring Recheck','/harden'],['Results Report','/report']]},
 {group:'CLINICAL CONTEXT',items:[['How Probe Works','/#how-it-works'],['Safety and Privacy','/#how-it-works']]}
] as const;
export function SiteNav(){const path=usePathname();const [expanded,setExpanded]=useState(false);const [mobile,setMobile]=useState(false);
 useEffect(()=>{setExpanded(false);setMobile(false)},[path]);useEffect(()=>{const listener=(e:KeyboardEvent)=>{if(e.key==='Escape'){setExpanded(false);setMobile(false)}};window.addEventListener('keydown',listener);return()=>window.removeEventListener('keydown',listener)},[]);
 return <header className="siteHeader no-print" onMouseLeave={()=>setExpanded(false)}><div className="container"><div className="headerContentWrapper">
  <div className="headerLogoWrapper"><Link href="/" aria-label="Probe homepage" className="headerLogo"><Image src="/probe-logo.png" alt="Probe" width={194} height={51} priority className="probe-logo-img" /></Link></div>
  <nav className="mainNav" aria-label="Primary"><ul><li><Link href="/demo">LIVE DEMO</Link></li><li className="hasDropdown" onMouseEnter={()=>setExpanded(true)}><button type="button" className={`noLink ${expanded?'nav-active':''}`} aria-expanded={expanded} aria-controls="probe-dropdown" onClick={()=>setExpanded(v=>!v)}>PRODUCT <ChevronDown size={13}/></button></li><li><Link href="/forger">FAKE SITE TEST</Link></li><li><Link href="/blind">TREATMENT PRIVACY</Link></li><li><Link href="/report">RESULTS</Link></li></ul></nav>
  <div className="utilityNav"><Link href="/setup" className="nav-create">SETUP</Link><Link href="/demo" className="nav-launch">LAUNCH DEMO <ArrowUpRight size={16}/></Link></div>
  <button className="mobileMenuToggle" type="button" aria-expanded={mobile} aria-label="Toggle menu" onClick={()=>setMobile(v=>!v)}>{mobile?<X size={27}/>:<Menu size={27}/>}</button>
 </div></div>
 <div id="probe-dropdown" className={`probe-mega ${expanded?'probe-mega-open':''}`} onMouseEnter={()=>setExpanded(true)}><div className="dropdownContent"><div className="dropdownColumns">{menu.map((m,i)=><div className="probe-dropdown-column" key={m.group}><span className="dropdownColumnHeading">//{m.group}</span><ul className="dropdownLinks">{m.items.map(([text,to])=><li key={text}><Link href={to} onClick={()=>setExpanded(false)}>{text}</Link></li>)}</ul>{i===0&&<Link className="probe-dropdown-footer" href="/demo">RUN ALL FIVE STAGES ↗</Link>}</div>)}</div></div></div>
 {mobile&&<nav aria-label="Mobile navigation" className="mobileMenu"><Link href="/demo">LIVE DEMO</Link><Link href="/setup">TRIAL SETUP</Link><Link href="/forger">FAKE SITE TEST</Link><Link href="/harden">CHECK MONITORING</Link><Link href="/blind">TREATMENT PRIVACY</Link><Link href="/report">RESULTS</Link></nav>}
 </header>
}
