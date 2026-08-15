import logging

from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from chat.services import ChatbotService
from .models import Articles, ArticlesVersion, ArticleTag, ArticleImage

logger = logging.getLogger(__name__)


def clear_article_caches(article_id=None):
    """
    Clears cache entries related to articles and search results.
    """
    if article_id:
        cache.delete(f"article_detail_{article_id}")

    try:
        cache.delete_pattern("search_results_*")
        cache.delete_pattern("staff_articles_*")
    except AttributeError:
        cache.clear()


@receiver([post_save, post_delete], sender=Articles)
def on_article_change(sender, instance, **kwargs):
    clear_article_caches(instance.id)


@receiver([post_save], sender=ArticlesVersion)
def on_version_change(sender, instance, **kwargs):
    clear_article_caches(instance.article_id)
    if getattr(instance, "content", None) and not getattr(instance, "embedding", None):
        try:
            if not getattr(instance, '_embedding_generation_in_progress', False):
                instance._embedding_generation_in_progress = True
                ChatbotService.generate_article_embedding(instance, force=False)
        except Exception:
            logger.exception("Failed to generate embedding for article version %s", instance.id)
        finally:
            instance._embedding_generation_in_progress = False


@receiver([post_delete], sender=ArticlesVersion)
def on_version_delete(sender, instance, **kwargs):
    clear_article_caches(instance.article_id)


@receiver([post_save, post_delete], sender=ArticleTag)
def on_tag_change(sender, instance, **kwargs):
    clear_article_caches(instance.article_id)


@receiver([post_save, post_delete], sender=ArticleImage)
def on_image_change(sender, instance, **kwargs):
    clear_article_caches(instance.article_id)