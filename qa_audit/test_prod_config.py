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
from app.core.config import Settings
s = Settings()
print('SUCCESS: Production configuration validated cleanly!')
print('APP_ENV:', s.APP_ENV)
print('CORS_ORIGINS:', s.CORS_ORIGINS)
