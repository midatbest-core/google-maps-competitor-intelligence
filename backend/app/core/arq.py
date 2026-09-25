from arq import create_pool
from arq.connections import RedisSettings
from app.core.config import settings

async def get_redis_pool():
    # Parse redis url
    # e.g., redis://localhost:6379/0
    import urllib.parse
    parsed = urllib.parse.urlparse(settings.REDIS_URL)
    host = parsed.hostname or "localhost"
    port = parsed.port or 6379
    database = int(parsed.path.strip("/")) if parsed.path and parsed.path.strip("/") else 0
    password = parsed.password
    
    redis_settings = RedisSettings(host=host, port=port, database=database, password=password)
    return await create_pool(redis_settings)
