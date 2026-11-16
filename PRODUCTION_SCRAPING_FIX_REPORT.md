# PRODUCTION SCRAPING FAILURE: DIAGNOSIS & REMEDIATION REPORT
**Google Maps Competitor Intelligence Platform**  
**Date:** November 16, 2026  
**Status:** ALL FIXES IMPLEMENTED & VERIFIED LOCALLY — AWAITING DEPLOYMENT APPROVAL

---

## 1. Executive Summary

A critical cascade of failures was identified in the production environment preventing users from initiating and monitoring Google Maps competitor scrapes:
1. **Frontend Polling Storm & Gateway Timeouts:** The scraping page utilized a fixed `setInterval(..., 2800)` that continually dispatched requests every 2.8 seconds regardless of whether previous requests had resolved.
2. **Severe Backend Latency (N+1 Queries):** Endpoints `GET /projects/{project_id}/competitors`, `GET /projects/{project_id}/scrape-runs`, and `GET /scrape-runs/{run_id}` suffered from severe N+1 lazy queries across the remote Neon connection pooler (~15–18 seconds per request). This led to request queue piling, Render edge 502/504 timeouts, and Render 429 rate limits.
3. **Apparent CORS Failures:** When Render's edge proxy generates 429 (Too Many Requests), 502 (Bad Gateway), or 504 (Gateway Timeout), it does not include FastAPI's application headers. The browser dropped these responses and reported `No 'Access-Control-Allow-Origin' header is present`. CORS itself was correctly configured in FastAPI (`CORSMiddleware` active, tested and verified).
4. **Scrape Run Creation Bottlenecks & 404/409 Misclassification:** Run creation executed 63 discrete SQL transactions (one per competitor). Furthermore, when an existing run was in `QUEUED`, `service.create_scrape_run` threw a `ValueError` that `routes.py` mapped to HTTP 404 Not Found instead of HTTP 409 Conflict.
5. **Background Worker Configuration Drift:** Background worker `comp-intel-worker` on Render failed to process queued jobs because its environment configuration retained a stale Render internal PostgreSQL hostname (`dpg-dasgq960tbcc73fbhvgg-a`) instead of the shared Neon PostgreSQL database URL.

All frontend and backend code fixes have been implemented, tested, and validated with zero regressions (138/138 pytest tests passing, frontend built cleanly in 424ms).

---

## 2. Root Cause Analysis

| Component | Failure Symptom | Underlying Root Cause | Verification Evidence |
| :--- | :--- | :--- | :--- |
| **Frontend Polling** | `AxiosError: Network Error`, 429 Too Many Requests | `setInterval` fired every 2.8s without awaiting response or backoff. Up to 10 in-flight requests accumulated concurrently. | Live logs showed stacked requests with overlapping durations >14s. |
| **Backend Latency** | `GET /competitors` took 14.88s; `GET /scrape-runs` took 17.85s | SQLAlchemy ORM lazy loaded 60+ competitor profiles one by one over cloud Neon pooler. | Profiled queries revealed 60+ individual roundtrips per request. |
| **CORS Errors** | `No 'Access-Control-Allow-Origin'` | Render edge proxy dropped headers on 502/504 and 429 responses. | FastAPI preflight (OPTIONS), 200, 401, and 422 returned `Access-Control-Allow-Origin: https://google-maps-competitor-intelligence.onrender.com`. |
| **Run Creation** | `POST /projects/{id}/scrape` returned 404 & 502 | 1) 63 discrete `commit()` calls for 61 competitors.<br>2) Active run conflict threw `ValueError` mapped to 404. | SQLite/Postgres traces showed individual roundtrips; route caught `ValueError` as 404. |
| **Worker Queue** | Scrape runs stuck indefinitely in `QUEUED` | `comp-intel-worker` crashed with `psycopg.OperationalError: failed to resolve host 'dpg-dasgq960tbcc73fbhvgg-a'`. | Render worker startup logs confirmed connection to obsolete database hostname. |

---

## 3. Implemented Fixes

### A. Frontend Resilient Polling (`frontend/src/pages/ProjectScraping.tsx` & `frontend/src/api.ts`)
- **Chained Asynchronous Scheduling:** Replaced `setInterval` with recursive `setTimeout`. A new request is only scheduled after the preceding request either completes or times out.
- **In-flight Cancellation:** Integrated `AbortController` into `getScrapeRuns`, `getScrapeRun`, and `getCompetitors`. In-flight requests are aborted immediately when switching projects or unmounting.
- **Exponential Backoff & Rate-Limit Respect:**
  - Transient errors (502, 503, 504, network failure) back off sequentially: `3.5s → 5.25s → 7.8s → 11.8s → max 30s`.
  - HTTP 429 parses `Retry-After` header or backs off dynamically.
- **Terminal State Polling Termination:** Polling stops when runs enter terminal states (`SUCCESS`, `PARTIAL_SUCCESS`, `FAILED`).
- **Duplicate Click Prevention:** Synchronous ref-based lock (`isSubmittingScrapeRef`) suppresses rapid multiple clicks on "Start Scrape".
- **Conflict Handling:** HTTP 409 Conflict is handled gracefully without triggering error alert loops.
- **UI Status Messaging:** Added user-facing non-intrusive status banner indicating reconnection or rate-limiting delays.

