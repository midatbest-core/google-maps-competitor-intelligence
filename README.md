# Google Maps Competitor Intelligence & Studio

An AI-native SaaS platform for scouting, scraping, analyzing, and outperforming local business competitors on Google Maps.

---

## ⚡ Quick Start: Running the Project Locally

You will need **Python 3.11+** and **Node.js 18+**.

### 1. Start the Backend (Terminal 1)

#### On Windows (PowerShell):
```powershell
# From the project root
.\venv\Scripts\activate
$env:APP_ENV="development"
$env:PYTHONPATH="backend"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

#### On macOS / Linux (Bash):
```bash
# From the project root
source venv/bin/activate
export APP_ENV="development"
export PYTHONPATH="backend"
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

> The API will be live at: **`http://127.0.0.1:8000`**  
> Interactive API Docs (Swagger): **`http://127.0.0.1:8000/docs`**

---

### 2. Start the Frontend (Terminal 2)

```bash
# Navigate to frontend
cd frontend

# Install dependencies (first time only)
npm install

# Start Vite development server
npm run dev
```

> The Web App will be live at: **`http://127.0.0.1:5173`**  
> (Vite automatically proxies `/api/*` requests to port `8000`).

---

### 3. Demo Login Credentials

* **Email:** `adisshinde05@gmail.com`
* **Password:** `12345678`

---

## 🚀 Running with Docker Compose (Full Stack)

To run the entire stack (PostgreSQL + pgvector, Redis, API, and background workers):

```bash
docker-compose up --build
```

---

## 🧭 Application Architecture & Workflow

The platform enforces a clean, decoupled 4-step workflow:

```
[ 1. Discovery Scout ] ──▶ [ 2. Competitor Roster ] ──▶ [ 3. Scraping Pipeline ] ──▶ [ 4. AI Studio ]
  Google Places API           Select / Add Directly       Playwright Scraper          Content Strategy &
  Radius in km (2-50km)       Designate Own Business      Posts & Reviews             Gemini Generator
```

### 1. Discovery Scout (`/projects/:id/discovery`)
* **Decoupled from Scraping:** Finds candidates without auto-triggering scraping.
* Select search range in kilometers (presets: **2 km, 5 km, 10 km, 25 km, 50 km** + slider).
* Real-time radar scan with live polling when a scout run is in progress.
* Multi-candidate selection with sticky floating action bar to add competitors in bulk.

### 2. Competitor Roster (`/projects/:id/competitors`)
* Manage your project competitors roster.
* Designate **Your Primary Business** (used as baseline to detect topic & keyword gaps).
* Add direct competitors via Google Maps URL or name/address.

### 3. Scraping Pipeline (`/projects/:id/scraping`)
* Gathers social/Google updates and customer reviews strictly for your competitor roster.
* Real-time live run status card with animated pulse indicators and auto-polling.
* Windows-optimized Playwright runner executing inside dedicated Proactor loops.
* Deep review extraction with dynamic DOM scroll container traversal.

### 4. Intelligence & Studio (`/projects/:id/strategy` & `/generate`)
* **Topic & Keyword Gap Analytics:** Compares competitor content themes against your business to find market gaps.
* **1-Click Idea Generator:** Direct bridge from market opportunities into the AI Content Studio.
* **Content Generation:** Produces hooks, offers, and full Google updates grounded in real customer reviews and competitor positioning.

---

## 🛠️ Testing & Verification

Run the comprehensive backend test suite:

```bash
.\venv\Scripts\python -m pytest backend/tests
```

Build the production frontend bundle:

```bash
cd frontend
npm run build
```

---

## 📁 Key Environment Variables (`.env`)

```ini
APP_ENV=development
DATABASE_URL=postgresql://user:password@localhost:5432/comp_intel
SECRET_KEY=your_super_secret_jwt_key
AI_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
GOOGLE_PLACES_API_KEY=your_google_places_api_key
```
