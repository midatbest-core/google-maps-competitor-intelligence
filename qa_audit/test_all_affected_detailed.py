import requests
import json
import time

origin = 'https://google-maps-competitor-intelligence.onrender.com'
backend = 'https://comp-intel-api-mehe.onrender.com'

# Login to get token
r_login = requests.post(
    f"{backend}/auth/login",
    json={"email": "adisshinde05@gmail.com", "password": "safe-test-password"},
    headers={"Origin": origin}
)
if r_login.status_code != 200:
    r_login = requests.post(
        f"{backend}/auth/login",
        json={"email": "adisshinde05@gmail.com", "password": "12345678"},
        headers={"Origin": origin}
    )

token = r_login.json()["access_token"]
headers = {
    "Origin": origin,
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# Get project
r_proj = requests.get(f"{backend}/projects", headers=headers)
projects = r_proj.json()
proj_id = projects[0]["id"]
print(f"Testing with Project ID: {proj_id}\n")

tests = [
    ("GET", f"/projects/{proj_id}/discovery-runs", None),
    ("GET", f"/projects/{proj_id}/discovery-candidates", None),
    ("POST", f"/projects/{proj_id}/discovery-candidates/bulk-select", {"candidate_ids": []}),
    ("GET", f"/projects/{proj_id}/competitors", None),
    ("GET", f"/projects/{proj_id}/scrape-runs", None),
    ("POST", f"/projects/{proj_id}/scrape", {}),
]

for method, path, data in tests:
    url = backend + path
    t0 = time.time()
    try:
        if method == "GET":
            res = requests.get(url, headers=headers, timeout=25)
        else:
            res = requests.post(url, headers=headers, json=data, timeout=25)
        dt = time.time() - t0
        cors = res.headers.get("access-control-allow-origin")
        print(f"[{method}] {path} -> {res.status_code} in {dt:.2f}s | CORS: {cors}")
        if res.status_code != 200:
            print(f"   Response Body: {res.text[:300]}")
        else:
            print(f"   Items returned: {len(res.json()) if isinstance(res.json(), list) else 'dict'}")
    except requests.exceptions.Timeout:
        print(f"[{method}] {path} -> TIMEOUT after {time.time()-t0:.2f}s (No response received)")
    except Exception as e:
        print(f"[{method}] {path} -> FAILED after {time.time()-t0:.2f}s: {e}")
