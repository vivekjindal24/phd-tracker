# PhD Tracker — web

Next.js (App Router) client for the PhD Tracker API. Deploys on Vercel; no Dockerfile needed.

## Local dev

```bash
npm install
npm run dev   # http://localhost:3000
```

Point it at the API and export service (defaults in `src/lib/api.ts`):

```bash
NEXT_PUBLIC_API_URL=http://localhost:8900/api/v1
NEXT_PUBLIC_EXPORT_URL=http://localhost:8902
```

See the root `docker-compose.yml` to bring up Postgres + API + export locally.

## Vercel

Import the repo, set the root directory to `web/`, and set the same two
`NEXT_PUBLIC_*` vars to the deployed API/export URLs. Vercel auto-deploys
`main`.

## Build notes

- Turbopack persistent cache is disabled in `next.config.ts` (the repo
  volume is exFAT, which breaks its cache DB). Vercel builds are unaffected.
- Pages are client components behind an auth gate (`src/lib/auth.ts`); the
  API is the security enforcer, the nav only hides what the API denies.