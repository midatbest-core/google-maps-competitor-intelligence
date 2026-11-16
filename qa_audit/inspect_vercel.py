import requests
import re

js = requests.get('https://roster-iq-delta.vercel.app/assets/index-CNtR8ZxM.js').text
routes = set(re.findall(r'path:\s*["\'](/[^"\']*)["\']', js))
print('Routes in Vercel bundle:', sorted(list(routes)))

texts = set(re.findall(r'["\']([A-Z][a-zA-Z0-9\s]{3,25})["\']', js))
relevant = [t for t in texts if any(w in t.lower() for w in ['competitor', 'roster', 'worker', 'shift', 'employee', 'google', 'scrape'])]
print('Relevant keywords in bundle:', relevant[:20])
