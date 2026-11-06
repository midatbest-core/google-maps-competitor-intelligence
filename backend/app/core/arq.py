from arq import create_pool
from arq.connections import RedisSettings
from app.core.config import settings
from urllib.parse import unquote, urlsplit


def redis_settings_from_url(
    redis_url: str,
    *,
    conn_timeout: int = 1,
    conn_retries: int = 0,
) -> RedisSettings:
    """Parse a Redis URI without silently weakening TLS or changing hosts."""
    parsed = urlsplit(redis_url)
    if parsed.scheme not in {"redis", "rediss"}:
        raise ValueError("REDIS_URL must use redis:// or rediss://")
    if not parsed.hostname:
        raise ValueError("REDIS_URL must include a hostname")

    database_text = parsed.path.strip("/")
    try:
        database = int(database_text) if database_text else 0
    except ValueError as exc:
        raise ValueError("REDIS_URL database must be an integer") from exc

    return RedisSettings(
        host=parsed.hostname,
        port=parsed.port or 6379,
        database=database,
        username=unquote(parsed.username) if parsed.username else None,
        password=unquote(parsed.password) if parsed.password else None,
        ssl=parsed.scheme == "rediss",
        conn_timeout=conn_timeout,
        conn_retries=conn_retries,
    )

async def get_redis_pool():
    return await create_pool(
        redis_settings_from_url(
            settings.REDIS_URL,
            conn_timeout=1,
            conn_retries=0,
        )
    )
