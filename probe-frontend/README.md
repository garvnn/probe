# Probe frontend

A five-screen clinical-trial testing frontend built with **Next.js 14, TypeScript, Tailwind, Recharts, React, and EventSource**. The homepage uses the typography, spacious section rhythm, boxed navigation, animated light trails and numbered accordions from the Lambda reference, with separate Probe branding and clinical-study content.

## What this version changes

This release keeps the oversized Lambda-style type, dark navigation, the Probe capsule logo, light-trail hero, and existing animations, but adds a much more recognizably medical visual language:

- A **full-width historical case study** about the real KYOTO HEART valsartan trial. The 2009 paper was retracted in 2013 because of critical data problems. It gives the integrity-testing story a real-world motivation, but the app does not claim to have analyzed that trial. Links to the original paper and retraction are included in the page.
- Flat **medical study forms** for site records, original-versus-updated monitoring, and six patient cards. These have recognizable fields and clinical chart styling rather than abstract placeholder bars.
- Consistent clinical teal, pale medical green, specimen-form rules, small medical crosses and capsule details on the existing spacious dark layout.
- Larger single-purpose feature panels and a readable, interactive five-step walkthrough. Mobile clinical panels adapt to available width.
- Updated headline: **Find problems in clinical trials before they start.**

The KYOTO HEART section cites historical publications, while the five-step interactive demo still uses the fictional PRB-101 diabetes scenario. KYOTO HEART was open-label with blinded endpoint assessment, so it is not a historical example of a placebo blinding leak. Probe has not evaluated its records and cannot claim it would have detected the historical problems. These forms are illustrations, not backend responses. They display no invented measurements, trial outcomes, or patient records. A saved copy of the reference site may exist locally under `reference/` for design comparison; it is gitignored and never loaded as application code.

## Logo

The header now uses the new capsule-inspired Probe wordmark, replacing the previous square P icon and typed brand name. The transparent source PNG is `public/probe-logo.png` and the favicon is `public/probe-icon.png`. To change its display size, edit `.probe-logo-img` in `app/globals.css`. The same logo is embedded into `public/probe-preview.html` for an offline preview.

## Preview without setup

Open `public/probe-preview.html` in a browser, or use the separately provided `probe-interactive-preview.html`. This is a **standalone landing-page preview** with the moving hero background, interactive four-step accordion, working five-step selector, navigation, and mobile menu. Preview navigation jumps between homepage sections. It is not a replacement for `/demo` and does not execute backend requests.

After editing the homepage styles, regenerate the preview with:

```bash
python scripts/build-preview.py
```

Font styling now follows the Lambda-style pairing: display type uses `Suisse Intl` when the visitor has a licensed installation, otherwise `Inter Tight`; technical paragraphs use `Suisse Intl Mono` when available, otherwise `IBM Plex Mono`. The two substitute fonts load from Google Fonts when a network is available. No proprietary fonts are distributed. The source font-family identification is from a third-party design analysis, so an exact font-file match to Lambda is not guaranteed.

The real Next.js homepage is `components/lambda/ClinicalHome.tsx`, its clinical graphics are in `components/lambda/ClinicalVisuals.tsx`, and responsive styles are in `app/globals.css`.

## Launch the application

From the repo root, start the backend first (fixtures only, no API keys needed):

```bash
make mock
```

Then, in a second terminal:

```bash
cd probe-frontend
npm install
cp .env.example .env.local
npm run dev            # or `make web` from the repo root
```

Browse to `http://localhost:3000` for the homepage or `/demo` for the presenter demo. The backend serves CORS for `localhost:3000`.

`lib/api-types.ts` is generated from the backend's `/openapi.json` (`backend/models.py`) and committed. After any backend model or route change, run `npm run gen:api` (or `make types`) with the API up, then `npm run typecheck`: a contract change shows up as a type error in `lib/api.ts` or the screen that reads the field. Missing endpoints (501 in cached/live mode) show a "Not built yet (owner: …)" panel rather than invented results.

## Five demo screens

| Route | Function |
| --- | --- |
| `/setup` | Create the simulated drug study and review what staff can see |
| `/forger` | Run fake study-site records through monitoring, with an SSE replay |
| `/harden` | Check whether updated monitoring catches more fake records on a separate test set |
| `/blind` | Judge guesses drug or placebo from six cards, then reviews the measured clues and possible changes |
| `/report` | Print-friendly result summary, organized by the five trial integrity checks |
| `/demo` | Presenter progression across all five screens; keyboard controls for next/previous/restart/pause and code view |

No clinical records are altered or hidden. Safety reports remain available to investigators. The system is a **pre-enrollment simulation**, not a certified medical or fraud-detection system for actual trials.

## What was tested

Against `make mock` (2026-10-17): `npm run typecheck` and `npm run build` pass, and a headless-Chrome run clicks through all five `/demo` stages (create trial → fake-data SSE stream → patch + test attacker + breaking point → Guess Who, blind-leak, cheapest fix, policy → report) with no console errors and no failed API calls. Cached and live modes have not been exercised from the UI yet; see `CLAUDE.md` at the repo root for status.

## Visual update: medical identity and scroll reveals

- The homepage prominently names **Probe** and labels it a clinical trial testing platform.
- A simulated PRB-101 drug study appears below the hero. Its screening, treatment assignment, patient-visit, week-24 measurement, and report sequence is illustrative; it is **not** an experimental result.
- Scroll progress, staggered content reveal, clinical-diagram entrance, and patient-card hover transitions are handled in `components/shared/ScrollEffects.tsx` and `app/globals.css`. Motion respects `prefers-reduced-motion`.
- The live five-screen app remains connected through `lib/api.ts`. The homepage art includes **no fabricated metrics**.

## Historical study evidence and boundaries

The homepage contains an educational example of the **KYOTO HEART Study**, a Japanese trial of add-on valsartan compared with conventional treatment without an angiotensin receptor blocker. Its main outcome was cardiovascular events, not the HbA1c endpoint used in Probe's fictional PRB-101 demo. The original trial enrolled **3,031** participants and was described as open-label with blinded endpoint assessment. The original 2009 *European Heart Journal* paper was retracted in 2013, citing critical problems with its reported data.

- Original published paper and design: https://pubmed.ncbi.nlm.nih.gov/19723695/
- Official retraction notice: https://academic.oup.com/eurheartj/article/34/14/1023/473163
- Published discussion of data fabrication in multiple valsartan trials: https://jamanetwork.com/journals/jamanetworkopen/fullarticle/2733427

This case is historical motivation, **not** a data source for the demo. The frontend never claims Probe detected this study's problems or could definitely have prevented them. It is not an example of a placebo-treatment blinding leak, since its design was open-label. The live demo remains based on the backend's fictional PRB-101 dataset.
