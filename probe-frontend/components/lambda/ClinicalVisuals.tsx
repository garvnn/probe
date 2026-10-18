/** Clinical-study illustrations. All graphics show structure, never invented patient values or test results. */

/** Historical example only. The app demo remains a separate simulated PRB-101 trial. */
export function TrialDossier(){return <div className="probe-dossier probe-dossier-history" aria-label="Historical clinical-trial case study: the retracted KYOTO HEART Study">
 <div className="probe-dossier-header"><span className="probe-dossier-seal" aria-hidden="true">+</span><span className="probe-dossier-eyebrow">CLINICAL TRIAL CASE STUDY / JAPAN</span><span className="probe-dossier-stamp">REAL STUDY · 2009 PAPER</span></div>
 <div className="probe-dossier-body">
  <div className="probe-dossier-intro"><span className="probe-dossier-code">KYOTO HEART STUDY / VALSARTAN</span>
   <h2>What happens when trial data cannot be trusted?</h2>
   <p>The KYOTO HEART Study tested the blood-pressure drug valsartan. Its published findings were retracted in 2013 after the journal identified serious problems with the reported data.</p>
   <div className="probe-dossier-badges"><span><i className="clinical-plus" aria-hidden="true">+</i> High blood pressure</span><span><i className="probe-capsule-mini" aria-hidden="true"/> Valsartan study</span></div>
   <div className="probe-case-why"><strong>Why this matters for Probe</strong><p>Drug studies need reliable records and conclusions. Probe tests those risks before enrollment, using simulated trials.</p></div>
  </div>
  <div className="probe-dossier-details">
   <div className="probe-dossier-row"><span>01 / TREATMENT</span><strong>Valsartan + usual care</strong><small>Compared with usual care without valsartan</small></div>
   <div className="probe-dossier-row"><span>02 / PARTICIPANTS</span><strong>3,031 patients</strong><small>People with uncontrolled high blood pressure and elevated cardiovascular risk</small></div>
   <div className="probe-dossier-row"><span>03 / PRIMARY OUTCOME</span><strong>Heart and stroke events</strong><small>Cardiovascular events, including fatal and nonfatal outcomes</small></div>
   <div className="probe-dossier-row"><span>04 / WHAT HAPPENED</span><strong>Retracted in 2013</strong><small>The journal reported critical problems with the study data</small></div>
  </div>
 </div>
 <div className="probe-dossier-footer"><span><i aria-hidden="true" className="clinical-plus">+</i> Historical context only. Probe did not analyze these trial records. The interactive demo uses a separate fictional study.</span><span className="probe-dossier-links"><a href="https://pubmed.ncbi.nlm.nih.gov/19723695/" target="_blank" rel="noopener noreferrer">ORIGINAL STUDY ↗</a><a href="https://academic.oup.com/eurheartj/article/34/14/1023/473163" target="_blank" rel="noopener noreferrer">RETRACTION ↗</a></span></div>
 </div>}

const protocolChecks = [
 ['01','Fake study sites','Can made-up site records pass as genuine?'],
 ['02','Drug or placebo privacy','Can staff work out which treatment patients received?'],
 ['03','Study results','Could fake records change the drug’s reported effect?'],
 ['04','Patient safety','Do investigators still receive safety reports?'],
 ['05','Site operations','Can staff still complete essential trial tasks?']
];

export function StudyProtocol(){return <div className="study-board" aria-label="Illustration of a simulated drug trial protocol">
 <div className="study-board-top"><span className="study-tag">SIMULATED STUDY</span><span className="study-code">PROTOCOL / PRB-101</span></div>
 <div className="study-board-title"><div className="study-pill" aria-hidden="true"><i/><i/></div><div><span className="study-tiny">TYPE 2 DIABETES</span><strong>One drug. Two study groups.</strong><p>Tested before a single patient enrolls.</p></div></div>
 <div className="study-two-arms"><div><span>GROUP A</span><strong>Study drug</strong><small>PRB-101</small></div><div><span>GROUP B</span><strong>Placebo</strong><small>Inactive comparison</small></div></div>
 <div className="study-board-bottom"><span>MEASURED IN THE SIMULATION</span><strong>Change in blood sugar (HbA1c) at week 24</strong></div>
 </div>}

export function ClinicalLayerStack(){return <div className="probe-checklist" aria-label="Five questions Probe checks in a simulated clinical study">
 <div className="probe-checklist-head"><span className="study-tag">THE FIVE STUDY CHECKS</span><span>BEFORE ENROLLMENT</span></div>
 {protocolChecks.map(([n,title,description])=><div className="probe-check" key={n}><span className="probe-check-index">{n}</span><div><strong>{title}</strong><p>{description}</p></div><span className="probe-check-status">TO TEST</span></div>)}
 <p className="probe-checklist-footer">Results appear only after the simulation runs.</p>
 </div>}

