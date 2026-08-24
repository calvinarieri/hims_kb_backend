import json
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.db import transaction

from articles.models import Articles, ArticlesVersion, Category
from product.models import Product, ProductVersion
from chat.services import ChatbotService

logger = logging.getLogger(__name__)


class ArticleImpactService:
    """Find, analyze, and update all article versions affected by a product change."""

    _MAX_SEMANTIC_CANDIDATES = getattr(settings, "ARTICLE_IMPACT_MAX_CANDIDATES", 20)
    _MAX_CONCURRENT_ANALYSIS = getattr(settings, "ARTICLE_IMPACT_MAX_CONCURRENT", 3)
    _ANALYSIS_SEMAPHORE = threading.BoundedSemaphore(value=_MAX_CONCURRENT_ANALYSIS)

    @classmethod
    def _get_change_embedding(cls, change_description: str) -> List[float]:
        text = (change_description or "").strip()
        if not text:
            return []

        try:
            embedding = ChatbotService._create_embedding_with_backoff(
                text,
                model_name=getattr(settings, "OPENROUTER_EMBEDDING_MODEL", "openai/text-embedding-3-small"),
            )
            return embedding if embedding else []
        except Exception as e:
            logger.exception("Failed to generate embedding for change description: %s", str(e))
            return []

    @classmethod
    def _candidate_text(cls, version: ArticlesVersion) -> str:
        article = getattr(version, "article", None)
        parts = []
        if article:
            if getattr(article, "title", None):
                parts.append(str(article.title).strip())
            if getattr(article, "description", None):
                parts.append(str(article.description).strip())
        if getattr(version, "content", None):
            parts.append(str(version.content).strip())
        if getattr(version, "changes", None):
            parts.append(str(version.changes).strip())
        return "\n\n".join(part for part in parts if part)

    @classmethod
    def _search_semantic_candidates(cls, change_description: str, product_id: Optional[str] = None, limit: int = None) -> List[Dict[str, Any]]:
        if not change_description or not change_description.strip():
            return []

        query_embedding = cls._get_change_embedding(change_description)
        if not query_embedding:
            logger.warning("Could not generate embedding for change description; falling back to no semantic search.")
            return []

        queryset = ArticlesVersion.objects.filter(status__iexact="PUBLISHED").select_related("article")
        if product_id:
            queryset = queryset.filter(product_version__product_id=product_id)

        versions = list(queryset.exclude(embedding__isnull=True).exclude(embedding=[]).all())
        if not versions:
            logger.info("No published articles with embeddings found for semantic search.")
            return []

        scored = []
        for version in versions:
            embedding = getattr(version, "embedding", None)
            if not embedding:
                continue
            try:
                score = ChatbotService.cosine_similarity(query_embedding, list(embedding))
                if score <= 0:
                    continue
                scored.append({"version": version, "score": round(float(score), 6)})
            except Exception as e:
                logger.warning("Failed to compute similarity for version %s: %s", getattr(version, "id", "unknown"), str(e))
                continue

        scored.sort(key=lambda item: item["score"], reverse=True)
        max_candidates = limit or cls._MAX_SEMANTIC_CANDIDATES
        return scored[:max_candidates]

    @staticmethod
    def _clean_json_content(raw_text: str) -> Optional[Dict[str, Any]]:
        if not raw_text:
            return None

        cleaned = raw_text.strip()
        
        # Remove markdown code fences
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\n?```$", "", cleaned, flags=re.IGNORECASE)
            cleaned = cleaned.strip()

        # Try direct JSON parse first
        try:
            loaded = json.loads(cleaned)
            if isinstance(loaded, dict):
                return loaded
        except json.JSONDecodeError:
            pass

        # Try to extract JSON object from text
        match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", cleaned, flags=re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                logger.warning("Failed to parse extracted JSON object.")
                return None

        logger.warning("No valid JSON found in response.")
        return None

    @classmethod
    def _parse_impact_analysis(cls, content: str) -> Dict[str, Any]:
        payload = cls._clean_json_content(content)
        if not payload:
            logger.warning("Impact analysis returned invalid JSON.")
            return {
                "article_id": None,
                "impact": "NOT_AFFECTED",
                "reason": "The model did not return valid JSON for impact analysis.",
                "affected_sections": [],
            }

        article_id = payload.get("article_id") or payload.get("id")
        impact = (payload.get("impact") or "NOT_AFFECTED").upper()
        if impact not in {"AFFECTED", "NOT_AFFECTED"}:
            impact = "NOT_AFFECTED"
            logger.warning("Unknown impact value in analysis; defaulting to NOT_AFFECTED.")

        return {
            "article_id": article_id,
            "impact": impact,
            "reason": (payload.get("reason") or "").strip() or "No reason provided.",
            "affected_sections": payload.get("affected_sections") or [],
        }

    @classmethod
    def _build_impact_prompt(cls, version: ArticlesVersion, change_description: str) -> str:
        article = version.article
        article_text = cls._candidate_text(version)
        return (
            "You are a knowledge-base curator classifying whether an article is affected by a platform change. "
            "Return ONLY valid JSON with no additional text.\n\n"
            "Use this exact schema:\n"
            "{\n"
            '  "article_id": "<article-uuid>",\n'
            '  "impact": "AFFECTED" or "NOT_AFFECTED",\n'
            '  "reason": "brief rationale (1-2 sentences)",\n'
            '  "affected_sections": ["section name", ...]\n'
            "}\n\n"
            "IMPACT CRITERIA:\n"
            "An article is AFFECTED if the change would make any existing statement, step, example, prerequisite, "
            "warning, or procedural instruction incorrect, incomplete, misleading, or obsolete. Consider:\n"
            "- Direct references to changed features or behavior\n"
            "- Dependent workflows or prerequisites\n"
            "- Related examples, troubleshooting steps, or warnings\n"
            "- Indirect dependencies or synonyms\n\n"
            f"ARTICLE TITLE: {article.title if article else 'Untitled'}\n\n"
            f"ARTICLE CONTENT:\n{article_text[:4000]}\n\n"
            f"CHANGE DESCRIPTION:\n{change_description[:1500]}\n"
        )

    @classmethod
    def _serializable_impact_analysis(cls, impact_analysis: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(impact_analysis, dict):
            return {}

        cleaned = {}
        for key, value in impact_analysis.items():
            if key == 'version':
                continue
            if isinstance(value, (list, tuple, set)):
                cleaned[key] = [str(item).strip() for item in value if item]
            elif isinstance(value, (str, int, float, bool)) or value is None:
                cleaned[key] = value
            else:
                cleaned[key] = str(value).strip()
        return cleaned

    @classmethod
    def _build_update_prompt(cls, version: ArticlesVersion, change_description: str, impact_analysis: Dict[str, Any]) -> str:
        article = version.article
        existing_content = (version.content or "").strip()
        safe_impact = cls._serializable_impact_analysis(impact_analysis)
        
        return (
            "You are updating a knowledge-base article to reflect a platform change. "
            "Return ONLY valid HTML with no markdown fences, JSON, or explanatory text.\n\n"
            "CORE RULES:\n"
            "1. Preserve all content unrelated to the change.\n"
            "2. Replace outdated procedures with the correct new procedure.\n"
            "3. Remove steps, warnings, examples, or prerequisites that are now incorrect or obsolete.\n"
            "4. Update any dependent instructions that relied on the old behavior.\n"
            "5. Maintain consistent logical flow from start to finish.\n"
            "6. Do not invent facts; only use information from the existing article and change description.\n"
            "7. Do not rewrite from scratch; edit the existing article in place.\n\n"
            f"ARTICLE TITLE: {article.title if article else 'Untitled'}\n\n"
            f"EXISTING ARTICLE HTML:\n{existing_content}\n\n"
            f"CHANGE DESCRIPTION:\n{change_description}\n\n"
            f"IMPACT ANALYSIS:\n{json.dumps(safe_impact, ensure_ascii=False, indent=2)}\n"
        )

    @classmethod
    def _validate_openfront_html(cls, candidate_html: str) -> Optional[str]:
        if not candidate_html:
            return None

        html = candidate_html.strip()
        
        # Remove markdown code fences if present
        if html.startswith("```"):
            html = re.sub(r"^```(?:html)?\s*\n?", "", html, flags=re.IGNORECASE)
            html = re.sub(r"\n?```$", "", html, flags=re.IGNORECASE)
            html = html.strip()

        if not html:
            return None

        # Validate presence of HTML tags
        if not re.search(r"<\s*(?:h[1-6]|p|ul|ol|li|div|section|article|table|strong|em|span|a|img|br)[^>]*>", html, flags=re.IGNORECASE):
            logger.warning("HTML does not contain valid content tags.")
            return None

        # Ensure at least minimal HTML structure
        has_heading = bool(re.search(r"<\s*h[1-6][^>]*>", html, flags=re.IGNORECASE))
        has_body = bool(re.search(r"<\s*(?:p|ul|ol|div|section)[^>]*>", html, flags=re.IGNORECASE))
        
        if not (has_heading or has_body):
            logger.warning("HTML lacks heading or body content.")
            return None

        return html

    @classmethod
    def resolve_product_version(cls, product_id=None, product_version_id=None):
        """Resolve a product version from product_id or product_version_id."""
        if product_version_id:
            return ProductVersion.objects.select_related('product').get(id=product_version_id)

        if product_id:
            product = Product.objects.get(id=product_id)
            return product.versions.order_by('-created_at').first() or ProductVersion.objects.create(
                product=product,
                version='impact-change',
                description='Auto-created from impact analysis of product change.',
            )

        raise ValueError("A product_id or product_version_id is required.")

    @classmethod
    def _analyze_candidate(cls, candidate: Dict[str, Any], change_description: str) -> Dict[str, Any]:
        """Analyze a single article version for impact. This runs in a thread pool."""
        version = candidate["version"]
        article = version.article
        
        # Use semaphore to limit concurrent API calls
        with cls._ANALYSIS_SEMAPHORE:
            prompt = cls._build_impact_prompt(version, change_description)
            try:
                response = ChatbotService._chat_completion_with_backoff(
                    model_name=getattr(settings, "OPENROUTER_MODEL", "openai/gpt-4-mini"),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                )
                content = (response.choices[0].message.content or "").strip()
            except Exception as e:
                logger.exception("Impact analysis failed for article %s: %s", getattr(article, "id", "unknown"), str(e))
                return {
                    "article_id": str(getattr(article, "id", "")),
                    "impact": "NOT_AFFECTED",
                    "reason": f"Analysis error: {str(e)[:100]}",
                    "affected_sections": [],
                    "version": version,
                    "error": True,
                }

        parsed = cls._parse_impact_analysis(content)
        parsed["version"] = version
        parsed["article_id"] = parsed.get("article_id") or str(getattr(article, "id", ""))
        parsed["error"] = False
        return parsed

    @classmethod
    def _generate_title_and_description(cls, version: ArticlesVersion, change_description: str, impact_analysis: Dict[str, Any]) -> tuple:
        """Generate an AI-created title and description reflecting the impact of the change."""
        article = version.article
        current_title = article.title if article else "Untitled"
        safe_impact = cls._serializable_impact_analysis(impact_analysis)
        
        prompt = (
            "You are updating an article's title and description to reflect a product change. "
            "Return ONLY valid JSON with no additional text.\n\n"
            "{\n"
            '  "title": "updated article title (keep under 80 characters)",\n'
            '  "description": "concise 1-2 sentence summary of what changed in this article (under 200 chars)"\n'
            "}\n\n"
            f"CURRENT ARTICLE TITLE: {current_title}\n\n"
            f"PRODUCT CHANGE:\n{change_description[:800]}\n\n"
            f"IMPACT ANALYSIS:\n"
            f'- Affected sections: {", ".join(safe_impact.get("affected_sections", []))}\n'
            f'- Reason: {safe_impact.get("reason", "Unknown impact")}\n\n'
            "Generate a title and brief description that reflect how this article was updated by the change. "
            "The title should be similar to the current one but indicate the change. "
            "The description should explain what changed in this article specifically."
        )
        
        try:
            response = ChatbotService._chat_completion_with_backoff(
                model_name=getattr(settings, "OPENROUTER_MODEL", "openai/gpt-4-mini"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            content = (response.choices[0].message.content or "").strip()
            payload = cls._clean_json_content(content)
            
            if payload and isinstance(payload, dict):
                title = (payload.get("title") or "").strip()
                description = (payload.get("description") or "").strip()
                
                # Validate and sanitize
                if title and len(title) <= 200:
                    title = re.sub(r"\s+", " ", title).strip()
                else:
                    title = None
                    
                if description and len(description) <= 500:
                    description = re.sub(r"\s+", " ", description).strip()
                else:
                    description = None
                
                return (title, description)
            else:
                logger.warning("Failed to parse title/description JSON for article %s", getattr(article, "id", "unknown"))
                return (None, None)
                
        except Exception as e:
            logger.warning("Failed to generate title/description for article %s: %s", getattr(article, "id", "unknown"), str(e))
            return (None, None)

    @classmethod
    def _should_create_new_article(cls, change_description: str, affected_count: int) -> bool:
        """Determine if a product change warrants creating an entirely new article."""
        # If very few articles are affected but change is significant, create new article
        if affected_count == 0 and change_description.strip():
            return True
        return False

    @classmethod
    def _generate_article_from_change(cls, change_description: str, product_version, category, user) -> Optional[Dict[str, Any]]:
        """Generate a brand new article from a product change description."""
        prompt = (
            "You are creating a new knowledge-base article to document a product change. "
            "Generate the article title, short description, and detailed HTML content. "
            "Return ONLY valid JSON with no additional text.\\n\\n"
            "{\n"
            '  "title": "article title (max 80 chars)",\n'
            '  "description": "1-2 sentence summary (max 200 chars)",\n'
            '  "content": "complete HTML article with <h1>, <h2>, <p>, <ul> tags explaining the change"\n'
            "}\n\n"
            "PRODUCT CHANGE:\n"
            f"{change_description}\n\n"
            "Create comprehensive documentation covering:\n"
            "- What changed and why\n"
            "- How users are affected\n"
            "- Step-by-step instructions for new workflows\n"
            "- Examples and use cases\n"
            "- Migration steps if applicable\n"
            "- Troubleshooting tips"
        )

        try:
            response = ChatbotService._chat_completion_with_backoff(
                model_name=getattr(settings, "OPENROUTER_MODEL", "openai/gpt-4-mini"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            content = (response.choices[0].message.content or "").strip()
            payload = cls._clean_json_content(content)

            if not payload or not isinstance(payload, dict):
                logger.warning("Failed to parse generated article JSON")
                return None

            title = (payload.get("title") or "").strip()
            description = (payload.get("description") or "").strip()
            article_html = (payload.get("content") or "").strip()

            # Validate
            if not title or len(title) > 200:
                logger.warning("Generated article title invalid: %s", title)
                return None
            if not description or len(description) > 500:
                logger.warning("Generated article description invalid: %s", description)
                return None
            if not article_html:
                logger.warning("Generated article content empty")
                return None

            # Validate HTML
            sanitized_html = cls._validate_openfront_html(article_html)
            if not sanitized_html:
                logger.warning("Generated article HTML failed validation")
                return None

            try:
                with transaction.atomic():
                    # Create article
                    article = Articles.objects.create(
                        title=title,
                        description=description,
                        category=category,
                        visibility="PUBLIC",
                        status="REVIEW",
                    )

                    # Create version
                    version = ArticlesVersion.objects.create(
                        article=article,
                        product_version=product_version,
                        content=sanitized_html,
                        changes=f"Auto-generated article from product change: {change_description[:200]}",
                        status="REVIEW",
                        author=user,
                        reviewed_by=user if getattr(user, "is_staff", False) else None,
                    )

                    # Generate embedding
                    try:
                        ChatbotService.generate_article_embedding(version, force=True)
                    except Exception as e:
                        logger.warning("Failed to generate embedding for new article %s: %s", article.id, str(e))

                    logger.info("Created new article %s: %s", article.id, title)

                    return {
                        "article_id": str(article.id),
                        "title": title,
                        "description": description,
                        "version_id": str(version.id),
                        "content": sanitized_html,
                    }

            except Exception as e:
                logger.exception("Failed to save generated article: %s", str(e))
                return None

        except Exception as e:
            logger.warning("Failed to generate article from change: %s", str(e))
            return None

    @classmethod
    def _update_article_version(cls, version: ArticlesVersion, change_description: str, impact_analysis: Dict[str, Any]) -> bool:
        """Update an article version's content based on impact analysis."""
        article = version.article
        prompt = cls._build_update_prompt(version, change_description, impact_analysis)

        try:
            response = ChatbotService._chat_completion_with_backoff(
                model_name=getattr(settings, "OPENROUTER_MODEL", "openai/gpt-4-mini"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            raw_html = (response.choices[0].message.content or "").strip()
        except Exception as e:
            logger.exception("HTML rewrite failed for article %s: %s", getattr(article, "id", "unknown"), str(e))
            return False

        sanitized_html = cls._validate_openfront_html(raw_html)
        if sanitized_html is None:
            logger.warning("Rejected malformed article HTML for version %s", getattr(version, "id", None))
            return False

        # Generate new title and description reflecting the change
        new_title, new_description = cls._generate_title_and_description(version, change_description, impact_analysis)

        try:
            with transaction.atomic():
                version.content = sanitized_html
                version.changes = change_description
                version.status = "REVIEW"
                version.save(update_fields=["content", "changes", "status", "updated_at"])

                if article is not None:
                    # Update title if LLM generated one
                    if new_title:
                        article.title = new_title
                        logger.info("Generated new title for article %s: %s", getattr(article, "id", "unknown"), new_title)
                    
                    # Update description if LLM generated one
                    if new_description:
                        article.description = new_description
                        logger.info("Generated new description for article %s: %s", getattr(article, "id", "unknown"), new_description)
                    elif not article.description:
                        # Only use change description as fallback if no description exists
                        article.description = change_description.strip()[:200]
                    
                    article.status = "REVIEW"
                    update_fields = ["status", "updated_at"]
                    if new_title:
                        update_fields.append("title")
                    if new_description:
                        update_fields.append("description")
                    article.save(update_fields=update_fields)

                # Regenerate embedding for updated content
                try:
                    ChatbotService.generate_article_embedding(version, force=True)
                except Exception as e:
                    logger.warning("Failed to regenerate embedding for version %s: %s", getattr(version, "id", "unknown"), str(e))
                    
        except Exception as e:
            logger.exception("Database update failed for article version %s: %s", getattr(version, "id", "unknown"), str(e))
            return False

        return True

    @classmethod
    def process_change(cls, change_description: str, product_id: Optional[str] = None, limit: int = 20, user=None, create_article_if_needed: bool = True):
        """Process a product change and update all affected articles. Create new article if needed."""
        if not change_description or not change_description.strip():
            logger.warning("process_change called with empty change description.")
            return {
                "change": "",
                "candidates_found": 0,
                "affected_articles": 0,
                "updated_articles": 0,
                "unchanged_articles": 0,
                "failed_articles": [],
                "analysis": [],
                "created_articles": [],
            }

        logger.info("Processing change: %s", change_description[:100])
        
        candidates = cls._search_semantic_candidates(change_description, product_id=product_id, limit=limit)
        if not candidates:
            logger.info("No candidate articles found for change.")
            
            # Attempt to create new article if no candidates found
            created = []
            if create_article_if_needed and user:
                logger.info("No existing articles found. Attempting to create new article.")
                try:
                    product_version = cls.resolve_product_version(product_id=product_id)
                    category = Category.objects.filter(name="General").first()
                    if not category:
                        category = Category.objects.create(
                            name="General",
                            description="Auto-generated content from product changes."
                        )
                    
                    new_article = cls._generate_article_from_change(
                        change_description,
                        product_version,
                        category,
                        user
                    )
                    if new_article:
                        created.append(new_article)
                        logger.info("Successfully created new article from change")
                except Exception as e:
                    logger.exception("Failed to create new article: %s", str(e))
            
            return {
                "change": change_description,
                "candidates_found": 0,
                "affected_articles": 0,
                "updated_articles": 0,
                "unchanged_articles": 0,
                "failed_articles": [],
                "analysis": [],
                "created_articles": created,
            }

        logger.info("Found %d candidate articles for impact analysis.", len(candidates))
        
        # Analyze candidates in parallel with bounded concurrency
        analysis_results = []
        max_workers = min(len(candidates), cls._MAX_CONCURRENT_ANALYSIS)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(cls._analyze_candidate, candidate, change_description): candidate
                for candidate in candidates
            }
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    analysis_results.append(result)
                except Exception as e:
                    logger.exception("Candidate analysis crashed: %s", str(e))

        # Filter for affected articles
        affected_versions = []
        for result in analysis_results:
            if result and result.get("impact") == "AFFECTED":
                version = result.get("version")
                if version is not None:
                    affected_versions.append((version, result))

        logger.info("Found %d affected articles out of %d analyzed.", len(affected_versions), len(analysis_results))

        # Update affected articles
        updated_count = 0
        failed = []
        for version, result in affected_versions:
            try:
                if cls._update_article_version(version, change_description, result):
                    updated_count += 1
                    logger.info("Successfully updated article %s", getattr(version.article, "id", "unknown"))
                else:
                    article_id = str(getattr(version.article, "id", ""))
                    failed.append(article_id)
                    logger.warning("Failed to update article %s", article_id)
            except Exception as e:
                article_id = str(getattr(version.article, "id", ""))
                failed.append(article_id)
                logger.exception("Error updating article %s: %s", article_id, str(e))

        unchanged = max(len(candidates) - len(affected_versions), 0)
        
        # Create new article if needed and no articles were affected
        created = []
        if create_article_if_needed and len(affected_versions) == 0 and user:
            logger.info("No articles affected by change. Attempting to create new article.")
            try:
                product_version = cls.resolve_product_version(product_id=product_id)
                category = Category.objects.filter(name="General").first()
                if not category:
                    category = Category.objects.create(
                        name="General",
                        description="Auto-generated content from product changes."
                    )
                
                new_article = cls._generate_article_from_change(
                    change_description,
                    product_version,
                    category,
                    user
                )
                if new_article:
                    created.append(new_article)
                    logger.info("Successfully created new article from change")
            except Exception as e:
                logger.exception("Failed to create new article: %s", str(e))
        
        return {
            "change": change_description,
            "candidates_found": len(candidates),
            "affected_articles": len(affected_versions),
            "updated_articles": updated_count,
            "unchanged_articles": unchanged,
            "failed_articles": failed,
            "analysis": analysis_results,
            "created_articles": created,
        }