FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including Playwright browsers
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium
RUN playwright install-deps chromium

COPY backend/ .

# Set python path
ENV PYTHONPATH=/app

CMD ["sh", "-c", "set -x; echo PATH=$PATH; which python; which alembic; which uvicorn; python --version; alembic --version; PYTHONUNBUFFERED=1 alembic upgrade head && PYTHONUNBUFFERED=1 uvicorn app.main:app --host 0.0.0.0 --port 8000"]
