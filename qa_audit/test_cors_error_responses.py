import os
import sys

os.environ['APP_ENV'] = 'production'
os.environ['DATABASE_URL'] = 'postgresql+psycopg://user:pass@localhost:5432/db'
os.environ['REDIS_URL'] = 'redis://localhost:6379'
os.environ['SECRET_KEY'] = 'a' * 32
os.environ['GOOGLE_PLACES_API_KEY'] = 'test-key'
os.environ['AI_PROVIDER'] = 'fake'
os.environ['CORS_ORIGINS'] = '["https://google-maps-competitor-intelligence.onrender.com"]'

sys.path.insert(0, 'backend')
from app.main import app
from starlette.testclient import TestClient

client = TestClient(app)
origin = "https://google-maps-competitor-intelligence.onrender.com"

# Test 1: OPTIONS Preflight
res = client.options("/projects/test-proj/discovery-candidates/bulk-select", headers={
    "Origin": origin,
    "Access-Control-Request-Method": "POST",
    "Access-Control-Request-Headers": "authorization,content-type"
})
print(f"1. OPTIONS Preflight: status={res.status_code}, CORS={res.headers.get('access-control-allow-origin')}")
assert res.status_code == 200
assert res.headers.get("access-control-allow-origin") == origin

# Test 2: 401 Unauthorized
res = client.get("/projects", headers={"Origin": origin})
print(f"2. 401 Unauthorized: status={res.status_code}, CORS={res.headers.get('access-control-allow-origin')}")
assert res.status_code == 401
assert res.headers.get("access-control-allow-origin") == origin

# Test 3: 422 Validation Error
res = client.post("/auth/login", json={"email": "not-an-email"}, headers={"Origin": origin})
print(f"3. 422 Validation Error: status={res.status_code}, CORS={res.headers.get('access-control-allow-origin')}")
assert res.status_code == 422
assert res.headers.get("access-control-allow-origin") == origin

# Test 4: Disallowed Origin
res = client.get("/health", headers={"Origin": "https://unauthorized-domain.com"})
print(f"4. Disallowed Origin: status={res.status_code}, CORS={res.headers.get('access-control-allow-origin')}")
assert res.headers.get("access-control-allow-origin") is None

print("\nALL CORS ERROR AND PREFLIGHT VERIFICATION CHECKS PASSED!")
