import os
import sys

os.environ['APP_ENV'] = 'production'
os.environ['DATABASE_URL'] = 'postgresql+psycopg://user:pass@host:5432/db'
os.environ['REDIS_URL'] = 'redis://localhost:6379'
os.environ['SECRET_KEY'] = 'test-secret-key-32-characters-long!!'
os.environ['GOOGLE_PLACES_API_KEY'] = 'test-places-key'
os.environ['AI_PROVIDER'] = 'fake'
os.environ['CORS_ORIGINS'] = '["https://comp-intel.vercel.app"]'

sys.path.insert(0, 'backend')
from app.main import app
from starlette.testclient import TestClient

client = TestClient(app)
res = client.get('/health')
print('Health endpoint status:', res.status_code)
print('Health endpoint body:', res.json())
