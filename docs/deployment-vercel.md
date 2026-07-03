# Deployment: Vercel frontend + single-VM backend

How to deploy the Malta professional-beta valuation app: the Next.js **frontend on
Vercel**, and the FastAPI **API + Celery worker + Redis + Caddy on one small VM**.

## Why this shape

- The `/enriched` valuation flow is **async** (API enqueues a Celery job; the browser
  polls for the result) and uses **no PostgreSQL** — only Redis (job store + rate
  limiter + broker), the baked model artifacts, the OSM cache, Gemini, and Nominatim.
- **Pure Vercel serverless was rejected**: the ML import stack (xgboost + scipy + numpy
  + sklearn ≈ 400 MB) exceeds Vercel's 250 MB function limit, and Vercel can't run a
  persistent Celery worker or Redis.
- **A single VM** keeps the existing Celery/Redis/local-disk-image flow working with
  near-zero code change; the API and worker share one host, so uploaded images pass
  through a shared volume with no re-plumbing.

### Component placement

| Component | Runs on |
|-----------|---------|
| Next.js frontend | Vercel |
| FastAPI API + Celery worker | VM (Docker) |
| Redis (job store · rate limit · broker) | VM (Docker) |
| Model `.joblib` + OSM cache + locality centroids | Baked into the backend image |
| Uploaded images (transient) | Shared Docker volume (`uploads`) → API + worker |
| Gemini · Nominatim | External APIs |
| TLS / domain | Caddy on the VM (auto Let's Encrypt) |
| PostgreSQL | **Not deployed** (unused by `/enriched`) |

Files: [`docker-compose.prod.yml`](../docker-compose.prod.yml),
[`backend/Dockerfile.prod`](../backend/Dockerfile.prod),
[`infra/caddy/Caddyfile`](../infra/caddy/Caddyfile),
[`.env.prod.example`](../.env.prod.example), [`.dockerignore`](../.dockerignore).

---

## Part A — Backend on a VM

1. **Back up first.** Commit the repo state; the models in `ml/artifacts/` and the OSM
   cache in `data/osm_cache/` are what get baked into the image — make sure they're the
   versions you intend to ship (`mt_apartment_{sale,rent}_v20260703`).

2. **Provision the VM.** e.g. Hetzner CX22 (2 vCPU / 4 GB / 40 GB), Ubuntu 24.04, a
   region close to Malta (Falkenstein/Nuremberg). Install Docker + the compose plugin.
   Open only ports **22, 80, 443** in the firewall.

3. **DNS.** Create an A record `api.<your-domain>` → the VM's public IP. Keep the
   apex/`www` pointed at Vercel for the frontend.

4. **Copy the repo to the VM** (git clone, or rsync — the build needs `backend/`,
   `ml/artifacts/`, `data/osm_cache/`; everything else is excluded by `.dockerignore`).

5. **Create `.env`** next to `docker-compose.prod.yml` (copy from `.env.prod.example`,
   `chmod 600`):
   - `API_DOMAIN=api.<your-domain>`
   - `CORS_ORIGINS=["https://<your-domain>","https://www.<your-domain>"]` — exact https
     origins, no trailing slash; add Vercel preview domains if you test from them.
   - `GOOGLE_API_KEY=…`, `LLM_PROVIDER=google`, `LLM_MODEL=gemini-3.1-flash-lite-preview`
   - `NOMINATIM_USER_AGENT="pricemap-beta (you@example.com)"`
   - **`CORS_ORIGINS` must be a JSON array** (`["https://…"]`, double quotes, brackets).
     A non-JSON value (e.g. `https://…`) makes the backend **crash-loop** at startup,
     not just misconfigure CORS.

6. **Bring it up:**
   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   ```
   This builds the baked image (context = repo root, `backend/Dockerfile.prod`), starts
   redis + backend + worker + Caddy. Caddy provisions Let's Encrypt TLS for `API_DOMAIN`
   on first request (needs the DNS record live + ports 80/443 reachable).

7. **Verify TLS + boot:**
   ```bash
   curl -sSf https://api.<your-domain>/openapi.json >/dev/null && echo OK
   ```
   (Use `/openapi.json`, not `/api/v1/health` — the health route requires Postgres.)

---

## Part B — Frontend on Vercel

1. Import the repo in Vercel; set **Root Directory = `frontend`** (framework auto-detects
   as Next.js).
2. Set env var **`NEXT_PUBLIC_API_URL=https://api.<your-domain>`** for **Production and
   Preview**. `api-client.ts` reads it — but `NEXT_PUBLIC_*` is **inlined at build
   time**, so set it *before the first deploy* and trigger a **full redeploy** (not just
   a restart) after any change, or the bundle keeps the `localhost:8000` fallback.
3. **Do not** route uploads through the `next.config.ts` `/api` rewrite — Vercel's
   serverless proxy caps request bodies at ~4.5 MB and would reject the 40 MB photo
   batches. Direct browser → VM calls (via CORS) are already what the client does.
4. Deploy. The browser calls the VM cross-origin; `CORS_ORIGINS` must list the **exact**
   Vercel origin(s). Vercel **preview** URLs rotate per commit and won't match the exact
   list — test on the **Production** domain (or add a stable branch alias to
   `CORS_ORIGINS`); matching arbitrary per-deploy hashes would need `allow_origin_regex`.

---

## Verification (end-to-end)

From the deployed frontend, submit a Sliema 2-bed apartment with a description and a
few photos and confirm:
- the job transitions `queued → running → complete`;
- the estimate is a sane range (a premium Sliema 2-bed lands roughly in the high
  hundreds of €k for sale / a few €k/month for rent — treat as a sanity band, not an
  exact target, since the output depends on the geocode, LLM read, and photos);
- the worker read the uploaded images (shared volume works) and deleted them afterward;
- a 6th submission within the hour returns **429** (rate limit).

---

## Gotchas

- **Shared upload volume (top risk).** The API writes images to
  `VALUATION_UPLOAD_DIR/{job_id}/` and the worker reads them; both mount the same
  `uploads` volume at `/uploads` in `docker-compose.prod.yml`. Without this the worker
  `FileNotFoundError`s and image valuations silently fail.
- **CORS is the most likely launch bug.** `cors_origins` defaults to localhost; a
  missing/mismatched `CORS_ORIGINS` (or an omitted preview domain) breaks all browser
  calls with opaque errors.
- **HTTPS is mandatory.** The Vercel frontend is https, so confirm Caddy issued the
  cert before pointing the frontend at the VM (otherwise mixed-content blocks).
- **No Postgres.** The API boots without a DB (`create_async_engine` is lazy; `/enriched`
  never calls `get_db`). The separate `/estimate` route and `/api/v1/health` **will 500**
  without Postgres — hide/disable their UI for the beta.
- **Rate-limit identity.** Caddy sets `X-Real-IP` to the real client and the backend
  port isn't published, so the per-IP limit can't be spoofed. A shared corporate NAT can
  collapse testers onto one IP — raise `VALUATION_RATE_LIMIT_HOUR` if needed. For a
  private beta, also gate the site behind Vercel password protection or a token.
- **Nominatim ToS.** Public OSM Nominatim needs a descriptive User-Agent and ~1 req/s
  max; set `NOMINATIM_USER_AGENT` and rely on the 30-day Redis geocode cache.
- **Vercel Hobby forbids commercial use.** A "professional beta" may need Vercel Pro.
- **Disk.** `restart: unless-stopped` + json-file log rotation are set. Monitor the 40 GB
  disk; the task deletes upload dirs in its `finally`, but a hard worker kill can orphan
  a few.

---

## Ops

- **Update models / code:** rebuild the image (models are baked): pull the repo,
  `docker compose -f docker-compose.prod.yml up -d --build`.
- **Logs:** `docker compose -f docker-compose.prod.yml logs -f backend worker`.
- **Rollback a model:** the image bakes whatever is in `ml/artifacts/`. The loader picks
  the newest version for which the **full quartet** (`lgb`, `xgb`, `encoders`, `meta`)
  exists. To roll back to v20260628, delete the **entire** v20260703 quartet
  (`rm ml/artifacts/mt_apartment_*_v20260703.*` — all four per model) and rebuild;
  deleting only some files is safe (the loader ignores incomplete versions) but leaving
  a lone `meta` won't downgrade.
- **Redis state:** AOF persistence (`--appendonly yes`) keeps job status + rate-limit /
  global-cap counters across restarts. Wiping the `redisdata` volume resets all abuse
  counters. Redis has no published port and no auth — it's reachable only on the compose
  network; add `--requirepass` if you ever run untrusted workloads on the same host.
