import logging
import math
import random
import threading
import time
from email.utils import parsedate_to_datetime
from typing import List

from django.conf import settings
from django.db.models import Q
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    OpenAI,
    RateLimitError,
)

from articles.models import ArticlesVersion
from product.models import Product
from .models import ChatSession, ChatMessage

logger = logging.getLogger(__name__)


class ChatbotService:
    """
    Service responsible for:
    1. Finding relevant published articles.
    2. Sending only the selected article context + user question to OpenRouter.
    3. Saving the conversation in the database.
    """

    _MAX_CONCURRENT_REQUESTS = getattr(settings, "OPENROUTER_MAX_CONCURRENT", 3)
    _OPENAI_SEMAPHORE = threading.BoundedSemaphore(value=_MAX_CONCURRENT_REQUESTS)

    @staticmethod
    def get_openai_client():
        """
        Creates an OpenRouter-compatible OpenAI client configured for the chat completions endpoint.
        """
        api_key = getattr(settings, "OPENROUTER_API_KEY", None) or getattr(settings, "OPENAI_API_KEY", None)
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY or OPENAI_API_KEY is not configured in Django settings.")

        base_url = getattr(settings, "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        return OpenAI(api_key=api_key, base_url=base_url, max_retries=0)

    @staticmethod
    def _parse_retry_after(headers):
        if not headers:
            return None

        retry_after = headers.get("Retry-After")
        if not retry_after:
            return None

        try:
            return max(float(retry_after), 0.0)
        except (TypeError, ValueError):
            pass

        try:
            dt = parsedate_to_datetime(retry_after)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=None)
            return max((dt - time.time()).total_seconds(), 0.0)
        except Exception:
            return None

    @classmethod
    def _sleep_for_retry(cls, attempt: int, exc: Exception = None):
        retry_after = None
        if exc is not None and getattr(exc, "response", None) is not None:
            retry_after = cls._parse_retry_after(getattr(exc.response, "headers", {}) or {})

        if retry_after is None:
            base_delay = min(2 ** attempt, 10)
            retry_after = base_delay + random.uniform(0.25, 1.5)

        logger.warning("OpenRouter retry delay: %.2fs (attempt %s)", retry_after, attempt)
        time.sleep(retry_after)

    @classmethod
    def _is_retryable_error(cls, exc: Exception) -> bool:
        if isinstance(exc, (APIConnectionError, APITimeoutError)):
            return True
        if isinstance(exc, RateLimitError):
            return True
        if isinstance(exc, APIStatusError):
            status_code = getattr(exc, "status_code", None)
            return status_code in {429, 500, 502, 503, 504}
        return False

    @classmethod
    def _create_embedding_with_backoff(cls, text: str, model_name: str = None):
        if not text or not text.strip():
            return []

        client = cls.get_openai_client()
        if model_name is None:
            model_name = getattr(settings, "OPENROUTER_EMBEDDING_MODEL", "openai/text-embedding-3-small")

        last_exc = None
        for attempt in range(1, 5):
            try:
                with cls._OPENAI_SEMAPHORE:
                    response = client.embeddings.create(model=model_name, input=[text[:4096]])
                    return list(response.data[0].embedding)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if not cls._is_retryable_error(exc) or attempt >= 4:
                    logger.exception("OpenRouter embedding call failed for %s", model_name)
                    raise
                cls._sleep_for_retry(attempt, exc)

        if last_exc is not None:
            raise last_exc
        return []

    @classmethod
    def _chat_completion_with_backoff(cls, model_name: str, messages, temperature: float = 0.2):
        client = cls.get_openai_client()
        last_exc = None
        candidate_models = []

        primary_model = (model_name or "").strip()
        if primary_model:
            candidate_models.append(primary_model)

        fallback_models = getattr(settings, "OPENROUTER_FALLBACK_MODELS", "")
        for item in [x.strip() for x in fallback_models.split(",") if x and x.strip()]:
            if item not in candidate_models:
                candidate_models.append(item)

        for model in candidate_models:
            for attempt in range(1, 5):
                try:
                    with cls._OPENAI_SEMAPHORE:
                        return client.chat.completions.create(
                            model=model,
                            messages=messages,
                            temperature=temperature,
                        )
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    status_code = getattr(getattr(exc, "response", None), "status_code", None)
                    message_text = str(exc)
                    should_retry = cls._is_retryable_error(exc)
                    if status_code == 404 and "unavailable for free" in message_text.lower():
                        logger.warning("OpenRouter rejected free model %s; trying fallback model.", model)
                        break
                    if not should_retry or attempt >= 4:
                        logger.exception("OpenRouter chat completion failed for model %s", model)
                        if model != candidate_models[-1]:
                            continue
                        raise
                    cls._sleep_for_retry(attempt, exc)

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("OpenRouter chat completion failed without an exception")

    @staticmethod
    def cosine_similarity(a: List[float], b: List[float]) -> float:
        if not a or not b:
            return 0.0

        if len(a) != len(b):
            return 0.0

        dot = sum(x * y for x, y in zip(a, b))
        a_norm = math.sqrt(sum(x * x for x in a))
        b_norm = math.sqrt(sum(x * x for x in b))
        if a_norm == 0 or b_norm == 0:
            return 0.0
        return dot / (a_norm * b_norm)

    @staticmethod
    def _keyword_tokens(query: str):
        terms = []
        for token in query.lower().replace("-", " ").split():
            clean = token.strip(".,!?;:/()[]{}\"")
            if len(clean) > 2:
                terms.append(clean)
        return list(dict.fromkeys(terms))[:8]

    @staticmethod
    def _is_greeting(message: str) -> bool:
        if not message:
            return False

        normalized = message.strip().lower()
        greetings = [
            "hello",
            "hi",
            "hey",
            "good morning",
            "good afternoon",
            "good evening",
            "hi there",
            "hello there",
            "hey there",
            "greetings",
            "salutations",
            "yo",
        ]
        return normalized in greetings or any(normalized.startswith(greeting) for greeting in greetings)

    @staticmethod
    def _get_product_context(product_id=None):
        if not product_id:
            return ""

        try:
            product = Product.objects.filter(id=product_id).first()
        except Exception:
            return ""

        if not product:
            return ""

        name = (product.name or "").strip()
        description = (product.description or "").strip()

        if not name and not description:
            return ""

        if name.lower() == "hmis" or "health management information system" in (name.lower() + " " + description.lower()):
            product_text = "HMIS (Health Management Information System): a digital system for managing health records, patient data, service reporting, and operational health information."
        else:
            product_text = f"{name}: {description}" if description else f"{name}"

        return product_text

    @classmethod
    def generate_article_embedding(cls, version, force: bool = False):
        if version is None:
            return None

        if not force and getattr(version, "embedding", None):
            return version.embedding

        text = f"{version.article.title or ''}\n\n{version.content or ''}".strip()
        if not text:
            return None

        try:
            embedding = cls._create_embedding_with_backoff(text)
            if embedding:
                version.embedding = embedding
                version.save(update_fields=["embedding"])
            return embedding
        except Exception:
            logger.exception("Failed to generate embedding for article version %s", version.id)
            return None

    @classmethod
    def retrieve_relevant_knowledge(cls, query: str, limit: int = 5, product_id=None):
        """
        Retrieves the most relevant published article versions for the current product or globally.
        The answer must be grounded in article content instead of broad, unfocused KB guesses.
        """
        query = (query or "").strip()
        if not query:
            return "", []

        base_queryset = ArticlesVersion.objects.filter(status__iexact="PUBLISHED").select_related("article", "product_version__product")
        if product_id:
            base_queryset = base_queryset.filter(product_version__product_id=product_id)

        candidates = base_queryset
        if not candidates.exists():
            candidates = ArticlesVersion.objects.filter(status__iexact="PUBLISHED").select_related("article", "product_version__product")

        # Ensure published articles have embeddings before semantic matching. This keeps
        # retrieval grounded in the actual article content instead of empty or stale vectors.
        for version in candidates[:200]:
            if not getattr(version, "embedding", None):
                cls.generate_article_embedding(version, force=False)

        candidates = candidates.exclude(embedding__isnull=True)
        if not candidates.exists():
            keywords = cls._keyword_tokens(query)
            q = Q()
            for keyword in keywords:
                q |= Q(content__icontains=keyword) | Q(article__title__icontains=keyword)

            fallback = base_queryset.filter(q)[:limit]
            snippets = []
            article_ids = []
            for version in fallback:
                content = (version.content or "")[:2000]
                snippets.append(f"Title: {version.article.title}\nContent: {content}")
                article_ids.append(version.article_id)
            return "\n\n---\n\n".join(snippets), article_ids

        try:
            query_embedding = cls._create_embedding_with_backoff(query)
        except Exception:
            query_embedding = []

        scored_versions = []
        if query_embedding:
            for version in candidates:
                embedding = getattr(version, "embedding", None)
                if not embedding:
                    continue
                vector = list(embedding) if isinstance(embedding, (list, tuple)) else list(embedding)
                score = cls.cosine_similarity(query_embedding, vector)
                if score > 0.10:
                    scored_versions.append((score, version))

            if scored_versions:
                top_versions = [version for (_score, version) in sorted(scored_versions, key=lambda item: item[0], reverse=True)[:limit]]
                selected = []
                seen_ids = set()
                for version in top_versions:
                    if version.article_id in seen_ids:
                        continue
                    seen_ids.add(version.article_id)
                    selected.append(version)
                if selected:
                    snippets = []
                    article_ids = []
                    for version in selected:
                        content = (version.content or "")[:2000]
                        snippets.append(f"Title: {version.article.title}\nContent: {content}")
                        article_ids.append(version.article_id)
                    return "\n\n---\n\n".join(snippets), article_ids

        keywords = cls._keyword_tokens(query)
        q = Q()
        for keyword in keywords:
            q |= Q(content__icontains=keyword) | Q(article__title__icontains=keyword)

        fallback = base_queryset.filter(q)[:limit]
        snippets = []
        article_ids = []
        for version in fallback:
            content = (version.content or "")[:2000]
            snippets.append(f"Title: {version.article.title}\nContent: {content}")
            article_ids.append(version.article_id)

        return "\n\n---\n\n".join(snippets), article_ids

    @classmethod
    def generate_ai_response(cls, question: str, context: str, product_id=None) -> str:
        """
        Sends the user's question and retrieved article context to the OpenRouter chat completions API.
        """
        model_name = getattr(settings, "OPENROUTER_MODEL", "openai/gpt-5-mini")

        product_context = cls._get_product_context(product_id)

        if cls._is_greeting(question):
            greeting = "Hello! "
            if product_context:
                greeting += f"I’m here to help with {product_context}. "
            else:
                greeting += "I’m here to help with the HMIS health management system. "
            return greeting + "How would you like me to help you today?"

        if context:
            prompt = f"""
            You are a helpful customer support assistant.

            Answer the user's question using ONLY the knowledge provided below.

            If the knowledge does not contain enough information to answer the question,
            say that you don't have enough information and recommend contacting support.

            Do not invent facts, policies, prices, features, or procedures.

            Product context:
            ----------------
            {product_context if product_context else 'This request is for the HMIS (Health Management Information System).'}
            ----------------

            Knowledge base:
            ----------------
            {context}
            ----------------

            User question:
            {question}
            """
        else:
            prompt = f"""
                You are a helpful customer support assistant.

                We could not find any relevant articles in our knowledge base.

                Answer politely that you don't have enough information to provide a
                specific answer and recommend contacting the support team.

                Do not invent an answer.

                Product context:
                ----------------
                {product_context if product_context else 'This request is for the HMIS (Health Management Information System).'}
                ----------------

                User question:
                {question}
                """

        try:
            response = cls._chat_completion_with_backoff(
                model_name=model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful customer support assistant."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
            return response.choices[0].message.content.strip()
        except Exception:
            logger.exception("OpenRouter response generation failed")
            raise

    @classmethod
    def process_user_message(
        cls,
        session_key: str,
        question: str,
        product_id=None,
        email=None,
        client_ip=None,
    ) -> ChatMessage:
        """
        Finds or creates a ChatSession, retrieves relevant knowledge,
        asks OpenRouter to generate the response, and saves the message.
        """

        session, created = ChatSession.objects.get_or_create(
            session_key=session_key,
            defaults={
                "product_id": product_id,
                "email": email,
                "device_ip": client_ip,
            },
        )

        if email and not session.email:
            session.email = email
            session.save(update_fields=["email"])

        context, article_ids = cls.retrieve_relevant_knowledge(question, limit=5, product_id=product_id)

        try:
            bot_response = cls.generate_ai_response(question=question, context=context, product_id=product_id)
        except Exception:
            logger.exception("Chat response generation failed for session %s", session_key)
            bot_response = (
                "Sorry, I'm having trouble processing your question right now. "
                "Please try again later or contact our support team."
            )

        chat_message = ChatMessage.objects.create(
            session=session,
            question=question,
            response=bot_response,
            article_ids=article_ids,
        )

        return chat_message
