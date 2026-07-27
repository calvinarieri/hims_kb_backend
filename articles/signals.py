from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import Articles, ArticlesVersion, ArticleTag, ArticleImage


def clear_article_caches(article_id=None):
    """
    Clears cache entries related to articles and search results.
    """
    if article_id:
        cache.delete(f"article_detail_{article_id}")

    # Wipe search and staff cached keys pattern or flush
    # In Redis production, use wildcard pattern deletion or cache versioning
    try:
        cache.delete_pattern("search_results_*")
        cache.delete_pattern("staff_articles_*")
    except AttributeError:
        # Fallback if cache backend doesn't support pattern matching
        cache.clear()


@receiver([post_save, post_delete], sender=Articles)
def on_article_change(sender, instance, **kwargs):
    clear_article_caches(instance.id)


@receiver([post_save, post_delete], sender=ArticlesVersion)
def on_version_change(sender, instance, **kwargs):
    clear_article_caches(instance.article_id)


@receiver([post_save, post_delete], sender=ArticleTag)
def on_tag_change(sender, instance, **kwargs):
    clear_article_caches(instance.article_id)


@receiver([post_save, post_delete], sender=ArticleImage)
def on_image_change(sender, instance, **kwargs):
    clear_article_caches(instance.article_id)