from .base import AIProvider
from app.schemas.analysis import AIAnalysisResult
import json
import logging

logger = logging.getLogger(__name__)

class GeminiProvider(AIProvider):
    def __init__(self, api_key: str, model: str = "gemini-1.5-pro"):
        self.api_key = api_key
        self._model_name = model

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model_name

    async def analyze_post(self, prompt: str, text: str) -> tuple[AIAnalysisResult, dict]:
        # Implementation left out for now.
        # This would use the google-genai library and Structured Outputs
        raise NotImplementedError("Real Gemini provider not fully implemented for this phase.")

    async def analyze_reviews(self, prompt: str, reviews_text: str):
        import google.generativeai as genai
        import json
        from app.schemas.analysis import AIReviewAnalysisResult

        full_prompt = f"{prompt}\n\nReviews:\n{reviews_text}"

        model = genai.GenerativeModel(self.model_name)
        response = model.generate_content(
            full_prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=AIReviewAnalysisResult
            )
        )

        raw_text = response.text
        try:
            parsed = AIReviewAnalysisResult.model_validate_json(raw_text)
            return parsed, {"raw": raw_text}
        except Exception as e:
            # Fallback if strict schema parsing fails
            raise ValueError(f"Failed to parse Gemini JSON: {e}")
