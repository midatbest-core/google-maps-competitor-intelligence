import logging
import json
from sqlalchemy.orm import Session
from typing import Optional, List, Dict
from datetime import datetime, timezone
import hashlib

from app.models.analysis import GeneratedContent, AIAnalysis, PostEmbedding
from app.models.project import Project
from app.models.profile import BusinessProfile
from app.schemas.generation import GenerationRequest, RegenerateRequest, AIStructuredOutput
from app.providers.ai.base import AIProvider
from app.providers.embedding.base import EmbeddingProvider
from app.prompts.generation_v1 import PROMPT_VERSION, IDEA_PROMPT_TEMPLATE, FULL_CONTENT_PROMPT_TEMPLATE
from app.services.similarity_service import SimilarityService
from app.services.analytics_service import AnalyticsService
from app.core.config import settings

from app.models.auth import Workspace

logger = logging.getLogger(__name__)

class GenerationService:
    def __init__(self, db: Session, ai_provider: AIProvider, embedding_provider: Optional[EmbeddingProvider] = None, similarity_service: Optional[SimilarityService] = None, workspace: Workspace = None):
        self.db = db
        self.ai_provider = ai_provider
        self.embedding_provider = embedding_provider
        self.similarity_service = similarity_service or SimilarityService(db)
        self.analytics_service = AnalyticsService(db, workspace)
        self.workspace = workspace
        
    def _verify_project(self, project_id: str):
        if not self.workspace:
            return
        project = self.db.query(Project).filter_by(id=project_id).first()
        if not project or project.workspace_id != self.workspace.id:
            raise ValueError("Not authorized to access this project")

    def request_generation(self, project_id: str, payload: GenerationRequest) -> List[GeneratedContent]:
        self._verify_project(project_id)
        project = self.db.query(Project).filter_by(id=project_id).first()
        if not project:
            raise ValueError("Project not found")

        contents = []
        for _ in range(payload.count if payload.generation_type == "IDEA" else 1):
            gc = GeneratedContent(
                project_id=project_id,
                generation_type=payload.generation_type,
                topic=payload.topic,
                content_type=payload.content_type,
                keywords=payload.keywords,
                cta=payload.cta_style,
                status="QUEUED"
            )
            # Store constraints safely in context for worker to read
            gc.source_context = {
                "campaign_context": payload.campaign_context
            }
            self.db.add(gc)
            contents.append(gc)

        self.db.commit()
        return contents

    def request_regeneration(self, project_id: str, content_id: str, payload: RegenerateRequest) -> GeneratedContent:
        self._verify_project(project_id)
        parent = self.db.query(GeneratedContent).filter_by(id=content_id, project_id=project_id).first()
        if not parent:
            raise ValueError("Content not found")

        gc = GeneratedContent(
            project_id=project_id,
            generation_type=parent.generation_type,
            topic=parent.topic,
            content_type=parent.content_type,
            keywords=parent.keywords,
            cta=parent.cta,
            status="QUEUED",
            parent_generation_id=parent.id,
            regeneration_reason=payload.regeneration_reason
        )
        gc.source_context = parent.source_context
        self.db.add(gc)
        self.db.commit()
        return gc
        
    def get_generated_content(self, project_id: str, content_id: str) -> GeneratedContent:
        self._verify_project(project_id)
        gc = self.db.query(GeneratedContent).filter_by(id=content_id, project_id=project_id).first()
        if not gc:
            raise ValueError("Content not found")
        return gc
        
    def list_generated_content(self, project_id: str, skip: int = 0, limit: int = 50) -> List[GeneratedContent]:
        self._verify_project(project_id)
        return self.db.query(GeneratedContent).filter_by(project_id=project_id).order_by(GeneratedContent.created_at.desc()).offset(skip).limit(limit).all()

    async def execute_generation(self, content_id: str):
        gc = self.db.query(GeneratedContent).filter_by(id=content_id).first()
        if not gc:
            return
            
        gc.status = "RUNNING"
        self.db.commit()
        
        try:
            # 1. Gather Context
            business_context = self._build_business_context(gc.project_id)
            intel_context = self._build_intel_context(gc.project_id)
            
            campaign = gc.source_context.get("campaign_context", "") if gc.source_context else ""
            
            # 2. Build Prompt
            if gc.generation_type == "IDEA":
                prompt = IDEA_PROMPT_TEMPLATE.format(
                    count=1, # One idea per worker job since we split them at request time
                    business_context=business_context,
                    intelligence_context=intel_context,
                    topic=gc.topic or "General",
                    content_type=gc.content_type or "Any",
                    keywords=", ".join(gc.keywords or []),
                    cta_style=gc.cta or "Any",
                    campaign_context=campaign
                )
            else:
                prompt = FULL_CONTENT_PROMPT_TEMPLATE.format(
                    business_context=business_context,
                    intelligence_context=intel_context,
                    topic=gc.topic or "General",
                    content_type=gc.content_type or "Any",
                    keywords=", ".join(gc.keywords or []),
                    cta_style=gc.cta or "Any",
                    campaign_context=campaign
                )
                
            # 3. Call AI
            raw_text, raw_dict = await self.ai_provider.generate_content(prompt)
            
            # 4. Parse JSON Output
            parsed_data = self._parse_json(raw_text, gc.generation_type)
            
            try:
                validated_data = AIStructuredOutput.model_validate(parsed_data).model_dump()
            except Exception as e:
                raise ValueError(f"AI output failed validation: {e}")
            
            # 5. Populate and Validate duplicate
            if gc.generation_type == "IDEA":
                candidate_text = validated_data.get("body", "")
                gc.generated_idea = candidate_text
            else:
                candidate_text = validated_data.get("body", "")
                gc.full_copy = candidate_text
                
            gc.topic = validated_data.get("topic")
            gc.keywords = validated_data.get("keywords", [])
            gc.cta = validated_data.get("cta")
            gc.image_concept = validated_data.get("image_concept")
            gc.content_type = validated_data.get("content_type")
            
            gc.provider = self.ai_provider.provider_name
            gc.model_name = self.ai_provider.model_name
            gc.prompt_version = PROMPT_VERSION
            
            if gc.source_context is None:
                gc.source_context = {}
            gc.source_context["rationale"] = validated_data.get("rationale")
            gc.source_context["offer"] = validated_data.get("offer")
            
            # Text duplication check
            fingerprint = self._generate_fingerprint(candidate_text)
            if self._is_exact_duplicate(gc.project_id, fingerprint, gc.id):
                gc.status = "REJECTED_DUPLICATE"
                gc.error_message = "Exact text duplicate found"
            else:
                gc.fingerprint = fingerprint
                
                # Semantic similarity check
                is_duplicate = False
                if self.embedding_provider and candidate_text:
                    try:
                        embedding = await self.embedding_provider.generate_embedding(candidate_text)
                        gc.embedding = embedding
                        if self._is_semantic_duplicate(gc.project_id, embedding, gc.id):
                            is_duplicate = True
                            gc.status = "REJECTED_DUPLICATE"
                            gc.error_message = "Semantic duplicate found"
                    except Exception as e:
                        logger.warning(f"Embedding failed for generation {gc.id}: {e}")
                        
                if not is_duplicate:
                    gc.status = "SUCCESS"
            
        except Exception as e:
            logger.exception("Generation failed")
            gc.status = "FAILED"
            gc.error_message = str(e)
            
        self.db.commit()

    def _parse_json(self, raw_text: str, gen_type: str) -> dict:
        try:
            start = raw_text.find('{')
            end = raw_text.rfind('}') + 1
            if start == -1 or end == 0:
                # Array case
                start = raw_text.find('[')
                end = raw_text.rfind(']') + 1
                if start != -1 and end != 0:
                    arr = json.loads(raw_text[start:end])
                    if arr:
                        return arr[0]
            if start != -1 and end != 0:
                return json.loads(raw_text[start:end])
            return json.loads(raw_text)
        except json.JSONDecodeError as e:
            raise ValueError(f"AI produced invalid JSON output: {e}")

    def _generate_fingerprint(self, text: str) -> str:
        if not text:
            return ""
        norm = " ".join(text.lower().split())
        return hashlib.sha256(norm.encode('utf-8')).hexdigest()

    def _is_exact_duplicate(self, project_id: str, fingerprint: str, exclude_id: str) -> bool:
        return self.db.query(GeneratedContent).filter(
            GeneratedContent.project_id == project_id,
            GeneratedContent.fingerprint == fingerprint,
            GeneratedContent.id != exclude_id
        ).count() > 0

    def _build_business_context(self, project_id: str) -> str:
        project = self.db.query(Project).filter_by(id=project_id).first()
        if not project or not project.own_business:
            return "No business context available."
        bp = project.own_business
        return f"Business Name: {bp.business_name}\nCategory: {bp.category or 'Unknown'}\nDescription: {bp.description or 'None'}"

    def _is_semantic_duplicate(self, project_id: str, embedding: List[float], exclude_id: str) -> bool:
        # Check against previous generated content in the same project using SimilarityService
        # We fetch recent generations with embeddings
        history = self.db.query(GeneratedContent).filter(
            GeneratedContent.project_id == project_id,
            GeneratedContent.id != exclude_id,
            GeneratedContent.embedding.isnot(None)
        ).order_by(GeneratedContent.created_at.desc()).limit(settings.GENERATION_MAX_GENERATED_HISTORY).all()
        
        for gc in history:
            if gc.embedding:
                similarity = self.similarity_service.calculate_similarity(embedding, gc.embedding)
                if similarity >= settings.CONTENT_SIMILARITY_THRESHOLD:
                    return True
        return False

    def _build_intel_context(self, project_id: str) -> str:
        topic_gaps = self.analytics_service.get_detailed_topic_gaps(project_id, limit=settings.GENERATION_MAX_GAPS)
        kw_gaps = self.analytics_service.get_detailed_keyword_gaps(project_id, limit=settings.GENERATION_MAX_KEYWORDS)
        type_gaps = self.analytics_service.get_content_type_gaps(project_id)
        
        context_parts = []
        
        if topic_gaps:
            topics_str = ", ".join([f"{t['topic']} (Gap: {t['gap_score']:.1f})" for t in topic_gaps])
            context_parts.append(f"Topic Gaps: {topics_str}")
            
        if kw_gaps:
            kws_str = ", ".join([f"{k['keyword']} (Gap: {k['gap_score']:.1f})" for k in kw_gaps])
            context_parts.append(f"Keyword Gaps: {kws_str}")
            
        if type_gaps:
            types_str = ", ".join([f"{t['content_type']} (Gap: {t['gap_score']:.1f})" for t in type_gaps[:settings.GENERATION_MAX_GAPS]])
            context_parts.append(f"Content Type Gaps: {types_str}")
            
        if not context_parts:
            return "No clear competitor gaps identified yet."
            
        return "\n".join(context_parts)
