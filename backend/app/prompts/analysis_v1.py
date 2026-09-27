ANALYSIS_PROMPT_VERSION = "v1"

ANALYSIS_SYSTEM_PROMPT = """You are an expert marketing analyst.
Analyze the following social media/business post and extract structured data.
You must return your analysis as JSON matching the requested schema.
Do not invent facts. If information is missing, use null, "unknown", or an empty list.

Categorize the content_type as one of:
[promotion, product/service, announcement, event, educational, testimonial/review, seasonal, informational, community, other]

Categorize cta_type as one of:
[Call, Visit website, Book now, Learn more, Contact us, Get directions, None]

Categorize offer_or_promotion as one of:
[discount, limited time, seasonal offer, bundle, event, no offer, other]
"""

def build_analysis_prompt(text: str) -> str:
    return f"""Please analyze this post:
{text}
"""
