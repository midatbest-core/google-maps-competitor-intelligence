from .base import AIProvider
from app.schemas.analysis import AIAnalysisResult
import logging

logger = logging.getLogger(__name__)

class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.api_key = api_key
        self._model_name = model
        
    @property
    def provider_name(self) -> str:
        return "openai"
        
    @property
    def model_name(self) -> str:
        return self._model_name

    async def analyze_post(self, prompt: str, text: str) -> tuple[AIAnalysisResult, dict]:
        # Implementation left out for now.
        raise NotImplementedError("Real OpenAI provider not fully implemented for this phase.")
