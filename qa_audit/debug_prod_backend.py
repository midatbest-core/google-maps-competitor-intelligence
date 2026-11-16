import requests
import time

origin = 'https://google-maps-competitor-intelligence.onrender.com'
backend = 'https://comp-intel-api-mehe.onrender.com'

print(f"Testing backend: {backend}")
print(f"Testing with Origin: {origin}\n")

endpoints = ['/health', '/ready', '/docs', '/openapi.json']
for ep in endpoints:
    t0 = time.time()
    try:
        r = requests.get(backend + ep, headers={'Origin': origin}, timeout=15)
        cors = r.headers.get('access-control-allow-origin')
        print(f"GET {ep} -> Status: {r.status_code} ({time.time()-t0:.2f}s)")
        print(f"  Access-Control-Allow-Origin: {cors}")
        print(f"  Body preview: {r.text[:150]}")
    except Exception as e:
        print(f"GET {ep} -> FAILED ({time.time()-t0:.2f}s): {e}")

print("\n--- Testing OPTIONS Preflight ---")
preflight_endpoints = [
    '/health',
    '/projects/235a2d92-9c65-4fe9-af13-a38275ba89bd/discovery-candidates/bulk-select',
    '/projects/235a2d92-9c65-4fe9-af13-a38275ba89bd/scrape',
    '/projects/235a2d92-9c65-4fe9-af13-a38275ba89bd/competitors'
]

for ep in preflight_endpoints:
    t0 = time.time()
    try:
        r = requests.options(
            backend + ep,
            headers={
                'Origin': origin,
                'Access-Control-Request-Method': 'POST',
                'Access-Control-Request-Headers': 'authorization,content-type'
            },
            timeout=15
        )
        print(f"OPTIONS {ep} -> Status: {r.status_code} ({time.time()-t0:.2f}s)")
        print(f"  Access-Control-Allow-Origin: {r.headers.get('access-control-allow-origin')}")
        print(f"  Access-Control-Allow-Methods: {r.headers.get('access-control-allow-methods')}")
        print(f"  Access-Control-Allow-Headers: {r.headers.get('access-control-allow-headers')}")
    except Exception as e:
        print(f"OPTIONS {ep} -> FAILED ({time.time()-t0:.2f}s): {e}")
