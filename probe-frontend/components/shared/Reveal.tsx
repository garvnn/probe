'use client';
import { useEffect, useRef, useState } from 'react';
export function Reveal({children,className='',delay=0}:{children:React.ReactNode;className?:string;delay?:number}){
  const el=useRef<HTMLDivElement>(null);const [seen,setSeen]=useState(false);
  useEffect(()=>{const o=new IntersectionObserver(([v])=>{if(v.isIntersecting){setSeen(true);o.disconnect()}},{threshold:.09});if(el.current)o.observe(el.current);return()=>o.disconnect()},[]);
  return <div ref={el} className={`reveal ${seen?'visible':''} ${className}`} style={{transitionDelay:`${delay}ms`}}>{children}</div>;
}
