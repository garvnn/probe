export const asObj = (v: unknown): Record<string, unknown> => (v !== null && typeof v === 'object' && !Array.isArray(v)) ? v as Record<string, unknown> : {};
export const arr = (v: unknown): unknown[] => Array.isArray(v) ? v : [];
export const str = (v: unknown, fallback = ''): string => typeof v === 'string' ? v : (typeof v === 'number' ? String(v) : fallback);
export const num = (v: unknown): number | null => typeof v === 'number' && Number.isFinite(v) ? v : null;
export const bool = (v: unknown): boolean => v === true;
export const pick = (v: unknown, ...keys: string[]): unknown => { const o = asObj(v); for (const k of keys) if (o[k] !== undefined && o[k] !== null) return o[k]; return undefined; };
export const percent = (n: unknown): string => num(n) === null ? 'N/A' : `${((num(n) as number) * 100).toFixed(1)}%`;
export const tidy = (s: string) => s.replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
export function errorText(e: unknown): string { return e instanceof Error ? e.message : String(e); }
export function isMock(v: unknown): boolean { return asObj(v)._mock === true; }
