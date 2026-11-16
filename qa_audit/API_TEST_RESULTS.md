# REST API Test Results & Performance Benchmarks

**Target Backend:** FastAPI (`http://127.0.0.1:8000`)  
**Database:** Neon PostgreSQL Cloud Pooler (TLS)  
**Redis:** Upstash Redis (Rediss TLS)  
**Authentication:** Stateless JWT (`Bearer <token>`, HS256)  

---

## 1. Complete API Endpoint Test Matrix

| HTTP Method | Endpoint Route | Expected Status | Actual Status | Latency (ms) | Result |
| :--- | :--- | :---: | :---: | :---: | :---: |
| `GET` | `/health` | 200 | **200** | 4.6 ms | **PASS** |
| `GET` | `/ready` | 200 | **200** | 3,761.9 ms | **PASS** |
| `GET` | `/auth/me` | 200 | **200** | 2,222.7 ms | **PASS** |
| `GET` | `/projects` | 200 | **200** | 1,341.8 ms | **PASS** |
| `GET` | `/projects/{project_id}` | 200 | **200** | 1,302.3 ms | **PASS** |
| `GET` | `/projects/{project_id}/summary` | 200 | **200** | 3,046.6 ms | **PASS** |
| `GET` | `/projects/{project_id}/competitors` | 200 | **200** | 1,716.2 ms | **PASS** |
| `GET` | `/projects/{project_id}/discovery-candidates` | 200 | **200** | 2,431.8 ms | **PASS** |
| `GET` | `/projects/{project_id}/discovery-runs` | 200 | **200** | 1,326.9 ms | **PASS** |
| `GET` | `/projects/{project_id}/scrape-runs` | 200 | **200** | 2,144.6 ms | **PASS** |
| `GET` | `/projects/{project_id}/posts?page=1&page_size=20` | 200 | **200** | 2,825.7 ms | **PASS** |
| `GET` | `/projects/{project_id}/reviews` | 200 | **200** | 2,167.4 ms | **PASS** |
| `GET` | `/projects/{project_id}/analytics/summary` | 200 | **200** | 11,342.7 ms | **PASS** |
| `GET` | `/analytics/{project_id}/analytics/topics` | 200 | **200** | 92.3 ms | **PASS** |
| `GET` | `/analytics/{project_id}/analytics/competitors`| 200 | **200** | 20.4 ms | **PASS** |
| `GET` | `/analytics/{project_id}/analytics/keywords` | 200 | **200** | 31.3 ms | **PASS** |
| `GET` | `/analytics/{project_id}/analytics/publishing` | 200 | **200** | 15.0 ms | **PASS** |
| `GET` | `/analytics/{project_id}/analytics/gaps` | 200 | **200** | 5.8 ms | **PASS** |
| `GET` | `/projects/{project_id}/intelligence` | 200 | **200** | 1,528.9 ms | **PASS** |
| `GET` | `/projects/{project_id}/intelligence/history` | 200 | **200** | 1,709.6 ms | **PASS** |
| `GET` | `/projects/{project_id}/content` | 200 | **200** | 1,721.0 ms | **PASS** |

**Summary:** 21 of 21 endpoints returned expected status codes (100% pass rate).

---

## 2. Security & Access Control Verification

| Test Scenario | Request Configuration | Expected Behavior | Observed Result | Status |
| :--- | :--- | :--- | :--- | :---: |
| **Unauthenticated Request** | `GET /projects/{project_id}` without `Authorization` header | Return HTTP 401 Unauthorized | Returned `401 Unauthorized` | **PASS** |
| **Cross-Tenant IDOR Protection** | Request Project A with User B token | Deny access to private project | Returned `401 Unauthorized` | **PASS** |
| **SQL Injection Sanitization** | `GET /projects/.../posts?search=' OR 1=1 --` | Safely escape query parameters | Handled safely, returned 200 with filtered items | **PASS** |
| **Invalid Credentials** | `POST /auth/login` with bad password | Reject with 401 | Returned `401 Unauthorized` | **PASS** |
| **Short Password Validation** | `POST /auth/register` with `password="short"` | Reject with 422 Unprocessable Entity | Returned `422 Unprocessable Entity` | **PASS** |

---

## 3. Database Query & Performance Optimizations Implemented

1. **Competitor Roster Eager Loading:**
   - *Previous:* `get_competitors` issued `select(ProjectCompetitor)` without joins. For 61 competitors, 62 roundtrips were issued across the cloud network to fetch each competitor's business profile.
   - *Optimization:* Added `options(joinedload(ProjectCompetitor.business))` in `backend/app/repositories/project_repo.py`.
   - *Result:* Reduced roundtrips from 62 to 1 single SQL join; latency dropped from >15s timeout to 1.7s.

2. **Scrape Run History Eager Loading:**
   - *Previous:* `get_runs_for_project` lazy-loaded `competitor_runs` and each competitor's `business` profile, resulting in up to 200 queries per request.
   - *Optimization:* Added `options(selectinload(ScrapeRun.competitor_runs).joinedload(ScrapeRunCompetitor.business))` in `backend/app/repositories/scrape_repo.py`.
   - *Result:* Reduced query count from O(N*M) to 2 queries; latency reduced from timeout to 2.1s.
