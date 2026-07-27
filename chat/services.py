from django.db.models import Q
from articles.models import ArticlesVersion
from .models import ChatSession, ChatMessage


class ChatbotService:
    @staticmethod
    def retrieve_relevant_knowledge(query: str, limit: int = 3):
        """
        Retrieves published article versions matching the query and extracts Article UUIDs.
        """
        results = ArticlesVersion.objects.filter(
            Q(content__icontains=query) | Q(article__title__icontains=query),
            status='published'
        ).select_related('article')[:limit]

        context_snippets = []
        article_ids = []

        for item in results:
            context_snippets.append(f"Title: {item.article.title}\nContent: {item.content[:500]}")
            article_ids.append(item.article.id)

        context = "\n\n---\n\n".join(context_snippets)
        return context, article_ids

    @classmethod
    def process_user_message(cls, session_key: str, question: str, product_id=None, email=None, client_ip=None) -> ChatMessage:
        """
        Finds or creates a ChatSession, retrieves article context, gets response, and saves a ChatMessage record.
        """
        session, created = ChatSession.objects.get_or_create(
            session_key=session_key,
            defaults={
                'product_id': product_id,
                'email': email,
                'device_ip': client_ip
            }
        )

        if email and not session.email:
            session.email = email
            session.save(update_fields=['email'])

        context, article_ids = cls.retrieve_relevant_knowledge(question)

        if context:
            bot_response = f"Based on our articles, here is what I found regarding '{question}':\n\n{context[:300]}..."
        else:
            bot_response = f"Thanks for asking! I couldn't find specific articles regarding '{question}', but our support team can help."

        chat_message = ChatMessage.objects.create(
            session=session,
            question=question,
            response=bot_response,
            article_ids=article_ids
        )

        return chat_message