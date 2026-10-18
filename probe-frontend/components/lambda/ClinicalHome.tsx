'use client';
import Link from 'next/link';
import { useState } from 'react';
import { ArrowUpRight, ArrowRight, MoveRight } from 'lucide-react';
import { HeroTunnel } from '@/components/visual/HeroTunnel';
import { ScrollEffects } from '@/components/shared/ScrollEffects';
import { Reveal } from '@/components/shared/Reveal';
import { CapsuleObject, PharmacologyNetwork, PatientCardsIllustration, SignalIllustration, StudyProtocol, TrialJourney, TrialDossier, ReportIllustration } from './ClinicalVisuals';

const explanations=[
 {title:'Set up a simulated drug study.',description:'Choose the study scenario. Probe creates sample sites and patient records for a fictional diabetes drug. No real trial patient records are used.',label:'01',href:'/setup'},
 {title:'Test whether fake site records are caught.',description:'Probe generates made-up records for an entire trial site and runs them through the fraud-monitoring checks. It measures which fake records get through.',label:'02',href:'/forger'},
 {title:'Test the updated checks on new sites.',description:'Probe adds a monitoring check and tests it on different simulated sites. It also checks that genuine sites are not flagged more often.',label:'03',href:'/harden'},
 {title:'Check if staff can identify the drug group.',description:'Probe checks whether appointment, pharmacy and side-effect records reveal who received the study drug or placebo, while preserving safety access.',label:'04',href:'/blind'}
];
const showcases=[
 {n:'01',label:'FAKE SITE RECORDS',title:'Catch made-up study sites.',description:'See whether a complete fake site can slip through clinical trial fraud checks.',detail:'Probe creates sample site records, runs the checks, and shows exactly which checks flag them.',href:'/forger',visual:<CapsuleObject/>},
 {n:'02',label:'VERIFY THE CHANGE',title:'Prove the new checks work.',description:'Compare original and updated fraud monitoring on new simulated sites.',detail:'A new test set shows whether the checks improve without wrongly flagging genuine sites.',href:'/harden',visual:<SignalIllustration/>},
 {n:'03',label:'DRUG VS PLACEBO',title:'Test treatment privacy.',description:'See whether everyday patient records reveal who received the drug.',detail:'Try guessing six patient cards yourself, then compare your answers with Probe.',href:'/blind',visual:<PatientCardsIllustration/>}
];
const demoSteps=[
 {n:'01',label:'SET UP A STUDY',title:'Create the sample trial',description:'Start with a fictional diabetes drug and a simulated set of patients.',href:'/setup',visual:<StudyProtocol/>},
 {n:'02',label:'TEST FOR FAKE SITES',title:'Find records that slip through',description:'Run simulated fake site records through fraud monitoring.',href:'/forger',visual:<CapsuleObject/>},
 {n:'03',label:'VERIFY IMPROVEMENTS',title:'Check the monitoring again',description:'Test the improved checks on sites not used during development.',href:'/harden',visual:<SignalIllustration/>},
 {n:'04',label:'DRUG OR PLACEBO',title:'Try the patient guessing game',description:'See whether treatment assignments leak through everyday records.',href:'/blind',visual:<PatientCardsIllustration/>},
 {n:'05',label:'READ THE RESULTS',title:'Review what Probe found',description:'See which trial checks failed, the impact, and the tested changes.',href:'/report',visual:<ReportIllustration/>}
];

