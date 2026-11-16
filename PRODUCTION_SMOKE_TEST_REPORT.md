# PRODUCTION SMOKE TEST REPORT: GOOGLE MAPS COMPETITOR INTELLIGENCE PLATFORM
**Live Production Environment Verification & Deployment Audit**

- **Date of Verification:** November 16, 2026 (02:30 IST / 21:00 UTC)
- **Auditor Role:** Senior QA Engineer, Software Test Architect & Security Auditor
- **Audit Target:** Live Deployed Production Environments (Vercel & Render)
- **Final Verdict:** **NOT READY FOR LIVE DEMONSTRATION**

---

## 1. Executive Summary & Critical URL Discovery

The user provided the following live deployment URLs for production smoke testing:
- **Frontend Target:** `https://roster-iq-delta.vercel.app`
- **Backend Target:** `https://rosteriq-backend-km04.onrender.com`

Per instructions to rigorously verify these URLs against the codebase configuration rather than assuming their correctness, an in-depth inspection of the deployment bundles, DNS, OpenAPI specifications, and codebase configuration was performed.

### Critical Discovery: Application Mismatch
1. **The Supplied URLs Host a Completely Different Application ("RosterIQ"):**
   - The live Vercel frontend (`https://roster-iq-delta.vercel.app`) serves **"RosterIQ | Smart Rostering"** (`<meta name="description" content="RosterIQ - Smart Rostering. Better Teams. Deterministic constraint-based workforce scheduling suite." />`).
   - The live Render backend (`https://rosteriq-backend-km04.onrender.com/openapi.json`) serves the **"RosterIQ API"** (`workforce, brands, processes, operating rules, deterministic roster generation and validation`). Its endpoints manage employee pods, shifts, and leave (`/api/v1/pods`, `/api/v1/employees`, `/api/v1/skills`, `/api/v1/unavailability`).
   - Analysis of the deployed JavaScript bundle (`/assets/index-CNtR8ZxM.js`) revealed 267 occurrences of "employee", 235 occurrences of "roster", and **0 occurrences of "competitor" or "scrape"**.
   - The Competitor Intelligence platform's endpoints (`/projects`, `/competitors`, `/discovery`, `/scrape-runs`, `/reviews`, `/intelligence`, `/content`) return **HTTP 404 Not Found** on `rosteriq-backend-km04.onrender.com`.

