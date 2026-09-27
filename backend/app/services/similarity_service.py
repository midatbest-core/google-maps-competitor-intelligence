from sqlalchemy.orm import Session
from typing import List, Tuple
from app.models.analysis import PostEmbedding

class SimilarityService:
    def __init__(self, db: Session):
        self.db = db
        
    def calculate_similarity(self, vector1: List[float], vector2: List[float]) -> float:
        """
        Calculates cosine similarity between two vectors in memory.
        Used for tests or small batches.
        """
        import math
        dot = sum(a * b for a, b in zip(vector1, vector2))
        mag1 = math.sqrt(sum(a * a for a in vector1))
        mag2 = math.sqrt(sum(a * a for a in vector2))
        if mag1 == 0 or mag2 == 0:
            return 0.0
        return dot / (mag1 * mag2)

    def find_similar_posts(self, embedding_id: str, limit: int = 5) -> List[Tuple[PostEmbedding, float]]:
        """
        Uses pgvector to find similar posts efficiently using cosine distance (<=>).
        """
        source = self.db.query(PostEmbedding).filter_by(id=embedding_id).first()
        if not source:
            return []
            
        # Using pgvector cosine distance: embedding <=> source.embedding
        # distance = 1 - cosine_similarity
        # similarity = 1 - distance
        results = self.db.query(
            PostEmbedding, 
            (1 - PostEmbedding.embedding.cosine_distance(source.embedding)).label('similarity')
        ).filter(
            PostEmbedding.id != embedding_id,
            PostEmbedding.embedding_model == source.embedding_model
        ).order_by(
            PostEmbedding.embedding.cosine_distance(source.embedding)
        ).limit(limit).all()
        
        return [(r[0], r[1]) for r in results]