export function ClinicalHome(){
 const [open,setOpen]=useState(0);
 const [active,setActive]=useState(0);
 return <main className="lambda-home probe-home-v4 probe-home-v5 probe-home-v6" id="main-content">
  <ScrollEffects/>
  <section className="pt-xl pb-xl _homeHeroWithCards_oc92w_1 module-comp lambda-hero" id="section-home-hero">
   <div className="_wrapper_oc92w_19"><div className="_backgroundAnimation_15jea_2 hero-bg _heroBg_oc92w_50"><HeroTunnel/></div></div><div className="lambda-hero-glow"/>
   <div className="probe-hero-identity" aria-label="Probe clinical trial testing platform"><span className="probe-hero-company">Probe<span className="probe-hero-company-dot">.</span></span><span className="probe-hero-ident-line"/><span className="probe-hero-category">PRE-ENROLLMENT CLINICAL TRIAL TESTING</span></div>
   <h1 className="h1-large _heroTitle_oc92w_137">Find problems in clinical trials<br/> before they start<span className="lambda-dot">.</span></h1>
   <div className="container _titleContainer_oc92w_97"><p className="lambda-hero-summary">Probe checks whether fake site records can pass fraud monitoring, whether staff can tell who received the drug, and whether updated checks actually work.</p>
    <div className="buttonGroup _buttonGroup_oc92w_102" data-align="center"><Link className="button" href="/demo">TRY THE FIVE-STEP DEMO <ArrowUpRight size={17}/></Link><Link className="button button--secondary" href="#how-it-works">SEE HOW PROBE WORKS <ArrowRight size={17}/></Link></div>
   </div>
   <div className="probe-hero-study-line" data-scroll="rise"><span className="probe-hero-study-symbol" aria-hidden="true"><i/></span><span>SIMULATED DEMO <b>PRB-101</b></span><span className="probe-hero-study-separator"/><span>TYPE 2 DIABETES</span><span className="probe-hero-study-separator"/><span>DRUG / PLACEBO</span></div>
   <div className="container lambda-hero-cards-container"><div className="_heroCards_1d0dg_1">
    <Link href="/forger" className="_heroCard_1d0dg_1" data-scroll="rise" data-stagger="0"><div className="_cardNumber_1d0dg_85">01/</div><div className="_content_1d0dg_102"><h2 className="h6">Check for fake<br/>trial sites.</h2><p className="_cardCopy_1d0dg_74">Find records that pass fraud monitoring.</p></div><span className="_button_1d0dg_73">↗</span></Link>
    <Link href="/harden" className="_heroCard_1d0dg_1" data-scroll="rise" data-stagger="1"><div className="_cardNumber_1d0dg_85">02/</div><div className="_content_1d0dg_102"><h2 className="h6">Test whether<br/>the checks improve.</h2><p className="_cardCopy_1d0dg_74">Verify changes on separate simulated sites.</p></div><span className="_button_1d0dg_73">↗</span></Link>
    <Link href="/blind" className="_heroCard_1d0dg_1" data-scroll="rise" data-stagger="2"><div className="_cardNumber_1d0dg_85">03/</div><div className="_content_1d0dg_102"><h2 className="h6">Protect drug<br/>and placebo privacy.</h2><p className="_cardCopy_1d0dg_74">Check what routine patient records reveal.</p></div><span className="_button_1d0dg_73">↗</span></Link>
   </div></div>
  </section>

  <section className="probe-dossier-section" aria-label="Documented clinical trial data integrity case study"><div className="container"><div data-scroll="rise"><TrialDossier/></div></div></section>

  <section id="how-it-works" className="pt-xl pb-xl module-comp lambda-accordion-section"><div className="container"><Reveal><div className="probe-section-top"><span className="probe-section-index">01 / WHAT HAPPENS</span><h2 className="h2">A complete trial check.<br/>Four simple steps.</h2><p>Probe runs on a simulated drug study, so teams can spot problems before people participate.</p></div></Reveal>
   <div className="lambda-accordion-layout"><div className="accordion">
    {explanations.map((r,i)=><div data-scroll="rise" data-stagger={i} className={`accordionItem ${open===i?'is-open':''}`} key={r.label}><div className="accordionItemNumberColumn"><span>{r.label}<span className="lambda-purple">/</span></span></div><div className="accordionItemContentColumn"><h3 className="accordionItemHeader"><button type="button" className="accordionItemHeaderButton" aria-expanded={open===i} onClick={()=>setOpen(open===i?-1:i)}><span className="accordionItemTitle">{r.title}</span><span className="accordionToggle">{open===i?'−':'+'}</span></button></h3><div className={`accordionItemContent ${open===i?'accordionItemContentOpen':''}`}><div className="accordionItemRich">{r.description}<Link href={r.href}>OPEN THIS STEP <ArrowUpRight size={14}/></Link></div></div></div></div>)}
   </div><div className="lambda-accordion-illustration" data-scroll="from-right"><StudyProtocol/></div></div>
   <div className="probe-journey-wrap" data-scroll="rise"><TrialJourney/></div>
  </div></section>

  <section className="pt-xl pb-xl module-comp lambda-products-section" id="tests"><div className="container"><Reveal><div className="probe-section-top"><span className="probe-section-index">02 / WHAT PROBE TESTS</span><h2 className="h2">Know exactly where<br/>a drug study is vulnerable.</h2><p>Three tests. Each one answers a specific question about clinical trial records.</p></div></Reveal>
   <div className="probe-showcase-list">{showcases.map((s,i)=><Reveal key={s.n} delay={i*75}><Link href={s.href} className={`probe-showcase ${i===1?'reverse':''}`}><div className="probe-showcase-copy"><span className="probe-showcase-number">{s.n} / {s.label}</span><h3>{s.title}</h3><p className="probe-showcase-lead">{s.description}</p><p className="probe-showcase-detail">{s.detail}</p><span className="probe-showcase-link">VIEW THIS TEST <ArrowUpRight size={18}/></span></div><div className="probe-showcase-visual" data-scroll="from-right">{s.visual}</div></Link></Reveal>)}</div>
  </div></section>

  <section className="pt-xl pb-xl module-comp lambda-security-section" id="safety"><div className="container"><div className="lambda-security-grid"><div className="lambda-security-copy"><Reveal><span className="lambda-section-label">03 / PATIENT SAFETY</span><h2 className="h2">Keep safety information visible. Keep drug groups private.</h2><div className="richtext"><p>Doctors must still see side effects and other safety reports. Probe checks whether ordinary site records reveal who received the drug, without hiding safety information or editing patient records.</p></div><Link className="button" href="/blind">TRY THE PATIENT CARDS <ArrowUpRight size={16}/></Link></Reveal></div><div className="lambda-security-art" data-scroll="from-right"><PharmacologyNetwork/></div></div></div></section>

  <section className="pt-xl pb-xl module-comp lambda-engines-section" id="demo-steps"><div className="container"><Reveal><div className="probe-section-top"><span className="probe-section-index">04 / INTERACTIVE DEMO</span><h2 className="h2">See every step<br/>of the clinical trial test.</h2><p>Pick a step to see what you will do. The full demo walks through all five.</p></div></Reveal>
   <div className="probe-demo-explorer"><div className="probe-demo-step-list" role="group" aria-label="Choose a demo step">{demoSteps.map((step,i)=><button key={step.n} data-scroll="rise" data-stagger={i} type="button" className={`probe-demo-step ${active===i?'selected':''}`} onClick={()=>setActive(i)} aria-pressed={active===i}><span className="probe-demo-step-num">{step.n}/</span><span className="probe-demo-step-name">{step.title}</span><span className="probe-demo-step-arrow">{active===i?'−':'+'}</span></button>)}</div><div className="probe-demo-active" data-scroll="from-right" aria-live="polite"><div className="probe-demo-active-heading"><span>{demoSteps[active].label}</span><strong>{demoSteps[active].title}</strong><p>{demoSteps[active].description}</p></div><div className="probe-demo-active-visual" key={active}>{demoSteps[active].visual}</div><Link className="probe-demo-open" href={demoSteps[active].href}>OPEN THIS SCREEN <ArrowUpRight size={17}/></Link></div></div>
  </div></section>

  <section className="pt-xl pb-xl module-comp _section_dn24w_1 lambda-last-section"><div className="container"><div className="lambda-final-grid" data-scroll="rise"><div><span className="lambda-final-kicker">PROBE / SIMULATED DRUG STUDIES</span><h2 className="h2">Test the study.<br/>Protect the results.</h2></div><div className="lambda-final-actions"><p>Run the five-step demo to see what Probe finds and how it verifies each change.</p><div className="buttonGroup"><Link href="/demo" className="button button--secondary">OPEN THE FULL DEMO <MoveRight size={16}/></Link><Link href="/report" className="button">VIEW THE REPORT <ArrowUpRight size={16}/></Link></div></div></div><div className="lambda-final-foot"><span>PROBE / CLINICAL TRIAL TESTING</span><span>SIMULATED DATA ONLY</span><Link href="#main-content">BACK TO TOP ↑</Link></div></div></section>
 </main>;
}
