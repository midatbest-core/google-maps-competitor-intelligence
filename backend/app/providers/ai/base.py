from typing import Any, Dict, List
import abc
from app.schemas.analysis import AIAnalysisResult

class AIProvider(abc.ABC):
    """Base class for AI providers (Gemini, OpenAI, etc.)."""
    
    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        pass
        
    @property
    @abc.abstractmethod
    def model_name(self) -> str:
        pass

    @abc.abstractmethod
    async def analyze_post(self, prompt: str, text: str) -> tuple[AIAnalysisResult, dict]:
        """
        Analyzes a post using the given prompt and returns a structured AIAnalysisResult
        and the raw response dictionary.
        """
        pass

    @abc.abstractmethod
    async def generate_content(self, prompt: str) -> tuple[str, dict]:
        """
        Generates content using the given prompt and returns the raw text
        and the raw response dictionary.
        """
        pass
