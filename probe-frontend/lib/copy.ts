/* Shared interface copy. Terminology explains the clinical test in plain English. */
export const copy = {
  brand: 'PROBE', eyebrow: 'CLINICAL TRIAL TESTING', tagline: 'Find trial risks before patients enroll.',
  summary: 'Probe checks if fake site records can pass monitoring or if staff can guess who got the drug. Then it checks whether the improvements worked.',
  sections: ['Set up trial', 'Fake site test', 'Check monitoring', 'Treatment privacy', 'Results report'] as const,
  shortSections: ['TRIAL SETUP', 'FAKE SITE TEST', 'MONITORING RECHECK', 'TREATMENT PRIVACY', 'REPORT'] as const,
  sectionNotes: [
    'Create a simulated trial and see the five things Probe will check.',
    'See if fabricated site records can get through the fraud checks.',
    'Measure whether updated checks find more fake sites without flagging valid sites.',
    'Guess who received the drug, then see what ordinary staff records reveal.',
    'Review the results, what failed, and which changes were tested.'
  ],
  properties: ['Data authenticity', 'Treatment confidentiality', 'Statistical integrity', 'Safety accessibility', 'Operational utility'] as const,
  status: { untested: 'NOT TESTED', held: 'PASSED', broken: 'FAILED' },
  counterexample: 'PROBLEM FOUND',
  heldout: 'Separate test: records not used to improve the monitoring checks',
  margin: 'How many undetected fake sites could change the study conclusion?',
  gauge: '50% means the guesses are no better than chance. Higher accuracy suggests treatment clues in the records.',
  pareto: 'Compare changes to treatment privacy with the site tasks they still allow.',
  remedyCost: 'Assigned cost is a relative estimate, not a market price.',
  warning: 'Simulated trial only. No real trial patient data. Not a tool for detecting fraud in live trials.',
  roleLabels: { coordinator: 'Coordinator', investigator: 'Investigator', pharmacist: 'Pharmacist', assessor: 'Outcome assessor' },
  leakLabels: {
    n_unsched: 'Extra unscheduled visits', unscheduled_visits: 'Extra unscheduled visits',
    dispensing_count: 'Pharmacy dose changes', dispensing_events: 'Pharmacy dose changes',
    antiemetic: 'Anti-nausea medications', antiemetic_yes: 'Anti-nausea medications',
    ae_count: 'Reported side effects', ae_terms: 'Reported side effects',
    glucose_trend: 'Local glucose readings', local_glucose_trend: 'Local glucose readings',
    days_between_visits: 'Time between visits', kit_returns: 'Kit return records',
    lab_draw_times: 'Lab draw times'
  } as Record<string, string>,
  checkLabels: {
    digit_pref: 'Terminal digit preference', variance: 'Variance (too tidy)', inlier: 'Inlier (too average)',
    corr_struct: 'Correlation structure', autocorr: 'Within-patient autocorrelation', date_anomaly: 'Date anomalies',
    ae_rate: 'AE under-reporting', missingness: 'Missingness', learned: 'Learned check (Patch)'
  } as Record<string, string>,
  patientFields: {
    n_unsched: 'Unscheduled visits', unscheduled_visits: 'Unscheduled visits',
    ae_terms: 'Side effects reported', gi_adverse_events: 'Stomach side effects reported', antiemetic: 'Anti-nausea medication', antiemetic_yes: 'Anti-nausea medication',
    dispensing_count: 'Medication pickup events', dispensing_events: 'Medication pickup events',
    local_glucose_trend: 'Glucose readings', glucose_trend: 'Glucose readings',
    days_between_visits: 'Days between visits'
  } as Record<string, string>
};
export function humanize(key: string, table: Record<string, string> = copy.leakLabels) {
  return table[key] ?? key.replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
}
