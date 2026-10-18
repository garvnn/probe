/**
 * Backend remains the only data source. Request and response types come from
 * lib/api-types.ts, generated from the FastAPI /openapi.json (backend/models.py) by
 * `npm run gen:api`; never handwrite response interfaces. Paths and bodies are
 * compile-time checked, so a backend contract change shows up as a typecheck error here.
 */
import type { components, paths } from './api-types';
import { asObj } from './utils';
export type Schemas = components['schemas'];
type Route = keyof paths extends never ? string : Extract<keyof paths,string>;
type JsonBody<T> = T extends {content:{'application/json':infer B}} ? B : unknown;
type Success<R> = R extends {200:infer A} ? JsonBody<A> : R extends {201:infer B} ? JsonBody<B> : unknown;
type ResponseFor<P extends string,M extends 'get'|'post'> = P extends keyof paths ?
  M extends keyof paths[P] ? NonNullable<paths[P][M]> extends {responses:infer R} ? Success<R> : unknown : unknown : unknown;
type BodyFor<P extends string> = P extends keyof paths ?
  NonNullable<paths[P]['post']> extends {requestBody:{content:{'application/json':infer B}}} ? B : never : Record<string,unknown>;
export const BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');
export class ApiError extends Error {
  constructor(public status: number, public owner: string | null, message: string) { super(message); this.name = 'ApiError'; }
}
async function request<P extends Route,M extends 'get'|'post'>(method:M,template:P,path:string,body?:unknown):Promise<ResponseFor<P,M>> {
  let response: Response;
  try { response = await fetch(`${BASE}${path}`, {
    method:method.toUpperCase(), body:body===undefined?undefined:JSON.stringify(body),
    headers: { 'Content-Type': 'application/json' }, cache: 'no-store'
  }); }
  catch { throw new ApiError(0, null, `Cannot reach Probe backend at ${BASE}. Start it with make mock.`); }
  const text = await response.text(); let data: unknown;
  try { data = text ? JSON.parse(text) as unknown : {}; } catch { data = { detail: text }; }
  if (!response.ok) {
    const o = asObj(data), detail = o.detail, d = asObj(detail);
    // Stubs answer 501 with {"detail": "owner: <name> (<mode> mode)"} (backend/main.py).
    const ownerInDetail = typeof detail === 'string' ? /owner:\s*([^(]+?)\s*(\(|$)/.exec(detail)?.[1] ?? null : null;
    const owner = typeof o.owner === 'string' ? o.owner : typeof d.owner === 'string' ? d.owner : ownerInDetail;
    const message = typeof detail === 'string' ? detail : typeof d.message === 'string' ? d.message : response.statusText;
    throw new ApiError(response.status, owner, response.status === 501 ? `Not built yet${owner ? ` (owner: ${owner})` : ''}` : message);
  }
  return data as ResponseFor<P,M>;
}
const get = <P extends Route>(template:P,path:string) => request('get',template,path);
const post = <P extends Route>(template:P,body:BodyFor<P>) => request('post',template,template,body);
const q = encodeURIComponent;
export const api = {
  // Mechanisms are omitted so the backend's DEFAULT_MECHANISMS (leaks on) apply.
  createTrial: (scenario: 'A' | 'B', seed = 2026) => post('/trials', { scenario, seed, n_sites: 20, patients_per_site: 40 }),
  getTrial: (id: string) => get('/trials/{trial_id}',`/trials/${q(id)}`),
  // `fixture` is mock-only: 'mixed' returns a post-run contract with held/broken properties.
  getContract: (id: string, fixture?: 'untested' | 'mixed') => get('/contract/{trial_id}',`/contract/${q(id)}${fixture ? `?fixture=${q(fixture)}` : ''}`),
  startFakeData: (id: string) => post('/fake-data/runs', { trial_id: id, attacker_id: 'training', suite_version: 0 }),
  fakeDataStreamUrl: (runId: string) => `${BASE}/fake-data/runs/${q(runId)}/stream`,
  patch: (id: string, runId: string, suiteVersion = 0) => post('/fraud-checks/patch', { trial_id: id, run_id: runId, suite_version: suiteVersion }),
  testAttacker: (id: string, suiteVersions: number[]) => post('/test-attacker/eval', { trial_id: id, attacker_id: 'test', suite_versions: suiteVersions }),
  breakingPoint: (id: string, suiteVersion: number) => post('/breaking-point', { trial_id: id, suite_version: suiteVersion }),
  guessCards: (id: string) => get('/blind-leak/guess-cards',`/blind-leak/guess-cards?trial_id=${q(id)}`),
  scoreGuesses: (id: string, guesses: Record<string, 'drug' | 'placebo'>) => post('/blind-leak/guess-cards/score', { trial_id: id, guesses }),
  blindRun: (id: string, view: Schemas['BlindLeakRunRequest']['view'] = 'coordinator') => post('/blind-leak/runs', { trial_id: id, view }),
  cheapestFix: (id: string) => post('/blind-leak/cheapest-fix', { trial_id: id }),
  applyPolicy: (id: string, remedies: Schemas['PolicyRequest']['remedies']) => post('/blind-leak/policy', { trial_id: id, view: 'assessor', remedies }),
  getReport: (id: string) => get('/report/{trial_id}',`/report/${q(id)}`)
};