### B. Backend Database Optimization (`backend/app/repositories/scrape_repo.py` & `project_repo.py`)
- **Eager Loading on Individual Run Details:**
  ```python
  # ScrapeRunRepository.get() override
  stmt = select(ScrapeRun).options(
      selectinload(ScrapeRun.competitor_runs).joinedload(ScrapeRunCompetitor.business)
  ).where(ScrapeRun.id == id)
  ```
  Eliminates 62 sequential lazy-load queries on `GET /scrape-runs/{run_id}`.
- **Eager Loading on Project Runs:**
  Maintained `selectinload` on `get_runs_for_project` to fetch all runs and child competitor runs in 2 single queries instead of hundreds.
- **Eager Loading on Competitor Retrieval:**
  Updated `ProjectRepository.get_competitors` with `joinedload(ProjectCompetitor.business)` to load competitor businesses in 1 join query instead of 61.

### C. Batch Run Creation (`backend/app/services/scrape_service.py`)
- Replaced 61 individual `create()` and commit calls with bulk session addition:
  ```python
  competitors = self.project_repo.get_competitors(project_id)
  for comp in competitors:
      comp_obj = ScrapeRunCompetitor(
          scrape_run_id=run.id,
          business_id=comp.business_id,
          status="PENDING"
      )
      self.db.add(comp_obj)
  run.competitors_attempted = len(competitors)
  self.db.commit()
  ```
  Reduces roundtrips from 63 down to 2.

### D. Route Status Code Accuracy (`backend/app/api/routes.py`)
- Fixed active run conflict mapping:
  ```python
  except ValueError as e:
      if "already has an active run" in str(e):
          raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
      raise HTTPException(status_code=404, detail=str(e))
  ```

---

## 4. Verification & Benchmarking Results

### 1. Performance Profiling (`qa_audit/test_phase6_verification.py`)
- **Scrape Run Creation (60 Competitors):** Reduced from **15.2s** down to **10.42ms** (1,400x improvement).
- **Eager Loading Resolution:** Verified that accessing nested relationships `run.competitor_runs[i].business.business_name` executes zero subsequent SQL queries.
- **HTTP 409 Mapping:** Verified that creating a duplicate active run triggers HTTP 409 Conflict.

### 2. Frontend Production Build
```text
> frontend@0.0.0 build
> tsc -b && vite build
✓ 1975 modules transformed.
dist/index.html                   0.45 kB │ gzip:   0.29 kB
dist/assets/index-Bc-XtYUm.css   48.12 kB │ gzip:   9.22 kB
dist/assets/index-Dddhspcj.js   445.58 kB │ gzip: 130.60 kB
✓ built in 424ms
```
Zero TypeScript or bundling errors.

### 3. Backend Pytest Suite
```text
138 passed, 4 warnings in 14.26s
```
Zero regressions across all repositories, services, auth enforcement, intelligence, and scraping workflows.

### 4. Live CORS & Gateway Test (`qa_audit/test_cors_error_responses.py`)
- `OPTIONS /projects/235a2d92-9c65-4fe9-af13-a38275ba89bd/scrape-runs`: HTTP 200 with `Access-Control-Allow-Origin: https://google-maps-competitor-intelligence.onrender.com`.
- `GET /projects` (Unauthenticated): HTTP 401 with valid CORS headers.
- `POST /auth/login` (Invalid schema): HTTP 422 with valid CORS headers.
- Disallowed Origin: Correctly rejected without CORS headers.

---

## 5. Polling Behavior Comparison

| Metric | Before Remediation | After Remediation |
| :--- | :--- | :--- |
| **Polling Mechanism** | Blind `setInterval(..., 2800)` | Sequential chained `setTimeout` |
| **Max Concurrent In-Flight** | Uncapped (often 5–10 requests) | Strictly **1** |
| **On Slow Response (>5s)** | Dispatched new requests over old ones | Waits for resolution before next poll |
| **Behavior on 429 / 502 / 503** | Continued hammer at 2.8s interval | Exponential backoff (3.5s → 30s) + `Retry-After` |
| **Behavior on Unmount/Switch** | Continued polling in background | Immediate cancellation via `AbortController` |
| **Duplicate Scrape Clicks** | Allowed multi-submits and 404 loops | Locked via `isSubmittingScrapeRef` + 409 handling |

---

## 6. Action Items for Production Deployment

To apply these fixes to the live production services without downtime:

1. **Update Worker Database URL (Render Dashboard):**
   - Service: `comp-intel-worker`
   - Setting: Environment Variable `DATABASE_URL`
   - Action: Update the connection string from the stale `dpg-dasgq960tbcc73fbhvgg-a` host to the Neon PostgreSQL connection string (identical to `comp-intel-api-mehe`).
2. **Deploy Code Changes:**
   - Commit the modified files (`backend/app/api/routes.py`, `backend/app/repositories/project_repo.py`, `backend/app/repositories/scrape_repo.py`, `backend/app/services/scrape_service.py`, `frontend/src/api.ts`, `frontend/src/pages/ProjectScraping.tsx`).
   - Trigger deployment on Render Web API and Render Static Site (or auto-deploy on git push).
3. **Verify Worker Operation:**
   - Confirm in `comp-intel-worker` logs that the worker connects to Neon and Upstash Redis without connection errors.
   - Run a test scrape from the frontend and verify it transitions smoothly from `QUEUED` to `RUNNING` to `SUCCESS`.
