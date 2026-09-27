from sqlalchemy.orm import Session
from sqlalchemy import select, func, or_, desc, asc
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.models.project import Project
from app.models.competitor import ProjectCompetitor
from app.models.post import Post, PostMedia
from app.models.profile import BusinessProfile
from app.models.analysis import AIAnalysis
from app.models.auth import Workspace

class PostService:
    def __init__(self, db: Session, workspace: Workspace = None):
        self.db = db
        self.workspace = workspace

    def _verify_project(self, project_id: str) -> Project:
        if not self.workspace:
            raise ValueError("Authentication required")
        project = self.db.query(Project).filter_by(id=project_id, workspace_id=self.workspace.id).first()
        if not project:
            raise ValueError("Project not found or not authorized")
        return project

    def _get_project_business_ids(self, project_id: str) -> List[str]:
        project = self._verify_project(project_id)
        b_ids = []
        if project.own_business_id:
            b_ids.append(project.own_business_id)
        competitors = self.db.query(ProjectCompetitor).filter_by(project_id=project_id).all()
        b_ids.extend([c.business_id for c in competitors])
        return b_ids

    def get_posts(
        self, 
        project_id: str, 
        page: int = 1, 
        page_size: int = 20,
        search: Optional[str] = None,
        competitor_id: Optional[str] = None, # actually business_id or project_competitor ID. We'll use business_id.
        topic: Optional[str] = None,
        content_type: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        has_analysis: Optional[bool] = None
    ) -> Dict[str, Any]:
        
        b_ids = self._get_project_business_ids(project_id)
        
        # Base query
        query = self.db.query(Post).filter(Post.business_id.in_(b_ids))
        
        # Joins for filtering
        if has_analysis is not None or topic or content_type:
            # We need to outer join analysis to filter by it
            query = query.outerjoin(AIAnalysis, AIAnalysis.post_id == Post.id)
            
        if competitor_id:
            query = query.filter(Post.business_id == competitor_id)
            
        if search:
            query = query.filter(Post.text_content.ilike(f"%{search}%"))
            
        if date_from:
            query = query.filter(Post.published_date >= date_from)
            
        if date_to:
            query = query.filter(Post.published_date <= date_to)
            
        if has_analysis is True:
            query = query.filter(AIAnalysis.id.isnot(None))
        elif has_analysis is False:
            query = query.filter(AIAnalysis.id.is_(None))
            
        if topic:
            query = query.filter(AIAnalysis.topic == topic)
            
        if content_type:
            query = query.filter(AIAnalysis.content_type == content_type)

        # Count total
        total = query.with_entities(func.count(Post.id)).scalar()
        
        # Bounded page size
        page_size = max(1, min(page_size, 100))
        page = max(1, page)
        
        # Order and paginate
        query = query.order_by(desc(Post.published_date), desc(Post.id))
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        posts = query.all()
        
        # To avoid N+1 for media and analysis, we could use joinedload, 
        # but since page_size <= 100, we can let SQLAlchemy lazy load or we explicitly eager load.
        # It's cleaner to eager load.
        from sqlalchemy.orm import selectinload
        
        query_eager = self.db.query(Post).filter(Post.id.in_([p.id for p in posts]))
        query_eager = query_eager.options(
            selectinload(Post.business),
            selectinload(Post.media),
            selectinload(Post.ai_analyses)
        )
        
        # re-fetch to get eager loaded relations, but keep order
        eager_posts = query_eager.all()
        eager_posts_dict = {p.id: p for p in eager_posts}
        
        ordered_posts = [eager_posts_dict[p.id] for p in posts]
        
        # Map to response structure
        items = []
        for p in ordered_posts:
            # Pick first analysis if exists
            analysis = p.ai_analyses[0] if p.ai_analyses else None
            
            items.append({
                "id": p.id,
                "business_id": p.business_id,
                "business": {
                    "id": p.business.id,
                    "business_name": p.business.business_name
                },
                "source_url": p.source_url,
                "text_content": p.text_content,
                "published_date": p.published_date,
                "scraped_date": p.scraped_date,
                "analysis": analysis,
                "media": p.media
            })
            
        pages = (total + page_size - 1) // page_size if total > 0 else 0
            
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages
        }

    def get_post_detail(self, project_id: str, post_id: str) -> Dict[str, Any]:
        b_ids = self._get_project_business_ids(project_id)
        
        from sqlalchemy.orm import selectinload
        post = self.db.query(Post).filter(Post.id == post_id, Post.business_id.in_(b_ids)).options(
            selectinload(Post.business),
            selectinload(Post.media),
            selectinload(Post.ai_analyses)
        ).first()
        
        if not post:
            raise ValueError("Post not found")
            
        analysis = post.ai_analyses[0] if post.ai_analyses else None
        
        return {
            "id": post.id,
            "business_id": post.business_id,
            "business": {
                "id": post.business.id,
                "business_name": post.business.business_name
            },
            "source_url": post.source_url,
            "text_content": post.text_content,
            "published_date": post.published_date,
            "scraped_date": post.scraped_date,
            "analysis": analysis,
            "media": post.media
        }
