import json
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.db import transaction

from articles.models import ArticlesVersion
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
            return ChatbotService._create_embedding_with_backoff(
                text,
                model_name=getattr(settings, "OPENROUTER_EMBEDDING_MODEL", "openai/text-embedding-3-small"),
            )
        except Exception:
            logger.exception("Failed to generate embedding for change description.")
            return []

    @classmethod
    def _candidate_text(cls, version: ArticlesVersion) -> str:
        article = getattr(version, "article", None)
        parts = []
        if article:
            if getattr(article, "title", None):
                parts.append(article.title)
            if getattr(article, "description", None):
                parts.append(article.description)
        if getattr(version, "content", None):
            parts.append(version.content)
        if getattr(version, "changes", None):
            parts.append(version.changes)
        return "\n\n".join(part for part in parts if part and str(part).strip())

    @classmethod
    def _search_semantic_candidates(cls, change_description: str, product_id: Optional[str] = None, limit: int = None) -> List[Dict[str, Any]]:
        if not change_description or not change_description.strip():
            return []

        query_embedding = cls._get_change_embedding(change_description)
        if not query_embedding:
            return []

        queryset = ArticlesVersion.objects.filter(status__iexact="PUBLISHED").select_related("article")
        if product_id:
            queryset = queryset.filter(product_version__product_id=product_id)

        versions = list(queryset.exclude(embedding__isnull=True).exclude(embedding=[]).all())
        if not versions:
            return []

        scored = []
        for version in versions:
            embedding = getattr(version, "embedding", None)
            if not embedding:
                continue
            score = ChatbotService.cosine_similarity(query_embedding, list(embedding))
            if score <= 0:
                continue
            scored.append({"version": version, "score": round(float(score), 6)})

        scored.sort(key=lambda item: item["score"], reverse=True)
        max_candidates = limit or cls._MAX_SEMANTIC_CANDIDATES
        return scored[:max_candidates]

    @staticmethod
    def _clean_json_content(raw_text: str) -> Optional[Dict[str, Any]]:
        if not raw_text:
            return None

        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.IGNORECASE)

        try:
            loaded = json.loads(cleaned)
            if isinstance(loaded, dict):
                return loaded
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None

        return None

    @classmethod
    def _parse_impact_analysis(cls, content: str) -> Dict[str, Any]:
        payload = cls._clean_json_content(content)
        if not payload:
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

        return {
            "article_id": article_id,
            "impact": impact,
            "reason": payload.get("reason") or "No reason provided.",
            "affected_sections": payload.get("affected_sections") or [],
        }

    @classmethod
    def _build_impact_prompt(cls, version: ArticlesVersion, change_description: str) -> str:
        article = version.article
        article_text = cls._candidate_text(version)
        return (
            "You are classifying whether a knowledge-base article is affected by a platform change. "
            "Return only valid JSON.\n\n"
            "Use this exact schema: {\n"
            "  \"article_id\": <uuid-or-id>,\n"
            "  \"impact\": \"AFFECTED\" or \"NOT_AFFECTED\",\n"
            "  \"reason\": \"very short rationale\",\n"
            "  \"affected_sections\": [\"section name\", ...]\n"
            "}\n\n"
            "Consider direct references, related workflows, prerequisites, instructions, examples, warnings, troubleshooting, "
            "synonyms, spelling variations, and indirect dependencies. An article is AFFECTED if the change would make any "
            "existing statement, step, example, prerequisite, or dependency incorrect, incomplete, or misleading.\n\n"
            f"ARTICLE TITLE: {article.title if article else 'Untitled'}\n\n"
            f"ARTICLE CONTENT:\n{article_text}\n\n"
            f"CHANGE DESCRIPTION:\n{change_description}\n"
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
                cleaned[key] = [str(item) for item in value]
            elif isinstance(value, (str, int, float, bool)) or value is None:
                cleaned[key] = value
            else:
                cleaned[key] = str(value)
        return cleaned

    @classmethod
    def _build_update_prompt(cls, version: ArticlesVersion, change_description: str, impact_analysis: Dict[str, Any]) -> str:
        article = version.article
        existing_content = version.content or ""
        safe_impact = cls._serializable_impact_analysis(impact_analysis)
        return (
            "Update this existing article in place. Preserve all valid information that remains correct. Modify only the parts affected by the new change. "
            "Remove outdated instructions, examples, prerequisites, and warnings that conflict with the new change. Keep the article structure intact wherever possible. "
            "Do not write a new article from scratch. Use the article's existing content as the starting point and revise only what is necessary.\n\n"
            "Return only valid OpenFront HTML. No markdown fences, no JSON, no explanation text before or after the HTML.\n\n"
            "CORE RULES:\n"
            "1. Preserve unrelated content and organization.\n"
            "2. Replace outdated procedures with the new procedure.\n"
            "3. Remove obsolete steps, warnings, or examples that are no longer correct.\n"
            "4. Update dependent instructions if they rely on the changed behavior.\n"
            "5. Keep the final result logically consistent from start to finish.\n"
            "6. Do not invent facts not present in the existing article or the new change description.\n\n"
            f"ARTICLE TITLE: {article.title if article else 'Untitled'}\n\n"
            f"EXISTING ARTICLE:\n{existing_content}\n\n"
            f"NEW CHANGE:\n{change_description}\n\n"
            f"IMPACT ANALYSIS:\n{json.dumps(safe_impact, ensure_ascii=False)}\n"
        )

    @classmethod
    def _validate_openfront_html(cls, candidate_html: str) -> Optional[str]:
        if not candidate_html:
            return None

        html = candidate_html.strip()
        if html.startswith("```"):
            html = re.sub(r"^```(?:html)?\s*", "", html, flags=re.IGNORECASE)
            html = re.sub(r"\s*```$", "", html, flags=re.IGNORECASE)

        if not html:
            return None

        if not re.search(r"<\s*(h[1-6]|p|ul|ol|li|div|table|section|article|strong|span|a|img|br)[^>]*>", html, flags=re.IGNORECASE):
            return None

        if "<html" not in html.lower() and "<h1" not in html.lower() and "<p" not in html.lower():
            return None

        return html

    @classmethod
    def _analyze_candidate(cls, candidate: Dict[str, Any], change_description: str) -> Dict[str, Any]:
        version = candidate["version"]
        with cls._ANALYSIS_SEMAPHORE:
            prompt = cls._build_impact_prompt(version, change_description)
            try:
                response = ChatbotService._chat_completion_with_backoff(
                    model_name=getattr(settings, "OPENROUTER_MODEL", "openai/gpt-5-mini"),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                )
                content = (response.choices[0].message.content or "").strip()
            except Exception:
                logger.exception("Impact analysis failed for article version %s", getattr(version, "id", None))
                return {
                    "article_id": str(getattr(version.article, "id", "")),
                    "impact": "NOT_AFFECTED",
                    "reason": "Impact analysis request failed; article left unchanged.",
                    "affected_sections": [],
                    "version": version,
                }

        parsed = cls._parse_impact_analysis(content)
        parsed["version"] = version
        parsed["article_id"] = parsed.get("article_id") or str(getattr(version.article, "id", ""))
        return parsed

    @classmethod
    def _update_article_version(cls, version: ArticlesVersion, change_description: str, impact_analysis: Dict[str, Any]) -> bool:
        article = version.article
        prompt = cls._build_update_prompt(version, change_description, impact_analysis)

        try:
            response = ChatbotService._chat_completion_with_backoff(
                model_name=getattr(settings, "OPENROUTER_MODEL", "openai/gpt-5-mini"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            raw_html = (response.choices[0].message.content or "").strip()
        except Exception:
            logger.exception("HTML rewrite failed for article version %s", getattr(version, "id", None))
            return False

        sanitized_html = cls._validate_openfront_html(raw_html)
        if sanitized_html is None:
            logger.warning("Rejected malformed article HTML for version %s", getattr(version, "id", None))
            return False

        try:
            with transaction.atomic():
                version.content = sanitized_html
                version.changes = change_description
                version.status = "REVIEW"
                version.save(update_fields=["content", "changes", "status", "updated_at"])

                if article is not None:
                    existing_description = (article.description or "").strip()
                    summary = change_description.strip()
                    if summary:
                        if not existing_description:
                            article.description = summary
                        elif summary.lower() not in existing_description.lower():
                            article.description = f"{existing_description}\n\n{summary}"
                    article.status = "REVIEW"
                    article.save(update_fields=["description", "status", "updated_at"])

                ChatbotService.generate_article_embedding(version, force=True)
        except Exception:
            logger.exception("Database update failed for article version %s", getattr(version, "id", None))
            return False

        return True

    @classmethod
    def process_change(cls, change_description: str, product_id: Optional[str] = None, limit: int = 20):
        if not change_description or not change_description.strip():
            return {
                "change": "",
                "candidates_found": 0,
                "affected_articles": 0,
                "updated_articles": 0,
                "unchanged_articles": 0,
                "failed_articles": [],
            }

        candidates = cls._search_semantic_candidates(change_description, product_id=product_id, limit=limit)
        if not candidates:
            return {
                "change": change_description,
                "candidates_found": 0,
                "affected_articles": 0,
                "updated_articles": 0,
                "unchanged_articles": 0,
                "failed_articles": [],
            }

        analysis_results = []
        with ThreadPoolExecutor(max_workers=min(len(candidates), cls._MAX_CONCURRENT_ANALYSIS)) as executor:
            futures = {
                executor.submit(cls._analyze_candidate, candidate, change_description): candidate
                for candidate in candidates
            }
            for future in as_completed(futures):
                try:
                    analysis_results.append(future.result())
                except Exception:
                    logger.exception("Candidate analysis crashed.")

        affected_versions = []
        failed = []
        for result in analysis_results:
            if (result or {}).get("impact") == "AFFECTED":
                version = result.get("version")
                if version is not None:
                    affected_versions.append((version, result))

        updated_count = 0
        for version, result in affected_versions:
            if cls._update_article_version(version, change_description, result):
                updated_count += 1
            else:
                failed.append(str(getattr(version.article, "id", "")))

        unchanged = max(len(candidates) - len(affected_versions), 0)
        return {
            "change": change_description,
            "candidates_found": len(candidates),
            "affected_articles": len(affected_versions),
            "updated_articles": updated_count,
            "unchanged_articles": unchanged,
            "failed_articles": failed,
            "analysis": analysis_results,
        }
