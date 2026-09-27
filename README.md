# Google Maps Competitor Intelligence Tool

An intelligent SaaS platform for managing, scraping, analyzing, and outperforming competitors on Google Maps.

## Features
- **Project & Workspace Isolation**: Multi-tenant architecture securely isolating data.
- **Google Maps Scraping**: Automated, resilient scraping of business posts and updates using Playwright.
- **Competitor Discovery**: Semantic and geospatial discovery of hidden competitors.
- **AI Intelligence**: Automated content gap analysis, topic frequency tracking, and posting cadence observation.
- **Content Studio**: Generates high-converting, uniquely formatted Google Maps updates using Gemini/OpenAI models.
- **Duplicate Protection**: Exact and semantic embedding checks prevent publishing similar content twice.
- **Automated Scheduling**: Persistent background ARQ workers automatically crawl targets on a schedule.

## Technology Stack
- **Backend**: FastAPI, SQLAlchemy, Alembic, PostgreSQL + pgvector
- **Frontend**: React, Vite, TypeScript
- **Queue/Workers**: Redis + ARQ
- **AI**: Gemini, OpenAI, sentence-transformers (mockable for dev)
- **Scraping**: Playwright

## Quick Start (Local Development)

### 1. Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Ensure `DATABASE_URL` is set to your local DB or `sqlite:///./test.db` for quick testing.

### 3. Migrations
```bash
cd backend
alembic upgrade head
```

### 4. Run Services
Start API:
```bash
cd backend
uvicorn app.main:app --reload
```

Start ARQ Worker (requires Redis):
```bash
cd backend
arq app.workers.main.WorkerSettings
```

Start Frontend:
```bash
cd frontend
npm install
npm run dev
```

## Production Deployment
See [docs/deployment.md](docs/deployment.md) for Docker deployment strategies, observability, and scaling rules.

## Known Limitations
- The current Google Maps scraper uses Chromium and may be subjected to CAPTCHAs. Manual intervention pauses are built-in, but automated proxy rotation is not configured.
- Local storage provider is enabled by default. For multi-node deployments, external object storage (e.g., S3) should be implemented.
