import { execFileSync } from 'node:child_process';
const url = process.env.OPENAPI_URL || `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/openapi.json`;
console.log(`Generating types from ${url}`);
// --default-non-nullable false: fields with a server default (seed, suite_version, ...) stay optional in request bodies.
execFileSync('npx', ['openapi-typescript', url, '-o', 'lib/api-types.ts', '--default-non-nullable', 'false'], { stdio: 'inherit' });
