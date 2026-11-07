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

    async def generate_combined_intelligence(self, prompt: str):
        if self.should_fail:
            raise ValueError("Fake provider failure simulated.")
        from app.schemas.analysis import (
            CombinedIntelligenceOutput,
            CompetitorInsightItem,
            MarketingIntelligenceSection,
            StrategicDisconnect,
            ActionableRecommendation,
            SupportingEvidence,
            ContentIdeaItem,
        )
        output = CombinedIntelligenceOutput(
            competitor_insights=[
                CompetitorInsightItem(
                    competitor_name="Competitor Central",
                    strengths=["Live entertainment", "Vibrant ambience"],
                    weaknesses=["Slow weekend service", "Crowded seating"],
                    customer_sentiment="Mixed (68% positive, 32% negative)",
                    recurring_complaints=["Wait time over 45 minutes on Saturday evenings", "Orders delayed"],
                    marketing_patterns=["Heavily promotes weekend live music and signature drinks"],
                    positioning="Nightlife & Entertainment Hub"
                )
            ],
            marketing_intelligence=MarketingIntelligenceSection(
                frequently_promoted_topics=["Weekend Events", "Happy Hour Specials", "Live Acoustic"],
                common_offers=["2-for-1 cocktails before 7 PM", "Free appetizer with entree"],
                posting_frequency="3-4 posts per week, predominantly Thursday to Saturday",
                content_formats=["Image with short caption", "Flyer announcement"],
                effective_ctas=["Book a table", "Call now"]
            ),
            strategic_disconnects=[
                StrategicDisconnect(
                    competitor_name="Competitor Central",
                    advertised_promise="Promotes seamless, vibrant weekend live music experiences in posts",
                    customer_reality="Customer reviews repeatedly complain of 45+ minute wait times and delayed table service during live sets",
                    opportunity="Position our venue for swift reservation seating, expedited service, and zero-wait dining before or during events",
                    recommended_action="Run a targeted campaign highlighting 'Guaranteed Seating & On-Time Service' with fast-track online table reservations"
                )
            ],
            business_opportunities=[
                "Capturing weekend dinner diners frustrated by neighboring long wait times",
                "Promoting weekday business lunch express specials where competitors have no presence",
                "Catering and group reservation packages"
            ],
            actionable_recommendations=[
                ActionableRecommendation(
                    title="Launch 'Zero-Wait Weekend Dining' Campaign",
                    description="Highlight guaranteed reservation times and fast table turnaround in marketing posts to directly contrast competitor wait complaints.",
                    category="marketing",
                    rationale="Directly targets the primary recurring complaint identified in competitor reviews.",
                    priority="HIGH",
                    supporting_evidence=[
                        SupportingEvidence(
                            source_type="review",
                            business_name="Competitor Central",
                            quote_or_summary="Reviewers consistently report waiting over 45 minutes for a table on Friday and Saturday nights."
                        ),
                        SupportingEvidence(
                            source_type="post",
                            business_name="Competitor Central",
                            quote_or_summary="Competitor posts push 'Packed Saturday Nights' without addressing capacity limitations."
                        )
                    ]
                )
            ],
            content_ideas=[
                ContentIdeaItem(
                    title="Skip the Line, Savor the Night",
                    hook="Tired of waiting 45 minutes for a weekend table? We reserve your seat and your peace of mind.",
                    angle="Directly addresses the weekend wait friction experienced at competitor venues.",
                    suggested_format="Image with caption & Book Now CTA",
                    target_audience="Couples and small groups looking for reliable weekend dinner reservations",
                    evidence_backed_reason="Competitor Central reviews show 6 reviews in last 30 days citing extreme weekend wait times."
                )
            ]
        )
        return output, {"raw": "{}"}