export function CapsuleObject({small=false}:{small?:boolean}){return <div className={`study-record-check clinical-paper ${small?'is-small':''}`} aria-label="Example trial site record fields compared with a fraud-monitoring checklist">
 <div className="study-visual-overline"><span><span className="clinical-plus" aria-hidden="true">+</span> CLINICAL SITE FILE</span><span className="study-file-id">ILLUSTRATION / NO REAL DATA</span></div>
 <div className="study-record-sheet"><div className="study-record-heading"><div><span>FORM / SITE REVIEW</span><strong>Site record review</strong></div><span className="study-record-seal">SIMULATED</span></div>
 {['Visit dates','HbA1c lab records','Adverse event logs','Medication dispensing'].map((label,i)=><div className="study-record-line" key={label}><span>{label}</span><span className="study-record-placeholder"><i style={{width:`${80-i*11}%`}}/></span></div>)}
 <div className="study-record-footer"><span>GENERATED RECORDS</span><span aria-hidden="true">→</span><strong>MONITORING CHECKS</strong></div></div>
 <div className="study-visual-caption">Question: could a made-up site pass the usual checks?</div></div>}

export function SignalIllustration(){return <div className="study-comparison clinical-paper" aria-label="Monitoring checks compared on separate simulated test sites">
 <div className="study-visual-overline"><span><span className="clinical-plus" aria-hidden="true">+</span> MONITORING VALIDATION</span><span>SEPARATE SIMULATED SITES</span></div>
 <div className="study-comparison-grid"><div><small>VERSION / 01</small><strong>Original checks</strong><p>Existing monitoring</p><span className="study-version-pill">BASELINE</span></div><div><small>VERSION / 02</small><strong>Updated checks</strong><p>Additional monitoring rule</p><span className="study-version-pill">RETEST</span></div></div>
 <div className="study-comparison-bottom"><span className="study-testing-dot"/>Compare detection and false alarms on sites not used to develop the new check.</div>
 </div>}

export function PatientCardsIllustration(){return <div className="study-patient-view clinical-paper" aria-label="Example patient information visible to study coordinators, without treatment labels">
 <div className="study-visual-overline"><span><span className="clinical-plus" aria-hidden="true">+</span> BLINDED PATIENT VIEW</span><span>SIMULATED / 6 CARDS</span></div>
 <div className="study-patient-grid">{Array.from({length:6},(_,i)=><div className="study-patient-card" key={i}><span><b aria-hidden="true">+</b> PATIENT {String(i+1).padStart(2,'0')}</span><small>Visit log</small><i/><small>Pharmacy</small><i/></div>)}</div>
 <div className="study-patient-prompt">Can site staff tell who received the drug?</div>
 </div>}

export function PharmacologyNetwork(){return <div className="study-access" aria-label="Safety information stays available while treatment assignments remain private">
 <div className="study-visual-overline"><span><span className="clinical-plus" aria-hidden="true">+</span> CLINICAL INFORMATION ACCESS</span><span>TRIAL SAFETY</span></div>
 <div className="study-access-row"><span className="study-access-symbol access-plus">+</span><div><strong>Side effects and safety reports</strong><p>Investigators must always have access.</p></div><span className="study-access-tag open">VISIBLE</span></div>
 <div className="study-access-row"><span className="study-access-symbol access-lock">◇</span><div><strong>Who received the study drug</strong><p>Routine records should not give this away.</p></div><span className="study-access-tag closed">PRIVATE</span></div>
 <p className="study-access-note">Probe tests the information staff can see. It never changes patient records or hides required safety reports.</p>
 </div>}

export function ReportIllustration(){return <div className="study-report" aria-label="Illustration of a trial testing report">
 <div className="study-visual-overline"><span>STUDY TEST REPORT</span><span>AFTER THE RUN</span></div>
 <div className="study-report-title">What the report answers</div>
 {['Which trial checks failed?','How much could fake records change the result?','Did the changes work on new test sites?'].map((x,i)=><div className="study-report-row" key={i}><span>0{i+1}</span><strong>{x}</strong><span>↗</span></div>)}
 </div>}

/** Illustrative study pathway. These are stages, not real patients or experimental results. */
const trialMilestones = [
 {n:'01',label:'Screening',detail:'Check eligibility'},
 {n:'02',label:'Assignment',detail:'Drug or placebo'},
 {n:'03',label:'Visits',detail:'Record side effects'},
 {n:'04',label:'Week 24',detail:'Measure HbA1c'},
 {n:'05',label:'Results',detail:'Review trial findings'}
];

export function TrialJourney(){return <div className="probe-journey" aria-label="Five stages in the simulated drug study">
  <div className="probe-journey-head">
    <div className="probe-journey-medication" aria-hidden="true"><span className="probe-capsule"><i/></span><span className="probe-medicine-cross">+</span></div>
    <div><span className="probe-journey-eyebrow">DRUG STUDY / PRB-101 / SIMULATED</span><h3>From the first visit to the final result.</h3><p>Probe tests whether the records and privacy safeguards would hold throughout a fictional diabetes drug trial.</p></div>
    <div className="probe-journey-trialtag"><span>STUDY DESIGN</span><strong>Drug <span>vs.</span> Placebo</strong><small>Primary outcome: HbA1c</small></div>
  </div>
  <div className="probe-journey-track" role="list">{trialMilestones.map((m,i)=><div className="probe-journey-milestone" role="listitem" data-scroll="rise" data-stagger={i} key={m.n}>
    <span className="probe-journey-index">{m.n}</span><div className="probe-journey-node"><span/></div><strong>{m.label}</strong><p>{m.detail}</p>
  </div>)}</div>
  <div className="probe-journey-foot"><span><b className="probe-keyline"/>No real clinical-trial patient records</span><span>ILLUSTRATIVE STUDY FLOW</span></div>
 </div>}
