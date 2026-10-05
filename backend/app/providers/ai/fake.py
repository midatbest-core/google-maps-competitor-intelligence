from .base import AIProvider
from app.schemas.analysis import AIAnalysisResult
import json

class FakeAIProvider(AIProvider):
    """A deterministic fake AI provider for testing."""
    
    def __init__(self, mock_response: AIAnalysisResult = None, should_fail: bool = False):
        self._mock_response = mock_response or AIAnalysisResult(
            topic="Test Topic",
            subtopic="Test Subtopic",
            keywords=["fake", "test"],
            content_type="other",
            cta_type="Learn more",
            offer_or_promotion="no offer",
            sentiment="neutral",
            summary="A test summary",
            confidence=0.99
        )
        self.should_fail = should_fail
        
    @property
    def provider_name(self) -> str:
        return "fake_provider"
        
    @property
    def model_name(self) -> str:
        return "fake_model"

    async def analyze_post(self, prompt: str, text: str) -> tuple[AIAnalysisResult, dict]:
        if self.should_fail:
            raise ValueError("Fake provider failure simulated.")
            
        raw = self._mock_response.model_dump()
        return self._mock_response, raw

    async def generate_content(self, prompt: str) -> tuple[str, dict]:
        if self.should_fail:
            raise ValueError("Fake provider failure simulated.")
            
        # Try to parse if it asks for JSON array (ideas) or object (full content)
        if "generate {count} unique content ideas" in prompt or "ideas" in prompt.lower():
            # mock array
            mock_res = [{
                "topic": "Fake Topic",
                "title": "Fake Title",
                "body": "Fake body",
                "keywords": ["fake"],
                "cta": "Fake CTA",
                "offer": None,
                "image_concept": "Fake Image",
                "content_type": "Update",
                "rationale": "Fake rationale"
            }]
            return json.dumps(mock_res), {"raw": "fake"}
            
        # mock object
        mock_res = {
            "topic": "Fake Topic",
            "title": "Fake Title",
            "body": "Fake body",
            "keywords": ["fake"],
            "cta": "Fake CTA",
            "offer": None,
            "image_concept": "Fake Image",
            "content_type": "Update",
            "rationale": "Fake rationale"
        }
        return json.dumps(mock_res), {"raw": "fake"}

    async def analyze_reviews(self, prompt: str, reviews_text: str):
        from app.schemas.analysis import AIReviewAnalysisResult, SentimentBreakdown
        res = AIReviewAnalysisResult(
            overall_sentiment="Positive",
            sentiment_breakdown=SentimentBreakdown(positive=80.0, neutral=10.0, negative=10.0),
            praise_themes=["Great service", "Friendly staff"],
            complaint_themes=["Long wait times"],
            pain_points=["Hard to find parking"],
            customer_needs=["Faster delivery"],
            frequently_mentioned_services=["Coffee", "Pastries"],
            strengths=["Quality of food"],
            weaknesses=["Expensive"],
            business_opportunities=["Catering"],
            recommended_actions=["Add more seating"]
        )
        return res, {"raw": "{}"}