2. **The Repository's Configured Deployment Target (`comp-intel-api-mehe`):**
   - In [`render.yaml`](file:///c:/Users/Admin/comp/render.yaml), the service name is configured as `comp-intel-api-mehe` (web) and `comp-intel-worker` (worker).
   - In [`frontend/.env.production`](file:///c:/Users/Admin/comp/frontend/.env.production), the production API URL is set to `https://comp-intel-api-mehe.onrender.com`.
   - Probing `https://comp-intel-api-mehe.onrender.com/health` resulted in **HTTP request timeouts (>60 seconds)** with 0 bytes returned from the upstream origin. The service is currently suspended, terminated, or crashing during container startup.

---

## 2. Comprehensive Verification Matrix

| Verification Area | Specific Check | Live Target Tested | Result Status | Evidence & Details |
| :--- | :--- | :--- | :---: | :--- |
| **Connectivity** | Frontend DNS & HTTPS | `https://roster-iq-delta.vercel.app` | **PASS** | Resolves to `64.29.17.67`, HTTP 200, TLS valid. |
| **Connectivity** | Frontend Identity Match | `https://roster-iq-delta.vercel.app` | **FAIL** | Hosts RosterIQ (Workforce Management), not Competitor Intel. |
| **Connectivity** | Supplied Backend Health | `https://rosteriq-backend-km04.onrender.com/health` | **PASS** | HTTP 200 OK (`{"status":"ok"}`), 0.48s latency. |
| **Connectivity** | Supplied Backend Identity | `https://rosteriq-backend-km04.onrender.com/openapi.json` | **FAIL** | Title is "RosterIQ API". Contains 0 competitor intelligence endpoints. |
| **Connectivity** | Configured Backend Health | `https://comp-intel-api-mehe.onrender.com/health` | **FAIL** | Connection timeout (>60s). Upstream origin unresponsive. |
| **Connectivity** | CORS Headers (Supplied) | `https://rosteriq-backend-km04.onrender.com` | **PASS** | Returns `access-control-allow-origin: https://roster-iq-delta.vercel.app`. |
| **Authentication** | Competitor Intel Login | Both live backends | **BLOCKED** | Neither backend exposes Competitor Intelligence auth routes. |
| **Authentication** | Session & JWT Behavior | Both live backends | **BLOCKED** | Blocked due to missing application endpoints. |
| **Workflows** | Business Profile CRUD | Both live backends | **BLOCKED** | Blocked due to missing `/projects` routes on live servers. |
| **Workflows** | Competitor Roster | Both live backends | **BLOCKED** | Blocked due to missing `/competitors` routes on live servers. |
| **Workflows** | Google Maps Discovery | Both live backends | **BLOCKED** | Blocked due to missing `/discovery` routes on live servers. |
| **Workflows** | Social & Review Scraping | Both live backends | **BLOCKED** | Blocked due to missing `/scrape-runs` routes on live servers. |
| **Workflows** | AI Strategic Analysis | Both live backends | **BLOCKED** | Blocked due to missing `/intelligence` routes on live servers. |
| **Workflows** | Content Generation | Both live backends | **BLOCKED** | Blocked due to missing `/content/generate` routes. |
| **UI Integration** | Console Errors (Vercel) | `https://roster-iq-delta.vercel.app` | **PASS** | 0 uncaught JavaScript errors, clean rendering of RosterIQ UI. |
| **Configuration** | Production Pydantic Config | `backend/app/core/config.py` | **FAIL** | Fails boot if `GOOGLE_PLACES_API_KEY` or HTTPS `CORS_ORIGINS` are missing. |

---

## 3. Deep-Dive Technical Findings

### Finding 1: Dissection of `https://roster-iq-delta.vercel.app`
Playwright browser automation was dispatched to inspect the live DOM, console, and network activity:
- **Title:** `RosterIQ | Smart Rostering`
- **Rendered Content:** Presentation demo access for 5 staging roles (System Admin, Operations Manager, Pod Lead, Brand User, Employee) and a live demo directory with 36 employees and 15 brands.
- **Console Output:** 0 errors.
- **Network Requests:** Loaded `/assets/index-CNtR8ZxM.js` (563 kB) and `/assets/index-Ak6onNcR.css`.
- **Screenshot Evidence:** Saved to [`qa_audit/screenshots/live_vercel_rosteriq.png`](file:///c:/Users/Admin/comp/qa_audit/screenshots/live_vercel_rosteriq.png).
- **Conclusion:** A separate workforce scheduling product was mistakenly deployed to this Vercel project or provided as the target URL.

### Finding 2: Dissection of `https://rosteriq-backend-km04.onrender.com`
A query to `/openapi.json` confirmed the API specification:
```json
{
  "title": "RosterIQ API",
  "description": "RosterIQ API: workforce, brands, processes, operating rules, deterministic roster generation and validation.",
  "paths": 69,
  "sample_paths": [
    "/api/v1/auth/login",
    "/api/v1/pods",
    "/api/v1/employees",
    "/api/v1/skills",
    "/api/v1/unavailability"
  ]
}
```
Attempting to hit Competitor Intelligence routes returned:
- `GET /ready` $\rightarrow$ **404 Not Found**
- `GET /api/projects` $\rightarrow$ **404 Not Found**
- `GET /projects` $\rightarrow$ **404 Not Found**
- `GET /auth/login` $\rightarrow$ **404 Not Found**

### Finding 3: Root Cause Analysis for `comp-intel-api-mehe.onrender.com` Failure
In [`backend/app/core/config.py`](file:///c:/Users/Admin/comp/backend/app/core/config.py), the application enforces strict production validation:
```python
@model_validator(mode="after")
def validate_production_configuration(self):
    if self.APP_ENV.lower() != "production":
        return self
    if not (self.GOOGLE_PLACES_API_KEY or "").strip():
        raise ValueError("GOOGLE_PLACES_API_KEY is required in production")
    if not self.CORS_ORIGINS or any("localhost" in origin for origin in self.CORS_ORIGINS):
        raise ValueError("Production CORS_ORIGINS must contain deployed HTTPS origins")
```
When deployed to Render with `APP_ENV=production`, if `GOOGLE_PLACES_API_KEY` is omitted or if `CORS_ORIGINS` still contains `localhost`, Pydantic raises a `ValueError` immediately upon module import. This causes Uvicorn to crash before binding to `$PORT`, resulting in Render returning gateway timeouts.

---

## 4. Blocked Tests & Outstanding Production Risks

### Blocked Test Executions
1. **Live Production Business CRUD:** Blocked because the deployed environment does not run the Competitor Intelligence schema or endpoints.
2. **Live Google Maps Scraping in Production:** Blocked because the live worker is not deployed or reachable.
3. **Live AI Generation in Production:** Blocked because live endpoints are not accessible.

### Outstanding Risks Before Go-Live
1. **Cloud Deployment Desynchronization:** The code in this repository (`comp-intel`) has never been deployed to the Vercel URL provided (`roster-iq-delta.vercel.app`), and the Render service configured in `render.yaml` (`comp-intel-api-mehe`) is dormant or crashing.
2. **Mandatory Production Environment Variables:** Deploying this repository requires five mandatory secrets that will cause immediate boot failure if omitted:
   - `APP_ENV=production`
   - `DATABASE_URL` (PostgreSQL with pgvector)
   - `REDIS_URL` (Upstash or hosted Redis)
   - `SECRET_KEY` (JWT signing key)
   - `GOOGLE_PLACES_API_KEY` (Required by validation schema)
   - `CORS_ORIGINS` (JSON array of deployed frontend HTTPS URLs, e.g. `["https://comp-intel.vercel.app"]`)
3. **Google Anti-Bot Verification in Cloud Workers:** Playwright running inside Render worker containers will face Cloudflare / Google anti-bot challenges unless residential proxies or manual verification hooks are provisioned.

---

## 5. Deployment Remediation Roadmap

To make the Google Maps Competitor Intelligence Platform ready for live demonstration:

1. **Step 1: Create a Dedicated Vercel Project:**
   - Link the frontend directory (`c:\Users\Admin\comp\frontend`) to a new, dedicated Vercel project (e.g., `competitor-intelligence.vercel.app`).
   - Set the build command: `npm run build`.
   - Set output directory: `dist`.
   - Set environment variable: `VITE_API_URL=https://<your-render-api-name>.onrender.com`.

2. **Step 2: Deploy Backend to Render using `render.yaml`:**
   - Deploy web service `comp-intel-api-mehe` and worker service `comp-intel-worker`.
   - In Render dashboard, set the mandatory environment variables:
     * `DATABASE_URL`: Hosted Neon PostgreSQL URI.
     * `REDIS_URL`: Upstash Redis URI.
     * `SECRET_KEY`: High-entropy 32+ character string.
     * `GOOGLE_PLACES_API_KEY`: Active Google Places API key.
     * `CORS_ORIGINS`: `["https://<your-vercel-domain>.vercel.app"]`
     * `AI_PROVIDER`: `gemini`
     * `GEMINI_API_KEY`: Active Gemini API key.

3. **Step 3: Execute Live Smoke Test against Deployed Targets:**
   - Verify `GET https://<your-render-api-name>.onrender.com/ready` returns `{"status":"ready","database":true,"redis":true}`.
   - Run live Playwright smoke test against the new Vercel URL.

---

## 6. Final Production Verdict

### **VERDICT: NOT READY FOR LIVE DEMONSTRATION**

**Justification:**
While the local application codebase is stable, verified, and passes 187/187 automated unit, integration, and E2E tests, the live URLs provided (`https://roster-iq-delta.vercel.app` and `https://rosteriq-backend-km04.onrender.com`) host a completely unrelated workforce management product ("RosterIQ"). Furthermore, the configured Render backend for this repository (`comp-intel-api-mehe.onrender.com`) is currently unresponsive. Live production demonstration cannot proceed until the Google Maps Competitor Intelligence Platform is deployed to its own dedicated live infrastructure.
