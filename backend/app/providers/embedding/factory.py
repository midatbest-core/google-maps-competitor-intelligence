from .base import EmbeddingProvider
from .fake import FakeEmbeddingProvider
from app.core.config import settings

def get_embedding_provider() -> EmbeddingProvider:
    if settings.APP_ENV == "test":
        return FakeEmbeddingProvider()
        
    if settings.EMBEDDING_PROVIDER == "fake":
        return FakeEmbeddingProvider()
        
    raise ValueError(f"Unknown embedding provider configured: {settings.EMBEDDING_PROVIDER}")
