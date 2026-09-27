from .base import AIProvider
from .gemini import GeminiProvider
from .openai import OpenAIProvider
from .fake import FakeAIProvider
from app.core.config import settings

def get_ai_provider() -> AIProvider:
    """Factory to get the AI provider based on settings."""
    if settings.APP_ENV == "test":
        return FakeAIProvider()
        
    if settings.AI_PROVIDER == "gemini":
        return GeminiProvider(api_key=settings.GEMINI_API_KEY)
    elif settings.AI_PROVIDER == "openai":
        return OpenAIProvider(api_key=settings.OPENAI_API_KEY)
    elif settings.AI_PROVIDER == "fake":
        return FakeAIProvider()
    else:
        raise ValueError(f"Unknown AI provider configured: {settings.AI_PROVIDER}")
