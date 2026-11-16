import logging
import json
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List, Dict
from datetime import datetime, timezone
import hashlib

from app.models.analysis import GeneratedContent, AIAnalysis, PostEmbedding, IntelligenceReport
from app.models.post import Post
from app.models.competitor import ProjectCompetitor
from app.models.project import Project
from app.models.profile import BusinessProfile
from app.models.review import ReviewIntelligence
from app.schemas.generation import GenerationRequest, RegenerateRequest, AIStructuredOutput
from app.providers.ai.base import AIProvider
from app.providers.embedding.base import EmbeddingProvider
from app.prompts.generation_v1 import PROMPT_VERSION, IDEA_PROMPT_TEMPLATE, FULL_CONTENT_PROMPT_TEMPLATE, OPPORTUNITIES_PROMPT_TEMPLATE
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
        legacy_request = payload.workflow_mode is None
        workflow_mode = payload.workflow_mode or ("CREATE_CONTENT" if payload.generation_type == "FULL" else "LEGACY_IDEA")
        if workflow_mode not in {"MARKETING_OPPORTUNITIES", "CREATE_CONTENT", "LEGACY_IDEA"}:
            raise ValueError("Invalid generation mode")
        if workflow_mode == "MARKETING_OPPORTUNITIES":
            generation_type = "IDEA"
        elif workflow_mode == "LEGACY_IDEA":
            generation_type = payload.generation_type
        else:
            generation_type = "FULL"
        request_context = {
            "campaign_context": payload.campaign_context,
            "workflow_mode": workflow_mode,
            "context_type": payload.context_type,
            "context_value": payload.context_value,
            "context_generation_id": payload.context_generation_id,
            "requested_topic": payload.topic,
            "requested_content_type": payload.content_type,
            "requested_keywords": payload.keywords or [],
        }
        # Resolve and validate context before queueing. Submitted gap scores/counts are never trusted.
        self._build_generation_intelligence(project_id, request_context)
        generation_count = payload.count if legacy_request and generation_type == "IDEA" else 1
        for _ in range(generation_count):
            gc = GeneratedContent(
                project_id=project_id,
                generation_type=generation_type,
                topic=payload.topic,
                content_type=payload.content_type,
                keywords=payload.keywords,
                cta=payload.cta_style,
                status="QUEUED"
            )
            # Store constraints safely in context for worker to read
            gc.source_context = request_context
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

    def mark_enqueue_failed(self, content_ids: list[str]) -> None:
        if not content_ids:
            return
        self.db.query(GeneratedContent).filter(
            GeneratedContent.id.in_(content_ids),
            GeneratedContent.status == "QUEUED",
        ).update(
            {
                GeneratedContent.status: "FAILED",
                GeneratedContent.error_message: "Failed to enqueue generation job",
            },
            synchronize_session=False,
        )
        self.db.commit()

    async def execute_generation(self, content_id: str):
        gc = self.db.query(GeneratedContent).filter_by(id=content_id).first()
        if not gc:
            return
            
        gc.status = "RUNNING"
        self.db.commit()
        
        try:
            # 1. Gather Context
            business_context = self._build_business_context(gc.project_id)
            intel_context, evidence = self._build_generation_intelligence(gc.project_id, gc.source_context or {})
            
            campaign = gc.source_context.get("campaign_context", "") if gc.source_context else ""
            
            # 2. Build Prompt
            workflow_mode = (gc.source_context or {}).get("workflow_mode")
            if workflow_mode == "MARKETING_OPPORTUNITIES":
                prompt = OPPORTUNITIES_PROMPT_TEMPLATE.format(
                    business_context=business_context,
                    intelligence_context=intel_context,
                )
            elif gc.generation_type == "IDEA":
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
            gc.prompt_version = "v2-review-aware" if workflow_mode == "LEGACY_IDEA" else PROMPT_VERSION
            
            updated_context = dict(gc.source_context or {})
            updated_context["rationale"] = validated_data.get("rationale")
            updated_context["offer"] = validated_data.get("offer")
            updated_context["title"] = validated_data.get("title")
            updated_context["evidence"] = evidence
            gc.source_context = updated_context
            
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
        return "\n".join([
            f"Business Name: {bp.business_name}",
            f"Category: {bp.category or 'Unknown'}",
            f"Address: {bp.address or 'Unknown'}",
            f"Project Description: {project.description or 'None'}",
        ])

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
            
        review_context = self._build_review_context(project_id)
        if review_context:
            context_parts.append(review_context)

        if not context_parts:
            return "No clear competitor gaps or review signals identified yet."
            
        return "\n".join(context_parts)

    def _build_generation_intelligence(self, project_id: str, request_context: dict) -> tuple[str, dict]:
        """Build bounded, source-traceable intelligence using project-scoped database records."""
        self._verify_project(project_id)
        project = self.db.query(Project).filter_by(id=project_id).first()
        if not project:
            raise ValueError("Project not found")
        context_type = request_context.get("context_type")
        context_value = request_context.get("context_value")
        context_generation_id = request_context.get("context_generation_id")
        allowed_types = {"topic", "keyword", "content_type", "competitor_post", "marketing_opportunity"}
        if context_type and context_type not in allowed_types:
            raise ValueError("Unsupported intelligence context")

        filters = {}
        if context_type in {"topic", "keyword", "content_type"}:
            authoritative_gaps = {
                "topic": self.analytics_service.get_detailed_topic_gaps(project_id, limit=100),
                "keyword": self.analytics_service.get_detailed_keyword_gaps(project_id, limit=100),
                "content_type": self.analytics_service.get_content_type_gaps(project_id),
            }[context_type]
            name_key = {"topic": "topic", "keyword": "keyword", "content_type": "content_type"}[context_type]
            gap = next((item for item in authoritative_gaps if str(item.get(name_key, "")).casefold() == str(context_value or "").casefold()), None)
            if not gap:
                raise ValueError("The selected content gap is no longer available. Refresh strategy data and try again.")
            filters = {context_type: gap[name_key]}
            request_context["authoritative_gap"] = gap
        elif context_type == "competitor_post":
            competitor_ids = [row.business_id for row in self.db.query(ProjectCompetitor).filter_by(project_id=project_id, is_active=True).all()]
            post = self.db.query(Post).filter(Post.id == context_value, Post.business_id.in_(competitor_ids)).first()
            if not post:
                raise ValueError("The selected competitor post is unavailable for this project")
            filters = {"post_id": post.id}
        elif context_type == "marketing_opportunity":
            generation = self.db.query(GeneratedContent).filter_by(id=context_generation_id, project_id=project_id).first()
            if not generation or (generation.source_context or {}).get("workflow_mode") != "MARKETING_OPPORTUNITIES":
                raise ValueError("The selected marketing opportunity is unavailable")
            request_context["selected_opportunity"] = {
                "id": generation.id,
                "title": generation.topic,
                "analysis": generation.generated_idea,
                "evidence": (generation.source_context or {}).get("evidence", {}),
            }
            request_context["selected_source_post_ids"] = (generation.source_context or {}).get("evidence", {}).get("post_ids", [])

        competitors = self.db.query(ProjectCompetitor).filter_by(project_id=project_id, is_active=True).all()
        business_ids = [row.business_id for row in competitors]
        if project.own_business_id:
            business_ids.append(project.own_business_id)
        query = self.db.query(Post, AIAnalysis, BusinessProfile.business_name).join(
            BusinessProfile, Post.business_id == BusinessProfile.id
        ).outerjoin(AIAnalysis, AIAnalysis.post_id == Post.id).filter(Post.business_id.in_(business_ids))
        if context_type == "competitor_post":
            query = query.filter(Post.id == filters["post_id"])
        elif context_type == "marketing_opportunity":
            query = query.filter(Post.id.in_(request_context["selected_source_post_ids"]))
        elif context_type in {"topic", "keyword", "content_type"}:
            col = {"topic": AIAnalysis.topic, "keyword": AIAnalysis.keywords, "content_type": AIAnalysis.content_type}[context_type]
            if context_type == "keyword":
                query = query.filter(col.isnot(None))
            else:
                query = query.filter(col == filters[context_type])
        if not context_type:
            candidates = query.order_by(Post.published_date.desc()).limit(100).all()
            terms = [str(term).casefold() for term in [request_context.get("requested_topic"), request_context.get("requested_content_type"), *(request_context.get("requested_keywords") or [])] if term]
            if terms:
                def relevance(row):
                    post, analysis, _ = row
                    searchable = " ".join([post.text_content or "", (analysis.summary or "") if analysis else "", (analysis.topic or "") if analysis else "", (analysis.content_type or "") if analysis else "", " ".join(analysis.keywords or []) if analysis else ""]).casefold()
                    return sum(1 for term in terms if term in searchable)
                candidates = [row for row in candidates if relevance(row) > 0]
                candidates.sort(key=lambda row: (relevance(row), row[0].published_date or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
            rows = candidates[:12]
        else:
            rows = query.order_by(Post.published_date.desc()).limit(100 if context_type == "keyword" else 12).all()
        if context_type == "keyword":
            rows = [row for row in rows if filters["keyword"].casefold() in [str(k).casefold() for k in (row[1].keywords or [])]]
            rows = rows[:12]
        comp_ids = {row.business_id for row in competitors}
        evidence_posts = []
        for post, analysis, business_name in rows:
            summary = (analysis.summary if analysis else None) or (post.text_content or "")
            evidence_posts.append({
                "post_id": post.id,
                "business": business_name,
                "source": "competitor" if post.business_id in comp_ids else "own_business",
                "date": post.published_date.isoformat() if post.published_date else None,
                "summary": summary[:500],
                "topic": analysis.topic if analysis else None,
                "format": analysis.content_type if analysis else None,
                "keywords": (analysis.keywords or [])[:10] if analysis else [],
                "offer": analysis.offer_or_promotion if analysis else None,
            })

        if context_type in {"topic", "keyword", "content_type"}:
            gap_data = request_context.get("authoritative_gap", {})
            label = filters[context_type]
            base_intelligence = f"Selected gap evidence only: {context_type}={label}; competitor posts={gap_data.get('competitor_frequency')}; own business posts={gap_data.get('project_frequency')}; gap multiplier={gap_data.get('gap_score')}"
        elif context_type in {"competitor_post", "marketing_opportunity"}:
            base_intelligence = "Use the selected source item and its linked evidence as the primary context. Do not blend unrelated gaps or posts."
        else:
            base_intelligence = self._build_intel_context(project_id)
        sections = ["Evidence policy: distinguish database evidence below from recommendations. Missing or empty fields mean unknown; never infer competitor activity or performance metrics.", base_intelligence]
        if not context_type:
            report = self.db.query(IntelligenceReport).filter_by(project_id=project_id).order_by(IntelligenceReport.created_at.desc()).first()
            if report and report.status == "COMPLETED":
                report_data = {
                    "posts_analyzed": report.posts_analyzed,
                    "competitors_analyzed": report.competitors_analyzed,
                    "competitor_insights": report.competitor_insights,
                    "marketing_intelligence": report.marketing_intelligence,
                    "strategic_disconnects": report.strategic_disconnects,
                    "business_opportunities": report.business_opportunities,
                    "actionable_recommendations": report.actionable_recommendations,
                    "content_ideas": report.content_ideas,
                    "created_at": report.created_at.isoformat() if report.created_at else None,
                }
                sections.append("Latest saved combined intelligence report (precomputed; do not treat recommendations as observed facts): " + json.dumps(report_data, ensure_ascii=False, default=str)[:8000])
        if project.keywords:
            sections.append("Project keywords: " + ", ".join(project.keywords[:30]))
        sections.append("Competitor profiles: " + (", ".join(
            f"{c.business.business_name} ({c.business.category or 'category unavailable'})" for c in competitors if c.business
        ) or "No active tracked competitors."))
        frequency_rows = self.db.query(Post.business_id, BusinessProfile.business_name, func.count(Post.id), func.max(Post.scraped_date)).join(
            BusinessProfile, Post.business_id == BusinessProfile.id
        ).filter(Post.business_id.in_(business_ids)).group_by(Post.business_id, BusinessProfile.business_name).all() if business_ids else []
        sections.append("Observed posting volume and latest collection: " + ("; ".join(
            f"{name}: {count} collected posts; latest scrape {latest.isoformat() if latest else 'date unavailable'}"
            for _, name, count, latest in frequency_rows
        ) or "No post activity has been collected."))
        latest_scrape = max((row[3] for row in frequency_rows if row[3]), default=None)
        stale = not latest_scrape or (datetime.now(timezone.utc) - (latest_scrape.replace(tzinfo=timezone.utc) if latest_scrape.tzinfo is None else latest_scrape)).days > 30
        sections.append("Intelligence freshness: " + ("stale or unavailable (latest post collection is over 30 days old or missing); qualify conclusions." if stale else "recently collected within the last 30 days."))
        sections.append("Engagement/performance metrics: unavailable in collected post data; do not claim competitor engagement or performance.")
        sections.append("Relevant post evidence (summaries reused when present; limited to 12 relevant posts): " + (json.dumps(evidence_posts, ensure_ascii=False) if evidence_posts else "No relevant posts are available."))
        if request_context.get("selected_opportunity"):
            sections.append("Selected prior marketing opportunity: " + json.dumps(request_context["selected_opportunity"], ensure_ascii=False))
        if context_type in {"topic", "keyword", "content_type"}:
            sections.append("Selected authoritative content gap: " + json.dumps({"type": context_type, "value": context_value, **request_context.get("authoritative_gap", {})}, ensure_ascii=False))
        summary = "\n".join(sections)
        request_context["evidence_post_ids"] = [item["post_id"] for item in evidence_posts]
        request_context["intelligence_status"] = "insufficient" if not evidence_posts and not competitors else "stale" if stale else "available"
        return summary, {"posts": evidence_posts, "post_ids": request_context["evidence_post_ids"], "gap": request_context.get("authoritative_gap"), "intelligence_status": request_context["intelligence_status"]}

    def list_competitor_post_sources(self, project_id: str, limit: int = 50) -> list[dict]:
        self._verify_project(project_id)
        competitors = self.db.query(ProjectCompetitor).filter_by(project_id=project_id, is_active=True).all()
        competitor_ids = [row.business_id for row in competitors]
        rows = self.db.query(Post, AIAnalysis, BusinessProfile.business_name).join(
            BusinessProfile, Post.business_id == BusinessProfile.id
        ).outerjoin(AIAnalysis, AIAnalysis.post_id == Post.id).filter(
            Post.business_id.in_(competitor_ids)
        ).order_by(Post.published_date.desc()).limit(min(max(limit, 1), 100)).all()
        return [{
            "id": post.id,
            "business_name": name,
            "date": post.published_date.isoformat() if post.published_date else None,
            "summary": ((analysis.summary if analysis else None) or post.text_content or "")[:500],
            "topic": analysis.topic if analysis else None,
            "content_type": analysis.content_type if analysis else None,
        } for post, analysis, name in rows]

    def _build_review_context(self, project_id: str) -> str | None:
        project = self.db.query(Project).filter_by(id=project_id).first()
        if not project or not project.own_business_id:
            return None

        review_intel = self.db.query(ReviewIntelligence).filter_by(
            project_id=project_id,
            business_id=project.own_business_id,
        ).order_by(ReviewIntelligence.analyzed_at.desc()).first()
        if not review_intel:
            return None

        signals = []
        review_fields = (
            ("Overall sentiment", review_intel.overall_sentiment),
            ("Customer praise themes", review_intel.praise_themes),
            ("Customer complaint themes", review_intel.complaint_themes),
            ("Customer pain points", review_intel.pain_points),
            ("Customer needs", review_intel.customer_needs),
            ("Business opportunities", review_intel.business_opportunities),
        )
        for label, value in review_fields:
            if isinstance(value, list):
                clean_values = [str(item).strip() for item in value if str(item).strip()]
                if clean_values:
                    signals.append(f"{label}: {', '.join(clean_values)}")
            elif value:
                signals.append(f"{label}: {value}")

        if not signals:
            return None

        business_name = (
            project.own_business.business_name
            if project.own_business
            else "Selected business"
        )
        return "\n".join([
            "\n=== CUSTOMER REVIEW EVIDENCE FOR SELECTED BUSINESS ===",
            f"Business: {business_name}",
            "Use these as customer-interest signals, not as verified business facts. "
            "Do not quote reviews, claim universal customer agreement, or imply that "
            "complaints were resolved unless the business or campaign context confirms it.",
            *signals,
        ])
