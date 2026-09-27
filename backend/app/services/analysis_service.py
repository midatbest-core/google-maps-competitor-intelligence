import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import Optional, List
import json

from app.models.post import Post
from app.models.analysis import AIAnalysis, PostEmbedding
from app.schemas.analysis import AIAnalysisResult
from app.providers.ai.base import AIProvider
from app.providers.embedding.base import EmbeddingProvider
from app.prompts.analysis_v1 import ANALYSIS_PROMPT_VERSION, ANALYSIS_SYSTEM_PROMPT, build_analysis_prompt
from app.repositories.analysis_repo import AnalysisRepository, EmbeddingRepository

logger = logging.getLogger(__name__)

class AnalysisService:
    def __init__(self, db: Session, ai_provider: AIProvider, embedding_provider: EmbeddingProvider, workspace=None):
        self.db = db
        self.ai = ai_provider
        self.embedding = embedding_provider
        self.analysis_repo = AnalysisRepository(db)
        self.embed_repo = EmbeddingRepository(db)
        self.workspace = workspace

    def _verify_post(self, post: Post):
        if not self.workspace:
            return
        from app.models.project import Project
        from app.models.competitor import ProjectCompetitor
        # Check if the post's business is in any project of the current workspace
        own_project = self.db.query(Project).filter(Project.own_business_id == post.business_id, Project.workspace_id == self.workspace.id).first()
        comp_project = self.db.query(Project).join(ProjectCompetitor, Project.id == ProjectCompetitor.project_id).filter(ProjectCompetitor.business_id == post.business_id, Project.workspace_id == self.workspace.id).first()
        if not own_project and not comp_project:
            raise ValueError("Not authorized to access this post")

    async def analyze_post(self, post_id: str) -> Optional[AIAnalysis]:
        """Analyzes a post, returning the AIAnalysis record. Idempotent."""
        post = self.db.query(Post).filter_by(id=post_id).first()
        if not post or not post.text_content:
            return None
            
        self._verify_post(post)

        # Check idempotency
        existing_analysis = self.analysis_repo.get_analysis(
            post_id=post_id,
            provider=self.ai.provider_name,
            model_name=self.ai.model_name,
            version=ANALYSIS_PROMPT_VERSION
        )
        
        if existing_analysis:
            return existing_analysis
            
        prompt = build_analysis_prompt(post.text_content)
        
        try:
            # AI call
            structured_result, raw_response = await self.ai.analyze_post(
                prompt=f"{ANALYSIS_SYSTEM_PROMPT}\n{prompt}",
                text=post.text_content
            )
        except Exception as e:
            logger.error(f"AI Provider failed for post {post_id}: {e}")
            return None
            
        analysis = AIAnalysis(
            post_id=post_id,
            provider=self.ai.provider_name,
            model_name=self.ai.model_name,
            analysis_version=ANALYSIS_PROMPT_VERSION,
            topic=structured_result.topic,
            subtopic=structured_result.subtopic,
            keywords=structured_result.keywords,
            content_type=structured_result.content_type,
            cta_type=structured_result.cta_type,
            offer_or_promotion=structured_result.offer_or_promotion,
            sentiment=structured_result.sentiment,
            summary=structured_result.summary,
            confidence=structured_result.confidence,
            raw_analysis=raw_response
        )
        
        try:
            return self.analysis_repo.create_analysis(analysis)
        except IntegrityError:
            self.db.rollback()
            # Concurrent insertion
            return self.analysis_repo.get_analysis(
                post_id=post_id,
                provider=self.ai.provider_name,
                model_name=self.ai.model_name,
                version=ANALYSIS_PROMPT_VERSION
            )
            
    async def embed_post(self, post_id: str) -> Optional[PostEmbedding]:
        """Generates embedding for a post. Idempotent."""
        post = self.db.query(Post).filter_by(id=post_id).first()
        if not post or not post.text_content:
            return None
            
        self._verify_post(post)

        embedding_version = "v1"
            
        existing_embedding = self.embed_repo.get_embedding(
            post_id=post_id,
            model_name=self.embedding.model_name,
            version=embedding_version
        )
        
        if existing_embedding:
            return existing_embedding
            
        # Get AI analysis if exists to augment text
        analysis = self.db.query(AIAnalysis).filter_by(post_id=post_id).order_by(AIAnalysis.analyzed_at.desc()).first()
        
        text_to_embed = post.text_content
        if analysis:
            extras = []
            if analysis.topic: extras.append(analysis.topic)
            if analysis.subtopic: extras.append(analysis.subtopic)
            if analysis.keywords: extras.extend(analysis.keywords)
            if extras:
                text_to_embed += "\n" + " ".join(extras)
                
        try:
            vector = await self.embedding.generate_embedding(text_to_embed)
        except Exception as e:
            logger.error(f"Embedding failed for post {post_id}: {e}")
            return None
            
        embed_record = PostEmbedding(
            post_id=post_id,
            embedding_model=self.embedding.model_name,
            embedding_version=embedding_version,
            embedding=vector
        )
        
        try:
            return self.embed_repo.create_embedding(embed_record)
        except IntegrityError:
            self.db.rollback()
            return self.embed_repo.get_embedding(
                post_id=post_id,
                model_name=self.embedding.model_name,
                version=embedding_version
            )
