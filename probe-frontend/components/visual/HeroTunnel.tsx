'use client';
import { useEffect, useRef } from 'react';
/** Layered animated streak geometry. Inspired by the supplied Lambda hero composition,
 *  drawn locally so the canvas works without the original external animation runtime. */
export function HeroTunnel(){
 const ref=useRef<HTMLCanvasElement>(null);
 useEffect(()=>{
  const canvas=ref.current;if(!canvas)return;const ctx=canvas.getContext('2d',{alpha:false});if(!ctx)return;
  let width=0,height=0,dpr=1,raf=0,frame=0,lastFrame=0;
  const prefersReduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  const shades=['#e9e3ff','#fbdfdd','#d5edff','#7268ee','#7bb5eb','#c8a5ff','#6d7bc9','#f3bcb5','#b3f4e1','#c6c7eb'];
  const fract=(x:number)=>x-Math.floor(x), hash=(x:number)=>fract(Math.sin(x*127.1+4.97)*43758.5453);
  const paths=Array.from({length:310},(_,i)=>({band:hash(i*2.1)*2-1,lane:hash(i*4.7)*2-1,phase:hash(i*3.5),speed:.35+hash(i*1.2)*2,width:.23+hash(i*7.7)*1.3,shade:Math.floor(hash(i*1.5)*shades.length),alpha:.1+hash(i*4.3)*.65}));
  const ro=new ResizeObserver(()=>{const box=canvas.getBoundingClientRect();width=box.width;height=box.height;dpr=Math.min(devicePixelRatio||1,1.8);canvas.width=Math.max(1,Math.floor(width*dpr));canvas.height=Math.max(1,Math.floor(height*dpr));ctx.setTransform(dpr,0,0,dpr,0,0)});ro.observe(canvas);
  const draw=(stamp=0)=>{
   if(!prefersReduced && stamp-lastFrame<32){raf=requestAnimationFrame(draw);return;}lastFrame=stamp;
   if(!width||!height){raf=requestAnimationFrame(draw);return}
   const w=width,h=height,t=frame*.00095,cy=h*.43;
   const bg=ctx.createLinearGradient(0,0,0,h);bg.addColorStop(0,'#11101a');bg.addColorStop(.42,'#181520');bg.addColorStop(.68,'#09090c');bg.addColorStop(1,'#080809');ctx.fillStyle=bg;ctx.fillRect(0,0,w,h);
   ctx.globalCompositeOperation='screen';
   // Multiple luminous ribs curve around a dark central tunnel, echoing the Lambda screenshot.
   for(let k=0;k<85;k++){
     const u=(k/84)*2-1, ay=Math.abs(u);
     const y=cy+(u>0?1:-1)*(22+ay*248)*(h/760);
     const wave=Math.sin(k*.78+t*1.4)*6;
     ctx.beginPath();ctx.moveTo(-75,y+30*ay+wave);
     ctx.bezierCurveTo(w*.2,y-63*u,w*.54,y+25*u,w+65,y-25*ay+wave);
     ctx.strokeStyle=shades[k%shades.length];ctx.lineWidth=k%16===0?2.6:.5;
     ctx.globalAlpha=(k%16===0?.41:.12)*(1-ay*.25);
     ctx.shadowBlur=k%16===0?18:0;ctx.shadowColor=shades[k%shades.length];ctx.stroke();
   }
   ctx.shadowBlur=0;
   for(const q of paths){
     const progress=fract(q.phase+t*q.speed*.4);const z=.12+Math.pow(progress,1.9)*2.25;
     const outside=q.band>0?1:-1, bend=outside*(.07+Math.abs(q.band)*.57);
     const xx=w*.5+q.lane*w*(.19+z*.57);
     const yy=cy+bend*h*(.12+z*.42);
     const len=1+z*z*16+q.speed*4;
     ctx.beginPath();ctx.moveTo(xx-len*1.7, yy+len*.13*bend);ctx.lineTo(xx+len*1.8,yy-len*.12*bend);
     ctx.strokeStyle=shades[q.shade];ctx.lineWidth=Math.min(3.8,q.width*(.5+z));ctx.globalAlpha=q.alpha*(.25+Math.min(.9,z*.49));ctx.stroke();
   }
   // Soft bright band behind title. Purple/teal for the clinical adaptation.
   const halo=ctx.createRadialGradient(w*.59,cy,w*.02,w*.57,cy,w*.46);
   halo.addColorStop(0,'#b9adff29');halo.addColorStop(.4,'#9486f310');halo.addColorStop(1,'#21193600');ctx.globalAlpha=.9;ctx.fillStyle=halo;ctx.fillRect(0,0,w,h);
   ctx.globalCompositeOperation='source-over';ctx.globalAlpha=1;
   const fade=ctx.createLinearGradient(0,0,0,h);fade.addColorStop(0,'#0b0b0b10');fade.addColorStop(.54,'#0b0b0b00');fade.addColorStop(.83,'#0b0b0bc9');fade.addColorStop(1,'#0b0b0b');ctx.fillStyle=fade;ctx.fillRect(0,0,w,h);
   frame++;if(!prefersReduced)raf=requestAnimationFrame(draw);
  };raf=requestAnimationFrame(draw);
  return()=>{cancelAnimationFrame(raf);ro.disconnect()}
 },[]);
 return <canvas ref={ref} aria-hidden="true" style={{position:'absolute',inset:0,width:'100%',height:'100%',pointerEvents:'none'}}/>;
}
