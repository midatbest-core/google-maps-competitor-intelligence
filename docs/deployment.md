# Deployment Guide

This guide explains how to deploy the Google Maps Competitor Intelligence Tool into a production environment.

## Architecture Topology

The application is composed of 4 main services:
1. **Frontend**: React SPA built with Vite (serves static assets).
2. **API Backend**: FastAPI application serving REST endpoints.
3. **Database**: PostgreSQL (requires `pgvector` extension) for relational data and embeddings.
4. **Queue/Worker**: Redis + ARQ for background scraping, intelligence analysis, and content generation.

## Prerequisites
- Docker & Docker Compose
- Or: Node.js 18+, Python 3.11+, PostgreSQL 15+ with pgvector, Redis 7+

## Environment Variables

Copy `.env.example` to `.env` and fill in the production values:

```env
APP_ENV=production
LOG_LEVEL=INFO
DATABASE_URL=postgresql://user:password@db:5432/comp_intel
REDIS_URL=redis://redis:6379/0

# Storage (use local for single-instance, S3 for multi-instance)
STORAGE_PROVIDER=local
LOCAL_STORAGE_DIR=/app/media

# AI Providers
AI_PROVIDER=gemini
GEMINI_API_KEY=your_key_here

# Security
SECRET_KEY=generate_a_secure_random_key
CORS_ORIGINS=["https://your-frontend-domain.com"]
```

## Running via Docker Compose

```bash
docker compose up -d --build
```

This will spin up:
- `db`: PostgreSQL with pgvector.
- `redis`: Redis server.
- `api`: Uvicorn serving FastAPI on port 8000.
- `worker`: ARQ worker running scheduled tasks and background jobs.

## Migrations

Before the application is fully usable, run the database migrations:

```bash
docker compose exec api alembic upgrade head
```

## Frontend Deployment

Build the frontend static assets:

```bash
cd frontend
npm install
npm run build
```

Serve the contents of the `frontend/dist` folder using a CDN, Nginx, or any static file host. Ensure `VITE_API_URL` is configured to point to your deployed FastAPI backend during build.

## Scalability Notes
- **Storage**: By default, `STORAGE_PROVIDER=local` writes to the local filesystem. For horizontal scaling, implement an S3 Storage Provider.
- **Scraper Limits**: Scaling workers is possible, but Google Maps IP-bans aggressively. Route scraper workers through residential proxies if deploying multiple nodes.
