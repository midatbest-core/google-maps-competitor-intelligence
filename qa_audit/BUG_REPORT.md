# Comprehensive Bug Report & Remediation Log

## Bug Inventory

| Bug ID | Module / Component | Severity | Description | Status |
| :--- | :--- | :---: | :--- | :---: |
| **BUG-001** | `post_service.py` | **P1** | HTTP 500 on `GET /projects/:id/posts`: `NameError: name 'distinct' is not defined` | **RESOLVED** |
| **BUG-002** | `ProjectScraping.tsx` | **P2** | HTTP 404 console flooding loop from optimistic client-side run IDs (`run-1794...`) | **RESOLVED** |
| **BUG-003** | `project_repo.py` | **P2** | N+1 database roundtrips on `GET /projects/:id/competitors` causing API timeouts | **RESOLVED** |
| **BUG-004** | `scrape_repo.py` | **P2** | N+1 database roundtrips on `GET /projects/:id/scrape-runs` causing API timeouts | **RESOLVED** |
| **BUG-005** | `review_collector.py` / `main.py` | **P2** | Method name mismatch: worker invoked `collect_for_business`, but service defined `collect_reviews_for_business` | **RESOLVED** |
| **BUG-006** | `auth.py` schema | **P3** | User registration schema accepted weak passwords shorter than 8 characters | **RESOLVED** |
| **BUG-007** | `.env` / `config.py` | **P3** | `APP_ENV=production` in local development caused CORS origin validator exceptions | **RESOLVED** |

---

## Detailed Bug Descriptions & Root Causes

### BUG-001: Missing `distinct` import in `post_service.py`
- **Severity:** P1 (Critical user-facing failure)
- **Symptom:** `GET /projects/{id}/posts` returned HTTP 500 Internal Server Error when opening the Posts Feed.
- **Root Cause:** SQLAlchemy `distinct` function was called at line 83 (`func.count(distinct(Post.id))`), but `distinct` was missing from the import list on line 2.
- **Fix:** Added `distinct` to `from sqlalchemy import select, func, or_, desc, asc, distinct` in `backend/app/services/post_service.py`. Added empty post result set guard.
- **Verification:** Unit and API tests return 200 with 8 posts verified.

---

### BUG-002: Optimistic Run ID 404 Polling Loop
- **Severity:** P2 (High user annoyance / console error flooding)
- **Symptom:** Browser console flooded with `GET /api/scrape-runs/run-1794254064167 404 Not Found` every 2.8 seconds.
- **Root Cause:** In `ProjectScraping.tsx`, an optimistic run card with temporary ID (`run-${Date.now()}`) was placed into state to give instant UI feedback on button click. `useEffect` and `setInterval` immediately queried the backend for details of this non-existent ID, and JavaScript closure inside `setInterval` retained the temporary ID.
- **Fix:**
  1. Added guard in `fetchActiveRunDetails`: skip network call if `runId.startsWith('run-')` or `runId.startsWith('temp-')`.
  2. Added `activeRunIdRef` to track live ID updates without stale closures in `setInterval`.
- **Verification:** Verified in Playwright browser tests; zero 404 network errors emitted.

---

### BUG-003 & BUG-004: N+1 Query Cascade on Competitors & Scrape Runs
- **Severity:** P2 (Performance bottleneck / Cloud DB latency timeouts)
- **Symptom:** `GET /projects/:id/competitors` and `GET /projects/:id/scrape-runs` exceeded 10-second request timeouts when testing projects with 60+ competitors.
- **Root Cause:** Pydantic serialization accessed lazy-loaded relationships (`comp.business` and `run.competitor_runs.business`). Over the cloud pooler connection to Neon PostgreSQL, this triggered 60 to 200 individual sequential network roundtrips.
- **Fix:**
  - In `backend/app/repositories/project_repo.py`: Added `options(joinedload(ProjectCompetitor.business))`.
  - In `backend/app/repositories/scrape_repo.py`: Added `options(selectinload(ScrapeRun.competitor_runs).joinedload(ScrapeRunCompetitor.business))`.
- **Verification:** Latency dropped from >15,000ms (timeout) down to 1,716ms for 61 competitors and 2,144ms for scrape runs. Both return HTTP 200.

---

### BUG-005: Method Mismatch in Worker Review Collection
- **Severity:** P2 (Silent background task failure)
- **Symptom:** Review collection was silently failing during scraping pipeline with `AttributeError: 'ReviewCollectorService' object has no attribute 'collect_for_business'`.
- **Root Cause:** In `backend/app/workers/main.py`, the call was `await review_collector.collect_for_business(c.business)`. The actual method name in `ReviewCollectorService` was `collect_reviews_for_business`.
- **Fix:** Standardized worker call to `collect_reviews_for_business` and added `collect_for_business = collect_reviews_for_business` as a method alias.
- **Verification:** Pytest `test_e2e_collection_pipeline.py` passed with 2/2 reviews successfully collected into DB.

---

### BUG-006: Missing Password Length Validation
- **Severity:** P3 (Security hygiene / validation)
- **Symptom:** Registration accepted passwords of any length (e.g. `"short"`).
- **Root Cause:** `UserCreate` schema had `password: str` without `Field(..., min_length=8)`.
- **Fix:** Added `password: str = Field(..., min_length=8)` to `backend/app/schemas/auth.py`.
- **Verification:** Tested with `"short"`, correctly rejected with HTTP 422 Unprocessable Entity.

---

### BUG-007: Development Environment Validation Conflict
- **Severity:** P3 (Developer onboarding / environment startup)
- **Symptom:** Uvicorn failed to start locally with `pydantic_core.ValidationError: Production CORS_ORIGINS must contain deployed HTTPS origins`.
- **Root Cause:** `.env` had `APP_ENV=production` which enforces strict deployed HTTPS origins even on local development machines.
- **Fix:** Changed `APP_ENV=development` in root and backend `.env`.
- **Verification:** Uvicorn and FastAPI initialized cleanly.
