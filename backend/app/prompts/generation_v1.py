import json

PROMPT_VERSION = "v1"

IDEA_PROMPT_TEMPLATE = """
You are an expert Google Maps marketing strategist.
Your task is to generate {count} unique content ideas for a business on Google Maps.
Use the provided repository context, but DO NOT copy competitor wording exactly. Use competitors to identify topic gaps and publishing patterns.

Business Context:
{business_context}

Competitor & Project Intelligence:
{intelligence_context}

User Constraints:
Topic: {topic}
Content Type: {content_type}
Keywords: {keywords}
CTA Style: {cta_style}
Campaign/Offer Context: {campaign_context}

Output your response as a strictly valid JSON array of objects, where each object matches this structure:
{{
  "topic": "The core topic of the idea",
  "title": "A catchy title",
  "body": "A brief summary of what the post would be about",
  "keywords": ["keyword1", "keyword2"],
  "cta": "The suggested Call to Action",
  "offer": "Any offer or promotion (or null)",
  "image_concept": "A description of the image to attach",
  "content_type": "Event, Offer, Update, etc.",
  "rationale": "Why this is a good idea based on the intelligence context and content gaps"
}}
"""

FULL_CONTENT_PROMPT_TEMPLATE = """
You are an expert Google Maps marketing strategist.
Your task is to generate a complete, publishable Google Maps update draft.
Use the provided repository context, but DO NOT copy competitor wording exactly.
Ensure the content is engaging, professionally written, and optimized for local SEO using the provided keywords.

Business Context:
{business_context}

Competitor & Project Intelligence:
{intelligence_context}

User Constraints:
Topic: {topic}
Content Type: {content_type}
Keywords: {keywords}
CTA Style: {cta_style}
Campaign/Offer Context: {campaign_context}

Output your response as a strictly valid JSON object that matches this structure:
{{
  "topic": "The core topic of the post",
  "title": "A catchy title",
  "body": "The complete, ready-to-publish body of the post",
  "keywords": ["keyword1", "keyword2"],
  "cta": "The specific Call to Action text (e.g. Call Now, Learn More)",
  "offer": "Any specific offer or promotion terms (or null)",
  "image_concept": "A detailed description of the image to attach",
  "content_type": "Event, Offer, Update, etc.",
  "rationale": "Why this specific post copy will perform well"
}}
"""
