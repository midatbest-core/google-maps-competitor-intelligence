from sqlalchemy.orm import Session
from app.models.analysis import AIAnalysis, PostEmbedding
from app.schemas.analysis import AIAnalysisResult
from typing import Optional

class AnalysisRepository:
    def __init__(self, db: Session):
        self.db = db
        
    def get_analysis(self, post_id: str, provider: str, model_name: str, version: str) -> Optional[AIAnalysis]:
        return self.db.query(AIAnalysis).filter_by(
            post_id=post_id,
            provider=provider,
            model_name=model_name,
            analysis_version=version
        ).first()
        
    def create_analysis(self, analysis: AIAnalysis) -> AIAnalysis:
        self.db.add(analysis)
        self.db.commit()
        return analysis

class EmbeddingRepository:
    def __init__(self, db: Session):
        self.db = db
        
    def get_embedding(self, post_id: str, model_name: str, version: str) -> Optional[PostEmbedding]:
        return self.db.query(PostEmbedding).filter_by(
            post_id=post_id,
            embedding_model=model_name,
            embedding_version=version
        ).first()
        
    def create_embedding(self, embedding: PostEmbedding) -> PostEmbedding:
        self.db.add(embedding)
        self.db.commit()
        return embedding
