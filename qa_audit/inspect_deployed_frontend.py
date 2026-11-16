import requests
import re

html = requests.get('https://google-maps-competitor-intelligence.onrender.com').text
scripts = re.findall(r'src=["\'](/assets/[^"\']+\.js)["\']', html)
print('Frontend scripts:', scripts)
for s in scripts:
    js = requests.get(f'https://google-maps-competitor-intelligence.onrender.com{s}').text
    print('Bundle size:', len(js))
    urls = set(re.findall(r'https?://[a-zA-Z0-9\.\-_]+onrender\.com[^\s"\'\`)]*', js))
    print('Render URLs in frontend bundle:', urls)
    base_urls = set(re.findall(r'baseURL:[^,}]+', js))
    print('baseURL in frontend bundle:', base_urls)
