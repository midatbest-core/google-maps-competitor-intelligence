import os
import sys

sys.path.insert(0, 'backend')
from app.core.config import Settings
from pydantic import ValidationError

def test_scenario(name, env_overrides):
    base_env = {
        'APP_ENV': 'production',
        'DATABASE_URL': 'postgresql+psycopg://user:pass@localhost:5432/db',
        'REDIS_URL': 'redis://localhost:6379/0',
        'SECRET_KEY': 'a' * 32,
        'GOOGLE_PLACES_API_KEY': 'places_api_key_123',
        'AI_PROVIDER': 'gemini',
        'GEMINI_API_KEY': 'gemini_api_key_123',
        'CORS_ORIGINS': '["https://competitor-intel.vercel.app"]'
    }
    for k, v in base_env.items():
        os.environ[k] = v
    for k, v in env_overrides.items():
        os.environ[k] = v
            
    try:
        s = Settings(_env_file=None)
        print(f"[PASS] {name}: Successfully validated (APP_ENV={s.APP_ENV})")
        return "PASS"
    except (ValidationError, ValueError) as e:
        first_err = str(e).split('\n')[0]
        if 'Value error' in str(e):
            first_err = [line.strip() for line in str(e).split('\n') if 'Value error' in line][0]
        print(f"[REJECTED] {name}: {first_err}")
        return "REJECTED"
    except Exception as e:
        print(f"[ERROR] {name}: Unexpected error {type(e).__name__}: {e}")
        return "ERROR"

print("=== TESTING CONFIGURATION SCENARIOS (WITH _env_file=None) ===")

test_scenario("1. Valid Production Config", {})
test_scenario("2. Missing Google Places API Key", {'GOOGLE_PLACES_API_KEY': ''})
test_scenario("3a. Non-Postgres Database URL (sqlite)", {'DATABASE_URL': 'sqlite:///test.db'})
test_scenario("3b. Non-Postgres Database URL (mysql)", {'DATABASE_URL': 'mysql://user:pass@localhost/db'})
test_scenario("4a. Non-Redis URL (http)", {'REDIS_URL': 'http://localhost:6379'})
test_scenario("5a. Invalid CORS Origin (localhost)", {'CORS_ORIGINS': '["http://localhost:5173"]'})
test_scenario("5b. Invalid CORS Origin (non-HTTPS)", {'CORS_ORIGINS': '["http://competitor-intel.vercel.app"]'})
test_scenario("6. Missing Gemini API Key (when AI_PROVIDER=gemini)", {'AI_PROVIDER': 'gemini', 'GEMINI_API_KEY': ''})
test_scenario("7. Development Configuration (APP_ENV=development)", {
    'APP_ENV': 'development',
    'DATABASE_URL': 'postgresql+psycopg://user:pass@localhost:5432/db',
    'REDIS_URL': 'redis://localhost:6379/0',
    'GOOGLE_PLACES_API_KEY': '',
    'AI_PROVIDER': 'fake',
    'GEMINI_API_KEY': '',
    'CORS_ORIGINS': '["http://localhost:5173"]'
})
