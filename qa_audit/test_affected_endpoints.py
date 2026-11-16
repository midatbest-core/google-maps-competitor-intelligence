import requests
import json

origin = 'https://google-maps-competitor-intelligence.onrender.com'
backend = 'https://comp-intel-api-mehe.onrender.com'

# Step 1: Login
login_url = f"{backend}/auth/login"
login_payload = {
    "email": "adisshinde05@gmail.com",
    "password": "safe-test-password" # Let's test safe-test-password and 12345678
}

print(f"Attempting login at {login_url}...")
token = None
for pwd in ["12345678", "safe-test-password"]:
    r = requests.post(
        login_url,
        json={"email": "adisshinde05@gmail.com", "password": pwd},
        headers={"Origin": origin, "Content-Type": "application/json"}
    )
    print(f"Login with pwd '{pwd}' -> Status: {r.status_code}")
    print(f"  CORS Header: {r.headers.get('access-control-allow-origin')}")
    print(f"  Response: {r.text[:200]}")
    if r.status_code == 200:
        token = r.json().get("access_token")
        break

if not token:
    print("Failed to obtain token!")
    exit(1)

print(f"\nGot token: {token[:15]}...")
headers = {
    "Origin": origin,
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# Check user's projects
r_proj = requests.get(f"{backend}/projects", headers=headers)
print(f"\nGET /projects -> Status: {r_proj.status_code}")
print(f"  CORS Header: {r_proj.headers.get('access-control-allow-origin')}")
print(f"  Projects Response: {r_proj.text[:250]}")

projects = r_proj.json() if r_proj.status_code == 200 else []
if not projects:
    print("No projects found!")
    exit(0)

project_id = projects[0]["id"]
print(f"\nUsing project_id: {project_id}")

# Test affected endpoints
endpoints_to_test = [
    ("GET", f"/projects/{project_id}/competitors", None),
    ("GET", f"/projects/{project_id}/discovery-runs", None),
    ("GET", f"/projects/{project_id}/discovery-candidates", None),
    ("GET", f"/projects/{project_id}/scrape-runs", None),
    ("POST", f"/projects/{project_id}/discovery-candidates/bulk-select", {"candidate_ids": []}),
    ("POST", f"/projects/{project_id}/scrape", {})
]

for method, path, data in endpoints_to_test:
    url = backend + path
    print(f"\n--- Testing {method} {path} ---")
    try:
        if method == "GET":
            res = requests.get(url, headers=headers, timeout=15)
        else:
            res = requests.post(url, headers=headers, json=data, timeout=15)
        print(f"Status: {res.status_code}")
        print(f"CORS Header: {res.headers.get('access-control-allow-origin')}")
        print(f"Response: {res.text[:300]}")
    except Exception as e:
        print(f"Request failed: {e}")
