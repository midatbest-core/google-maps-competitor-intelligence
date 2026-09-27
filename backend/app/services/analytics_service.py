from sqlalchemy.orm import Session
from sqlalchemy import func, distinct, desc
from typing import List, Dict, Any

from app.models.project import Project
from app.models.competitor import ProjectCompetitor
from app.models.post import Post
from app.models.analysis import AIAnalysis
from app.models.scrape import ScrapeObservation

from app.models.auth import Workspace

class AnalyticsService:
    def __init__(self, db: Session, workspace: Workspace = None):
        self.db = db
        self.workspace = workspace
        
    def _verify_project(self, project_id: str):
        if not self.workspace:
            return
        project = self.db.query(Project).filter_by(id=project_id).first()
        if not project or project.workspace_id != self.workspace.id:
            raise ValueError("Not authorized to access this project")

    def _get_project_business_ids(self, project_id: str) -> List[str]:
        self._verify_project(project_id)
        project = self.db.query(Project).filter_by(id=project_id).first()
        if not project:
            return []
        b_ids = [project.own_business_id]
        competitors = self.db.query(ProjectCompetitor).filter_by(project_id=project_id).all()
        b_ids.extend([c.business_id for c in competitors])
        return b_ids

    def get_topic_frequency(self, project_id: str) -> List[Dict[str, Any]]:
        b_ids = self._get_project_business_ids(project_id)
        if not b_ids:
            return []
            
        results = self.db.query(
            AIAnalysis.topic,
            func.count(distinct(Post.id)).label('post_count')
        ).join(Post).filter(
            Post.business_id.in_(b_ids),
            AIAnalysis.topic.isnot(None)
        ).group_by(AIAnalysis.topic).order_by(desc('post_count')).all()
        
        return [{"topic": r[0], "count": r[1]} for r in results]

    def get_competitor_coverage(self, project_id: str) -> List[Dict[str, Any]]:
        b_ids = self._get_project_business_ids(project_id)
        if not b_ids:
            return []
            
        results = self.db.query(
            AIAnalysis.topic,
            func.count(distinct(Post.business_id)).label('competitor_count')
        ).join(Post).filter(
            Post.business_id.in_(b_ids),
            AIAnalysis.topic.isnot(None)
        ).group_by(AIAnalysis.topic).order_by(desc('competitor_count')).all()
        
        return [{"topic": r[0], "competitor_count": r[1]} for r in results]

    def get_topic_percentage(self, project_id: str) -> List[Dict[str, Any]]:
        b_ids = self._get_project_business_ids(project_id)
        if not b_ids:
            return []
            
        # Total analyzed posts
        total_posts = self.db.query(func.count(distinct(Post.id))).join(AIAnalysis).filter(
            Post.business_id.in_(b_ids)
        ).scalar() or 0
        
        if total_posts == 0:
            return []
            
        freq = self.get_topic_frequency(project_id)
        for f in freq:
            f["percentage"] = (f["count"] / total_posts) * 100.0
            
        return freq
        
    def get_keyword_frequency(self, project_id: str) -> List[Dict[str, Any]]:
        # For a production app we might use PostgreSQL array functions (e.g. unnest)
        # For compatibility and simplicity we can do it in memory for now if the dataset is small,
        # but let's try raw unnest if possible. However, SQLite doesn't have unnest.
        # SQLite compatible approach: fetch and aggregate in python.
        b_ids = self._get_project_business_ids(project_id)
        if not b_ids:
            return []
            
        analyses = self.db.query(AIAnalysis.keywords).join(Post).filter(
            Post.business_id.in_(b_ids),
            AIAnalysis.keywords.isnot(None)
        ).all()
        
        counts = {}
        for (kw_list,) in analyses:
            if isinstance(kw_list, list):
                for kw in kw_list:
                    counts[kw] = counts.get(kw, 0) + 1
                    
        sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return [{"keyword": k, "count": c} for k, c in sorted_counts[:50]]

    def get_publishing_patterns(self, project_id: str) -> Dict[str, Any]:
        b_ids = self._get_project_business_ids(project_id)
        if not b_ids:
            return {}
            
        # Posts per competitor
        results = self.db.query(
            Post.business_id,
            func.count(Post.id).label('post_count')
        ).filter(
            Post.business_id.in_(b_ids)
        ).group_by(Post.business_id).all()
        
        return {
            "posts_per_competitor": [{"business_id": r[0], "count": r[1]} for r in results]
        }

    def get_content_gaps(self, project_id: str) -> Dict[str, Any]:
        self._verify_project(project_id)
        project = self.db.query(Project).filter_by(id=project_id).first()
        if not project:
            return {}
            
        own_b_id = project.own_business_id
        c_ids = [c.business_id for c in self.db.query(ProjectCompetitor).filter_by(project_id=project_id).all()]
        
        # Get own topics
        own_topics = {
            r[0] for r in self.db.query(AIAnalysis.topic).join(Post).filter(
                Post.business_id == own_b_id,
                AIAnalysis.topic.isnot(None)
            ).all()
        }
        
        # Get competitor topics
        comp_topics = {
            r[0] for r in self.db.query(AIAnalysis.topic).join(Post).filter(
                Post.business_id.in_(c_ids),
                AIAnalysis.topic.isnot(None)
            ).all()
        }
        
        gap_topics = comp_topics - own_topics
        
        # Keywords gap
        own_kws = set()
        for (kw_list,) in self.db.query(AIAnalysis.keywords).join(Post).filter(
            Post.business_id == own_b_id, AIAnalysis.keywords.isnot(None)
        ).all():
            if isinstance(kw_list, list): own_kws.update(kw_list)
            
        comp_kws = set()
        for (kw_list,) in self.db.query(AIAnalysis.keywords).join(Post).filter(
            Post.business_id.in_(c_ids), AIAnalysis.keywords.isnot(None)
        ).all():
            if isinstance(kw_list, list): comp_kws.update(kw_list)
            
        gap_kws = comp_kws - own_kws
        
        return {
            "topic_gaps": list(gap_topics),
            "keyword_gaps": list(gap_kws)
        }

    def get_detailed_topic_gaps(self, project_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        self._verify_project(project_id)
        project = self.db.query(Project).filter_by(id=project_id).first()
        if not project or not project.own_business_id:
            return []
            
        own_b_id = project.own_business_id
        c_ids = [c.business_id for c in self.db.query(ProjectCompetitor).filter_by(project_id=project_id).all()]
        if not c_ids:
            return []

        own_topics = self.db.query(
            AIAnalysis.topic, func.count(Post.id)
        ).join(Post).filter(
            Post.business_id == own_b_id,
            AIAnalysis.topic.isnot(None)
        ).group_by(AIAnalysis.topic).all()
        
        comp_topics = self.db.query(
            AIAnalysis.topic, func.count(Post.id)
        ).join(Post).filter(
            Post.business_id.in_(c_ids),
            AIAnalysis.topic.isnot(None)
        ).group_by(AIAnalysis.topic).all()
        
        own_counts = {t[0]: t[1] for t in own_topics}
        comp_counts = {t[0]: t[1] for t in comp_topics}
        
        gaps = []
        for topic, c_count in comp_counts.items():
            o_count = own_counts.get(topic, 0)
            gap_score = c_count / max(o_count, 1)
            gaps.append({
                "topic": topic,
                "competitor_frequency": c_count,
                "project_frequency": o_count,
                "gap_score": gap_score
            })
            
        gaps.sort(key=lambda x: x["gap_score"], reverse=True)
        return gaps[:limit]

    def get_detailed_keyword_gaps(self, project_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        self._verify_project(project_id)
        project = self.db.query(Project).filter_by(id=project_id).first()
        if not project or not project.own_business_id:
            return []
            
        own_b_id = project.own_business_id
        c_ids = [c.business_id for c in self.db.query(ProjectCompetitor).filter_by(project_id=project_id).all()]
        if not c_ids:
            return []

        # We process in memory as earlier
        own_kws = {}
        for (kw_list,) in self.db.query(AIAnalysis.keywords).join(Post).filter(Post.business_id == own_b_id, AIAnalysis.keywords.isnot(None)).all():
            if isinstance(kw_list, list):
                for kw in kw_list:
                    own_kws[kw] = own_kws.get(kw, 0) + 1
                    
        comp_kws = {}
        for (kw_list,) in self.db.query(AIAnalysis.keywords).join(Post).filter(Post.business_id.in_(c_ids), AIAnalysis.keywords.isnot(None)).all():
            if isinstance(kw_list, list):
                for kw in kw_list:
                    comp_kws[kw] = comp_kws.get(kw, 0) + 1

        gaps = []
        for kw, c_count in comp_kws.items():
            o_count = own_kws.get(kw, 0)
            gap_score = c_count / max(o_count, 1)
            gaps.append({
                "keyword": kw,
                "competitor_frequency": c_count,
                "project_frequency": o_count,
                "gap_score": gap_score
            })
            
        gaps.sort(key=lambda x: x["gap_score"], reverse=True)
        return gaps[:limit]

    def get_content_type_gaps(self, project_id: str) -> List[Dict[str, Any]]:
        self._verify_project(project_id)
        project = self.db.query(Project).filter_by(id=project_id).first()
        if not project or not project.own_business_id:
            return []
            
        own_b_id = project.own_business_id
        c_ids = [c.business_id for c in self.db.query(ProjectCompetitor).filter_by(project_id=project_id).all()]
        if not c_ids:
            return []

        own_types = self.db.query(
            AIAnalysis.content_type, func.count(Post.id)
        ).join(Post).filter(
            Post.business_id == own_b_id,
            AIAnalysis.content_type.isnot(None)
        ).group_by(AIAnalysis.content_type).all()
        
        comp_types = self.db.query(
            AIAnalysis.content_type, func.count(Post.id)
        ).join(Post).filter(
            Post.business_id.in_(c_ids),
            AIAnalysis.content_type.isnot(None)
        ).group_by(AIAnalysis.content_type).all()
        
        own_counts = {t[0]: t[1] for t in own_types}
        comp_counts = {t[0]: t[1] for t in comp_types}
        
        gaps = []
        for ctype, c_count in comp_counts.items():
            o_count = own_counts.get(ctype, 0)
            gap_score = c_count / max(o_count, 1)
            gaps.append({
                "content_type": ctype,
                "competitor_frequency": c_count,
                "project_frequency": o_count,
                "gap_score": gap_score
            })
            
        gaps.sort(key=lambda x: x["gap_score"], reverse=True)
        return gaps
