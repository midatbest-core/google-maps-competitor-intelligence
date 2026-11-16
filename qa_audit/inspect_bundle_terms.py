import requests

js = requests.get('https://roster-iq-delta.vercel.app/assets/index-CNtR8ZxM.js').text
print('Bundle size:', len(js))
print('Sample text:', js[:500])

for term in ['competitor', 'scrape', 'review', 'roster', 'employee', 'login', 'schedule', 'shift', 'intelligence']:
    count = js.lower().count(term)
    print(f'Count of "{term}": {count}')
