import pytest

from app.core.arq import redis_settings_from_url
from app.workers.main import WorkerSettings


def test_rediss_url_enables_tls_and_preserves_credentials():
    redis = redis_settings_from_url(
        "rediss://default:p%40ss@example.upstash.io:6380/2",
        conn_timeout=3,
        conn_retries=4,
    )

    assert redis.host == "example.upstash.io"
    assert redis.port == 6380
    assert redis.database == 2
    assert redis.username == "default"
    assert redis.password == "p@ss"
    assert redis.ssl is True
    assert redis.conn_timeout == 3
    assert redis.conn_retries == 4


def test_plain_redis_url_does_not_enable_tls():
    redis = redis_settings_from_url("redis://localhost:6379/0")

    assert redis.host == "localhost"
    assert redis.ssl is False
    assert redis.database == 0


@pytest.mark.parametrize(
    "url, message",
    [
        ("https://example.upstash.io", "redis:// or rediss://"),
        ("rediss:///0", "hostname"),
        ("rediss://example.upstash.io/not-a-number", "integer"),
    ],
)
def test_invalid_redis_urls_fail_without_localhost_fallback(url, message):
    with pytest.raises(ValueError, match=message):
        redis_settings_from_url(url)


def test_worker_is_manual_only_and_has_no_scheduler():
    assert not hasattr(WorkerSettings, "cron_jobs")
