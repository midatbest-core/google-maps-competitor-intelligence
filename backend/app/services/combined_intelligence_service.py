from collections import Counter
from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.models.analysis import AIAnalysis, IntelligenceReport
from app.models.auth import Workspace
from app.models.competitor import ProjectCompetitor
from app.models.post import Post
from app.models.profile import BusinessProfile
from app.models.project import Project
from app.models.review import Review
from app.providers.ai.base import AIProvider
from app.repositories.analysis_repo import IntelligenceReportRepository
from app.schemas.analysis import CombinedIntelligenceOutput

logger = logging.getLogger(__name__)

class CombinedIntelligenceService:
    def __init__(
        self,
        db: Session,
        ai_provider: AIProvider,
        workspace: Optional[Workspace] = None,
        report_repo: Optional[IntelligenceReportRepository] = None,
    ):
        self.db = db
        self.ai_provider = ai_provider
        self.workspace = workspace
        self.report_repo = report_repo or IntelligenceReportRepository(db)

    def _verify_project(self, project_id: str) -> Project:
        project = self.db.query(Project).filter_by(id=project_id).first()
        if not project:
            raise ValueError("Project not found")
        if self.workspace and project.workspace_id != self.workspace.id:
            raise ValueError("Not authorized to access this project")
        return project

    def get_latest_report(self, project_id: str) -> Optional[IntelligenceReport]:
        self._verify_project(project_id)
        return self.report_repo.get_latest_report(project_id)

    def list_reports(self, project_id: str, limit: int = 10) -> List[IntelligenceReport]:
        self._verify_project(project_id)
        return self.report_repo.list_reports(project_id, limit=limit)

    async def generate_report(self, project_id: str) -> IntelligenceReport:
        project = self._verify_project(project_id)

        # 1. Collect businesses in this project
        competitor_links = self.db.query(ProjectCompetitor).filter_by(
            project_id=project_id,
            is_active=True
        ).all()
        competitor_ids = [c.business_id for c in competitor_links]

        all_business_ids = list(competitor_ids)
        if project.own_business_id and project.own_business_id not in all_business_ids:
            all_business_ids.append(project.own_business_id)

        businesses = {
            b.id: b for b in self.db.query(BusinessProfile).filter(BusinessProfile.id.in_(all_business_ids)).all()
        }

        # 2. Gather Posts with AI Analysis
        posts_with_analysis = (
            self.db.query(Post, AIAnalysis)
            .outerjoin(AIAnalysis, Post.id == AIAnalysis.post_id)
            .filter(Post.business_id.in_(all_business_ids))
            .order_by(desc(Post.scraped_date))
            .limit(100)
            .all()
        )

        # 3. Gather Reviews
        reviews = (
            self.db.query(Review)
            .filter(Review.business_id.in_(all_business_ids))
            .order_by(desc(Review.created_at))
            .limit(100)
            .all()
        )

        posts_count = len(posts_with_analysis)
        reviews_count = len(reviews)
        competitors_count = len(competitor_ids)

        # 4. Calculate Deterministic Statistics
        posts_by_biz: Dict[str, List[Dict[str, Any]]] = {}
        reviews_by_biz: Dict[str, List[Dict[str, Any]]] = {}

        seen_post_texts: set[tuple[str, str]] = set()
        for post, analysis in posts_with_analysis:
            biz_name = businesses.get(post.business_id, BusinessProfile(business_name="Unknown")).business_name
            norm_text = (post.text_content or "").strip().lower()
            text_key = (post.business_id, norm_text[:120])
            if norm_text and text_key in seen_post_texts:
                continue
            if norm_text:
                seen_post_texts.add(text_key)

            posts_by_biz.setdefault(biz_name, []).append({
                "post_id": post.id,
                "text": (post.text_content or "")[:200],
                "topic": analysis.topic if analysis else None,
                "content_type": analysis.content_type if analysis else None,
                "cta": analysis.cta_type if analysis else None,
                "offer": analysis.offer_or_promotion if analysis else None,
            })

        for rev in reviews:
            biz_name = businesses.get(rev.business_id, BusinessProfile(business_name="Unknown")).business_name
            reviews_by_biz.setdefault(biz_name, []).append({
                "review_id": rev.id,
                "author": rev.author_name,
                "rating": rev.rating,
                "sentiment": rev.sentiment,
                "text": (rev.text or "")[:200],
                "relative_time": rev.relative_time_description,
                "source": rev.source,
            })

        # 5. Build Structured Intelligence Prompt
        own_biz_name = project.own_business.business_name if project.own_business else "Our Business"
        own_category = project.own_business.category if project.own_business else "General"

        summary_lines = [
            f"Business: {own_biz_name} (Category: {own_category})",
            f"Project: {project.name} - {project.description or ''}",
            f"Competitors tracked: {competitors_count} | Posts analyzed: {posts_count} | Reviews analyzed: {reviews_count}",
            "\n=== OBSERVED COMPETITOR POSTS (MARKETING CLAIMS & PATTERNS) ==="
        ]

        if not posts_by_biz:
            summary_lines.append("No competitor posts recorded yet.")
        else:
            for bname, p_list in posts_by_biz.items():
                summary_lines.append(f"\nCompetitor: {bname} ({len(p_list)} posts)")
                for p in p_list[:5]:
                    summary_lines.append(f" - [Post {p['post_id'][:8]}] Topic: {p['topic'] or 'General'} | CTA: {p['cta'] or 'None'} | Offer: {p['offer'] or 'None'} | Summary: {p['text']}")

        summary_lines.append("\n=== OBSERVED CUSTOMER REVIEWS (ACTUAL CUSTOMER EXPERIENCES & COMPLAINTS) ===")
        if not reviews_by_biz:
            summary_lines.append("No customer reviews recorded yet.")
        else:
            for bname, r_list in reviews_by_biz.items():
                ratings = [r['rating'] for r in r_list if r['rating'] is not None]
                avg_r = sum(ratings) / len(ratings) if ratings else 0.0
                summary_lines.append(f"\nCompetitor: {bname} ({len(r_list)} reviews, Avg Rating: {avg_r:.1f}★)")
                for r in r_list[:8]:
                    summary_lines.append(f" - [Review {r['review_id'][:8]}] {r['rating']}★ ({r['sentiment']}): \"{r['text']}\" (Time: {r['relative_time'] or 'recent'})")

        summary_lines.append(
            "\n=== INSTRUCTIONS ==="
            "\nYou are an elite competitive intelligence architect."
            "\nAnalyze the above factual competitor posts and customer reviews."
            "\n1. Identify competitor strengths, weaknesses, marketing patterns, and overall positioning."
            "\n2. Crucially identify STRATEGIC DISCONNECTS: Where competitors advertise something in their posts (e.g., fast service, live events, premium food) but customer reviews reveal frustration (e.g., long wait times, noisy seating, delays)."
            "\n3. Formulate actionable recommendations for our business that directly capitalize on these disconnects, with cited evidence from the observed data."
            "\n4. Generate high-converting marketing content ideas and angles that position our business as the superior alternative."
            "\nNever invent quotes, fake reviews, or false facts. Return strictly valid structured output matching the schema."
        )

        full_prompt = "\n".join(summary_lines)

        try:
            structured_output, raw_dict = await self.ai_provider.generate_combined_intelligence(full_prompt)
            output_dict = structured_output.model_dump()
        except Exception as e:
            logger.exception(f"Failed to generate combined intelligence via AI provider: {e}")
            # Save failed report record
            report = IntelligenceReport(
                project_id=project_id,
                posts_analyzed=posts_count,
                reviews_analyzed=reviews_count,
                competitors_analyzed=competitors_count,
                status="FAILED",
                error_message=str(e),
                provider=self.ai_provider.provider_name,
                model_name=self.ai_provider.model_name
            )
            return self.report_repo.create_report(report)

        report = IntelligenceReport(
            project_id=project_id,
            posts_analyzed=posts_count,
            reviews_analyzed=reviews_count,
            competitors_analyzed=competitors_count,
            competitor_insights=output_dict.get("competitor_insights"),
            marketing_intelligence=output_dict.get("marketing_intelligence"),
            strategic_disconnects=output_dict.get("strategic_disconnects"),
            business_opportunities=output_dict.get("business_opportunities"),
            actionable_recommendations=output_dict.get("actionable_recommendations"),
            content_ideas=output_dict.get("content_ideas"),
            provider=self.ai_provider.provider_name,
            model_name=self.ai_provider.model_name,
            status="COMPLETED"
        )

        return self.report_repo.create_report(report)

